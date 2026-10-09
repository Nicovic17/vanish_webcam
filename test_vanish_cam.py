import unittest
from types import SimpleNamespace

import numpy as np
import mediapipe as mp

from local_app.vanish_cam import (
    AppState, MultiViewGestureRecognizer, recognize_gesture, start_vanish_on_gesture,
    victory_landmark_score,
)


def hand_points(extended=(True, True, False, False)):
    points = np.zeros((21, 3))
    for base, x, opened, spread in zip(
        (5, 9, 13, 17), (-0.45, 0.0, 0.4, 0.75), extended, (-0.35, 0.25, 0.0, 0.0)
    ):
        if opened:
            points[base : base + 4] = [
                (x, 1.0, 0.0), (x + spread * 0.45, 1.7, 0.0),
                (x + spread * 0.75, 2.15, 0.0), (x + spread, 2.5, 0.0),
            ]
        else:
            points[base : base + 4] = [
                (x, 1.0, 0.0), (x, 1.5, 0.2),
                (x, 1.3, 0.5), (x, 0.95, 0.3),
            ]
    return points


def landmarks(points):
    return [SimpleNamespace(x=x, y=y, z=z) for x, y, z in points]


class VictoryGestureTests(unittest.TestCase):
    def test_victory_with_back_palm_rotation_mirror_and_scale(self):
        points = hand_points()
        for angle in (0.0, 0.7, 1.57, 2.6, np.pi):
            c, s = np.cos(angle), np.sin(angle)
            rotation = np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
            tilt = np.array(((1, 0, 0), (0, c, -s), (0, s, c)))
            for mirror in (1, -1):
                for scale in (0.02, 1.0, 100.0):
                    with self.subTest(angle=angle, mirror=mirror, scale=scale):
                        transformed = points @ rotation @ tilt
                        transformed[:, 0] *= mirror
                        transformed = transformed * scale + (0.5, 0.3, 0.1)
                        self.assertGreater(victory_landmark_score(transformed), 0.62)

    def test_other_gestures_do_not_trigger(self):
        for fingers in (
            (False, False, False, False),  # Pugno.
            (True, True, True, True),  # Palmo aperto.
            (True, False, False, False),  # Solo indice.
            (True, False, False, True),  # Corna.
            (True, True, True, False),  # Tre dita.
        ):
            with self.subTest(fingers=fingers):
                self.assertEqual(victory_landmark_score(hand_points(fingers)), 0.0)

    def test_invalid_or_degenerate_landmarks(self):
        for points in (np.zeros((21, 3)), np.zeros((20, 3)), np.full((21, 3), np.nan)):
            self.assertEqual(victory_landmark_score(points), 0.0)

    def test_landmarks_trigger_without_classifier_category(self):
        result = SimpleNamespace(
            hand_world_landmarks=[landmarks(hand_points())], hand_landmarks=[], gestures=[]
        )
        recognizer = SimpleNamespace(recognize_for_video=lambda image, timestamp: result)
        name, score = recognize_gesture(recognizer, None, 1000)
        self.assertEqual(name, "Victory")
        self.assertGreater(score, 0.62)

    def test_normalized_landmark_fallback_handles_video_aspect_ratio(self):
        image = SimpleNamespace(width=960, height=540)
        points = hand_points() * 40 + (480, 200, 0)
        normalized = points / (image.width, image.height, image.width)
        result = SimpleNamespace(
            hand_world_landmarks=[], hand_landmarks=[landmarks(normalized)], gestures=[]
        )
        recognizer = SimpleNamespace(recognize_for_video=lambda image, timestamp: result)
        self.assertEqual(recognize_gesture(recognizer, image, 1000)[0], "Victory")

    def test_existing_classifier_still_works(self):
        result = SimpleNamespace(
            hand_world_landmarks=[], hand_landmarks=[],
            gestures=[[SimpleNamespace(category_name="Victory", score=0.9)]],
        )
        recognizer = SimpleNamespace(recognize_for_video=lambda image, timestamp: result)
        self.assertEqual(recognize_gesture(recognizer, None, 1000), ("Victory", 0.9))

    def test_occluded_folded_fingers_can_appear_short_and_straight(self):
        points = hand_points()
        for base in (13, 17):
            points[base : base + 4] = [
                (0.4, 1.0, 0.0), (0.4, 1.1, 0.0),
                (0.4, 1.2, 0.0), (0.4, 1.3, 0.0),
            ]
        self.assertGreater(victory_landmark_score(points), 0.62)

    def test_hidden_fingers_with_coincident_landmarks(self):
        points = hand_points()
        points[13:16] = points[13]
        points[16] = points[13]
        points[17:20] = points[17]
        points[20] = points[17]
        self.assertGreater(victory_landmark_score(points), 0.62)

    def test_visible_geometry_is_used_even_with_inaccurate_world_landmarks(self):
        image = SimpleNamespace(width=960, height=540)
        points = hand_points() * 40 + (480, 200, 0)
        world = hand_points()
        world[8] = world[6]
        self.assertEqual(victory_landmark_score(world), 0.0)
        result = SimpleNamespace(
            hand_world_landmarks=[landmarks(world)],
            hand_landmarks=[landmarks(points / (960, 540, 960))], gestures=[],
        )
        recognizer = SimpleNamespace(recognize_for_video=lambda image, timestamp: result)
        self.assertEqual(recognize_gesture(recognizer, image, 1000)[0], "Victory")

    def test_diagnostics_distinguish_missing_hand_and_rejected_gesture(self):
        for hands, expected in (([], "No_Hand"), ([landmarks(hand_points((False,) * 4))], "Hand_Detected")):
            result = SimpleNamespace(hand_world_landmarks=hands, hand_landmarks=[], gestures=[])
            recognizer = SimpleNamespace(recognize_for_video=lambda image, timestamp: result)
            self.assertEqual(recognize_gesture(recognizer, None, 1000)[0], expected)


