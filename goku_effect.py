"""Two-finger forehead trigger and a brief comic-style teleport effect."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np


HOLD_SECONDS = 1.0
TELEPORT_SECONDS = 0.25
SNAP_SECONDS = 0.045
TRACKING_GRACE_SECONDS = 0.25


def _finger_straight(points: np.ndarray, joints: tuple[int, int, int, int]) -> bool:
    chain = points[list(joints)]
    length = np.linalg.norm(np.diff(chain, axis=0), axis=1).sum()
    return length > 1e-6 and np.linalg.norm(chain[-1] - chain[0]) / length > 0.76


def fingers_on_forehead(hands, faces, width: int, height: int) -> bool:
    """Match joined, extended index/middle fingertips to a detected forehead."""
    if not faces or not hands:
        return False
    for hand in hands:
        if len(hand) != 21:
            continue
        points = np.asarray([(p.x * width, p.y * height) for p in hand], np.float32)
        if not np.isfinite(points).all():
            continue
        palm = max(np.linalg.norm(points[5] - points[17]),
                   np.linalg.norm(points[0] - points[9]))
        if palm < 10:
            continue
        if not (_finger_straight(points, (5, 6, 7, 8))
                and _finger_straight(points, (9, 10, 11, 12))):
            continue
        if _finger_straight(points, (13, 14, 15, 16)) or _finger_straight(points, (17, 18, 19, 20)):
            continue
        if np.linalg.norm(points[8] - points[12]) > palm * 0.52:
            continue
        index_direction = points[8] - points[5]
        middle_direction = points[12] - points[9]
        alignment = np.dot(index_direction, middle_direction) / max(
            np.linalg.norm(index_direction) * np.linalg.norm(middle_direction), 1e-6,
        )
        if alignment < 0.75:
            continue
        for x, y, face_width, face_height in faces:
            if face_width < 30 or face_height < 30:
                continue
            # BlazeFace's box encloses the upper face; allow a little room at
            # the hairline and temples for either hand and camera mirroring.
            forehead = (
                x - 0.18 * face_width, x + 1.18 * face_width,
                y - 0.16 * face_height, y + 0.46 * face_height,
            )
            tips = points[[8, 12]]
            if (np.all((tips[:, 0] >= forehead[0]) & (tips[:, 0] <= forehead[1]))
                    and np.all((tips[:, 1] >= forehead[2]) & (tips[:, 1] <= forehead[3]))):
                return True
    return False


@dataclass
class GokuGestureGate:
    """Require a sustained pose and a deliberate release before the next use."""

    armed: bool = True
    hold_started: float | None = None
    last_seen: float | None = None
    release_started: float | None = None
    hold_seconds: float = HOLD_SECONDS

    def __post_init__(self):
        if not math.isfinite(self.hold_seconds) or self.hold_seconds <= 0:
            raise ValueError('Il tempo di mantenimento deve essere positivo e finito.')

    def update(self, pose: bool, now: float) -> bool:
        if not pose:
            if self.release_started is None:
                self.release_started = now
            if now - self.release_started >= 0.35:
                self.armed = True
            if self.last_seen is None or now - self.last_seen > TRACKING_GRACE_SECONDS:
                self.hold_started = None
            return False

        self.release_started = None
        if not self.armed:
            return False
        if self.last_seen is not None and now - self.last_seen > TRACKING_GRACE_SECONDS:
            self.hold_started = None
        if self.hold_started is None:
            self.hold_started = now
        self.last_seen = now
        if now < self.hold_started + self.hold_seconds:
            return False
        self.armed = False
        self.hold_started = None
        return True

    def reset(self) -> None:
        self.armed = True
        self.hold_started = None
        self.last_seen = None
        self.release_started = None


class GokuPoseRecognizer:
    def __init__(self, hand_detector, face_detector, fallback_hand_detector=None):
        self.hand_detector = hand_detector
        self.face_detector = face_detector
        self.fallback_hand_detector = fallback_hand_detector
        self.last_hand_count = 0
        self.last_face_count = 0
        self._faces = []
        self._face_seen_ms = -1000
        self._next_retry_ms = 0

    def recognize_pose(self, image, timestamp_ms: int) -> bool:
        detected = self.face_detector.detect_for_video(image, timestamp_ms).detections
        self.last_face_count = len(detected)
        if detected:
            self._faces = [
                (box.origin_x, box.origin_y, box.width, box.height)
                for detection in detected
                for box in (detection.bounding_box,)
            ]
            self._face_seen_ms = timestamp_ms
        elif timestamp_ms - self._face_seen_ms > 250:
            self._faces = []
        if not self._faces:
            self.last_hand_count = 0
            return False
        hands = self.hand_detector.detect_for_video(image, timestamp_ms).hand_landmarks
        self.last_hand_count = len(hands)
        if fingers_on_forehead(hands, self._faces, image.width, image.height):
            return True
        if self.fallback_hand_detector is None or timestamp_ms < self._next_retry_ms:
            return False
        self._next_retry_ms = timestamp_ms + 300
        x, y, width, height = max(self._faces, key=lambda face: face[2] * face[3])
        left = max(0, round(x - width * 0.55))
        top = max(0, round(y - height * 0.40))
        right = min(image.width, round(x + width * 1.55))
        bottom = min(image.height, round(y + height * 1.60))
        if right - left < 32 or bottom - top < 32:
            return False
        crop = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(image.numpy_view()[top:bottom, left:right]),
        )
        recovered = self.fallback_hand_detector.detect(crop).hand_landmarks
        self.last_hand_count = max(self.last_hand_count, len(recovered))
        mapped = [
            [SimpleNamespace(
                x=(left + point.x * crop.width) / image.width,
                y=(top + point.y * crop.height) / image.height,
            ) for point in hand]
            for hand in recovered
        ]
        return fingers_on_forehead(mapped, self._faces, image.width, image.height)

    def close(self) -> None:
        try:
            self.hand_detector.close()
        finally:
            try:
                if self.fallback_hand_detector is not None:
                    self.fallback_hand_detector.close()
            finally:
                self.face_detector.close()


class GokuTeleport:
    """One sharp cut framed by animated vertical ink and light streaks."""

    def __init__(self, frame: np.ndarray, background: np.ndarray, mask: np.ndarray):
        self.visible = background.copy()
        self.ghost = background.copy()
        self.streaks = []
        self.streak_area = None
        points = cv2.findNonZero((mask > 0.04).astype(np.uint8))
        if points is None:
            return
        x, y, width, height = cv2.boundingRect(points)
        frame_height, frame_width = frame.shape[:2]
        pad_x = max(5, round(width * 0.10))
        pad_y = max(5, round(height * 0.18))
        self.streak_area = (
            max(0, x - pad_x), max(0, y - pad_y),
            min(frame_width, x + width + pad_x),
            min(frame_height, y + height + pad_y),
        )
        # Fixed per teleport: the streaks move, but do not flicker between frames.
        rng = np.random.default_rng(1616)
        count = max(14, min(38, round(width / 12)))
        for index, center in enumerate(np.linspace(x, x + width - 1, count)):
            line_x = int(round(center + rng.uniform(-0.18, 0.18) * width / count))
            start_y = int(round(y + height * rng.uniform(-0.12, 0.67)))
            length = max(9, int(round(height * rng.uniform(0.28, 0.80))))
            if index % 5 == 0:
                start_y = int(round(y - height * rng.uniform(0.08, 0.20)))
                length = int(round(height * rng.uniform(0.85, 1.10)))
            self.streaks.append((line_x, start_y, length, 2 if index % 6 == 0 else 1,
                                 index % 4 == 0))
        area = np.s_[y:y + height, x:x + width]
        alpha = mask[area][:, :, None]
        self.visible[area] = (
            frame[area].astype(np.float32) * alpha
            + background[area].astype(np.float32) * (1.0 - alpha)
        ).astype(np.uint8)
        outline = cv2.morphologyEx(
            (mask > 0.42).astype(np.uint8), cv2.MORPH_GRADIENT,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        shifted = np.zeros_like(outline)
        shifted[:, 5:] = outline[:, :-5]
        self.ghost[shifted > 0] = np.clip(
            self.ghost[shifted > 0].astype(np.int16) + (78, 67, 42), 0, 255,
        ).astype(np.uint8)
        self.visible[outline > 0] = np.clip(
            self.visible[outline > 0].astype(np.int16) + (45, 35, 20), 0, 255,
        ).astype(np.uint8)

    def render(self, background: np.ndarray, age: float, appearing: bool) -> np.ndarray:
        if age >= TELEPORT_SECONDS:
            return self.visible if appearing else background
        # The subject still changes in a single cut; the comic streaks begin
        # before it and linger briefly over either the ghost or the body.
        base = (self.ghost if age < SNAP_SECONDS else self.visible) if appearing else (
            self.visible if age < SNAP_SECONDS else self.ghost
        )
        if not self.streaks or self.streak_area is None:
            return base
        strength = (0.72 + 0.28 * max(0.0, age) / SNAP_SECONDS) if age < SNAP_SECONDS else (
            max(0.0, (TELEPORT_SECONDS - age) / (TELEPORT_SECONDS - SNAP_SECONDS))
        )
        left, top, right, bottom = self.streak_area
        output = base.copy()
        region = output[top:bottom, left:right]
        ink = region.copy()
        drift = round((age / TELEPORT_SECONDS) * min(18, (bottom - top) * 0.10))
        direction = -1 if appearing else 1
        for line_x, start_y, length, thickness, dark in self.streaks:
            x_pos = line_x - left
            y_pos = start_y - top + direction * drift
            end_y = y_pos + length
            if dark:
                cv2.line(ink, (x_pos, y_pos), (x_pos, end_y),
                         (42, 45, 52), thickness, cv2.LINE_AA)
            else:
                # An ink edge and an off-white center read as a drawn speed line.
                cv2.line(ink, (x_pos + 2, y_pos + 3), (x_pos + 2, end_y - 2),
                         (62, 64, 69), thickness, cv2.LINE_AA)
                cv2.line(ink, (x_pos, y_pos), (x_pos, end_y),
                         (237, 246, 255), thickness, cv2.LINE_AA)
        cv2.addWeighted(ink, strength, region, 1.0 - strength, 0, dst=region)
        return output
