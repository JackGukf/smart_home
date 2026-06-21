#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
fi

"$PYTHON" -m uvicorn src.python.web_app:app --host "$HOST" --port "$PORT"
