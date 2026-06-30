// test_bridge_device.cpp
// Tests for BridgeDevice — the Matter dynamic endpoint wrapper.
//
// Strategy: BridgeDevice.cpp calls CHIP SDK global functions
// (emberAfSetDynamicEndpoint, emberAfClearDynamicEndpoint, etc.).
// We provide stub implementations of those globals here so the test binary
// links without the real CHIP SDK.

#include <gtest/gtest.h>
#include <cstdint>
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <vector>

// ─── Minimal CHIP SDK type stubs ─────────────────────────────────────────────

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

using CHIP_ERROR = int;
static constexpr CHIP_ERROR CHIP_NO_ERROR = 0;

struct EmberAfDeviceType {
    chip::DeviceTypeId device_type;
    uint8_t            revision;
};

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

#define ZAP_ATTRIBUTE_MASK(mask) 0
#define ZAP_CLUSTER_MASK(mask)   0

// ─── Cluster / Attribute IDs ──────────────────────────────────────────────────
// Match the real ZCL values (BridgeDevice.cpp uses these via its own #defines
// that alias the SDK namespace constants; we provide equivalent numeric values).

#define ZCL_ON_OFF_CLUSTER_ID                              0x0006u
#define ZCL_ON_OFF_ATTRIBUTE_ID                            0x0000u
#define ZCL_DESCRIPTOR_CLUSTER_ID                          0x001Du
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID    0x0039u
#define ZCL_PRODUCT_NAME_ATTRIBUTE_ID                      0x0003u
#define ZCL_NODE_LABEL_ATTRIBUTE_ID                        0x0005u
#define ZCL_REACHABLE_ATTRIBUTE_ID                         0x0011u
#define ZCL_DEVICE_LIST_ATTRIBUTE_ID                       0x0000u
#define ZCL_SERVER_LIST_ATTRIBUTE_ID                       0x0001u
#define ZCL_CLIENT_LIST_ATTRIBUTE_ID                       0x0002u
#define ZCL_PARTS_LIST_ATTRIBUTE_ID                        0x0003u
#define ZCL_TEMP_MEASUREMENT_CLUSTER_ID                    0x0402u
#define ZCL_TEMP_MEASURED_VALUE_ATTRIBUTE_ID               0x0000u
#define ZCL_TEMP_MIN_MEASURED_VALUE_ATTRIBUTE_ID           0x0001u
#define ZCL_TEMP_MAX_MEASURED_VALUE_ATTRIBUTE_ID           0x0002u

#define ZCL_BOOLEAN_ATTRIBUTE_TYPE   0x10
#define ZCL_CHAR_STRING_ATTRIBUTE_TYPE 0x42
#define ZCL_INT16S_ATTRIBUTE_TYPE    0x29
#define ZCL_ARRAY_ATTRIBUTE_TYPE     0x48

#define BOOLEAN     ZCL_BOOLEAN_ATTRIBUTE_TYPE
#define CHAR_STRING ZCL_CHAR_STRING_ATTRIBUTE_TYPE
#define INT16S      ZCL_INT16S_ATTRIBUTE_TYPE
#define ARRAY       ZCL_ARRAY_ATTRIBUTE_TYPE

template <typename T, size_t N>
constexpr size_t ArraySize(T (&)[N]) { return N; }

