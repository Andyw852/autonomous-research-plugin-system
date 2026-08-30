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
  uv venv --no-config --no-progress --python 3.11 "$VENV_DIR"
fi

PYTHON_MINOR="$($VENV_PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_MINOR" != "3.11" ]]; then
  echo "Expected CPython 3.11 in $VENV_DIR, found $PYTHON_MINOR" >&2
  exit 1
fi

uv pip sync --no-config --no-progress --python "$VENV_PYTHON" "$LOCK_FILE"

CHECK_STATUS=0
CHECK_OUTPUT="$(uv pip check --no-config --python "$VENV_PYTHON" 2>&1)" || CHECK_STATUS=$?
if grep -Fq 'All installed packages are compatible' <<<"$CHECK_OUTPUT"; then
  :
elif grep -Fq 'Found 1 incompatibility' <<<"$CHECK_OUTPUT" \
  && grep -Fq 'The package `dataclasses` requires Python >=3.6, <3.7' <<<"$CHECK_OUTPUT" \
  && [[ "$(grep -c '^The package ' <<<"$CHECK_OUTPUT")" == "1" ]]; then
  echo "Accepted known PyTDC 1.1.14 metadata defect: dataclasses 0.8 is declared for CPython 3.11." >&2
else
  echo "uv pip check exited with status $CHECK_STATUS" >&2
  printf '%s\n' "$CHECK_OUTPUT" >&2
  exit 1
fi

"$VENV_PYTHON" -c 'import dataclasses, importlib.metadata as m; assert "site-packages" not in dataclasses.__file__; assert m.version("PyTDC") == "1.1.14"; assert m.version("setuptools") == "80.9.0"'
