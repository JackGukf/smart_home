// test_bridge_device.cpp
// Tests for BridgeDevice — the Matter dynamic endpoint wrapper.
//
// Strategy: BridgeDevice.cpp calls CHIP SDK global functions
// (emberAfSetDynamicEndpoint, emberAfClearDynamicEndpoint, emberAfWriteAttribute).
// We provide stub implementations of those globals here so that the test binary
// links without the real CHIP SDK. We also define the minimal CHIP SDK types
// needed for compilation.

#include <gtest/gtest.h>
#include <cstdint>
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <vector>

// ─── Minimal CHIP SDK type stubs ────────────────────────────────────────────
// These satisfy BridgeDevice.h's use of chip:: types without needing real headers.

namespace chip {
    using EndpointId   = uint16_t;
    using ClusterId    = uint32_t;
    using AttributeId  = uint32_t;
    using DeviceTypeId = uint16_t;
    using DataVersion  = uint32_t;
    using CommandId    = uint32_t;

    template <typename T>
    struct Span {
        Span(T* data, size_t size) : data_(data), size_(size) {}
        T*     data_;
        size_t size_;
    };
} // namespace chip

// CHIP_ERROR type
using CHIP_ERROR = int;
static constexpr CHIP_ERROR CHIP_NO_ERROR = 0;

// EmberAfDeviceType
struct EmberAfDeviceType {
    chip::DeviceTypeId device_type;
    uint8_t            revision;
};

// Attribute and cluster descriptor stubs — BridgeDevice.cpp uses
// DECLARE_DYNAMIC_* macros which expand to these.
struct EmberAfAttributeMetadata {
    chip::AttributeId attributeId;
    uint8_t           attributeType;
    uint16_t          size;
    uint8_t           mask;
};

struct EmberAfCluster {
    chip::ClusterId              clusterId;
    EmberAfAttributeMetadata*    attributes;
    uint16_t                     attributeCount;
    uint8_t                      mask;
    const chip::CommandId*       acceptedCommandList;
    const chip::CommandId*       generatedCommandList;
};

struct EmberAfEndpointType {
    EmberAfCluster* cluster;
    uint8_t         clusterCount;
    uint16_t        endpointSize;
};

// ZAP attribute mask / cluster mask helpers used by DECLARE_DYNAMIC_* macros
#define ZAP_ATTRIBUTE_MASK(mask) 0
#define ZAP_CLUSTER_MASK(mask)   0

// Cluster / Attribute IDs referenced in BridgeDevice.cpp
#define ZCL_ON_OFF_CLUSTER_ID                              0x0006
#define ZCL_ON_OFF_ATTRIBUTE_ID                            0x0000
#define ZCL_DESCRIPTOR_CLUSTER_ID                          0x001D
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID    0x0039
#define ZCL_NODE_LABEL_ATTRIBUTE_ID                        0x0005
#define ZCL_REACHABLE_ATTRIBUTE_ID                         0x0011
#define ZCL_DEVICE_LIST_ATTRIBUTE_ID                       0x0000
#define ZCL_SERVER_LIST_ATTRIBUTE_ID                       0x0001
#define ZCL_CLIENT_LIST_ATTRIBUTE_ID                       0x0002
#define ZCL_PARTS_LIST_ATTRIBUTE_ID                        0x0003
#define ZCL_TEMP_MEASUREMENT_CLUSTER_ID                    0x0402
#define ZCL_TEMP_MEASURED_VALUE_ATTRIBUTE_ID               0x0000
#define ZCL_TEMP_MIN_MEASURED_VALUE_ATTRIBUTE_ID           0x0001
#define ZCL_TEMP_MAX_MEASURED_VALUE_ATTRIBUTE_ID           0x0002

// Attribute types
#define ZCL_BOOLEAN_ATTRIBUTE_TYPE  0x10
#define ZCL_CHAR_STRING_ATTRIBUTE_TYPE 0x42
#define ZCL_INT16S_ATTRIBUTE_TYPE   0x29
#define ZCL_ARRAY_ATTRIBUTE_TYPE    0x48

