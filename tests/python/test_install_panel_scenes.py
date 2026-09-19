import json
"""The Voice Panel's scenes: what they switch, and that they match the panel."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("install_panel_scenes",
                                              ROOT / "scripts/install-panel-scenes.py")
scenes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenes)


def panel_card_entities() -> set[str]:
    """The lights the panel's Home page binds its cards to."""
    text = (ROOT / "configs/esphome/voice-panel.yaml").read_text(encoding="utf-8")
    return set(re.findall(r"file: panel/card-toggle\.yaml\s+vars: \{[^}]*entity: (light\.[a-z0-9_]+)",
                          text))


def test_all_lights_scenes_switch_exactly_the_panel_lights():
    assert len(scenes.LIGHTS) == len(set(scenes.LIGHTS)) == 6
    assert set(scenes.LIGHTS) == panel_card_entities()
    body = scenes.scripts()
    # On only to the ones that are off (a light already on can flash).
    on_steps = body["panel_all_lights_on"]["sequence"]
    assert [step["if"] for step in on_steps] == [
        [{"condition": "state", "entity_id": e, "state": "off"}] for e in scenes.LIGHTS]
    assert [step["then"] for step in on_steps] == [
        [{"action": "light.turn_on", "target": {"entity_id": e}}] for e in scenes.LIGHTS]
    assert body["panel_all_lights_off"]["sequence"] == [
        {"action": "light.turn_off", "target": {"entity_id": scenes.LIGHTS}}]


def _switched(steps):
    for step in steps:
        if "then" in step:
            yield from ((("if-on", a), e) for a, e in _switched(step["then"]))
        elif "action" in step:
            targets = step["target"]["entity_id"]
            for entity in targets if isinstance(targets, list) else [targets]:
                yield step["action"], entity


def test_movie_mode_is_the_owners_decision():
    """The live Movie mode as of 2026-09-18: the IKEA cabinet LEDs and the cabinet
    LED plug instead of the IR cabinet light, which was never learned."""
    steps = scenes.scripts()["movie_mode"]["sequence"]
    assert set(_switched(steps)) == {
        ("switch.turn_on", "switch.0xa4c1380c14c64266_switch1"),   # projector
        ("switch.turn_on", "switch.0xa4c1380c14c64266_switch2"),   # Fire TV
        ("switch.turn_on", "switch.0xa4c1380c14c64266_switch3"),   # Z906
        (("if-on", "light.turn_off"), "light.family_room_switch"),
        (("if-on", "light.turn_off"), "light.kitchen_light_switch"),
        ("light.turn_off", "light.family_room_led"),
        ("light.turn_off", "light.0x286847fffe5eb711"),            # IKEA cabinet LED upper
        ("light.turn_off", "light.0x64028ffffe64de32"),            # IKEA cabinet LED lower
        ("switch.turn_off", "switch.family_room_cabinet_led"),        # TP-Link plug, cabinet LED
    }


def test_movie_mode_turns_the_room_dark_after_the_projector_is_on():
    steps = scenes.scripts()["movie_mode"]["sequence"]
    last_on = max(i for i, s in enumerate(steps) if s.get("action") == "switch.turn_on")
    assert "delay" in steps[last_on + 1]
    assert all(s.get("action") != "switch.turn_on" for s in steps[last_on + 1:])


def test_the_ir_codes_go_out_one_at_a_time():
    """Projector, Fire TV and Z906 share one IR blaster: a pause between each."""
    steps = scenes.scripts()["movie_mode"]["sequence"]
    kinds = ["on" if s.get("action") == "switch.turn_on" else "wait" if "delay" in s else "other"
             for s in steps[:6]]
    assert kinds == ["on", "wait", "on", "wait", "on", "wait"]
    assert steps[1]["delay"]["seconds"] >= 1


def test_the_ir_cabinet_light_is_gone():
    body = json.dumps(scenes.scripts()["movie_mode"])
    assert "smart_ir_cabinet" not in body and "button.press" not in body


def test_dry_run_writes_nothing(monkeypatch, capsys):
    def refuse(*_args, **_kwargs):
        raise AssertionError("a dry run must not call Home Assistant")

    monkeypatch.setattr(scenes, "install", refuse)
    assert scenes.main([]) == 0
    assert "Nothing was written" in capsys.readouterr().out
