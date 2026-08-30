#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
LOCK_FILE="$SKILL_DIR/requirements.lock"

command -v uv >/dev/null 2>&1 || {
  echo "uv is required but was not found on PATH" >&2
  exit 1
}

if [[ ! -x "$VENV_PYTHON" ]]; then
  uv venv --no-config --no-progress --python 3.12 "$VENV_DIR"
fi

PYTHON_MINOR="$($VENV_PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_MINOR" != "3.12" ]]; then
  echo "Expected CPython 3.12 in $VENV_DIR, found $PYTHON_MINOR" >&2
  exit 1
fi

uv pip sync --no-config --no-progress --strict --python "$VENV_PYTHON" "$LOCK_FILE"