// Convenience shortcuts matching the macro spelling in BridgeDevice.cpp
#define BOOLEAN    ZCL_BOOLEAN_ATTRIBUTE_TYPE
#define CHAR_STRING ZCL_CHAR_STRING_ATTRIBUTE_TYPE
#define INT16S     ZCL_INT16S_ATTRIBUTE_TYPE
#define ARRAY      ZCL_ARRAY_ATTRIBUTE_TYPE

// ArraySize helper
template <typename T, size_t N>
constexpr size_t ArraySize(T (&)[N]) { return N; }

// on-off server incoming commands sentinel
static const chip::CommandId OnOffIncomingCommands[] = { 0x00, 0x01, 0x02, 0xFFFF'FFFF };

// ─── DECLARE_DYNAMIC_* macros (minimal stubs matching CHIP SDK spelling) ────

#define DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(name) \
    static EmberAfAttributeMetadata name[] = {

#define DECLARE_DYNAMIC_ATTRIBUTE(attrId, type, size, mask) \
    { (attrId), (type), (size), (uint8_t)(mask) }

#define DECLARE_DYNAMIC_ATTRIBUTE_LIST_END() \
    };

#define DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(name) \
    static EmberAfCluster name[] = {

#define DECLARE_DYNAMIC_CLUSTER(clusterId, attribs, mask, inCmds, outCmds) \
    { (clusterId), (attribs), (uint16_t)(sizeof(attribs)/sizeof(attribs[0])), (mask), (inCmds), (outCmds) }

#define DECLARE_DYNAMIC_CLUSTER_LIST_END \
    };

#define DECLARE_DYNAMIC_ENDPOINT(name, clusters) \
    static EmberAfEndpointType name = { (clusters), (uint8_t)(sizeof(clusters)/sizeof(clusters[0])), 0 }

// ─── Stub CHIP SDK global function implementations ──────────────────────────
// These replace the real CHIP SDK functions for unit-test purposes.
// Each records its most recent call so tests can verify behavior.

struct ChipStubs {
    // emberAfSetDynamicEndpoint
    uint8_t            last_set_dynamic_index = 0;
    chip::EndpointId   last_set_endpoint_id   = 0;
    CHIP_ERROR         set_dynamic_return      = CHIP_NO_ERROR;
    bool               set_dynamic_called      = false;

    // emberAfClearDynamicEndpoint
    uint8_t            last_clear_index = 0;
    bool               clear_called     = false;

    // emberAfWriteAttribute
    struct WriteCall {
        chip::EndpointId  endpoint;
        chip::ClusterId   cluster;
        chip::AttributeId attribute;
        uint8_t           value_byte; // first byte of the value buffer
        uint8_t           attr_type;
    };
    std::vector<WriteCall> write_calls;

    void Reset() {
        last_set_dynamic_index = 0;
        last_set_endpoint_id   = 0;
        set_dynamic_return     = CHIP_NO_ERROR;
        set_dynamic_called     = false;
        last_clear_index       = 0;
        clear_called           = false;
        write_calls.clear();
    }
};

static ChipStubs gStubs;

// The real CHIP_ERROR signature for emberAfSetDynamicEndpoint varies by SDK
// version. We match what BridgeDevice.cpp expects.
CHIP_ERROR emberAfSetDynamicEndpoint(
    uint8_t                                   dynamic_index,
    chip::EndpointId                          endpoint_id,
    const EmberAfEndpointType*                /*ep_type*/,
    chip::Span<chip::DataVersion>             /*data_versions*/,
    chip::Span<const EmberAfDeviceType>       /*dev_types*/)
{
    gStubs.last_set_dynamic_index = dynamic_index;
    gStubs.last_set_endpoint_id   = endpoint_id;
    gStubs.set_dynamic_called     = true;
    return gStubs.set_dynamic_return;
}

void emberAfClearDynamicEndpoint(uint8_t dynamic_index) {
    gStubs.last_clear_index = dynamic_index;
    gStubs.clear_called     = true;
}

// emberAfWriteAttribute signature from CHIP SDK attribute-storage.h
using EmberAfStatus = uint8_t;
static constexpr EmberAfStatus EMBER_ZCL_STATUS_SUCCESS = 0x00;

EmberAfStatus emberAfWriteAttribute(
    chip::EndpointId  endpoint,
    chip::ClusterId   cluster,
    chip::AttributeId attribute,
    uint8_t*          value,
    uint8_t           attr_type)
{
    gStubs.write_calls.push_back({endpoint, cluster, attribute, value ? static_cast<uint8_t>(*value) : uint8_t{0}, attr_type});
    return EMBER_ZCL_STATUS_SUCCESS;
}

// ─── Pull in the production source ──────────────────────────────────────────
// We include the headers and .cpp directly so that the single test binary
// exercises the real implementation with our stub globals.

#include "src/cpp/matter_bridge/DeviceMapper.h"
#include "src/cpp/matter_bridge/SyncClient.h"
#include "src/cpp/matter_bridge/BridgeDevice.h"
#include "src/cpp/matter_bridge/BridgeDevice.cpp"

// Also include DeviceMapper.cpp for MapCategoryToMatter()
#include "src/cpp/matter_bridge/DeviceMapper.cpp"

// ─── Helper to build a DeviceInfo ───────────────────────────────────────────
static DeviceInfo MakeDevice(const std::string& id,
                              const std::string& category,
                              bool dimmable = false) {
    DeviceInfo d;
    d.device_id = id;
    d.name      = "Test " + id;
    d.room      = "Living Room";
    d.category  = category;
    d.dimmable  = dimmable;
    return d;
}

// ─── Test fixtures ───────────────────────────────────────────────────────────

class BridgeDeviceTest : public ::testing::Test {
protected:
    void SetUp() override {
        gStubs.Reset();
    }
    void TearDown() override {
        // Registry may hold a pointer; clear stubs but registry self-cleans via Unregister
        gStubs.Reset();
    }
};

// ─── Constructor / accessor tests ───────────────────────────────────────────

TEST_F(BridgeDeviceTest, ConstructorStoresDeviceId) {
    DeviceInfo info = MakeDevice("kasa:192.168.1.10", "light_switch");
    BridgeDevice dev(0, 2, info);
    EXPECT_EQ(dev.GetDeviceId(), "kasa:192.168.1.10");
}

TEST_F(BridgeDeviceTest, ConstructorStoresEndpointId) {
    DeviceInfo info = MakeDevice("dev1", "outlet");
    BridgeDevice dev(1, 3, info);
    EXPECT_EQ(dev.GetEndpointId(), 3u);
}

TEST_F(BridgeDeviceTest, GetTypeLightSwitch) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    EXPECT_EQ(dev.GetType(), MatterDeviceType::OnOffLight);
}

