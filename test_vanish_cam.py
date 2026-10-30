import unittest
from types import SimpleNamespace

import numpy as np
import mediapipe as mp

from vanish_cam import (
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
        self.assertEqual(len(calls), 3)
        recognize_gesture(detector, self.image, 1140)
        self.assertEqual(len(calls), 6)
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
        self.assertEqual(recognize_gesture(detector, self.image, 1000)[0], "No_Hand")
        self.assertEqual(recognize_gesture(detector, self.image, 1140)[0], "Victory")
        self.assertEqual(detector.preferred_crop, "lower_left")
        self.assertEqual(detector.preferred_rotation, 0)
        calls.clear()
        self.assertEqual(recognize_gesture(detector, self.image, 1280)[0], "Victory")
        self.assertEqual(calls, [(37, 24)])


class GestureSmoothingTests(unittest.TestCase):
    def test_requires_consecutive_frames_and_clear_release(self):
        from gesture_detection import GestureGate
        gate = GestureGate(on_frames=3, off_frames=4)
        self.assertFalse(gate.update(.95, 0))
        self.assertFalse(gate.update(.95, .1))
        self.assertTrue(gate.update(.95, .2))
        for i, score in enumerate((.95, 0, .95, 0, 0, .95), 3):
            self.assertFalse(gate.update(score, i / 10))
        self.assertTrue(gate.latched)
        for i in range(9, 13):
            self.assertFalse(gate.update(0, i / 10))
        self.assertFalse(gate.latched)
        events = [gate.update(.95, i / 10) for i in range(13, 18)]
        self.assertEqual(sum(events), 1)

    def test_flickering_candidates_never_trigger(self):
        from gesture_detection import GestureGate
        gate = GestureGate()
        self.assertFalse(any(gate.update(score, i / 30) for i, score in enumerate([.95, 0] * 20)))

    def test_repeated_frame_is_not_counted(self):
        from gesture_detection import GestureGate
        gate = GestureGate()
        self.assertFalse(any(gate.update(.95, 1) for _ in range(20)))
        self.assertEqual(gate.consecutive, 1)

    def test_stale_gap_breaks_candidate_hold(self):
        from gesture_detection import GestureGate
        gate = GestureGate()
        gate.update(.95, 0)
        gate.update(.95, .1)
        self.assertFalse(gate.update(.95, 1))

    def test_goku_requires_one_unbroken_second_and_release(self):
        from gesture_detection import GestureGate
        gate = GestureGate(hold_seconds=1)
        self.assertFalse(any(gate.update(.95, i / 10) for i in range(9)))
        gate.update(0, .9)
        self.assertFalse(any(gate.update(.95, i / 10) for i in range(10, 20)))
        events = [gate.update(.95, i / 10) for i in range(20, 30)]
        self.assertEqual(sum(events), 1)
        self.assertTrue(gate.latched)

    def test_nonfinite_confidence_is_rejected(self):
        from gesture_detection import GestureGate
        gate = GestureGate()
        self.assertFalse(any(gate.update(float("nan"), i / 30) for i in range(5)))


class MappingAndForeheadTests(unittest.TestCase):
    def test_landmarks_map_to_full_resolution(self):
        from gesture_detection import pixel_landmarks
        result = pixel_landmarks([SimpleNamespace(x=.25, y=.75, z=.1)], 1280, 720)
        np.testing.assert_allclose(result[0], (320, 540, 128))

    def test_forehead_requires_adjacent_fingers_and_face(self):
        from gesture_detection import forehead_score
        world = hand_points()
        for base, x in ((5, -.1), (9, .1)):
            world[base:base + 4, 0] = x
        face = np.zeros((478, 3), np.float32)
        face[10], face[168] = (640, 110, 0), (640, 180, 0)
        face[234], face[454] = (540, 200, 0), (740, 200, 0)
        pixels = world * 30 + (640, 70, 0)
        pixels[8], pixels[12] = (635, 138, 0), (645, 138, 0)
        self.assertGreater(forehead_score(pixels, face, world), .62)
        self.assertEqual(forehead_score(pixels, None, world), 0)
        moved = pixels.copy()
        moved[:, :2] += 300
        self.assertEqual(forehead_score(moved, face, world), 0)
        world[8, 0] -= 2
        self.assertEqual(forehead_score(pixels, face, world), 0)


class ProceduralEffectTests(unittest.TestCase):
    def setUp(self):
        import cv2
        self.frame = np.full((180, 320, 3), (90, 130, 180), np.uint8)
        self.background = np.full_like(self.frame, (35, 45, 60))
        self.mask = np.zeros((180, 320), np.float32)
        cv2.ellipse(self.mask, (180, 100), (40, 70), 0, 0, 360, 1, -1)

    def test_every_mode_has_exact_endpoints_and_reversible_deterministic_frames(self):
        from vanish_effects import MODES, SilhouetteEffect
        for mode, _, _ in MODES:
            if mode == "naruto":
                continue
            with self.subTest(mode=mode):
                effect = SilhouetteEffect(self.frame, self.mask, mode)
                np.testing.assert_array_equal(effect.render(self.background, 0), self.frame)
                middle = effect.render(self.background, .35).copy()
                self.assertFalse(np.array_equal(middle, self.frame))
                self.assertFalse(np.array_equal(middle, self.background))
                np.testing.assert_array_equal(effect.render(self.background, 1), self.background)
                np.testing.assert_array_equal(effect.render(self.background, .35), middle)
                np.testing.assert_array_equal(effect.render(self.background, 0), self.frame)

    def test_input_frames_and_masks_are_not_modified(self):
        from vanish_effects import SilhouetteEffect
        before, mask_before, background_before = self.frame.copy(), self.mask.copy(), self.background.copy()
        effect = SilhouetteEffect(self.frame, self.mask, "burn")
        for p in (.1, .5, .9):
            output = effect.render(self.background, p)
            self.assertEqual(output.dtype, np.uint8)
            self.assertEqual(output.shape, self.frame.shape)
        np.testing.assert_array_equal(before, self.frame)
        np.testing.assert_array_equal(mask_before, self.mask)
        np.testing.assert_array_equal(background_before, self.background)

    def test_silhouette_position_changes_effect_origin(self):
        from vanish_effects import SilhouetteEffect
        shifted = np.roll(self.mask, -90, axis=1)
        first = SilhouetteEffect(self.frame, self.mask, "whoosh")
        second = SilhouetteEffect(self.frame, shifted, "whoosh")
        self.assertAlmostEqual(first.cx - second.cx, 90, delta=2)
        self.assertAlmostEqual(first.head_y, second.head_y, delta=1)

    def test_final_frame_is_clean_at_multiple_resolutions(self):
        import cv2
        from vanish_effects import MODES, SilhouetteEffect
        for width, height in ((160, 120), (640, 360), (1280, 720)):
            frame = cv2.resize(self.frame, (width, height))
            mask = cv2.resize(self.mask, (width, height))
            background = cv2.resize(self.background, (width, height))
            for mode, _, _ in MODES:
                if mode != "naruto":
                    effect = SilhouetteEffect(frame, mask, mode)
                    np.testing.assert_array_equal(effect.render(background, 1), background)

    def test_generated_sounds_are_bounded_stereo_pcm(self):
        from vanish_sound import synthesized_samples
        for mode in ("burn", "whoosh", "goku", "piccolo", "electric"):
            samples = synthesized_samples(mode)
            self.assertEqual(samples.dtype, np.int16)
            self.assertEqual(samples.shape[1], 2)
            self.assertGreater(np.max(np.abs(samples)), 0)
            self.assertLess(np.max(np.abs(samples)), 32767)
            np.testing.assert_array_equal(samples, synthesized_samples(mode))


if __name__ == "__main__":
    unittest.main()
