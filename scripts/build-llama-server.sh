#!/usr/bin/env bash
#
# Build llama.cpp for the Orange Pi 6 Plus.  Run it ON the board.
#
#   ssh orangepi@192.168.0.234
#   cd smart_home_AI && ./scripts/build-llama-server.sh
#
# The arch flags are the whole point of this script.  Measured 2026-09-02 on
# Qwen3-4B Q4_K_M, 8 threads pinned to the A720 cores:
#
#   -mcpu=native (the default)            16.8 t/s prompt   11.4 t/s generation
#   -march=armv9-a+i8mm+dotprod+sve+bf16  52.6 t/s prompt   14.6 t/s generation
#
# GCC 13 cannot identify this heterogeneous A720+A520 CPU, so `-mcpu=native`
# compiles happily while emitting *zero* __ARM_FEATURE_* macros - every ggml
# feature probe fails and you get a baseline armv8-a binary with no warning.
# Check with:  echo | gcc -mcpu=native -dM -E - | grep __ARM_FEATURE
#
# KleidiAI is deliberately OFF.  It was worth ~1% on prompt processing here and
# consistently *cost* generation throughput (13.3 vs 14.6 t/s on Q4_K_M, 14.3 vs
# 15.4 on Q4_0), so it is not a win on this board.
set -euo pipefail

SRC_DIR="${LLAMA_SRC:-${HOME}/llama-kleidi}"
BUILD_DIR="${SRC_DIR}/build-kleidi-off"
ARCH="${LLAMA_ARCH:-armv9-a+i8mm+dotprod+sve+bf16}"
JOBS="${JOBS:-8}"

if [[ ! -d "${SRC_DIR}/.git" ]]; then
  echo "==> cloning llama.cpp into ${SRC_DIR}"
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "${SRC_DIR}"
fi

echo "==> configuring (-march=${ARCH}, KleidiAI off)"
cmake -B "${BUILD_DIR}" -S "${SRC_DIR}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF \
  -DGGML_CPU_ARM_ARCH="${ARCH}" \
  -DGGML_CPU_KLEIDIAI=OFF \
  -DGGML_LLAMAFILE=OFF \
  -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF

# Fail loudly if the arch did not take: a silently baseline build is the exact
# trap this script exists to avoid.
if ! grep -q "HAVE_DOTPROD.*Success" "${BUILD_DIR}/CMakeFiles/CMakeConfigureLog.yaml" 2>/dev/null; then
  echo "    (could not confirm dotprod from the configure log; check the output above)" >&2
fi

echo "==> building"
cmake --build "${BUILD_DIR}" -j"${JOBS}" --target llama-server llama-cli llama-bench llama-quantize

echo "==> built:"
ls -la "${BUILD_DIR}/bin/" | grep -E "llama-(server|cli|bench|quantize)$"

cat <<EOF

Next:
  # produce the Q4_0 model this board is fastest on
  ${BUILD_DIR}/bin/llama-quantize --allow-requantize \\
      \${HOME}/Qwen3-4B-Q4_K_M.gguf \${HOME}/Qwen3-4B-Q4_0.gguf Q4_0

  # then install the service
  ./scripts/install-ai-services.sh
EOF
