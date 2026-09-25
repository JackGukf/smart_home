"""The disarm PIN (security.disarm_pin): whatever lowers the alarm asks for it.

Disarm, Morning disarm, and Home while on Vacation need it once it is set;
arming, the other modes and the speaker's Stop never do. The wall panel's
trusted address skips the login, not the PIN.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.python.web_app as web_app_module
from src.python.web_app import _LoginGuard, create_app


def _client(tmp_path: Path, monkeypatch, pin_yaml: str | None = '"4821"', *,
            peer: str = "testclient", trusted: bool = False, mode: str | None = "Home"):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(web_app_module, "_home_assistant_alarm_command",
                        lambda path, command: sent.append(("alarm", command)) or {"status": "ok"})
    monkeypatch.setattr(web_app_module, "_house_mode_command",
                        lambda path, action: sent.append(("mode", action)) or {"status": "ok"})
    monkeypatch.setattr(web_app_module, "_alarm_speaker_stop",
                        lambda path: sent.append(("speaker", "stop")) or {"status": "ok"})
    monkeypatch.setattr(web_app_module, "_house_mode_now", lambda path: mode)
    monkeypatch.setattr(web_app_module, "_alarm_payload", lambda path: {"status": "ok"})
    cfg = tmp_path / "config.yaml"
    text = "dashboard_auth:\n  username: admin\n  password: admin\n"
    if trusted:
        text += f"  trusted_hosts:\n    - {peer}\n"
    if pin_yaml is not None:
        text += f"security:\n  disarm_pin: {pin_yaml}\n"
    cfg.write_text(text, encoding="utf-8")
    disc = tmp_path / "disc.json"
    disc.write_text('{"count": 0, "switches": []}', encoding="utf-8")
    client = TestClient(create_app(discovery_path=disc, config_path=cfg, check_camera_ports=False),
                        follow_redirects=False, client=(peer, 50000))
    if not trusted:
        client.post("/login", data={"username": "admin", "password": "admin"})
    return client, sent


def _pin_reason(resp) -> str | None:
    detail = resp.json().get("detail")
    return detail.get("pin") if isinstance(detail, dict) else None


def test_no_pin_set_disarms_as_before(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch, pin_yaml=None)
    assert client.post("/api/alarm/commands/disarmed").status_code == 200
    assert sent == [("alarm", "disarmed")]


@pytest.mark.parametrize("command", ["disarm", "disarmed"])
def test_disarm_needs_the_pin(tmp_path, monkeypatch, command):
    client, sent = _client(tmp_path, monkeypatch)
    resp = client.post(f"/api/alarm/commands/{command}")
    assert resp.status_code == 403 and _pin_reason(resp) == "required"
    resp = client.post(f"/api/alarm/commands/{command}", json={"pin": "0000"})
    assert resp.status_code == 403 and _pin_reason(resp) == "wrong"
    assert sent == []
    assert client.post(f"/api/alarm/commands/{command}", json={"pin": "4821"}).status_code == 200
    assert sent == [("alarm", command)]


@pytest.mark.parametrize("command", ["home", "away"])
def test_arming_never_asks(tmp_path, monkeypatch, command):
    client, sent = _client(tmp_path, monkeypatch)
    assert client.post(f"/api/alarm/commands/{command}").status_code == 200
    assert sent == [("alarm", command)]


def test_speaker_stop_never_asks(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    assert client.post("/api/alarm/speaker/stop").status_code == 200


def test_the_wall_panel_skips_the_login_not_the_pin(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch, peer="192.168.0.176", trusted=True)
    resp = client.post("/api/alarm/commands/disarmed")
    assert resp.status_code == 403 and _pin_reason(resp) == "required"
    assert client.post("/api/alarm/commands/disarmed", json={"pin": "4821"}).status_code == 200


def test_morning_disarm_needs_the_pin(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    assert _pin_reason(client.post("/api/house-mode/morning_disarm")) == "required"
    assert client.post("/api/house-mode/morning_disarm", json={"pin": "4821"}).status_code == 200
    assert sent == [("mode", "morning_disarm")]


@pytest.mark.parametrize("mode, asks", [("Vacation", True), (None, True), ("Away", False), ("Home", False)])
def test_home_asks_only_when_it_ends_a_vacation(tmp_path, monkeypatch, mode, asks):
    """Unknown (Home Assistant not answering) fails closed."""
    client, sent = _client(tmp_path, monkeypatch, mode=mode)
    resp = client.post("/api/house-mode/home")
    if asks:
        assert resp.status_code == 403 and _pin_reason(resp) == "required"
        assert sent == []
    else:
        assert resp.status_code == 200


@pytest.mark.parametrize("action", ["away", "vacation", "night_arm"])
def test_modes_that_arm_never_ask(tmp_path, monkeypatch, action):
    client, sent = _client(tmp_path, monkeypatch, mode="Vacation")
    assert client.post(f"/api/house-mode/{action}").status_code == 200


def test_wrong_pins_lock_the_address_out(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    for _ in range(_LoginGuard.LOGIN_MAX_FAILURES - 1):
        assert _pin_reason(client.post("/api/alarm/commands/disarmed", json={"pin": "1111"})) == "wrong"
    assert _pin_reason(client.post("/api/alarm/commands/disarmed", json={"pin": "1111"})) == "locked"
    # Locked: the right PIN is refused too, and nothing reached the alarm.
    assert _pin_reason(client.post("/api/alarm/commands/disarmed", json={"pin": "4821"})) == "locked"
    assert sent == []


@pytest.mark.parametrize("pin_yaml", ["4821", "0123", '"12"', '"12ab"'])
def test_a_badly_set_pin_refuses_rather_than_turning_the_check_off(tmp_path, monkeypatch, pin_yaml):
    """Unquoted, YAML reads 0123 as the octal number 83 - not what was typed."""
    client, sent = _client(tmp_path, monkeypatch, pin_yaml=pin_yaml)
    resp = client.post("/api/alarm/commands/disarmed", json={"pin": pin_yaml.strip('"')})
    assert resp.status_code == 500
    # Shaped as a PIN refusal, so the keypad shows it instead of failing silently.
    assert _pin_reason(resp) == "misconfigured"
    assert "in quotes" in resp.json()["detail"]["message"]
    assert sent == []
    assert client.get("/api/alarm").json()["disarm_pin"] is True


def test_the_page_learns_whether_not_what(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.get("/api/alarm").json()
    assert body["disarm_pin"] is True
    assert "4821" not in client.get("/api/alarm").text
    other = tmp_path / "unset"
    other.mkdir()
    unset, _ = _client(other, monkeypatch, pin_yaml=None)
    assert unset.get("/api/alarm").json()["disarm_pin"] is False


def test_wrong_pin_is_audited(tmp_path, monkeypatch, caplog):
    records = []

    class _Capture(web_app_module.logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = _Capture()
    web_app_module._AUDIT_LOG.addHandler(handler)
    try:
        client, _ = _client(tmp_path, monkeypatch)
        client.post("/api/alarm/commands/disarmed", json={"pin": "9999"})
    finally:
        web_app_module._AUDIT_LOG.removeHandler(handler)
    assert any("alarm disarm refused: wrong PIN by admin from testclient" in m for m in records)
    assert not any("9999" in m for m in records)


def test_the_keypad_is_on_the_page():
    root = Path(__file__).resolve().parents[2] / "src/python/web_static"
    html = (root / "index.html").read_text(encoding="utf-8")
    js = (root / "app.js").read_text(encoding="utf-8")
    assert 'id="pinModal"' in html and 'data-pin-key="ok"' in html
    assert "postWithDisarmPin" in js and "JSON.stringify({ pin })" in js
    assert 'refusal.pin === "misconfigured"' in js
