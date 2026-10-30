import argparse
import unittest
from contextlib import ExitStack
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

import vanish_cam as app
from vanish_runtime import FramePacket
from vanish_vision import VisionResult, PreparedTransition


def arguments(**overrides):
    values = dict(camera=0, width=1280, height=720, fps=30.0, fullscreen=False,
                  no_mirror=True, virtual_camera=None, virtual_backend=None, virtual_device=None,
                  gesture_debug=False, mode="normal", profile=False, headless=False,
                  detection_width=640, detection_light=False, gesture_frames=3,
                  gesture_release_frames=5, duration=0)
    values.update(overrides)
    return argparse.Namespace(**values)


class VirtualCameraTests(unittest.TestCase):
    def test_rgb_format_and_actual_frame_dimensions(self):
        camera = Mock(device="OBS Virtual Camera")
        module = SimpleNamespace(Camera=Mock(return_value=camera), PixelFormat=SimpleNamespace(RGB="RGB"))
        with patch.dict("sys.modules", pyvirtualcam=module), patch.object(app.platform, "system", return_value="Windows"):
            self.assertIs(app.open_virtual_camera(arguments(), 640, 480), camera)
        module.Camera.assert_called_once_with(width=640, height=480, fps=30.0, fmt="RGB", backend="obs", device=None)

    def test_obs_then_unity_and_preview_fallback(self):
        camera = Mock(device="Unity Capture")
        module = SimpleNamespace(Camera=Mock(side_effect=[RuntimeError("OBS missing"), camera]),
                                 PixelFormat=SimpleNamespace(RGB="RGB"))
        with patch.dict("sys.modules", pyvirtualcam=module), patch.object(app.platform, "system", return_value="Windows"):
            self.assertIs(app.open_virtual_camera(arguments(), 640, 480), camera)
        self.assertEqual([c.kwargs["backend"] for c in module.Camera.call_args_list], ["obs", "unitycapture"])

    def test_missing_driver_preview_fallback_and_required_camera_errors(self):
        module = SimpleNamespace(Camera=Mock(side_effect=RuntimeError("driver missing")),
                                 PixelFormat=SimpleNamespace(RGB="RGB"))
        with patch.dict("sys.modules", pyvirtualcam=module), patch("builtins.print"):
            self.assertIsNone(app.open_virtual_camera(arguments(), 640, 480))
            for options in (dict(virtual_camera=True), dict(virtual_backend="obs"), dict(headless=True)):
                with self.assertRaisesRegex(RuntimeError, "driver missing"):
                    app.open_virtual_camera(arguments(**options), 640, 480)

    def test_disabled_camera_does_not_open_device(self):
        module = SimpleNamespace(Camera=Mock())
        with patch.dict("sys.modules", pyvirtualcam=module):
            self.assertIsNone(app.open_virtual_camera(arguments(virtual_camera=False), 640, 480))
        module.Camera.assert_not_called()

    def test_rgb_colors_and_noncontiguous_frames(self):
        camera = Mock(width=40, height=24)
        frame = np.zeros((24, 40, 3), np.uint8)
        frame[:] = (10, 70, 200)
        app.send_virtual_frame(camera, frame[:, ::-1])
        sent = camera.send.call_args.args[0]
        self.assertTrue(sent.flags.c_contiguous)
        np.testing.assert_array_equal(sent[0, 0], [200, 70, 10])

    def test_send_resizes_if_input_resolution_changes(self):
        camera = Mock(width=40, height=24)
        app.send_virtual_frame(camera, np.full((48, 80, 3), 42, np.uint8))
        sent = camera.send.call_args.args[0]
        self.assertEqual(sent.shape, (24, 40, 3))
        self.assertTrue((sent == 42).all())


