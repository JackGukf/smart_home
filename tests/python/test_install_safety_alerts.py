"""Leak and smoke alerts: when they fire, what they say, and what stops them.

The templates are rendered here with Jinja2 against fake states, so a syntax
slip or a wrong condition fails in the test rather than at 3 AM in Home
Assistant.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

from src.python import safety_sensors

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install-safety-alerts.py"
spec = importlib.util.spec_from_file_location("safety_alerts", SCRIPT)
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)

TELEGRAM = ["notify.house_bot_jack"]
NOW = datetime(2026, 9, 25, 14, 32, tzinfo=timezone.utc)
BOILER = "binary_sensor.0xa4c138304954cd8d_water_leak"
WASHER = "binary_sensor.0xa4c138534cac048e_water_leak"
TUYA_LEAK = "binary_sensor.water_sensor_moisture"
ZIGBEE_SMOKE = "binary_sensor.0xa4c138577961949d_smoke"


class _States:
    """HA's `states`: callable for a state string, subscript for the object."""

    def __init__(self, table: dict[str, tuple[str, datetime]]):
        self._table = table

    def __call__(self, entity_id: str) -> str:
        return self._table.get(entity_id, ("unknown", NOW))[0]

    def __getitem__(self, entity_id: str):
        if entity_id not in self._table:
            return None
        state, changed = self._table[entity_id]
        return SimpleNamespace(state=state, last_changed=changed)


def render(template: str, table: dict | None = None, **variables) -> str:
    states = _States(table or {})
    env = jinja2.Environment(extensions=["jinja2.ext.loopcontrols"])
    is_state = lambda entity_id, value: states(entity_id) == value  # noqa: E731
    env.tests["is_state"] = is_state
    env.filters["float"] = lambda value, default=0.0: _float(value, default)
    return env.from_string(template).render(
        states=states, is_state=is_state, now=lambda: NOW, **variables).strip()


def _float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _trigger(entity_id: str, from_state: str | None):
    return SimpleNamespace(entity_id=entity_id,
                           from_state=None if from_state is None else SimpleNamespace(state=from_state))


def _this(last_triggered: datetime | None):
    return SimpleNamespace(attributes=SimpleNamespace(last_triggered=last_triggered))


BY_ID = {a["id"]: a for a in safety.everything(TELEGRAM)["automations"]}


def _strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)
    elif isinstance(node, str):
        yield node


def test_every_template_parses():
    env = jinja2.Environment(extensions=["jinja2.ext.loopcontrols"])
    plan = safety.everything(TELEGRAM)
    templates = [s for s in _strings(plan) if "{{" in s or "{%" in s]
    assert len(templates) > 10
    for template in templates:
        env.parse(template)


def test_every_leak_and_smoke_sensor_is_watched():
    assert set(BY_ID["water_leak_detected"]["triggers"][0]["entity_id"]) == set(safety_sensors.LEAK)
    assert set(BY_ID["smoke_detected"]["triggers"][0]["entity_id"]) == set(safety_sensors.SMOKE)
    assert BY_ID["water_leak_detected"]["triggers"][0]["to"] == "on"


@pytest.mark.parametrize("from_state, last, alerts", [
    ("off", NOW - timedelta(minutes=5), True),            # a new leak, even right after another
    ("unknown", NOW - timedelta(minutes=5), True),        # a sleepy Zigbee detector's first report
    (None, NOW - timedelta(minutes=5), True),
    ("unavailable", None, True),                          # never alerted: news
    ("unavailable", NOW - timedelta(hours=4), True),      # long ago: news
    ("unavailable", NOW - timedelta(minutes=20), False),  # the Tuya cloud flapping mid-alert
])
def test_a_flap_back_from_unavailable_does_not_alert_again(from_state, last, alerts):
    template = BY_ID["water_leak_detected"]["conditions"][0]["value_template"]
    result = render(template, trigger=_trigger(TUYA_LEAK, from_state), this=_this(last))
    assert result == str(alerts)


def test_the_script_is_told_where():
    data = BY_ID["water_leak_detected"]["actions"][0]["data"]["variables"]["where"]
    assert render(data, trigger=_trigger(BOILER, "off")) == "the boiler"


def test_the_first_message_names_every_wet_place():
    body = safety.script("water_leak", TELEGRAM)
    push = body["sequence"][1]
    assert push["action"] == safety.PHONE
    table = {BOILER: ("on", NOW), WASHER: ("on", NOW), TUYA_LEAK: ("off", NOW)}
    message = render(push["data"]["message"], table, where="the boiler")
    assert message == "Water at the washing machine and the boiler."


def test_a_flap_between_trigger_and_send_still_names_the_place():
    body = safety.script("water_leak", TELEGRAM)
    table = {TUYA_LEAK: ("unavailable", NOW)}
    assert render(body["sequence"][1]["data"]["message"], table, where="the utility room") \
        == "Water at the utility room."


@pytest.mark.parametrize("key", ["water_leak", "smoke"])
def test_the_push_is_critical_with_i_know(key):
    push = safety.script(key, TELEGRAM)["sequence"][1]["data"]["data"]
    assert push["push"]["sound"]["critical"] == 1
    assert push["actions"] == [{"action": safety.HAZARDS[key]["ack"], "title": "I know"}]
    assert push["tag"] == safety.HAZARDS[key]["tag"]