class ImmediateAnimationTests(unittest.TestCase):
    def test_first_recognized_v_starts_animation_immediately(self):
        state = AppState(phase="ready")
        self.assertTrue(start_vanish_on_gesture(state, "Victory", 0.9, 12.5))
        self.assertEqual(state.phase, "vanishing")
        self.assertEqual(state.vanish_started, 12.5)

    def test_other_or_weak_gestures_do_not_vanish(self):
        for name, score in (("No_Hand", 0.0), ("Hand_Detected", 0.0), ("Victory", 0.61)):
            with self.subTest(name=name, score=score):
                state = AppState(phase="ready")
                self.assertFalse(start_vanish_on_gesture(state, name, score, 12.5))
                self.assertEqual(state.phase, "ready")
                self.assertIsNone(state.vanish_started)

    def test_only_ready_phase_responds(self):
        for phase in ("calibrating", "vanishing", "vanished"):
            state = AppState(phase=phase)
            self.assertFalse(start_vanish_on_gesture(state, "Victory", 0.9, 12.5))
            self.assertEqual(state.phase, phase)


class MultiViewTests(unittest.TestCase):
    def setUp(self):
        self.empty = SimpleNamespace(hand_world_landmarks=[], hand_landmarks=[], gestures=[])
        self.victory = SimpleNamespace(
            hand_world_landmarks=[], hand_landmarks=[],
            gestures=[[SimpleNamespace(category_name="Victory", score=0.9)]],
        )
        self.image = mp.Image(
            image_format=mp.ImageFormat.SRGB, data=np.zeros((32, 48, 3), dtype=np.uint8)
        )

    def test_rotated_detection_and_preferred_view_are_used(self):
        calls = []

        def recognize(image):
            calls.append((image.width, image.height))
            return self.victory if image.width == 32 else self.empty

        detector = MultiViewGestureRecognizer(
            SimpleNamespace(recognize_for_video=lambda image, timestamp: self.empty),
            SimpleNamespace(recognize=recognize),
        )
        self.assertEqual(recognize_gesture(detector, self.image, 1000)[0], "Victory")
        self.assertEqual(calls, [(48, 32), (32, 48)])
        self.assertEqual(detector.preferred_rotation, 1)
        calls.clear()
        self.assertEqual(recognize_gesture(detector, self.image, 1140)[0], "Victory")
        self.assertEqual(calls, [(32, 48)])

    def test_failed_search_is_throttled_without_reusing_old_positive(self):
        calls = []
        alternate = SimpleNamespace(recognize=lambda image: calls.append(image) or self.empty)
        detector = MultiViewGestureRecognizer(
            SimpleNamespace(recognize_for_video=lambda image, timestamp: self.empty), alternate
        )
        self.assertEqual(recognize_gesture(detector, self.image, 1000)[0], "No_Hand")
        self.assertEqual(len(calls), 10)
        recognize_gesture(detector, self.image, 1140)
        self.assertEqual(len(calls), 10)
        alternate.recognize = lambda image: self.victory
        self.assertEqual(recognize_gesture(detector, self.image, 1420)[0], "Victory")
        alternate.recognize = lambda image: self.empty
        self.assertEqual(recognize_gesture(detector, self.image, 1560)[0], "No_Hand")

    def test_primary_victory_avoids_extra_inference(self):
        calls = []
        detector = MultiViewGestureRecognizer(
            SimpleNamespace(recognize_for_video=lambda image, timestamp: self.victory),
            SimpleNamespace(recognize=lambda image: calls.append(image) or self.empty),
        )
        self.assertEqual(recognize_gesture(detector, self.image, 1000)[0], "Victory")
        self.assertEqual(calls, [])

    def test_lower_hand_crop_recovers_a_small_sideways_v(self):
        calls = []

        def recognize(image):
            calls.append((image.width, image.height))
            return self.victory if (image.width, image.height) == (37, 24) else self.empty

        detector = MultiViewGestureRecognizer(
            SimpleNamespace(recognize_for_video=lambda image, timestamp: self.empty),
            SimpleNamespace(recognize=recognize),
        )
        self.assertEqual(recognize_gesture(detector, self.image, 1000)[0], "Victory")
        self.assertEqual(detector.preferred_crop, "lower_left")
        self.assertEqual(detector.preferred_rotation, 0)
        calls.clear()
        self.assertEqual(recognize_gesture(detector, self.image, 1140)[0], "Victory")
        self.assertEqual(calls, [(37, 24)])


if __name__ == "__main__":
    unittest.main()
