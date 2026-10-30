#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  print -u2 'This build targets Apple silicon Macs. Use BUILD_WINDOWS.bat on Windows.'
  exit 1
fi
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  print -u2 'Python 3.12 is required. Install it or set PYTHON_BIN to its executable.'
  exit 1
fi
"$PYTHON_BIN" -c 'import sys; sys.exit(None if sys.version_info[:2] == (3, 12) else "Use Python 3.12 for this build")'
"$PYTHON_BIN" -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements-macos.txt
.venv-macos/bin/python -c 'from vanish_cam import download_models; download_models()'
.venv-macos/bin/python -m PyInstaller --clean --noconfirm VanishCam-macOS.spec
dist/VanishCam.app/Contents/MacOS/VanishCam --self-test
print 'Built and verified: dist/VanishCam.app'
