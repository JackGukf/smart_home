"""Freeze and furnace-failure alerts (A5): rendered with Jinja against fake thermostats."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import jinja2

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install-heating-alerts.py"
spec = importlib.util.spec_from_file_location("heating_alerts", SCRIPT)
heat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heat)
BY_ID = {a["id"]: a for a in heat.automations()}


def render(template: str, attrs: dict, states: dict | None = None, **variables) -> str:
    states = states or {}
    env = jinja2.Environment()
    env.filters["float"] = lambda v, default=0.0: _float(v, default)
    return env.from_string(template).render(
        state_attr=lambda e, a: attrs.get((e, a)),
        is_state_attr=lambda e, a, v: attrs.get((e, a)) == v,
        states=lambda e: states.get(e, "unknown"), **variables).strip()


def _float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


CLOUD, LOCAL = heat.THERMOSTATS


def _temps(cloud=None, local=None, heating=None):
    return {(CLOUD, "current_temperature"): cloud, (LOCAL, "current_temperature"): local,
            (CLOUD, "hvac_action"): heating, (LOCAL, "hvac_action"): heating}


def test_too_cold_uses_the_setting_and_falls_back_to_the_local_thermostat():
    t = heat.too_cold()
    assert render(t, _temps(cloud=11.5)) == "True"                          # default 12
    assert render(t, _temps(cloud=13.0)) == "False"
    assert render(t, _temps(local=11.0)) == "True"                          # the internet is down
    assert render(t, _temps()) == "False"                                   # no reading: no alarm
    assert render(t, _temps(cloud=11.5), {"input_number.house_freeze_below_c": "10"}) == "False"


def test_the_furnace_is_failing_only_when_the_house_has_not_warmed():
    t = heat.not_warming()
    start = {"input_number.heat_call_start_temp": "18.0"}
    assert render(t, _temps(cloud=18.1), start) == "True"                   # +0.1 in an hour
    assert render(t, _temps(cloud=18.6), start) == "False"                  # it is heating
    assert render(t, _temps(cloud=18.1), {}) == "False"                     # no start recorded


def test_the_failing_rule_waits_the_setting_and_names_the_temperatures():
    rule = BY_ID["heating_furnace_not_heating"]
    trigger = rule["triggers"][0]
    assert "house_furnace_fail_min" in trigger["for"]["minutes"]
    assert render(trigger["for"]["minutes"], {}) == "60"
    why = rule["actions"][0]["data"]["variables"]["why"]
    text = render(why, _temps(cloud=18.1), {"input_number.heat_call_start_temp": "18.0"})
    assert text == "Heat has been on for 60 minutes and the house went from 18.0 to 18.1 °C - the furnace may not be working."


def test_the_start_temperature_is_remembered_when_heat_is_called():
    rule = BY_ID["heating_call_started"]
    assert render(rule["triggers"][0]["value_template"], _temps(cloud=18.0, heating="heating")) == "True"
    assert render(rule["actions"][0]["data"]["value"], _temps(cloud=18.0)) == "18.0"


def test_the_push_is_time_sensitive_not_critical():
    push = heat.script([])["sequence"][2]["data"]["data"]
    assert push["push"] == {"interruption-level": "time-sensitive"}
    assert push["actions"] == [{"action": heat.ACK_ACTION, "title": "I know"}]


def test_reminders_hourly_only_while_it_still_holds():
    loop = next(x for x in heat.script([])["sequence"] if "repeat" in x)["repeat"]
    assert loop["sequence"][0]["timeout"] == {"hours": 1}
    still = loop["sequence"][1]["if"][1]["value_template"]
    assert render(still, _temps(cloud=11.0)) == "True"
    assert render(still, _temps(cloud=20.0, heating="idle"), {"input_number.heat_call_start_temp": "20.0"}) == "False"
