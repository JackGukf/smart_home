/*
 * Matter Bridge main.cpp
 *
 * Initialises the CHIP stack, fetches devices from the Python bridge sync API,
 * registers them as dynamic Matter endpoints, then runs a background poll loop
 * that keeps Apple Home in sync with real device state.
 *
 * Build: scripts/build-matter-bridge.sh (inside Docker dev container)
 */
#include "BridgeDevice.h"
#include "DeviceMapper.h"
#include "SyncClient.h"

#include <app/server/Server.h>
#include <app/server/CommissioningWindowManager.h>
#include <credentials/DeviceAttestationCredsProvider.h>
#include <credentials/examples/DeviceAttestationCredsExample.h>
#include <lib/core/ErrorStr.h>
#include <platform/CHIPDeviceLayer.h>
#include <platform/Linux/NetworkCommissioningDriver.h>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

using namespace chip;
using namespace chip::app;
using namespace chip::DeviceLayer;

// ── Constants ─────────────────────────────────────────────────────────────────

static constexpr uint16_t kDevicePollIntervalSeconds   = 10;
static constexpr uint16_t kDeviceRescanIntervalSeconds = 60;
// Endpoint 0 = root node, endpoint 1 = aggregator/bridge; dynamic starts at 2.
static constexpr EndpointId kDynamicEndpointStart = 2;
static constexpr uint8_t    kMaxDynamicDevices    = 50;

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

// ── CHIP SDK callbacks ────────────────────────────────────────────────────────

