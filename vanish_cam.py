"""Webcam locale: dissolvenza avviata dal gesto con indice e medio a V."""

from __future__ import annotations

from vanish_hud import guidance, draw_guidance
import argparse
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from gesture_detection import victory_score
from vanish_effects import MODES, DURATIONS, SilhouetteEffect
from vanish_runtime import InferenceWorker, LatestFrameCapture, Profiler, terminal_key, build_background
from vanish_vision import VisionProcessor

try:
    from .naruto_effect import (
        EFFECT_SECONDS, joined_hands_from_landmarks, landed_log_anchor,
        load_log, overlay_log, render_substitution, substitution_anchor,
    )
    from .vanish_sound import SOUND_PATH, VanishSound, ProceduralSound
except ImportError:
    from naruto_effect import (
        EFFECT_SECONDS, joined_hands_from_landmarks, landed_log_anchor,
        load_log, overlay_log, render_substitution, substitution_anchor,
    )
    from vanish_sound import SOUND_PATH, VanishSound, ProceduralSound


APP_DIR = Path(__file__).resolve().parent
MODEL_DIR = APP_DIR / "models"
WINDOW_NAME = "Webcam - Anteprima"

SEGMENTER_MODEL = MODEL_DIR / "selfie_segmenter_landscape.tflite"
GESTURE_MODEL = MODEL_DIR / "gesture_recognizer.task"
HAND_MODEL = APP_DIR / "hand_landmarker.task"
FACE_MODEL = APP_DIR / "face_landmarker.task"

MODEL_URLS = {
    SEGMENTER_MODEL: (
        "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
        "selfie_segmenter_landscape/float16/latest/"
        "selfie_segmenter_landscape.tflite"
    ),
    GESTURE_MODEL: (
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
        "gesture_recognizer/float16/1/gesture_recognizer.task"
    ),
}

CALIBRATION_SECONDS = 4.0
BACKGROUND_SAMPLE_SECONDS = 0.55
VANISH_SECONDS = 3.6
GESTURE_INTERVAL_SECONDS = 0.14


@dataclass
class AppState:
    phase: str = "calibrating"
    calibration_started: float = 0.0
    vanish_started: float | None = None
    last_gesture_check: float = 0.0
    fullscreen: bool = False


def positive_fps(value: str) -> float:
    fps = float(value)
    if not np.isfinite(fps) or not 1 <= fps <= 120:
        raise argparse.ArgumentTypeError("Gli FPS devono essere compresi tra 1 e 120.")
    return fps


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Value must be positive.")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local silhouette effects with automatic virtual-camera output."
    )
    parser.add_argument("--camera", type=int, default=0, help="Indice della webcam")
    parser.add_argument("--width", type=positive_int, default=1280, help="Capture width (default: 1280)")
    parser.add_argument("--height", type=positive_int, default=720, help="Capture height (default: 720)")
    parser.add_argument(
        "--fullscreen", action="store_true", help="Avvia a schermo intero"
    )
    parser.add_argument(
        "--no-mirror", action="store_true", help="Non specchiare la webcam"
    )
    parser.add_argument("--fps", type=positive_fps, default=30.0, help="FPS massimi dell'uscita virtuale (default: 30)")
    parser.add_argument(
        "--virtual-camera", action=argparse.BooleanOptionalAction, default=None,
        help="Richiede la webcam virtuale; per default si attiva se disponibile. --no-virtual-camera la disattiva",
    )
    parser.add_argument(
        "--virtual-backend", choices=("obs", "unitycapture", "v4l2loopback"),
        help="Driver della webcam virtuale da usare",
    )
    parser.add_argument("--virtual-device", help="Nome del dispositivo virtuale da usare")
    parser.add_argument(
        "--mode", choices=tuple(item[0] for item in MODES),
        help="Salta il menu iniziale e avvia direttamente la modalità scelta",
    )
    parser.add_argument(
        "--gesture-debug", action="store_true",
        help="Stampa nel terminale lo stato del riconoscimento (senza scritte nel video)",
    )
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--profile", action="store_true", help="Terminal FPS and mean/p95 stage timings")
    parser.add_argument("--headless", action="store_true", help="No GUI; virtual camera required, console menu and keys")
    parser.add_argument("--detection-width", type=positive_int, default=640, help="Inference copy width (default: 640)")
    parser.add_argument("--detection-light", action="store_true", help="Mild contrast normalization on detection only")
    parser.add_argument("--gesture-frames", type=positive_int, default=3, help="Consecutive detections to trigger")
    parser.add_argument("--gesture-release-frames", type=positive_int, default=5, help="Clear misses to rearm gesture")
    parser.add_argument("--duration", type=float, default=0, help="Stop after this many seconds (0: until Q/ESC/Ctrl+C)")
    return parser.parse_args()


