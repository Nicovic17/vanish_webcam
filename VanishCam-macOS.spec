"""Standalone, ad-hoc signed Apple silicon application bundle."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

root = Path(SPECPATH).resolve()
resources = [
    (root / "hand_landmarker.task", "."),
    (root / "models" / "gesture_recognizer.task", "models"),
    (root / "models" / "selfie_segmenter_landscape.tflite", "models"),
    (root / "assets" / "substitution_log.png", "assets"),
    (root / "assets" / "vanish.MP3", "assets"),
]
for path, _ in resources:
    if not path.is_file():
        raise SystemExit(f"Missing bundled resource: {path}")

a = Analysis(
    [str(root / "macos_launcher.py")],
    pathex=[str(root)],
    binaries=collect_dynamic_libs("mediapipe"),
    datas=[(str(path), destination) for path, destination in resources]
          + collect_data_files("mediapipe"),
    hiddenimports=["mediapipe.tasks.c", "pyvirtualcam"],
    excludes=["pygame", "tkinter", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="VanishCam",
    debug=False, strip=False, upx=False, console=False,
    argv_emulation=False, target_arch="arm64", codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VanishCam")
app = BUNDLE(
    coll, name="VanishCam.app", icon=str(root / "assets" / "vanish_icon.ico"),
    bundle_identifier="io.github.nicovic17.vanishcam",
    info_plist={
        "CFBundleName": "VanishCam",
        "CFBundleDisplayName": "VanishCam",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "NSCameraUsageDescription": "VanishCam uses your camera to apply disappearance effects locally on your Mac.",
        "NSPrincipalClass": "NSApplication",
        "NSRequiresAquaSystemAppearance": False,
    },
)
