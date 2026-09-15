#pragma once
// The Settings app's Wi-Fi page (voice-panel.yaml: wifi_scan): scan while
// connected, and list what was found for an LVGL roller.
#include <algorithm>
#include <string>
#include <vector>
#include <esp_wifi.h>
#include "esphome/components/wifi/wifi_component.h"

// A scan the Wi-Fi component did not start. ESP-IDF allows one while connected
// (the radio leaves its channel briefly); the component stores the results as
// for its own scans, and keeps every network because the wifi_info
// scan_results sensor asks it to.
inline bool panel_wifi_scan_start() { return esp_wifi_scan_start(nullptr, false) == ESP_OK; }

// Named networks from the last scan, strongest first, each once, one per line.
inline std::string panel_wifi_scan_options(size_t max_count) {
  struct Seen {
    std::string ssid;
    int rssi;
  };
  std::vector<Seen> seen;
  for (const auto &scan : esphome::wifi::global_wifi_component->get_scan_result()) {
    const auto &name = scan.get_ssid();
    std::string ssid(name.c_str(), name.size());
    if (ssid.empty() || ssid.find('\n') != std::string::npos)
      continue;
    auto it = std::find_if(seen.begin(), seen.end(), [&](const Seen &s) { return s.ssid == ssid; });
    if (it == seen.end()) {
      seen.push_back({ssid, scan.get_rssi()});
    } else {
      it->rssi = std::max(it->rssi, (int) scan.get_rssi());
    }
  }
  std::sort(seen.begin(), seen.end(), [](const Seen &a, const Seen &b) { return a.rssi > b.rssi; });
  // What the scan returned, for checking the list against what is really around.
  ESP_LOGI("wifi_page", "Scan: %u results, %u named networks",
           (unsigned) esphome::wifi::global_wifi_component->get_scan_result().size(), (unsigned) seen.size());
  for (const auto &s : seen)
    ESP_LOGI("wifi_page", "  %s %d dBm", s.ssid.c_str(), s.rssi);
  std::string options;
  for (size_t i = 0; i < seen.size() && i < max_count; i++) {
    if (!options.empty())
      options += '\n';
    options += seen[i].ssid;
  }
  return options;
}
