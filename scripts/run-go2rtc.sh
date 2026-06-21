#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO2RTC_BIN="${GO2RTC_BIN:-$ROOT_DIR/bin/go2rtc}"
CONFIG_FILE="${GO2RTC_CONFIG:-$ROOT_DIR/go2rtc/go2rtc.yaml}"

cd "$ROOT_DIR"

if [[ ! -x "$GO2RTC_BIN" ]]; then
  echo "ERROR: go2rtc binary not found at $GO2RTC_BIN"
  echo "Install it first, then rerun this script."
  exit 1
fi

python3 scripts/generate-go2rtc-config.py
exec "$GO2RTC_BIN" -config "$CONFIG_FILE"
