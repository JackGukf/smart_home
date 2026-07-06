"""Tests for the Bluetooth audio API (bluetoothctl wrapper)."""

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from src.python import web_app
from src.python.web_app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "switches.json"
    discovery.write_text(json.dumps({"count": 0, "switches": []}), encoding="utf-8")
    app = create_app(
        discovery_path=discovery,
        config_path=tmp_path / "missing.yaml",
        check_camera_ports=False,
        areas_path=tmp_path / "areas.json",
    )
    return TestClient(app)


def _fake_run(outputs):
    def run(cmd, capture_output=True, text=True, timeout=0):
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs.get(tuple(cmd), ""), stderr="")
    return run


def test_devices_parses_bluetoothctl_output(monkeypatch) -> None:
    outputs = {
        ("bluetoothctl", "devices"):
            "Device AA:BB:CC:DD:EE:FF JBL Flip 6\n"
            "Device 11:22:33:44:55:66 Some Keyboard\n"
            "garbage line\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"):
            "\tName: JBL Flip 6\n\tPaired: yes\n\tConnected: yes\n\tIcon: audio-card\n",
        ("bluetoothctl", "info", "11:22:33:44:55:66"):
            "\tName: Some Keyboard\n\tPaired: no\n\tConnected: no\n\tIcon: input-keyboard\n",
    }
    monkeypatch.setattr(web_app.subprocess, "run", _fake_run(outputs))

    payload = web_app._bluetooth_devices_payload()

    assert payload["status"] == "ok"
    assert [d["mac"] for d in payload["devices"]] == ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"]
    speaker = payload["devices"][0]
    assert speaker["name"] == "JBL Flip 6"
    assert speaker["connected"] is True
    assert speaker["paired"] is True
    assert speaker["icon"] == "audio-card"


def test_devices_hides_anonymous_and_labels_unresolved(monkeypatch) -> None:
    outputs = {
        ("bluetoothctl", "devices"):
            "Device AA:BB:CC:DD:EE:01 AA-BB-CC-DD-EE-01\n"  # anonymous BLE advertiser
            "Device AA:BB:CC:DD:EE:02 AA-BB-CC-DD-EE-02\n"  # unresolved but has icon
            "Device AA:BB:CC:DD:EE:03 AA-BB-CC-DD-EE-03\n",  # unresolved but paired
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:01"):
            "\tPaired: no\n\tConnected: no\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:02"):
            "\tPaired: no\n\tConnected: no\n\tIcon: audio-card\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:03"):
            "\tPaired: yes\n\tConnected: no\n",
    }
    monkeypatch.setattr(web_app.subprocess, "run", _fake_run(outputs))

    payload = web_app._bluetooth_devices_payload()

    macs = [d["mac"] for d in payload["devices"]]
    assert "AA:BB:CC:DD:EE:01" not in macs  # anonymous advertiser hidden
    by_mac = {d["mac"]: d for d in payload["devices"]}
    assert by_mac["AA:BB:CC:DD:EE:02"]["name"] == "Unknown speaker"
    assert by_mac["AA:BB:CC:DD:EE:02"]["type"] == "Speaker"
    assert by_mac["AA:BB:CC:DD:EE:03"]["name"] == "Unknown device"


def test_devices_unavailable_without_bluetoothctl(monkeypatch) -> None:
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("bluetoothctl")

    monkeypatch.setattr(web_app.subprocess, "run", raise_missing)
    payload = web_app._bluetooth_devices_payload()
    assert payload["status"] == "unavailable"
    assert payload["devices"] == []


def test_connect_reports_success(monkeypatch) -> None:
    outputs = {
        ("bluetoothctl", "show"): "Controller B8:27:EB:00:00:00\n\tPowered: yes\n",
        ("bluetoothctl", "pair", "AA:BB:CC:DD:EE:FF"): "Failed to pair: org.bluez.Error.AlreadyExists\n",
        ("bluetoothctl", "trust", "AA:BB:CC:DD:EE:FF"): "trust succeeded\n",
        ("bluetoothctl", "connect", "AA:BB:CC:DD:EE:FF"): "Attempting to connect\nConnection successful\n",
    }
    monkeypatch.setattr(web_app.subprocess, "run", _fake_run(outputs))
    result = web_app._bluetooth_connect("AA:BB:CC:DD:EE:FF")
    assert result["status"] == "ok"


def test_endpoints_reject_invalid_mac(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    assert client.post("/api/bluetooth/devices/not-a-mac/connect").status_code == 400
    assert client.post("/api/bluetooth/devices/AA:BB;rm -rf/disconnect").status_code == 400


def test_devices_endpoint_returns_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_app, "_bluetooth_devices_payload", lambda: {"status": "ok", "devices": []})
    client = _make_client(tmp_path)
    response = client.get("/api/bluetooth/devices")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "devices": []}
