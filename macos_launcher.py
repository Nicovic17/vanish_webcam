"""Finder launcher for the macOS build; video processing stays upstream."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback


def configure_application():
    """Use the same graceful quit path for the app menu and Dock Quit."""
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyRegular, NSMenu, NSMenuItem,
        NSTerminateCancel,
    )
    from Foundation import NSObject

    class VanishCamApplicationDelegate(NSObject):
        def applicationShouldTerminate_(self, application):
            self.quit_requested = True
            if application.modalWindow() is not None:
                application.abortModal()
            # The video loop owns the camera, audio and model cleanup.
            return NSTerminateCancel

    application = NSApplication.sharedApplication()
    delegate = VanishCamApplicationDelegate.alloc().init()
    delegate.quit_requested = False
    application.setDelegate_(delegate)
    application.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    menu = NSMenu.alloc().init()
    app_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("VanishCam", None, "")
    app_menu = NSMenu.alloc().initWithTitle_("VanishCam")
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit VanishCam", "terminate:", "q"
    )
    quit_item.setTarget_(application)
    app_menu.addItem_(quit_item)
    app_item.setSubmenu_(app_menu)
    menu.addItem_(app_item)
    application.setMainMenu_(menu)
    application.finishLaunching()
    application.activateIgnoringOtherApps_(True)
    # Retain the delegate: NSApplication's delegate reference is weak.
    return application, delegate


def configure_logging() -> None:
    log_dir = Path.home() / "Library" / "Logs" / "VanishCam"
    log_dir.mkdir(parents=True, exist_ok=True)
    stream = (log_dir / "VanishCam.log").open("a", buffering=1)
    sys.stdout = stream
    sys.stderr = stream
    # Also capture diagnostics from native MediaPipe/OpenCV libraries.
    os.dup2(stream.fileno(), 1)
    os.dup2(stream.fileno(), 2)
    # This is a fixed-location bundle, so retain the font cache between launches
    # instead of PyInstaller's temporary directory on every run.
    os.environ["MPLCONFIGDIR"] = str(log_dir / "matplotlib")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def show_alert(title: str, text: str, buttons: tuple[str, ...]) -> int:
    from AppKit import NSAlert

    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(text)
    for label in buttons:
        alert.addButtonWithTitle_(label)
    return alert.runModal() - 1000


def authorize_camera() -> None:
    from AVFoundation import (
        AVCaptureDevice, AVMediaTypeVideo, AVAuthorizationStatusAuthorized,
        AVAuthorizationStatusNotDetermined,
    )
    from Foundation import NSDate, NSRunLoop

    status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)
    if status == AVAuthorizationStatusNotDetermined:
        result = []
        AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVMediaTypeVideo, lambda allowed: result.append(allowed)
        )
        while not result:
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.05)
            )
        if result[0]:
            return
    elif status == AVAuthorizationStatusAuthorized:
        return
    raise RuntimeError(
        "Camera access is disabled. Allow VanishCam in System Settings > "
        "Privacy & Security > Camera, then reopen the app."
    )


def main() -> int:
    # Keep the bundled diagnostic command usable without requesting camera access.
    if any(argument in sys.argv for argument in ("--self-test", "--help", "-h")):
        import vanish_cam
        return vanish_cam.main()

    configure_logging()
    application, delegate = configure_application()
    try:
        if not any(arg == "--mode" or arg.startswith("--mode=") for arg in sys.argv[1:]):
            choice = show_alert(
                "VanishCam",
                "Choose an effect. After the camera opens, step out of frame for "
                "4 seconds to capture the empty background.\n\n"
                "Normal Vanish: make a V sign to dissolve.\n"
                "Naruto Vanish: bring both palms together for smoke and a log.\n\n"
                "Click the video window to use these keys:\n"
                "V — vanish     R — reappear\n"
                "Space — recapture background\n"
                "F — fullscreen     Q, Esc or Command-Q — quit\n\n"
                "Video is processed locally. No microphone is needed.",
                ("Normal Vanish", "Naruto Vanish", "Quit"),
            )
            if choice not in (0, 1):
                return 0
            sys.argv.extend(["--mode", ("normal", "naruto")[choice]])
        authorize_camera()
        import vanish_cam
        # Let this wrapper display errors visibly instead of swallowing them.
        return vanish_cam.run(should_quit=lambda: delegate.quit_requested)
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        traceback.print_exc()
        show_alert(
            "VanishCam could not start",
            f"{error}\n\nDetails: ~/Library/Logs/VanishCam/VanishCam.log",
            ("OK",),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
