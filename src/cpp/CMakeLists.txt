cmake_minimum_required(VERSION 3.16)
project(smart_home_rpi4 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(smart_home_controller
    main.cpp
)