def test_telegram_is_sent_to_every_chat():
    body = safety.script("smoke", TELEGRAM)
    telegram = body["sequence"][2]
    assert telegram["target"]["entity_id"] == TELEGRAM
    assert telegram["data"]["message"].startswith("🔥 Smoke in ")


def test_without_telegram_only_the_phone():
    actions = [step.get("action") for step in safety.script("smoke", [])["sequence"]]
    assert "notify.send_message" not in actions


@pytest.mark.parametrize("key", ["water_leak", "smoke"])
def test_reminders_stop_on_i_know_and_only_while_it_stands(key):
    hazard = safety.HAZARDS[key]
    loop = safety.script(key, TELEGRAM)["sequence"][3]["repeat"]
    assert {"condition": "state", "entity_id": hazard["flag"], "state": "on"} in loop["while"]
    wait = loop["sequence"][0]
    assert wait["wait_for_trigger"] == [{"trigger": "state", "entity_id": hazard["flag"], "to": "off"}]
    assert wait["timeout"] == hazard["remind_every"]
    reminder_if = loop["sequence"][1]["if"]
    still_on = reminder_if[1]["value_template"]
    sensor = next(iter(hazard["sensors"]))
    assert render(still_on, {sensor: ("on", NOW)}) == "True"
    assert render(still_on, {sensor: ("off", NOW)}) == "False"


def test_a_second_sensor_restarts_the_script():
    assert safety.script("water_leak", TELEGRAM)["mode"] == "restart"


def test_dry_again_is_said_once_and_keeps_the_banner():
    body = BY_ID["water_leak_cleared"]
    flag = safety.HAZARDS["water_leak"]["flag"]
    none_on = body["conditions"][1]["value_template"]
    assert render(none_on, {BOILER: ("off", NOW), WASHER: ("off", NOW)}) == "True"
    assert render(none_on, {BOILER: ("off", NOW), WASHER: ("on", NOW)}) == "False"
    once = body["conditions"][2]["value_template"]
    alert_began = NOW - timedelta(minutes=30)
    table = {flag: ("on", alert_began)}
    assert render(once, table, this=_this(None)) == "True"
    assert render(once, table, this=_this(alert_began - timedelta(days=1))) == "True"
    assert render(once, table, this=_this(NOW - timedelta(minutes=5))) == "False"
    # It says so; it does not clear the flag - "I know" does.
    assert not any(a.get("action") == "input_boolean.turn_off" for a in body["actions"])


def test_i_know_on_the_phone_clears_it():
    body = BY_ID["smoke_acknowledged"]
    assert body["triggers"][0]["event_data"] == {"action": "SMOKE_ACK"}
    assert body["actions"] == [{"action": "input_boolean.turn_off",
                                "target": {"entity_id": "input_boolean.smoke_alert"}}]


def test_health_lists_low_batteries_and_silent_sensors_not_resting_ones():
    template = safety.health_problems()
    table = {
        "sensor.shui_jin_chuan_gan_qi_battery": ("18.0", NOW),
        "sensor.0xa4c138304954cd8d_battery": ("100", NOW),
        "sensor.fire_alarm_detector_battery": ("unavailable", NOW),     # not a low battery
        "binary_sensor.0xa4c138534cac048e_battery_low": ("on", NOW),
        TUYA_LEAK: ("unavailable", NOW - timedelta(hours=7)),
        BOILER: ("unavailable", NOW - timedelta(hours=2)),              # not long enough yet
        ZIGBEE_SMOKE: ("unknown", NOW - timedelta(days=3)),             # how a sleepy one rests
    }
    lines = render(template, table).splitlines()
    assert lines == [
        "Leak sensor, utility room: battery 18%",
        "Leak sensor, washing machine: battery low",
        "Leak sensor at the utility room (WATER SENSOR): not reporting for 7 h",
    ]


def test_health_says_nothing_when_all_is_well():
    body = BY_ID["safety_sensors_need_attention"]
    assert render(safety.health_problems(), {}) == ""
    gate = body["actions"][1]
    assert gate["condition"] == "template" and "problems | trim" in gate["value_template"]
    triggers = {t["trigger"] for t in body["triggers"]}
    assert triggers == {"numeric_state", "state", "time"}


def test_the_dashboard_knows_the_same_flags():
    from src.python import web_app
    for key, hazard in safety.HAZARDS.items():
        assert web_app.HOUSE_ALERTS[key]["flag"] == hazard["flag"]
        assert web_app.HOUSE_ALERTS[key]["subjects"] == hazard["sensors"]


def test_entity_ids_starting_with_a_digit_are_never_dotted():
    """states.binary_sensor.0xa4c... is a Jinja syntax error."""
    for template in _strings(safety.everything(TELEGRAM)):
        assert "states.binary_sensor.0x" not in template and "states.sensor.0x" not in template


def test_dry_run_prints_the_plan(capsys):
    assert safety.main([]) == 0
    out = capsys.readouterr().out
    plan = json.loads(out[: out.rindex("}") + 1])
    assert set(plan["scripts"]) == {"water_leak_alert", "smoke_alert"}
    assert "Nothing was written" in out
