#pragma once
#include "DeviceMapper.h"
#include "SyncClient.h"

#include <cstdint>
#include <string>

// CHIP SDK headers — only available after CHIP SDK bootstrap (Task 6).
// When compiling without the real SDK (e.g. unit tests) these are satisfied by
// stub definitions provided by the test file before this header is included.
//
// In a full SDK build (build-matter-bridge.sh) these resolve to real SDK headers:
//   #include <app/clusters/on-off-server/on-off-server.h>
//   #include <app/util/attribute-storage.h>
//   #include <app/util/endpoint-config-api.h>
//   #include <app-common/zap-generated/ids/Attributes.h>
//   #include <app-common/zap-generated/ids/Clusters.h>

// Matter device type IDs (from the Matter specification)
static constexpr chip::DeviceTypeId kDeviceTypeIdBridgedNode    = 0x0013;
static constexpr chip::DeviceTypeId kDeviceTypeIdOnOffLight     = 0x0100;
static constexpr chip::DeviceTypeId kDeviceTypeIdDimmableLight  = 0x0101;
static constexpr chip::DeviceTypeId kDeviceTypeIdOnOffPlugIn    = 0x010A;
static constexpr chip::DeviceTypeId kDeviceTypeIdTempSensor     = 0x0302;
static constexpr chip::DeviceTypeId kDeviceTypeIdHumiditySensor = 0x0307;

static constexpr uint16_t kNodeLabelMaxSize    = 64;
static constexpr uint16_t kProductNameMaxSize  = 64;
static constexpr uint16_t kDescriptorArraySize = 254;

class BridgeDevice {
public:
    // dynamic_index: 0-based slot in the dynamic endpoint array (max ~252)
    // endpoint_id:   Matter endpoint ID (must be >= DYNAMIC_ENDPOINT_START, e.g. 2)
    // info:          device metadata from SyncClient::FetchDevices()
    BridgeDevice(uint8_t dynamic_index,
                 chip::EndpointId endpoint_id,
                 const DeviceInfo& info);
    ~BridgeDevice();

    // Disallow copy; allow move
    BridgeDevice(const BridgeDevice&) = delete;
    BridgeDevice& operator=(const BridgeDevice&) = delete;
    BridgeDevice(BridgeDevice&&) = default;

    // Register this device's dynamic endpoint with the CHIP stack.
    // Call from the Matter event loop thread.
    CHIP_ERROR Register();

    // Remove this device's dynamic endpoint from the CHIP stack.
    // Also called by the destructor.
    void Unregister();

    // Update Matter OnOff attribute (endpoint_id_, OnOff cluster, OnOff attribute).
    // Returns true if the value changed, false if it was already the same (no-op).
    // notify: pass false when called from the ZCL external-attribute-write path
    // (HandleOnOffCommand) — the SDK's emAfWriteAttribute() already calls
    // MatterReportingAttributeChangeCallback() itself once that write returns, so
    // notifying here too double-bumps the cluster DataVersion and double-queues the
    // report for the same change. Pass true (default) for poll-driven/initial sync
    // (ApplyOnOffUpdate, RegisterDevices), where nothing else fires the notification.
    // Call from Matter event loop thread.
    bool UpdateOnOff(bool on, bool notify = true);

    // Mark the device as reachable/unreachable in BridgedDeviceBasicInformation.
    void SetReachable(bool reachable);

    const std::string& GetDeviceId()  const { return device_id_; }
    const std::string& GetName()      const { return name_; }
    chip::EndpointId   GetEndpointId() const { return endpoint_id_; }
    MatterDeviceType   GetType()       const { return spec_.type; }
    int8_t             GetLastOnValue() const { return last_on_value_; }
    bool               GetReachable()  const { return reachable_; }

    // Called by HandleAttributeChanged() when the ZCL layer writes to this device's endpoint.
    void OnAttributeChanged(chip::ClusterId cluster_id,
                            chip::AttributeId attribute_id,
                            uint8_t* value);

private:
    std::string      device_id_;
    std::string      name_;
    uint8_t          dynamic_index_;
    chip::EndpointId endpoint_id_;
    MatterDeviceSpec spec_;

    bool             registered_  = false;
    bool             reachable_   = false;

    // Tracks on/off state; -1 = never set, 0 = off, 1 = on.
    // Served directly by emberAfExternalAttributeReadCallback.
    int8_t           last_on_value_ = -1;

    // Per-instance data versions (one per cluster; arrays must outlive the endpoint).
    // 4 to accommodate future DimmableLight (adds LevelControl cluster)
    static constexpr size_t kMaxClusters = 4;
    chip::DataVersion data_versions_[kMaxClusters] = {};
};

// ─── Global endpoint registry ─────────────────────────────────────────────────
// Maps endpoint_id → BridgeDevice*.
// Used by MatterPostAttributeChangeCallback (in main.cpp) to dispatch attribute changes.

void        BridgeDeviceRegisterInstance(chip::EndpointId id, BridgeDevice* dev);
void        BridgeDeviceUnregisterInstance(chip::EndpointId id);
BridgeDevice* BridgeDeviceLookup(chip::EndpointId id);

// ─── Global callback ──────────────────────────────────────────────────────────
// main.cpp's MatterPostAttributeChangeCallback should delegate here.
void HandleAttributeChanged(chip::EndpointId  endpoint_id,
                            chip::ClusterId   cluster_id,
                            chip::AttributeId attribute_id,
                            uint8_t*          value);
