#!/usr/bin/env bash
# Lancia Vanish Lab su macOS/Linux. Equivalente a AVVIA_LOCALE.bat.
set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv-local"
VENV_PY="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "[Vanish Lab] Creo l'ambiente Python locale..."
  python3 -m venv "$VENV_DIR"
fi

if ! "$VENV_PY" -c "import cv2, mediapipe, numpy, pyvirtualcam" >/dev/null 2>&1; then
  echo "[Vanish Lab] Installo i componenti necessari. Serve internet solo questa volta..."
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r requirements.txt
fi

echo "[Vanish Lab] Avvio la webcam..."
exec "$VENV_PY" vanish_cam.py "$@"
