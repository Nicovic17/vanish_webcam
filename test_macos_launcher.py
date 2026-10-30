"""Camera permission and quit paths are testable on Windows as well as macOS."""

import sys
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import macos_launcher as launcher


class CameraPermissionTests(unittest.TestCase):
    def check_permission(self, status, response=None):
        device = Mock()
        device.authorizationStatusForMediaType_.return_value = status
        if response is not None:
            device.requestAccessForMediaType_completionHandler_.side_effect = (
                lambda media, callback: callback(response)
            )
        modules = {
            "AVFoundation": SimpleNamespace(
                AVCaptureDevice=device, AVMediaTypeVideo="video",
                AVAuthorizationStatusAuthorized=3, AVAuthorizationStatusNotDetermined=0,
            ),
            "Foundation": SimpleNamespace(NSDate=Mock(), NSRunLoop=Mock()),
        }
        with patch.dict(sys.modules, modules):
            launcher.authorize_camera()
        return device

    def test_authorized_camera_does_not_prompt_again(self):
        device = self.check_permission(3)
        device.requestAccessForMediaType_completionHandler_.assert_not_called()

    def test_new_permission_can_be_granted(self):
        self.check_permission(0, True)

    def test_denied_and_restricted_permissions_have_actionable_errors(self):
        for status in (1, 2):
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, "System Settings"):
                self.check_permission(status)
        with self.assertRaisesRegex(RuntimeError, "System Settings"):
            self.check_permission(0, False)


class LauncherTests(unittest.TestCase):
    def test_diagnostics_do_not_request_camera_access(self):
        for flag in ("--self-test", "--help", "-h"):
            app = Mock()
            app.main.return_value = 0
            with patch.object(sys, "argv", ["VanishCam", flag]), patch.dict(
                sys.modules, vanish_cam=app
            ), patch.object(launcher, "authorize_camera") as authorize:
                self.assertEqual(launcher.main(), 0)
            app.main.assert_called_once()
            authorize.assert_not_called()

    def test_quit_from_chooser_never_opens_camera(self):
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(sys, "argv", ["VanishCam"]))
            mocks.enter_context(patch.object(launcher, "configure_logging"))
            mocks.enter_context(patch.object(launcher, "configure_application", return_value=(Mock(), Mock())))
            mocks.enter_context(patch.object(launcher, "show_alert", return_value=2))
            authorize = mocks.enter_context(patch.object(launcher, "authorize_camera"))
            self.assertEqual(launcher.main(), 0)
            authorize.assert_not_called()

    def test_explicit_mode_skips_chooser_and_connects_graceful_quit(self):
        app = Mock()
        app.run.return_value = 0
        delegate = SimpleNamespace(quit_requested=False)
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(sys, "argv", ["VanishCam", "--mode=naruto"]))
            mocks.enter_context(patch.dict(sys.modules, vanish_cam=app))
            mocks.enter_context(patch.object(launcher, "configure_logging"))
            mocks.enter_context(patch.object(launcher, "configure_application", return_value=(Mock(), delegate)))
            mocks.enter_context(patch.object(launcher, "authorize_camera"))
            alert = mocks.enter_context(patch.object(launcher, "show_alert"))
            self.assertEqual(launcher.main(), 0)
            alert.assert_not_called()
        should_quit = app.run.call_args.kwargs["should_quit"]
        self.assertFalse(should_quit())
        delegate.quit_requested = True
        self.assertTrue(should_quit())

    def test_native_menu_and_dock_quit_cancel_modal_and_request_cleanup(self):
        class NSObject:
            @classmethod
            def alloc(cls):
                return cls()

            def init(self):
                return self

        application = Mock()
        modules = {
            "Foundation": SimpleNamespace(NSObject=NSObject),
            "AppKit": SimpleNamespace(
                NSApplication=Mock(sharedApplication=Mock(return_value=application)),
                NSApplicationActivationPolicyRegular=0, NSTerminateCancel=0,
                NSMenu=Mock(), NSMenuItem=Mock(),
            ),
        }
        with patch.dict(sys.modules, modules):
            _, delegate = launcher.configure_application()
        self.assertFalse(delegate.quit_requested)
        self.assertEqual(delegate.applicationShouldTerminate_(application), 0)
        self.assertTrue(delegate.quit_requested)
        application.abortModal.assert_called_once()
        application.modalWindow.return_value = None
        delegate.applicationShouldTerminate_(application)
        self.assertEqual(application.abortModal.call_count, 1)


if __name__ == "__main__":
    unittest.main()