def choose_mode(headless=False) -> str | None:
    """Simple keyboard/mouse menu shown before the clean camera feed."""
    title = "Scegli effetto"
    selected = [None]
    if headless:
        for index, (_, label, detail) in enumerate(MODES, 1):
            print(f"{index}. {label}: {detail}")
        while True:
            answer = input("Choose 1-8 (Q to quit): ").strip().lower()
            if answer in ("q", "quit"):
                return None
            if answer in tuple(str(i) for i in range(1, len(MODES) + 1)):
                return MODES[int(answer) - 1][0]
    window = np.zeros((740, 800, 3), dtype=np.uint8)
    window[:] = (26, 29, 34)
    cv2.putText(window, "SCEGLI IL TUO VANISH", (68, 88),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (236, 239, 242), 2, cv2.LINE_AA)
    buttons = tuple((mode, f"{index + 1}  {label}", detail, 115 + index * 75)
                    for index, (mode, label, detail) in enumerate(MODES))
    for mode, heading, detail, top in buttons:
        cv2.rectangle(window, (65, top), (735, top + 65), (48, 54, 62), -1, cv2.LINE_AA)
        cv2.rectangle(window, (65, top), (735, top + 65), (111, 142, 153), 2, cv2.LINE_AA)
        cv2.putText(window, heading, (90, top + 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (240, 245, 247), 1, cv2.LINE_AA)
        cv2.putText(window, detail, (90, top + 51),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (179, 195, 201), 1, cv2.LINE_AA)

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONUP and 65 <= x <= 735:
            for mode, _, _, top in buttons:
                if top <= y <= top + 65:
                    selected[0] = mode

    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(title, on_mouse)
    try:
        while selected[0] is None:
            cv2.imshow(title, window)
            key = cv2.waitKey(30) & 0xFF
            if ord("1") <= key < ord("1") + len(MODES):
                selected[0] = MODES[key - ord("1")][0]
            elif key in (ord("q"), 27):
                return None
            if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                return None
        return selected[0]
    finally:
        cv2.destroyWindow(title)


def open_virtual_camera(args: argparse.Namespace, width: int, height: int):
    if args.virtual_camera is False:
        return None
    errors = []
    backends = ([args.virtual_backend] if args.virtual_backend else
                ["obs", "unitycapture"] if platform.system() == "Windows" else
                ["v4l2loopback"] if platform.system() == "Linux" else ["obs"])
    for backend in backends:
        try:
            import pyvirtualcam
            camera = pyvirtualcam.Camera(
                width=width, height=height, fps=args.fps,
                fmt=pyvirtualcam.PixelFormat.RGB, backend=backend, device=args.virtual_device)
            print(f"[Camera] {camera.device}: {width}x{height} at {args.fps:g} FPS. "
                  "Select this device in your meeting app. Keep OBS Virtual Camera stopped.")
            return camera
        except (ImportError, RuntimeError, OSError, ValueError) as error:
            errors.append(f"{backend}: {error}")
    message = virtual_camera_help() + "\n" + "\n".join(errors)
    if args.virtual_camera is True or args.virtual_backend or args.virtual_device or getattr(args, "headless", False):
        raise RuntimeError(message)
    print(f"[Camera] {message}\n[Camera] Preview only; other apps cannot receive the effect yet.")
    return None


def virtual_camera_help():
    if platform.system() != "Windows":
        return "Install/configure the OBS virtual camera (macOS) or v4l2loopback (Linux), then restart."
    installed = any((Path(os.environ.get(key, "C:/Program Files")) / "obs-studio/bin/64bit/obs64.exe").is_file()
                    for key in ("ProgramFiles", "ProgramFiles(x86)"))
    registered = False
    try:
        import winreg
        category = r"CLSID\{860BB310-5D01-11D0-BD3B-00A0C911CE86}\Instance"
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, category) as key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                with winreg.OpenKey(key, winreg.EnumKey(key, index)) as device:
                    try:
                        name = winreg.QueryValueEx(device, "FriendlyName")[0]
                        registered |= "obs" in name.lower()
                    except OSError:
                        pass
    except (ImportError, OSError):
        pass
    if registered:
        return ("OBS Virtual Camera is registered but unavailable. Stop Virtual Camera in OBS; "
                "close other VanishCam instances. Open OBS once, Start Virtual Camera, then Stop it and retry.")
    if installed:
        return ("OBS is installed but its virtual camera is not registered. Open OBS once, click Start Virtual Camera, "
                "then Stop. If missing, run obs-studio/data/obs-plugins/win-dshow/virtualcam-install.bat "
                "as administrator and restart your meeting app.")
    return ("Install OBS Studio from https://obsproject.com/download (includes OBS Virtual Camera). "
            "Open OBS once, Start Virtual Camera, then Stop it. Restart VanishCam and your meeting app. "
            "Unity Capture is the alternative backend.")


