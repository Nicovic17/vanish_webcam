import unittest
from types import SimpleNamespace

import numpy as np
import mediapipe as mp

from local_app.goku_effect import (
    GokuGestureGate, GokuPoseRecognizer, GokuTeleport, HOLD_SECONDS, TELEPORT_SECONDS,
    fingers_on_forehead,
)


def gesture_hand(index_tip=(130, 55), middle_tip=(139, 55), open_ring=False):
    points = np.zeros((21, 2), np.float32)
    points[0] = (150, 190)
    points[5:9] = ((132, 143), (131, 110), (130, 80), index_tip)
    points[9:13] = ((145, 143), (142, 110), (140, 80), middle_tip)
    points[13:17] = ((160, 145), (160, 130), (164, 132), (162, 145))
    points[17:21] = ((175, 145), (175, 133), (178, 137), (177, 148))
    if open_ring:
        points[13:17] = ((160, 145), (160, 115), (160, 85), (160, 55))
    return [SimpleNamespace(x=x / 320, y=y / 240) for x, y in points]


class GokuPoseTests(unittest.TestCase):
    def test_joined_extended_fingers_on_forehead(self):
        self.assertTrue(fingers_on_forehead([gesture_hand()], [(100, 40, 100, 120)], 320, 240))

    def test_requires_face_contact_and_two_joined_fingers(self):
        for hands, faces in (
            ([gesture_hand()], []),
            ([gesture_hand(index_tip=(130, 120), middle_tip=(139, 120))], [(100, 40, 100, 120)]),
            ([gesture_hand(middle_tip=(205, 55))], [(100, 40, 100, 120)]),
            ([gesture_hand(open_ring=True)], [(100, 40, 100, 120)]),
        ):
            with self.subTest(hands=hands, faces=faces):
                self.assertFalse(fingers_on_forehead(hands, faces, 320, 240))

    def test_detector_combines_face_and_hand_and_closes_both(self):
        face = SimpleNamespace(bounding_box=SimpleNamespace(
            origin_x=100, origin_y=40, width=100, height=120,
        ))
        class FakeDetector:
            def __init__(self, results):
                self.results = iter(results)
                self.closed = False

            def detect_for_video(self, image, timestamp):
                return next(self.results)

            def close(self):
                self.closed = True

        faces = FakeDetector([
            SimpleNamespace(detections=[face]),
            SimpleNamespace(detections=[]),
        ])
        hands = FakeDetector([
            SimpleNamespace(hand_landmarks=[gesture_hand()]),
            SimpleNamespace(hand_landmarks=[gesture_hand()]),
        ])
        detector = GokuPoseRecognizer(hands, faces)
        image = SimpleNamespace(width=320, height=240)
        self.assertTrue(detector.recognize_pose(image, 1000))
        self.assertTrue(detector.recognize_pose(image, 1150))  # Brief face occlusion.
        detector.close()
        self.assertTrue(hands.closed and faces.closed)

    def test_cropped_hand_retry_recovers_small_fingers(self):
        face = SimpleNamespace(bounding_box=SimpleNamespace(
            origin_x=100, origin_y=40, width=100, height=120,
        ))
        face_detector = SimpleNamespace(
            detect_for_video=lambda image, timestamp: SimpleNamespace(detections=[face]),
            close=lambda: None,
        )
        hand_detector = SimpleNamespace(
            detect_for_video=lambda image, timestamp: SimpleNamespace(hand_landmarks=[]),
            close=lambda: None,
        )
        original = gesture_hand()
        recovered = [SimpleNamespace(
            x=(point.x * 320 - 45) / 210,
            y=(point.y * 240) / 232,
        ) for point in original]
        fallback = SimpleNamespace(
            detect=lambda image: SimpleNamespace(hand_landmarks=[recovered]),
            close=lambda: None,
        )
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.zeros((240, 320, 3), np.uint8),
        )
        detector = GokuPoseRecognizer(hand_detector, face_detector, fallback)
        self.assertTrue(detector.recognize_pose(image, 1000))
        detector.close()


