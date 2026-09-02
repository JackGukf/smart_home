#!/usr/bin/env bash
#
# Serve Qwen3-4B from llama.cpp on the Orange Pi 6 Plus.
#
# Runs alongside Ollama rather than replacing it: Ollama bundles its own
# llama.cpp, so swapping its runner would be undone by the next Ollama update.
# This is a separate, reversible service on its own port.
#
# Two board-specific details do all the work here, both measured 2026-09-02:
#
#   * The build must come from build-kleidi-off, configured with an explicit
#     -march. GCC 13 cannot identify this heterogeneous A720+A520 CPU, so
#     -mcpu=native emits zero __ARM_FEATURE_* macros and silently produces a
#     baseline armv8-a binary: 16.8 t/s prompt vs 86.9 with the arch spelled
#     out. KleidiAI measurably did not help (and hurt generation), so it is off.
#
#   * Threads are pinned to the eight A720 cores. Their numbering is
#     interleaved - 0,1,6,7,8,9,10,11 are A720, 2,3,4,5 are A520 - so an
#     unpinned 12-thread run waits on the 1.8GHz little cores every matmul:
#     15.4 t/s generation pinned vs 9.3 unpinned.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LLAMA_BIN="${LLAMA_BIN:-${HOME}/llama-kleidi/build-kleidi-off/bin/llama-server}"
# Q4_0 over Q4_K_M: 86.9 vs 52.6 t/s prompt processing, and slightly better
# generation too.
LLAMA_MODEL="${LLAMA_MODEL:-${HOME}/Qwen3-4B-Q4_0.gguf}"
LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_PORT:-8081}"
LLAMA_CTX="${LLAMA_CTX:-4096}"
LLAMA_THREADS="${LLAMA_THREADS:-8}"
BIG_CORES="${LLAMA_BIG_CORES:-0,1,6,7,8,9,10,11}"

[[ -x "${LLAMA_BIN}" ]] || {
  echo "llama-server not found at ${LLAMA_BIN}" >&2
  echo "Build it with scripts/build-llama-server.sh" >&2
  exit 1
}
[[ -r "${LLAMA_MODEL}" ]] || { echo "model not found at ${LLAMA_MODEL}" >&2; exit 1; }

# Loopback by default. Generation is memory-bandwidth bound at ~15 tok/s, so
# this is a single-user endpoint; reach it over SSH rather than widening it,
# the same posture as the Ollama service.
exec taskset -c "${BIG_CORES}" "${LLAMA_BIN}" \
  --model "${LLAMA_MODEL}" \
  --host "${LLAMA_HOST}" \
  --port "${LLAMA_PORT}" \
  --ctx-size "${LLAMA_CTX}" \
  --threads "${LLAMA_THREADS}" \
  --threads-batch "${LLAMA_THREADS}" \
  --no-warmup
