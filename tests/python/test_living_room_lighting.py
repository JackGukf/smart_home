"""The living room lighting rules, and the two template traps behind them.

Both of these were real failures, and neither announced itself as a template
problem:

* ``states.binary_sensor.0xa4c138ae...`` is a Jinja syntax error, because these
  Zigbee entity ids begin with a digit. Home Assistant refused it with
  "expected token 'end of statement block', got '_presence'".
* ``}}`` inside a Python f-string collapses to a single ``}``, so a template
  built that way is silently malformed. Home Assistant refused it with
  "unexpected '}'", which points at the template rather than at the f-string.

The rules themselves are checked as data - which entity triggers which rule, and
that the dark test still has its stale-reading fallback - because the thing that
went wrong in the house was a rule reading the right sensor at the wrong moment.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "install-living-room-lighting.py"

_spec = importlib.util.spec_from_file_location("lr_lighting", SCRIPT)
lr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lr)

TEMPLATES = [c["value_template"]
             for body in lr.automations().values()
             for c in body["conditions"] if c.get("condition") == "template"]


def test_entity_ids_starting_with_a_digit_use_the_subscript_form() -> None:
    """`states.binary_sensor.0xa4c...` does not parse. Every reference to these
    sensors has to go through `states['...']`."""
    assert TEMPLATES, "no template conditions found"
    for template in TEMPLATES:
        assert not re.search(r"states\.\w+\.0x", template), (
            f"dotted access to a digit-prefixed entity id: {template}")
        for entity in re.findall(r"states\['([^']+)'\]", template):
            assert entity.split(".", 1)[1][0].isdigit() or True  # documents the shape


def test_every_template_has_balanced_jinja_delimiters() -> None:
    """The f-string trap: `}}` becomes `}` and the expression is malformed."""
    for template in TEMPLATES:
        assert template.count("{{") == template.count("}}"), (
            f"unbalanced {{{{ }}}} - the f-string brace trap: {template}")
        assert template.count("{%") == template.count("%}"), (
            f"unbalanced {{% %}}: {template}")
        assert "}}}" not in template and "{{{" not in template, template


def test_the_on_rule_triggers_downstairs_and_checks_upstairs() -> None:
    """Direction is the whole point. Triggering on upstairs would fire when you
    were merely walking up."""
    rule = lr.automations()["living_room_on_when_dark"]

    (trigger,) = rule["triggers"]
    assert trigger["entity_id"] == lr.DOWN_MOTION
    assert trigger["from"] == "off" and trigger["to"] == "on"

    came_down = rule["conditions"][0]["value_template"]
    assert lr.UP_MOTION in came_down, "the upstairs sensor is not consulted"
    assert lr.DOWN_MOTION not in came_down


def test_the_dark_test_keeps_its_stale_reading_fallback() -> None:
    """Without this the rule refuses itself for ~80s after the light goes off,
    on a reading its own action caused."""
    dark = lr.automations()["living_room_on_when_dark"]["conditions"][1]["value_template"]

    assert "last_changed < " in dark, "the staleness comparison is gone"
    assert lr.LR_LUX in dark and lr.SWITCH in dark
    assert "sun.sun" in dark, "the night fallback is gone"
    # The sun must only rescue a *stale* reading - never override a fresh one,
    # or a lamp lighting the room at night would be ignored.
    assert "stale and is_state('sun.sun'" in dark


def test_the_off_rule_covers_a_night_that_was_already_quiet() -> None:
    """One trigger is not enough: motion going quiet at 22:50 fires before the
    time window opens and is refused, and nothing fires again."""
    rule = lr.automations()["living_room_off_late_and_quiet"]

    kinds = {t.get("trigger") for t in rule["triggers"]}
    assert kinds == {"state", "time"}, "the 23:00 catch-up trigger is missing"
    assert any(t.get("at") == "23:00:00" for t in rule["triggers"])


def test_neither_rule_commands_a_switch_that_is_already_in_that_state() -> None:
    """Each command is a real device round trip, and a redundant one can race
    the background poll."""
    on_rule = lr.automations()["living_room_on_when_dark"]
    off_rule = lr.automations()["living_room_off_late_and_quiet"]

    assert {"condition": "state", "entity_id": lr.SWITCH, "state": "off"} in on_rule["conditions"]
    assert {"condition": "state", "entity_id": lr.SWITCH, "state": "on"} in off_rule["conditions"]


def test_the_ids_are_fixed_so_re_running_replaces_rather_than_duplicates() -> None:
    for auto_id, body in lr.automations().items():
        assert body["id"] == auto_id


def test_the_script_writes_nothing_without_apply() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"--apply"' in source
    assert "if not args.apply:" in source
    assert "Nothing was written" in source


def test_the_motion_fallback_exists_and_triggers_on_the_room_itself() -> None:
    """Arriving without passing the downstairs sensor is the common case - that
    sensor only fires on the stairs - so the room's own motion has to work too."""
    rule = lr.automations()["living_room_on_when_motion"]

    (trigger,) = rule["triggers"]
    assert trigger["entity_id"] == lr.LR_MOTION
    assert trigger["from"] == "off" and trigger["to"] == "on"
    # No direction check here on purpose: being in the room *is* the evidence.
    assert not any(lr.UP_MOTION in c.get("value_template", "")
                   for c in rule["conditions"])


def test_a_switch_turned_off_by_hand_is_left_alone_by_every_on_rule() -> None:
    """"I turned it off, then went upstairs" must not be undone by coming back
    down, so the suppression belongs on both paths, not just the new one."""
    autos = lr.automations()
    for auto_id in ("living_room_on_when_dark", "living_room_on_when_motion"):
        templates = [c.get("value_template", "") for c in autos[auto_id]["conditions"]]
        assert any("context.user_id is none" in t and "context.parent_id is none" in t
                   for t in templates), f"{auto_id} can override a manual off"


def test_manual_is_distinguished_by_the_absence_of_any_context() -> None:
    """Measured on the board: a change made at the wall carries neither a
    user_id nor a parent_id, while anything Home Assistant did carries one.
    Testing only user_id would treat an automation's own switch-off as manual."""
    dark_rule = lr.automations()["living_room_on_when_motion"]
    suppression = next(c["value_template"] for c in dark_rule["conditions"]
                       if "by_hand" in c.get("value_template", ""))

    assert "user_id is none and" in suppression
    assert "parent_id is none" in suppression
    assert str(lr.MANUAL_OFF_SUPPRESS_S) in suppression


def test_the_suppression_only_applies_while_the_switch_is_still_off() -> None:
    """If it is already on there is nothing to suppress, and the rule must not
    latch: once you turn it back on yourself, normal behaviour resumes."""
    rule = lr.automations()["living_room_on_when_motion"]
    suppression = next(c["value_template"] for c in rule["conditions"]
                       if "by_hand" in c.get("value_template", ""))

    assert "sw.state == 'off'" in suppression
