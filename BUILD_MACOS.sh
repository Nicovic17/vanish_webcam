#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "BUILD_MACOS.sh must be run on macOS." >&2
    exit 1
fi

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python 3.10 through 3.13 is required. Set PYTHON to its executable." >&2
    exit 1
fi
if ! "$PYTHON" -c 'import sys; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 14)))'; then
    echo "Python 3.10 through 3.13 is required for the declared MediaPipe dependency." >&2
    exit 1
fi

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-macos}"
VENV_PY="$VENV_DIR/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
    "$PYTHON" -m venv "$VENV_DIR"
fi

"$VENV_PY" -m pip install -r requirements.txt "pyinstaller>=6,<7"
"$VENV_PY" -c "from vanish_cam import download_models; download_models()"
"$VENV_PY" -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath dist/macos \
    --workpath build/macos \
    VanishCam.macos.spec

APP_EXECUTABLE="$ROOT_DIR/dist/macos/VanishCam.app/Contents/MacOS/VanishCam"
if [[ ! -x "$APP_EXECUTABLE" ]]; then
    echo "The build did not produce VanishCam.app." >&2
    exit 1
fi

"$APP_EXECUTABLE" --self-test
echo
echo "Build complete: $ROOT_DIR/dist/macos/VanishCam.app"
