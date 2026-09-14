"""The Voice Panel's scenes by voice: sentences, names and exposure agree."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SENTENCES = ROOT / "configs/homeassistant/custom_sentences/en/voice_scenes.yaml"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice = _load("setup_ha_voice", ROOT / "scripts/setup-ha-voice.py")
scenes = _load("install_panel_scenes", ROOT / "scripts/install-panel-scenes.py")


def _expand(template: str) -> set[str]:
    """Expand [optional] and (a|b) the way Home Assistant's matcher reads them."""
    match = re.search(r"\[([^\[\]]*)\]|\(([^()]*)\)", template)
    if not match:
        return {" ".join(template.split())}
    options = [""] + match.group(1).split("|") if match.group(1) is not None else match.group(2).split("|")
    out: set[str] = set()
    for option in options:
        out |= _expand(template[:match.start()] + option + template[match.end():])
    return out


def _blocks() -> list[dict]:
    data = yaml.safe_load(SENTENCES.read_text(encoding="utf-8"))
    assert set(data["intents"]) == {"HassTurnOn"}, "only Home Assistant's own intent"
    return data["intents"]["HassTurnOn"]["data"]


def _heard(name: str) -> set[str]:
    return {s for b in _blocks() if b["slots"]["name"] == name for t in b["sentences"] for s in _expand(t)}


def test_every_sentence_names_a_script_the_installer_creates() -> None:
    aliases = {body["alias"] for body in scenes.scripts().values()}
    for block in _blocks():
        assert block["slots"]["domain"] == "script"
        assert block["slots"]["name"] in aliases


def test_the_ways_people_ask_for_movie_mode_are_covered() -> None:
    heard = _heard("Movie mode")
    for said in ["movie mode", "start movie mode", "turn on movie mode", "activate the movie mode",
                 "movie night", "lets watch a movie"]:
        assert said in heard, said


def test_the_whole_house_sentence_is_left_to_home_assistant() -> None:
    """ "Turn on all the lights" means every light; the panel's scene is "all lights on"."""
    every = {s for b in _blocks() for t in b["sentences"] for s in _expand(t)}
    assert "turn on all the lights" not in every
    assert "all lights on" in _heard("All lights on")
    assert "all the lights off" in _heard("All lights off")
    assert not _heard("All lights on") & _heard("All lights off")


def test_the_scene_scripts_are_exposed_to_assist_and_stay_exposed() -> None:
    entities = [{"entity_id": eid, "platform": "script"} for eid in sorted(voice.VOICE_SCRIPTS)]
    entities.append({"entity_id": "script.something_else", "platform": "script"})
    expose, hide = voice.plan_exposure(entities, [], {}, {})
    assert expose == sorted(voice.VOICE_SCRIPTS) and hide == []
    exposed = {eid: {"conversation": True} for eid in expose}
    assert voice.plan_exposure(entities, [], {}, exposed) == ([], [])


def test_voice_scripts_are_the_installers_scripts() -> None:
    assert voice.VOICE_SCRIPTS == {f"script.{sid}" for sid in scenes.scripts()}
