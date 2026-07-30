# Cross-compile toolchain for the Orange Pi 6 Plus (Cix P1 / CD8180).
#
# Verified on the board: Ubuntu 24.04 ARM64, 12 cores, Armv9.2-A big.LITTLE
# (Cortex-A720, CPU part 0xd81 + Cortex-A520, CPU part 0xd80).
#
# -mcpu=cortex-a720 / cortex-a520 need GCC 14+, and the dev container ships the
# Ubuntu 22.04 aarch64 cross-compiler (GCC 11), so the exact core flags are not
# available here. Probe for the best -march the cross-compiler actually accepts
# instead of hardcoding one, and fall back to a baseline that always runs.
# Override with -DORANGEPI6_ARCH_FLAGS=... to pin a specific set.

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

if(NOT DEFINED ORANGEPI6_ARCH_FLAGS)
    set(_orangepi6_arch_candidates
        "-march=armv9-a"            # GCC 12+; matches the Armv9.2-A cores
        "-march=armv8.4-a+crypto"   # GCC 8+; closest widely available baseline
        "-march=armv8.2-a+crypto"
        ""                          # generic armv8-a
    )
    set(_orangepi6_selected "")
    foreach(_candidate IN LISTS _orangepi6_arch_candidates)
        if(_candidate STREQUAL "")
            break()
        endif()
        execute_process(
            COMMAND ${CMAKE_C_COMPILER} ${_candidate} -E -x c -
            INPUT_FILE /dev/null
            RESULT_VARIABLE _orangepi6_probe
            OUTPUT_QUIET
            ERROR_QUIET
        )
        if(_orangepi6_probe EQUAL 0)
            set(_orangepi6_selected "${_candidate}")
            break()
        endif()
    endforeach()
    set(ORANGEPI6_ARCH_FLAGS "${_orangepi6_selected}" CACHE STRING
        "Architecture flags for the Orange Pi 6 Plus cross build")
endif()

if(NOT ORANGEPI6_ARCH_FLAGS STREQUAL "")
    string(APPEND CMAKE_C_FLAGS_INIT " ${ORANGEPI6_ARCH_FLAGS}")
    string(APPEND CMAKE_CXX_FLAGS_INIT " ${ORANGEPI6_ARCH_FLAGS}")
endif()

set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
