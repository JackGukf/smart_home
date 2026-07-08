/*
 * Matter Bridge main.cpp
 *
 * Initialises the CHIP stack, fetches devices from the Python bridge sync API,
 * registers them as dynamic Matter endpoints, then runs a background poll loop
 * that keeps Apple Home in sync with real device state.
 *
 * Build: scripts/build-matter-bridge.sh (inside Docker dev container)
 */
#include <AppMain.h>
#include <app-common/zap-generated/cluster-objects.h>
#include <app/CommandHandler.h>
#include <app/CommandHandlerInterface.h>
#include <app/ConcreteCommandPath.h>
#include <app/InteractionModelEngine.h>
#include <app/reporting/reporting.h>
#include <app/server/Server.h>
#include <credentials/examples/DeviceAttestationCredsExample.h>
#include <lib/core/ErrorStr.h>
#include <lib/support/ZclString.h>
#include <platform/CHIPDeviceLayer.h>
#include <platform/Linux/NetworkCommissioningDriver.h>
#include <system/SystemConfig.h>

// Bridge-specific headers must come after SDK headers so chip:: types are resolved
#include "BridgeDevice.h"
#include "DeviceMapper.h"
#include "SyncClient.h"

// SDK bridge-app includes (for Action/EndpointListInfo types expected by bridged-actions-stub.cpp)
#include "Device.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

using namespace chip;
using namespace chip::app;
using namespace chip::DeviceLayer;

// ── Constants ─────────────────────────────────────────────────────────────────

static_assert(CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE == 0,
              "Matter bridge must use heap packet buffers for Apple Home wildcard subscriptions");
static_assert(CHIP_SYSTEM_CONFIG_PACKETBUFFER_CAPACITY_MAX >= 9050,
              "Matter bridge packet buffer capacity must fit Apple Home wildcard subscription reports");

static constexpr uint16_t kDevicePollIntervalSeconds   = 10;
static constexpr uint16_t kDeviceRescanIntervalSeconds = 60;
// Endpoint 0 = root node, endpoint 1 = aggregator/bridge.
// ep=2 is reserved by the bridge-app ZAP static config (example light with
// LevelControl) — starting at 3 avoids that LevelControl data leaking into our
// OnOffLight devices and confusing Apple Home into treating them as DimmableLight.
static constexpr EndpointId kDynamicEndpointStart = 3;
static constexpr uint8_t    kMaxDynamicDevices    = 4;

// ── Globals ───────────────────────────────────────────────────────────────────

// Base URL: prefer BRIDGE_SYNC_URL env var, fall back to localhost.
static const char* GetBridgeSyncUrl() {
    const char* env = std::getenv("BRIDGE_SYNC_URL");
    return (env && env[0] != '\0') ? env : "http://localhost:8000";
}

// gSyncClient is initialised in main() after we know the URL.
static SyncClient*  gSyncClient = nullptr;

// gDevices is only written by the Matter event loop thread (initial registration)
// or the poll thread. Protected by gDevicesMutex for poll-thread access.
static std::mutex                              gDevicesMutex;
static std::vector<std::unique_ptr<BridgeDevice>> gDevices;
static std::atomic<bool>                       gRunning{true};

// Condition variable used to wake the poll thread on shutdown instead of
// waiting out the full kDevicePollIntervalSeconds sleep.
static std::condition_variable gShutdownCv;
static std::mutex              gShutdownMutex;

// ── Helpers ───────────────────────────────────────────────────────────────────

// Parse a string state value to bool ("true" or "1" → true).
static bool ParseBoolState(const std::string& val) {
    return val == "true" || val == "1";
}

// ── Signal handler ─────────────────────────────────────────────────────────────

static void HandleSignal(int /*sig*/) {
    gRunning = false;
    gShutdownCv.notify_all();
    chip::DeviceLayer::PlatformMgr().StopEventLoopTask();
}

// ── CHIP SDK callbacks ────────────────────────────────────────────────────────

