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
    assert body["panel_all_lights_on"]["sequence"] == [
        {"action": "light.turn_on", "target": {"entity_id": scenes.LIGHTS}}]
    assert body["panel_all_lights_off"]["sequence"] == [
        {"action": "light.turn_off", "target": {"entity_id": scenes.LIGHTS}}]


def test_movie_mode_is_the_owners_decision():
    steps = scenes.scripts()["movie_mode"]["sequence"]
    switched = {(s["action"], e) for s in steps for e in s["target"]["entity_id"]}
    assert switched == {
        ("light.turn_off", "light.living_room_living_room_switch_2"),
        ("switch.turn_off", "switch.living_room_cabinet_led"),
        ("light.turn_on", "light.h6076"),
    }


def test_dry_run_writes_nothing(monkeypatch, capsys):
    def refuse(*_args, **_kwargs):
        raise AssertionError("a dry run must not call Home Assistant")

    monkeypatch.setattr(scenes, "install", refuse)
    assert scenes.main([]) == 0
    assert "Nothing was written" in capsys.readouterr().out