static const chip::CommandId OnOffIncomingCommands[] = { 0x00, 0x01, 0x02, 0xFFFF'FFFFu };

// ─── DECLARE_DYNAMIC_* macros ─────────────────────────────────────────────────

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

// ─── Stub CHIP SDK global functions ──────────────────────────────────────────

struct ChipStubs {
    // emberAfSetDynamicEndpoint
    uint8_t          last_set_dynamic_index = 0;
    chip::EndpointId last_set_endpoint_id   = 0;
    CHIP_ERROR       set_dynamic_return     = CHIP_NO_ERROR;
    bool             set_dynamic_called     = false;

    // emberAfClearDynamicEndpoint
    uint8_t          last_clear_index = 0;
    bool             clear_called     = false;

    // emberAfWriteAttribute (kept for completeness; not called by current code paths)
    struct WriteCall {
        chip::EndpointId  endpoint;
        chip::ClusterId   cluster;
        chip::AttributeId attribute;
        uint8_t           value_byte;
        uint8_t           attr_type;
    };
    std::vector<WriteCall> write_calls;

    // MatterReportingAttributeChangeCallback
    struct ReportCall {
        chip::EndpointId  endpoint;
        chip::ClusterId   cluster;
        chip::AttributeId attribute;
    };
    std::vector<ReportCall> reporting_calls;

    // emberAfEndpointEnableDisable
    struct EnableDisableCall {
        chip::EndpointId endpoint;
        bool             enabled;
    };
    std::vector<EnableDisableCall> enable_disable_calls;

    void Reset() {
        last_set_dynamic_index = 0;
        last_set_endpoint_id   = 0;
        set_dynamic_return     = CHIP_NO_ERROR;
        set_dynamic_called     = false;
        last_clear_index       = 0;
        clear_called           = false;
        write_calls.clear();
        reporting_calls.clear();
        enable_disable_calls.clear();
    }
};

static ChipStubs gStubs;

// 6-param version: BridgeDevice.cpp passes parentEndpointId=1 as the 6th arg
// so that bridged devices appear under the aggregator endpoint's PartsList.
CHIP_ERROR emberAfSetDynamicEndpoint(
    uint8_t                             dynamic_index,
    chip::EndpointId                    endpoint_id,
    const EmberAfEndpointType*          /*ep_type*/,
    chip::Span<chip::DataVersion>       /*data_versions*/,
    chip::Span<const EmberAfDeviceType> /*dev_types*/,
    chip::EndpointId                    /*parentEndpointId*/)
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

// emberAfEndpointEnableDisable is called by Unregister() before Clear to avoid
// "endpoint already exists" errors on re-registration.
void emberAfEndpointEnableDisable(chip::EndpointId endpoint, bool enabled) {
    gStubs.enable_disable_calls.push_back({endpoint, enabled});
}

using EmberAfStatus = uint8_t;
static constexpr EmberAfStatus EMBER_ZCL_STATUS_SUCCESS = 0x00;

EmberAfStatus emberAfWriteAttribute(
    chip::EndpointId  endpoint,
    chip::ClusterId   cluster,
    chip::AttributeId attribute,
    uint8_t*          value,
    uint8_t           attr_type)
{
    gStubs.write_calls.push_back({
        endpoint, cluster, attribute,
        value ? static_cast<uint8_t>(*value) : uint8_t{0},
        attr_type
    });
    return EMBER_ZCL_STATUS_SUCCESS;
}

// MatterReportingAttributeChangeCallback marks an attribute dirty for
// subscription delivery.  Called by UpdateOnOff (when value changes) and
// SetReachable (always).
void MatterReportingAttributeChangeCallback(chip::EndpointId  endpoint,
                                             chip::ClusterId   cluster,
                                             chip::AttributeId attribute) {
    gStubs.reporting_calls.push_back({endpoint, cluster, attribute});
}

// ─── Pull in production source ────────────────────────────────────────────────

#define CHIP_SDK_STUB_TYPES_DEFINED
#include "src/cpp/matter_bridge/DeviceMapper.h"
#include "src/cpp/matter_bridge/SyncClient.h"
#include "src/cpp/matter_bridge/BridgeDevice.h"
#include "src/cpp/matter_bridge/BridgeDevice.cpp"
#include "src/cpp/matter_bridge/DeviceMapper.cpp"

// ─── Helper ──────────────────────────────────────────────────────────────────

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

// ─── Test fixture ─────────────────────────────────────────────────────────────

class BridgeDeviceTest : public ::testing::Test {
protected:
    void SetUp()    override { gStubs.Reset(); }
    void TearDown() override { gStubs.Reset(); }
};

// ─── Constructor / accessor tests ────────────────────────────────────────────

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

TEST_F(BridgeDeviceTest, GetTypeDimmableFallsBackToOnOffLight) {
    // DimmableLight requires LevelControl cluster which is not implemented.
    // DeviceMapper intentionally maps dimmable light_switch to OnOffLight.
    DeviceInfo info = MakeDevice("dev1", "light_switch", true);
    BridgeDevice dev(0, 2, info);
    EXPECT_EQ(dev.GetType(), MatterDeviceType::OnOffLight);
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
    gStubs.set_dynamic_return = 1;
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    CHIP_ERROR err = dev.Register();
    EXPECT_NE(err, CHIP_NO_ERROR);
    EXPECT_EQ(BridgeDeviceLookup(2), nullptr);
}

TEST_F(BridgeDeviceTest, UnregisterCallsClearDynamicEndpoint) {
    DeviceInfo info = MakeDevice("dev1", "outlet");
    {
        BridgeDevice dev(1, 3, info);
        dev.Register();
        gStubs.Reset();
        dev.Unregister();
        EXPECT_TRUE(gStubs.clear_called);
        EXPECT_EQ(gStubs.last_clear_index, 1u);
        EXPECT_EQ(BridgeDeviceLookup(3), nullptr);
    }
    // destructor fires — Unregister is a no-op (already unregistered)
}

TEST_F(BridgeDeviceTest, UnregisterCallsEndpointDisable) {
    DeviceInfo info = MakeDevice("dev1", "outlet");
    BridgeDevice dev(1, 3, info);
    dev.Register();
    gStubs.Reset();
    dev.Unregister();
    ASSERT_EQ(gStubs.enable_disable_calls.size(), 1u);
    EXPECT_EQ(gStubs.enable_disable_calls[0].endpoint, 3u);
    EXPECT_FALSE(gStubs.enable_disable_calls[0].enabled);
    dev.Unregister(); // idempotent — must not crash or call again
    EXPECT_EQ(gStubs.enable_disable_calls.size(), 1u);
}

TEST_F(BridgeDeviceTest, DestructorCallsUnregister) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    {
        BridgeDevice dev(0, 2, info);
        dev.Register();
        EXPECT_NE(BridgeDeviceLookup(2), nullptr);
    } // destructor fires
    EXPECT_EQ(BridgeDeviceLookup(2), nullptr);
}