TEST_F(BridgeDeviceTest, GetTypeDimmable) {
    DeviceInfo info = MakeDevice("dev1", "light_switch", true);
    BridgeDevice dev(0, 2, info);
    EXPECT_EQ(dev.GetType(), MatterDeviceType::DimmableLight);
}

TEST_F(BridgeDeviceTest, GetTypeOutlet) {
    DeviceInfo info = MakeDevice("dev1", "outlet");
    BridgeDevice dev(0, 2, info);
    EXPECT_EQ(dev.GetType(), MatterDeviceType::OnOffPlugInUnit);
}

TEST_F(BridgeDeviceTest, GetTypeTemperatureSensor) {
    DeviceInfo info = MakeDevice("sensor1", "tuya_sensor");
    BridgeDevice dev(0, 2, info);
    EXPECT_EQ(dev.GetType(), MatterDeviceType::TemperatureSensor);
}

// ─── Register / Unregister tests ─────────────────────────────────────────────

TEST_F(BridgeDeviceTest, RegisterCallsSetDynamicEndpoint) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    CHIP_ERROR err = dev.Register();
    EXPECT_EQ(err, CHIP_NO_ERROR);
    EXPECT_TRUE(gStubs.set_dynamic_called);
    EXPECT_EQ(gStubs.last_set_dynamic_index, 0u);
    EXPECT_EQ(gStubs.last_set_endpoint_id,   2u);
}

TEST_F(BridgeDeviceTest, RegisterAddsToGlobalRegistry) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.Register();
    EXPECT_EQ(BridgeDeviceLookup(2), &dev);
}