def mock_video(mode="whoosh", headless=False, mirrored=False, send_error=None,
               keys=None, events=None, worker_error=None, event_delay=0, hud=False, sound_error=None):
    """Exercise the real state/render/output loop with deterministic device boundaries."""
    clock = SimpleNamespace(now=100.0)
    capture = Mock()
    reader = Mock()
    reader.close.side_effect = capture.release
    state = SimpleNamespace(sequence=0, packet=None, prepared=None, event=0)
    raw, shown, sent = [], [], []
    def read(timeout=0):
        state.sequence += 1
        frame = np.full((80, 120, 3), min(200, 20 + state.sequence * 5), np.uint8)
        frame[:, :12] = (10, 40, 210)
        frame[:, -12:] = (220, 70, 20)
        state.packet = FramePacket(state.sequence, clock.now, frame)
        raw.append(frame.copy())
        return state.packet
    reader.read.side_effect = read
    worker = Mock()
    mask = np.zeros((80, 120), np.float32)
    mask[8:75, 25:95] = 1
    def poll():
        if worker_error:
            raise worker_error
        event = max((value for index, value in (events or {}).items() if state.sequence >= index), default=0)
        packet = state.packet
        submitted = worker.submit.call_args.args[0]
        if submitted.prepare_effect or event > state.event:
            effect = app.SilhouetteEffect(packet.frame, mask, mode) if mode != "naruto" else None
            anchor = app.substitution_anchor(mask) if mode == "naruto" else None
            state.prepared = PreparedTransition(packet.captured_at-event_delay, packet.frame, mask, effect, anchor)
        state.event = event
        return VisionResult(packet.sequence, packet.captured_at-event_delay, packet.frame, mask,
                            event, packet.captured_at-event_delay, .95 if event else 0, "test", prepared=state.prepared)
    worker.poll.side_effect = poll
    camera = Mock(width=120, height=80)
    def send(frame):
        if send_error:
            raise send_error
        sent.append(frame.copy())
    camera.send.side_effect = send
    sound = Mock()
    sound.play.side_effect = sound_error
    keys = iter(keys or [0, ord("v")] + [0] * 20 + [ord("q")])
    def key(*unused):
        clock.now += .15
        return next(keys, ord("q"))
    with ExitStack() as mocks:
        builder = Mock()
        def submit_background(function, samples):
            future = Future()
            future.set_result(function(samples))
            return future
        builder.submit.side_effect = submit_background
        mocks.enter_context(patch.object(app, "ThreadPoolExecutor", return_value=builder))
        mocks.enter_context(patch.object(app, "parse_args", return_value=arguments(mode=mode, headless=headless, no_mirror=not mirrored)))
        mocks.enter_context(patch.object(app, "CALIBRATION_SECONDS", .15))
        mocks.enter_context(patch.object(app, "BACKGROUND_SAMPLE_SECONDS", .15))
        mocks.enter_context(patch.object(app, "download_models"))
        mocks.enter_context(patch.object(app, "open_camera", return_value=capture))
        mocks.enter_context(patch.object(app, "LatestFrameCapture", return_value=reader))
        mocks.enter_context(patch.object(app, "InferenceWorker", return_value=worker))
        mocks.enter_context(patch.object(app, "make_sound", return_value=sound))
        mocks.enter_context(patch.object(app, "open_virtual_camera", return_value=camera))
        mocks.enter_context(patch.object(app.time, "perf_counter", side_effect=lambda: clock.now))
        mocks.enter_context(patch.object(app.time, "sleep", side_effect=lambda duration: setattr(clock, "now", clock.now + duration)))
        named = mocks.enter_context(patch.object(app.cv2, "namedWindow"))
        mocks.enter_context(patch.object(app.cv2, "resizeWindow"))
        mocks.enter_context(patch.object(app.cv2, "destroyAllWindows"))
        mocks.enter_context(patch.object(app.cv2, "getWindowProperty", return_value=1))
        mocks.enter_context(patch.object(app.cv2, "imshow", side_effect=lambda name, frame: shown.append(frame.copy())))
        mocks.enter_context(patch.object(app.cv2, "waitKey", side_effect=key))
        mocks.enter_context(patch.object(app.cv2, "pollKey", side_effect=key))
        mocks.enter_context(patch.object(app, "terminal_key", side_effect=key))
        if not hud:
            mocks.enter_context(patch.object(app, "draw_guidance", side_effect=lambda frame, message: frame))
        mocks.enter_context(patch("builtins.print"))
        error = send_error or worker_error
        if error:
            try:
                app.run()
            except type(error):
                pass
            else:
                raise AssertionError("Expected device error")
        else:
            assert app.run() == 0
        if headless:
            named.assert_not_called()
        reader.close.assert_called_once()
        capture.release.assert_called_once()
        worker.close.assert_called_once()
        camera.close.assert_called_once()
        sound.close.assert_called_once()
        builder.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    return SimpleNamespace(raw=raw, shown=shown, sent=sent, sound=sound)