// Called by the CHIP stack when an attribute is written.
// Delegates to HandleAttributeChanged() for logging; the actual command is
// dispatched via HandleOnOffCommand on a background thread, not here.
void MatterPostAttributeChangeCallback(const ConcreteAttributePath& path,
                                       uint8_t  /*type*/,
                                       uint16_t /*size*/,
                                       uint8_t* value) {
    ChipLogDetail(AppServer, "ATTR_CHANGE ep=%u cluster=0x%04X attr=0x%04X val=%u",
                  path.mEndpointId, (unsigned)path.mClusterId,
                  (unsigned)path.mAttributeId, value ? (unsigned)*value : 0);
    HandleAttributeChanged(path.mEndpointId, path.mClusterId,
                           path.mAttributeId, value);
}

// Access-control stubs required by the CHIP dynamic endpoint layer.
bool emberAfAttributeReadAccessCallback(EndpointId, ClusterId, AttributeId) {
    return true;
}
bool emberAfAttributeWriteAccessCallback(EndpointId, ClusterId, AttributeId) {
    return true;
}

using IMStatus = chip::Protocols::InteractionModel::Status;
using namespace chip::app::Clusters;

// ── OnOff command dispatch ────────────────────────────────────────────────────
// The ZCL on-off cluster server plugin is NOT part of this build: the ZAP
// pruning in build-matter-bridge.sh removes the last static OnOff cluster
// instance, so codegen drops the on-off-server (that's also why main.cpp stubs
// MatterOnOffPluginServerInitCallback).  InvokeCommands for OnOff are therefore
// handled by DynamicOnOffCommandHandler below, registered with the Interaction
// Model engine.  Because the handler marks commands handled,
// DispatchSingleClusterCommand/emAfWriteAttribute never run for commands — the
// handler itself must update state AND notify the reporting engine
// (HandleOnOffCommand with notify_subscribers=true).
//
// Direct WriteAttribute requests still go through
// emberAfExternalAttributeWriteCallback, where the SDK fires the reporting
// callback for us (notify_subscribers=false on that path).

// notify_subscribers: pass false ONLY from emberAfExternalAttributeWriteCallback
// — there the SDK's emAfWriteAttribute() fires MatterReportingAttributeChangeCallback
// itself right after the callback returns, so notifying here too would double-bump
// the cluster DataVersion and double-queue the same report (confirmed by reading
// src/app/util/attribute-table.cpp's emAfWriteAttribute()).
// Pass true from DynamicOnOffCommandHandler::InvokeCommand — that path marks the
// command handled, so DispatchSingleClusterCommand/emAfWriteAttribute never run
// (see InteractionModelEngine::DispatchCommand) and nothing else bumps the
// DataVersion or queues the report. Without it, Apple Home never receives a
// subscription report confirming its own On/Off command: the tile reverts after
// a few seconds and the accessory eventually shows "No Response".
static void HandleOnOffCommand(EndpointId endpoint, bool new_on, bool notify_subscribers) {
    BridgeDevice* dev = BridgeDeviceLookup(endpoint);
    if (!dev) return;
    const std::string device_id = dev->GetDeviceId();
    ChipLogDetail(AppServer, "OnOff cmd ep=%u → %s (dev=%s)",
                  endpoint, new_on ? "on" : "off", device_id.c_str());

    // Returns false when the value didn't change (e.g. "On" sent to a device
    // that is already on).  Skip the HTTP call in that case.
    if (!dev->UpdateOnOff(new_on, /*notify=*/notify_subscribers)) return;

    // The actual HTTP call to the Python bridge must NOT block the Matter event
    // loop — doing so prevents the InvokeResponse from being sent quickly and
    // causes Apple Home to timeout the command and show "not available".
    std::thread([device_id, new_on]() {
        if (gSyncClient) {
            try {
                gSyncClient->SendCommand(device_id, new_on ? "on" : "off");
            } catch (const SyncClientError& e) {
                ChipLogError(AppServer, "SendCommand failed: %s", e.what());
            }
        }
    }).detach();
}

