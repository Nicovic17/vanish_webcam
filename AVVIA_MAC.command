#!/bin/bash
# Avvio locale su macOS: ambiente Python, componenti e webcam.
set -euo pipefail
cd "$(dirname "$0")"

fail() {
  echo
  echo "Impossibile avviare Vanish Lab. Leggi il README per le soluzioni comuni."
  read -r -p "Premi Invio per chiudere..." _ || true
  exit 1
}
trap fail ERR

VENV_DIR=".venv-local"
VENV_PY="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "[Vanish Lab] Creo l'ambiente Python locale..."
  for PYTHON in python3.13 python3.12 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 \
                /usr/local/bin/python3.13 /usr/local/bin/python3.12; do
    if command -v "$PYTHON" >/dev/null 2>&1; then
      "$PYTHON" -m venv "$VENV_DIR"
      break
    fi
  done
  if [ ! -x "$VENV_PY" ]; then
    echo "[Vanish Lab] Serve Python 3.12 o 3.13: pygame non ha pacchetti per Python 3.14 e successivi."
    false
  fi
fi

if ! "$VENV_PY" -c "import cv2, mediapipe, numpy, pyvirtualcam" >/dev/null 2>&1; then
  echo "[Vanish Lab] Installo i componenti necessari. Serve internet solo questa volta..."
  "$VENV_PY" -m pip install --upgrade pip >/dev/null
  "$VENV_PY" -m pip install -r requirements.txt
fi

echo "[Vanish Lab] Avvio la webcam..."
"$VENV_PY" vanish_cam.py "$@"
