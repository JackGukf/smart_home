#include <gtest/gtest.h>

#include "controller.hpp"

TEST(ControllerTest, StartupMessageNamesOrangePiController) {
    EXPECT_EQ(startup_message(), "Smart Home Orange Pi 6 Plus controller starting...");
}
