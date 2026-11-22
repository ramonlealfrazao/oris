#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
exec "$PY" iniciar.py "$@"
