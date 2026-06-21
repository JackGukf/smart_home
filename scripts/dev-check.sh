#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-$HOME/workspace/smart-home-rpi4}"

echo "Checking tools..."
command -v gcc
command -v g++
command -v cmake
command -v ninja
command -v gdb
command -v python3

echo
echo "Running Python starter..."
python3 "$PROJECT_ROOT/src/python/controller.py"

echo
echo "Running Python tests..."
python3 -m pytest "$PROJECT_ROOT/tests/python"

echo
echo "Configuring C++ starter..."
if [[ -f "$PROJECT_ROOT/CMakePresets.json" ]]; then
    cmake -S "$PROJECT_ROOT" -B "$PROJECT_ROOT/build/dev-check" -G Ninja -DCMAKE_BUILD_TYPE=Debug
    cmake --build "$PROJECT_ROOT/build/dev-check"
    CPP_BINARY="$PROJECT_ROOT/build/dev-check/src/cpp/smart_home_controller"
else
    cmake -S "$PROJECT_ROOT/src/cpp" -B "$PROJECT_ROOT/src/cpp/build" -G Ninja
    cmake --build "$PROJECT_ROOT/src/cpp/build"
    CPP_BINARY="$PROJECT_ROOT/src/cpp/build/smart_home_controller"
fi

echo
echo "Running C++ starter..."
"$CPP_BINARY"

echo
echo "Running C++ tests..."
ctest --test-dir "$PROJECT_ROOT/build/dev-check" --output-on-failure
