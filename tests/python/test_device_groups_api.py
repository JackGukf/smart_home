"""Tests for the device group document, its loader, and its API."""

import json
from pathlib import Path

from src.python.web_app import (
    DEFAULT_DEVICE_GROUPS,
    _coerce_group_color,
    _coerce_group_icon,
    _load_device_groups,
    _save_device_groups,
)


def test_missing_file_returns_the_seeded_default(tmp_path: Path) -> None:
    doc = _load_device_groups(tmp_path / "nope.json")

    assert [g["id"] for g in doc["groups"]] == [g["id"] for g in DEFAULT_DEVICE_GROUPS]
    assert doc["overrides"] == {}


def test_null_and_malformed_documents_fall_back(tmp_path: Path) -> None:
    for content in ["null", "[]", "{}", '{"groups": null}', '{"groups": []}', "not json at all"]:
        path = tmp_path / "groups.json"
        path.write_text(content, encoding="utf-8")

        doc = _load_device_groups(path)

        assert len(doc["groups"]) == len(DEFAULT_DEVICE_GROUPS), f"failed for: {content}"


def test_null_overrides_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    path.write_text(json.dumps({"groups": DEFAULT_DEVICE_GROUPS, "overrides": None}), encoding="utf-8")

    assert _load_device_groups(path)["overrides"] == {}


def test_hand_edited_bad_colour_is_coerced_not_fatal(tmp_path: Path) -> None:
    """The colour reaches a CSS custom property, so a hand-edited file must be
    neutralised rather than trusted or allowed to break the page."""
    path = tmp_path / "groups.json"
    groups = [dict(DEFAULT_DEVICE_GROUPS[0], color="red; background:url(x)")]
    path.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    assert _load_device_groups(path)["groups"][0]["color"] == "slate"


def test_hand_edited_bad_icon_is_coerced(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    groups = [dict(DEFAULT_DEVICE_GROUPS[0], icon='x" onload="alert(1)')]
    path.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    assert _load_device_groups(path)["groups"][0]["icon"] == "device-desktop"


def test_valid_colour_survives() -> None:
    assert _coerce_group_color("red") == "red"
    assert _coerce_group_icon("temperature-celsius") == "temperature-celsius"


def test_unknown_kinds_and_chrome_are_dropped(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    groups = [dict(DEFAULT_DEVICE_GROUPS[0], kinds=["light", "wormhole"], chrome=["lightScenes", "rm -rf"])]
    path.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    loaded = _load_device_groups(path)["groups"][0]

    assert loaded["kinds"] == ["light"]
    assert loaded["chrome"] == ["lightScenes"]


def test_overrides_naming_unknown_groups_are_pruned(tmp_path: Path) -> None:
    """A deleted group leaves override entries behind; they must be ignored,
    not fatal, and dropped on the next save."""
    path = tmp_path / "groups.json"
    path.write_text(
        json.dumps(
            {
                "groups": DEFAULT_DEVICE_GROUPS,
                "overrides": {
                    "dev:1.2.3.4": {"include": ["lights", "deleted-group"], "exclude": []},
                    "dev:5.6.7.8": {"include": ["gone"], "exclude": ["also-gone"]},
                },
            }
        ),
        encoding="utf-8",
    )

    overrides = _load_device_groups(path)["overrides"]

    assert overrides == {"dev:1.2.3.4": {"include": ["lights"], "exclude": []}}


def test_round_trip_through_save(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    original = _load_device_groups(tmp_path / "missing.json")
    _save_device_groups(path, original)

    assert _load_device_groups(path)["groups"] == original["groups"]