class VideoLoopTests(unittest.TestCase):
    def test_preview_and_virtual_output_have_no_text_and_correct_color(self):
        result = mock_video()
        self.assertEqual(len(result.shown), len(result.sent))
        for rgb, bgr in zip(result.sent, result.shown):
            np.testing.assert_array_equal(rgb, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        np.testing.assert_array_equal(result.shown[-1], result.shown[-2])
        self.assertFalse(np.array_equal(result.shown[-1], result.raw[-1]))

    def test_mirrored_preview_never_mirrors_virtual_output(self):
        result = mock_video(mirrored=True)
        for rgb, preview in zip(result.sent, result.shown):
            np.testing.assert_array_equal(rgb, cv2.cvtColor(preview[:, ::-1], cv2.COLOR_BGR2RGB))
        np.testing.assert_array_equal(result.sent[0][0, 0], [210, 40, 10])

    def test_all_devices_close_on_send_error(self):
        mock_video(send_error=RuntimeError("send failed"))

    def test_all_devices_close_on_worker_failure(self):
        mock_video(worker_error=RuntimeError("inference failed"))

    def test_all_devices_close_on_ctrl_c(self):
        mock_video(send_error=KeyboardInterrupt())

    def test_headless_has_no_windows(self):
        result = mock_video(headless=True)
        self.assertEqual(result.shown, [])
        self.assertGreater(len(result.sent), 2)

    def test_r_reverses_effect_and_returns_to_live_video(self):
        result = mock_video(keys=[0, ord("v")] + [0] * 6 + [ord("r")] + [0] * 6 + [ord("q")])
        np.testing.assert_array_equal(result.shown[-1], result.raw[-1])
        self.assertEqual(result.sound.play.call_count, 2)

    def test_goku_ignores_v_and_r_keys(self):
        result = mock_video(mode="goku", keys=[0, ord("v"), ord("r"), 0, ord("q")])
        np.testing.assert_array_equal(result.shown[-1], result.raw[-1])
        result.sound.play.assert_not_called()

    def test_goku_gesture_disappears_and_reappears(self):
        result = mock_video(mode="goku", keys=[0] * 24 + [ord("q")], events={4: 1, 14: 2})
        self.assertEqual(result.sound.play.call_count, 2)
        np.testing.assert_array_equal(result.shown[-1], result.raw[-1])

    def test_every_mode_returns_with_second_gesture(self):
        for mode, _, _ in app.MODES:
            with self.subTest(mode=mode):
                result = mock_video(mode=mode, keys=[0]*70+[ord("q")], events={4:1, 38:2})
                self.assertEqual(result.sound.play.call_count, 2)
                np.testing.assert_array_equal(result.shown[-1], result.raw[-1])

    def test_goku_preparation_delay_does_not_discard_latched_event(self):
        result = mock_video(mode="goku", keys=[0]*24+[ord("q")], events={4:1, 14:2}, event_delay=.65)
        self.assertEqual(result.sound.play.call_count, 2)
        np.testing.assert_array_equal(result.shown[-1], result.raw[-1])

    def test_preview_guidance_does_not_leak_into_virtual_output(self):
        result = mock_video(mode="goku", keys=[0, 0, ord("q")], hud=True)
        self.assertFalse(np.array_equal(result.shown[0], cv2.cvtColor(result.sent[0], cv2.COLOR_RGB2BGR)))
        np.testing.assert_array_equal(result.sent[0], cv2.cvtColor(result.raw[1], cv2.COLOR_BGR2RGB))


    def test_audio_failure_keeps_video_and_return_working(self):
        result = mock_video(mode="whoosh", keys=[0]*24+[ord("q")],
                            events={4:1, 14:2}, sound_error=RuntimeError("audio device disconnected"))
        self.assertEqual(result.sound.play.call_count, 1)
        np.testing.assert_array_equal(result.shown[-1], result.raw[-1])

    def test_mute_stops_audio_and_skips_next_play(self):
        result = mock_video(keys=[0, ord("m"), ord("v")]+[0]*10+[ord("q")])
        result.sound.stop.assert_called_once()
        result.sound.play.assert_not_called()

if __name__ == "__main__":
    unittest.main()
