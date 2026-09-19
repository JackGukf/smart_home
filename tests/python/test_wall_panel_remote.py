"""The Voice Panel's wall-panel remote: only the wall panel changes view.

The Voice Panel fires a Home Assistant event, esphome.wall_panel_show_view, with
the view to show. The dashboard's event stream forwards it as a show_view frame -
but only on streams from a trusted host, the wall panel. A phone or the PC must
never jump to another view because someone tapped the kitchen panel.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.python import web_app

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


@pytest.mark.parametrize("view", sorted(web_app.WALL_PANEL_VIEWS))
@pytest.mark.asyncio
async def test_each_decided_view_is_forwarded(view: str) -> None:
    feed = Feed()
    feed.queue.put_nowait(_event(web_app.WALL_PANEL_VIEW_EVENT, {"view": view, "device_id": "x"}))
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=1)
    assert frames == [f"event: show_view\ndata: {json.dumps({'view': view})}\n\n"]


def test_the_views_are_the_owners_decision() -> None:
    """Home, Cameras, Security, Devices, Climate and Status - Security is 'alarm' here."""
    assert web_app.WALL_PANEL_VIEWS == {"home", "cameras", "alarm", "devices", "climate", "status"}


@pytest.mark.asyncio
async def test_an_unknown_or_missing_view_is_ignored() -> None:
    feed = Feed()
    for data in ({"view": "zigbee"}, {"view": "../login"}, {}):
        feed.queue.put_nowait(_event(web_app.WALL_PANEL_VIEW_EVENT, data))
    feed.queue.put_nowait(_event("state_changed", {"entity_id": "binary_sensor.door"}))
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=1)
    assert frames and frames[0].startswith("event: changed"), frames


@pytest.mark.asyncio
async def test_a_view_request_does_not_swallow_a_held_change() -> None:
    """A request arriving inside a coalescing window is sent at once, and the
    change being held is still delivered when the window ends."""
    feed = Feed()
    feed.queue.put_nowait(_event("state_changed", {"entity_id": "binary_sensor.door"}))
    feed.queue.put_nowait(_event("state_changed", {"entity_id": "binary_sensor.window"}))
    feed.queue.put_nowait(_event(web_app.WALL_PANEL_VIEW_EVENT, {"view": "cameras"}))
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=3)
    assert frames[0].startswith("event: changed") and "door" in frames[0]
    assert frames[1].startswith("event: show_view") and "cameras" in frames[1]
    assert frames[2].startswith("event: changed") and "window" in frames[2]


# --- who follows -------------------------------------------------------------

def _client(tmp_path: Path, monkeypatch, client_host: str, calls: list) -> TestClient:
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "home_assistant": {"base_url": "http://127.0.0.1:8123"},
        "dashboard_auth": {"username": "user", "password": "pass", "trusted_hosts": [KIOSK]},
    }), encoding="utf-8")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    async def fake_stream(config, token, before_notify=None, follow_wall_panel=False, follow_tv_cast=False):
        calls.append(follow_wall_panel)
        yield "event: ready\ndata: {}\n\n"

    monkeypatch.setattr(web_app, "_home_assistant_event_stream", fake_stream)
    app = web_app.create_app(config_path=cfg, check_camera_ports=False)
    return TestClient(app, follow_redirects=False, client=(client_host, 40000))


def test_the_wall_panels_stream_follows_view_requests(tmp_path, monkeypatch) -> None:
    calls: list = []
    client = _client(tmp_path, monkeypatch, KIOSK, calls)
    with client.stream("GET", "/api/events/stream") as response:
        assert response.status_code == 200
        "".join(response.iter_text())
    assert calls == [True]


def test_a_logged_in_pc_does_not_follow_view_requests(tmp_path, monkeypatch) -> None:
    calls: list = []
    client = _client(tmp_path, monkeypatch, PC, calls)
    login = client.post("/login", data={"username": "user", "password": "pass"})
    assert login.status_code in (302, 303)
    with client.stream("GET", "/api/events/stream") as response:
        assert response.status_code == 200
        "".join(response.iter_text())
    assert calls == [False]



# --- the TV cast's remote ----------------------------------------------------

def _tv_client(tmp_path: Path, monkeypatch, client_host: str, calls: list) -> TestClient:
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "home_assistant": {"base_url": "http://127.0.0.1:8123"},
        "dashboard_auth": {"username": "user", "password": "pass", "trusted_hosts": [KIOSK]},
    }), encoding="utf-8")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    async def fake_stream(config, token, before_notify=None, follow_wall_panel=False, follow_tv_cast=False):
        calls.append((follow_wall_panel, follow_tv_cast))
        yield "event: ready\ndata: {}\n\n"

    monkeypatch.setattr(web_app, "_home_assistant_event_stream", fake_stream)
    app = web_app.create_app(config_path=cfg, check_camera_ports=False)
    client = TestClient(app, follow_redirects=False, client=(client_host, 40000))
    from src.python import dashboard_cast
    client.cookies.set("session", dashboard_cast.session_cookie(cfg))
    return client


def test_the_casts_browser_follows_the_tv_remote(tmp_path, monkeypatch) -> None:
    calls: list = []
    client = _tv_client(tmp_path, monkeypatch, "127.0.0.1", calls)
    with client.stream("GET", "/api/events/stream?screen=tv") as response:
        "".join(response.iter_text())
    assert calls == [(False, True)]


def test_a_phone_asking_to_be_the_tv_is_not(tmp_path, monkeypatch) -> None:
    calls: list = []
    client = _tv_client(tmp_path, monkeypatch, "192.168.0.50", calls)
    with client.stream("GET", "/api/events/stream?screen=tv") as response:
        "".join(response.iter_text())
    assert calls == [(False, False)]


def test_the_board_without_screen_tv_follows_nothing(tmp_path, monkeypatch) -> None:
    calls: list = []
    client = _tv_client(tmp_path, monkeypatch, "127.0.0.1", calls)
    with client.stream("GET", "/api/events/stream") as response:
        "".join(response.iter_text())
    assert calls == [(False, False)]


def test_only_the_board_can_name_the_tvs_camera(tmp_path, monkeypatch) -> None:
    posted: list = []
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda config, token, path, body: posted.append((path, body)))
    phone = _tv_client(tmp_path, monkeypatch, "192.168.0.50", [])
    assert phone.post("/api/tv-cast/camera", json={"name": "Garage camera"}).json() == {"status": "ignored"}
    assert posted == []

    board = _tv_client(tmp_path, monkeypatch, "127.0.0.1", [])
    assert board.post("/api/tv-cast/camera", json={"name": "Front  door camera"}).json()["name"] == "Front door camera"
    assert posted[0][0] == "/api/states/sensor.tv_cast_camera"


def test_the_tvs_events_become_the_same_frames_as_the_wall_panels() -> None:
    assert web_app._TV_CAST_FRAMES[web_app.TV_CAST_VIEW_EVENT]({"view": "cameras"}) == \
        web_app._WALL_PANEL_FRAMES[web_app.WALL_PANEL_VIEW_EVENT]({"view": "cameras"})
    assert web_app._TV_CAST_FRAMES[web_app.TV_CAST_VIEW_EVENT]({"view": "settings"}) is None
    assert web_app._TV_CAST_FRAMES[web_app.TV_CAST_SCROLL_EVENT]({"direction": "sideways"}) is None
    assert set(web_app._TV_CAST_FRAMES).isdisjoint(web_app._WALL_PANEL_FRAMES)
