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

// Distinct display identity. The SDK defaults these to "TEST_VENDOR" /
// "TEST_PRODUCT", which is also what the office Stick S3 advertises -- during
// the 2026-09-04 investigation node 1 was misidentified as this bridge for
// exactly that reason, and the wrong conclusion reached the runbook. Naming the
// bridge makes the two tellable apart in Apple Home, in Home Assistant's device
// registry, and in matter-server's node list.
//
// Names only. CHIP_DEVICE_CONFIG_DEVICE_VENDOR_ID / _PRODUCT_ID must stay at
// the example DAC's 0xFFF1 / 0x8001, or attestation fails and commissioning
// stops at "Pairing failed" -- see Bug 3 in docs/matter-bridge.md.
#define CHIP_DEVICE_CONFIG_DEVICE_VENDOR_NAME  "Smart Home AI"
#define CHIP_DEVICE_CONFIG_DEVICE_PRODUCT_NAME "Dashboard Bridge"
