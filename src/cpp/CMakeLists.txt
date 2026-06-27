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

    find_package(CURL REQUIRED)

    add_executable(matter_bridge_sync_client_tests
        ../../tests/cpp/matter_bridge/test_sync_client.cpp
        matter_bridge/SyncClient.cpp
    )
    target_include_directories(matter_bridge_sync_client_tests
        PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${CMAKE_SOURCE_DIR}
    )
    target_link_libraries(matter_bridge_sync_client_tests
        PRIVATE GTest::gtest_main CURL::libcurl
    )
    gtest_discover_tests(matter_bridge_sync_client_tests)

    # BridgeDevice tests: all sources are #include-ed by the test translation unit,
    # so only the test file itself is listed here. CHIP SDK globals are stubbed
    # inside test_bridge_device.cpp; no real SDK linkage is required.
    add_executable(matter_bridge_device_tests
        ../../tests/cpp/matter_bridge/test_bridge_device.cpp
    )
    target_include_directories(matter_bridge_device_tests
        PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}
            ${CMAKE_SOURCE_DIR}
    )
    target_link_libraries(matter_bridge_device_tests
        PRIVATE GTest::gtest_main
    )
    gtest_discover_tests(matter_bridge_device_tests)
endif()
