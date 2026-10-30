"""Bounded, latest-frame workers and terminal-only performance measurements."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import threading
import time

import numpy as np


def build_background(samples):
    """Original per-pixel median, computed in small strips to bound temporary RAM."""
    if not samples:
        raise ValueError("Background capture needs at least one frame.")
    output = np.empty_like(samples[0])
    for top in range(0, output.shape[0], 48):
        bottom = min(output.shape[0], top + 48)
        stack = np.stack([frame[top:bottom] for frame in samples])
        output[top:bottom] = np.median(stack, axis=0, overwrite_input=True)
    return output


class Profiler:
    def __init__(self, enabled=False, interval=2.0):
        self.enabled = enabled
        self.interval = interval
        self.samples = defaultdict(lambda: deque(maxlen=180))
        self.lock = threading.Lock()
        self.started = time.perf_counter()
        self.frames = 0

    def add(self, stage, seconds):
        if self.enabled:
            with self.lock:
                self.samples[stage].append(seconds * 1000)

    def tick(self, now=None):
        if not self.enabled:
            return
        now = time.perf_counter() if now is None else now
        self.frames += 1
        elapsed = now - self.started
        if elapsed < self.interval:
            return
        with self.lock:
            fields = [f"{name}={np.mean(values):.1f}/{np.percentile(values, 95):.1f}"
                      for name, values in sorted(self.samples.items()) if values]
            self.samples.clear()
        print(f"[Profile] output={self.frames / elapsed:.1f} FPS | ms mean/p95: "
              + " ".join(fields), flush=True)
        self.frames = 0
        self.started = now


@dataclass(frozen=True)
class FramePacket:
    sequence: int
    captured_at: float
    frame: np.ndarray  # Owned by capture; consumers must never modify it.
    need_mask: bool = False
    prepare_effect: bool = False


class LatestFrameCapture:
    """One capture owner, one published frame; no FIFO of old video frames."""
    def __init__(self, capture, profiler=None):
        self.capture = capture
        self.profiler = profiler or Profiler()
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.latest = None
        self.error = None
        self.thread = threading.Thread(target=self._run, name="vanish-capture", daemon=True)
        self.thread.start()

    def _run(self):
        sequence = 0
        failures = 0
        try:
            while not self.stop.is_set():
                started = time.perf_counter()
                ok, frame = self.capture.read()
                now = time.perf_counter()
                self.profiler.add("capture_read", now - started)
                if not ok or frame is None or not frame.size:
                    failures += 1
                    if failures >= 30:
                        raise RuntimeError("Camera stopped sending frames. Close other camera apps and restart.")
                    self.stop.wait(0.03)
                    continue
                failures = 0
                sequence += 1
                with self.condition:
                    self.latest = FramePacket(sequence, now, frame)
                    self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.error = error
                self.condition.notify_all()
        finally:
            self.capture.release()

    def read(self, timeout=0.0):
        with self.condition:
            if self.latest is None and self.error is None and timeout:
                self.condition.wait_for(lambda: self.latest is not None or self.error is not None,
                                        timeout=timeout)
            if self.error is not None:
                raise RuntimeError(str(self.error)) from self.error
            return self.latest

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2.0)
        if self.thread.is_alive():
            # Some drivers block in read until the device is released.
            self.capture.release()
            self.thread.join(timeout=2.0)
        if self.thread.is_alive():
            print("[Camera] Driver is still closing; restart VanishCam if the device stays busy.")


class InferenceWorker:
    """One pending job is replaced on submit. Models live only on this thread."""
    def __init__(self, factory):
        self.factory = factory
        self.condition = threading.Condition()
        self.pending = None
        self.latest = None
        self.error = None
        self.stopping = False
        self.last_submitted = -1
        self.thread = threading.Thread(target=self._run, name="vanish-inference", daemon=True)
        self.thread.start()

    def submit(self, packet):
        with self.condition:
            if packet.sequence <= self.last_submitted or self.stopping:
                return
            self.last_submitted = packet.sequence
            self.pending = packet
            self.condition.notify()

    def poll(self):
        with self.condition:
            if self.error is not None:
                raise RuntimeError(f"Detection worker failed: {self.error}") from self.error
            return self.latest

    def _run(self):
        processor = None
        try:
            processor = self.factory()
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.stopping or self.pending is not None)
                    if self.stopping:
                        break
                    packet = self.pending
                    self.pending = None
                result = processor.process(packet)
                with self.condition:
                    self.latest = result
        except Exception as error:
            with self.condition:
                self.error = error
        finally:
            if processor is not None:
                processor.close()

    def close(self):
        with self.condition:
            self.stopping = True
            self.pending = None
            self.condition.notify_all()
        self.thread.join(timeout=5.0)
        if self.thread.is_alive():
            print("[Detection] Native inference is still shutting down.")


def terminal_key():
    """Poll a Windows console without creating a preview window."""
    try:
        import msvcrt
    except ImportError:
        return -1
    if not msvcrt.kbhit():
        return -1
    value = msvcrt.getwch()
    if value in ("\x00", "\xe0"):
        if msvcrt.kbhit():
            msvcrt.getwch()
        return -1
    return ord(value.lower())
