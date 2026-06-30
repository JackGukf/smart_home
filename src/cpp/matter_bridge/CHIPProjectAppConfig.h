#pragma once

// Dynamic endpoint count for the bridge aggregator.
// Must match or exceed the number of bridged devices.
#define CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT 16

// Pull in system-layer overrides (CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE etc.).
#include <CHIPProjectConfig.h>
