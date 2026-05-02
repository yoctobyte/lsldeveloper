#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${LSLDEVELOPER_VENV:-"$ROOT_DIR/.venv"}"

usage() {
    cat <<'EOF'
Usage: ./ide.sh [--init-venv] [project-folder] [ide options]

Runs the Tk LSL IDE from the project root.

Options:
  --init-venv   Create .venv first if it does not exist.
  -h, --help    Show the IDE help.

Environment:
  LSLDEVELOPER_VENV   Override the venv path. Defaults to .venv.
  PYTHON              Python executable used when no venv exists.
EOF
}

if [[ "${1:-}" == "--init-venv" ]]; then
    PYTHON_BIN="${PYTHON:-python3}"
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
    shift
fi

if [[ "${1:-}" == "--script-help" ]]; then
    usage
    exit 0
fi

if [[ -x "$VENV_DIR/bin/python" ]]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
else
    PYTHON_BIN="${PYTHON:-python3}"
fi

cd "$ROOT_DIR"
exec "$PYTHON_BIN" -m ide "$@"
