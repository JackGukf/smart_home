#!/usr/bin/env bash
# The forecasting environment for energy-forecast.service, on the board.
#
# Kept apart from the dashboard's .venv on purpose: torch alone is several GB,
# and the dashboard must not import it. The dashboard only reads the JSON the
# nightly job writes. Disk cost ~5.6 GB for the venv plus ~456 MB of model
# weights in ~/.cache/huggingface; the job's peak memory is ~1.3 GB with
# Chronos-2, ~160 MB without it.
#
#   scripts/install-forecast-venv.sh              # everything, including Chronos-2
#   scripts/install-forecast-venv.sh --no-chronos # baseline + LightGBM only (~200 MB)
set -euo pipefail

VENV="${FORECAST_VENV:-$HOME/forecast-venv}"
WITH_CHRONOS=yes
[[ "${1:-}" == "--no-chronos" ]] && WITH_CHRONOS=no

python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade -q pip

# scikit-learn is not optional: lightgbm's sklearn API refuses to load without it.
"$VENV/bin/pip" install -q numpy lightgbm scikit-learn aiohttp pyyaml

if [[ $WITH_CHRONOS == yes ]]; then
    "$VENV/bin/pip" install -q torch pandas chronos-forecasting
fi

"$VENV/bin/python" - <<'PY'
import importlib
for name in ("numpy", "lightgbm", "sklearn", "aiohttp"):
    print(f"{name:12} {importlib.import_module(name).__version__}")
for name in ("torch", "pandas", "chronos"):
    try:
        print(f"{name:12} {getattr(importlib.import_module(name), '__version__', 'installed')}")
    except ImportError:
        print(f"{name:12} not installed (baseline + LightGBM only)")
PY

echo
echo "next:  cp deploy/systemd/user/energy-forecast.{service,timer} ~/.config/systemd/user/"
echo "       systemctl --user daemon-reload && systemctl --user enable --now energy-forecast.timer"
