# Cross-compile toolchain for the Raspberry Pi 4 (Cortex-A72, Armv8-A).
#
# SECONDARY TARGET. The primary board is the Orange Pi 6 Plus — see
# orangepi6-aarch64.cmake. This file is kept so existing Raspberry Pi 4
# installations still build; select it with the docker-rpi4-release preset or
# scripts/build-orangepi6.sh --board rpi4.

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