class DynamicOnOffCommandHandler : public CommandHandlerInterface
{
public:
    DynamicOnOffCommandHandler() : CommandHandlerInterface(Optional<EndpointId>::Missing(), OnOff::Id) {}

    void InvokeCommand(HandlerContext & ctx) override
    {
        const EndpointId endpoint = ctx.mRequestPath.mEndpointId;
        BridgeDevice* dev = BridgeDeviceLookup(endpoint);
        if (!dev)
        {
            ctx.mCommandHandler.AddStatus(ctx.mRequestPath, IMStatus::UnsupportedEndpoint);
            ctx.SetCommandHandled();
            return;
        }

        switch (ctx.mRequestPath.mCommandId)
        {
        case OnOff::Commands::Off::Id:
            HandleOnOffCommand(endpoint, false, /*notify_subscribers=*/true);
            ctx.mCommandHandler.AddStatus(ctx.mRequestPath, IMStatus::Success);
            ctx.SetCommandHandled();
            return;
        case OnOff::Commands::On::Id:
            HandleOnOffCommand(endpoint, true, /*notify_subscribers=*/true);
            ctx.mCommandHandler.AddStatus(ctx.mRequestPath, IMStatus::Success);
            ctx.SetCommandHandled();
            return;
        case OnOff::Commands::Toggle::Id:
            HandleOnOffCommand(endpoint, dev->GetLastOnValue() != 1, /*notify_subscribers=*/true);
            ctx.mCommandHandler.AddStatus(ctx.mRequestPath, IMStatus::Success);
            ctx.SetCommandHandled();
            return;
        default:
            ctx.mCommandHandler.AddStatus(ctx.mRequestPath, IMStatus::UnsupportedCommand);
            ctx.SetCommandHandled();
            return;
        }
    }

    CHIP_ERROR EnumerateAcceptedCommands(const ConcreteClusterPath & cluster,
                                         CommandIdCallback callback,
                                         void * context) override
    {
        if (!BridgeDeviceLookup(cluster.mEndpointId))
        {
            return CHIP_ERROR_NOT_IMPLEMENTED;
        }
        for (CommandId command : { OnOff::Commands::Off::Id, OnOff::Commands::On::Id, OnOff::Commands::Toggle::Id })
        {
            if (callback(command, context) == Loop::Break)
            {
                break;
            }
        }
        return CHIP_NO_ERROR;
    }

    CHIP_ERROR EnumerateGeneratedCommands(const ConcreteClusterPath & cluster,
                                          CommandIdCallback callback,
                                          void * context) override
    {
        if (!BridgeDeviceLookup(cluster.mEndpointId))
        {
            return CHIP_ERROR_NOT_IMPLEMENTED;
        }
        (void) callback;
        (void) context;
        return CHIP_NO_ERROR;
    }
};

static DynamicOnOffCommandHandler gDynamicOnOffCommandHandler;

// ── External attribute callbacks ──────────────────────────────────────────────
// DECLARE_DYNAMIC_ATTRIBUTE always sets ATTRIBUTE_MASK_EXTERNAL_STORAGE, so
// the CHIP SDK calls these for every dynamic attribute read/write instead of
// touching its static SRAM attribute store.  We serve values from BridgeDevice.
//
// emberAfExternalAttributeWriteCallback is the PRIMARY dispatch point for all
// On/Off state changes — both InvokeCommand (On/Off/Toggle via ZCL server) and
// direct WriteAttribute from a controller.  The ZCL on-off server writes the
// attribute here AFTER computing the correct new value (Toggle uses the current
// value from emberAfExternalAttributeReadCallback, so it always computes the
// right toggle without any race with our local state).

