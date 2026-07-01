#include "SyncClient.h"

#include <AppMain.h>
#include <app-common/zap-generated/attributes/Accessors.h>
#include <app-common/zap-generated/ids/Attributes.h>
#include <app-common/zap-generated/ids/Clusters.h>
#include <app/ConcreteAttributePath.h>
#include <lib/support/logging/CHIPLogging.h>
#include <platform/PlatformManager.h>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

using namespace chip;
using namespace chip::app;
using namespace chip::app::Clusters;
using chip::DeviceLayer::PlatformMgr;

namespace {
constexpr EndpointId kLightEndpoint = 1;
constexpr const char * kDeviceId    = "kasa:192.168.0.73";
constexpr const char * kDeviceName  = "Living room light switch 2";
constexpr int kPollSeconds          = 5;

std::unique_ptr<SyncClient> gSyncClient;
std::atomic_bool gRunning{ true };
std::atomic_bool gSuppressNextOnOffCommand{ false };
std::atomic<int> gLastPublishedOnOff{ -1 };
std::atomic<int> gLastPolledOnOff{ -1 };
std::mutex gCommandMutex;

bool ParseBoolState(const std::string & value)
{
    return value == "true" || value == "1" || value == "on" || value == "True";
}

void ApplyMatterOnOff(intptr_t ctx)
{
    const bool on     = ctx != 0;
    const int desired = on ? 1 : 0;
    if (gLastPublishedOnOff.load() == desired)
    {
        return;
    }

    gSuppressNextOnOffCommand.store(true);
    Protocols::InteractionModel::Status status = OnOff::Attributes::OnOff::Set(kLightEndpoint, on);
    gSuppressNextOnOffCommand.store(false);
    if (status == Protocols::InteractionModel::Status::Success)
    {
        gLastPublishedOnOff.store(desired);
        ChipLogProgress(AppServer, "Single light: published polled OnOff=%d", on);
        return;
    }

    ChipLogError(AppServer, "Single light: failed to update Matter OnOff=%d status=%u", on, to_underlying(status));
}

void SendKasaCommandAsync(bool on)
{
    std::thread([on] {
        std::lock_guard<std::mutex> lock(gCommandMutex);
        try
        {
            gSyncClient->SendCommand(kDeviceId, on ? "on" : "off");
            ChipLogProgress(AppServer, "Single light: sent %s to %s", on ? "on" : "off", kDeviceId);
        }
        catch (const std::exception & ex)
        {
            ChipLogError(AppServer, "Single light: command %s failed: %s", on ? "on" : "off", ex.what());
        }
    }).detach();
}

void PollLoop()
{
    while (gRunning.load())
    {
        try
        {
            auto states = gSyncClient->FetchAllStatesFor({ kDeviceId });
            auto devIt = states.find(kDeviceId);
            if (devIt != states.end())
            {
                auto onIt = devIt->second.find("on");
                if (onIt != devIt->second.end())
                {
                    bool on         = ParseBoolState(onIt->second);
                    const int polled = on ? 1 : 0;
                    if (gLastPolledOnOff.exchange(polled) != polled)
                    {
                        PlatformMgr().ScheduleWork(ApplyMatterOnOff, polled);
                    }
                }
            }
        }
        catch (const std::exception & ex)
        {
            ChipLogError(AppServer, "Single light: state poll failed: %s", ex.what());
        }

        for (int i = 0; i < kPollSeconds && gRunning.load(); ++i)
        {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
}
} // namespace

void MatterPostAttributeChangeCallback(const ConcreteAttributePath & attributePath, uint8_t type, uint16_t size, uint8_t * value)
{
    if (attributePath.mEndpointId != kLightEndpoint || attributePath.mClusterId != OnOff::Id ||
        attributePath.mAttributeId != OnOff::Attributes::OnOff::Id || value == nullptr)
    {
        return;
    }

    bool on = (*value != 0);
    gLastPublishedOnOff.store(on ? 1 : 0);
    ChipLogProgress(AppServer, "Single light: Matter OnOff changed to %d", on);
    if (gSuppressNextOnOffCommand.exchange(false))
    {
        return;
    }
    SendKasaCommandAsync(on);
}

void emberAfOnOffClusterInitCallback(EndpointId endpoint) {}
void MatterLevelControlPluginServerInitCallback() {}

void ApplicationInit()
{
    ChipLogProgress(AppServer, "Single light accessory ready for %s (%s)", kDeviceName, kDeviceId);
}

void ApplicationShutdown()
{
    gRunning.store(false);
}

int main(int argc, char * argv[])
{
    if (ChipLinuxAppInit(argc, argv) != 0)
    {
        return -1;
    }

    const char * baseUrl = std::getenv("BRIDGE_SYNC_URL");
    if (baseUrl == nullptr || *baseUrl == '\0')
    {
        baseUrl = "http://localhost:8000";
    }
    gSyncClient = std::make_unique<SyncClient>(baseUrl);

    std::thread pollThread(PollLoop);
    ChipLinuxAppMainLoop();
    gRunning.store(false);
    if (pollThread.joinable())
    {
        pollThread.join();
    }
    gSyncClient.reset();
    return 0;
}
