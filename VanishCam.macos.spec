"""PyInstaller app-bundle build for macOS."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs


root = Path(SPECPATH).resolve()
resources = [
    (root / "hand_landmarker.task", "."),
    (root / "models" / "gesture_recognizer.task", "models"),
    (root / "models" / "selfie_segmenter_landscape.tflite", "models"),
    (root / "assets" / "substitution_log.png", "assets"),
    (root / "assets" / "vanish.MP3", "assets"),
]
missing = [str(path) for path, _ in resources if not path.is_file()]
if missing:
    raise SystemExit("Required build files are missing:\n" + "\n".join(missing))

a = Analysis(
    [str(root / "vanish_cam.py")],
    pathex=[str(root)],
    binaries=collect_dynamic_libs("mediapipe"),
    datas=[(str(path), destination) for path, destination in resources],
    hiddenimports=["mediapipe.tasks.c"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pygame"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VanishCam",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
    argv_emulation=False,
)
collect = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VanishCam",
)
app = BUNDLE(
    collect,
    name="VanishCam.app",
    icon=None,
    bundle_identifier="com.vanishcam.app",
    info_plist={
        "NSCameraUsageDescription": (
            "VanishCam uses the camera locally to apply visual effects. "
            "Camera frames are not recorded or uploaded."
        ),
    },
)
