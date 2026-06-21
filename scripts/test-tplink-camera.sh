#!/usr/bin/env bash
set -euo pipefail

CAMERA_HOST="${1:-192.168.0.24}"
STREAM_PATH="${2:-/stream1}"
OUTPUT="${OUTPUT:-/tmp/tplink-camera-test.jpg}"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

if [[ -z "${TAPO_CAMERA_USERNAME:-}" || -z "${TAPO_CAMERA_PASSWORD:-}" ]]; then
  echo "ERROR missing TAPO_CAMERA_USERNAME or TAPO_CAMERA_PASSWORD in .env"
  exit 2
fi

if [[ "${TAPO_CAMERA_USERNAME}" == "replace_me" || "${TAPO_CAMERA_PASSWORD}" == "replace_me" ]]; then
  echo "ERROR .env still contains placeholder camera credentials"
  exit 2
fi

python3 - "$CAMERA_HOST" "$STREAM_PATH" "$OUTPUT" <<'PY'
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


host = sys.argv[1]
stream_path = sys.argv[2]
output = Path(sys.argv[3])
if not stream_path.startswith("/"):
    stream_path = f"/{stream_path}"

username = quote(os.environ["TAPO_CAMERA_USERNAME"], safe="")
password = quote(os.environ["TAPO_CAMERA_PASSWORD"], safe="")
rtsp_url = f"rtsp://{username}:{password}@{host}:554{stream_path}"

result = subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-frames:v",
        "1",
        "-y",
        str(output),
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    timeout=20,
)

if result.returncode != 0:
    print(f"ERROR ffmpeg could not read the stream, return code {result.returncode}")
    raise SystemExit(result.returncode)

print(f"OK wrote one frame to {output} ({output.stat().st_size} bytes)")
PY
