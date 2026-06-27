cmake_minimum_required(VERSION 3.16)
project(smart_home_rpi4_cpp LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(smart_home_core
    controller.cpp
)

target_include_directories(smart_home_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
)

add_executable(smart_home_controller
    main.cpp
)

target_link_libraries(smart_home_controller
    PRIVATE
        smart_home_core
)

if(BUILD_TESTING)
    find_package(GTest REQUIRED)

    add_executable(smart_home_cpp_tests
        ../../tests/cpp/test_controller.cpp
    )

    target_link_libraries(smart_home_cpp_tests
        PRIVATE
            smart_home_core
            GTest::gtest_main
    )

    include(GoogleTest)
    gtest_discover_tests(smart_home_cpp_tests)

    add_executable(matter_bridge_mapper_tests
        ../../tests/cpp/matter_bridge/test_device_mapper.cpp
        matter_bridge/DeviceMapper.cpp
    )
    target_include_directories(matter_bridge_mapper_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    target_link_libraries(matter_bridge_mapper_tests PRIVATE GTest::gtest_main)
    gtest_discover_tests(matter_bridge_mapper_tests)
endif()
