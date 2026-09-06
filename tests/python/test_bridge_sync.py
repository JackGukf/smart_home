"""Tests for the Bridge Sync API router."""
from __future__ import annotations
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.python import bridge_sync
from src.python.bridge_sync import router, register_handlers, update_state_cache, cached_state_for, _state_cache


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


def test_cached_state_for_returns_copy(client):
    update_state_cache("kasa:192.168.1.10", {"on": True})

    state = cached_state_for("kasa:192.168.1.10")
    assert state == {"on": True}
    state["on"] = False

    assert _state_cache["kasa:192.168.1.10"] == {"on": True}


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


def _three_devices() -> list:
    return [
        {"device_id": "kasa:192.168.0.110", "name": "Kitchen light switch",
         "room": "Kitchen", "category": "light_switch", "dimmable": False,
         "state": {"on": True}},
        {"device_id": "kasa:192.168.0.143", "name": "Master bedroom light",
         "room": "Master Bedroom", "category": "light_switch", "dimmable": False,
         "state": {"on": False}},
        {"device_id": "kasa:192.168.0.61", "name": "Family room switch",
         "room": "Family Room", "category": "light_switch", "dimmable": False,
         "state": {"on": False}},
    ]


def test_list_devices_respects_the_allowlist(client, monkeypatch):
    """The device list *is* the Matter endpoint topology: the C++ bridge
    registers one dynamic endpoint per entry. Apple Home tolerates state
    changing under a commissioned bridge but not the endpoint set changing --
    it answers that with No Response.

    web_app._bridge_device_list() already applies the allowlist before handing
    the list over; this pins the same invariant at the router boundary, so a
    future get_devices_fn that forgets cannot widen the endpoint set.
    """
    monkeypatch.setenv(
        "BRIDGE_DEVICE_ALLOWLIST", "kasa:192.168.0.110,kasa:192.168.0.61"
    )

    async def fake_get() -> list:
        return _three_devices()

    register_handlers(get_devices_fn=fake_get, execute_command_fn=None)
    data = client.get("/bridge/devices").json()

    assert [d["device_id"] for d in data] == [
        "kasa:192.168.0.110",
        "kasa:192.168.0.61",
    ]


def test_list_devices_returns_everything_when_no_allowlist_is_set(client, monkeypatch):
    """An unset allowlist must stay "expose everything", not "expose nothing" --
    the bridge would otherwise register zero endpoints on a normal install."""
    monkeypatch.delenv("BRIDGE_DEVICE_ALLOWLIST", raising=False)

    async def fake_get() -> list:
        return _three_devices()

    register_handlers(get_devices_fn=fake_get, execute_command_fn=None)

    assert len(client.get("/bridge/devices").json()) == 3


def test_an_empty_allowlist_is_treated_as_unset(client, monkeypatch):
    """A blank or whitespace value in .env must not silently unregister every
    endpoint on the next bridge restart."""
    monkeypatch.setenv("BRIDGE_DEVICE_ALLOWLIST", "   ")

    async def fake_get() -> list:
        return _three_devices()

    register_handlers(get_devices_fn=fake_get, execute_command_fn=None)

    assert len(client.get("/bridge/devices").json()) == 3


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


def test_state_all_can_be_filtered_to_exposed_devices(client):
    update_state_cache("kasa:192.168.0.73", {"on": True})
    update_state_cache("kasa:192.168.0.51", {"on": False})

    resp = client.get("/bridge/state/all?device_id=kasa:192.168.0.73")

    assert resp.status_code == 200
    assert resp.json() == {"kasa:192.168.0.73": {"on": True}}


def test_state_cache_ignores_non_allowlisted_devices(client, monkeypatch):
    monkeypatch.setenv("BRIDGE_DEVICE_ALLOWLIST", "kasa:192.168.0.73")

    update_state_cache("kasa:192.168.0.73", {"on": True})
    update_state_cache("kasa:192.168.0.51", {"on": False})

    resp = client.get("/bridge/state/all")

    assert resp.status_code == 200
    assert resp.json() == {"kasa:192.168.0.73": {"on": True}}
    assert set(_state_cache) == {"kasa:192.168.0.73"}


# ── Matter devices re-exposed through the bridge ──────────────────────────────

def test_matter_device_reaches_the_bridge_list(monkeypatch):
    """The Stick S3 is commissioned into the dashboard's own controller, which is
    a different fabric from the one the bridge serves. Bridging it is how it
    reaches Apple Home without being commissioned there directly."""
    import src.python.web_app as web_app

    monkeypatch.setattr(web_app, "_matter_device_meta",
                        {1: {"name": "Stick S3", "room": "Office"}})
    monkeypatch.setenv("BRIDGE_DEVICE_ALLOWLIST", "matter:1")

    import asyncio
    devices = asyncio.run(web_app._bridge_device_list())

    assert [d["device_id"] for d in devices] == ["matter:1"]
    assert devices[0]["name"] == "Stick S3"
    # light_switch is what DeviceMapper turns into an OnOffLight endpoint.
    assert devices[0]["category"] == "light_switch"


