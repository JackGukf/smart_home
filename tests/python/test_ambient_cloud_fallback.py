"""Ambient lights that went "unknown", and CO2 on Home.

The lights: nothing had read them since the rebuild. The H6076 stopped
answering on the LAN (its LAN Control goes off, e.g. after a firmware update),
and a BLE strip cannot be asked at all - so every restart showed "unknown".

  * a light the Govee account knows is read from the cloud, cached a minute;
  * a command tries the local path first and the cloud when that fails - but
    not for a refusal (400), which the cloud would refuse too;
  * what was just sent is trusted over the cloud for a few seconds;
  * a remembered state says it is remembered.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.python import web_app
from src.python.web_app import AmbientLightDefinition

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

CLOUD_LIGHTS = [
    {"sku": "H6076", "device": "20:58:00:00:00:00:00:01", "type": "devices.types.light"},
    {"sku": "H6054", "device": "3E:DB:00:00:00:00:00:02", "type": "devices.types.light"},
    {"sku": "H5140", "device": "0B:AD:00:00:00:00:00:03", "type": "devices.types.air_quality_monitor"},
]


def _light(provider="govee_lan", model="H6076", name="Living room ambient light", address="AA:BB:CC:DD:EE:FF"):
    return AmbientLightDefinition(name=name, provider=provider, model=model, room="Ambient", address=address,
                                  alexa_name=None)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("GOVEE_API_KEY", "key")
    web_app._GOVEE_CLOUD_CACHE.update({"devices": CLOUD_LIGHTS, "fetched": time.time()})
    web_app._GOVEE_CLOUD_LIGHT_STATE.clear()
    web_app.AMBIENT_LIGHT_RUNTIME_STATE.clear()
    yield
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app._GOVEE_CLOUD_LIGHT_STATE.clear()
    web_app.AMBIENT_LIGHT_RUNTIME_STATE.clear()


def _cloud_state(monkeypatch, power=0, brightness=13, rgb=0x00FFFF, online=True) -> list[dict]:
    calls: list[dict] = []

    def request(path, payload=None):
        calls.append({"path": path, "payload": payload})
        if path.endswith("/device/state"):
            return {"payload": {"capabilities": [
                {"instance": "online", "state": {"value": online}},
                {"instance": "powerSwitch", "state": {"value": power}},
                {"instance": "brightness", "state": {"value": brightness}},
                {"instance": "colorRgb", "state": {"value": rgb}},
            ]}}
        return {"code": 200}

    monkeypatch.setattr(web_app, "_govee_cloud_request", request)
    return calls


def test_a_light_the_lan_cannot_reach_is_read_from_the_cloud(monkeypatch) -> None:
    calls = _cloud_state(monkeypatch, power=0, brightness=100, rgb=11812095)
    monkeypatch.setattr(web_app, "_govee_lan_status", lambda light: None)
    light = _light()

    web_app._refresh_ambient_live_state([light])
    card = web_app._ambient_light_card(light)

    assert card["is_on"] is False and card["brightness"] == 100
    assert card["color"] == {"red": 0xB4, "green": 0x3C, "blue": 0xFF}
    assert card["state_source"] == "cloud"

    web_app._refresh_ambient_live_state([light])
    assert len([c for c in calls if c["path"].endswith("/device/state")]) == 1, "cached for a minute"


def test_the_lan_answer_wins_when_there_is_one(monkeypatch) -> None:
    calls = _cloud_state(monkeypatch)
    monkeypatch.setattr(web_app, "_govee_lan_status", lambda light: {"is_on": True, "brightness": 40})
    light = _light()

    web_app._refresh_ambient_live_state([light])

    assert web_app._ambient_light_card(light)["state_source"] == "lan"
    assert not calls


def test_a_ble_light_the_account_knows_is_read_too(monkeypatch) -> None:
    _cloud_state(monkeypatch, power=1)
    light = _light(provider="govee_ble", model="H6054", name="TV backlight")
    web_app._refresh_ambient_live_state([light])
    assert web_app._ambient_light_card(light)["is_on"] is True


def test_a_light_the_account_does_not_know_keeps_what_was_set(monkeypatch) -> None:
    calls = _cloud_state(monkeypatch)
    light = _light(provider="govee_ble", model="H613A", name="Mirror")
    web_app._remember_ambient_light_command(light, "on", {})
    web_app.AMBIENT_LIGHT_RUNTIME_STATE[light.address]["set_at"] = 0

    web_app._refresh_ambient_live_state([light])
    card = web_app._ambient_light_card(light)

    assert card["is_on"] is True and card["state_source"] == "last_set"
    assert not [c for c in calls if c["path"].endswith("/device/state")]


def test_an_offline_light_is_not_read_as_off(monkeypatch) -> None:
    _cloud_state(monkeypatch, online=False)
    light = _light()
    monkeypatch.setattr(web_app, "_govee_lan_status", lambda light: None)
    web_app._refresh_ambient_live_state([light])
    assert web_app._ambient_light_card(light)["is_on"] is None


def test_a_failed_local_command_goes_through_the_cloud(monkeypatch) -> None:
    calls = _cloud_state(monkeypatch)

    def unreachable(light, command, body):
        raise HTTPException(status_code=502, detail="not found on the network.")

    monkeypatch.setattr(web_app, "_govee_lan_command_payload", unreachable)
    light = _light()

    result = web_app._ambient_command_with_fallback(light, "on", {})
    assert result["via"] == "cloud" and result["local_error"] == "not found on the network."
    control = [c for c in calls if c["path"].endswith("/device/control")][0]["payload"]["payload"]
    assert control["sku"] == "H6076"
    assert control["capability"] == {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "value": 1}
    assert web_app._ambient_light_card(light)["is_on"] is True

    web_app._ambient_command_with_fallback(light, "color", {"red": 255, "green": 128, "blue": 64})
    colour = [c for c in calls if c["path"].endswith("/device/control")][-1]["payload"]["payload"]["capability"]
    assert colour == {"type": "devices.capabilities.color_setting", "instance": "colorRgb", "value": 0xFF8040}

    web_app._ambient_command_with_fallback(light, "brightness", {"brightness": 250})
    level = [c for c in calls if c["path"].endswith("/device/control")][-1]["payload"]["payload"]["capability"]
    assert level == {"type": "devices.capabilities.range", "instance": "brightness", "value": 100}


def test_a_refusal_is_not_retried_in_the_cloud(monkeypatch) -> None:
    calls = _cloud_state(monkeypatch)

    def refuse(light, command, body):
        raise HTTPException(status_code=400, detail="toggle needs state")

    monkeypatch.setattr(web_app, "_govee_lan_command_payload", refuse)
    with pytest.raises(HTTPException) as error:
        web_app._ambient_command_with_fallback(_light(), "toggle", {})
    assert error.value.status_code == 400 and not calls


def test_a_light_the_account_does_not_know_reports_the_local_failure(monkeypatch) -> None:
    _cloud_state(monkeypatch)

    def ble_down(light, command, body):
        raise HTTPException(status_code=502, detail="BLE command failed")

    monkeypatch.setattr(web_app, "_govee_ble_command_payload", ble_down)
    with pytest.raises(HTTPException) as error:
        web_app._ambient_command_with_fallback(_light(provider="govee_ble", model="H613A"), "on", {})
    assert error.value.detail == "BLE command failed"


def test_what_was_just_sent_is_trusted_over_the_cloud(monkeypatch) -> None:
    _cloud_state(monkeypatch, power=0)
    monkeypatch.setattr(web_app, "_govee_lan_status", lambda light: None)
    light = _light()
    web_app._remember_ambient_light_command(light, "on", {})

    web_app._refresh_ambient_live_state([light])
    assert web_app._ambient_light_card(light)["is_on"] is True, "the cloud has not caught up yet"

    web_app.AMBIENT_LIGHT_RUNTIME_STATE[light.address]["set_at"] = time.time() - web_app.AMBIENT_TRUST_SET_S - 1
    web_app._refresh_ambient_live_state([light])
    assert web_app._ambient_light_card(light)["is_on"] is False


HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
};
globalThis.escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
eval(pick('ambientLightCard') + pick('homeCo2Reading'));
const base = { id: 'x', name: 'Mirror', provider: 'govee_ble', model: 'H613A', controllable: true,
  capabilities: { power: true, brightness: true, color: true } };
const monitors = [
  { name: 'Office', online: true, co2: 900, co2_level: { key: 'ok' } },
  { name: 'Bedroom', online: true, co2: 1250, co2_level: { key: 'stuffy' } },
  { name: 'Hall', online: false, co2: 2000, co2_level: { key: 'poor' } },
];
console.log(JSON.stringify({
  unknown: ambientLightCard({ ...base, is_on: null }).includes('Not known yet'),
  remembered: ambientLightCard({ ...base, is_on: true, state_source: 'last_set' }).includes('On · as last set'),
  live: ambientLightCard({ ...base, is_on: false, state_source: 'cloud' }).includes('>Off<'),
  brightness: ambientLightCard({ ...base, is_on: true, brightness: 13 }).includes('value="13"'),
  worst: homeCo2Reading(monitors).name,
  none: homeCo2Reading([{ online: true, co2: null }]),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_cards_say_where_the_state_came_from_and_home_shows_the_stuffiest_room(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {"unknown": True, "remembered": True, "live": True, "brightness": True,
                                      "worst": "Bedroom", "none": None}


def test_home_temperatures_card_has_a_co2_slot() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("function renderHomeTempSensors("):js.index("drawTempSparks();", js.index("function renderHomeTempSensors("))]
    assert "homeCo2Reading()" in body and 'class="tc-co2"' in body and "has-co2" in body
