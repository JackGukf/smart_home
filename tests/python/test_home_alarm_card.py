"""Which sensors the Home alarm card shows.

Showing every zone put nine motion sensors on a card meant to be glanced at,
so the card now shows a chosen subset while the Alarm view still shows
everything. The choice is stored server-side, which is the point: the card is
builtin so that it reaches every device, and a per-browser choice of contents
would put that inconsistency straight back.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def _zone(entity_id: str, device_class: str, state: str = "off", name: str = "") -> dict:
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": {"device_class": device_class, "friendly_name": name or entity_id},
    }


def test_fire_and_water_are_alarm_zones() -> None:
    """They were not, which is why the card could not show them.

    An alarm system that watches doors and motion but not smoke or a leak is
    watching the wrong half of the house.
    """
    from src.python.web_app import _home_assistant_alarm_zone, _is_home_assistant_alarm_zone

    for device_class in ("smoke", "moisture", "gas", "carbon_monoxide", "door", "window"):
        entity = _zone(f"binary_sensor.x_{device_class}", device_class)
        assert _is_home_assistant_alarm_zone(entity), f"{device_class} is not a zone"

    # A leak is "detected", not "open" -- the frontend renders these differently.
    assert _home_assistant_alarm_zone(_zone("binary_sensor.leak", "moisture", "on"))["state"] == "alert"
    assert _home_assistant_alarm_zone(_zone("binary_sensor.leak", "moisture", "off"))["state"] == "clear"
    assert _home_assistant_alarm_zone(_zone("binary_sensor.smoke", "smoke", "on"))["state"] == "alert"
    # Doors keep their own wording.
    assert _home_assistant_alarm_zone(_zone("binary_sensor.d", "door", "on"))["state"] == "open"
    # Gas and CO borrow the smoke icon rather than falling through to the dot.
    assert _home_assistant_alarm_zone(_zone("binary_sensor.g", "gas"))["type"] == "smoke"
    assert _home_assistant_alarm_zone(_zone("binary_sensor.o", "opening"))["type"] == "door"


def test_the_default_is_a_rule_not_a_list_of_entity_ids() -> None:
    """A fixed list would need editing every time a sensor is added, and would
    be wrong on any other house. Presence is what gets excluded: motion tripping
    is normal life; a door, smoke or a leak is worth interrupting for."""
    from src.python.web_app import default_home_alarm_sensors

    zones = [
        {"id": "binary_sensor.front_door", "type": "door"},
        {"id": "binary_sensor.office_window", "type": "door"},
        {"id": "binary_sensor.fire", "type": "smoke"},
        {"id": "binary_sensor.leak", "type": "moisture"},
        {"id": "binary_sensor.hall_motion", "type": "motion"},
        {"id": "binary_sensor.kitchen_presence", "type": "motion"},
    ]
    chosen = default_home_alarm_sensors(zones)

    assert chosen == ["binary_sensor.front_door", "binary_sensor.office_window",
                      "binary_sensor.fire", "binary_sensor.leak"]
    assert not any("motion" in c or "presence" in c for c in chosen)

    # A door sensor added later is picked up with no configuration.
    zones.append({"id": "binary_sensor.back_door", "type": "door"})
    assert "binary_sensor.back_door" in default_home_alarm_sensors(zones)


def test_the_choice_round_trips_and_a_missing_file_means_default(tmp_path: Path) -> None:
    """None is not the same as an empty list: never-chosen falls back to the
    rule, whereas choosing nothing is a choice and must be honoured."""
    from src.python.web_app import load_home_alarm_selection, save_home_alarm_selection

    path = tmp_path / "dashboard_home_alarm.json"
    assert load_home_alarm_selection(path) is None

    save_home_alarm_selection(path, ["binary_sensor.a", "binary_sensor.b"])
    assert load_home_alarm_selection(path) == ["binary_sensor.a", "binary_sensor.b"]

    save_home_alarm_selection(path, [])
    assert load_home_alarm_selection(path) == []

    # A truncated or hand-mangled file must not take the card down with it.
    path.write_text("{ not json", encoding="utf-8")
    assert load_home_alarm_selection(path) is None
    path.write_text(json.dumps({"sensors": "everything"}), encoding="utf-8")
    assert load_home_alarm_selection(path) is None


def test_the_choice_is_server_side_so_it_reaches_every_device() -> None:
    """The whole reason the card is builtin. Storing its contents in
    localStorage would reintroduce exactly the desktop-only problem."""
    source = APP_JS.read_text(encoding="utf-8")
    body = source.split("async function loadHomeAlarmSelection()")[1].split("\nfunction ")[0]

    assert "/api/home-alarm-card" in body
    assert "localStorage" not in body

    save = source.split("async function saveHomeAlarmSelection(")[1].split("\n(function ")[0]
    assert '"PUT"' in save
    assert "localStorage" not in save


def test_the_card_filters_zones_while_the_view_keeps_all_of_them() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    card = source.split("function renderHomeAlarmCard(")[1].split("\n/* ── Which sensors")[0]
    view = source.split("function renderAlarmSection(")[1].split("\nfunction ")[0]

    # The card narrows; the default drops presence.
    assert "chosen.includes" in card
    assert 'z.type !== "motion"' in card
    # The view is untouched: it still renders whatever the payload holds.
    assert "chosen" not in view, "the Alarm view should still show every zone"


def test_the_security_label_is_display_only_and_the_ids_stay_alarm() -> None:
    """Renamed in the UI, not in the identifiers, and deliberately.

    Home card positions live in localStorage keyed by data-home-card, so
    renaming that id would orphan the saved position of every Alarm card
    anyone had dragged -- it would silently jump back to its default cell.
    The same argument covers data-view, which a saved default-view points at.
    """
    html = (PROJECT_ROOT / "src" / "python" / "web_static" / "index.html").read_text(encoding="utf-8")
    app = APP_JS.read_text(encoding="utf-8")

    # What the user reads.
    assert "\n        Security\n" in html, "the sidebar item is not labelled Security"
    assert '<span class="section-title">Security</span>' in html
    assert 'alarm: "Security",' in app

    # What the code and the browser's stored state key on.
    assert 'data-view="alarm"' in html
    assert 'data-view-panel="alarm"' in html
    assert 'data-home-card="alarm"' in html
    assert "alarm:" in app.split("const DEFAULT_HOME_LAYOUT = {")[1].split("};")[0]

    # "Alarm" as a bare visible label should be gone from the sidebar and titles.
    assert "\n        Alarm\n" not in html
    assert "Alarm System" not in html


def test_a_vibration_sensor_is_a_zone() -> None:
    """The backdoor sensor reports vibration, and Zigbee gives it a `contact`
    entity it never reports. Leaving vibration out of the zone classes meant the
    only pickable entity for a working sensor sat at "unknown" for ever, and the
    card said "No data" about a sensor that had just fired."""
    from src.python.web_app import _home_assistant_alarm_zone, _is_home_assistant_alarm_zone

    entity = {
        "entity_id": "binary_sensor.0xa4c1387000391a9e_vibration",
        "state": "on",
        "attributes": {"device_class": "vibration", "friendly_name": "Vibration sensor backdoor Vibration"},
    }

    assert _is_home_assistant_alarm_zone(entity)
    zone = _home_assistant_alarm_zone(entity)
    assert zone["type"] == "vibration"
    assert zone["state"] == "alert", "a knock is not a door standing open"

    still = _home_assistant_alarm_zone({**entity, "state": "off"})
    assert still["state"] == "clear"


def test_a_vibration_alert_clears_itself() -> None:
    """These sensors announce a knock and never send "off", so the card sat at
    Movement for ever. What the zone reports is "did it move recently"."""
    from src.python.web_app import VIBRATION_ALERT_SECONDS, _home_assistant_alarm_zone

    now = 1_789_700_000.0
    def zone_at(seconds_ago: float) -> str:
        from datetime import datetime, timezone
        changed = datetime.fromtimestamp(now - seconds_ago, tz=timezone.utc).isoformat()
        return _home_assistant_alarm_zone({
            "entity_id": "binary_sensor.backdoor_vibration",
            "state": "on",
            "last_changed": changed,
            "attributes": {"device_class": "vibration"},
        }, now=now)["state"]

    assert zone_at(5) == "alert"
    assert zone_at(VIBRATION_ALERT_SECONDS - 1) == "alert"
    assert zone_at(VIBRATION_ALERT_SECONDS + 1) == "clear", "a knock an hour ago is not movement now"


def test_an_entity_that_never_reported_is_marked_and_left_out_of_the_default() -> None:
    """Zigbee gives the vibration sensor a contact entity it never reports.
    Offering it puts a permanent "No data" on the card."""
    from src.python.web_app import _home_assistant_alarm_zone, default_home_alarm_sensors

    quiet = _home_assistant_alarm_zone({
        "entity_id": "binary_sensor.backdoor_contact",
        "state": "unknown",
        "attributes": {"device_class": "door"},
    })
    talking = _home_assistant_alarm_zone({
        "entity_id": "binary_sensor.front_door_contact",
        "state": "off",
        "attributes": {"device_class": "door"},
    })

    assert quiet["reported"] is False and talking["reported"] is True
    assert default_home_alarm_sensors([quiet, talking]) == ["binary_sensor.front_door_contact"]


def test_the_picker_hides_them_unless_they_are_already_chosen() -> None:
    js = (Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")
    body = js[js.index("function renderHomeAlarmPicker()"):js.index("async function saveHomeAlarmSelection(")]

    assert "z.reported === false && !selected.includes(String(z.id))" in body
    # One already on the card stays listed, or it could never be removed.
    assert "const available = homeAlarmAvailable.filter((z) => !hidden.includes(z));" in body
    assert "never reported anything" in body


def test_a_vibration_zone_reads_as_movement_in_the_card() -> None:
    js = (Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")

    assert '"Movement" : "Still"' in js
    columns = js[js.index("const ALARM_KIND_COLUMNS = ["):js.index("/* A camera\'s person detector")]
    assert '"vibration"' in columns, "a door's vibration sensor belongs with the doors"


def test_a_camera_is_outdoor_by_its_config_or_its_name() -> None:
    """`outdoor:` in the camera's config always wins; a house that has never set
    it gets a guess from the name, which is what the Home strip filters on."""
    from src.python.web_app import CameraDefinition, _camera_is_outdoor

    def camera(name: str, room: str | None = None, outdoor: bool | None = None) -> CameraDefinition:
        return CameraDefinition(
            name=name, host="10.0.0.1", provider="wyze", model=None, room=room,
            snapshot_url=None, stream_url=None, view_url=None, mjpeg_fps=5,
            mjpeg_width=640, mjpeg_quality=60, stream_name="cam", go2rtc_url=None,
            battery_powered=False, outdoor=outdoor,
        )

    assert _camera_is_outdoor(camera("Garage camera"))
    assert _camera_is_outdoor(camera("Frontyard camera"))
    assert _camera_is_outdoor(camera("Backyard camera"))
    assert _camera_is_outdoor(camera("Front door camera"))
    assert not _camera_is_outdoor(camera("Family room camera"))
    assert not _camera_is_outdoor(camera("Office camera"))
    # The config wins either way.
    assert _camera_is_outdoor(camera("Office camera", outdoor=True))
    assert not _camera_is_outdoor(camera("Garage camera", outdoor=False))
