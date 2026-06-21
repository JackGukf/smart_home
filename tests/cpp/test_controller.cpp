#include <gtest/gtest.h>

#include "controller.hpp"

TEST(ControllerTest, StartupMessageNamesRaspberryPiController) {
    EXPECT_EQ(startup_message(), "Smart Home Raspberry Pi 4 controller starting...");
}
