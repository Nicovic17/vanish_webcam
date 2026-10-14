#!/usr/bin/env bash
cd "$(dirname "$0")"
exec ./run_local.sh --virtual-camera "$@"
