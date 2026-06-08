#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-$HOME/workspace/smart-home-rpi4}"

echo "Checking tools..."
command -v gcc
command -v g++
command -v cmake
command -v python3

echo
echo "Running Python starter..."
python3 "$PROJECT_ROOT/src/python/controller.py"

echo
echo "Configuring C++ starter..."
cmake -S "$PROJECT_ROOT/src/cpp" -B "$PROJECT_ROOT/src/cpp/build" -G Ninja
cmake --build "$PROJECT_ROOT/src/cpp/build"

echo
echo "Running C++ starter..."
"$PROJECT_ROOT/src/cpp/build/smart_home_controller"
