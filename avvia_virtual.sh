#!/usr/bin/env bash
# Richiede la webcam virtuale. Equivalente a AVVIA_VIRTUAL.bat.
set -euo pipefail
exec "$(dirname "$0")/avvia_locale.sh" --virtual-camera "$@"