class GokuTimingTests(unittest.TestCase):
    def test_one_second_and_release_required_for_reappearance(self):
        gate = GokuGestureGate()
        for index in range(10):
            self.assertFalse(gate.update(True, 10.0 + index * 0.1))
        self.assertTrue(gate.update(True, 10.0 + HOLD_SECONDS))
        self.assertFalse(gate.update(True, 20.0))  # Holding cannot retrigger.
        self.assertFalse(gate.update(False, 20.1))
        self.assertFalse(gate.update(False, 20.5))
        for index in range(10):
            self.assertFalse(gate.update(True, 21.0 + index * 0.1))
        self.assertTrue(gate.update(True, 21.0 + HOLD_SECONDS))

    def test_breaking_pose_resets_countdown(self):
        gate = GokuGestureGate()
        gate.update(True, 1.0)
        gate.update(False, 2.0)
        gate.update(False, 2.3)
        for index in range(10):
            self.assertFalse(gate.update(True, 3.0 + index * 0.1))
        self.assertTrue(gate.update(True, 4.0))

    def test_single_tracking_miss_does_not_erase_a_real_hold(self):
        gate = GokuGestureGate()
        gate.update(True, 1.0)
        gate.update(True, 1.1)
        gate.update(False, 1.2)
        self.assertFalse(gate.update(True, 1.3))
        for index in range(14, 20):
            gate.update(True, index * 0.1)
        self.assertTrue(gate.update(True, 2.0))


class TeleportTests(unittest.TestCase):
    def test_hard_cut_disappearance_and_reverse_arrival(self):
        background = np.full((100, 140, 3), 30, np.uint8)
        frame = background.copy()
        frame[20:80, 40:100] = (65, 115, 205)
        mask = np.zeros((100, 140), np.float32)
        mask[20:80, 40:100] = 1.0
        effect = GokuTeleport(frame, background, mask)
        center = np.s_[35:65, 55:85]
        np.testing.assert_allclose(
            np.median(effect.render(background, 0.0, False)[center], axis=(0, 1)),
            frame[50, 70], atol=10,
        )
        np.testing.assert_allclose(
            np.median(effect.render(background, 0.08, False)[center], axis=(0, 1)),
            background[50, 70], atol=10,
        )
        np.testing.assert_array_equal(effect.render(background, TELEPORT_SECONDS, False), background)
        np.testing.assert_allclose(
            np.median(effect.render(background, 0.0, True)[center], axis=(0, 1)),
            background[50, 70], atol=10,
        )
        np.testing.assert_allclose(
            np.median(effect.render(background, 0.08, True)[center], axis=(0, 1)),
            frame[50, 70], atol=10,
        )
        np.testing.assert_array_equal(effect.render(background, TELEPORT_SECONDS, True)[50, 70], frame[50, 70])

    def test_vertical_streaks_anticipate_and_outlast_cut_in_both_directions(self):
        background = np.full((160, 180, 3), 90, np.uint8)
        frame = background.copy()
        frame[25:140, 45:135] = (80, 125, 170)
        mask = np.zeros((160, 180), np.float32)
        mask[25:140, 45:135] = 1.0
        effect = GokuTeleport(frame, background, mask)
        for appearing in (False, True):
            for age, base in ((0.0, effect.ghost if appearing else effect.visible),
                              (0.10, effect.visible if appearing else effect.ghost),
                              (0.20, effect.visible if appearing else effect.ghost)):
                with self.subTest(appearing=appearing, age=age):
                    changed = np.any(effect.render(background, age, appearing) != base, axis=2)
                    self.assertGreaterEqual(np.count_nonzero(changed.sum(axis=0) >= 12), 5)
            np.testing.assert_array_equal(
                effect.render(background, TELEPORT_SECONDS, appearing),
                effect.visible if appearing else background,
            )
        self.assertFalse(np.array_equal(
            effect.render(background, 0.10, False),
            effect.render(background, 0.17, False),
        ))


if __name__ == "__main__":
    unittest.main()