IMStatus emberAfExternalAttributeReadCallback(EndpointId endpoint,
                                              ClusterId  clusterId,
                                              const EmberAfAttributeMetadata* am,
                                              uint8_t*   buffer,
                                              uint16_t   maxReadLength)
{
    BridgeDevice* dev = BridgeDeviceLookup(endpoint);
    if (!dev) {
        memset(buffer, 0, maxReadLength);
        return IMStatus::Success;
    }

    if (clusterId == OnOff::Id) {
        if (am->attributeId == OnOff::Attributes::OnOff::Id && maxReadLength >= 1) {
            *buffer = (dev->GetLastOnValue() == 1) ? 1 : 0;
            return IMStatus::Success;
        }
    } else if (clusterId == BridgedDeviceBasicInformation::Id) {
        if (am->attributeId == BridgedDeviceBasicInformation::Attributes::ProductName::Id ||
            am->attributeId == BridgedDeviceBasicInformation::Attributes::NodeLabel::Id ||
            am->attributeId == BridgedDeviceBasicInformation::Attributes::UniqueID::Id) {
            const auto& value =
                (am->attributeId == BridgedDeviceBasicInformation::Attributes::UniqueID::Id)
                    ? dev->GetUniqueId()
                    : dev->GetName();
            size_t cap = (maxReadLength > 1) ? (maxReadLength - 1) : 0;
            size_t len = std::min(value.size(), cap);
            buffer[0] = static_cast<uint8_t>(len);
            memcpy(buffer + 1, value.c_str(), len);
            return IMStatus::Success;
        }
        if (am->attributeId == BridgedDeviceBasicInformation::Attributes::Reachable::Id
            && maxReadLength >= 1) {
            *buffer = dev->GetReachable() ? 1 : 0;
            return IMStatus::Success;
        }
    }

    // ClusterRevision, FeatureMap, AcceptedCommandList, etc. — return zeros
    // so the SDK can still encode a valid (default) response.
    memset(buffer, 0, maxReadLength);
    return IMStatus::Success;
}

IMStatus emberAfExternalAttributeWriteCallback(EndpointId endpoint,
                                               ClusterId  clusterId,
                                               const EmberAfAttributeMetadata* am,
                                               uint8_t*   buffer)
{
    // Called by the ZCL server for every attribute write on dynamic (external-
    // storage) endpoints.  This is the single dispatch point for On/Off state
    // changes regardless of whether the trigger was an InvokeCommand (On, Off,
    // Toggle) or a direct WriteAttribute from the controller.
    if (clusterId == OnOff::Id &&
        am->attributeId == OnOff::Attributes::OnOff::Id) {
        bool on = (*buffer != 0);
        // notify_subscribers=false: emAfWriteAttribute() fires the reporting
        // callback itself after this returns (see HandleOnOffCommand comment).
        HandleOnOffCommand(endpoint, on, /*notify_subscribers=*/false);
    }
    return IMStatus::Success;
}

// ── Device management ─────────────────────────────────────────────────────────

