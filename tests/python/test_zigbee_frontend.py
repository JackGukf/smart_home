"""Embedding the Zigbee2MQTT web app in the dashboard.

Zigbee2MQTT runs on its own port, so the dashboard frames it cross-origin and
the iframe cannot read the token the browser stored for that origin. The
frontend accepts ?token=, and /api/zigbee/frontend supplies it from the board.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from src.python.web_app import (
    ZIGBEE_FRONTEND_PORT,
    _home_assistant_device_cards,
    _is_zigbee_bridge_entity,
    _mark_new_light_switch_entities,
    _zigbee_bridge_payload,
    _zigbee_frontend_token,
    create_app,
)

STATIC = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static"


def _client(secret_path: Path) -> TestClient:
    return TestClient(create_app(zigbee_secret_path=secret_path, check_camera_ports=False))


def _write_secret(path: Path, token: str = "TOKEN123") -> Path:
    path.write_text(
        f"mqtt_user: zigbee2mqtt\nmqtt_password: hunter2\nfrontend_token: {token}\n",
        encoding="utf-8",
    )
    return path


def test_token_is_returned_when_the_stack_is_installed(tmp_path: Path) -> None:
    payload = _client(_write_secret(tmp_path / "secret.yaml")).get("/api/zigbee/frontend").json()
    assert payload["available"] is True
    assert payload["token"] == "TOKEN123"
    assert payload["port"] == ZIGBEE_FRONTEND_PORT


def test_missing_secret_reports_unavailable_rather_than_failing(tmp_path: Path) -> None:
    """A board without the Zigbee stack is a normal state, not an error.

    The dashboard uses this to explain itself instead of framing a login prompt
    nobody can satisfy.
    """
    response = _client(tmp_path / "absent.yaml").get("/api/zigbee/frontend")
    assert response.status_code == 200
    assert response.json() == {"available": False, "port": ZIGBEE_FRONTEND_PORT, "token": None}


def test_unreadable_secret_degrades_instead_of_raising(tmp_path: Path) -> None:
    broken = tmp_path / "secret.yaml"
    broken.write_text(": : not valid yaml : [", encoding="utf-8")
    assert _zigbee_frontend_token(broken) is None
    assert _client(broken).get("/api/zigbee/frontend").json()["available"] is False


def test_secret_without_a_frontend_token_is_not_advertised(tmp_path: Path) -> None:
    partial = tmp_path / "secret.yaml"
    partial.write_text("mqtt_user: zigbee2mqtt\nmqtt_password: hunter2\n", encoding="utf-8")
    assert _zigbee_frontend_token(partial) is None


def test_zigbee_view_is_wired_into_the_dashboard() -> None:
    """The sidebar entry, the panel it opens, and the frame it fills."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'data-view="zigbee"' in index
    assert 'data-view-panel="zigbee"' in index
    assert 'id="zigbeeFrame"' in index


def test_frame_is_not_given_a_hardcoded_board_address() -> None:
    """Only the browser knows which address it reached the board on.

    A literal IP here would break the moment the board's address changed, which
    is the same trap homeAssistantUrl() already avoids.
    """
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    start = app_js.index("function _zigbeeUiUrl")
    body = app_js[start:start + 400]
    assert "window.location.hostname" in body


def test_legacy_browsers_are_sent_to_a_tab_instead_of_a_dead_frame() -> None:
    """Zigbee2MQTT ships an ES-module bundle.

    On Safari 12.1 - the iPad mini this dashboard still supports - that renders
    as an empty shell, the same failure the go2rtc player has. Those browsers
    must be offered a real link rather than a blank box.
    """
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    start = app_js.index("async function loadZigbeeFrame")
    body = app_js[start:app_js.index("document.querySelector(\"#openZigbeeUI\")", start)]
    assert "LEGACY_JS" in body
    assert "_showZigbeeFallback" in body


def test_bridge_controls_are_not_offered_as_new_devices() -> None:
    """permit_join is a switch entity, so it would otherwise be proposed as one.

    Confirming that prompt is what put it on the Devices view rendering as a
    light switch in the first place.
    """
    entities = [
        {"entity_id": "switch.zigbee2mqtt_bridge_permit_join", "domain": "switch"},
        {"entity_id": "switch.living_room_switch_2", "domain": "switch"},
    ]
    _mark_new_light_switch_entities(entities, known_ids=set())
    assert entities[0]["is_new"] is False
    assert entities[1]["is_new"] is True


def test_bridge_controls_are_kept_off_the_device_grid(tmp_path: Path) -> None:
    """Filtered on read, so an entry already in devices.local.yaml stops showing.

    Fixing only the confirmation path would have left the bad entry rendering.
    """
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant_devices:\n"
        "  - entity_id: switch.zigbee2mqtt_bridge_permit_join\n"
        "    name: Zigbee2MQTT Bridge Permit join\n"
        "    category: smart_plug\n"
        "    room: Zigbee2MQTT Bridge Permit join\n"
        "  - entity_id: light.kitchen_light_switch\n"
        "    name: Kitchen light switch\n"
        "    category: light_switch\n"
        "    room: Kitchen\n",
        encoding="utf-8",
    )
    ids = [card["id"] for card in _home_assistant_device_cards(config)]
    assert ids == ["light.kitchen_light_switch"]


