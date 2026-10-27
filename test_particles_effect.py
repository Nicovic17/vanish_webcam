import unittest

import numpy as np

from local_app.particles_effect import PARTICLE_SECONDS, ParticleEffect


class ParticleEffectTests(unittest.TestCase):
    def setUp(self):
        self.background = np.full((120, 180, 3), 35, np.uint8)
        self.frame = self.background.copy()
        self.frame[15:110, 35:120] = (80, 145, 210)
        self.mask = np.zeros((120, 180), np.float32)
        self.mask[15:110, 35:120] = 1.0

    def test_body_breaks_into_particles_then_disappears(self):
        effect = ParticleEffect(self.frame, self.mask, seed=7)
        start = effect.render(self.background, 0.0)
        middle = effect.render(self.background, 0.6)
        end = effect.render(self.background, PARTICLE_SECONDS)
        self.assertTrue(np.any(start != self.background))
        self.assertTrue(np.any(middle != start))
        np.testing.assert_array_equal(end, self.background)
        self.assertTrue(np.all(effect.speed_x > 0))

    def test_no_person_and_mismatched_background(self):
        effect = ParticleEffect(self.frame, np.zeros_like(self.mask), seed=7)
        np.testing.assert_array_equal(effect.render(self.background, 0.5), self.background)
        weak = ParticleEffect(self.frame, np.full_like(self.mask, 0.1), seed=7)
        np.testing.assert_array_equal(weak.render(self.background, 0.5), self.background)
        with self.assertRaises(ValueError):
            effect.render(self.background[:80], 0.5)


if __name__ == "__main__":
    unittest.main()