def send_virtual_frame(camera, frame: np.ndarray, rgb_buffer=None) -> None:
    if frame.shape[:2] != (camera.height, camera.width):
        frame = cv2.resize(frame, (camera.width, camera.height), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB, dst=rgb_buffer)
    camera.send(rgb)


def download_models(mode: str = "normal") -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for destination, url in MODEL_URLS.items():
        if mode == "naruto" and destination == GESTURE_MODEL:
            continue
        if destination.exists() and destination.stat().st_size > 100_000:
            continue

        temporary = destination.with_suffix(destination.suffix + ".part")
        print(f"[Vanish Lab] Scarico {destination.name}...")
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Vanish-Lab/1.0"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                total = int(response.headers.get("Content-Length", 0))
                received = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(1024 * 256):
                        output.write(chunk)
                        received += len(chunk)
                        if total:
                            percent = int(received * 100 / total)
                            print(f"\r  {percent:3d}%", end="", flush=True)
            print()
            os.replace(temporary, destination)
        except (OSError, urllib.error.URLError) as error:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(
                "Non riesco a scaricare i modelli MediaPipe. "
                "Controlla la connessione internet e riprova."
            ) from error


def open_camera(index: int, width: int, height: int) -> cv2.VideoCapture:
    if platform.system() == "Windows":
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(index)
    else:
        capture = cv2.VideoCapture(index)

    if not capture.isOpened():
        raise RuntimeError(
            f"Webcam {index} non disponibile. Chiudi le altre app oppure prova --camera 1."
        )

    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def create_tasks(mode: str = "normal") -> tuple[vision.ImageSegmenter, MultiViewGestureRecognizer | MultiViewHandLandmarker]:
    segmenter_options = vision.ImageSegmenterOptions(
        base_options=python.BaseOptions(model_asset_path=str(SEGMENTER_MODEL)),
        running_mode=vision.RunningMode.VIDEO,
        output_confidence_masks=True,
        output_category_mask=False,
    )
    if mode == "naruto":
        if not HAND_MODEL.is_file():
            raise RuntimeError(f"Modello delle mani non trovato: {HAND_MODEL}")
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(HAND_MODEL)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.35,
            min_hand_presence_confidence=0.35,
            min_tracking_confidence=0.45,
        )
        task_class = vision.HandLandmarker
        wrapper_class = MultiViewHandLandmarker
    else:
        classifier_options = mp.tasks.components.processors.ClassifierOptions(
            score_threshold=0.55,
            category_allowlist=["Victory"],
        )
        options = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(model_asset_path=str(GESTURE_MODEL)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.35,
            min_hand_presence_confidence=0.35,
            min_tracking_confidence=0.5,
            canned_gesture_classifier_options=classifier_options,
        )
        task_class = vision.GestureRecognizer
        wrapper_class = MultiViewGestureRecognizer

    segmenter = vision.ImageSegmenter.create_from_options(segmenter_options)
    try:
        primary = task_class.create_from_options(options)
        try:
            alternate = task_class.create_from_options(
                replace(options, running_mode=vision.RunningMode.IMAGE)
            )
        except Exception:
            primary.close()
            raise
    except Exception:
        segmenter.close()
        raise
    return segmenter, wrapper_class(primary, alternate)


def smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    values = np.clip((values - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return values * values * (3.0 - 2.0 * values)


def ease_in_out_cubic(value: float) -> float:
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def make_dissolve_fields(height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(7391)
    y, x = np.mgrid[0:height, 0:width]
    y_normal = y.astype(np.float32) / max(height - 1, 1)
    x_normal = x.astype(np.float32) / max(width - 1, 1)
    low_noise = rng.random((max(2, height // 10), max(2, width // 10)), dtype=np.float32)
    low_noise = cv2.resize(low_noise, (width, height), interpolation=cv2.INTER_CUBIC)
    fine_noise = rng.random((height, width), dtype=np.float32)
    field = (
        (1.0 - y_normal) * 0.72
        + low_noise * 0.17
        + fine_noise * 0.08
        + np.sin(x_normal * 18.0) * 0.025
    )
    return np.clip(field, 0.0, 1.0), fine_noise


def person_mask(
    segmenter: vision.ImageSegmenter,
    image: mp.Image,
    timestamp_ms: int,
    width: int,
    height: int,
) -> np.ndarray:
    result = segmenter.segment_for_video(image, timestamp_ms)
    if not result.confidence_masks:
        return np.zeros((height, width), dtype=np.float32)
    raw = np.squeeze(result.confidence_masks[0].numpy_view()).astype(np.float32)
    resized = cv2.resize(raw, (width, height), interpolation=cv2.INTER_LINEAR)
    resized = cv2.GaussianBlur(resized, (0, 0), sigmaX=2.2, sigmaY=2.2)
    return np.clip((resized - 0.12) / 0.68, 0.0, 1.0)


def alpha_composite(person: np.ndarray, background: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    alpha_3 = alpha[:, :, None]
    return (
        person.astype(np.float32) * alpha_3
        + background.astype(np.float32) * (1.0 - alpha_3)
    ).astype(np.uint8)


def apply_dissolve(
    frame: np.ndarray,
    background: np.ndarray,
    mask: np.ndarray,
    progress: float,
    field: np.ndarray,
    sparkle_noise: np.ndarray,
) -> np.ndarray:
    if progress <= 0.002:
        return alpha_composite(frame, background, mask)
    if progress >= 0.999:
        return background.copy()

    points = cv2.findNonZero((mask > 0.01).astype(np.uint8))
    if points is None:
        return background.copy()
    x, y, width, height = cv2.boundingRect(points)
    left, top = max(0, x - 18), max(0, y - 18)
    right = min(mask.shape[1], x + width + 18)
    bottom = min(mask.shape[0], y + height + 18)
    area = np.s_[top:bottom, left:right]
    mask = mask[area]
    field = field[area]
    sparkle_noise = sparkle_noise[area]
    eased = ease_in_out_cubic(progress)
    survival = smoothstep(eased - 0.055, eased + 0.055, field)
    alpha = mask * survival
    output = alpha_composite(frame[area], background[area], alpha)
    edge = (
        (np.abs(field - eased) < 0.018)
        & (mask > 0.48)
        & (sparkle_noise > 0.54)
    ).astype(np.float32)
    glow = cv2.GaussianBlur(edge, (0, 0), sigmaX=5.0, sigmaY=5.0)
    glow = np.clip(glow * 5.0 + edge, 0.0, 1.0)[:, :, None]
    cyan = np.full_like(output, (255, 228, 92), dtype=np.uint8)
    result = np.clip(
        output.astype(np.float32) * (1.0 - glow * 0.8)
        + cyan.astype(np.float32) * glow * 0.8,
        0,
        255,
    ).astype(np.uint8)
    canvas = background.copy()
    canvas[area] = result
    return canvas


def victory_landmark_score(points: np.ndarray) -> float:
    """Rotation-independent joint-angle and palm-relative V-sign score."""
    return victory_score(points)


def classify_gesture_result(
    result: vision.GestureRecognizerResult,
    image: mp.Image,
) -> tuple[str, float]:
    # I landmark vengono restituiti anche quando il classificatore non riconosce
    # "Victory" (ad esempio con il dorso della mano rivolto alla webcam).
    for landmarks in result.hand_world_landmarks:
        points = np.array([(point.x, point.y, point.z) for point in landmarks])
        score = victory_landmark_score(points)
        if score:
            return "Victory", score
    # Controlla SEMPRE anche la geometria visibile: la profondita' stimata
    # puo' essere imprecisa quando palmo e dita piegate sono nascosti.
    for landmarks in result.hand_landmarks:
        points = np.array([(point.x * image.width, point.y * image.height, 0.0)
                           for point in landmarks])
        score = victory_landmark_score(points)
        if score:
            return "Victory", score
    for categories in result.gestures:
        for category in categories:
            if category.category_name == "Victory" and category.score >= 0.62:
                return "Victory", float(category.score)
    if result.hand_landmarks or result.hand_world_landmarks:
        return "Hand_Detected", 0.0
    return "No_Hand", 0.0


class MultiViewGestureRecognizer:
    """Riprova la rilevazione su fotogrammi ruotati senza alterare il tracking."""

    def __init__(self, primary, alternate):
        self.primary = primary
        self.alternate = alternate
        self.preferred_rotation: int | None = None
        self.preferred_crop: str | None = None
        self.next_retry_ms = 0
        self.retry_cursor = 0

    def recognize_gesture(self, image: mp.Image, timestamp_ms: int) -> tuple[str, float]:
        result = self.primary.recognize_for_video(image, timestamp_ms)
        best = classify_gesture_result(result, image)
        if best[0] == "Victory":
            self.preferred_rotation = None
            self.preferred_crop = None
            return best
        if timestamp_ms < self.next_retry_ms:
            return best

        # IMAGE forza una nuova rilevazione; il modello VIDEO resta sul frame
        # originale. Evita timestamp/tracking incoerenti tra rotazioni diverse.
        rgb = image.numpy_view()
        height, width = rgb.shape[:2]
        # Il palmo nella posa laterale e' spesso troppo piccolo nel frame
        # completo. I due ritagli inferiori si sovrappongono e coprono entrambe
        # le mani, anche quando l'immagine e' specchiata.
        crops = {
            "full": rgb,
            "lower_left": rgb[int(height * 0.28):, :int(width * 0.78)],
            "lower_right": rgb[int(height * 0.28):, int(width * 0.22):],
        }
        views = [("full", rotation) for rotation in (0, 1, 3, 2)]
        views += [(crop, rotation) for crop in ("lower_left", "lower_right")
                  for rotation in (0, 1, 3)]
        preferred = (self.preferred_crop, self.preferred_rotation)
        selected = []
        if preferred in views:
            selected.append(preferred)
        # Spread the expensive IMAGE attempts over successive video frames.
        while len(selected) < 3:
            view = views[self.retry_cursor % len(views)]
            self.retry_cursor += 1
            if view not in selected:
                selected.append(view)
        for crop, rotation in selected:
            rotated = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(np.rot90(crops[crop], rotation)),
            )
            result = self.alternate.recognize(rotated)
            candidate = classify_gesture_result(result, rotated)
            if candidate[0] == "Victory":
                self.preferred_rotation = rotation
                self.preferred_crop = crop
                self.next_retry_ms = timestamp_ms + int(GESTURE_INTERVAL_SECONDS * 1000)
                return candidate
            if candidate[0] == "Hand_Detected":
                best = candidate
        self.preferred_rotation = None
        self.preferred_crop = None
        self.next_retry_ms = timestamp_ms + int(GESTURE_INTERVAL_SECONDS * 1000)
        return best

    def close(self) -> None:
        try:
            self.primary.close()
        finally:
            self.alternate.close()


class MultiViewHandLandmarker:
    """Track two hands in video and retry difficult views with the hand model."""

    def __init__(self, primary, alternate):
        self.primary = primary
        self.alternate = alternate
        self.preferred_view: tuple[str, int] | None = None
        self.next_retry_ms = 0
        self.last_hand_count = 0
        self.retry_cursor = 0

    def recognize_joined_hands(self, image: mp.Image, timestamp_ms: int) -> bool:
        result = self.primary.detect_for_video(image, timestamp_ms)
        self.last_hand_count = len(result.hand_landmarks)
        if joined_hands_from_landmarks(result.hand_landmarks, image.width, image.height):
            self.preferred_view = None
            return True
        if timestamp_ms < self.next_retry_ms:
            return False

        rgb = image.numpy_view()
        height, width = rgb.shape[:2]
        views = {
            "full": rgb,
            "center": rgb[int(height * 0.18):, int(width * 0.12):int(width * 0.88)],
            "lower_left": rgb[int(height * 0.22):, :int(width * 0.78)],
            "lower_right": rgb[int(height * 0.22):, int(width * 0.22):],
        }
        attempts = [("full", rotation) for rotation in (1, 3, 2)]
        attempts += [("center", rotation) for rotation in (0, 1, 3)]
        attempts += [("lower_left", 0), ("lower_right", 0)]
        selected = []
        if self.preferred_view in attempts:
            selected.append(self.preferred_view)
        while len(selected) < 2:
            view = attempts[self.retry_cursor % len(attempts)]
            self.retry_cursor += 1
            if view not in selected:
                selected.append(view)
        for crop, rotation in selected:
            rotated = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(np.rot90(views[crop], rotation)),
            )
            result = self.alternate.detect(rotated)
            self.last_hand_count = max(self.last_hand_count, len(result.hand_landmarks))
            if joined_hands_from_landmarks(result.hand_landmarks, rotated.width, rotated.height):
                self.preferred_view = (crop, rotation)
                self.next_retry_ms = timestamp_ms + 90
                return True
        self.preferred_view = None
        self.next_retry_ms = timestamp_ms + 80
        return False

    def close(self) -> None:
        try:
            self.primary.close()
        finally:
            self.alternate.close()


def recognize_gesture(
    recognizer: MultiViewGestureRecognizer,
    image: mp.Image,
    timestamp_ms: int,
) -> tuple[str, float]:
    if isinstance(recognizer, MultiViewGestureRecognizer):
        return recognizer.recognize_gesture(image, timestamp_ms)
    return classify_gesture_result(recognizer.recognize_for_video(image, timestamp_ms), image)


def start_vanish_on_gesture(state: AppState, name: str, score: float, now: float) -> bool:
    """Avvia la dissolvenza al primo riconoscimento affidabile della V."""
    if state.phase == "ready" and name == "Victory" and score >= 0.62:
        state.phase = "vanishing"
        state.vanish_started = now
        return True
    return False


def start_naruto_on_join(state: AppState, joined: bool, now: float) -> bool:
    if state.phase == "ready" and joined:
        state.phase = "naruto_vanishing"
        state.vanish_started = now
        return True
    return False


def set_fullscreen(enabled: bool) -> None:
    mode = cv2.WINDOW_FULLSCREEN if enabled else cv2.WINDOW_NORMAL
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, mode)


def self_test() -> int:
    """Initialize both worker configurations without opening or recording a camera."""
    required = (SEGMENTER_MODEL, HAND_MODEL, FACE_MODEL, SOUND_PATH)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing resources: {', '.join(missing)}")
    load_log()
    from types import SimpleNamespace
    args = SimpleNamespace(gesture_frames=3, gesture_release_frames=5,
                           detection_light=False, detection_width=640)
    for mode in ("normal", "goku"):
        processor = VisionProcessor(args, mode, Profiler(), SEGMENTER_MODEL, HAND_MODEL, FACE_MODEL)
        processor.close()
    from vanish_sound import synthesized_samples
    for mode in ("burn", "whoosh", "goku"):
        assert synthesized_samples(mode).shape[1] == 2
    print("[Webcam] Self-test passed: hand/face models, segmentation, assets and generated audio.")
    return 0


def run() -> int:
    args = parse_args()
    # The default 20 OpenCV threads added substantial scheduling overhead here.
    cv2.setNumThreads(1)
    if getattr(args, "self_test", False):
        return self_test()
    if args.headless and args.virtual_camera is False:
        raise ValueError("--headless requires virtual-camera output. Remove --no-virtual-camera.")
    if not np.isfinite(args.duration) or args.duration < 0:
        raise ValueError("--duration must be zero or a positive finite number.")
    mode = args.mode or choose_mode(headless=args.headless)
    if mode is None:
        return 0
    with ExitStack() as resources:
        return run_camera(args, resources, mode)


def make_sound(mode):
    if mode == "normal":
        return None
    try:
        if mode == "naruto":
            return VanishSound()
        teleport = APP_DIR / "assets" / "teleport.MP3"
        if mode == "goku" and teleport.is_file():
            return VanishSound(teleport)
        return ProceduralSound(mode)
    except Exception as error:
        print(f"[Audio] Sound unavailable; video continues. {error}")
        return None


def run_camera(args: argparse.Namespace, resources: ExitStack, mode: str) -> int:
    download_models(mode)
    profiler = Profiler(args.profile)
    capture = open_camera(args.camera, args.width, args.height)
    capture.set(cv2.CAP_PROP_FPS, args.fps)
    reader = LatestFrameCapture(capture, profiler)
    resources.callback(reader.close)
    first = reader.read(timeout=5.0)
    if first is None:
        raise RuntimeError("No camera frame received in 5 seconds. Check Windows Camera permissions.")
    height, width = first.frame.shape[:2]
    print(f"[Camera] Capture {width}x{height}; requested {args.width}x{args.height} at {args.fps:g} FPS (MJPG requested).")
    virtual_camera = open_virtual_camera(args, width, height)
    if virtual_camera is not None:
        resources.callback(virtual_camera.close)
    elif args.headless:
        raise RuntimeError("Headless mode requires a working virtual camera.")
    worker = InferenceWorker(lambda: VisionProcessor(args, mode, profiler, SEGMENTER_MODEL, HAND_MODEL, FACE_MODEL))
    resources.callback(worker.close)
    sound = make_sound(mode)
    if sound is not None:
        resources.callback(sound.close)
    log_sprite = load_log() if mode == "naruto" else None
    log_cache, smoke_cache = {}, {}
    if not args.headless:
        resources.callback(cv2.destroyAllWindows)
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, width, height)
        if args.fullscreen:
            set_fullscreen(True)
    rgb_buffer, preview_buffer = np.empty_like(first.frame), np.empty_like(first.frame)
    state = AppState(calibration_started=time.perf_counter(), fullscreen=args.fullscreen)
    background = None
    background_samples = []
    background_builder = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vanish-background")
    resources.callback(background_builder.shutdown, wait=True, cancel_futures=True)
    background_future = None
    sample_sequence = -1
    effect = None
    effect_mask = None
    effect_frame = None
    log_anchor = None
    vanished_frame = None
    pending = None
    pending_since = 0.0
    seen_event = 0
    start_progress = 0.0
    last_report = 0.0
    calibration_remaining = None
    ready_at = None
    camera_dark = False
    muted = False
    notice = None
    notice_until = 0.0
    started = time.perf_counter()
    profiler.started = started
    deadline = started
    last_frame_at = started
    print("[Webcam] Step completely out of frame for 4 seconds to capture the background.")
    print("[Webcam] SPACE: new background | H: help | M: mute | F: fullscreen | Q/ESC: quit.")
    print("[Webcam] " + ("Goku: hold two fingers together at your forehead for 1 second. Lower hand before repeating."
                         if mode == "goku" else "V: disappear | R: reappear. Release the gesture before triggering again."))
    if args.headless:
        print("[Webcam] Headless: use keys in this terminal; no preview window is created.")
    try:
        while True:
            tick = time.perf_counter()
            packet = reader.read()
            if packet is None:
                time.sleep(.001)
                continue
            if tick - packet.captured_at > 2.0:
                raise RuntimeError("Camera frames are stale. Close other camera apps and restart.")
            camera_frame = packet.frame
            dark_now = not np.any(camera_frame[::32, ::32] > 3)
            if dark_now and not camera_dark:
                print("[Camera] Image is black. Check the webcam privacy shutter/switch or room lighting.")
            camera_dark = dark_now
            if camera_dark and state.phase == "calibrating":
                state.calibration_started = tick
                background_samples.clear()
                if background_future is not None:
                    background_future.cancel()
                    background_future = None
            if camera_frame.shape[:2] != (height, width):
                raise RuntimeError("Camera resolution changed while running. Restart with the new resolution.")
            worker.submit(replace(packet, need_mask=bool(pending) or (mode == "normal" and state.phase == "vanishing"),
                                  prepare_effect=bool(pending)))
            result = worker.poll()
            profiler.add("capture_age", max(0, tick - packet.captured_at))
            fresh = result is not None and tick - result.captured_at < .45
            mask_fresh = (result is not None and result.mask is not None and
                          tick - (result.mask_at if result.mask_at is not None else result.captured_at) < .45)
            if result is not None:
                profiler.add("detection_age", tick - result.captured_at)
                if args.gesture_debug and tick - last_report >= 1:
                    print(f"[Gesture] {result.debug}" + (" STALE" if not fresh else ""))
                    last_report = tick
                if result.event_id > seen_event:
                    seen_event = result.event_id
                    if tick - result.event_at < 1.5:
                        if state.phase == "ready":
                            pending, pending_since = "vanish", result.event_at
                        elif state.phase == "vanished":
                            pending, pending_since = "return", result.event_at
            if state.phase == "calibrating":
                elapsed = tick - state.calibration_started
                remaining = max(0, int(np.ceil(CALIBRATION_SECONDS - elapsed)))
                if remaining != calibration_remaining:
                    print(f"[Webcam] Background capture: {remaining} seconds.")
                    calibration_remaining = remaining
                if (background_future is None and elapsed >= CALIBRATION_SECONDS - BACKGROUND_SAMPLE_SECONDS
                        and packet.sequence != sample_sequence):
                    background_samples.append(camera_frame.copy())
                    background_samples[:] = background_samples[-18:]
                    sample_sequence = packet.sequence
                if elapsed >= CALIBRATION_SECONDS and background_future is None:
                    background_future = background_builder.submit(
                        build_background, tuple(background_samples) or (camera_frame.copy(),))
                    background_samples.clear()
                if background_future is not None and background_future.done():
                    background = background_future.result()
                    background_future = None
                    state.phase = "ready"
                    ready_at = tick
                    print("[Webcam] Background ready. Step back into view.")
            if pending and background is not None and result is not None and result.prepared is not None:
                prepared = result.prepared
                if (prepared.captured_at >= pending_since - .001
                        and tick - prepared.captured_at < 1.5):
                    effect_frame, effect_mask = prepared.frame, prepared.mask
                    if mode == "naruto":
                        log_anchor = prepared.anchor
                        log_cache.clear()
                        smoke_cache.clear()
                        state.phase = "naruto_returning" if pending == "return" else "naruto_vanishing"
                    else:
                        effect = prepared.effect
                        state.phase = "returning" if pending == "return" else "vanishing"
                    start_progress = 1.0 if pending == "return" else 0.0
                    state.vanish_started = time.perf_counter()
                    vanished_frame = None
                    pending = None
                    if sound and not muted:
                        try:
                            sound.play()
                        except Exception as error:
                            muted = True
                            notice = ("SOUND UNAVAILABLE - VIDEO CONTINUES", "Press M to retry sound", "", 0)
                            notice_until = tick + 5
                            print(f"[Audio] Playback failed; muted until M is pressed: {error}")
                elif tick - pending_since > 1.5:
                    print("[Gesture] No clear silhouette yet. Lower your hand, step into view, and try again.")
                    notice = ("NO CLEAR SILHOUETTE", "Lower your hand, stay fully in view, then repeat the sign", "", 0)
                    notice_until = tick + 5
                    pending = None
            elif pending and tick - pending_since > 1.5:
                print("[Gesture] Waiting for fresh detection; lower your hand, then try again.")
                notice = ("DETECTION NOT READY", "Lower your hand, keep face and hands visible, then retry", "", 0)
                notice_until = tick + 5
                pending = None

            render_start = time.perf_counter()
            display = camera_frame
            if state.phase == "vanished":
                display = vanished_frame if vanished_frame is not None else background
            elif state.phase in ("naruto_vanishing", "naruto_returning"):
                returning = state.phase == "naruto_returning"
                age = time.perf_counter() - state.vanish_started
                display = render_substitution(effect_frame, background, effect_mask,
                                              log_sprite, log_anchor, max(0, EFFECT_SECONDS-age) if returning else age, log_cache, smoke_cache)
                if age >= EFFECT_SECONDS:
                    state.phase = "ready" if returning else "vanished"
                    vanished_frame = None if returning else display
                    if returning:
                        display = camera_frame
            elif state.phase in ("vanishing", "returning"):
                age = time.perf_counter() - state.vanish_started
                duration = DURATIONS[mode]
                returning = state.phase == "returning"
                progress = max(0, start_progress - age / duration) if returning else min(1, start_progress + age / duration)
                # Normal mode keeps tracking the live silhouette during dissolution.
                display = effect.render(background, progress,
                                        live_frame=camera_frame if mode == "normal" and not returning else None,
                                        live_mask=result.mask if mode == "normal" and not returning and mask_fresh else None)
                if (returning and progress <= 0) or (not returning and progress >= 1):
                    state.phase = "ready" if returning else "vanished"
                    vanished_frame = None if returning else background
                    if returning:
                        display = camera_frame
            profiler.add("render", time.perf_counter() - render_start)
            send_start = time.perf_counter()
            if virtual_camera is not None:
                send_virtual_frame(virtual_camera, display, rgb_buffer)
            profiler.add("virtual_send", time.perf_counter() - send_start)
            preview_start = time.perf_counter()
            if args.headless:
                key = terminal_key()
            else:
                if not args.no_mirror:
                    preview = cv2.flip(display, 1, dst=preview_buffer)
                else:
                    np.copyto(preview_buffer, display)
                    preview = preview_buffer
                message = guidance(state.phase, tick-state.calibration_started,
                                   tick-ready_at if ready_at is not None else 0, mode,
                                   CALIBRATION_SECONDS, getattr(result, "hold_progress", 0),
                                   getattr(result, "latched", False))
                if pending:
                    message = ("PREPARING EFFECT", "Keep your face and body in view", "", 0)
                if notice is not None and tick < notice_until:
                    message = notice
                if camera_dark:
                    message = ("CAMERA IMAGE IS BLACK", "Open the webcam privacy shutter/switch; check lighting", "", 0)
                draw_guidance(preview, message)
                cv2.imshow(WINDOW_NAME, preview)
                # Win32 pollKey pumps GUI messages without waitKey's timer delay.
                key = (cv2.pollKey() if hasattr(cv2, "pollKey") else cv2.waitKey(1)) & 0xFF
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
            profiler.add("preview", time.perf_counter() - preview_start)
            if key in (ord("q"), ord("Q"), 27):
                break
            now = time.perf_counter()
            if key == ord(" "):
                state.phase, state.calibration_started = "calibrating", now
                state.vanish_started = None
                background_samples.clear()
                if background_future is not None:
                    background_future.cancel()
                    background_future = None
                calibration_remaining = None
                pending = None
                effect = None
                vanished_frame = None
                log_anchor = None
                print("[Webcam] Step out of frame for the new background.")
            elif key in (ord("r"), ord("R")) and mode != "goku" and background is not None:
                pending = None
                if mode == "naruto":
                    state.phase = "ready"
                    vanished_frame, log_anchor = None, None
                elif state.phase == "vanished":
                    pending, pending_since = "return", now
                elif state.phase == "vanishing":
                    start_progress = min(1, start_progress + (now - state.vanish_started) / DURATIONS[mode])
                    state.phase, state.vanish_started = "returning", now
            elif key in (ord("v"), ord("V")) and mode != "goku" and state.phase == "ready":
                pending, pending_since = "vanish", now
            elif key in (ord("h"), ord("H")):
                ready_at = now
                notice = None
                print("[Help] " + dict((item[0], item[2]) for item in MODES)[mode]
                      + ". Lower your hand, then repeat the sign to return. SPACE: background; M: mute; Q: quit.")
            elif key in (ord("m"), ord("M")):
                muted = not muted
                if muted and sound:
                    try:
                        sound.stop()
                    except Exception as error:
                        print(f"[Audio] Could not stop current sound: {error}")
                notice = ("SOUND MUTED" if muted else "SOUND ENABLED", "M toggles sound; H shows gesture help", "", 0)
                notice_until = now + 2
                print("[Audio] " + ("Muted" if muted else "Enabled"))
            elif key in (ord("f"), ord("F")) and not args.headless:
                state.fullscreen = not state.fullscreen
                set_fullscreen(state.fullscreen)
            profiler.add("frame_work", time.perf_counter() - tick)
            profiler.add("output_interval", now - last_frame_at)
            last_frame_at = now
            profiler.tick(now)
            if args.duration and now - started >= args.duration:
                break
            deadline += 1.0 / args.fps
            delay = deadline - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                deadline = time.perf_counter()
    finally:
        resources.close()
    return 0


def main() -> int:
    try:
        return run()
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        print(f"\n[Vanish Lab] ERRORE: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
