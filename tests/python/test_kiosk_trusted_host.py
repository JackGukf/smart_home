"""
The wall-panel kiosk logs itself in by address.

A Raspberry Pi on the wall has no keyboard, so it cannot type the dashboard
password - not at install time, and not when the 30-day session cookie expires
in the middle of the night. `dashboard_auth.trusted_hosts` lets a listed address
skip the login page, the same trade Home Assistant makes with `trusted_networks`.

These tests pin both halves of that: the listed address gets in, and every
address that is not listed is still challenged exactly as before.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python.web_app import _host_is_trusted, _parse_trusted_hosts, create_app

KIOSK = "192.168.0.176"
STRANGER = "192.168.0.99"


def _make_client(
    tmp_path: Path,
    trusted: list[str] | None,
    client_host: str,
) -> TestClient:
    auth: dict = {"username": "user", "password": "pass"}
    if trusted is not None:
        auth["trusted_hosts"] = trusted
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({"dashboard_auth": auth}), encoding="utf-8")
    app = create_app(config_path=cfg, check_camera_ports=False)
    return TestClient(
        app,
        raise_server_exceptions=False,
        follow_redirects=False,
        client=(client_host, 40000),
    )


# ── The panel gets in without a cookie ───────────────────────────────────────

def test_trusted_host_reaches_api_without_session(tmp_path):
    client = _make_client(tmp_path, [KIOSK], client_host=KIOSK)
    assert client.get("/api/health").status_code == 200


def test_trusted_host_is_not_redirected_to_login(tmp_path):
    client = _make_client(tmp_path, [KIOSK], client_host=KIOSK)
    resp = client.get("/")
    assert resp.status_code != 303, "the kiosk must not be sent to a login form"


def test_trusted_host_asking_for_login_is_sent_to_the_dashboard(tmp_path):
    """A stale /login URL on the panel would be a form nobody can fill in."""
    client = _make_client(tmp_path, [KIOSK], client_host=KIOSK)
    resp = client.get("/login")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_a_cidr_range_also_matches(tmp_path):
    client = _make_client(tmp_path, ["192.168.0.176/32"], client_host=KIOSK)
    assert client.get("/api/health").status_code == 200


# ── Everyone else is still challenged ────────────────────────────────────────

def test_untrusted_host_still_gets_401_on_api(tmp_path):
    client = _make_client(tmp_path, [KIOSK], client_host=STRANGER)
    assert client.get("/api/health").status_code == 401


def test_untrusted_host_still_redirects_to_login(tmp_path):
    client = _make_client(tmp_path, [KIOSK], client_host=STRANGER)
    resp = client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/login")


def test_absent_trusted_hosts_challenges_everyone(tmp_path):
    """The key is opt-in: a config without it behaves exactly as it always did."""
    client = _make_client(tmp_path, None, client_host=KIOSK)
    assert client.get("/api/health").status_code == 401


def test_unparseable_entry_is_ignored_not_fatal(tmp_path):
    """A typo must not take the dashboard down, nor let the typo in."""
    client = _make_client(tmp_path, ["not-an-ip", KIOSK], client_host=KIOSK)
    assert client.get("/api/health").status_code == 200


# ── The address matcher itself ───────────────────────────────────────────────

def test_parse_accepts_a_bare_string():
    assert len(_parse_trusted_hosts(KIOSK)) == 1


def test_parse_drops_junk_and_keeps_the_rest():
    assert len(_parse_trusted_hosts(["", "nonsense", KIOSK, "10.0.0.0/8"])) == 2


def test_non_ip_peer_is_never_trusted():
    """TestClient's default peer is the literal string "testclient"."""
    nets = _parse_trusted_hosts(["0.0.0.0/0"])
    assert _host_is_trusted("testclient", nets) is False
    assert _host_is_trusted(None, nets) is False


def test_empty_network_list_trusts_nobody():
    assert _host_is_trusted(KIOSK, []) is False