// Must be called from the Matter event loop thread (or before RunEventLoop).
// Clears old devices OUTSIDE the mutex (so destructors run without holding it),
// then registers new devices and only takes the mutex briefly to push each
// successfully-registered device into gDevices. Uses a separate slot counter so
// that Unknown-category devices don't leave gaps in the endpoint ID space.
static void RegisterDevices(const std::vector<DeviceInfo>& infos) {
    // Release old device objects without holding gDevicesMutex, so their
    // destructors (which may call back into the CHIP registry) don't deadlock.
    std::vector<std::unique_ptr<BridgeDevice>> old_devices;
    {
        std::lock_guard<std::mutex> lock(gDevicesMutex);
        old_devices.swap(gDevices);
    }
    old_devices.clear(); // destructors run here, outside the lock

    // ep_slot only advances for successfully registered devices, so endpoint IDs
    // are contiguous even when Unknown-category entries are skipped.
    uint8_t ep_slot = 0;
    for (size_t i = 0; i < infos.size() && ep_slot < kMaxDynamicDevices; ++i) {
        const auto& info = infos[i];
        auto spec = MapCategoryToMatter(info.category, info.dimmable);
        if (spec.type == MatterDeviceType::Unknown) {
            ChipLogDetail(AppServer, "Skipping unknown category '%s' for device '%s'",
                          info.category.c_str(), info.name.c_str());
            continue;
        }

        auto ep_id = static_cast<EndpointId>(kDynamicEndpointStart + ep_slot);
        auto dev   = std::make_unique<BridgeDevice>(ep_slot, ep_id, info);

        // CHIP SDK calls (Register, UpdateOnOff, SetReachable) must NOT be made
        // while holding gDevicesMutex — they can trigger callbacks that acquire
        // other locks, risking lock-order inversion.
        CHIP_ERROR err = dev->Register();
        if (err != CHIP_NO_ERROR) {
            ChipLogError(AppServer, "Register endpoint %u ('%s') failed: %s",
                         ep_id, info.name.c_str(), ErrorStr(err));
            continue;
        }

        // Apply initial on/off state if available.
        auto it = info.state.find("on");
        if (it != info.state.end()) {
            dev->UpdateOnOff(ParseBoolState(it->second));
        }
        dev->SetReachable(true);

        ChipLogDetail(AppServer, "Registered '%s' (ep=%u) as %s",
                      info.name.c_str(), ep_id,
                      MatterDeviceTypeName(spec.type));

        // Only the push_back needs the mutex; CHIP SDK calls are done above.
        {
            std::lock_guard<std::mutex> lock(gDevicesMutex);
            gDevices.push_back(std::move(dev));
        }
        ep_slot++;
    }
}

// ── OnOff update helper (scheduled onto Matter event loop) ────────────────────

struct OnOffUpdate {
    std::string device_id;  // store ID, not raw pointer — avoids use-after-free on rescan
    bool        on;
};

static void ApplyOnOffUpdate(intptr_t ctx) {
    auto* upd = reinterpret_cast<OnOffUpdate*>(ctx);
    std::unique_ptr<OnOffUpdate> guard(upd);  // RAII delete
    std::lock_guard<std::mutex> lock(gDevicesMutex);
    for (auto& dev : gDevices) {
        if (dev->GetDeviceId() == upd->device_id) {
            dev->UpdateOnOff(upd->on);
            break;
        }
    }
}

// ── Background poll thread ────────────────────────────────────────────────────

