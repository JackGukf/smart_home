#include "DeviceMapper.h"

MatterDeviceSpec MapCategoryToMatter(const std::string& category, bool dimmable) {
    if (category == "light_switch") {
        // DimmableLight requires the LevelControl cluster which we don't implement.
        // Apple Home tries to dim and gets "No response" without it, so always use OnOffLight.
        (void)dimmable;
        return {MatterDeviceType::OnOffLight, false};
    }
    if (category == "outlet" || category == "tuya_switch") {
        return {MatterDeviceType::OnOffPlugInUnit, false};
    }
    if (category == "tuya_sensor") {
        return {MatterDeviceType::TemperatureSensor, true};
    }
    if (category == "scene" || category == "virtual_switch") {
        return {MatterDeviceType::VirtualOnOffLight, false};
    }
    return {MatterDeviceType::Unknown, false};
}

const char* MatterDeviceTypeName(MatterDeviceType type) {
    switch (type) {
        case MatterDeviceType::OnOffLight:        return "OnOffLight";
        case MatterDeviceType::DimmableLight:     return "DimmableLight";
        case MatterDeviceType::OnOffPlugInUnit:   return "OnOffPlugInUnit";
        case MatterDeviceType::TemperatureSensor: return "TemperatureSensor";
        case MatterDeviceType::HumiditySensor:    return "HumiditySensor";
        case MatterDeviceType::VirtualOnOffLight: return "VirtualOnOffLight";
        case MatterDeviceType::Unknown:            return "Unknown";
    }
    return "Unknown";
}
