#include "SyncClient.h"
#include <curl/curl.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* output) {
    output->append(static_cast<char*>(contents), size * nmemb);
    return size * nmemb;
}

// RAII wrapper for a libcurl easy handle
struct CurlHandle {
    CURL* h = nullptr;
    CurlHandle() : h(curl_easy_init()) {}
    ~CurlHandle() { if (h) curl_easy_cleanup(h); }
    operator CURL*() const { return h; }
    CurlHandle(const CurlHandle&) = delete;
    CurlHandle& operator=(const CurlHandle&) = delete;
};

// RAII wrapper for a curl_slist (HTTP headers)
struct CurlSlist {
    curl_slist* h = nullptr;
    ~CurlSlist() { if (h) curl_slist_free_all(h); }
    CurlSlist(const CurlSlist&) = delete;
    CurlSlist& operator=(const CurlSlist&) = delete;
};

SyncClient::SyncClient(const std::string& base_url) : base_url_(base_url) {
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

SyncClient::~SyncClient() {
    curl_global_cleanup();
}

std::string SyncClient::DoGet(const std::string& path) {
    CurlHandle curl;
    if (!curl.h) throw SyncClientError("curl_easy_init failed");

    std::string response;
    const std::string url = base_url_ + path;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);

    const CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    // curl handle freed automatically by CurlHandle destructor

    if (res != CURLE_OK) {
        throw SyncClientError(std::string("GET ") + path + " failed: " + curl_easy_strerror(res));
    }
    if (http_code >= 400) {
        throw SyncClientError("GET " + path + " returned HTTP " + std::to_string(http_code));
    }
    return response;
}

std::string SyncClient::DoPost(const std::string& path, const std::string& body) {
    CurlHandle curl;
    if (!curl.h) throw SyncClientError("curl_easy_init failed");

    std::string response;
    const std::string url = base_url_ + path;
    CurlSlist headers;
    headers.h = curl_slist_append(headers.h, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers.h);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);

    const CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    // curl handle and headers freed automatically by RAII destructors

    if (res != CURLE_OK) {
        throw SyncClientError(std::string("POST ") + path + " failed: " + curl_easy_strerror(res));
    }
    if (http_code >= 400) {
        throw SyncClientError("POST " + path + " returned HTTP " + std::to_string(http_code));
    }
    return response;
}

std::vector<DeviceInfo> SyncClient::FetchDevices() {
    const std::string body = DoGet("/bridge/devices");
    json j;
    try {
        j = json::parse(body);
    } catch (const json::exception& ex) {
        throw SyncClientError(std::string("FetchDevices parse error: ") + ex.what());
    }
    std::vector<DeviceInfo> devices;
    for (const auto& item : j) {
        DeviceInfo d;
        d.device_id = item.at("device_id").get<std::string>();
        d.name      = item.at("name").get<std::string>();
        d.room      = item.value("room", "");
        d.category  = item.at("category").get<std::string>();
        d.dimmable  = item.value("dimmable", false);
        if (item.contains("state") && item["state"].is_object()) {
            for (const auto& [k, v] : item["state"].items()) {
                d.state[k] = v.is_string() ? v.get<std::string>() : v.dump();
            }
        }
        devices.push_back(std::move(d));
    }
    return devices;
}

std::map<std::string, std::map<std::string, std::string>> SyncClient::FetchAllStates() {
    const std::string body = DoGet("/bridge/state/all");
    json j;
    try {
        j = json::parse(body);
    } catch (const json::exception& ex) {
        throw SyncClientError(std::string("FetchAllStates parse error: ") + ex.what());
    }
    std::map<std::string, std::map<std::string, std::string>> result;
    for (const auto& [device_id, state] : j.items()) {
        for (const auto& [k, v] : state.items()) {
            result[device_id][k] = v.is_string() ? v.get<std::string>() : v.dump();
        }
    }
    return result;
}

void SyncClient::SendCommand(const std::string& device_id, const std::string& command) {
    json body_j;
    body_j["device_id"] = device_id;
    body_j["command"]   = command;
    DoPost("/bridge/command", body_j.dump());
}
