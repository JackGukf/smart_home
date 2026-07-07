#include "SyncClient.h"

#include <AppMain.h>
#include <app-common/zap-generated/attributes/Accessors.h>
#include <app-common/zap-generated/ids/Attributes.h>
#include <app-common/zap-generated/ids/Clusters.h>
#include <app/ConcreteAttributePath.h>
#include <lib/support/logging/CHIPLogging.h>
#include <platform/PlatformManager.h>

#include <array>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

using namespace chip;
using namespace chip::app;
using namespace chip::app::Clusters;
using chip::DeviceLayer::PlatformMgr;

namespace {
struct LightSpec
{
    EndpointId endpoint;
    const char * deviceId;
    const char * name;
};

constexpr std::array<LightSpec, 4> kLights = {{
    { 1, "kasa:192.168.0.110", "Kitchen light switch" },
    { 2, "kasa:192.168.0.143", "Master bedroom light switch" },
    { 3, "kasa:192.168.0.61", "Family room light switch" },
    { 4, "kasa:192.168.0.73", "Living room light switch 2" },
}};
constexpr int kPollSeconds = 5;

struct OnOffUpdate
{
    size_t index;
    bool on;
};

std::unique_ptr<SyncClient> gSyncClient;
std::atomic_bool gRunning{ true };
std::array<std::atomic_bool, kLights.size()> gSuppressNextOnOffCommand;
std::array<std::atomic<int>, kLights.size()> gLastPublishedOnOff;
std::array<std::atomic<int>, kLights.size()> gLastPolledOnOff;
std::mutex gCommandMutex;

bool ParseBoolState(const std::string & value)
{
    return value == "true" || value == "1" || value == "on" || value == "True";
}

const LightSpec * FindLightByEndpoint(EndpointId endpoint, size_t * index = nullptr)
{
    for (size_t i = 0; i < kLights.size(); ++i)
    {
        if (kLights[i].endpoint == endpoint)
        {
            if (index != nullptr)
            {
                *index = i;
            }
            return &kLights[i];
        }
    }
    return nullptr;
}

void ApplyMatterOnOff(intptr_t ctx)
{
    std::unique_ptr<OnOffUpdate> update(reinterpret_cast<OnOffUpdate *>(ctx));
    if (update->index >= kLights.size())
    {
        return;
    }

    const auto & light = kLights[update->index];
    const int desired  = update->on ? 1 : 0;
    if (gLastPublishedOnOff[update->index].load() == desired)
    {
        return;
    }

    gSuppressNextOnOffCommand[update->index].store(true);
    Protocols::InteractionModel::Status status = OnOff::Attributes::OnOff::Set(light.endpoint, update->on);
    gSuppressNextOnOffCommand[update->index].store(false);
    if (status == Protocols::InteractionModel::Status::Success)
    {
        gLastPublishedOnOff[update->index].store(desired);
        ChipLogProgress(AppServer, "Fixed lights: published %s OnOff=%d", light.name, update->on);
        return;
    }

    ChipLogError(AppServer, "Fixed lights: failed to update %s OnOff=%d status=%u", light.name, update->on,
                 to_underlying(status));
}

void SendKasaCommandAsync(size_t index, bool on)
{
    if (index >= kLights.size())
    {
        return;
    }

    const std::string deviceId = kLights[index].deviceId;
    const std::string name     = kLights[index].name;
    std::thread([deviceId, name, on] {
        std::lock_guard<std::mutex> lock(gCommandMutex);
        try
        {
            gSyncClient->SendCommand(deviceId, on ? "on" : "off");
            ChipLogProgress(AppServer, "Fixed lights: sent %s to %s (%s)", on ? "on" : "off", name.c_str(),
                            deviceId.c_str());
        }
        catch (const std::exception & ex)
        {
            ChipLogError(AppServer, "Fixed lights: command %s failed for %s: %s", on ? "on" : "off", name.c_str(),
                         ex.what());
        }
    }).detach();
}

void PollLoop()
{
    std::vector<std::string> deviceIds;
    deviceIds.reserve(kLights.size());
    for (const auto & light : kLights)
    {
        deviceIds.emplace_back(light.deviceId);
    }

    while (gRunning.load())
    {
        try
        {
            auto states = gSyncClient->FetchAllStatesFor(deviceIds);
            for (size_t i = 0; i < kLights.size(); ++i)
            {
                const auto & light = kLights[i];
                auto devIt        = states.find(light.deviceId);
                if (devIt == states.end())
                {
                    continue;
                }
                auto onIt = devIt->second.find("on");
                if (onIt == devIt->second.end())
                {
                    continue;
                }

                bool on          = ParseBoolState(onIt->second);
                const int polled = on ? 1 : 0;
                if (gLastPolledOnOff[i].exchange(polled) != polled)
                {
                    PlatformMgr().ScheduleWork(ApplyMatterOnOff, reinterpret_cast<intptr_t>(new OnOffUpdate{ i, on }));
                }
            }
        }
        catch (const std::exception & ex)
        {
            ChipLogError(AppServer, "Fixed lights: state poll failed: %s", ex.what());
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
    size_t index = 0;
    const LightSpec * light = FindLightByEndpoint(attributePath.mEndpointId, &index);
    if (light == nullptr || attributePath.mClusterId != OnOff::Id ||
        attributePath.mAttributeId != OnOff::Attributes::OnOff::Id || value == nullptr)
    {
        return;
    }

    bool on = (*value != 0);
    gLastPublishedOnOff[index].store(on ? 1 : 0);
    ChipLogProgress(AppServer, "Fixed lights: Matter OnOff changed for %s to %d", light->name, on);
    if (gSuppressNextOnOffCommand[index].exchange(false))
    {
        return;
    }
    SendKasaCommandAsync(index, on);
}

void emberAfOnOffClusterInitCallback(EndpointId endpoint) {}
void MatterLevelControlPluginServerInitCallback() {}

void ApplicationInit()
{
    for (size_t i = 0; i < kLights.size(); ++i)
    {
        gSuppressNextOnOffCommand[i].store(false);
        gLastPublishedOnOff[i].store(-1);
        gLastPolledOnOff[i].store(-1);
        ChipLogProgress(AppServer, "Fixed lights accessory endpoint %u: %s (%s)", kLights[i].endpoint, kLights[i].name,
                        kLights[i].deviceId);
    }
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
