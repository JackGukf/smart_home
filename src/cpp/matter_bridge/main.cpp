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
#include <credentials/DeviceAttestationCredsProvider.h>
#include <credentials/examples/DeviceAttestationCredsExample.h>
#include <lib/core/ErrorStr.h>
#include <platform/CHIPDeviceLayer.h>
#include <platform/Linux/NetworkCommissioningDriver.h>

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
                size_t current_count;
                {
                    std::lock_guard<std::mutex> lock(gDevicesMutex);
                    current_count = gDevices.size();
                }
                if (new_infos.size() != current_count) {
                    ChipLogDetail(AppServer,
                                  "Device list changed (%zu → %zu), re-registering",
                                  current_count, new_infos.size());
                    // Re-register from the Matter event loop thread so that
                    // emberAf* calls are thread-safe. RegisterDevices() handles
                    // clearing the old device list internally (outside the mutex).
                    PlatformMgr().ScheduleWork([](intptr_t ctx) {
                        auto* infos =
                            reinterpret_cast<std::vector<DeviceInfo>*>(ctx);
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

                bool on = ParseBoolState(on_it->second);
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

    // ── Signal handlers (SIGINT / SIGTERM for graceful systemctl stop) ────────
    signal(SIGINT,  HandleSignal);
    signal(SIGTERM, HandleSignal);

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
    gShutdownCv.notify_all(); // wake poll thread immediately instead of waiting
    poll_thread.join();

    Server::GetInstance().Shutdown();
    PlatformMgr().Shutdown();
    return 0;
}
