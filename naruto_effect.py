"""Two-hand trigger and smoke/log compositing for body substitution."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


EFFECT_SECONDS = 1.45
LOG_PATH = Path(__file__).resolve().parent / "assets" / "substitution_log.png"


def joined_hands_from_landmarks(hands, width: int, height: int) -> bool:
    """Recognize two nearby, similarly oriented open hands in image space."""
    if len(hands) < 2:
        return False
    points = [np.array([(p.x * width, p.y * height) for p in hand])
              for hand in hands[:2] if len(hand) == 21]
    if len(points) != 2 or not all(np.isfinite(hand).all() for hand in points):
        return False
    palms = [hand[[0, 5, 9, 13, 17]].mean(axis=0) for hand in points]
    scale = [max(float(np.linalg.norm(hand[5] - hand[17])),
                 float(np.linalg.norm(hand[0] - hand[9]))) for hand in points]
    if min(scale) < 8.0 or max(scale) > min(scale) * 2.2:
        return False
    size = sum(scale) * 0.5
    directions = [hand[9] - hand[0] for hand in points]
    alignment = float(np.dot(*directions) /
                      max(1e-6, np.linalg.norm(directions[0]) * np.linalg.norm(directions[1])))
    fingertips = [hand[[8, 12, 16, 20]].mean(axis=0) for hand in points]
    return (
        alignment > 0.25
        and np.linalg.norm(palms[0] - palms[1]) < size * 1.55
        and np.linalg.norm(fingertips[0] - fingertips[1]) < size * 1.9
    )


def substitution_anchor(mask: np.ndarray) -> tuple[int, int, int]:
    """Place the log at the person's torso instead of at a fixed screen spot."""
    height, width = mask.shape
    binary = (mask > 0.45).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    if count <= 1:
        return width // 2, height // 2, int(height * 0.57)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, _ = stats[largest]
    size = int(np.clip(h * 0.58, height * 0.24, height * 0.70))
    center_x = int(np.clip(x + w * 0.5, size // 3, width - size // 3))
    center_y = int(np.clip(y + h * 0.52, size // 3, height - size // 3))
    return center_x, center_y, size


def load_log() -> np.ndarray:
    sprite = cv2.imread(str(LOG_PATH), cv2.IMREAD_UNCHANGED)
    if sprite is None or sprite.ndim != 3 or sprite.shape[2] != 4:
        raise RuntimeError(f"Sprite del tronco non disponibile: {LOG_PATH}")
    return sprite


def overlay_log(frame: np.ndarray, sprite: np.ndarray, anchor: tuple[int, int, int],
                opacity: float = 1.0, scale: float = 1.0,
                cache: dict[int, np.ndarray] | None = None) -> None:
    if opacity <= 0:
        return
    cx, cy, target_height = anchor
    height = max(1, int(target_height * scale))
    width = max(1, int(height * sprite.shape[1] / sprite.shape[0]))
    sized = cache.get(height) if cache is not None else None
    if sized is None:
        sized = cv2.resize(sprite, (width, height), interpolation=cv2.INTER_AREA)
        if cache is not None:
            cache[height] = sized
    x1, y1 = cx - width // 2, cy - height // 2
    x2, y2 = x1 + width, y1 + height
    left, top = max(0, x1), max(0, y1)
    right, bottom = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if left >= right or top >= bottom:
        return
    part = sized[top - y1:bottom - y1, left - x1:right - x1]
    alpha = (part[:, :, 3:4].astype(np.float32) / 255.0) * opacity
    destination = frame[top:bottom, left:right]
    destination[:] = np.clip(
        part[:, :, :3].astype(np.float32) * alpha
        + destination.astype(np.float32) * (1.0 - alpha),
        0, 255,
    ).astype(np.uint8)


def landed_log_anchor(anchor: tuple[int, int, int], frame_height: int) -> tuple[int, int, int]:
    cx, cy, size = anchor
    return cx, max(cy, frame_height - round(size * 0.48)), size


def falling_log_anchor(anchor: tuple[int, int, int], frame_height: int,
                       age: float) -> tuple[int, int, int]:
    """Accelerate downwards, touch the frame floor, then settle with a small bounce."""
    cx, cy, size = anchor
    floor_y = landed_log_anchor(anchor, frame_height)[1]
    distance = floor_y - cy
    if distance <= 0 or age <= 0.18:
        return anchor
    elapsed = age - 0.18
    gravity = frame_height * 3.2
    fall = gravity * elapsed * elapsed * 0.5
    if fall < distance:
        return cx, cy + round(fall), size
    landed_at = math.sqrt(2.0 * distance / gravity)
    bounce_age = elapsed - landed_at
    bounce = size * 0.075 * math.exp(-5.0 * bounce_age) * abs(math.sin(11.0 * bounce_age))
    return cx, floor_y - round(bounce), size


def _smoke_layer(frame: np.ndarray, anchor: tuple[int, int, int],
                 age: float, foreground: bool) -> None:
    if age >= EFFECT_SECONDS:
        return
    cx, cy, size = anchor
    rng = np.random.default_rng(9127 if foreground else 1934)
    reveal = min(1.0, age / 0.16)
    fade = max(0.0, 1.0 - max(0.0, age - 0.33) / 1.12)
    if fade <= 0:
        return
    # Smoke only occupies the area around the log; avoid allocating and
    # blending a full-size RGBA video frame twice per animation frame.
    margin = int(size * 1.35)
    left, top = max(0, cx - margin), max(0, cy - margin)
    right = min(frame.shape[1], cx + margin + 1)
    bottom = min(frame.shape[0], cy + margin + 1)
    if left >= right or top >= bottom:
        return
    layer = np.zeros((bottom - top, right - left, 4), dtype=np.uint8)
    radius = size * (0.27 + 0.54 * min(age, 1.0))
    for _ in range(22 if foreground else 18):
        angle = rng.uniform(0, 2 * math.pi)
        distance = radius * rng.uniform(0.25, 1.0)
        x = int(cx + math.cos(angle) * distance) - left
        y = int(cy + math.sin(angle) * distance * 0.63 - age * size * 0.13) - top
        puff = max(2, int(size * rng.uniform(0.09, 0.20) * (0.7 + age * 0.7)))
        color = (229, 235, 235, 190) if foreground else (152, 162, 166, 125)
        cv2.ellipse(layer, (x, y), (puff, int(puff * 0.68)),
                    rng.uniform(-25, 25), 0, 360, color, -1, cv2.LINE_AA)
    # Long white winding smoke ribbons echo the supplied anime reference.
    for direction in (-1, 1):
        center = (int(cx + direction * size * 0.13) - left,
                  int(cy - size * 0.13 - age * size * 0.09) - top)
        axes = (max(2, int(size * (0.30 + age * 0.27))),
                max(2, int(size * (0.09 + age * 0.12))))
        cv2.ellipse(layer, center, axes, direction * 15, 20, 230,
                    (244, 247, 245, 220), max(2, int(size * 0.025)), cv2.LINE_AA)
    occupied = cv2.findNonZero(layer[:, :, 3])
    if occupied is None:
        return
    x, y, width, height = cv2.boundingRect(occupied)
    destination = frame[top + y:top + y + height, left + x:left + x + width]
    layer = layer[y:y + height, x:x + width]
    alpha = (layer[:, :, 3:4].astype(np.float32) / 255.0) * reveal * fade
    destination[:] = np.clip(
        layer[:, :, :3].astype(np.float32) * alpha
        + destination.astype(np.float32) * (1.0 - alpha),
        0, 255,
    ).astype(np.uint8)


def render_substitution(frame: np.ndarray, background: np.ndarray, mask: np.ndarray,
                        sprite: np.ndarray, anchor: tuple[int, int, int], age: float,
                        log_cache: dict[int, np.ndarray] | None = None) -> np.ndarray:
    """Quick body replacement, expanding smoke, then a persistent wooden log."""
    if age >= EFFECT_SECONDS:
        output = background.copy()
        overlay_log(output, sprite, landed_log_anchor(anchor, output.shape[0]), cache=log_cache)
        return output
    if age >= 0.13:
        output = background.copy()
    else:
        person_alpha = mask * max(0.0, 1.0 - age / 0.13)
        output = (
            frame.astype(np.float32) * person_alpha[:, :, None]
            + background.astype(np.float32) * (1.0 - person_alpha[:, :, None])
        ).astype(np.uint8)
    _smoke_layer(output, anchor, age, foreground=False)
    log_opacity = min(1.0, max(0.0, (age - 0.05) / 0.15))
    moving_anchor = falling_log_anchor(anchor, output.shape[0], age)
    overlay_log(output, sprite, moving_anchor, log_opacity,
                scale=1.15 - min(age, 0.25) * 0.6, cache=log_cache)
    _smoke_layer(output, anchor, age, foreground=True)
    return output
