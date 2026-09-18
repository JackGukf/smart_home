"""Quick actions say what they did, and what they control.

  * a script's configuration becomes plain steps, conditions and waits kept;
  * after a run, each device says whether it is where its step left it - and a
    step behind a condition that did not hold is not called a failure;
  * a button that is not in Home Assistant yet (the cabinet light before it is
    learned) is named as such, not as a failure of the run;
  * the run waits for the script to finish, calling it by name;
  * the card's sheet escapes what it shows.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import script_steps, web_app
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
IR = "switch.0xa4c1380c14c64266_"


def _off_if_on(entity: str) -> dict:
    return {"if": [{"condition": "state", "entity_id": entity, "state": "on"}],
            "then": [{"action": "light.turn_off", "target": {"entity_id": entity}}]}


MOVIE_MODE = {"alias": "Movie mode", "sequence": [
    {"alias": "Projector on", "action": "switch.turn_on", "target": {"entity_id": IR + "switch1"}},
    {"action": "switch.turn_on", "target": {"entity_id": IR + "switch2"}},
    {"delay": {"seconds": 2}},
    {"alias": "Family room switch off, if on", **_off_if_on("light.family_room_switch")},
    {"action": "light.turn_off", "target": {"entity_id": "light.family_room_led"}},
    {"action": "button.press", "continue_on_error": True, "target": {"entity_id": "button.smart_ir_cabinet_cabinet_light_off"}},
]}


def _state(entity_id: str, state: str, name: str) -> dict:
    return {"entity_id": entity_id, "state": state, "attributes": {"friendly_name": name}}


STATES = {s["entity_id"]: s for s in [
    _state(IR + "switch1", "on", "Projector"),
    _state(IR + "switch2", "off", "Fire TV Stick"),
    _state("light.family_room_switch", "on", "Family room switch"),
    _state("light.family_room_led", "off", "Family room LED"),
    _state("script.movie_mode", "off", "Movie mode"),
]}


def test_a_script_becomes_plain_steps() -> None:
    steps = script_steps.flatten(MOVIE_MODE["sequence"])
    assert [s["kind"] for s in steps] == ["action", "action", "delay", "action", "action", "action"]
    assert steps[2]["text"] == "Wait 2 s"
    assert steps[3] == {"kind": "action", "action": "light.turn_off", "entities": ["light.family_room_switch"],
                        "alias": None, "when": "if it is on"}


def test_after_a_run_each_device_says_whether_it_took() -> None:
    now = time.time()
    described = script_steps.describe(script_steps.flatten(MOVIE_MODE["sequence"]), STATES.get, ran_at=now)
    by_entity = {d["entity_id"]: d for step in described for d in step["devices"]}

    assert by_entity[IR + "switch1"]["ok"] is True
    assert by_entity[IR + "switch2"]["ok"] is False, "asked on, still off"
    # Still on after "off, if it is on": the state afterwards cannot say
    # whether the condition held, so it is not judged - never a false failure.
    assert by_entity["light.family_room_switch"]["ok"] is None
    assert by_entity["light.family_room_led"]["ok"] is True
    cabinet = by_entity["button.smart_ir_cabinet_cabinet_light_off"]
    assert cabinet["ok"] is None and cabinet["problem"] == "not in Home Assistant"
    assert script_steps.summary(described) == {"devices": 5, "ok": 2, "failed": 1, "unknown": 2}


def test_a_conditional_step_that_worked_is_ok_and_a_pressed_button_counts() -> None:
    now = time.time()
    pressed = datetime.fromtimestamp(now + 1, timezone.utc).isoformat()
    states = {**STATES,
              "light.family_room_switch": _state("light.family_room_switch", "off", "Family room switch"),
              "button.smart_ir_cabinet_cabinet_light_off": _state("button.smart_ir_cabinet_cabinet_light_off", pressed, "Cabinet light off")}
    described = script_steps.describe(script_steps.flatten(MOVIE_MODE["sequence"]), states.get, ran_at=now)
    by_entity = {d["entity_id"]: d for step in described for d in step["devices"]}
    assert by_entity["light.family_room_switch"]["ok"] is True
    assert by_entity["button.smart_ir_cabinet_cabinet_light_off"]["ok"] is True


def test_before_a_run_nothing_is_judged() -> None:
    described = script_steps.describe(script_steps.flatten(MOVIE_MODE["sequence"]), STATES.get)
    assert all("ok" not in d for step in described for d in step["devices"])


def test_the_run_waits_for_the_script_by_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    called: list[str] = []
    monkeypatch.setattr(web_app, "_home_assistant_post_waiting", lambda config, token, path, body: called.append(path))
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda config, token, path, body: called.append(path))

    def ha_get(config, token, path):
        return MOVIE_MODE if path.startswith("/api/config/script/config/") else list(STATES.values())

    monkeypatch.setattr(web_app, "_home_assistant_get", ha_get)
    client = TestClient(create_app(discovery_path=tmp_path / "s.json", config_path=tmp_path / "d.yaml",
                                   check_camera_ports=False))

    result = client.post("/api/home-assistant/scripts/script.movie_mode/run", params={"wait": "true"}).json()
    assert called == ["/api/services/script/movie_mode"], "by name, which waits; turn_on would return at once"
    assert result["status"] == "ok" and result["name"] == "Movie mode"
    assert result["summary"]["devices"] == 5

    steps = client.get("/api/home-assistant/scripts/script.movie_mode/steps").json()
    assert [d["name"] for step in steps["steps"] for d in step["devices"]][:2] == ["Projector", "Fire TV Stick"]
    assert client.get("/api/home-assistant/scripts/light.kitchen/steps").status_code == 400
    assert client.post("/api/home-assistant/scripts/light.kitchen/run", params={"wait": "true"}).status_code == 400


HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  // The body's brace, not a destructured parameter's.
  let depth = 0, i = src.indexOf(') {', at) + 2;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
};
globalThis.escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
globalThis.shortZoneName = (n) => n;
eval(pick('quickSheetHtml') + pick('outcomeStatus') + pick('scriptRows'));
const rows = scriptRows([
  { kind: 'action', action: 'switch.turn_on', when: null, devices: [{ name: 'Projector', state: 'on', ok: true }] },
  { kind: 'delay', text: 'Wait 2 s' },
  { kind: 'action', action: 'light.turn_off', when: 'if it is on', devices: [{ name: 'Kitchen', state: 'off', ok: true }] },
  { kind: 'action', action: 'button.press', when: null, devices: [{ name: 'Cabinet <off>', state: null, problem: 'not in Home Assistant', ok: null }] },
]);
const html = quickSheetHtml({ title: 'Movie <mode>', status: 'Done', tone: 'good', rows });
console.log(JSON.stringify({
  details: rows.map((r) => r.detail),
  oks: rows.map((r) => r.ok),
  escaped: html.includes('Movie &lt;mode>') && html.includes('Cabinet &lt;off>'),
  done: outcomeStatus(5, 0, 3.2),
  partial: outcomeStatus(4, 1, null).state,
  failed: outcomeStatus(0, 2, null).state,
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_sheet_says_what_happened(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result["details"] == ["on · now on", "", "off, if it is on · now off", "press · not in Home Assistant"]
    assert result["oks"] == [True, None, True, None]
    assert result["escaped"]
    assert result["done"] == {"status": "Done in 3.2 s · all 5 OK", "tone": "good", "state": "done"}
    assert (result["partial"], result["failed"]) == ("partial", "failed")


def test_every_quick_action_has_a_what_it_controls_button() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("function renderHomeQuickActions("):js.index("function quickButton(")]
    assert 'data-quick-info="${escapeHtml(button.key)}"' in body
    assert 'id="quickSheet"' in body
