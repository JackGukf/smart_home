"""
Regression tests: /bridge/* endpoints must be reachable without a login session.

Bug: the auth middleware redirected unauthenticated /bridge/devices to /login,
so the C++ bridge always received an empty response instead of the device list.
Fix: added path.startswith("/bridge/") to the auth skip list.

Skipping the login is only safe because the bridge API answers loopback
callers alone (bridge_sync.require_loopback): the dashboard listens on
0.0.0.0, and before that check anyone on the LAN could switch devices.
"""
from __future__ import annotations

import yaml
from pathlib import Path
from fastapi.testclient import TestClient

from src.python.web_app import create_app


def _make_client(tmp_path: Path, peer: str = "127.0.0.1") -> TestClient:
    """Create a test app with auth enabled and no real devices."""
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({"dashboard_auth": {"username": "user", "password": "pass"}}))
    app = create_app(config_path=cfg, check_camera_ports=False)
    return TestClient(app, raise_server_exceptions=False, follow_redirects=False,
                      client=(peer, 50000))


# ── /bridge/* must pass through without a session ────────────────────────────

def test_bridge_devices_no_auth_not_redirected(tmp_path):
    client = _make_client(tmp_path)
    resp = client.get("/bridge/devices")
    assert resp.status_code != 303, "/bridge/devices must not redirect to /login"


def test_bridge_state_all_no_auth_not_redirected(tmp_path):
    client = _make_client(tmp_path)
    resp = client.get("/bridge/state/all")
    assert resp.status_code != 303


def test_bridge_command_no_auth_not_redirected(tmp_path):
    client = _make_client(tmp_path)
    resp = client.post("/bridge/command", json={"device_id": "x", "command": "on"})
    # 404/503 is fine — 303 to /login is the regression
    assert resp.status_code not in (303, 401, 403)


# ── ...but only from the board itself ───────────────────────────────────────

def test_bridge_command_from_lan_refused_without_session(tmp_path):
    client = _make_client(tmp_path, peer="192.168.0.50")
    resp = client.post("/bridge/command", json={"device_id": "x", "command": "on"})
    assert resp.status_code == 403


def test_bridge_devices_from_lan_refused(tmp_path):
    client = _make_client(tmp_path, peer="192.168.0.50")
    assert client.get("/bridge/devices").status_code == 403


# ── Non-bridge paths still require auth ──────────────────────────────────────

def test_api_endpoint_blocked_without_session(tmp_path):
    # /api/* returns 401 (not a redirect) so JSON callers get a clear error
    client = _make_client(tmp_path)
    resp = client.get("/api/status")
    assert resp.status_code == 401


def test_root_redirects_to_login_without_session(tmp_path):
    client = _make_client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 303


def test_static_assets_pass_through_without_session(tmp_path):
    client = _make_client(tmp_path)
    resp = client.get("/static/nonexistent.css")
    # 404 is fine — 303 would be wrong
    assert resp.status_code != 303