static void PollLoop() {
    // ── Initial device registration (runs before first sleep) ────────────────
    // This must happen in the poll thread, not main(), so that RunEventLoop()
    // starts immediately and the Matter event loop can handle iPhone
    // commissioning while we wait for the Python dashboard to become ready.
    while (gRunning) {
        try {
            auto infos = gSyncClient->FetchDevices();
            if (!infos.empty()) {
                PlatformMgr().ScheduleWork([](intptr_t ctx) {
                    auto* p = reinterpret_cast<std::vector<DeviceInfo>*>(ctx);
                    RegisterDevices(*p);
                    delete p;
                }, reinterpret_cast<intptr_t>(new std::vector<DeviceInfo>(std::move(infos))));
                break;
            }
            ChipLogDetail(AppServer, "No devices yet; retrying in 5 s...");
        } catch (const SyncClientError& e) {
            const char* msg = e.what();
            ChipLogError(AppServer, "Waiting for bridge sync API: %s - retrying in 5 s", msg);
        }
        std::unique_lock<std::mutex> lk(gShutdownMutex);
        gShutdownCv.wait_for(lk, std::chrono::seconds(5),
                              [] { return !gRunning.load(); });
    }

    uint32_t ticks = 0;

    while (gRunning) {
        // Interruptible sleep: woken immediately on shutdown instead of waiting
        // out the full kDevicePollIntervalSeconds.
        {
            std::unique_lock<std::mutex> lk(gShutdownMutex);
            gShutdownCv.wait_for(lk,
                std::chrono::seconds(kDevicePollIntervalSeconds),
                [] { return !gRunning.load(); });
        }

        if (!gRunning) break;
        ++ticks;

        // ── Rescan for new/removed devices every kDeviceRescanIntervalSeconds ──
        bool do_rescan = (ticks % (kDeviceRescanIntervalSeconds /
                                    kDevicePollIntervalSeconds) == 0);
        if (do_rescan) {
            try {
                auto new_infos = gSyncClient->FetchDevices();
                // Count only registrable devices (Unknown category is skipped in
                // RegisterDevices) so the comparison doesn't fire every 60 s when
                // the device list contains any unmapped-category entries.
                size_t registrable_count = 0;
                for (const auto& di : new_infos) {
                    if (MapCategoryToMatter(di.category, di.dimmable).type
                            != MatterDeviceType::Unknown)
                        ++registrable_count;
                }
                size_t current_count;
                {
                    std::lock_guard<std::mutex> lock(gDevicesMutex);
                    current_count = gDevices.size();
                }
                if (registrable_count != current_count) {
                    ChipLogDetail(AppServer,
                                  "Device list changed (%zu → %zu registrable); keeping existing Matter endpoints stable",
                                  current_count, registrable_count);
                    // Do not restart from the poll loop. /bridge/devices can be
                    // partial during dashboard restarts or slow device status
                    // reads; restarting a commissioned bridge drops active
                    // controller sessions and makes Apple Home show No Response.
                    // Endpoint topology changes require an intentional bridge
                    // restart/recommission after the device list is known stable.
                }
            } catch (const SyncClientError& poll_err) {
                const char* poll_msg = poll_err.what();
                ChipLogError(AppServer, "FetchDevices failed: %s", poll_msg);
            }
        }

        // ── Poll current state and push to Matter attributes ──────────────────
        try {
            std::vector<std::string> registered_device_ids;
            {
                std::lock_guard<std::mutex> lock(gDevicesMutex);
                for (const auto& dev_ptr : gDevices) {
                    registered_device_ids.push_back(dev_ptr->GetDeviceId());
                }
            }

            auto states = gSyncClient->FetchAllStatesFor(registered_device_ids);

            std::lock_guard<std::mutex> lock(gDevicesMutex);
            for (const auto& dev_ptr : gDevices) {
                const auto sit = states.find(dev_ptr->GetDeviceId());
                if (sit == states.end()) continue;

                const auto& state  = sit->second;
                auto        on_it  = state.find("on");
                if (on_it == state.end()) continue;

                bool on = ParseBoolState(on_it->second);
                auto* upd = new OnOffUpdate{dev_ptr->GetDeviceId(), on};
                PlatformMgr().ScheduleWork(ApplyOnOffUpdate,
                                           reinterpret_cast<intptr_t>(upd));
            }
        } catch (const SyncClientError& poll_err) {
            const char* poll_msg = poll_err.what();
            ChipLogError(AppServer, "FetchAllStates failed: %s", poll_msg);
        }
    }

    ChipLogDetail(AppServer, "Poll thread exiting.");
}