TEST_F(BridgeDeviceTest, RegisterReturnsErrorWhenChipFails) {
    gStubs.set_dynamic_return = 1; // simulate failure
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    CHIP_ERROR err = dev.Register();
    EXPECT_NE(err, CHIP_NO_ERROR);
    // On failure, device should NOT be in registry
    EXPECT_EQ(BridgeDeviceLookup(2), nullptr);
}

TEST_F(BridgeDeviceTest, UnregisterCallsClearDynamicEndpoint) {
    DeviceInfo info = MakeDevice("dev1", "outlet");
    {
        BridgeDevice dev(1, 3, info);
        dev.Register();
        gStubs.Reset(); // clear register call tracking
        dev.Unregister();
        EXPECT_TRUE(gStubs.clear_called);
        EXPECT_EQ(gStubs.last_clear_index, 1u);
        EXPECT_EQ(BridgeDeviceLookup(3), nullptr);
    }
    // destructor calls Unregister again — should be idempotent (already cleared)
}

TEST_F(BridgeDeviceTest, DestructorCallsUnregister) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    {
        BridgeDevice dev(0, 2, info);
        dev.Register();
        EXPECT_NE(BridgeDeviceLookup(2), nullptr);
    } // destructor fires here
    EXPECT_EQ(BridgeDeviceLookup(2), nullptr);
}

// ─── UpdateOnOff tests ───────────────────────────────────────────────────────

TEST_F(BridgeDeviceTest, UpdateOnOffWritesTrueValue) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.UpdateOnOff(true);
    ASSERT_EQ(gStubs.write_calls.size(), 1u);
    auto& c = gStubs.write_calls[0];
    EXPECT_EQ(c.endpoint,  2u);
    EXPECT_EQ(c.cluster,   static_cast<chip::ClusterId>(ZCL_ON_OFF_CLUSTER_ID));
    EXPECT_EQ(c.attribute, static_cast<chip::AttributeId>(ZCL_ON_OFF_ATTRIBUTE_ID));
    EXPECT_EQ(c.value_byte, 1u);
}

TEST_F(BridgeDeviceTest, UpdateOnOffWritesFalseValue) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.UpdateOnOff(false);
    ASSERT_EQ(gStubs.write_calls.size(), 1u);
    EXPECT_EQ(gStubs.write_calls[0].value_byte, 0u);
}

// ─── SetReachable tests ──────────────────────────────────────────────────────

TEST_F(BridgeDeviceTest, SetReachableTrueWritesCorrectCluster) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.SetReachable(true);
    ASSERT_EQ(gStubs.write_calls.size(), 1u);
    auto& c = gStubs.write_calls[0];
    EXPECT_EQ(c.cluster,   static_cast<chip::ClusterId>(ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID));
    EXPECT_EQ(c.attribute, static_cast<chip::AttributeId>(ZCL_REACHABLE_ATTRIBUTE_ID));
    EXPECT_EQ(c.value_byte, 1u);
}

TEST_F(BridgeDeviceTest, SetReachableFalseWritesZero) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.SetReachable(false);
    ASSERT_EQ(gStubs.write_calls.size(), 1u);
    EXPECT_EQ(gStubs.write_calls[0].value_byte, 0u);
}

// ─── OnAttributeChanged tests ────────────────────────────────────────────────

TEST_F(BridgeDeviceTest, OnAttributeChangedOnOffOnSendsCommand) {
    DeviceInfo info = MakeDevice("kasa:1.2.3.4", "light_switch");
    BridgeDevice dev(0, 2, info);

    std::vector<std::pair<std::string,std::string>> commands;
    SetCommandSender([&](const std::string& id, const std::string& cmd) {
        commands.push_back({id, cmd});
    });

    uint8_t value = 1; // on
    dev.OnAttributeChanged(ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value);

    ASSERT_EQ(commands.size(), 1u);
    EXPECT_EQ(commands[0].first,  "kasa:1.2.3.4");
    EXPECT_EQ(commands[0].second, "on");
}