def test_matter_command_is_routed_and_cached_authoritatively(monkeypatch):
    """A command must update the cache authoritatively, or the next poll can
    overwrite it with a stale read and Apple Home shows the old state."""
    import src.python.web_app as web_app
    import asyncio

    sent = []

    class _FakeClient:
        async def send_command(self, node_id, command, brightness=None):
            sent.append((node_id, command))

    monkeypatch.setattr(web_app, "_matter_client", _FakeClient())
    monkeypatch.setenv("BRIDGE_DEVICE_ALLOWLIST", "matter:1")

    asyncio.run(web_app._bridge_execute_command("matter:1", "on"))

    assert sent == [(1, "on")]
    assert cached_state_for("matter:1") == {"on": True}


def test_a_malformed_matter_id_raises_keyerror_not_valueerror(monkeypatch):
    """/bridge/command turns KeyError into "unknown device"; an uncaught
    ValueError from int() would surface as a 500 instead."""
    import src.python.web_app as web_app
    import asyncio

    with pytest.raises(KeyError):
        asyncio.run(web_app._bridge_execute_command("matter:not-a-number", "on"))


# ── Endpoint pinning ──────────────────────────────────────────────────────────
#
# The endpoint number *is* the accessory identity to a Matter controller, so it
# must not move when the device list changes. Before this, endpoints came from
# position in the list: adding a Kasa switch that sat earlier in
# tplink_switches.json inserted it mid-list and shifted every endpoint after it.

def test_endpoints_are_pinned_and_survive_an_insertion(tmp_path):
    import src.python.web_app as web_app

    path = tmp_path / "bridge_endpoints.json"
    first = web_app._assign_bridge_endpoints(["kasa:a", "kasa:b", "matter:1"], path)
    assert first == {"kasa:a": 3, "kasa:b": 4, "matter:1": 5}

    # A device that would sort into the middle must not displace anyone.
    second = web_app._assign_bridge_endpoints(
        ["kasa:a", "kasa:INSERTED", "kasa:b", "matter:1"], path
    )
    assert second["kasa:a"] == 3
    assert second["kasa:b"] == 4
    assert second["matter:1"] == 5
    assert second["kasa:INSERTED"] == 6, "a new device takes the lowest free endpoint"


def test_removing_a_device_does_not_renumber_the_others(tmp_path):
    import src.python.web_app as web_app

    path = tmp_path / "bridge_endpoints.json"
    web_app._assign_bridge_endpoints(["kasa:a", "kasa:b", "kasa:c"], path)
    after = web_app._assign_bridge_endpoints(["kasa:a", "kasa:c"], path)

    assert after == {"kasa:a": 3, "kasa:c": 5}, "c keeps 5; it does not slide into 4"

    # The freed endpoint is available again for something new.
    later = web_app._assign_bridge_endpoints(["kasa:a", "kasa:c", "kasa:new"], path)
    assert later["kasa:new"] == 4


def test_assignments_survive_a_restart(tmp_path):
    """They are only stable if they are persisted -- an in-memory map would
    renumber everything the next time the dashboard restarted."""
    import src.python.web_app as web_app

    path = tmp_path / "bridge_endpoints.json"
    web_app._assign_bridge_endpoints(["kasa:a", "kasa:b"], path)
    assert path.exists()
    assert web_app._load_bridge_endpoints(path) == {"kasa:a": 3, "kasa:b": 4}


def test_a_corrupt_assignment_file_does_not_break_the_bridge(tmp_path):
    import src.python.web_app as web_app

    path = tmp_path / "bridge_endpoints.json"
    path.write_text("not json", encoding="utf-8")

    assert web_app._assign_bridge_endpoints(["kasa:a"], path) == {"kasa:a": 3}


def test_running_out_of_endpoints_is_survivable(tmp_path):
    """16 slots. The 17th device gets none rather than an out-of-range endpoint
    the bridge would refuse -- and the bridge logs what it could not register."""
    import src.python.web_app as web_app

    path = tmp_path / "bridge_endpoints.json"
    ids = [f"kasa:{i}" for i in range(web_app.BRIDGE_MAX_ENDPOINTS + 1)]
    assigned = web_app._assign_bridge_endpoints(ids, path)

    assert len(assigned) == web_app.BRIDGE_MAX_ENDPOINTS
    assert max(assigned.values()) == web_app.BRIDGE_FIRST_ENDPOINT + web_app.BRIDGE_MAX_ENDPOINTS - 1
