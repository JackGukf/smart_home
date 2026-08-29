#!/usr/bin/env bash
# Stage the dashboard's static assets for deployment, compiling app.js down to
# a syntax level older browsers can parse.
#
# app.js is written in modern JavaScript (optional chaining, nullish
# coalescing). Those are *syntax*, so a browser that does not understand them
# fails to parse the whole file and runs none of it - the dashboard renders its
# "Loading…" placeholders forever. No polyfill can help, because a polyfill is
# itself JavaScript that must parse first.
#
# Compiling to ES2019 also makes the file smaller, since esbuild reprints the
# code without comments, so every browser gets a faster download than the
# untranspiled source.
#
# Usage: scripts/build-dashboard-assets.sh <output-dir>
set -euo pipefail

# The oldest browser the dashboard supports. iOS 12.5.8 (the iPad mini) ships
# Safari 12.1, which implements ES2019 but not the ES2020 syntax above.
# Raising this is a product decision: check what it drops before changing it.
ES_TARGET="es2019"

OUT_DIR="${1:-}"
if [[ -z "${OUT_DIR}" ]]; then
    echo "Usage: scripts/build-dashboard-assets.sh <output-dir>" >&2
    exit 2
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATIC_DIR="${PROJECT_ROOT}/src/python/web_static"

if ! command -v npx >/dev/null 2>&1; then
    echo "ERROR: npx not found, so app.js cannot be compiled for older browsers." >&2
    echo "       Install Node.js, or deploy knowing the dashboard will not load" >&2
    echo "       on anything older than Safari 13.1 / Chrome 80." >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"
# Copy everything first, then overwrite app.js with the compiled build, so any
# asset added to web_static ships without needing a change here.
cp -a "${STATIC_DIR}/." "${OUT_DIR}/"

echo "==> Compiling app.js to ${ES_TARGET}"
npx --yes esbuild "${STATIC_DIR}/app.js" \
    --target="${ES_TARGET}" \
    --sourcemap \
    --outfile="${OUT_DIR}/app.js" \
    --log-level=warning

# A silent failure here would ship syntax the old browsers choke on, which is
# the exact bug this script exists to prevent. Fixed-string, not regex: these
# tokens are regex metacharacters, and a malformed pattern would fail open.
for token in '?.' '??'; do
    if grep -qF -- "${token}" "${OUT_DIR}/app.js"; then
        echo "ERROR: compiled app.js still contains '${token}'." >&2
        echo "       Old browsers cannot parse it. Check the esbuild target." >&2
        exit 1
    fi
done

SRC_BYTES="$(stat -c%s "${STATIC_DIR}/app.js")"
OUT_BYTES="$(stat -c%s "${OUT_DIR}/app.js")"
echo "==> app.js ${SRC_BYTES} -> ${OUT_BYTES} bytes (${ES_TARGET}, source map alongside)"