// Called by the CHIP stack when an attribute is written (e.g. Apple Home
// toggles a switch).  Delegates to HandleAttributeChanged() which uses the
// process-global CommandSenderFn installed via SetCommandSender().
void MatterPostAttributeChangeCallback(const ConcreteAttributePath& path,
                                       uint8_t  /*type*/,
                                       uint16_t /*size*/,
                                       uint8_t* value) {
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

// ── Device management ─────────────────────────────────────────────────────────

// Must be called from the Matter event loop thread (or before RunEventLoop).
static void RegisterDevices(const std::vector<DeviceInfo>& infos) {
    std::lock_guard<std::mutex> lock(gDevicesMutex);

    for (size_t i = 0; i < infos.size() && i < kMaxDynamicDevices; ++i) {
        const auto& info = infos[i];
        auto spec = MapCategoryToMatter(info.category, info.dimmable);
        if (spec.type == MatterDeviceType::Unknown) {
            ChipLogDetail(AppServer, "Skipping unknown category '%s' for device '%s'",
                          info.category.c_str(), info.name.c_str());
            continue;
        }

        auto ep_id = static_cast<EndpointId>(kDynamicEndpointStart + i);
        auto dev   = std::make_unique<BridgeDevice>(
            static_cast<uint8_t>(i), ep_id, info);

        CHIP_ERROR err = dev->Register();
        if (err != CHIP_NO_ERROR) {
            ChipLogError(AppServer, "Register endpoint %u ('%s') failed: %s",
                         ep_id, info.name.c_str(), ErrorStr(err));
            continue;
        }

        // Apply initial on/off state if available.
        auto it = info.state.find("on");
        if (it != info.state.end()) {
            bool on = (it->second == "true" || it->second == "1");
            dev->UpdateOnOff(on);
        }
        dev->SetReachable(true);

        ChipLogDetail(AppServer, "Registered '%s' (ep=%u) as %s",
                      info.name.c_str(), ep_id,
                      MatterDeviceTypeName(spec.type));

        gDevices.push_back(std::move(dev));
    }
}

// ── OnOff update helper (scheduled onto Matter event loop) ────────────────────

struct OnOffUpdate {
    BridgeDevice* dev;
    bool          on;
};

static void ApplyOnOffUpdate(intptr_t ctx) {
    auto* u = reinterpret_cast<OnOffUpdate*>(ctx);
    u->dev->UpdateOnOff(u->on);
    delete u;
}

// ── Background poll thread ────────────────────────────────────────────────────

static void PollLoop() {
    uint32_t ticks = 0;

    while (gRunning) {
        std::this_thread::sleep_for(
            std::chrono::seconds(kDevicePollIntervalSeconds));

        if (!gRunning) break;
        ++ticks;

        // ── Rescan for new/removed devices every kDeviceRescanIntervalSeconds ──
        bool do_rescan = (ticks % (kDeviceRescanIntervalSeconds /
                                    kDevicePollIntervalSeconds) == 0);
        if (do_rescan) {
            try {
                auto new_infos = gSyncClient->FetchDevices();
                size_t current_count;
                {
                    std::lock_guard<std::mutex> lock(gDevicesMutex);
                    current_count = gDevices.size();
                }
                if (new_infos.size() != current_count) {
                    ChipLogDetail(AppServer,
                                  "Device list changed (%zu → %zu), re-registering",
                                  current_count, new_infos.size());
                    // Clear existing devices, then re-register from the Matter
                    // event loop thread so emberAf* calls are thread-safe.
                    PlatformMgr().ScheduleWork([](intptr_t ctx) {
                        auto* infos =
                            reinterpret_cast<std::vector<DeviceInfo>*>(ctx);
                        {
                            std::lock_guard<std::mutex> lock(gDevicesMutex);
                            gDevices.clear();
                        }
                        RegisterDevices(*infos);
                        delete infos;
                    }, reinterpret_cast<intptr_t>(
                           new std::vector<DeviceInfo>(std::move(new_infos))));
                }
            } catch (const SyncClientError& e) {
                ChipLogError(AppServer, "FetchDevices failed: %s", e.what());
            }
        }

        // ── Poll current state and push to Matter attributes ──────────────────
        try {
            auto states = gSyncClient->FetchAllStates();

            std::lock_guard<std::mutex> lock(gDevicesMutex);
            for (const auto& dev_ptr : gDevices) {
                const auto sit = states.find(dev_ptr->GetDeviceId());
                if (sit == states.end()) continue;

                const auto& state  = sit->second;
                auto        on_it  = state.find("on");
                if (on_it == state.end()) continue;

                bool on = (on_it->second == "true" || on_it->second == "1");
                auto* u = new OnOffUpdate{dev_ptr.get(), on};
                PlatformMgr().ScheduleWork(ApplyOnOffUpdate,
                                           reinterpret_cast<intptr_t>(u));
            }
        } catch (const SyncClientError& e) {
            ChipLogError(AppServer, "FetchAllStates failed: %s", e.what());
        }
    }

    ChipLogDetail(AppServer, "Poll thread exiting.");
}

// ── main ──────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    // ── Platform / CHIP stack init ────────────────────────────────────────────
    CHIP_ERROR err = Platform::MemoryInit();
    VerifyOrDie(err == CHIP_NO_ERROR);

    err = PlatformMgr().InitChipStack();
    VerifyOrDie(err == CHIP_NO_ERROR);

    // Use example DAC provider (replace with production certificates before
    // shipping a real product).
    SetDeviceAttestationCredentialsProvider(
        Credentials::Examples::GetExampleDACProvider());

    // KVS / commissioning data path: /data/bridge/ (the matter-data Docker volume).
    // At runtime, pass `--KVS /data/bridge/kvs` on the command line, or set the
    // path before Server::Init() via ConfigurationMgr if programmatic override is
    // needed. Leaving initParams at defaults means the SDK reads any --KVS flag
    // supplied by the container's entrypoint.
    static CommonCaseDeviceServerInitParams initParams;
    initParams.InitializeStaticResourcesBeforeServerInit();
    err = Server::GetInstance().Init(initParams);
    VerifyOrDie(err == CHIP_NO_ERROR);

    // ── SyncClient setup ──────────────────────────────────────────────────────
    const char* base_url = GetBridgeSyncUrl();
    ChipLogDetail(AppServer, "Bridge sync URL: %s", base_url);
    SyncClient sync_client(base_url);
    gSyncClient = &sync_client;

    // Install the CommandSenderFn that HandleAttributeChanged() will use when
    // Apple Home writes to a bridged device (e.g. toggles a switch).
    SetCommandSender([](const std::string& device_id,
                        const std::string& command) {
        if (!gSyncClient) return;
        try {
            gSyncClient->SendCommand(device_id, command);
        } catch (const SyncClientError& e) {
            ChipLogError(AppServer, "SendCommand(%s, %s) failed: %s",
                         device_id.c_str(), command.c_str(), e.what());
        }
    });

    // ── Initial device discovery (retry until Python dashboard is ready) ───────
    std::vector<DeviceInfo> device_infos;
    while (device_infos.empty() && gRunning) {
        try {
            device_infos = gSyncClient->FetchDevices();
            if (device_infos.empty()) {
                ChipLogDetail(AppServer,
                              "No devices returned; retrying in 5 s...");
                std::this_thread::sleep_for(std::chrono::seconds(5));
            }
        } catch (const SyncClientError& e) {
            ChipLogError(AppServer,
                         "Waiting for bridge sync API: %s — retrying in 5 s",
                         e.what());
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
    }

    if (!gRunning) return 0;

    RegisterDevices(device_infos);

    // ── Background poll thread ─────────────────────────────────────────────────
    std::thread poll_thread(PollLoop);

    ChipLogDetail(AppServer,
                  "Matter bridge running — commission via Apple Home.");
    PlatformMgr().RunEventLoop();   // blocks until Shutdown() is called

    // ── Teardown ───────────────────────────────────────────────────────────────
    gRunning = false;
    poll_thread.join();

    Server::GetInstance().Shutdown();
    PlatformMgr().Shutdown();
    return 0;
}
