"""MediaPipe CPU inference, owned and called by the latest-frame worker."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from gesture_detection import GestureGate, finger_geometry, forehead_score, pixel_landmarks, victory_score
from naruto_effect import joined_hands_from_landmarks, substitution_anchor
from vanish_effects import SilhouetteEffect


@dataclass(frozen=True)
class PreparedTransition:
    captured_at: float
    frame: np.ndarray
    mask: np.ndarray
    effect: SilhouetteEffect | None
    anchor: tuple | None


@dataclass(frozen=True)
class VisionResult:
    sequence: int
    captured_at: float
    frame: np.ndarray
    mask: np.ndarray | None
    event_id: int
    event_at: float
    score: float
    debug: str
    mask_frame: np.ndarray | None = None
    mask_at: float | None = None
    prepared: PreparedTransition | None = None
    hold_progress: float = 0.0
    latched: bool = False


class VisionProcessor:
    def __init__(self, args, mode, profiler, segmenter_path, hand_path, face_path):
        self.args, self.mode, self.profiler = args, mode, profiler
        self.resources = ExitStack()
        self.event_id, self.event_at = 0, 0.0
        self.timestamp = -1
        self.gate = GestureGate(on_frames=args.gesture_frames, off_frames=args.gesture_release_frames,
                                hold_seconds=1.0 if mode == "goku" else 0.0,
                                max_gap=.75 if mode == "goku" else .4)
        self.clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)) if args.detection_light else None
        self.size = None
        self.published_mask = None
        self.mask_frame = None
        self.mask_at = None
        self.prepared = None
        self.last_face_pixels = None
        self.last_face_at = 0.0
        self.was_preparing = False
        try:
            self.segmenter = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                base_options=python.BaseOptions(model_asset_path=str(segmenter_path)),
                running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True,
                output_category_mask=False))
            self.resources.callback(self.segmenter.close)
            self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(hand_path)),
                running_mode=vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.40, min_hand_presence_confidence=.40,
                min_tracking_confidence=.50))
            self.resources.callback(self.hands.close)
            self.face = None
            if mode == "goku":
                self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=str(face_path)),
                    running_mode=vision.RunningMode.VIDEO, num_faces=1,
                    min_face_detection_confidence=.40, min_face_presence_confidence=.40,
                    min_tracking_confidence=.50))
                self.resources.callback(self.face.close)
        except Exception:
            self.resources.close()
            raise

    def process(self, packet):
        start = time.perf_counter()
        frame = packet.frame
        height, width = frame.shape[:2]
        small_width = min(width, self.args.detection_width)
        size = (small_width, max(1, round(height * small_width / width)))
        if self.size != size:
            self.size = size
            self.small = np.empty((size[1], size[0], 3), np.uint8)
            self.rgb = np.empty_like(self.small)
            self.mask = np.empty((size[1], size[0]), np.float32)
            self.light_rgb = np.empty_like(self.small)
            self.lab = np.empty_like(self.small)
        cv2.resize(frame, size, dst=self.small, interpolation=cv2.INTER_AREA)
        cv2.cvtColor(self.small, cv2.COLOR_BGR2RGB, dst=self.rgb)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=self.rgb)
        timestamp = max(self.timestamp + 1, int(packet.captured_at * 1000))
        self.timestamp = timestamp
        self.profiler.add("detect_prepare", time.perf_counter() - start)
        segmentation_image = image
        if self.clahe is not None:
            cv2.cvtColor(self.rgb, cv2.COLOR_RGB2LAB, dst=self.lab)
            self.lab[:, :, 0] = self.clahe.apply(self.lab[:, :, 0])
            cv2.cvtColor(self.lab, cv2.COLOR_LAB2RGB, dst=self.light_rgb)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=self.light_rgb)
        started = time.perf_counter()
        hands = self.hands.detect_for_video(image, timestamp)
        # No forehead gesture can exist without a hand. Avoid face inference then.
        face = self.face.detect_for_video(image, timestamp) if self.face and hands.hand_landmarks else None
        self.profiler.add("landmarks", time.perf_counter() - started)
        face_pixels = (pixel_landmarks(face.face_landmarks[0], width, height)
                       if face and face.face_landmarks else None)
        if face_pixels is not None:
            self.last_face_pixels, self.last_face_at = face_pixels, packet.captured_at
        elif self.mode == "goku" and packet.captured_at - self.last_face_at <= .25:
            # A touching hand briefly occludes the brow. Reuse only very recent face geometry.
            face_pixels = self.last_face_pixels
        score = 0.0
        diagnostics = []
        open_counts = []
        for index, landmarks in enumerate(hands.hand_landmarks):
            pixels = pixel_landmarks(landmarks, width, height)
            flat = pixels.copy()
            flat[:, 2] = 0  # A useful fallback when estimated depth is unreliable.
            world = np.asarray([(p.x, p.y, p.z) for p in hands.hand_world_landmarks[index]], np.float32)
            candidates = (world, flat)
            geometry = [finger_geometry(points) for points in candidates]
            candidate_scores = [forehead_score(pixels, face_pixels, points) if self.mode == "goku"
                                else victory_score(points) for points in candidates]
            selected = int(np.argmax(candidate_scores))
            score = max(score, *candidate_scores)
            fingers = geometry[selected]
            open_counts.append(max((sum(f["extended"] for f in group) for group in geometry), default=0))
            states = ",".join(f"{name}:{'extended' if f['extended'] else 'curled' if f['curled'] else 'uncertain'}"
                              f"({f['confidence']:.2f})" for name, f in
                              zip(("index", "middle", "ring", "little"), fingers))
            diagnostics.append(f"hand{index + 1}[{states}]")
        if self.mode == "naruto":
            joined = joined_hands_from_landmarks(hands.hand_landmarks, width, height)
            open_hands = len(open_counts) == 2 and min(open_counts) >= 2 and sum(open_counts) >= 6
            score = .95 if joined and open_hands else 0.0
        triggered = self.gate.update(score, packet.captured_at)
        if triggered:
            self.event_id += 1
            self.event_at = packet.captured_at
        # Segment on a trigger/manual request, or while Normal tracks its dissolve.
        # Frozen transitions need no repeated segmentation. This keeps gesture
        # tracking responsive while the live camera image is shown unchanged.
        if triggered or packet.need_mask:
            started = time.perf_counter()
            segmentation = self.segmenter.segment_for_video(segmentation_image, timestamp)
            if segmentation.confidence_masks:
                raw = np.squeeze(segmentation.confidence_masks[0].numpy_view())
                cv2.resize(raw, size, dst=self.mask, interpolation=cv2.INTER_LINEAR)
                cv2.GaussianBlur(self.mask, (0, 0), 1.1, dst=self.mask)
                self.mask -= .12
                self.mask /= .68
                np.clip(self.mask, 0, 1, out=self.mask)
            else:
                self.mask.fill(0)
            self.profiler.add("segment", time.perf_counter() - started)
            # Publish immutable pixels paired with their exact segmentation frame.
            self.published_mask = self.mask.copy()
            self.mask_frame = frame
            self.mask_at = packet.captured_at
        if triggered or (packet.prepare_effect and (not self.was_preparing or self.prepared is None)):
            self.prepared = None
            if self.published_mask is not None and np.count_nonzero(self.published_mask > .45) >= self.published_mask.size * .003:
                prep_start = time.perf_counter()
                full_mask = cv2.resize(self.published_mask, (width, height), interpolation=cv2.INTER_LINEAR)
                effect = SilhouetteEffect(frame, full_mask, self.mode) if self.mode != "naruto" else None
                anchor = substitution_anchor(full_mask) if self.mode == "naruto" else None
                self.prepared = PreparedTransition(packet.captured_at, frame, full_mask, effect, anchor)
                self.profiler.add("effect_prepare", time.perf_counter() - prep_start)
        self.was_preparing = packet.prepare_effect
        held = packet.captured_at - self.gate.started if self.gate.started is not None else 0
        debug = (f"hands={len(hands.hand_landmarks)} geometry={score:.2f} smooth={self.gate.smoothed:.2f} "
                 f"hold={held:.1f}s latched={self.gate.latched} " + " ".join(diagnostics))
        self.profiler.add("inference", time.perf_counter() - start)
        return VisionResult(packet.sequence, packet.captured_at, frame, self.published_mask,
                            self.event_id, self.event_at, score, debug, self.mask_frame, self.mask_at, self.prepared,
                            min(1.0, held) if self.mode == "goku" else 0.0, self.gate.latched)

    def close(self):
        self.resources.close()
