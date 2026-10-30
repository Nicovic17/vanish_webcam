"""Procedural silhouette effects with reusable buffers and deterministic particles."""
from __future__ import annotations

import math
import cv2
import numpy as np


MODES = (
    ("normal", "NORMAL VANISH", "V sign / dissolve"),
    ("naruto", "NARUTO VANISH", "Palms together / smoke and log"),
    ("particles", "PARTICLES", "V sign / wind-blown fragments"),
    ("goku", "GOKU", "Two fingers at forehead / hold 1 sec"),
    ("piccolo", "PICCOLO", "V sign / green ki and rising energy"),
    ("burn", "FULL BURN AND ASH", "V sign / flames, embers and ash"),
    ("whoosh", "SIMPLE WHOOSH", "V sign / quick disappearance"),
    ("electric", "ELECTRIC BLINK", "V sign / blue sparks and teleport"),
)
DURATIONS = dict(normal=3.6, naruto=1.45, particles=2.1, goku=0.75,
                 piccolo=1.65, burn=2.8, whoosh=0.4, electric=0.7)


class SilhouetteEffect:
    """One frozen subject per transition. Output is valid until the next render.

    Geometry, noise and particle trajectories are seeded at setup. Reduced-size
    effect fields are enlarged into reusable buffers; the camera/background stay
    at their original resolution. No elapsed time is accumulated per frame.
    """
    def __init__(self, frame, mask, mode, effect_width=None):
        if effect_width is None:
            effect_width = 320 if mode == "burn" else 480
        self.mode = mode
        self.frame = frame.copy()
        self.height, self.width = frame.shape[:2]
        self.scale = min(1.0, effect_width / self.width)
        self.size = (max(1, round(self.width * self.scale)),
                     max(1, round(self.height * self.scale)))
        w, h = self.size
        self.mask = cv2.resize(mask, self.size, interpolation=cv2.INTER_LINEAR)
        self.mask = np.ascontiguousarray(self.mask, dtype=np.float32)
        np.clip(self.mask, 0, 1, out=self.mask)
        self.alpha = np.empty_like(self.mask)
        self.work = np.empty_like(self.mask)
        self.light = np.zeros_like(self.mask)
        self.glow = np.zeros((h, w, 3), np.uint8)
        self.full_glow = np.empty_like(frame)
        self.full_alpha = np.empty((self.height, self.width), np.float32)
        self.inverse = np.empty_like(self.full_alpha)
        self.output = np.empty_like(frame)
        self.colored = np.empty_like(frame)
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self.outline = cv2.dilate(self.mask, self.kernel) - self.mask
        points = cv2.findNonZero((self.mask > 0.25).astype(np.uint8))
        self.bounds = cv2.boundingRect(points) if points is not None else (0, 0, w, h)
        x, y, bw, bh = self.bounds
        if mode == "normal":
            self.low_area = np.s_[:, :]
            self.area = np.s_[:, :]
        else:
            left, top = max(0, x - 12), max(0, y - 12)
            right, bottom = min(w, x + bw + 12), min(h, y + bh + 12)
            self.low_area = np.s_[top:bottom, left:right]
            self.area = np.s_[round(top / self.scale):min(self.height, round(bottom / self.scale)),
                              round(left / self.scale):min(self.width, round(right / self.scale))]
        self.area_size = (self.output[self.area].shape[1], self.output[self.area].shape[0])
        self.cx, self.cy = (x + bw / 2) / self.scale, (y + bh / 2) / self.scale
        self.body_width, self.body_height = bw / self.scale, bh / self.scale
        self.head_y = (y + bh * 0.10) / self.scale
        yy, xx = np.mgrid[:h, :w].astype(np.float32)
        self.up = np.clip(1 - (yy - y) / max(bh, 1), 0, 1)
        self.side = np.clip((xx - x) / max(bw, 1), 0, 1)
        rng = np.random.default_rng(7391)
        coarse = rng.random((max(2, h // 10), max(2, w // 10)), dtype=np.float32)
        coarse = cv2.resize(coarse, self.size, interpolation=cv2.INTER_CUBIC)
        self.noise = rng.random((h, w), dtype=np.float32)
        self.field = np.clip(self.up * .72 + coarse * .17 + self.noise * .08
                             + np.sin(xx / max(w, 1) * 18) * .025, 0, 1)
        self.burn_field = np.clip(self.up * .85 + coarse * .12, 0, 1)
        self.particle_field = self.side * .8 + self.noise * .12
        self.aura = cv2.GaussianBlur(cv2.dilate(self.outline, self.kernel), (0, 0), 2.5)
        # Vectorized setup avoids hundreds of Python/RNG calls after a gesture.
        ys, xs = np.nonzero(self.mask > .65)
        count = min(1000 if mode == "particles" else 360, len(xs))
        indices = rng.choice(len(xs), count, replace=False)
        xs, ys = xs[indices], ys[indices]
        self.px = xs.astype(np.float32) / self.scale
        self.py = ys.astype(np.float32) / self.scale
        self.speed = rng.uniform(.6, 1.4, count).astype(np.float32)
        self.spread = rng.uniform(-1, 1, count).astype(np.float32)
        self.sizes = rng.uniform(.6, 1.7, count).astype(np.float32)
        self.colors = self.frame[np.minimum(self.height - 1, self.py.astype(int)),
                                 np.minimum(self.width - 1, self.px.astype(int))].astype(np.float32)
        self.births = ((self.px - (self.cx - self.body_width / 2)) / max(self.body_width, 1) * .55
                       if mode == "particles" else .10 + self.up[ys, xs] * .48)
        self.radii = np.clip(np.rint(self.sizes * self.height / 720 *
                                     (2 if mode == "particles" else 1.5)), 1, 3).astype(np.int32)
        self.flame_phase = xx * .35 + coarse * 7
        self.streaks = tuple(zip(rng.uniform(.08, .92, 22), rng.uniform(.08, .45, 22),
                                rng.uniform(0, 1, 22)))
        # Freeze winding bolt paths once; render only changes their envelope.
        self.bolts = []
        for side in (-1, 1):
            path = []
            for i in range(13):
                bx = self.cx + side * self.body_width * (.43 + rng.uniform(-.12, .12))
                by = y / self.scale + i / 12 * self.body_height
                path.append((round(bx), round(by)))
            self.bolts.append(np.asarray(path, np.int32))

    def _survival(self, field, threshold, softness=.07):
        np.subtract(field, threshold - softness, out=self.alpha)
        self.alpha /= 2 * softness
        np.clip(self.alpha, 0, 1, out=self.alpha)
        # Smoothstep with scratch arrays, retaining the original dissolve shape.
        np.multiply(self.alpha, -2, out=self.work)
        self.work += 3
        self.alpha *= self.alpha
        self.alpha *= self.work
        self.alpha *= self.mask

    def _color_light(self, color, amount=1.0):
        np.multiply(self.light, amount, out=self.work)
        np.clip(self.work, 0, 1, out=self.work)
        for channel in range(3):
            np.multiply(self.work, color[channel], out=self.alpha)
            self.glow[:, :, channel] = self.alpha
        cv2.resize(self.glow[self.low_area], self.area_size, dst=self.full_glow[self.area],
                   interpolation=cv2.INTER_LINEAR)
        cv2.add(self.output[self.area], self.full_glow[self.area], dst=self.output[self.area])

    def render(self, background, progress, live_frame=None, live_mask=None):
        p = float(np.clip(progress, 0, 1))
        source = self.frame if live_frame is None else live_frame
        if p <= 0:
            np.copyto(self.output, source)
            return self.output
        if p >= 1:
            np.copyto(self.output, background)
            return self.output
        if live_mask is not None:
            cv2.resize(live_mask, self.size, dst=self.mask, interpolation=cv2.INTER_LINEAR)
        mode = self.mode
        self.light.fill(0)
        if mode == "normal":
            eased = p  # Start dissolving immediately after recognition.
            self._survival(self.field, eased)
            np.subtract(self.field, eased, out=self.work)
            np.abs(self.work, out=self.work)
            self.light[:] = (self.work < .018) & (self.mask > .48) & (self.noise > .54)
            cv2.GaussianBlur(self.light, (0, 0), 2.5, dst=self.light)
            self.light *= 3.2
            color = (255, 228, 92)
        elif mode == "particles":
            self._survival(self.particle_field, p * 1.15)
            color = (0, 0, 0)
        elif mode == "piccolo":
            self._survival(self.burn_field, max(0, (p - .20) / .63))
            envelope = math.sin(min(1, p / .8) * math.pi) ** 2
            ripple = .65 + .35 * np.sin(self.flame_phase * .45 - p * 18) ** 2
            self.light[:] = (self.outline * .22 + self.aura * 1.8) * envelope * ripple * 1.6
            color = (120, 255, 160)
        elif mode == "burn":
            threshold = max(0, (p - .12) / .65)
            self._survival(self.burn_field, threshold, .05)
            # Charcoal develops ahead of the flame front; flame edge moves upward.
            np.subtract(self.burn_field, threshold, out=self.work)
            np.abs(self.work, out=self.work)
            self.light[:] = np.maximum(0, 1 - self.work / .13) * self.mask
            # Wavering flame tongues grow above the burn front, with a hot core.
            tongues = (.5 + .5 * np.sin(self.flame_phase + p * 33)) ** 3
            delta = self.burn_field - threshold
            flames = np.clip(1 - np.abs(delta - tongues * .08) / .10, 0, 1)
            self.light[:] = flames * self.mask
            cv2.GaussianBlur(self.light, (0, 0), .7, dst=self.light)
            cv2.convertScaleAbs(source[self.area], dst=self.colored[self.area], alpha=max(.12, 1 - p * 2.5))
            source = self.colored
            color = (20, 130, 255)
        elif mode in ("goku", "electric"):
            remaining = max(0, 1 - max(0, p - .25) / .20)
            np.multiply(self.mask, remaining, out=self.alpha)
            flash = max(0, 1 - abs(p - .32) / .09)
            self.light[:] = self.mask * flash * .9
            if mode == "goku":
                # Uneven tapered streaks replace the rigid barcode pattern.
                x0, y0, bw, bh = self.bounds
                strength = math.sin(p * math.pi) ** 2
                for fraction, length, phase in self.streaks:
                    sx = round(x0 + bw * fraction)
                    sy = round(y0 + bh * ((phase - p * 1.8) % 1))
                    tip = max(0, round(sy - bh * length))
                    cv2.line(self.light, (sx, sy), (sx, tip), strength, 1, cv2.LINE_AA)
                cv2.GaussianBlur(self.light, (0, 0), .6, dst=self.light)
                self.light *= self.mask
            else:
                self.light += self.outline * math.sin(p * math.pi) ** 2
            color = (255, 245, 220) if mode == "goku" else (255, 190, 60)
        else:  # Minimal whoosh, 0.4 seconds in total.
            np.multiply(self.mask, max(0, 1 - p / .48), out=self.alpha)
            color = (0, 0, 0)

        cv2.resize(self.alpha[self.low_area], self.area_size, dst=self.full_alpha[self.area],
                   interpolation=cv2.INTER_LINEAR)
        np.subtract(1, self.full_alpha[self.area], out=self.inverse[self.area])
        np.copyto(self.output, background)
        cv2.blendLinear(source[self.area], background[self.area], self.full_alpha[self.area],
                        self.inverse[self.area], dst=self.output[self.area])
        if mode not in ("particles", "whoosh"):
            self._color_light(color)
        if mode == "burn":
            # Amber outer flame plus a smaller pale-yellow hot core.
            self.light[:] = np.maximum(0, self.light - .68) * 2.5
            self._color_light((90, 210, 255), .65)
        if mode in ("particles", "piccolo", "burn", "electric"):
            self._draw_particles(p)
        if mode == "piccolo" and .12 < p < .58:
            strength = math.sin((p - .12) / .46 * math.pi)
            radius = self.body_width * (.35 + p * 1.4)
            cv2.ellipse(self.output, (int(self.cx), int(self.cy)),
                        (max(1, int(radius)), max(1, int(radius * .25))), 0, 0, 360,
                        (int(170 * strength), int(255 * strength), int(195 * strength)),
                        max(1, round(self.width / 500)), cv2.LINE_AA)
        if mode == "whoosh":
            fade = max(0, 1 - p)
            length = self.body_width * (.25 + p * .50)
            for side in (-1, -.65, .65, 1):
                x1 = self.cx + side * self.body_width * .26
                x2 = x1 + side * length
                y = self.head_y + side * self.body_height * .025
                # Curved tapered airflow, with staggered lengths.
                path = np.asarray([(round(x1), round(y)),
                                   (round((x1+x2)/2), round(y-self.body_height*.025)),
                                   (round(x2), round(y-self.body_height*.01))], np.int32)
                cv2.polylines(self.output, [path], False, (int(225 * fade),) * 3,
                              max(1, round(self.width / 650)), cv2.LINE_AA)
        if mode == "electric" and .08 < p < .9:
            strength = math.sin(p * math.pi)
            for index, original in enumerate(self.bolts):
                bolt = original.copy()
                bolt[:, 0] += (np.sin(np.arange(len(bolt)) * 2.7 + p * 65 + index) * self.body_width * .035).astype(np.int32)
                cv2.polylines(self.output, [bolt], False, (int(255 * strength), int(180 * strength), 30),
                              max(2, round(self.width / 250)), cv2.LINE_AA)
                cv2.polylines(self.output, [bolt], False, tuple(int(v * strength) for v in (240, 250, 255)), 1, cv2.LINE_AA)
                for vertex in (3, 7, 10):
                    origin = bolt[vertex]
                    end = origin + np.array([(-1 if index == 0 else 1)*self.body_width*.10,
                                             -self.body_height*.06], np.int32)
                    cv2.line(self.output, tuple(origin), tuple(end),
                             (int(255*strength), int(170*strength), 50), 1, cv2.LINE_AA)
        return self.output

    def _draw_particles(self, p):
        if not len(self.px):
            return
        mode = self.mode
        unit = self.height / 720
        age = np.maximum(0, p - self.births)
        fade = np.minimum(np.minimum(1, age / .07), (1 - p) / .20)
        if mode == "piccolo":
            x = self.px + self.spread * age * 70 * unit
            y = self.py - age * (150 + 280 * self.speed) * unit
            colors = np.where((self.sizes > 1)[:, None], (170, 255, 190), (80, 225, 100))
        elif mode == "electric":
            x = self.px + self.spread * age * 180 * unit
            y = self.py - age * self.speed * 180 * unit
            colors = np.broadcast_to((255, 205, 110), self.colors.shape)
        elif mode == "burn":
            x = self.px + age ** 1.3 * (230 + self.speed * 220) * unit
            y = self.py - age * 95 * unit + self.spread * age * 100 * unit
            ember = self.sizes > 1.35
            y += ember * age * age * 240 * unit
            colors = np.where(ember[:, None], (20, 110, 255), (115, 120, 125))
        else:
            x = self.px + age ** 1.25 * (190 + self.speed * 230) * unit
            y = self.py + self.spread * age * 130 * unit - age * 45 * unit
            y += np.sin(age * 11 + self.speed * 6) * age * 22 * unit
            colors = self.colors
        x, y = np.rint(x).astype(np.int32), np.rint(y).astype(np.int32)
        # Draw the fixed pool in a few vectorized batches instead of hundreds of
        # Python calls. Small diamond fragments have soft outer pixels.
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                distance = abs(dx) + abs(dy)
                if distance > 3:
                    continue
                sx, sy = x + dx, y + dy
                visible = ((age > 0) & (self.radii >= distance) &
                           (sx >= 0) & (sx < self.width) & (sy >= 0) & (sy < self.height))
                if not np.any(visible):
                    continue
                xs, ys = sx[visible], sy[visible]
                opacity = (fade[visible] * (1 if distance == 0 else .65))[:, None]
                base = self.output[ys, xs].astype(np.float32)
                self.output[ys, xs] = base * (1 - opacity) + colors[visible] * opacity
