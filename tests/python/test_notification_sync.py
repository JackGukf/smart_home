"""New-device banners follow the server, and can never fill the screen.

Closing a "new device" banner on the PC told the server (POST .../ignore), but
each browser keeps its own banners in memory. The wall panel never reloads, so
it kept every banner it had ever been shown - and after a few devices joined in
one evening they covered the whole panel.

Like tests/python/test_device_group_counts.py, this executes the real app.js in
Node against a stub DOM instead of asserting on its text, because the bug is in
behaviour: what is left after a refresh, and how much is shown. It skips where
Node is unavailable.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

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
process.on("uncaughtException", () => {});
process.on("unhandledRejection", () => {});
vm.runInContext(src, ctx, { filename: "app.js" });

// Top-level bindings of app.js are shared by later scripts in the same context.
const seed = JSON.parse(process.argv[3]);
const out = vm.runInContext(`(() => {
  const s = ${JSON.stringify(seed)};
  const ids = (list) => list.map((n) => n.entityId || n.type);
  for (const n of s.push) pushNotification(n.type, n.title || n.type, "message", n.meta || {});
  const changed = [];
  for (const round of s.refreshes || []) {
    changed.push(syncNewDeviceNotifications(round));
    notifySeenNewHomeAssistantDevices(round);
  }
  const all = [...notifMap.values()];
  const view = notificationsToShow(all);
  return { changed, remaining: ids(all), shown: ids(view.shown), hidden: view.hiddenNewDevices,
           markup: notificationsMarkup(all) };
})()`, ctx);
console.log(JSON.stringify(out));
"""


def _new(entity_id: str) -> dict:
    return {"type": "new_device", "title": f"New device found: {entity_id}",
            "meta": {"entityId": entity_id, "eventKey": entity_id}}


def _entity(entity_id: str, is_new: bool) -> dict:
    return {"entity_id": entity_id, "name": entity_id, "domain": entity_id.split(".")[0], "is_new": is_new}


def _run(tmp_path: Path, seed: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available to execute app.js")
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    result = subprocess.run([node, str(harness), str(APP_JS), json.dumps(seed)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, f"harness failed:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_a_banner_closed_on_another_screen_disappears_on_the_next_refresh(tmp_path: Path) -> None:
    """The panel's case: it still holds banners the PC already closed."""
    out = _run(tmp_path, {
        "push": [_new("switch.raspberry_pi"), _new("switch.living_room_cabinet_led")],
        "refreshes": [[_entity("switch.raspberry_pi", False), _entity("switch.living_room_cabinet_led", True)]],
    })
    assert out["remaining"] == ["switch.living_room_cabinet_led"]
    assert out["changed"] == [True]


def test_a_dropped_banner_is_not_pushed_again(tmp_path: Path) -> None:
    out = _run(tmp_path, {
        "push": [_new("switch.raspberry_pi")],
        "refreshes": [[_entity("switch.raspberry_pi", False)], [_entity("switch.raspberry_pi", False)]],
    })
    assert out["remaining"] == []


def test_home_assistant_being_unreachable_does_not_clear_banners(tmp_path: Path) -> None:
    """An empty entity list is an outage, not "nothing is new"."""
    out = _run(tmp_path, {"push": [_new("switch.raspberry_pi")], "refreshes": [[]]})
    assert out["remaining"] == ["switch.raspberry_pi"]
    assert out["changed"] == [False]


def test_other_banners_are_never_touched_by_the_sync(tmp_path: Path) -> None:
    out = _run(tmp_path, {
        "push": [{"type": "fire", "meta": {"deviceId": "smoke"}}, _new("switch.raspberry_pi")],
        "refreshes": [[_entity("switch.raspberry_pi", False)]],
    })
    assert out["remaining"] == ["fire"]


def test_new_device_banners_are_capped_and_the_rest_collapse(tmp_path: Path) -> None:
    entity_ids = [f"switch.plug_{i}" for i in range(6)]
    out = _run(tmp_path, {"push": [_new(e) for e in entity_ids]})
    assert out["shown"] == entity_ids[:2]
    assert out["hidden"] == 4
    assert "+4 more new devices" in out["markup"]
    assert 'data-notif-dismiss-new="all"' in out["markup"]
    assert out["markup"].count("notif-banner") == 3


def test_urgent_banners_always_show_even_with_many_new_devices(tmp_path: Path) -> None:
    out = _run(tmp_path, {"push": [*[_new(f"switch.plug_{i}") for i in range(5)],
                                   {"type": "alarm", "meta": {"eventKey": "sos"}}]})
    assert "alarm" in out["shown"]
    assert out["hidden"] == 3


def test_no_more_line_when_everything_fits(tmp_path: Path) -> None:
    out = _run(tmp_path, {"push": [_new("switch.plug_1")]})
    assert out["hidden"] == 0
    assert "more new device" not in out["markup"]


def test_dismiss_all_tells_the_server_about_every_new_device() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    handler = source.split('closest("button[data-notif-dismiss-new]")', 1)[1].split("return;", 1)[0]
    assert "/ignore" in handler and 'notif.type !== "new_device"' in handler
    assert "renderNotifications()" in handler


def test_the_banner_area_cannot_take_the_whole_screen() -> None:
    css = STYLES.read_text(encoding="utf-8")
    block = re.search(r"\.notif-area\s*\{([^}]*)\}", css).group(1)
    assert "max-height: 40vh" in block
    assert "overflow-y: auto" in block
