#!/usr/bin/env bash
# Anteprima locale senza webcam virtuale (sorgente per una scena OBS).
# Equivalente a AVVIA_OBS.bat.
set -euo pipefail
exec "$(dirname "$0")/avvia_locale.sh" --no-virtual-camera "$@"
