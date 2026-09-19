"""The IR remotes page: the Zigbee IR remote's learned buttons, and the page's
own Manage / Edit settings. States are the family room ZG-IR01's (2026-09-18)."""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import web_app

IEEE = "0xa4c1380c14c64266"
APP_JS = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js"
INDEX = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "index.html"


def _state(entity_id, state, name):
    return {"entity_id": entity_id, "state": state, "attributes": {"friendly_name": name}}


def remote_states(channel6_learned=False):
    states = [_state(f"button.{IEEE}_switch_learn_ir_code", "unknown", "IR remote family room Learn ir code")]
    names = {1: "Projector", 2: "Fire TV Stick", 3: "Logitech Z906 Speaker", 4: "Fire TV Stick Volume",
             5: "Logitech Z906 Speaker Volume", 6: "IR remote family room Switch6"}
    for channel, name in names.items():
        learned = "registered" if channel < 6 or channel6_learned else "unregistered"
        states += [_state(f"switch.{IEEE}_switch{channel}", "off", name),
                   _state(f"select.{IEEE}_switch{channel}_on", learned, f"IR remote family room Switch{channel} on"),
                   _state(f"select.{IEEE}_switch{channel}_off", learned, f"IR remote family room Switch{channel} off")]
    # Not an IR remote: a switch that looks alike but has no learn button.
    states.append(_state("switch.0x1111111111111111_switch1", "on", "Some relay"))
    return states


def test_the_learned_channels_of_the_zigbee_remote_are_found():
    [remote] = web_app._zigbee_ir_remotes(remote_states())

    assert remote["id"] == f"zigbee-{IEEE}" and remote["kind"] == "zigbee"
    assert remote["name"] == "IR remote family room"
    assert [b["name"] for b in remote["buttons"]] == [
        "Projector", "Fire TV Stick", "Logitech Z906 Speaker", "Fire TV Stick Volume", "Logitech Z906 Speaker Volume"]
    assert all(b["on"] and b["off"] for b in remote["buttons"])
    assert remote["unlearned"] == 1  # channel 6


def test_a_channel_learned_later_appears_with_the_remotes_name_trimmed():
    [remote] = web_app._zigbee_ir_remotes(remote_states(channel6_learned=True))
    assert remote["buttons"][-1]["name"] == "Switch6" and remote["unlearned"] == 0


def _client(tmp_path, monkeypatch, posted, states=None):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({"home_assistant": {"base_url": "http://127.0.0.1:8123"}}), encoding="utf-8")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    monkeypatch.setattr(web_app, "_home_assistant_get", lambda c, t, path: states if states is not None else remote_states())
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda c, t, path, body: posted.append((path, body)))
    app = web_app.create_app(config_path=cfg, check_camera_ports=False, ir_page_path=tmp_path / "ir_page.json")
    app.state.ir_hub_loader = lambda: []
    return TestClient(app)


def test_the_page_lists_the_zigbee_remote_and_its_settings(tmp_path, monkeypatch):
    doc = _client(tmp_path, monkeypatch, []).get("/api/ir/hubs").json()

    assert [h["kind"] for h in doc["hubs"]] == ["zigbee"]
    assert doc["page"] == {"name": "IR remotes", "icon": "device-remote", "color": "pink", "hidden": []}


def test_on_and_off_send_the_learned_codes_through_home_assistant(tmp_path, monkeypatch):
    posted: list = []
    client = _client(tmp_path, monkeypatch, posted)

    assert client.post(f"/api/ir/zigbee/zigbee-{IEEE}/buttons/switch1/on").json()["button"] == "Projector"
    assert client.post(f"/api/ir/zigbee/zigbee-{IEEE}/buttons/switch3/off").status_code == 200
    assert posted == [("/api/services/switch/turn_on", {"entity_id": f"switch.{IEEE}_switch1"}),
                      ("/api/services/switch/turn_off", {"entity_id": f"switch.{IEEE}_switch3"})]


def test_only_a_learned_channel_of_a_found_remote_is_sent(tmp_path, monkeypatch):
    posted: list = []
    client = _client(tmp_path, monkeypatch, posted)

    assert client.post(f"/api/ir/zigbee/zigbee-{IEEE}/buttons/switch6/on").status_code == 404  # not learned
    assert client.post("/api/ir/zigbee/zigbee-0x1111111111111111/buttons/switch1/on").status_code == 404
    assert client.post(f"/api/ir/zigbee/zigbee-{IEEE}/buttons/switch1/toggle").status_code == 404
    assert posted == []


def test_home_assistant_down_still_shows_the_tuya_hubs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, [])

    def down(*_a):
        raise OSError("refused")

    monkeypatch.setattr(web_app, "_home_assistant_get", down)
    assert client.get("/api/ir/hubs").json()["hubs"] == []


def test_edit_and_manage_are_saved_and_validated(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, [])

    saved = client.put("/api/ir/page", json={"name": "  Remotes  ", "icon": "remote", "color": "teal",
                                             "hidden": ["smart_ir_cabinet"]}).json()
    assert saved == {"name": "Remotes", "icon": "remote", "color": "teal", "hidden": ["smart_ir_cabinet"]}
    assert client.get("/api/ir/hubs").json()["page"] == saved

    assert client.put("/api/ir/page", json={"color": "chartreuse"}).status_code == 400
    assert client.put("/api/ir/page", json={"icon": "<script>"}).status_code == 400
    assert client.put("/api/ir/page", json={"name": "   "}).status_code == 400
    assert client.put("/api/ir/page", json={"hidden": ["a b"]}).status_code == 400


def test_the_page_has_back_manage_and_edit_like_the_device_groups():
    html = INDEX.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    header = html[html.index('data-view-panel="ir"'):]
    header = header[:header.index('id="irGrid"')]

    assert "data-back-to-devices" in header and "data-ir-manage" in header and 'data-edit-group="ir"' in header
    # The back button is shown for the IR page when it was reached from Devices.
    assert 'if (viewName === "ir") {\n    /* Not a device group, but reached from the Devices overview like one. */\n    setDevicesBackVisible(arrivedFromDevices);' in js
    assert "groupModalEditingId === IR_PAGE_ID" in js
