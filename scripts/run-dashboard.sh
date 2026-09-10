#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"
# The dashboard holds a /api/events/stream SSE connection open for every browser
# tab that has ever looked at it. Those never close on their own, so without a
# deadline uvicorn logs "Waiting for connections to close" and waits for ever -
# systemd then SIGKILLs it at TimeoutStopSec and leaves the unit `failed`, which
# does not self-recover and made every deploy a coin flip.
GRACEFUL_SHUTDOWN_S="${GRACEFUL_SHUTDOWN_S:-5}"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
fi

# exec so uvicorn *is* the service's main process: systemd's SIGTERM reaches it
# directly, and there is no shell left behind for "process remains running".
exec "$PYTHON" -m uvicorn src.python.web_app:app \
  --host "$HOST" --port "$PORT" \
  --timeout-graceful-shutdown "$GRACEFUL_SHUTDOWN_S"
