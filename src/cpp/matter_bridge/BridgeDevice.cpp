// When compiled as part of the CHIP SDK GN build, include real SDK headers so
// chip:: types and ember AF macros are defined.  When the test driver
// (test_bridge_device.cpp) #includes this file directly it defines
// CHIP_SDK_STUB_TYPES_DEFINED first, supplying its own lightweight stubs instead.
#ifndef CHIP_SDK_STUB_TYPES_DEFINED
#include <app-common/zap-generated/ids/Attributes.h>
#include <app-common/zap-generated/ids/Clusters.h>
#include <app/reporting/reporting.h>
#include <app/util/af.h>
#include <app/util/attribute-storage.h>

// CHIP SDK v1.x uses C++ namespaces rather than old-style ZCL_* C macros.
// Provide aliases so the same BridgeDevice.cpp compiles against either the
// real SDK (here) or the minimal stubs in test_bridge_device.cpp.
namespace _bdns = chip::app::Clusters;
#define ZCL_ON_OFF_CLUSTER_ID                            _bdns::OnOff::Id
#define ZCL_DESCRIPTOR_CLUSTER_ID                        _bdns::Descriptor::Id
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID  _bdns::BridgedDeviceBasicInformation::Id
#define ZCL_TEMP_MEASUREMENT_CLUSTER_ID                  _bdns::TemperatureMeasurement::Id

#define ZCL_ON_OFF_ATTRIBUTE_ID \
    _bdns::OnOff::Attributes::OnOff::Id
#define ZCL_PRODUCT_NAME_ATTRIBUTE_ID \
    _bdns::BridgedDeviceBasicInformation::Attributes::ProductName::Id
#define ZCL_NODE_LABEL_ATTRIBUTE_ID \
    _bdns::BridgedDeviceBasicInformation::Attributes::NodeLabel::Id
#define ZCL_REACHABLE_ATTRIBUTE_ID \
    _bdns::BridgedDeviceBasicInformation::Attributes::Reachable::Id
#define ZCL_DEVICE_LIST_ATTRIBUTE_ID \
    _bdns::Descriptor::Attributes::DeviceTypeList::Id
#define ZCL_SERVER_LIST_ATTRIBUTE_ID \
    _bdns::Descriptor::Attributes::ServerList::Id
#define ZCL_CLIENT_LIST_ATTRIBUTE_ID \
    _bdns::Descriptor::Attributes::ClientList::Id
#define ZCL_PARTS_LIST_ATTRIBUTE_ID \
    _bdns::Descriptor::Attributes::PartsList::Id
#define ZCL_TEMP_MEASURED_VALUE_ATTRIBUTE_ID \
    _bdns::TemperatureMeasurement::Attributes::MeasuredValue::Id
#define ZCL_TEMP_MIN_MEASURED_VALUE_ATTRIBUTE_ID \
    _bdns::TemperatureMeasurement::Attributes::MinMeasuredValue::Id
#define ZCL_TEMP_MAX_MEASURED_VALUE_ATTRIBUTE_ID \
    _bdns::TemperatureMeasurement::Attributes::MaxMeasuredValue::Id

// On-off accepted commands: Off=0x00, On=0x01, Toggle=0x02
static const chip::CommandId OnOffIncomingCommands[] = {
    0x00, 0x01, 0x02, chip::kInvalidCommandId
};
#endif

#include "BridgeDevice.h"
#include <map>
#include <mutex>

// ─── Global endpoint registry ──────────────────────────────────────────────────

static std::mutex                                  gRegistryMutex;
static std::map<chip::EndpointId, BridgeDevice*>  gEndpointRegistry;

void BridgeDeviceRegisterInstance(chip::EndpointId id, BridgeDevice* dev) {
    std::lock_guard<std::mutex> lock(gRegistryMutex);
    gEndpointRegistry[id] = dev;
}

void BridgeDeviceUnregisterInstance(chip::EndpointId id) {
    std::lock_guard<std::mutex> lock(gRegistryMutex);
    gEndpointRegistry.erase(id);
}

BridgeDevice* BridgeDeviceLookup(chip::EndpointId id) {
    std::lock_guard<std::mutex> lock(gRegistryMutex);
    auto it = gEndpointRegistry.find(id);
    return (it != gEndpointRegistry.end()) ? it->second : nullptr;
}

