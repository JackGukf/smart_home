#include <gtest/gtest.h>
#include "src/cpp/matter_bridge/SyncClient.h"
#include <map>
#include <string>
#include <vector>
#include <stdexcept>

// Testable subclass that overrides the HTTP layer
class FakeSyncClient : public SyncClient {
public:
    FakeSyncClient() : SyncClient("http://localhost:8000") {}
    std::string devices_response;
    std::string states_response;
    std::string last_post_path;
    std::string last_post_body;

protected:
    std::string DoGet(const std::string& path) override {
        if (path == "/bridge/devices") return devices_response;
        if (path == "/bridge/state/all") return states_response;
        throw SyncClientError("unexpected GET: " + path);
    }
    std::string DoPost(const std::string& path, const std::string& body) override {
        last_post_path = path;
        last_post_body = body;
        return R"({"status":"ok"})";
    }
};

TEST(SyncClient, FetchDevicesParsesJson) {
    FakeSyncClient client;
    client.devices_response = R"([
        {"device_id":"kasa:192.168.1.10","name":"Living Room","room":"Living Room",
         "category":"light_switch","dimmable":false,"state":{"on":true}}
    ])";
    auto devices = client.FetchDevices();
    ASSERT_EQ(devices.size(), 1u);
    EXPECT_EQ(devices[0].device_id, "kasa:192.168.1.10");
    EXPECT_EQ(devices[0].category, "light_switch");
    EXPECT_EQ(devices[0].state.at("on"), "true");
    EXPECT_FALSE(devices[0].dimmable);
}

TEST(SyncClient, FetchDevicesEmptyList) {
    FakeSyncClient client;
    client.devices_response = "[]";
    auto devices = client.FetchDevices();
    EXPECT_TRUE(devices.empty());
}

TEST(SyncClient, FetchAllStatesParsesJson) {
    FakeSyncClient client;
    client.states_response = R"({"kasa:192.168.1.10":{"on":"true"}})";
    auto states = client.FetchAllStates();
    ASSERT_EQ(states.count("kasa:192.168.1.10"), 1u);
    EXPECT_EQ(states.at("kasa:192.168.1.10").at("on"), "true");
}

TEST(SyncClient, SendCommandPostsCorrectBody) {
    FakeSyncClient client;
    client.SendCommand("kasa:192.168.1.10", "on");
    EXPECT_EQ(client.last_post_path, "/bridge/command");
    // body must contain device_id and command
    EXPECT_NE(client.last_post_body.find("kasa:192.168.1.10"), std::string::npos);
    EXPECT_NE(client.last_post_body.find("\"on\""), std::string::npos);
}

TEST(SyncClient, FetchDevicesBadJsonThrows) {
    FakeSyncClient client;
    client.devices_response = "not json";
    EXPECT_THROW(client.FetchDevices(), SyncClientError);
}
