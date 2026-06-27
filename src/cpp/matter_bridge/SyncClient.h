#pragma once
#include <map>
#include <string>
#include <vector>
#include <stdexcept>

struct DeviceInfo {
    std::string device_id;
    std::string name;
    std::string room;
    std::string category;
    bool dimmable = false;
    std::map<std::string, std::string> state;
};

class SyncClientError : public std::runtime_error {
public:
    explicit SyncClientError(const std::string& msg) : std::runtime_error(msg) {}
};

class SyncClient {
public:
    explicit SyncClient(const std::string& base_url);
    virtual ~SyncClient();

    virtual std::vector<DeviceInfo> FetchDevices();
    virtual std::map<std::string, std::map<std::string, std::string>> FetchAllStates();
    virtual void SendCommand(const std::string& device_id, const std::string& command);

protected:
    // Virtual so tests can override the HTTP layer
    virtual std::string DoGet(const std::string& path);
    virtual std::string DoPost(const std::string& path, const std::string& body);

private:
    std::string base_url_;
};