// ─── Static cluster/attribute tables ──────────────────────────────────────────
// These MUST be static (or global) — the CHIP stack holds raw pointers to them.

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sOnOffAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_ON_OFF_ATTRIBUTE_ID, BOOLEAN, 1, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sBridgedBasicAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_PRODUCT_NAME_ATTRIBUTE_ID, CHAR_STRING, kProductNameMaxSize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_NODE_LABEL_ATTRIBUTE_ID, CHAR_STRING, kNodeLabelMaxSize,
                              ZAP_ATTRIBUTE_MASK(WRITABLE)),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_REACHABLE_ATTRIBUTE_ID, BOOLEAN, 1, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sDescriptorAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_DEVICE_LIST_ATTRIBUTE_ID,  ARRAY, kDescriptorArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_SERVER_LIST_ATTRIBUTE_ID,  ARRAY, kDescriptorArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_CLIENT_LIST_ATTRIBUTE_ID,  ARRAY, kDescriptorArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_PARTS_LIST_ATTRIBUTE_ID,   ARRAY, kDescriptorArraySize, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sTempAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_TEMP_MEASURED_VALUE_ATTRIBUTE_ID,     INT16S, 2, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_TEMP_MIN_MEASURED_VALUE_ATTRIBUTE_ID, INT16S, 2, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_TEMP_MAX_MEASURED_VALUE_ATTRIBUTE_ID, INT16S, 2, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

// Cluster list: OnOff Light / virtual switch / plug-in unit (all share same clusters)
DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(sOnOffClusters)
    DECLARE_DYNAMIC_CLUSTER(ZCL_ON_OFF_CLUSTER_ID,
                            sOnOffAttribs,
                            ZAP_CLUSTER_MASK(SERVER),
                            OnOffIncomingCommands, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_DESCRIPTOR_CLUSTER_ID,
                            sDescriptorAttribs,
                            ZAP_CLUSTER_MASK(SERVER),
                            nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID,
                            sBridgedBasicAttribs,
                            ZAP_CLUSTER_MASK(SERVER),
                            nullptr, nullptr),
DECLARE_DYNAMIC_CLUSTER_LIST_END;

// Cluster list: Temperature Sensor (read-only)
DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(sTempClusters)
    DECLARE_DYNAMIC_CLUSTER(ZCL_TEMP_MEASUREMENT_CLUSTER_ID,
                            sTempAttribs,
                            ZAP_CLUSTER_MASK(SERVER),
                            nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_DESCRIPTOR_CLUSTER_ID,
                            sDescriptorAttribs,
                            ZAP_CLUSTER_MASK(SERVER),
                            nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID,
                            sBridgedBasicAttribs,
                            ZAP_CLUSTER_MASK(SERVER),
                            nullptr, nullptr),
DECLARE_DYNAMIC_CLUSTER_LIST_END;

// Endpoint type descriptors (one per Matter device type we support)
DECLARE_DYNAMIC_ENDPOINT(sOnOffEndpointType, sOnOffClusters);
DECLARE_DYNAMIC_ENDPOINT(sTempEndpointType,  sTempClusters);

// ─── Device type lists per Matter type ────────────────────────────────────────

static const EmberAfDeviceType kOnOffLightTypes[] = {
    {kDeviceTypeIdOnOffLight, 1}, {kDeviceTypeIdBridgedNode, 1}
};
static const EmberAfDeviceType kPlugInUnitTypes[] = {
    {kDeviceTypeIdOnOffPlugIn, 1}, {kDeviceTypeIdBridgedNode, 1}
};
static const EmberAfDeviceType kTempSensorTypes[] = {
    {kDeviceTypeIdTempSensor, 1}, {kDeviceTypeIdBridgedNode, 1}
};

// ─── BridgeDevice implementation ──────────────────────────────────────────────

BridgeDevice::BridgeDevice(uint8_t dynamic_index,
                           chip::EndpointId endpoint_id,
                           const DeviceInfo& info)
    : device_id_(info.device_id),
      name_(info.name),
      dynamic_index_(dynamic_index),
      endpoint_id_(endpoint_id),
      spec_(MapCategoryToMatter(info.category, info.dimmable))
{}

BridgeDevice::~BridgeDevice() {
    Unregister();
}

