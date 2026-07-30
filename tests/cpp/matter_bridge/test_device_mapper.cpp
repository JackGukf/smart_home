#include <gtest/gtest.h>
#include "matter_bridge/DeviceMapper.h"

TEST(DeviceMapper, LightSwitchNonDimmable) {
    auto spec = MapCategoryToMatter("light_switch", false);
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffLight);
    EXPECT_FALSE(spec.read_only);
}

// Dimmable light switches are deliberately still mapped to OnOffLight.
// DimmableLight requires the LevelControl cluster, which the bridge does not
// implement; advertising it makes Apple Home attempt to dim and show
// "No response". Revisit only when LevelControl is actually supported.
TEST(DeviceMapper, LightSwitchDimmableStillMapsToOnOffLight) {
    auto spec = MapCategoryToMatter("light_switch", true);
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, OutletMapsToPlugInUnit) {
    auto spec = MapCategoryToMatter("outlet");
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffPlugInUnit);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, TuyaSwitchMapsToPlugInUnit) {
    auto spec = MapCategoryToMatter("tuya_switch");
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffPlugInUnit);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, TuyaSensorMapsToTempSensor) {
    auto spec = MapCategoryToMatter("tuya_sensor");
    EXPECT_EQ(spec.type, MatterDeviceType::TemperatureSensor);
    EXPECT_TRUE(spec.read_only);
}

TEST(DeviceMapper, SceneMapsToVirtualOnOffLight) {
    auto spec = MapCategoryToMatter("scene");
    EXPECT_EQ(spec.type, MatterDeviceType::VirtualOnOffLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, VirtualSwitchMapsToVirtualOnOffLight) {
    auto spec = MapCategoryToMatter("virtual_switch");
    EXPECT_EQ(spec.type, MatterDeviceType::VirtualOnOffLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, UnknownCategoryReturnsUnknown) {
    auto spec = MapCategoryToMatter("bogus_category");
    EXPECT_EQ(spec.type, MatterDeviceType::Unknown);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, DeviceTypeName) {
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::OnOffLight), "OnOffLight");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::DimmableLight), "DimmableLight");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::OnOffPlugInUnit), "OnOffPlugInUnit");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::TemperatureSensor), "TemperatureSensor");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::HumiditySensor), "HumiditySensor");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::VirtualOnOffLight), "VirtualOnOffLight");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::Unknown), "Unknown");
}
