"""Build the complete VanishCam and three focused Windows editions."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs


root = Path(SPECPATH).resolve()
icon_file = root / "assets" / "vanish_icon.ico"
segmenter = (root / "models" / "selfie_segmenter_landscape.tflite", "models")
license_config = (root / "license_config.json", ".")
editions = (
    (
        "full", "VanishCam",
        (
            (root / "hand_landmarker.task", "."),
            (root / "models" / "gesture_recognizer.task", "models"),
            (root / "models" / "blaze_face_short_range.tflite", "models"),
            (root / "assets" / "substitution_log.png", "assets"),
            (root / "assets" / "vanish.MP3", "assets"),
            (root / "assets" / "teleport.MP3", "assets"),
            (root / "assets" / "itachi_crow_sheet.png", "assets"),
            (root / "assets" / "sharingan.png", "assets"),
        ),
    ),
    (
        "naruto", "Naruto Vanish Effect",
        (
            (root / "hand_landmarker.task", "."),
            (root / "assets" / "substitution_log.png", "assets"),
            (root / "assets" / "vanish.MP3", "assets"),
        ),
    ),
    (
        "goku", "Goku Vanish Effect",
        (
            (root / "hand_landmarker.task", "."),
            (root / "models" / "blaze_face_short_range.tflite", "models"),
            (root / "assets" / "teleport.MP3", "assets"),
        ),
    ),
    (
        "normal_particles", "Normal and Particles Vanish",
        ((root / "models" / "gesture_recognizer.task", "models"),),
    ),
)

all_resources = [
    path for edition, _, extras in editions
    for path, _ in (segmenter, *extras, (root / "editions" / edition / "edition.txt", "."))
]
missing = [str(path) for path in (icon_file, license_config[0], *all_resources) if not path.is_file()]
if missing:
    raise SystemExit("File necessari alla build mancanti:\n" + "\n".join(missing))

mediapipe_binaries = collect_dynamic_libs("mediapipe")
executables = []
for edition, name, extras in editions:
    resources = (segmenter, license_config, *extras, (root / "editions" / edition / "edition.txt", "."))
    analysis = Analysis(
        [str(root / "vanish_cam.py")],
        pathex=[str(root)],
        binaries=mediapipe_binaries,
        datas=[(str(path), destination) for path, destination in resources],
        hiddenimports=["pygame.mixer", "mediapipe.tasks.c"],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=[],
        noarchive=False,
    )
    archive = PYZ(analysis.pure)
    executables.append(EXE(
        archive,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        icon=str(icon_file),
    ))