def test_only_bridge_entities_are_recognised() -> None:
    assert _is_zigbee_bridge_entity("switch.zigbee2mqtt_bridge_permit_join") is True
    assert _is_zigbee_bridge_entity("sensor.zigbee2mqtt_bridge_version") is True
    assert _is_zigbee_bridge_entity("binary_sensor.stairs_motion_occupancy") is False
    assert _is_zigbee_bridge_entity(None) is False


def test_bridge_card_degrades_when_home_assistant_is_absent(tmp_path: Path, monkeypatch) -> None:
    """No token means no Home Assistant, which is a normal state, not an error."""
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
    config = tmp_path / "devices.local.yaml"
    config.write_text("home_assistant:\n  base_url: http://127.0.0.1:8123\n", encoding="utf-8")
    assert _zigbee_bridge_payload(config)["available"] is False


def test_bridge_payload_reports_when_the_connection_state_last_changed(
    tmp_path: Path, monkeypatch
) -> None:
    """"Offline" alone does not say whether to worry.

    A replug on 2026-09-02 left the bridge down for 66 minutes with nothing on
    screen saying so, so the health tile needs the timestamp to turn that into
    "down for 1 h".
    """
    import src.python.web_app as web_app

    config = tmp_path / "devices.local.yaml"
    config.write_text("home_assistant:\n  base_url: http://127.0.0.1:8123\n", encoding="utf-8")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "t0ken")
    monkeypatch.setattr(
        web_app,
        "_home_assistant_get",
        lambda *a, **k: [
            {
                "entity_id": "binary_sensor.zigbee2mqtt_bridge_connection_state",
                "state": "off",
                "last_changed": "2026-09-02T01:26:17+00:00",
            },
            {"entity_id": "sensor.zigbee2mqtt_bridge_version", "state": "2.13.0"},
        ],
    )

    payload = _zigbee_bridge_payload(config)
    assert payload["available"] is True
    assert payload["connected"] is False
    assert payload["connection_changed"] == "2026-09-02T01:26:17+00:00"
    assert payload["version"] == "2.13.0"


def test_bridge_payload_shape_is_stable_when_home_assistant_is_absent(
    tmp_path: Path, monkeypatch
) -> None:
    """The tile reads connection_changed unconditionally, so the key must exist."""
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
    config = tmp_path / "devices.local.yaml"
    config.write_text("home_assistant:\n  base_url: http://127.0.0.1:8123\n", encoding="utf-8")
    payload = _zigbee_bridge_payload(config)
    assert payload["connection_changed"] is None
    assert payload["connected"] is None


def test_zigbee_health_tile_is_on_the_home_view() -> None:
    """A dead bridge is silent - every Zigbee device simply stops updating.

    The tile has to live on the landing view; on the Zigbee view it would only be
    seen by someone who already suspected a problem.
    """
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    home = index[index.index('data-view-panel="home"'):index.index('data-view-panel="cameras"')]
    assert 'data-home-card="zigbeehealth"' in home
    assert 'id="homeZigbeeBody"' in home
    assert 'id="homeZigbeeState"' in home


def test_zigbee_health_tile_is_registered_as_a_home_card() -> None:
    """Unregistered cards cannot be hidden or laid out with the others."""
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "zigbeehealth:" in app_js[app_js.index("const DEFAULT_HOME_LAYOUT"):][:600]
    assert 'zigbeehealth: "Zigbee"' in app_js


def test_zigbee_health_tile_separates_offline_from_unknown() -> None:
    """"Cannot reach Home Assistant" is a different problem from "bridge is down".

    Collapsing them would either cry wolf when HA restarts, or stay quiet during
    a real outage.
    """
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    start = app_js.index("async function loadZigbeeHealthCard")
    body = app_js[start:app_js.index("async function loadZigbeeBridgeCard", start)]
    assert 'render("offline"' in body
    assert 'render("unknown"' in body
    assert 'render("online"' in body
    # available is false when HA is unreachable, which must not read as Offline.
    assert "if (!info.available)" in body


def test_zigbee_health_tile_refreshes_without_a_reload() -> None:
    """The outage this exists for started while the dashboard was already open."""
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    start = app_js.index("/* Auto-refresh every 60 s */")
    assert "loadZigbeeHealthCard()" in app_js[start:start + 400]


def test_zigbee_health_tile_does_not_rely_on_colour_alone() -> None:
    """The dot is paired with a word, for colour-blind readers and screenshots."""
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert '.home-zigbee-body[data-state="offline"] .home-zigbee-state' in css
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'class="home-zigbee-state"' in index
