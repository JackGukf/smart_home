"""Devices overview tile counts follow group re-assignments.

The builtin tiles (Lights, Plugs, Sensors, ...) count from the typed device
lists rather than from resolved group membership, so a device the user moved out
of a group in Manage Devices kept being counted by the tile it left: the tile
said 9 while the panel under it listed 8.

Most front-end tests in this suite assert on the *text* of app.js, because there
is no browser here, and text cannot catch a counting bug. This executes the real
deviceGroupTileData() instead, so it fails on wrong arithmetic rather than on a
phrase disappearing. It skips where Node is unavailable; the deploy already needs
npx to compile app.js, so the tooling is not a new requirement.

tests/python/test_device_groups_ui.py runs Node too, but extracts individual
functions with pick(). That suits testing one function in isolation; the tile
count depends on a dozen collaborators, so this loads the whole file against a
stub DOM rather than listing every dependency and drifting from the real thing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js"

# app.js is a browser script: it wires up listeners at load. The stub only has to
# be inert enough for that to complete - every query returns a chainable no-op.
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
  setInterval: () => 0, setTimeout: () => 0, clearInterval: () => {}, clearTimeout: () => {},
  queueMicrotask: (f) => f(), requestAnimationFrame: () => 0,
  navigator: { userAgent: "node" }, CSS: { escape: (s) => s, supports: () => true },
  Node: { TEXT_NODE: 3 }, EventSource: function () {}, WebSocket: function () {},
  URL, URLSearchParams, Image: function () {},
};
ctx.globalThis = ctx; ctx.self = ctx;
vm.createContext(ctx);
// Listener wiring runs after load and may throw against the stub DOM; the pure
// functions under test are already defined by then.
process.on("uncaughtException", () => {});
process.on("unhandledRejection", () => {});
vm.runInContext(src, ctx, { filename: "app.js" });

// Top-level `let` bindings are lexical, not properties of the vm global, so
// state has to be seeded by running assignments inside the context.
const seed = JSON.parse(process.argv[3]);
vm.runInContext(`latestTuyaDevices = ${JSON.stringify(seed.tuya)};`, ctx);
for (const name of ["latestSwitchDevices", "latestMatterDevices", "latestAmbientLights",
                    "latestHumidifiers", "latestThermostats", "latestEnvironmentSensors",
                    "latestCameras"]) {
  vm.runInContext(`${name} = [];`, ctx);
}
vm.runInContext(`latestDeviceGroups = ${JSON.stringify(seed.groups || [])};`, ctx);
vm.runInContext(`latestDeviceGroupOverrides = ${JSON.stringify(seed.overrides)};`, ctx);

const tile = ctx.deviceGroupTileData().find((t) => t.view === seed.view);
console.log(JSON.stringify({ count: tile.count, summary: tile.summary }));
"""

SENSOR_NAMES = [
    "Motion Sensor&TH", "Motion Sensor&TH 2", "Door Sensor",
    "Water Sensor", "Fire alarm detector", "Temperature and humidity sensor",
    "Smart button", "Family room Motion",
]

# Arrives on the same Tuya feed as the sensors above, but is classified as a
# bridge by rule, so it must not be counted by the Sensors tile.
BRIDGE_NAMES = ["Multi-Mode Gateway"]

BRIDGES_GROUP = [
    {"id": "bridges", "name": "Bridges", "icon": "router", "color": "green",
     "kinds": ["bridge"], "chrome": [], "readingFilter": None, "builtin": False},
]


def _tile(tmp_path: Path, overrides: dict, view: str = "tuya", groups: list | None = None) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available to execute app.js")

    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    seed = {
        "tuya": [
            {"id": f"t{i}", "name": name, "category": "tuya_device", "room": "",
             "online": True, "state": "on"}
            for i, name in enumerate([*SENSOR_NAMES, *BRIDGE_NAMES])
        ],
        "overrides": overrides,
        "groups": groups or [],
        "view": view,
    }
    result = subprocess.run(
        [node, str(harness), str(APP_JS), json.dumps(seed)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"harness failed:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_sensors_tile_counts_every_group_when_nothing_is_reassigned(tmp_path: Path) -> None:
    assert _tile(tmp_path, overrides={})["count"] == len(SENSOR_NAMES)


def test_sensors_tile_drops_a_device_moved_to_another_group(tmp_path: Path) -> None:
    """The reported bug: the tile said 9 while the panel under it listed 8.

    The original report moved Multi-Mode Gateway out of Sensors by hand; the
    gateway is now classified as a bridge by rule, so this drives the same
    override through a device that really is a sensor.
    """
    overrides = {
        "sensor:door-sensor": {"include": ["bridges"], "exclude": ["tuya"]},
    }
    tile = _tile(tmp_path, overrides)
    assert tile["count"] == len(SENSOR_NAMES) - 1
    # The summary counts the same universe, so it has to move in step with the
    # count rather than keeping its own tally.
    assert tile["summary"] == "7 online"


def test_exclusion_from_a_different_group_leaves_the_tile_alone(tmp_path: Path) -> None:
    """Membership is multi-valued: leaving Environment is not leaving Sensors."""
    overrides = {"sensor:door-sensor": {"include": [], "exclude": ["environment"]}}
    assert _tile(tmp_path, overrides)["count"] == len(SENSOR_NAMES)


def test_the_gateway_is_counted_by_bridges_and_not_by_sensors(tmp_path: Path) -> None:
    """A gateway is a radio other devices talk through, not a sensor. It reaches
    the dashboard on the Tuya feed all the same, so the only thing keeping it out
    of the Sensors tile is the bridge rule."""
    assert _tile(tmp_path, {})["count"] == len(SENSOR_NAMES)

    bridges = _tile(tmp_path, {}, view="bridges", groups=BRIDGES_GROUP)
    # The Tuya gateway, plus the Zigbee coordinator, which reaches the dashboard
    # as bridge health rather than on any device list.
    assert bridges["count"] == len(BRIDGE_NAMES) + 1
