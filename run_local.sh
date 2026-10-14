#!/usr/bin/env bash
set -e

# Change to the project directory
cd "$(dirname "$0")"

VENV_DIR=".venv"
VENV_PY="$VENV_DIR/bin/python3"

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "[Vanish Cam] Error: python3 is not installed or not in PATH." >&2
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -f "$VENV_PY" ]; then
    echo "[Vanish Cam] Creating local Python virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Ensure required packages are installed
if ! "$VENV_PY" -c "import cv2, mediapipe, numpy, pyvirtualcam, pygame" >/dev/null 2>&1; then
    echo "[Vanish Cam] Installing required dependencies (first run only)..."
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r requirements.txt
fi

echo "[Vanish Cam] Launching webcam application..."
exec "$VENV_PY" vanish_cam.py "$@"