CHIP_ERROR BridgeDevice::Register() {
    const EmberAfEndpointType* ep_type         = &sOnOffEndpointType;
    const EmberAfDeviceType*   dev_types        = kOnOffLightTypes;
    size_t                     dev_types_count  = ArraySize(kOnOffLightTypes);
    size_t                     cluster_count    = ArraySize(sOnOffClusters);

    if (spec_.type == MatterDeviceType::OnOffPlugInUnit) {
        dev_types       = kPlugInUnitTypes;
        dev_types_count = ArraySize(kPlugInUnitTypes);
        // ep_type and cluster_count remain sOnOffEndpointType / sOnOffClusters
    } else if (spec_.type == MatterDeviceType::TemperatureSensor) {
        ep_type         = &sTempEndpointType;
        dev_types       = kTempSensorTypes;
        dev_types_count = ArraySize(kTempSensorTypes);
        cluster_count   = ArraySize(sTempClusters);
    }
    // DimmableLight, VirtualOnOffLight → treated same as OnOffLight

    // parentEndpointId = 1: registers this device under the bridge aggregator
    // endpoint so it appears in ep=1's PartsList. Without this, Apple Home
    // cannot discover bridged devices (PartsList stays empty).
    CHIP_ERROR err = emberAfSetDynamicEndpoint(
        dynamic_index_,
        endpoint_id_,
        ep_type,
        chip::Span<chip::DataVersion>(data_versions_, cluster_count),
        chip::Span<const EmberAfDeviceType>(dev_types, dev_types_count),
        /* parentEndpointId = */ 1
    );

    if (err == CHIP_NO_ERROR) {
        registered_ = true;
        BridgeDeviceRegisterInstance(endpoint_id_, this);
        // NodeLabel and Reachable are served directly by
        // emberAfExternalAttributeReadCallback — no emberAfWriteAttribute needed.
    }
    return err;
}

void BridgeDevice::Unregister() {
    if (!registered_) return;
    registered_ = false;
    BridgeDeviceUnregisterInstance(endpoint_id_);
    // Must disable before clearing — without this the SDK slot stays marked
    // "occupied" and the next emberAfSetDynamicEndpoint on the same index
    // fails with "Trying to add dynamic endpoint that already exists".
    emberAfEndpointEnableDisable(endpoint_id_, false);
    emberAfClearDynamicEndpoint(dynamic_index_);
}

bool BridgeDevice::UpdateOnOff(bool on, bool notify) {
    int8_t new_val = on ? 1 : 0;
    bool changed = (last_on_value_ != new_val);
    last_on_value_ = new_val;
    // notify=false from HandleOnOffCommand (ZCL external-attribute-write path):
    // emAfWriteAttribute() in the SDK calls MatterReportingAttributeChangeCallback
    // itself right after emberAfExternalAttributeWriteCallback() returns, so firing
    // it here too would bump the cluster DataVersion twice for one logical change.
    // notify=true (default) from ApplyOnOffUpdate/RegisterDevices: nothing else in
    // those paths notifies the subscription engine, so we must do it here.
    if (changed && notify) {
        MatterReportingAttributeChangeCallback(endpoint_id_,
                                               ZCL_ON_OFF_CLUSTER_ID,
                                               ZCL_ON_OFF_ATTRIBUTE_ID);
    }
    return changed;
}

void BridgeDevice::SetReachable(bool reachable) {
    reachable_ = reachable;
    MatterReportingAttributeChangeCallback(endpoint_id_,
                                           ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID,
                                           ZCL_REACHABLE_ATTRIBUTE_ID);
}

void BridgeDevice::OnAttributeChanged(chip::ClusterId   cluster_id,
                                      chip::AttributeId attribute_id,
                                      uint8_t*          value) {
    // The ZCL on-off-server fires MatterPostAttributeChangeCallback after writing
    // the attribute.  By the time this runs, HandleOnOffCommand (dispatched from
    // emberAfExternalAttributeWriteCallback) has already queued the HTTP call on
    // a background thread.  Nothing to do here.
    (void)cluster_id;
    (void)attribute_id;
    (void)value;
}

// ─── Global callback ──────────────────────────────────────────────────────────

void HandleAttributeChanged(chip::EndpointId  endpoint_id,
                            chip::ClusterId   cluster_id,
                            chip::AttributeId attribute_id,
                            uint8_t*          value) {
    BridgeDevice* dev = BridgeDeviceLookup(endpoint_id);
    if (dev) {
        dev->OnAttributeChanged(cluster_id, attribute_id, value);
    }
}
