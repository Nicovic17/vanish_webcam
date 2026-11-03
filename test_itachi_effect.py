import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

import cv2
import numpy as np

from local_app.itachi_effect import (
    BODY_RELEASE_SECONDS, EFFECT_SECONDS, ItachiCrowEffect,
    ItachiGestureGate, ItachiPoseRecognizer, hands_touch_at_chest,
    load_sharingan_art,
)
from local_app import vanish_cam as app


def hand(x, y=.47):
    points = [SimpleNamespace(x=x, y=y) for _ in range(21)]
    points[0] = SimpleNamespace(x=x, y=y + .09)
    for index, offset in ((5, -.025), (9, -.008), (13, .008), (17, .025)):
        points[index] = SimpleNamespace(x=x + offset, y=y)
    for index, offset in ((4, -.025), (8, -.025), (12, -.008),
                          (16, .008), (20, .025)):
        points[index] = SimpleNamespace(x=x + offset, y=y - .07)
    return points


def scene():
    background = np.full((240, 320, 3), (96, 157, 191), np.uint8)
    person = background.copy()
    mask = np.zeros((240, 320), np.float32)
    cv2.ellipse(mask, (160, 115), (60, 105), 0, 0, 360, 1, -1)
    person[mask > .5] = (145, 95, 55)
    return person, background, mask


class ItachiGestureTests(unittest.TestCase):
    def test_full_menu_selects_itachi_with_seven(self):
        with patch.object(app.cv2, "namedWindow"), patch.object(app.cv2, "setMouseCallback"), \
             patch.object(app.cv2, "imshow"), patch.object(app.cv2, "destroyWindow"), \
             patch.object(app.cv2, "waitKey", return_value=ord("5")), \
             patch.object(app.cv2, "getWindowProperty", return_value=1):
            self.assertEqual(app.choose_mode(), "itachi")

    def test_contact_is_required_at_centre_of_chest(self):
        _, _, mask = scene()
        self.assertTrue(hands_touch_at_chest([hand(.47), hand(.53)], mask))
        self.assertFalse(hands_touch_at_chest([hand(.47)], mask))
        self.assertFalse(hands_touch_at_chest([hand(.25), hand(.75)], mask))
        self.assertFalse(hands_touch_at_chest([hand(.47, .09), hand(.53, .09)], mask))
        self.assertFalse(hands_touch_at_chest([hand(.76), hand(.82)], mask))

    def test_gate_triggers_immediately_and_requires_release(self):
        gate = ItachiGestureGate()
        self.assertTrue(gate.update(True, 1.0))
        self.assertFalse(gate.update(True, 1.1))
        self.assertFalse(gate.update(False, 2.0))
        self.assertFalse(gate.update(False, 2.26))
        self.assertTrue(gate.update(True, 2.35))

    def test_hand_recognizer_uses_video_frame(self):
        frame, _, mask = scene()
        primary, fallback = Mock(), Mock()
        primary.detect_for_video.return_value = SimpleNamespace(
            hand_landmarks=[hand(.47), hand(.53)])
        image = app.mp.Image(image_format=app.mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        recognizer = ItachiPoseRecognizer(primary, fallback)
        self.assertTrue(recognizer.recognize_pose(image, 100, mask))
        fallback.detect.assert_not_called()


class ItachiAnimationTests(unittest.TestCase):
    def test_local_body_removal_crows_flap_and_final_frame_is_clean(self):
        person, background, mask = scene()
        effect = ItachiCrowEffect(person, mask)
        self.assertEqual(len(effect.crows), 78)
        self.assertEqual(sum(crow.hero for crow in effect.crows), 4)
        self.assertGreaterEqual(len(effect.feathers), 30)
        self.assertGreater(float(np.percentile(effect.release_map[mask > .5], 75)), 1.8)
        self.assertGreaterEqual(float(effect.release_map[75, 160]), 1.86)
        self.assertLessEqual(float(effect.release_map[35, 160]), 1.71)
        first = effect.render(background, 0)
        middle = effect.render(background, BODY_RELEASE_SECONDS * .55)
        later = effect.render(background, BODY_RELEASE_SECONDS)
        final = effect.render(background, EFFECT_SECONDS)
        self.assertTrue(np.array_equal(first, person))
        self.assertGreater(np.count_nonzero(np.any(middle != person, axis=2)), 100)
        self.assertFalse(np.array_equal(middle, later))
        self.assertFalse(np.array_equal(final, background))
        self.assertLess(int(final[0, 0, 0]), int(background[0, 0, 0]))
        self.assertTrue(np.array_equal(final, effect.render(background, EFFECT_SECONDS + 1)))
        self.assertFalse(np.array_equal(effect.sprites[0], effect.sprites[2]))

    def test_sharingan_appears_briefly_without_a_black_rectangle(self):
        person, background, mask = scene()
        art = load_sharingan_art()
        self.assertEqual(art.shape[2], 4)
        self.assertEqual(int(art[0, 0, 3]), 0)
        self.assertTrue(np.all(art[:, 0, 3] == 0))
        self.assertTrue(np.all(art[:, -1, 3] == 0))
        effect = ItachiCrowEffect(person, mask)
        with_eyes = effect.render(background, 1.0)
        with patch.object(effect, '_draw_sharingan'):
            without_eyes = effect.render(background, 1.0)
        self.assertFalse(np.array_equal(with_eyes[:90], without_eyes[:90]))
        late = effect.render(background, 3.0)
        with patch.object(effect, '_draw_sharingan'):
            late_without_eyes = effect.render(background, 3.0)
        self.assertTrue(np.array_equal(late, late_without_eyes))

    def test_reverse_animation_reconstructs_person(self):
        person, background, mask = scene()
        effect = ItachiCrowEffect(person, mask)
        self.assertTrue(np.array_equal(effect.render(background, 0, appearing=True),
                                       effect.render(background, EFFECT_SECONDS)))
        self.assertTrue(np.array_equal(effect.render(background, EFFECT_SECONDS, appearing=True), person))


if __name__ == "__main__":
    unittest.main()