// ─── UpdateOnOff tests ───────────────────────────────────────────────────────
// UpdateOnOff stores the on/off state locally and calls
// MatterReportingAttributeChangeCallback only when the value changes.
// (The ZCL server's internal emberAfWriteAttribute/MatterPostAttributeChangeCallback
// fires when called from an InvokeCommand; UpdateOnOff is for poll-based sync.)

TEST_F(BridgeDeviceTest, UpdateOnOffSetsOnState) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    bool changed = dev.UpdateOnOff(true);
    EXPECT_TRUE(changed);           // initial value is -1, so first call always changes
    EXPECT_EQ(dev.GetLastOnValue(), 1);
}

TEST_F(BridgeDeviceTest, UpdateOnOffSetsOffState) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    bool changed = dev.UpdateOnOff(false);
    EXPECT_TRUE(changed);
    EXPECT_EQ(dev.GetLastOnValue(), 0);
}

TEST_F(BridgeDeviceTest, UpdateOnOffReturnsFalseWhenUnchanged) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.UpdateOnOff(true);
    bool changed = dev.UpdateOnOff(true); // same value
    EXPECT_FALSE(changed);
}

TEST_F(BridgeDeviceTest, UpdateOnOffReportsAttributeWhenChanged) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.Register();
    gStubs.reporting_calls.clear();

    dev.UpdateOnOff(true);

    ASSERT_EQ(gStubs.reporting_calls.size(), 1u);
    EXPECT_EQ(gStubs.reporting_calls[0].endpoint,  2u);
    EXPECT_EQ(gStubs.reporting_calls[0].cluster,
              static_cast<chip::ClusterId>(ZCL_ON_OFF_CLUSTER_ID));
    EXPECT_EQ(gStubs.reporting_calls[0].attribute,
              static_cast<chip::AttributeId>(ZCL_ON_OFF_ATTRIBUTE_ID));
}

TEST_F(BridgeDeviceTest, UpdateOnOffDoesNotReportWhenUnchanged) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.UpdateOnOff(true);
    gStubs.reporting_calls.clear();

    dev.UpdateOnOff(true); // same value — must NOT call MatterReportingAttributeChangeCallback
    EXPECT_EQ(gStubs.reporting_calls.size(), 0u);
}

TEST_F(BridgeDeviceTest, UpdateOnOffDoesNotCallEmberAfWriteAttribute) {
    // State is stored locally; emberAfWriteAttribute is NOT called.
    // The ZCL server writes the attribute internally when handling InvokeCommands.
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.UpdateOnOff(true);
    dev.UpdateOnOff(false);
    EXPECT_EQ(gStubs.write_calls.size(), 0u);
}

// notify=false is what HandleOnOffCommand (the ZCL external-attribute-write
// path) passes: the SDK's emAfWriteAttribute() already calls
// MatterReportingAttributeChangeCallback itself right after that callback
// returns, so UpdateOnOff must NOT also notify — doing so double-bumps the
// cluster DataVersion and double-queues the report for one logical change.
TEST_F(BridgeDeviceTest, UpdateOnOffSkipsReportWhenNotifyFalseEvenIfChanged) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.Register();
    gStubs.reporting_calls.clear();

    bool changed = dev.UpdateOnOff(true, /*notify=*/false);

    EXPECT_TRUE(changed);
    EXPECT_EQ(gStubs.reporting_calls.size(), 0u);
    EXPECT_EQ(dev.GetLastOnValue(), 1);
}

