#pragma once

// Use heap-based (unlimited) packet buffer pool on Linux.
// Default static pool of 15 is exhausted when Apple Home (HomePod) subscribes
// to all bridge endpoints simultaneously, causing "No memory" errors and
// marking every device "No response" even though commands work fine.
// Setting to 0 enables malloc-based allocation on non-LwIP platforms.
#define CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE 0

// Apple Home issues wildcard subscriptions after commissioning. The default
// Linux packet-buffer capacity (1583 bytes) is too small for bridge-common's
// generated attribute reports and causes CHIP_ERROR_NO_MEMORY while encoding
// ReportData, after which Home marks the accessory No Response. 9050 is the
// socket-platform capacity used by CHIP's standalone/python example configs.
#define CHIP_SYSTEM_CONFIG_PACKETBUFFER_CAPACITY_MAX 9050
