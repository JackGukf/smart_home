"""The Voice Panel's remote, beyond views: scroll the wall panel, step its camera.

  * each command is its own Home Assistant event, forwarded to the wall panel
    only after its value is checked against a fixed list;
  * the wall panel's stream subscribes to all three and learns it is the wall
    panel, so only it reports which camera its Home card shows;
  * that report is heard only from the wall panel, and becomes a Home
    Assistant state the Voice Panel shows between its arrows;
  * the firmware sends exactly these events, and the page still fits 480 px.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.python import web_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
PANEL = PROJECT_ROOT / "configs" / "esphome" / "voice-panel.yaml"
BUTTON = PROJECT_ROOT / "configs" / "esphome" / "panel" / "wall-button.yaml"
KIOSK = "192.168.0.176"
PC = "192.168.0.99"


def _event(event_type: str, data: dict) -> dict:
    return {"type": "event", "event": {"event_type": event_type, "data": data}}


class Feed:
    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()

    async def receive(self, timeout: float) -> dict:
        return await asyncio.wait_for(self.queue.get(), timeout=timeout)


async def _frames(gen, count: int, within: float = 1.0) -> list[str]:
    out: list[str] = []

    async def take() -> None:
        async for frame in gen:
            out.append(frame)
            if len(out) >= count:
                return

    try:
        await asyncio.wait_for(take(), within)
    except (asyncio.TimeoutError, TimeoutError):
        pass
    return out


@pytest.fixture(autouse=True)
def fast_windows(monkeypatch):
    monkeypatch.setattr(web_app, "_EVENT_COALESCE_SECONDS", 0.1)
    monkeypatch.setattr(web_app, "_EVENT_KEEPALIVE_SECONDS", 5.0)


@pytest.mark.asyncio
async def test_scroll_and_camera_commands_are_forwarded() -> None:
    feed = Feed()
    feed.queue.put_nowait(_event(web_app.WALL_PANEL_SCROLL_EVENT, {"direction": "down"}))
    feed.queue.put_nowait(_event(web_app.WALL_PANEL_CAMERA_EVENT, {"step": "next"}))
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=2)
    assert frames == ['event: wall_scroll\ndata: {"direction": "down"}\n\n',
                      'event: wall_camera\ndata: {"step": "next"}\n\n']


@pytest.mark.asyncio
async def test_anything_else_is_dropped() -> None:
    feed = Feed()
    for event, data in ((web_app.WALL_PANEL_SCROLL_EVENT, {"direction": "sideways"}),
                        (web_app.WALL_PANEL_SCROLL_EVENT, {}),
                        (web_app.WALL_PANEL_CAMERA_EVENT, {"step": "garage"}),
                        (web_app.WALL_PANEL_CAMERA_EVENT, {"step": "<script>"})):
        feed.queue.put_nowait(_event(event, data))
    feed.queue.put_nowait(_event("state_changed", {"entity_id": "binary_sensor.door"}))
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=1)
    assert frames and frames[0].startswith("event: changed"), frames


@pytest.mark.asyncio
async def test_the_wall_panels_stream_subscribes_to_every_command_and_says_so(monkeypatch) -> None:
    sent: list[dict] = []

    class WS:
        def __init__(self):
            self.inbox = [{"type": "auth_required"}, {"type": "auth_ok"}, {"id": 1, "success": True}]

        async def receive_json(self):
            if self.inbox:
                return self.inbox.pop(0)
            await asyncio.sleep(10)

        async def send_json(self, message):
            sent.append(message)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class Session:
        def ws_connect(self, url, heartbeat):
            return WS()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", Session)
    config = web_app.HomeAssistantConfig(base_url="http://ha", token_env="T", include_domains=())
    frames = await _frames(web_app._home_assistant_event_stream(config, "token", follow_wall_panel=True), count=2)

    subscribed = {m["event_type"] for m in sent if m.get("type") == "subscribe_events"}
    assert subscribed == {"state_changed", web_app.WALL_PANEL_VIEW_EVENT,
                          web_app.WALL_PANEL_SCROLL_EVENT, web_app.WALL_PANEL_CAMERA_EVENT}
    assert frames == ["event: ready\ndata: {}\n\n", "event: wall_panel\ndata: {}\n\n"]


def _client(tmp_path: Path, monkeypatch, host: str, posted: list) -> TestClient:
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "home_assistant": {"base_url": "http://127.0.0.1:8123"},
        "dashboard_auth": {"username": "user", "password": "pass", "trusted_hosts": [KIOSK]},
    }), encoding="utf-8")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda config, token, path, body: posted.append((path, body)))
    return TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False),
                      follow_redirects=False, client=(host, 40000))


def test_only_the_wall_panel_can_name_its_camera(tmp_path, monkeypatch) -> None:
    posted: list = []
    kiosk = _client(tmp_path, monkeypatch, KIOSK, posted)
    assert kiosk.post("/api/wall-panel/camera", json={"name": "  Garage   camera "}).json() == {"status": "ok", "name": "Garage camera"}
    assert posted == [("/api/states/sensor.wall_panel_camera",
                       {"state": "Garage camera", "attributes": {"friendly_name": "Wall panel camera", "icon": "mdi:cctv"}})]

    pc = _client(tmp_path, monkeypatch, PC, posted)
    pc.post("/login", data={"username": "user", "password": "pass"})
    assert pc.post("/api/wall-panel/camera", json={"name": "Office camera"}).json() == {"status": "ignored"}
    assert len(posted) == 1
    assert kiosk.post("/api/wall-panel/camera", json={"name": "x" * 200}).status_code == 422


def test_the_firmware_sends_these_events_and_the_page_fits() -> None:
    panel = PANEL.read_text(encoding="utf-8")
    button = BUTTON.read_text(encoding="utf-8")
    start = panel.index("- id: wall_page")
    page = panel[start:panel.index("- id: settings_page", start)]

    sends = set(re.findall(r"event: (esphome\.wall_panel_\w+), field: (\w+), value: (\w+)", page))
    assert sends == {("esphome.wall_panel_scroll", "direction", "up"), ("esphome.wall_panel_scroll", "direction", "down"),
                     ("esphome.wall_panel_camera", "step", "prev"), ("esphome.wall_panel_camera", "step", "next")}
    for _, field, value in sends:
        allowed = web_app.WALL_PANEL_SCROLLS if field == "direction" else web_app.WALL_PANEL_CAMERA_STEPS
        assert value in allowed, "the firmware must send what the dashboard accepts"
    assert "homeassistant.event:" in button and "${field}: ${value}" in button

    # Every button row (54px tall) ends above the bottom of the 480px screen.
    for y in re.findall(r"wall-button\.yaml, vars: \{[^}]*y: (\d+),", page):
        assert int(y) + 54 <= 480
    assert "entity_id: sensor.wall_panel_camera" in panel and "id: wall_camera_name" in page


HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
};
for (const line of src.match(/const WALL_PANEL_(SCROLLS|CAMERA_STEPS) = [^;]+;/g)) eval(line.replace('const ', 'globalThis.'));
const options = [{ value: 'a' }, { value: 'b' }, { value: 'c' }];
const select = { options, selectedIndex: 2, dispatched: 0, dispatchEvent() { this.dispatched++; } };
let activated = null;
globalThis.Event = class { constructor(type) { this.type = type; } };
globalThis.activateView = (v) => { activated = v; };
globalThis.document = { querySelector: (q) => (q === '#homeCameraSelect' ? select : null) };
eval(pick('wallPanelField') + pick('stepHomeCamera'));
stepHomeCamera('next');
const afterNext = select.selectedIndex;
stepHomeCamera('prev');
console.log(JSON.stringify({
  fields: [wallPanelField('{"direction":"down"}', 'direction', WALL_PANEL_SCROLLS),
           wallPanelField('{"direction":"left"}', 'direction', WALL_PANEL_SCROLLS),
           wallPanelField('not json', 'step', WALL_PANEL_CAMERA_STEPS)],
  afterNext, afterPrev: select.selectedIndex, dispatched: select.dispatched, activated,
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_wall_panel_obeys_and_wraps_around(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result["fields"] == ["down", None, None]
    assert result["afterNext"] == 0 and result["afterPrev"] == 2, "wraps both ways"
    assert result["dispatched"] == 2 and result["activated"] == "home"


def test_the_remotes_state_is_declared_before_startup_reads_it() -> None:
    """renderHomeCamera runs during start-up and reads isWallPanel; declared any
    later, the first render throws and the page never finishes loading."""
    js = APP_JS.read_text(encoding="utf-8")
    assert js.index("let isWallPanel = false;") < js.index("function renderHomeCamera(")
    assert js.index("let isWallPanel = false;") < js.index("activateView(initialView);")
