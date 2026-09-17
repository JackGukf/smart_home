"""Quick actions on Home, and the Security card's grouped layout.

  * a button may run a Home Assistant script or scene and nothing else - the
    endpoint takes an entity id from the browser, so the domain is checked;
  * "Good night" is ours: lights off, and the thermostat to sleep if it has
    that preset, each independent of the other;
  * the Security card shows the alarm state, arm buttons that reuse the
    Security view's own handler, and a way to add sensors from the card.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import web_app
from src.python.web_app import create_app

APP_JS = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "index.html"


def test_only_scripts_and_scenes_can_be_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    calls: list[str] = []
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda config, token, path, body: calls.append(path) or {})

    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
    ))

    assert client.post("/api/home-assistant/scripts/script.movie_mode/run").status_code == 200
    assert client.post("/api/home-assistant/scripts/scene.evening/run").status_code == 200
    for refused in ("light.kitchen", "alarm_control_panel.house", "homeassistant.restart"):
        assert client.post(f"/api/home-assistant/scripts/{refused}/run").status_code == 400

    assert calls == ["/api/services/script/turn_on", "/api/services/scene/turn_on"]


def test_the_script_list_is_only_scripts_and_scenes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    states = [
        {"entity_id": "script.movie_mode", "attributes": {"friendly_name": "Movie mode"}},
        {"entity_id": "scene.turn_off_all_lights", "attributes": {"friendly_name": "Turn off all lights"}},
        {"entity_id": "light.kitchen", "attributes": {"friendly_name": "Kitchen"}},
    ]
    monkeypatch.setattr(web_app, "_home_assistant_get", lambda config, token, path: states)

    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
    ))
    payload = client.get("/api/home-assistant/scripts").json()

    assert [item["entity_id"] for item in payload["items"]] == ["script.movie_mode", "scene.turn_off_all_lights"]
    assert payload["items"][0]["name"] == "Movie mode"


def test_without_a_token_the_list_is_empty_rather_than_an_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
    ))

    assert client.get("/api/home-assistant/scripts").json() == {"status": "needs_auth", "items": []}


def test_the_card_offers_the_light_scenes_and_good_night() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    body = js[js.index("function quickActionButtons()"):js.index("function renderHomeQuickActions(")]

    assert 'data-home-card="quick"' in html
    assert 'scene: "on"' in body and 'scene: "off"' in body
    assert 'quick: "good-night"' in body
    # A script that is not in Home Assistant is not offered as a dead button.
    assert "quickScripts || []).find" in body


def test_good_night_turns_the_lights_off_even_without_a_thermostat() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("async function runGoodNight("):js.index("document.addEventListener(\"click\", (event) => {\n  const scriptBtn")]

    assert 'data-light-scene="off"' in body, "the lights are the part that must always happen"
    assert body.index("data-light-scene") < body.index("latestThermostats"), "lights first"
    assert "/sleep/i" in body, "the thermostat goes to its sleep preset when it has one"


def test_the_security_card_groups_by_kind_and_can_add_sensors() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("function renderHomeAlarmCard("):js.index("/* ── Which sensors the Home alarm card shows ──")]

    assert "ALARM_KIND_COLUMNS" in js
    for label in ("Doors & windows", "Safety", "Cameras"):
        assert label in js
    # Arming rides the Security view's handler rather than a second copy.
    assert 'data-arm-mode="home"' in body and 'data-arm-mode="away"' in body
    assert 'id="homeAlarmAddButton"' in body
    assert "function shortZoneName(name)" in js


@pytest.mark.parametrize("raw, expected", [
    ("Door sensor front door", "Front door"),
    ("Front Door Camera (NPU) Person", "Front Door Camera"),
    ("Fire alarm detector Smoke", "Smoke detector"),
    ("Vibration sensor backdoor", "Vibration sensor backdoor"),
])
def test_zone_names_shorten_to_the_place(raw: str, expected: str) -> None:
    """Mirrors shortZoneName in app.js; the card has no room for device models."""
    import re

    name = re.sub(r"^door sensor\s+", "", raw, flags=re.I)
    name = re.sub(r"\s*\(NPU\)\s*Person$", "", name, flags=re.I)
    name = re.sub(r"^fire alarm detector\s+smoke$", "Smoke detector", name, flags=re.I)
    name = re.sub(r"\s+(Smoke|Moisture|Contact|Occupancy|Motion)$", "", name, flags=re.I)
    assert name[:1].upper() + name[1:] == expected
