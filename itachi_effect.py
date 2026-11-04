"""Cel shaded crow transformation driven by the captured person's silhouette."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np


EFFECT_SECONDS = 4.0
BODY_RELEASE_SECONDS = 3.05
CROW_COUNT = 78
FIRST_CROW_SECONDS = 0.14
LAST_CROW_SECONDS = 2.82
CROW_SHEET_PATH = Path(__file__).resolve().parent / "assets" / "itachi_crow_sheet.png"
SHARINGAN_PATH = Path(__file__).resolve().parent / "assets" / "sharingan.png"


def _smoothstep(start: float, end: float, value: float) -> float:
    t = float(np.clip((value - start) / (end - start), 0, 1))
    return t * t * (3 - 2 * t)


def _largest_person(mask: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    binary = (mask > 0.48).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count < 2:
        return None
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, area = (int(v) for v in stats[component])
    if area < mask.size * 0.025 or width < 20 or height < 35:
        return None
    return (labels == component).astype(np.uint8), (x, y, width, height)


def hands_touch_at_chest(hands, mask: np.ndarray) -> bool:
    """Require two touching hands over the middle third of the visible torso."""
    if len(hands) != 2 or any(len(hand) != 21 for hand in hands):
        return False
    person = _largest_person(mask)
    if person is None:
        return False
    _, (x, y, width, height) = person
    frame_height, frame_width = mask.shape
    points = [np.asarray([(p.x * frame_width, p.y * frame_height) for p in hand], np.float32)
              for hand in hands]
    if not all(np.isfinite(p).all() for p in points):
        return False
    sizes = [max(float(np.linalg.norm(p[9] - p[0])),
                 float(np.linalg.norm(p[5] - p[17]))) for p in points]
    if min(sizes) < 10 or max(sizes) > min(sizes) * 2.5:
        return False
    size = sum(sizes) * 0.5
    palms = [p[[0, 5, 9, 13, 17]].mean(axis=0) for p in points]
    center = (palms[0] + palms[1]) * 0.5
    torso_center = x + width * 0.5
    if (abs(center[0] - torso_center) > max(width * 0.23, height * 0.17)
            or not y + height * 0.19 <= center[1] <= y + height * 0.79):
        return False
    if np.linalg.norm(palms[0] - palms[1]) > size * 1.45:
        return False
    # Fingertips or palm edges must meet. Wrist proximity alone is insufficient.
    contact = [4, 5, 8, 9, 12, 13, 16, 17, 20]
    distances = np.linalg.norm(points[0][contact, None] - points[1][None, contact], axis=2)
    return float(np.min(distances)) <= size * 0.48


class ItachiPoseRecognizer:
    """VIDEO hand tracking with a centered IMAGE retry for overlapping hands."""

    def __init__(self, detector, fallback):
        self.detector = detector
        self.fallback = fallback
        self.last_hand_count = 0
        self.next_retry_ms = 0

    def recognize_pose(self, image: mp.Image, timestamp_ms: int, mask: np.ndarray) -> bool:
        hands = self.detector.detect_for_video(image, timestamp_ms).hand_landmarks
        self.last_hand_count = len(hands)
        if hands_touch_at_chest(hands, mask):
            return True
        if timestamp_ms < self.next_retry_ms:
            return False
        self.next_retry_ms = timestamp_ms + 170
        rgb = image.numpy_view()
        x1, x2 = round(image.width * 0.18), round(image.width * 0.82)
        y1, y2 = round(image.height * 0.16), round(image.height * 0.92)
        crop = mp.Image(image_format=mp.ImageFormat.SRGB,
                        data=np.ascontiguousarray(rgb[y1:y2, x1:x2]))
        recovered = self.fallback.detect(crop).hand_landmarks
        self.last_hand_count = max(self.last_hand_count, len(recovered))
        mapped = [[SimpleNamespace(x=(x1 + p.x * crop.width) / image.width,
                                   y=(y1 + p.y * crop.height) / image.height)
                   for p in hand] for hand in recovered]
        return hands_touch_at_chest(mapped, mask)

    def close(self) -> None:
        try:
            self.detector.close()
        finally:
            self.fallback.close()


@dataclass
class ItachiGestureGate:
    armed: bool = True
    release_started: float | None = None

    def update(self, pose: bool, now: float) -> bool:
        if not pose:
            if self.release_started is None:
                self.release_started = now
            if now - self.release_started >= 0.25:
                self.armed = True
            return False
        self.release_started = None
        if self.armed:
            self.armed = False
            return True
        return False

    def reset(self) -> None:
        self.armed = True
        self.release_started = None


@lru_cache(maxsize=1)
def load_crow_sprites() -> tuple[np.ndarray, ...]:
    """Extract the five separate alpha components from the original sheet."""
    sheet = cv2.imread(str(CROW_SHEET_PATH), cv2.IMREAD_UNCHANGED)
    if sheet is None or sheet.ndim != 3 or sheet.shape[2] != 4:
        raise RuntimeError(f"Sprite dei corvi non disponibile: {CROW_SHEET_PATH}")
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (sheet[:, :, 3] > 30).astype(np.uint8), 8)
    birds = sorted((index for index in range(1, count) if stats[index, cv2.CC_STAT_AREA] > 5000),
                   key=lambda index: stats[index, cv2.CC_STAT_LEFT])
    if len(birds) != 5:
        raise RuntimeError("Lo sprite sheet dei corvi deve contenere cinque pose separate.")
    sprites = []
    for index in birds:
        x, y, width, height, _ = (int(value) for value in stats[index])
        left, top = max(0, x - 10), max(0, y - 10)
        right = min(sheet.shape[1], x + width + 10)
        bottom = min(sheet.shape[0], y + height + 10)
        crop = sheet[top:bottom, left:right].copy()
        crop[labels[top:bottom, left:right] != index] = 0
        factor = min(168 / crop.shape[1], 120 / crop.shape[0])
        scaled = cv2.resize(crop, (max(1, round(crop.shape[1] * factor)),
                                   max(1, round(crop.shape[0] * factor))),
                            interpolation=cv2.INTER_AREA)
        canvas = np.zeros((128, 176, 4), np.uint8)
        px = (176 - scaled.shape[1]) // 2
        py = (128 - scaled.shape[0]) // 2
        canvas[py:py + scaled.shape[0], px:px + scaled.shape[1]] = scaled
        sprites.append(canvas)
    return tuple(sprites)


@lru_cache(maxsize=1)
def load_sharingan_art() -> np.ndarray:
    """Matte the supplied black-backed eyes without losing dark pupils."""
    image = cv2.imread(str(SHARINGAN_PATH), cv2.IMREAD_COLOR)
    if image is None or image.shape[0] < 700 or image.shape[1] < 1000:
        raise RuntimeError(f"Immagine Sharingan non disponibile: {SHARINGAN_PATH}")
    crop = image[175:850].copy()
    height, width = crop.shape[:2]
    glow = np.zeros((height, width), np.uint8)
    for cx in (int(width * .19), int(width * .81)):
        cv2.ellipse(glow, (cx, 180), (int(width * .21), 145),
                    0, 0, 360, 220, -1, cv2.LINE_AA)
    glow = cv2.GaussianBlur(glow, (0, 0), 26)
    brightness = np.max(crop, axis=2).astype(np.float32)
    alpha = np.maximum(glow.astype(np.float32),
                       np.clip((brightness - 13) * 1.3, 0, 255)).astype(np.uint8)
    horizontal = np.minimum(np.arange(width), width - 1 - np.arange(width)) / 65.0
    vertical = np.minimum(np.arange(height), height - 1 - np.arange(height)) / 32.0
    edge_fade = np.clip(horizontal[None, :], 0, 1) * np.clip(vertical[:, None], 0, 1)
    alpha = (alpha * edge_fade).astype(np.uint8)
    return np.dstack((crop, alpha))


def _cubic(p0, p1, p2, p3, t: float) -> np.ndarray:
    u = 1.0 - t
    return u ** 3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3 * p3


@dataclass(frozen=True)
class Crow:
    origin: np.ndarray
    control1: np.ndarray
    control2: np.ndarray
    destination: np.ndarray
    launch: float
    duration: float
    size: float
    phase: float
    frequency: float
    depth: float
    hero: bool


@dataclass(frozen=True)
class Feather:
    origin: np.ndarray
    destination: np.ndarray
    launch: float
    duration: float
    size: float
    angle: float
    spin: float


class ItachiCrowEffect:
    """Immutable source frame, local body removal, and independently flapping crows."""

    def __init__(self, frame: np.ndarray, mask: np.ndarray, seed: int = 4411):
        self.source = frame.copy()
        self.mask = np.clip(mask.astype(np.float32), 0, 1)
        self.height, self.width = mask.shape
        rng = np.random.default_rng(seed)
        person = _largest_person(mask)
        if person is None:
            raise ValueError("Sagoma della persona non disponibile")
        binary, (left, top, body_width, body_height) = person
        self.bounds = (left, top, body_width, body_height)
        interior = cv2.erode(binary, np.ones((7, 7), np.uint8))
        candidates = np.argwhere(interior > 0)
        if len(candidates) < CROW_COUNT:
            candidates = np.argwhere(binary > 0)
        relative_y = (candidates[:, 0] - top) / max(1, body_height)
        weights = np.where((relative_y > .18) & (relative_y < .68), 3.0, 1.0)
        weights = weights / weights.sum()
        chosen = candidates[rng.choice(len(candidates), CROW_COUNT, replace=len(candidates) < CROW_COUNT,
                                       p=weights)]
        # Stable release sequence: shoulders, arms and torso lead; the face
        # follows. Random variation breaks rows without scrambling anatomy.
        priorities = []
        for row, column in chosen:
            vertical = (row - top) / max(1, body_height)
            priority = abs(vertical - .39) * .65 + (0.42 if vertical < .20 else 0.0)
            priorities.append(priority + rng.uniform(0, .27))
        order = np.argsort(priorities)
        launches = np.empty(CROW_COUNT, np.float32)
        launches[order] = np.linspace(FIRST_CROW_SECONDS, LAST_CROW_SECONDS, CROW_COUNT)
        rank = np.empty(CROW_COUNT, np.int32)
        rank[order] = np.arange(CROW_COUNT)
        hero_ranks = {10, 31, 54, 72}

        crows = []
        for index, (row, column) in enumerate(chosen):
            origin = np.array([float(column), float(row)], np.float32)
            hero = int(rank[index]) in hero_ranks
            route = 3 if hero else index % 5
            direction = (-1 if index % 2 else 1)
            if route == 0:  # Ascend, often in a shallow curve.
                destination = np.array([column + direction * rng.uniform(80, 310), -150.0])
            elif route in (1, 2):
                destination = np.array([self.width + 160.0 if direction > 0 else -160.0,
                                        row - rng.uniform(90, self.height * .7)])
            elif route == 3:  # A near bird crosses the foreground.
                destination = np.array([self.width + 210.0 if direction > 0 else -210.0,
                                        row + rng.uniform(-80, 130)])
            else:
                destination = np.array([column + direction * rng.uniform(130, 350), -100.0])
            bend = rng.uniform(-110, 110)
            control1 = origin + np.array([direction * rng.uniform(30, 130),
                                          -rng.uniform(35, 160)])
            control2 = destination + np.array([-direction * rng.uniform(20, 150), bend])
            depth = 1.75 if hero else (1.17 if route == 3 else (0.63 if route == 4 else 1.0))
            size = (rng.uniform(63, 83) if hero else rng.uniform(32, 62)) * depth
            size *= min(self.width / 960, self.height / 540)
            crows.append(Crow(origin, control1, control2, destination,
                              float(launches[index]),
                              float(min(rng.uniform(1.45, 1.85), EFFECT_SECONDS - launches[index] - .08)), size,
                              float(rng.uniform(0, 2 * math.pi)),
                              float(rng.uniform(2.0, 2.9) if hero else rng.uniform(2.6, 3.8)),
                              depth, hero))
        self.crows = crows
        self.feathers = []
        scale = min(self.width / 960, self.height / 540)
        for index in rng.choice(CROW_COUNT, size=34, replace=False):
            crow = crows[int(index)]
            destination = crow.origin + np.array([
                rng.uniform(-165, 165) * scale, -rng.uniform(45, 160) * scale,
            ], np.float32)
            self.feathers.append(Feather(crow.origin, destination,
                                         crow.launch + float(rng.uniform(.06, .19)),
                                         float(rng.uniform(.68, 1.25)),
                                         float(rng.uniform(7, 15) * scale),
                                         float(rng.uniform(-math.pi, math.pi)),
                                         float(rng.uniform(-4.5, 4.5))))
        self.sprites = load_crow_sprites()
        eyes = load_sharingan_art()
        eye_width = min(round(self.width * .62), round(self.height * 1.16))
        eye_height = round(eye_width * eyes.shape[0] / eyes.shape[1])
        self.sharingan = cv2.resize(eyes, (eye_width, eye_height), interpolation=cv2.INTER_AREA)
        self._blood_frame: np.ndarray | None = None
        self.release_map = self._release_map(chosen, launches, rng)
        self.sprite_cache: dict[tuple[int, int], np.ndarray] = {}
        self.rotated_cache: dict[tuple[int, int, int], np.ndarray] = {}

    def _release_map(self, origins: np.ndarray, launches: np.ndarray, rng) -> np.ndarray:
        scale = 4
        hh = max(1, (self.height + scale - 1) // scale)
        ww = max(1, (self.width + scale - 1) // scale)
        ys, xs = np.mgrid[:hh, :ww].astype(np.float32)
        xs *= scale
        ys *= scale
        nearest = np.full((hh, ww), np.inf, np.float32)
        release = np.zeros((hh, ww), np.float32)
        for (row, column), launch in zip(origins, launches):
            distance = (xs - column) ** 2 + (ys - row) ** 2
            closer = distance < nearest
            nearest[closer] = distance[closer]
            release[closer] = launch
        # Small organic tear across each territory, rather than whole-body
        # fading or identical tile boundaries.
        noise = rng.uniform(-.055, .055, (max(2, hh // 6), max(2, ww // 6))).astype(np.float32)
        noise = cv2.resize(noise, (ww, hh), interpolation=cv2.INTER_CUBIC)
        release = np.clip(release + noise + .10, .09, BODY_RELEASE_SECONDS - .06)
        release = cv2.resize(release, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        # Each departing bird cuts a matching winged hole in the source body.
        # The Voronoi territories above finish removing the tissue between
        # those distinct bird silhouettes.
        for crow in self.crows:
            bird_width = max(14, round(crow.size * 2.15))
            bird_height = max(10, round(bird_width * 128 / 176))
            wing = cv2.resize(self.sprites[2][:, :, 3], (bird_width, bird_height),
                              interpolation=cv2.INTER_LINEAR)
            x = round(crow.origin[0] - bird_width * .5)
            y = round(crow.origin[1] - bird_height * .5)
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(self.width, x + bird_width), min(self.height, y + bird_height)
            if x1 < x2 and y1 < y2:
                target = release[y1:y2, x1:x2]
                silhouette = wing[y1 - y:y2 - y, x1 - x:x2 - x] > 110
                np.minimum(target, crow.launch + .035, out=target, where=silhouette)
        # Preserve a connected neck/torso core while the shoulders fragment.
        # The head then breaks up before that core, avoiding a floating face.
        left, top, width, height = self.bounds
        y1, y2 = top, min(self.height, top + height)
        x1, x2 = left, min(self.width, left + width)
        region = release[y1:y2, x1:x2]
        yy, xx = np.ogrid[y1:y2, x1:x2]
        vertical = (yy - top) / max(1, height)
        central = np.abs(xx - (left + width * .5)) < width * .18
        core = (vertical >= .18) & (vertical < .76) & central
        np.maximum(region, 1.86, out=region, where=core)
        head = (vertical < .22) & (self.mask[y1:y2, x1:x2] > .48)
        np.clip(region, 1.03, 1.70, out=region, where=head)
        return release

    def _draw_crow(self, frame: np.ndarray, crow: Crow, age: float) -> None:
        progress = (age - crow.launch) / crow.duration
        if progress < 0 or progress > 1:
            return
        t = float(np.clip(progress, 0, 1))
        point = _cubic(crow.origin, crow.control1, crow.control2, crow.destination, t)
        tangent = _cubic(crow.origin, crow.control1, crow.control2, crow.destination,
                         min(1.0, t + .015)) - point
        angle = float(np.degrees(math.atan2(tangent[1], tangent[0])))
        # The sprite faces the viewer; lean toward travel without hiding wings.
        angle = float(np.clip(angle * .22, -30, 30))
        pose = int(((age - crow.launch) * crow.frequency + crow.phase / (2 * math.pi)) * 5) % 5
        scale = (1.0 + .38 * t if crow.depth > 1.1 else
                 1.0 - .42 * t if crow.depth < .8 else 1.0)
        if crow.depth > 1.1 and .12 < t < .90:
            previous = _cubic(crow.origin, crow.control1, crow.control2,
                              crow.destination, max(0.0, t - (.10 if crow.hero else .055)))
            direction = point - previous
            norm = float(np.linalg.norm(direction))
            if norm > 3:
                side = np.array([-direction[1], direction[0]]) / norm
                for sign in (-1, 1):
                    offset = side * sign * crow.size * (.27 if crow.hero else .18)
                    start = tuple(np.rint(previous + offset).astype(int))
                    end = tuple(np.rint(point + offset * .60).astype(int))
                    cv2.line(frame, start, end, (43, 44, 51),
                             2 if crow.hero else 1, cv2.LINE_AA)
        target_width = max(12, int(round(crow.size * 2.15 * scale / 4) * 4))
        key = (pose, target_width)
        sprite = self.sprite_cache.get(key)
        if sprite is None:
            target_height = max(8, round(target_width * 128 / 176))
            sprite = cv2.resize(self.sprites[pose], (target_width, target_height),
                                interpolation=cv2.INTER_AREA if target_width < 176 else cv2.INTER_LINEAR)
            if len(self.sprite_cache) < 600:
                self.sprite_cache[key] = sprite
        angle_bucket = round(angle / 10) * 10
        rotation_key = (pose, target_width, angle_bucket)
        rotated = self.rotated_cache.get(rotation_key)
        if rotated is None:
            sh, sw = sprite.shape[:2]
            padding = max(6, int(max(sw, sh) * .25))
            transform = cv2.getRotationMatrix2D((sw / 2, sh / 2), angle_bucket, 1)
            transform[:, 2] += padding
            rotated = cv2.warpAffine(sprite, transform, (sw + 2 * padding, sh + 2 * padding),
                                     flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            if len(self.rotated_cache) < 800:
                self.rotated_cache[rotation_key] = rotated
        x = round(point[0] - rotated.shape[1] / 2)
        y = round(point[1] - rotated.shape[0] / 2)
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(self.width, x + rotated.shape[1]), min(self.height, y + rotated.shape[0])
        if x1 >= x2 or y1 >= y2:
            return
        patch = rotated[y1 - y:y2 - y, x1 - x:x2 - x]
        alpha = patch[:, :, 3:4].astype(np.float32) * (1 / 255)
        # Short appearance window: emerging feathers form the boundary of
        # each disappearing body region.
        alpha *= min(1.0, (age - crow.launch) / .10)
        dest = frame[y1:y2, x1:x2]
        dest[:] = (dest * (1.0 - alpha) + patch[:, :, :3] * alpha).astype(np.uint8)

    def _draw_feather(self, frame: np.ndarray, feather: Feather, age: float) -> None:
        progress = (age - feather.launch) / feather.duration
        if not 0 <= progress <= 1:
            return
        t = float(progress)
        point = feather.origin * (1.0 - t) + feather.destination * t
        point[1] -= math.sin(math.pi * t) * feather.size * 2.5
        angle = feather.angle + feather.spin * t
        axis = np.array([math.cos(angle), math.sin(angle)]) * feather.size
        side = np.array([-axis[1], axis[0]])
        shape = np.rint([point + axis, point + side * .30,
                         point - axis * .70, point - side * .20]).astype(np.int32)
        margin = max(3, int(feather.size * 2))
        x, y = int(point[0]), int(point[1])
        x1, y1 = max(0, x - margin), max(0, y - margin)
        x2, y2 = min(self.width, x + margin + 1), min(self.height, y + margin + 1)
        if x1 >= x2 or y1 >= y2:
            return
        destination = frame[y1:y2, x1:x2]
        overlay = destination.copy()
        shape[:, 0] -= x1
        shape[:, 1] -= y1
        cv2.fillPoly(overlay, [shape], (15, 17, 24), cv2.LINE_AA)
        cv2.line(overlay, tuple(shape[2]), tuple(shape[0]), (53, 55, 63), 1, cv2.LINE_AA)
        opacity = min(1.0, (1.0 - t) * 3.5, (age - feather.launch) * 12)
        cv2.addWeighted(overlay, opacity, destination, 1.0 - opacity, 0, dst=destination)

    def _draw_ink_edge(self, frame: np.ndarray, timeline: float) -> None:
        left, top, width, height = self.bounds
        release = self.release_map[top:top + height, left:left + width]
        person = self.mask[top:top + height, left:left + width]
        front = ((release > timeline - .015) & (release < timeline + .070)
                 & (person > .48)).astype(np.uint8)
        if not np.any(front):
            return
        edge = cv2.dilate(front, np.ones((3, 3), np.uint8)) > 0
        region = frame[top:top + height, left:left + width]
        region[edge] = (region[edge].astype(np.uint16) * 3 // 10 +
                        np.array((15, 16, 22), np.uint16) * 7 // 10).astype(np.uint8)

    def _blood_background(self, background: np.ndarray, timeline: float) -> np.ndarray:
        """Semi-transparent crimson ink over the actual captured room."""
        strength = _smoothstep(.08, 1.10, timeline)
        if strength <= 0:
            return background.copy()
        if self._blood_frame is None:
            rng = np.random.default_rng(1903)
            coarse = rng.random((max(4, self.height // 58), max(5, self.width // 58))).astype(np.float32)
            fine = rng.random((max(8, self.height // 15), max(10, self.width // 15))).astype(np.float32)
            coarse = cv2.resize(coarse, (self.width, self.height), interpolation=cv2.INTER_CUBIC)
            fine = cv2.resize(fine, (self.width, self.height), interpolation=cv2.INTER_CUBIC)
            pattern = np.clip(coarse * .66 + fine * .34, 0, 1)
            red_alpha = (.60 + .20 * pattern)[:, :, None]
            crimson = np.array((15, 10, 200), np.float32)
            colored = background.astype(np.float32) * (1 - red_alpha) + crimson * red_alpha
            ink = np.clip((.36 - pattern) * 1.25, 0, .30)[:, :, None]
            colored = colored * (1 - ink) + np.array((9, 10, 17), np.float32) * ink
            self._blood_frame = np.clip(colored, 0, 255).astype(np.uint8)
        if strength >= 1:
            return self._blood_frame.copy()
        return cv2.addWeighted(background, 1.0 - strength, self._blood_frame, strength, 0)

    def _draw_sharingan(self, frame: np.ndarray, timeline: float) -> None:
        opacity = (_smoothstep(.28, .66, timeline)
                   * (1.0 - _smoothstep(1.65, 2.38, timeline)))
        if opacity <= 0:
            return
        opacity *= .93 + .07 * math.sin(timeline * 6.0) ** 2
        eyes = self.sharingan
        x = (self.width - eyes.shape[1]) // 2
        y = max(3, round(self.height * .018))
        bottom = min(self.height, y + eyes.shape[0])
        if bottom <= y:
            return
        eyes = eyes[:bottom - y]
        destination = frame[y:bottom, x:x + eyes.shape[1]]
        alpha = eyes[:, :, 3:4].astype(np.float32) * (opacity / 255.0)
        destination[:] = (destination * (1.0 - alpha) +
                          eyes[:, :, :3] * alpha).astype(np.uint8)

    def render(self, background: np.ndarray, age: float, appearing: bool = False) -> np.ndarray:
        if background.shape != self.source.shape:
            raise ValueError("Sfondo e fotogramma devono avere la stessa dimensione")
        if age >= EFFECT_SECONDS:
            return self.source.copy() if appearing else self._blood_background(background, EFFECT_SECONDS)
        timeline = EFFECT_SECONDS - max(0.0, age) if appearing else max(0.0, age)
        remaining = np.clip((self.release_map - timeline) / .055, 0, 1)
        alpha = (self.mask * remaining)[:, :, None]
        output = self._blood_background(background, timeline)
        # Distant birds sit behind the remaining silhouette, foreground birds
        # cover it. Both groups originate at actual body mask samples.
        for crow in self.crows:
            if crow.depth < .8:
                self._draw_crow(output, crow, timeline)
        output = (output * (1.0 - alpha) + self.source * alpha).astype(np.uint8)
        self._draw_ink_edge(output, timeline)
        for feather in self.feathers:
            self._draw_feather(output, feather, timeline)
        self._draw_sharingan(output, timeline)
        for crow in self.crows:
            if crow.depth >= .8:
                self._draw_crow(output, crow, timeline)
        return output
