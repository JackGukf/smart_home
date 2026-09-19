"""Dashboard devices to Home Assistant entities, and the All lights scripts the
Voice Panel runs. Rows are the board's own (HA 2026.6, 2026-09-19)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import panel_scenes as ps
from src.python import web_app


def row(entity, integration, name, mac=None):
    return {"entity_id": entity, "integration": integration, "name": name, "macs": [mac] if mac else []}


ROWS = [
    row("light.kitchen_light_switch", "tplink", "Kitchen light switch", "10:27:f5:77:2d:04"),
    row("switch.kitchen_light_switch_led", "tplink", "Kitchen light switch LED", "10:27:f5:77:2d:04"),
    row("switch.master_bedroom_light", "tplink", "Master bedroom light", "e8:48:b8:e3:7c:26"),
    row("switch.master_bedroom_light_led", "tplink", "Master bedroom light LED", "e8:48:b8:e3:7c:26"),
    row("light.bedroom_master_bedroom_light", "switch_as_x", "Master bedroom light", "e8:48:b8:e3:7c:26"),
    row("switch.family_room_cabinet_led", "tplink", "Family room cabinet LED", "60:a4:b7:e2:ee:b3"),
    row("switch.family_room_cabinet_led_led", "tplink", "Family room cabinet LED LED", "60:a4:b7:e2:ee:b3"),
    row("light.kitchen_light_switch_2", "matter", "Kitchen light switch"),   # the bridge's copy
    row("light.bedroom_north_bedroom_light_switch", "matter", "North Bedroom Light Switch"),
    row("light.stick_s3", "matter", "Stick S3"),
]


def test_each_kind_of_device_finds_its_entity():
    devices = [
        {"host": "192.168.0.110", "name": "Kitchen light switch", "mac": "10:27:F5:77:2D:04"},
        {"host": "192.168.0.143", "name": "Master bedroom light", "mac": "E8:48:B8:E3:7C:26"},
        {"host": "192.168.0.142", "name": "Family room cabinet LED", "mac": "60:A4:B7:E2:EE:B3"},
        {"host": "matter:2", "name": "North Bedroom Light Switch"},
        {"host": "ha:light.0x286847fffe5eb711", "name": "Cabinet LED upper"},
    ]
    entities, unmatched = ps.match_entities(devices, ROWS, {"light.0x286847fffe5eb711"})

    assert entities == [
        "light.kitchen_light_switch",              # the TP-Link one, not the Matter bridge's "_2" copy
        "light.bedroom_master_bedroom_light",      # the wall switch shown as a light
        "switch.family_room_cabinet_led",          # the plug, not its "_led" indicator
        "light.bedroom_north_bedroom_light_switch",
        "light.0x286847fffe5eb711",
    ]
    assert unmatched == []


def test_what_cannot_be_matched_is_reported_not_guessed():
    devices = [
        {"host": "192.168.0.99", "name": "New plug", "mac": "aa:bb:cc:dd:ee:ff"},
        {"host": "matter:9", "name": "Nowhere"},
        {"host": "ha:light.gone", "name": "Gone light"},
        {"host": "192.168.0.100", "name": "No MAC"},
    ]
    assert ps.match_entities(devices, ROWS, set()) == ([], ["New plug", "Nowhere", "Gone light", "No MAC"])


def test_the_scripts_turn_on_only_what_is_off_and_off_through_each_domain():
    scripts = ps.all_lights_scripts(["light.a", "switch.b"])
    on = scripts[ps.SCRIPT_ON]["sequence"]
    assert [s["then"][0]["action"] for s in on] == ["light.turn_on", "switch.turn_on"]
    assert all(s["if"][0]["state"] == "off" for s in on)
    assert scripts[ps.SCRIPT_OFF]["sequence"] == [
        {"action": "light.turn_off", "target": {"entity_id": ["light.a"]}},
        {"action": "switch.turn_off", "target": {"entity_id": ["switch.b"]}}]
    # No empty step for a domain with nothing in it.
    assert [s["action"] for s in ps.all_lights_scripts(["light.a"])[ps.SCRIPT_OFF]["sequence"]] == ["light.turn_off"]


# ── The dashboard's sync ────────────────────────────────────────────────────

def _client(tmp_path, monkeypatch, posted):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({"home_assistant": {"base_url": "http://127.0.0.1:8123"}}), encoding="utf-8")
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text(json.dumps({"switches": [{"host": "192.168.0.142", "mac": "60:A4:B7:E2:EE:B3"}]}))
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    monkeypatch.setattr(web_app, "_home_assistant_get",
                        lambda c, t, path: [{"entity_id": "light.0x286847fffe5eb711"}])

    def post(c, t, path, body):
        posted.append(path)
        return ROWS if path == "/api/template" else {"result": "ok"}

    monkeypatch.setattr(web_app, "_home_assistant_post", post)
    app = web_app.create_app(config_path=cfg, discovery_path=discovery, check_camera_ports=False,
                             light_scenes_path=tmp_path / "light_scenes.json")
    return TestClient(app)


def test_sync_rewrites_the_scripts_once_and_reports_the_unmatched(tmp_path, monkeypatch):
    posted: list = []
    client = _client(tmp_path, monkeypatch, posted)
    body = {"devices": [{"host": "192.168.0.142", "name": "Family room cabinet LED"},
                        {"host": "ha:light.0x286847fffe5eb711", "name": "Cabinet LED upper"},
                        {"host": "matter:9", "name": "Nowhere"}]}

    first = client.post("/api/light-scenes/sync", json=body).json()
    assert first == {"entities": ["switch.family_room_cabinet_led", "light.0x286847fffe5eb711"],
                     "unmatched": ["Nowhere"], "changed": True}
    assert "/api/config/script/config/panel_all_lights_on" in posted
    assert "/api/config/script/config/panel_all_lights_off" in posted
    assert client.get("/api/light-scenes").json()["entities"] == first["entities"]

    posted.clear()
    again = client.post("/api/light-scenes/sync", json=body).json()
    assert again["changed"] is False
    assert not any(p.startswith("/api/config/script") for p in posted)  # unchanged: left alone


def test_sync_never_empties_the_scripts(tmp_path, monkeypatch):
    posted: list = []
    client = _client(tmp_path, monkeypatch, posted)
    response = client.post("/api/light-scenes/sync", json={"devices": [{"host": "matter:9", "name": "Nowhere"}]})
    assert response.status_code == 409
    assert not any(p.startswith("/api/config/script") for p in posted)


def test_the_page_syncs_only_after_a_change_someone_made():
    js = (Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")
    assert js.count("syncVoicePanelLights();") == 2   # after a Manage tick, after a Lights group change
    assert 'if (manageDevicesGroupId === "lights") syncVoicePanelLights();' in js
