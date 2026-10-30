import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

import vanish_cam as app
from naruto_effect import (
    EFFECT_SECONDS, falling_log_anchor, joined_hands_from_landmarks,
    landed_log_anchor, load_log, overlay_log, render_substitution, substitution_anchor,
)
from test_video_output import arguments


class JoinedHandsTests(unittest.TestCase):
    def test_joined_hands_start_effect_immediately(self):
        state = app.AppState(phase="ready")
        self.assertFalse(app.start_naruto_on_join(state, False, 1.0))
        self.assertTrue(app.start_naruto_on_join(state, True, 1.1))
        self.assertEqual(state.phase, "naruto_vanishing")
        self.assertEqual(state.vanish_started, 1.1)
        self.assertFalse(app.start_naruto_on_join(state, True, 1.2))

    @staticmethod
    def hand(center_x, upward=True):
        points = [SimpleNamespace(x=center_x, y=0.53) for _ in range(21)]
        points[0] = SimpleNamespace(x=center_x, y=0.70)
        for index, offset in ((5, -0.045), (9, -0.015), (13, 0.015), (17, 0.045)):
            points[index] = SimpleNamespace(x=center_x + offset, y=0.54 if upward else 0.84)
        for index, offset in ((8, -0.045), (12, -0.015), (16, 0.015), (20, 0.045)):
            points[index] = SimpleNamespace(x=center_x + offset, y=0.34 if upward else 1.04)
        return points

    def test_two_nearby_hands_recognized_but_one_or_separated_hands_are_not(self):
        left, right = self.hand(0.45), self.hand(0.55)
        self.assertTrue(joined_hands_from_landmarks([left, right], 640, 480))
        self.assertFalse(joined_hands_from_landmarks([left], 640, 480))
        self.assertFalse(joined_hands_from_landmarks([left, self.hand(0.83)], 640, 480))
        self.assertFalse(joined_hands_from_landmarks([left, self.hand(0.55, upward=False)], 640, 480))

    def test_rotated_joined_hands_still_recognized(self):
        hands = [self.hand(0.45), self.hand(0.55)]
        rotated = [[SimpleNamespace(x=point.y, y=1 - point.x) for point in hand]
                   for hand in hands]
        self.assertTrue(joined_hands_from_landmarks(rotated, 480, 640))

    def test_recognizer_uses_two_hands_in_the_current_frame(self):
        primary, alternate = Mock(), Mock()
        primary.detect_for_video.return_value = SimpleNamespace(
            hand_landmarks=[self.hand(0.45), self.hand(0.55)])
        recognizer = app.MultiViewHandLandmarker(primary, alternate)
        image = app.mp.Image(image_format=app.mp.ImageFormat.SRGB,
                             data=np.zeros((480, 640, 3), np.uint8))
        self.assertTrue(recognizer.recognize_joined_hands(image, 100))
        self.assertEqual(recognizer.last_hand_count, 2)
        alternate.detect.assert_not_called()

    def test_hand_model_recovers_joined_hands_in_a_cropped_view(self):
        primary, alternate = Mock(), Mock()
        primary.detect_for_video.return_value = SimpleNamespace(
            hand_landmarks=[self.hand(0.45)])
        alternate.detect.side_effect = [
            SimpleNamespace(hand_landmarks=[]),
            SimpleNamespace(hand_landmarks=[self.hand(0.45), self.hand(0.55)]),
        ]
        recognizer = app.MultiViewHandLandmarker(primary, alternate)
        image = app.mp.Image(image_format=app.mp.ImageFormat.SRGB,
                             data=np.zeros((480, 640, 3), np.uint8))
        self.assertTrue(recognizer.recognize_joined_hands(image, 100))
        self.assertEqual(recognizer.preferred_view, ("full", 3))
        self.assertEqual(recognizer.last_hand_count, 2)


