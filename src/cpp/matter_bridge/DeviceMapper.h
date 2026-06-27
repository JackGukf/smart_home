#pragma once
#include <string>

enum class MatterDeviceType {
    OnOffLight,
    DimmableLight,
    OnOffPlugInUnit,
    TemperatureSensor,
    HumiditySensor,
    VirtualOnOffLight,
    Unknown,
};

struct MatterDeviceSpec {
    MatterDeviceType type;
    bool read_only;
};

MatterDeviceSpec MapCategoryToMatter(const std::string& category, bool dimmable = false);
const char* MatterDeviceTypeName(MatterDeviceType type);
