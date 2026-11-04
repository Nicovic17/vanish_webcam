"""Lightweight wind-blown particle disappearance from a captured silhouette."""

from __future__ import annotations

import cv2
import numpy as np


PARTICLE_SECONDS = 2.1
BODY_SECONDS = 1.05
MAX_PARTICLES = 1800


class ParticleEffect:
    """Capture the person once, then render the effect without more inference."""

    def __init__(self, frame: np.ndarray, mask: np.ndarray, seed: int | None = None):
        height, width = mask.shape
        self.frame_size = (height, width)
        self.bounds: tuple[int, int, int, int] | None = None
        self.rng = np.random.default_rng(seed)
        occupied = cv2.findNonZero((mask > 0.02).astype(np.uint8))
        if occupied is None:
            return

        x, y, body_width, body_height = cv2.boundingRect(occupied)
        self.bounds = (x, y, x + body_width, y + body_height)
        area = np.s_[y:y + body_height, x:x + body_width]
        self.person = frame[area].copy()
        self.mask = mask[area].copy()

        # A soft, irregular front erodes the body as the wind carries pixels away.
        horizontal = np.linspace(0.0, 1.0, body_width, dtype=np.float32)[None, :]
        noise = self.rng.random(
            (max(2, body_height // 18), max(2, body_width // 18)),
            dtype=np.float32,
        )
        noise = cv2.resize(noise, (body_width, body_height), interpolation=cv2.INTER_CUBIC)
        self.field = np.clip(horizontal + (noise - 0.5) * 0.16, 0.0, 1.0)

        coordinates = np.argwhere(mask > 0.45)
        count = min(MAX_PARTICLES, max(90, len(coordinates) // 80), len(coordinates))
        if count == 0:
            self.bounds = None
            return
        chosen = coordinates[self.rng.choice(len(coordinates), count, replace=False)]
        self.origins = chosen[:, ::-1].astype(np.float32)  # x, y
        self.colors = frame[chosen[:, 0], chosen[:, 1]].copy()
        bright = self.rng.random(count) < 0.20
        self.colors[bright] = (
            self.colors[bright].astype(np.float32) * 0.55
            + np.array((255, 229, 166), np.float32) * 0.45
        ).astype(np.uint8)
        relative_x = (self.origins[:, 0] - x) / max(body_width - 1, 1)
        self.release_at = np.clip(
            relative_x * BODY_SECONDS + self.rng.normal(0.0, 0.075, count),
            0.0, BODY_SECONDS,
        ).astype(np.float32)
        self.speed_x = self.rng.uniform(200, 420, count).astype(np.float32) * width / 960
        self.speed_y = -self.rng.uniform(15, 115, count).astype(np.float32) * height / 540
        self.acceleration = self.rng.uniform(70, 180, count).astype(np.float32) * width / 960
        self.sway = self.rng.uniform(3, 18, count).astype(np.float32) * height / 540
        self.phase = self.rng.uniform(0, 6.28, count).astype(np.float32)
        self.life = self.rng.uniform(0.65, 1.15, count).astype(np.float32)
        self.radius = self.rng.choice((1, 2, 3), count, p=(0.48, 0.42, 0.10))

    def render(self, background: np.ndarray, age: float) -> np.ndarray:
        if background.shape[:2] != self.frame_size:
            raise ValueError("Lo sfondo deve avere la dimensione del fotogramma acquisito")
        output = background.copy()
        if self.bounds is None or age >= PARTICLE_SECONDS:
            return output

        x1, y1, x2, y2 = self.bounds
        area = np.s_[y1:y2, x1:x2]
        front = max(0.0, age / BODY_SECONDS)
        if front < 1.08:
            survival = np.clip((self.field - front) * 13.0 + 0.5, 0.0, 1.0)
            alpha = (self.mask * survival)[:, :, None]
            background_area = background[area]
            body = (
                self.person.astype(np.float32) * alpha
                + background_area.astype(np.float32) * (1.0 - alpha)
            ).astype(np.uint8)
            edge = (np.abs(self.field - front) < 0.025) & (self.mask > 0.45)
            if np.any(edge):
                body[edge] = np.clip(
                    body[edge].astype(np.int16) + (45, 32, 12), 0, 255,
                ).astype(np.uint8)
            output[area] = body

        active = (self.release_at <= age) & (age - self.release_at < self.life)
        indexes = np.flatnonzero(active)
        if not len(indexes):
            return output
        elapsed = age - self.release_at[indexes]
        x = self.origins[indexes, 0] + self.speed_x[indexes] * elapsed
        x += 0.5 * self.acceleration[indexes] * elapsed * elapsed
        y = self.origins[indexes, 1] + self.speed_y[indexes] * elapsed
        y += self.sway[indexes] * np.sin(self.phase[indexes] + elapsed * 9.0) * elapsed
        x = np.rint(x).astype(np.int32)
        y = np.rint(y).astype(np.int32)
        visible = (x >= 0) & (x < output.shape[1]) & (y >= 0) & (y < output.shape[0])
        indexes, x, y, elapsed = indexes[visible], x[visible], y[visible], elapsed[visible]
        if not len(indexes):
            return output

        fade = np.clip((self.life[indexes] - elapsed) / 0.28, 0.0, 1.0)
        fade *= np.clip((PARTICLE_SECONDS - age) / 0.35, 0.0, 1.0)
        colors = self.colors[indexes].astype(np.float32)
        colors = colors * fade[:, None] + background[y, x] * (1.0 - fade[:, None])
        for index, px, py, color in zip(indexes, x, y, colors.astype(np.uint8)):
            bgr = tuple(int(channel) for channel in color)
            radius = int(self.radius[index])
            if radius > 1 and index % 5 == 0:
                cv2.line(output, (max(0, px - radius * 3), py + 1), (px, py), bgr, 1, cv2.LINE_AA)
            cv2.circle(output, (px, py), radius, bgr, -1, cv2.LINE_AA)
        return output
