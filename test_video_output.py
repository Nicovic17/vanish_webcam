import argparse
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from local_app import vanish_cam as app


def arguments(**overrides):
    values = dict(
        camera=0, width=960, height=540, fps=30.0, fullscreen=False,
        no_mirror=True, virtual_camera=None, virtual_backend=None, virtual_device=None,
        gesture_debug=False, mode="normal",
    )
    values.update(overrides)
    return argparse.Namespace(**values)


class VirtualCameraTests(unittest.TestCase):
    def test_bgr_format_and_actual_frame_dimensions(self):
        camera = Mock(device="OBS Virtual Camera")
        module = SimpleNamespace(Camera=Mock(return_value=camera), PixelFormat=SimpleNamespace(BGR="BGR"))
        with patch.dict("sys.modules", pyvirtualcam=module):
            self.assertIs(app.open_virtual_camera(arguments(), 640, 480), camera)
        module.Camera.assert_called_once_with(
            width=640, height=480, fps=30.0, fmt="BGR", backend=None, device=None,
        )

    def test_unavailable_driver_auto_falls_back_but_explicit_mode_fails(self):
        module = SimpleNamespace(Camera=Mock(side_effect=RuntimeError("driver missing")),
                                 PixelFormat=SimpleNamespace(BGR="BGR"))
        with patch.dict("sys.modules", pyvirtualcam=module), patch("builtins.print"):
            self.assertIsNone(app.open_virtual_camera(arguments(), 640, 480))
            for options in (dict(virtual_camera=True), dict(virtual_backend="obs")):
                with self.assertRaisesRegex(RuntimeError, "driver missing"):
                    app.open_virtual_camera(arguments(**options), 640, 480)

    def test_disabled_camera_does_not_open_device(self):
        module = SimpleNamespace(Camera=Mock())
        with patch.dict("sys.modules", pyvirtualcam=module):
            self.assertIsNone(app.open_virtual_camera(arguments(virtual_camera=False), 640, 480))
        module.Camera.assert_not_called()

    def test_send_preserves_colors_and_handles_noncontiguous_frames(self):
        camera = Mock(width=40, height=24)
        frame = np.zeros((24, 40, 3), np.uint8)
        frame[:] = (10, 70, 200)  # BGR: non scambiare rosso e blu.
        app.send_virtual_frame(camera, frame[:, ::-1])
        sent = camera.send.call_args.args[0]
        self.assertTrue(sent.flags.c_contiguous)
        np.testing.assert_array_equal(sent, frame)

    def test_send_resizes_if_input_resolution_changes(self):
        camera = Mock(width=40, height=24)
        app.send_virtual_frame(camera, np.full((48, 80, 3), 42, np.uint8))
        sent = camera.send.call_args.args[0]
        self.assertEqual(sent.shape, (24, 40, 3))
        self.assertTrue((sent == 42).all())


class VideoLoopTests(unittest.TestCase):
    def run_mock_video(self, send_error=None, gesture=("No_Hand", 0.0)):
        capture = Mock()
        frames = [np.full((24, 40, 3), color, np.uint8) for color in (10, 40, 80, 120, 160)]
        capture.read.side_effect = [(True, frame) for frame in frames]
        segmenter, recognizer = Mock(), Mock()
        camera = Mock(width=40, height=24)
        camera.send.side_effect = send_error
        displayed = []
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(app, "parse_args", return_value=arguments()))
            mocks.enter_context(patch.object(app, "download_models"))
            mocks.enter_context(patch.object(app, "open_camera", return_value=capture))
            mocks.enter_context(patch.object(app, "create_tasks", return_value=(segmenter, recognizer)))
            opening = mocks.enter_context(patch.object(app, "open_virtual_camera", return_value=camera))
            mocks.enter_context(patch.object(app, "person_mask", return_value=np.ones((24, 40), np.float32)))
            mocks.enter_context(patch.object(app, "recognize_gesture", return_value=gesture))
            times = (0, 0, 0.1, 4.1, 4.3, 4.35, 5.0, 5.02, 8.2, 8.23)
            mocks.enter_context(patch.object(app.time, "perf_counter", side_effect=times))
            mocks.enter_context(patch.object(app.cv2, "namedWindow"))
            mocks.enter_context(patch.object(app.cv2, "resizeWindow"))
            destroy = mocks.enter_context(patch.object(app.cv2, "destroyAllWindows"))
            mocks.enter_context(patch.object(app.cv2, "imshow", side_effect=lambda name, frame: displayed.append(frame.copy())))
            keys = (0, 0, ord("v") if gesture[0] != "Victory" else 0, 0, ord("q"))
            mocks.enter_context(patch.object(app.cv2, "waitKey", side_effect=keys))
            mocks.enter_context(patch.object(app.cv2, "putText", side_effect=AssertionError("Overlay vietato")))
            mocks.enter_context(patch("builtins.print"))
            if send_error is None:
                self.assertEqual(app.run(), 0)
            else:
                with self.assertRaisesRegex(RuntimeError, "send failed"):
                    app.run()
            opening.assert_called_once()
            self.assertEqual(opening.call_args.args[1:], (40, 24))
            capture.release.assert_called_once()
            segmenter.close.assert_called_once()
            recognizer.close.assert_called_once()
            camera.close.assert_called_once()
            destroy.assert_called_once()
        return frames, camera, displayed

    def test_preview_and_virtual_output_are_clean_in_all_phases(self):
        frames, camera, displayed = self.run_mock_video()
        self.assertEqual(len(displayed), 5)
        for sent, preview in zip(camera.send.call_args_list, displayed):
            np.testing.assert_array_equal(sent.args[0], preview)
        np.testing.assert_array_equal(displayed[0], frames[0])  # Calibrazione.
        np.testing.assert_array_equal(displayed[2], frames[2])  # Pronto.
        np.testing.assert_array_equal(displayed[4], frames[1])  # Sparito: solo sfondo.

    def test_first_gesture_starts_dissolve_in_preview_and_virtual_output(self):
        frames, camera, displayed = self.run_mock_video(gesture=("Victory", 0.9))
        np.testing.assert_array_equal(camera.send.call_args_list[2].args[0], displayed[2])
        self.assertTrue(np.any(displayed[3] != frames[3]))  # Animazione in corso.
        self.assertTrue(np.any(displayed[3] != frames[1]))  # Non ancora sparito.
        np.testing.assert_array_equal(displayed[4], frames[1])  # Animazione completata.

    def test_all_devices_close_on_send_error(self):
        self.run_mock_video(send_error=RuntimeError("send failed"))


if __name__ == "__main__":
    unittest.main()
