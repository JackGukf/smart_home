#pragma once

// Use heap-based (unlimited) packet buffer pool on Linux.
// Default static pool of 15 is exhausted when Apple Home (HomePod) subscribes
// to all bridge endpoints simultaneously, causing "No memory" errors and
// marking every device "No response" even though commands work fine.
// Setting to 0 enables malloc-based allocation on non-LwIP platforms.
#define CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE 0
