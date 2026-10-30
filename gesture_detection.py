"""Rotation-independent hand geometry and debounced gesture events."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


FINGER_NAMES = ("index", "middle", "ring", "little")


def finger_geometry(points):
    """Return extended/curled states, confidence and joint cosines for four fingers."""
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (21, 3) or not np.isfinite(points).all():
        return []
    palm = max(float(np.linalg.norm(points[9] - points[0])),
               float(np.linalg.norm(points[5] - points[17])))
    if palm < 1e-7:
        return []
    result = []
    for base in (5, 9, 13, 17):
        finger = points[base:base + 4]
        bones = np.diff(finger, axis=0)
        lengths = np.linalg.norm(bones, axis=1)
        length = float(lengths.sum())
        reach = float(np.linalg.norm(finger[3] - finger[0]))
        ratio = reach / max(length, 1e-7)
        cosines = [float(np.dot(bones[i], bones[i + 1]) /
                         max(float(lengths[i] * lengths[i + 1]), 1e-10)) for i in (0, 1)]
        tip = float(np.linalg.norm(finger[3] - points[0])) / palm
        joint = float(np.linalg.norm(finger[1] - points[0])) / palm
        extended = ratio >= 0.82 and min(cosines) >= 0.45 and tip > joint * 1.10
        curled = ratio < 0.78 or tip <= joint * 1.05 or length < 1e-7
        result.append(dict(extended=extended, curled=curled, confidence=ratio,
                           joint_cosines=tuple(cosines), reach=reach, length=length))
    return result


def victory_score(points):
    fingers = finger_geometry(points)
    if not fingers:
        return 0.0
    reference = min(fingers[0]["length"], fingers[1]["length"])
    folded = [f["curled"] or f["reach"] < reference * 0.65 for f in fingers[2:]]
    if not (fingers[0]["extended"] and fingers[1]["extended"] and all(folded)):
        return 0.0
    if np.linalg.norm(points[8] - points[12]) < reference * 0.20:
        return 0.0
    return float(min(fingers[0]["confidence"], fingers[1]["confidence"]))


def forehead_score(hand_pixels, face_pixels, geometry_points=None):
    """Two straight, adjacent fingers touching the forehead, including rolled faces."""
    if face_pixels is None or len(face_pixels) < 169:
        return 0.0
    points = hand_pixels if geometry_points is None else geometry_points
    fingers = finger_geometry(points)
    if not fingers or not all(f["extended"] or (f["confidence"] >= .78 and min(f["joint_cosines"]) >= .25) for f in fingers[:2]):
        return 0.0
    if not all(f["curled"] or f["reach"] < min(x["length"] for x in fingers[:2]) * 0.65
               for f in fingers[2:]):
        return 0.0
    palm = max(np.linalg.norm(points[9] - points[0]), np.linalg.norm(points[5] - points[17]))
    if np.linalg.norm(points[8] - points[12]) > palm * 0.80:
        return 0.0
    face = np.asarray(face_pixels)
    face_width = float(np.linalg.norm(face[234, :2] - face[454, :2])) if len(face) > 454 else 0
    if face_width < 8 or not np.isfinite(face).all():
        return 0.0
    forehead = face[10, :2] * 0.60 + face[168, :2] * 0.40
    # Accept forehead or temple, not only one small point in the brow center.
    horizontal = face[454, :2] - face[234, :2]
    horizontal /= max(np.linalg.norm(horizontal), 1e-6)
    vertical = np.array([-horizontal[1], horizontal[0]])
    offsets = hand_pixels[[8, 12], :2] - forehead
    across = np.abs(offsets @ horizontal)
    above = np.abs(offsets @ vertical)
    distance = max(float(np.linalg.norm(offset)) for offset in offsets)
    if np.any(across > face_width * .55) or np.any(above > face_width * .35):
        return 0.0
    return float(min(fingers[0]["confidence"], fingers[1]["confidence"],
                     1.0 - 0.3 * min(1, distance / (face_width * .65))))


def pixel_landmarks(landmarks, width, height):
    # MediaPipe x/y are normalized independently; z uses the image width.
    return np.asarray([(p.x * width, p.y * height, getattr(p, "z", 0.0) * width)
                       for p in landmarks], dtype=np.float32)


@dataclass
class GestureGate:
    on_frames: int = 3
    off_frames: int = 5
    on_threshold: float = 0.62
    off_threshold: float = 0.35
    hold_seconds: float = 0.0
    max_gap: float = 0.4
    consecutive: int = 0
    misses: int = 0
    latched: bool = False
    smoothed: float = 0.0
    started: float | None = None
    last_time: float | None = None

    def update(self, score, now):
        if self.last_time is not None and now <= self.last_time:
            return False  # Repeated output frames must never count as observations.
        if self.last_time is not None and now - self.last_time > self.max_gap:
            self.consecutive = 0
            self.started = None
            self.smoothed = 0.0
        first = self.last_time is None
        self.last_time = now
        score = float(score) if np.isfinite(score) else 0.0
        self.smoothed = score if first else 0.65 * score + 0.35 * self.smoothed
        if score < self.on_threshold:
            self.consecutive = 0
            self.started = None  # Goku requires an uninterrupted one-second hold.
        if score < self.off_threshold:
            self.misses += 1
            if self.misses >= self.off_frames:
                self.latched = False
        else:
            self.misses = 0
        if score >= self.on_threshold and self.smoothed >= self.on_threshold:
            if self.started is None:
                self.started = now
            self.consecutive += 1
            if (not self.latched and self.consecutive >= self.on_frames
                    and now - self.started >= self.hold_seconds):
                self.latched = True
                return True
        return False
