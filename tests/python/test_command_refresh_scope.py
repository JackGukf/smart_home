"""A command refreshes the source it addressed, not all nine of them.

loadDevices() fans out to nine endpoints and Promise.all-waits for the slowest.
Measured on the Orange Pi with warm caches:

    /api/tuya/devices            2930 ms   (Tuya cloud)
    /api/weather                  931 ms
    /api/ecobee/thermostats       106 ms
    /api/matter/devices             5 ms
    /api/devices                    3 ms   (cached)

so every Stick S3 toggle -- a 5 ms device -- waited on Tuya's cloud before the
card settled, which is why the dashboard felt seconds behind the Home app for
the same light. These run the real functions under Node against a stubbed
fetch, so they fail on a reintroduced fan-out rather than on a phrase changing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js"

HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
const noop = new Proxy(function () {}, {
  get: (t, k) => (k === "then" ? undefined : noop),
  apply: () => noop, set: () => true, has: () => true,
});
const ctx = {
  console,
  document: {
    querySelector: () => noop, querySelectorAll: () => [], addEventListener: () => {},
    createElement: () => noop, body: noop,
    documentElement: {
      classList: { contains: () => false, add: () => {}, remove: () => {}, toggle: () => {} },
      className: "", style: { setProperty: () => {}, removeProperty: () => {} }, dataset: {},
    },
  },
  window: {
    location: { hostname: "board.local", protocol: "http:", search: "", pathname: "/" },
    addEventListener: () => {},
    matchMedia: () => ({ matches: false, addListener() {}, addEventListener() {} }),
  },
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
  setInterval: () => 0, setTimeout: (f) => { f(); return 0; },
  clearInterval: () => {}, clearTimeout: () => {},
  queueMicrotask: (f) => f(), requestAnimationFrame: () => 0,
  navigator: { userAgent: "node" }, CSS: { escape: (s) => s, supports: () => true },
  Node: { TEXT_NODE: 3 }, EventSource: function () {}, WebSocket: function () {},
  URL, URLSearchParams, Image: function () {}, Date,
};
ctx.globalThis = ctx; ctx.self = ctx;
vm.createContext(ctx);
process.on("uncaughtException", () => {});
process.on("unhandledRejection", () => {});
vm.runInContext(src, ctx, { filename: "app.js" });

// Record every endpoint the code under test asks for.
const asked = [];
ctx.requestJson = (url) => {
  asked.push(String(url).split("?")[0]);
  if (String(url).startsWith("/api/matter/devices")) {
    return Promise.resolve({ devices: [], matter_online: true });
  }
  return Promise.resolve({ devices: [], entities: [], cameras: [], thermostats: [] });
};
// Rendering is not what these assert on, and it wants a real DOM.
for (const fn of ["renderDevices", "renderDevicesOverview", "renderHomeView",
                  "refreshActiveDynamicGroupPanel", "renderTuyaDevices",
                  "_updateMatterServerStatus", "_renderMatterDeviceList",
                  "logActivity"]) {
  ctx[fn] = () => {};
}

const scenario = process.argv[3];
(async () => {
  if (scenario === "matter") {
    await ctx.refreshDeviceSource("matter:1");
  } else if (scenario === "switch") {
    await ctx.refreshDeviceSource("192.168.0.110");
  } else if (scenario === "ha") {
    await ctx.refreshDeviceSource("ha:light.kitchen");
  } else if (scenario === "fallback") {
    ctx.requestJson = (url) => {
      asked.push(String(url).split("?")[0]);
      if (String(url).startsWith("/api/matter/devices")) return Promise.reject(new Error("boom"));
      return Promise.resolve({ devices: [], entities: [], cameras: [], thermostats: [] });
    };
    await ctx.refreshDeviceSource("matter:1");
  } else if (scenario === "patch") {
    vm.runInContext("latestMatterDevices = [{ host: 'matter:1', name: 'Stick S3', is_on: false, brightness: 10 }];", ctx);
    ctx.patchLocalDeviceState("matter:1", { is_on: true, brightness: 70 });
    const out = vm.runInContext("JSON.stringify(latestMatterDevices)", ctx);
    console.log(JSON.stringify({ asked, devices: JSON.parse(out) }));
    return;
  }
  console.log(JSON.stringify({ asked }));
})();
"""

SLOW = ["/api/tuya/devices", "/api/weather", "/api/ecobee/thermostats", "/api/cameras"]


def _run(tmp_path: Path, scenario: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available to execute app.js")
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(APP_JS), scenario],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"harness failed:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_a_matter_command_reads_only_the_matter_endpoint(tmp_path: Path) -> None:
    """The Stick S3 case: 5 ms of work must not wait on 2.9 s of Tuya cloud."""
    asked = _run(tmp_path, "matter")["asked"]

    assert asked == ["/api/matter/devices"]
    assert not [url for url in asked if url in SLOW]


def test_a_switch_command_reads_only_the_cached_device_list(tmp_path: Path) -> None:
    asked = _run(tmp_path, "switch")["asked"]

    assert asked == ["/api/devices"]


def test_a_home_assistant_command_reads_the_device_list(tmp_path: Path) -> None:
    """/api/devices merges the Home Assistant cards in with the TP-Link ones,
    so an "ha:" host is served by the same endpoint."""
    asked = _run(tmp_path, "ha")["asked"]

    assert asked == ["/api/devices"]


def test_a_failed_targeted_read_falls_back_to_the_full_refresh(tmp_path: Path) -> None:
    """Better a slow correct repaint than a card left showing an optimistic
    value that nothing confirmed."""
    asked = _run(tmp_path, "fallback")["asked"]

    assert asked[0] == "/api/matter/devices"
    assert "/api/tuya/devices" in asked, "expected the loadDevices() fan-out as a fallback"


def test_the_local_model_is_patched_with_what_was_commanded(tmp_path: Path) -> None:
    """Brightness turns a Matter light on as a side effect, and the server can
    report the new level a beat after the command returns. Without this the card
    snaps back to the old value before settling."""
    devices = _run(tmp_path, "patch")["devices"]

    assert devices[0]["is_on"] is True
    assert devices[0]["brightness"] == 70