class EffectTests(unittest.TestCase):
    def test_generated_asset_has_real_transparency(self):
        sprite = load_log()
        self.assertEqual(sprite.shape[2], 4)
        self.assertEqual(int(sprite[:, :, 3].min()), 0)
        self.assertGreaterEqual(int(sprite[:, :, 3].max()), 250)

    def test_smoke_animation_leaves_log_behind(self):
        frame = np.full((160, 240, 3), 130, np.uint8)
        background = np.full_like(frame, 35)
        mask = np.ones(frame.shape[:2], np.float32)
        sprite = load_log()
        anchor = (120, 85, 100)
        early = render_substitution(frame, background, mask, sprite, anchor, 0.04)
        middle = render_substitution(frame, background, mask, sprite, anchor, 0.55)
        final = render_substitution(frame, background, mask, sprite, anchor, EFFECT_SECONDS)
        self.assertTrue(np.any(early != frame))
        self.assertTrue(np.any(middle != frame))
        self.assertTrue(np.any(middle != background))
        self.assertTrue(np.any(final != background))
        np.testing.assert_array_equal(final[0, 0], background[0, 0])

    def test_log_anchor_tracks_person_region(self):
        mask = np.zeros((160, 240), np.float32)
        mask[20:130, 140:210] = 1.0
        x, y, size = substitution_anchor(mask)
        self.assertGreater(x, 140)
        self.assertGreater(size, 35)
        self.assertTrue(20 < y < 130)

    def test_log_falls_then_stays_on_floor(self):
        anchor = (120, 80, 90)
        ys = [falling_log_anchor(anchor, 240, age)[1] for age in (0.1, 0.3, 0.5, 0.7)]
        self.assertEqual(ys[0], anchor[1])
        self.assertGreater(ys[2], ys[1])
        self.assertGreater(ys[3], ys[2])
        floor = landed_log_anchor(anchor, 240)
        self.assertGreater(floor[1], ys[3])
        background = np.full((240, 240, 3), 35, np.uint8)
        output = render_substitution(background, background, np.zeros((240, 240), np.float32),
                                     load_log(), anchor, EFFECT_SECONDS)
        expected = background.copy()
        overlay_log(expected, load_log(), floor)
        np.testing.assert_array_equal(output, expected)


class MenuTests(unittest.TestCase):
    def test_keyboard_selection(self):
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(app.cv2, "namedWindow"))
            mocks.enter_context(patch.object(app.cv2, "setMouseCallback"))
            mocks.enter_context(patch.object(app.cv2, "imshow"))
            mocks.enter_context(patch.object(app.cv2, "destroyWindow"))
            mocks.enter_context(patch.object(app.cv2, "getWindowProperty", return_value=1))
            key = mocks.enter_context(patch.object(app.cv2, "waitKey", return_value=ord("2")))
            self.assertEqual(app.choose_mode(), "naruto")
            key.return_value = ord("1")
            self.assertEqual(app.choose_mode(), "normal")
            for number, mode in ((3, "particles"), (4, "goku"), (5, "piccolo"),
                                 (6, "burn"), (7, "whoosh"), (8, "electric")):
                key.return_value = ord(str(number))
                self.assertEqual(app.choose_mode(), mode)

    def test_headless_menu_uses_console_only(self):
        with patch("builtins.input", return_value="8"), patch("builtins.print"), \
                patch.object(app.cv2, "namedWindow", side_effect=AssertionError("No headless GUI")):
            self.assertEqual(app.choose_mode(headless=True), "electric")


class NarutoVideoLoopTests(unittest.TestCase):
    def test_effect_is_sent_to_preview_and_virtual_camera(self):
        from test_video_output import mock_video
        result = mock_video(mode="naruto")
        self.assertEqual(len(result.sent), len(result.shown))
        for rgb, preview in zip(result.sent, result.shown):
            np.testing.assert_array_equal(rgb, app.cv2.cvtColor(preview, app.cv2.COLOR_BGR2RGB))
        self.assertFalse(np.array_equal(result.shown[-1], result.raw[-1]))
        result.sound.play.assert_called_once()

    def test_r_restores_live_video_and_removes_log(self):
        from test_video_output import mock_video
        result = mock_video(mode="naruto", keys=[0, ord("v")] + [0] * 12 + [ord("r"), 0, ord("q")])
        np.testing.assert_array_equal(result.shown[-1], result.raw[-1])

    def test_cached_smoke_is_deterministic_and_reverse_seek_safe(self):
        frame = np.full((160, 240, 3), 130, np.uint8)
        background = np.full_like(frame, 35)
        mask = np.ones(frame.shape[:2], np.float32)
        cache, smoke = {}, {}
        sprite = load_log()
        reference = render_substitution(frame, background, mask, sprite, (120, 85, 100), .35, cache, smoke)
        render_substitution(frame, background, mask, sprite, (120, 85, 100), 1.0, cache, smoke)
        actual = render_substitution(frame, background, mask, sprite, (120, 85, 100), .35, cache, smoke)
        np.testing.assert_array_equal(reference, actual)


if __name__ == "__main__":
    unittest.main()
