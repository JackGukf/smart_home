"""Tests for the Bridge Sync API router."""
from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.python import bridge_sync
from src.python.bridge_sync import router, register_handlers, update_state_cache, _state_cache


@pytest.fixture(autouse=True)
def clear_state():
    _state_cache.clear()
    bridge_sync._get_devices_fn = None
    bridge_sync._execute_command_fn = None
    yield
    _state_cache.clear()
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


def test_send_command_unknown_device_returns_404(client):
    async def fake_execute(device_id: str, command: str) -> None:
        raise KeyError(device_id)

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)
    resp = client.post("/bridge/command", json={"device_id": "unknown", "command": "on"})
    assert resp.status_code == 404


def test_send_command_device_unreachable_returns_503(client):
    async def fake_execute(device_id: str, command: str) -> None:
        raise RuntimeError("timeout")

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)
    resp = client.post("/bridge/command", json={"device_id": "kasa:x", "command": "on"})
    assert resp.status_code == 503


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