// ── main ──────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    // ── Platform / CHIP stack init ────────────────────────────────────────────
    // ChipLinuxAppInit handles MemoryInit, InitChipStack, the commissionable
    // data provider (discriminator/passcode), and the example DAC provider.
    // It also parses standard CHIP CLI flags such as --KVS, --discriminator,
    // --passcode that the container entrypoint passes through.
    if (ChipLinuxAppInit(argc, argv) != 0) {
        return -1;
    }

    // ChipLinuxAppMainLoop() normally sets up the example DAC provider, but we
    // run our own event loop, so set it explicitly here before Server::Init().
    chip::Credentials::SetDeviceAttestationCredentialsProvider(
        chip::Credentials::Examples::GetExampleDACProvider());

    static CommonCaseDeviceServerInitParams initParams;
    initParams.InitializeStaticResourcesBeforeServerInit();
    CHIP_ERROR err = Server::GetInstance().Init(initParams);
    VerifyOrDie(err == CHIP_NO_ERROR);
    err = InteractionModelEngine::GetInstance()->RegisterCommandHandler(&gDynamicOnOffCommandHandler);
    VerifyOrDie(err == CHIP_NO_ERROR);
    ChipLogDetail(AppServer, "Registered dynamic OnOff command handler");

    // Disable the static example DimmableLight from the bridge-app ZAP config
    // (ep=2). If left enabled it appears in the aggregator PartsList with an
    // empty NodeLabel, causing Apple Home to show it as "Light 1" and pushing
    // our real devices to "Light 2-8".
    emberAfEndpointEnableDisable(2, false);

    // ── Signal handlers (SIGINT / SIGTERM for graceful systemctl stop) ────────
    signal(SIGINT,  HandleSignal);
    signal(SIGTERM, HandleSignal);

    // ── SyncClient setup ──────────────────────────────────────────────────────
    const char* base_url = GetBridgeSyncUrl();
    ChipLogDetail(AppServer, "Bridge sync URL: %s", base_url);
    SyncClient sync_client(base_url);
    gSyncClient = &sync_client;

    // ── Background poll thread ────────────────────────────────────────────────
    // Starts immediately so RunEventLoop() is reached without delay.
    // The poll thread handles initial device registration internally, retrying
    // until the Python dashboard is ready — this way the Matter event loop
    // (and iPhone commissioning) can proceed even if the dashboard is slow.
    std::thread poll_thread(PollLoop);

    ChipLogDetail(AppServer,
                  "Matter bridge running — commission via Apple Home.");
    PlatformMgr().RunEventLoop();   // blocks until Shutdown() is called

    // ── Teardown ───────────────────────────────────────────────────────────────
    gRunning = false;
    gShutdownCv.notify_all(); // wake poll thread immediately instead of waiting
    poll_thread.join();

    InteractionModelEngine::GetInstance()->UnregisterCommandHandler(&gDynamicOnOffCommandHandler);
    Server::GetInstance().Shutdown();
    PlatformMgr().Shutdown();
    return 0;
}

// ── AppMain.h required callbacks ──────────────────────────────────────────────
// ChipLinuxAppMainLoop calls these; we don't use that loop but must satisfy the
// link since AppMain.h declares them.
// No-op plugin init callbacks for clusters pruned from bridge-app.zap.
// CHIP's util.cpp still references these stock bridge app extension points.
void MatterDiagnosticLogsPluginServerInitCallback() {}
void MatterEthernetNetworkDiagnosticsPluginServerInitCallback() {}
void MatterGeneralDiagnosticsPluginServerInitCallback() {}
void MatterLevelControlPluginServerInitCallback() {}
void MatterLocalizationConfigurationPluginServerInitCallback() {}
void MatterOnOffPluginServerInitCallback() {}
void MatterSoftwareDiagnosticsPluginServerInitCallback() {}
void MatterSwitchPluginServerInitCallback() {}
void MatterThreadNetworkDiagnosticsPluginServerInitCallback() {}
void MatterTimeFormatLocalizationPluginServerInitCallback() {}
void MatterUserLabelPluginServerInitCallback() {}
void MatterWiFiNetworkDiagnosticsPluginServerInitCallback() {}

void ApplicationInit() {}
void ApplicationShutdown() {}

// ── Bridge-app callbacks required by bridged-actions-stub.cpp ─────────────────
// We don't implement the Actions cluster, so these stubs return empty results.

std::vector<EndpointListInfo> GetEndpointListInfo(chip::EndpointId /* parentId */) {
    return {};
}

std::vector<Action*> GetActionListInfo(chip::EndpointId /* parentId */) {
    return {};
}

bool emberAfActionsClusterInstantActionCallback(
    chip::app::CommandHandler* commandObj,
    const chip::app::ConcreteCommandPath& commandPath,
    const chip::app::Clusters::Actions::Commands::InstantAction::DecodableType& /* commandData */)
{
    commandObj->AddStatus(commandPath, chip::Protocols::InteractionModel::Status::NotFound);
    return true;
}