// ─── SetReachable tests ──────────────────────────────────────────────────────

TEST_F(BridgeDeviceTest, SetReachableTrueUpdatesState) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.SetReachable(true);
    EXPECT_TRUE(dev.GetReachable());
}

TEST_F(BridgeDeviceTest, SetReachableFalseUpdatesState) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    dev.SetReachable(false);
    EXPECT_FALSE(dev.GetReachable());
}

TEST_F(BridgeDeviceTest, SetReachableReportsAttributeChange) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    gStubs.reporting_calls.clear();
    dev.SetReachable(true);
    ASSERT_EQ(gStubs.reporting_calls.size(), 1u);
    EXPECT_EQ(gStubs.reporting_calls[0].cluster,
              static_cast<chip::ClusterId>(ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID));
    EXPECT_EQ(gStubs.reporting_calls[0].attribute,
              static_cast<chip::AttributeId>(ZCL_REACHABLE_ATTRIBUTE_ID));
}

// ─── OnAttributeChanged tests ────────────────────────────────────────────────
// OnAttributeChanged is intentionally a no-op. Command dispatch happens in
// main.cpp's emberAfExternalAttributeWriteCallback (the ZCL server writes the
// attribute and we intercept it there). By the time OnAttributeChanged fires
// via MatterPostAttributeChangeCallback, the HTTP command is already in flight.

TEST_F(BridgeDeviceTest, OnAttributeChangedOnOffIsNoOp) {
    DeviceInfo info = MakeDevice("kasa:1.2.3.4", "light_switch");
    BridgeDevice dev(0, 2, info);
    uint8_t value = 1;
    EXPECT_NO_FATAL_FAILURE(
        dev.OnAttributeChanged(ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value)
    );
    // No side effects
    EXPECT_EQ(gStubs.write_calls.size(),     0u);
    EXPECT_EQ(gStubs.reporting_calls.size(), 0u);
}

TEST_F(BridgeDeviceTest, OnAttributeChangedUnknownClusterIsNoOp) {
    DeviceInfo info = MakeDevice("dev1", "light_switch");
    BridgeDevice dev(0, 2, info);
    uint8_t value = 1;
    EXPECT_NO_FATAL_FAILURE(
        dev.OnAttributeChanged(0xDEADu, ZCL_ON_OFF_ATTRIBUTE_ID, &value)
    );
    EXPECT_EQ(gStubs.write_calls.size(), 0u);
}

TEST_F(BridgeDeviceTest, OnAttributeChangedTemperatureSensorIsNoOp) {
    DeviceInfo info = MakeDevice("sensor1", "tuya_sensor");
    BridgeDevice dev(0, 2, info);
    uint8_t value = 1;
    EXPECT_NO_FATAL_FAILURE(
        dev.OnAttributeChanged(ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value)
    );
    EXPECT_EQ(gStubs.write_calls.size(), 0u);
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
// HandleAttributeChanged calls dev->OnAttributeChanged which is a no-op.
// The actual command dispatch occurs in main.cpp's
// emberAfExternalAttributeWriteCallback (not testable here without the SDK).

TEST_F(BridgeDeviceTest, HandleAttributeChangedDispatchesToRegisteredDevice) {
    DeviceInfo info = MakeDevice("kasa:5.6.7.8", "light_switch");
    BridgeDevice dev(0, 4, info);
    dev.Register();

    uint8_t value = 1;
    EXPECT_NO_FATAL_FAILURE(
        HandleAttributeChanged(4, ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value)
    );
    // OnAttributeChanged is a no-op — no write or report side effects
    EXPECT_EQ(gStubs.write_calls.size(),     0u);
    EXPECT_EQ(gStubs.reporting_calls.size(), 0u);
}

TEST_F(BridgeDeviceTest, HandleAttributeChangedSafeForUnknownEndpoint) {
    uint8_t value = 1;
    EXPECT_NO_FATAL_FAILURE(
        HandleAttributeChanged(999, ZCL_ON_OFF_CLUSTER_ID, ZCL_ON_OFF_ATTRIBUTE_ID, &value)
    );
}
