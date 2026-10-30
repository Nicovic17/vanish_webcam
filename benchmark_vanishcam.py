"""Synthetic 720p effects benchmark; optional live capture/inference test.

Only timings and generated test graphics are saved. Webcam frames stay in RAM.
"""
import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np

from vanish_effects import MODES, DURATIONS, SilhouetteEffect
from naruto_effect import load_log, render_substitution, substitution_anchor


def synthetic_scene(width=1280, height=720):
    background = np.full((height, width, 3), (48, 39, 30), np.uint8)
    for x in range(0, width, max(1, width // 10)):
        cv2.line(background, (x, 0), (x, height - 1), (60, 48, 36), 1)
    frame = background.copy()
    mask = np.zeros((height, width), np.float32)
    cv2.ellipse(mask, (width // 2, int(height * .25)),
                (int(width * .055), int(height * .12)), 0, 0, 360, 1, -1)
    cv2.ellipse(mask, (width // 2, int(height * .67)),
                (int(width * .14), int(height * .34)), 0, 0, 360, 1, -1)
    frame[mask > .5] = (175, 105, 65)
    cv2.ellipse(frame, (width // 2, int(height * .25)),
                (int(width * .055), int(height * .12)), 0, 0, 360, (125, 170, 200), -1)
    return frame, background, mask


def summary(values):
    return {"mean_ms": round(float(np.mean(values)), 2),
            "p95_ms": round(float(np.percentile(values, 95)), 2)}


def effects_benchmark(preview=None):
    frame, background, mask = synthetic_scene()
    sprite = load_log()
    result, rows = {}, []
    for mode, label, _ in MODES:
        prep = time.perf_counter()
        effect = SilhouetteEffect(frame, mask, mode) if mode != "naruto" else None
        anchor = substitution_anchor(mask)
        cache, smoke = {}, {}
        prepare_ms = (time.perf_counter() - prep) * 1000
        def render(progress):
            if effect:
                return effect.render(background, progress)
            return render_substitution(frame, background, mask, sprite, anchor,
                                       progress * DURATIONS[mode], cache, smoke)
        render(.01)  # Warm the OpenCV kernels and sprite cache.
        values = []
        for progress in np.linspace(.03, .97, 90):
            start = time.perf_counter()
            render(float(progress))
            values.append((time.perf_counter() - start) * 1000)
        result[mode] = dict(summary(values), prepare_ms=round(prepare_ms, 2))
        if preview:
            tiles = [cv2.resize(render(p), (320, 180)) for p in (.08, .35, .65, 1)]
            row = np.full((210, 1280, 3), 20, np.uint8)
            row[30:] = np.hstack(tiles)
            cv2.putText(row, label + " | 8%, 35%, 65%, 100%", (12, 21),
                        cv2.FONT_HERSHEY_SIMPLEX, .55, (230, 230, 230), 1, cv2.LINE_AA)
            rows.append(row)
    if preview:
        cv2.imwrite(str(preview), np.vstack(rows))
    return result


def live_benchmark(seconds, mode):
    from types import SimpleNamespace
    from contextlib import ExitStack
    from vanish_cam import open_camera, SEGMENTER_MODEL, HAND_MODEL, FACE_MODEL
    from vanish_runtime import LatestFrameCapture, InferenceWorker, Profiler
    from vanish_vision import VisionProcessor
    args = SimpleNamespace(gesture_frames=3, gesture_release_frames=5,
                           detection_width=640, detection_light=False)
    profiler = Profiler(enabled=True, interval=99999)
    frame, background, mask = synthetic_scene()
    effect = SilhouetteEffect(frame, mask, mode)
    with ExitStack() as resources:
        cap = open_camera(0, 1280, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        reader = LatestFrameCapture(cap, profiler)
        resources.callback(reader.close)
        if reader.read(timeout=5) is None:
            raise RuntimeError("Camera did not deliver a frame")
        worker = InferenceWorker(lambda: VisionProcessor(args, mode, profiler, SEGMENTER_MODEL, HAND_MODEL, FACE_MODEL))
        resources.callback(worker.close)
        # Warm inference before measuring steady-state frame scheduling.
        deadline = time.perf_counter() + 8
        while worker.poll() is None:
            worker.submit(reader.read())
            if time.perf_counter() > deadline:
                raise RuntimeError("Inference startup timed out")
            time.sleep(.01)
        with profiler.lock:
            profiler.samples.clear()
        start = time.perf_counter()
        next_frame = start
        count, captured, detected = 0, set(), set()
        latencies = []
        while time.perf_counter() - start < seconds:
            tick = time.perf_counter()
            packet = reader.read()
            captured.add(packet.sequence)
            latencies.append((tick - packet.captured_at) * 1000)
            worker.submit(packet)
            result = worker.poll()
            if result:
                detected.add(result.sequence)
                profiler.add("detection_age", tick - result.captured_at)
            effect.render(background, ((tick - start) % DURATIONS[mode]) / DURATIONS[mode])
            profiler.add("render_loop", time.perf_counter() - tick)
            count += 1
            next_frame += 1 / 30
            delay = next_frame - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_frame = time.perf_counter()
        elapsed = time.perf_counter() - start
        with profiler.lock:
            stages = {key: summary(values) for key, values in profiler.samples.items() if values}
        return dict(output_fps=round(count / elapsed, 2), fresh_capture_fps=round(len(captured) / elapsed, 2),
                    inference_fps=round(len(detected) / elapsed, 2), capture_age=summary(latencies), stages=stages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use camera transiently; never save its frames")
    parser.add_argument("--seconds", type=float, default=12)
    parser.add_argument("--mode", choices=[m[0] for m in MODES if m[0] != "naruto"], default="normal")
    parser.add_argument("--output", default="diagnostics")
    args = parser.parse_args()
    cv2.setNumThreads(1)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.live:
        data = live_benchmark(args.seconds, args.mode)
        name = f"live-{args.mode}.json"
    else:
        data = effects_benchmark(output / "effects-preview.png")
        name = "effects-720p.json"
    (output / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
