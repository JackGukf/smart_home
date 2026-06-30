"""Tests for the Bridge Sync API router."""
from __future__ import annotations
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.python import bridge_sync
from src.python.bridge_sync import router, register_handlers, update_state_cache, _state_cache


@pytest.fixture(autouse=True)
def clear_state():
    _state_cache.clear()
    bridge_sync._pending_until.clear()
    bridge_sync._get_devices_fn = None
    bridge_sync._execute_command_fn = None
    yield
    _state_cache.clear()
    bridge_sync._pending_until.clear()
    bridge_sync._get_devices_fn = None
    bridge_sync._execute_command_fn = None


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_state_all_empty(client):
    resp = client.get("/bridge/state/all")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_update_state_cache_visible_in_state_all(client):
    update_state_cache("kasa:192.168.1.10", {"on": True})
    resp = client.get("/bridge/state/all")
    assert resp.status_code == 200
    assert resp.json() == {"kasa:192.168.1.10": {"on": True}}


def test_send_command_unknown_device_returns_200_immediately(client):
    # /bridge/command always returns 200 immediately so the C++ bridge's
    # synchronous HTTP call returns without blocking the Matter event loop.
    # Errors (unknown device, timeout) are logged but NOT returned as HTTP
    # error codes — the bridge already sent a Success InvokeResponse to Apple Home.
    async def fake_execute(device_id: str, command: str) -> None:
        raise KeyError(device_id)

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)
    resp = client.post("/bridge/command", json={"device_id": "unknown", "command": "on"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_send_command_device_unreachable_returns_200_immediately(client):
    async def fake_execute(device_id: str, command: str) -> None:
        raise RuntimeError("timeout")

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)
    resp = client.post("/bridge/command", json={"device_id": "kasa:x", "command": "on"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_devices_returns_bridge_device_list(client):
    async def fake_get() -> list:
        return [
            {
                "device_id": "kasa:192.168.1.10",
                "name": "Living Room",
                "room": "Living Room",
                "category": "light_switch",
                "dimmable": False,
                "state": {"on": False},
            }
        ]

    register_handlers(get_devices_fn=fake_get, execute_command_fn=None)
    resp = client.get("/bridge/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["device_id"] == "kasa:192.168.1.10"
    assert data[0]["category"] == "light_switch"


# ── Regression test for the toggle-then-"No Response" bug ──────────────────
# Root cause: a command from Apple Home reports its new value optimistically,
# but the physical device takes time to actually flip. If a concurrent status
# read (the C++ bridge's periodic device rescan, or the dashboard polling
# /api/devices) lands on the *pre-command* value while the command is still
# in flight, it used to clobber _state_cache. The next 10s poll tick would
# then report the device flipping back to its old state right after the user
# toggled it, which is exactly the kind of self-contradicting report that
# makes Matter controllers mark an accessory "No Response".


def test_send_command_marks_pending_so_concurrent_status_read_is_dropped(client):
    async def fake_execute(device_id: str, command: str) -> None:
        return None

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)

    resp = client.post("/bridge/command", json={"device_id": "kasa:1.2.3.4", "command": "on"})
    assert resp.status_code == 200

    # Simulates a concurrent rescan/dashboard poll reading the device's
    # pre-command status while the command above is still "in flight".
    update_state_cache("kasa:1.2.3.4", {"on": False})

    assert _state_cache.get("kasa:1.2.3.4") is None, (
        "a plain (non-authoritative) status read landed inside the pending "
        "window and clobbered the cache with the stale pre-command value"
    )


def test_authoritative_update_always_wins_and_clears_pending(client):
    bridge_sync.mark_command_pending("kasa:1.2.3.4")
    update_state_cache("kasa:1.2.3.4", {"on": True}, authoritative=True)
    assert _state_cache["kasa:1.2.3.4"] == {"on": True}

    # Pending window is cleared, so a subsequent plain read is no longer dropped.
    update_state_cache("kasa:1.2.3.4", {"on": False})
    assert _state_cache["kasa:1.2.3.4"] == {"on": False}


def test_pending_window_expires(client):
    bridge_sync.mark_command_pending("kasa:1.2.3.4")
    bridge_sync._pending_until["kasa:1.2.3.4"] = time.monotonic() - 1  # force-expire
    update_state_cache("kasa:1.2.3.4", {"on": False})
    assert _state_cache["kasa:1.2.3.4"] == {"on": False}