TEST_F(BridgeDeviceTest, OnAttributeChangedOnOffOffSendsCommand) {
    DeviceInfo info = MakeDevice("kasa:1.2.3.4", "light_switch");
    BridgeDevice dev(0, 2, info);

    std::vector<std::pair<std::string,std::string>> commands;
    SetCommandSender([&](const std::string& id, const std::string& cmd) {
        commands.push_back({id, cmd});
    });

    uint8_t value = 0; // off
    dev.OnAttributeChanged(ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value);

    ASSERT_EQ(commands.size(), 1u);
    EXPECT_EQ(commands[0].second, "off");
}

TEST_F(BridgeDeviceTest, OnAttributeChangedReadOnlyDeviceDoesNotSendCommand) {
    // tuya_sensor is read_only; attribute changes should be ignored
    DeviceInfo info = MakeDevice("sensor1", "tuya_sensor");
    BridgeDevice dev(0, 2, info);

    std::vector<std::pair<std::string,std::string>> commands;
    SetCommandSender([&](const std::string& id, const std::string& cmd) {
        commands.push_back({id, cmd});
    });

    uint8_t value = 1;
    dev.OnAttributeChanged(ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value);

    EXPECT_TRUE(commands.empty());
}

TEST_F(BridgeDeviceTest, OnAttributeChangedUnknownClusterDoesNotSendCommand) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);

    std::vector<std::pair<std::string,std::string>> commands;
    SetCommandSender([&](const std::string& id, const std::string& cmd) {
        commands.push_back({id, cmd});
    });

    uint8_t value = 1;
    // Wrong cluster ID
    dev.OnAttributeChanged(0xDEAD, ZCL_ON_OFF_ATTRIBUTE_ID, &value);
    EXPECT_TRUE(commands.empty());
}

// ─── Global registry tests ───────────────────────────────────────────────────

TEST_F(BridgeDeviceTest, RegistryLookupReturnsNullForMissingId) {
    EXPECT_EQ(BridgeDeviceLookup(99), nullptr);
}

TEST_F(BridgeDeviceTest, RegistrySupportsMultipleDevices) {
    DeviceInfo info1 = MakeDevice("dev1", "light_switch");
    DeviceInfo info2 = MakeDevice("dev2", "outlet");
    BridgeDevice dev1(0, 2, info1);
    BridgeDevice dev2(1, 3, info2);
    dev1.Register();
    dev2.Register();

    EXPECT_EQ(BridgeDeviceLookup(2), &dev1);
    EXPECT_EQ(BridgeDeviceLookup(3), &dev2);
}

TEST_F(BridgeDeviceTest, UnregisterRemovesOnlyTargetDevice) {
    DeviceInfo info1 = MakeDevice("dev1", "light_switch");
    DeviceInfo info2 = MakeDevice("dev2", "outlet");
    BridgeDevice dev1(0, 2, info1);
    BridgeDevice dev2(1, 3, info2);
    dev1.Register();
    dev2.Register();

    dev1.Unregister();

    EXPECT_EQ(BridgeDeviceLookup(2), nullptr);
    EXPECT_EQ(BridgeDeviceLookup(3), &dev2);

    dev2.Unregister();
}

// ─── HandleAttributeChanged global function tests ─────────────────────────────

TEST_F(BridgeDeviceTest, HandleAttributeChangedDispatchesToRegisteredDevice) {
    DeviceInfo info = MakeDevice("kasa:5.6.7.8", "light_switch");
    BridgeDevice dev(0, 4, info);
    dev.Register();

    std::string received_id;
    std::string received_cmd;
    SetCommandSender([&](const std::string& id, const std::string& cmd) {
        received_id  = id;
        received_cmd = cmd;
    });

    uint8_t value = 1;
    HandleAttributeChanged(4, ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value);

    EXPECT_EQ(received_id,  "kasa:5.6.7.8");
    EXPECT_EQ(received_cmd, "on");
}

TEST_F(BridgeDeviceTest, HandleAttributeChangedSafeForUnknownEndpoint) {
    // No device registered for endpoint 999 — must not crash.
    SetCommandSender([](const std::string&, const std::string&) {});
    uint8_t value = 1;
    EXPECT_NO_FATAL_FAILURE(
        HandleAttributeChanged(999, ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value)
    );
}
