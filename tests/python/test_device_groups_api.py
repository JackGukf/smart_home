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


def test_non_dict_rule_value_is_already_tolerated(tmp_path: Path) -> None:
    """Guards the already-correct behaviour: a bad per-rule VALUE is handled
    by the isinstance(rule, dict) check inside the loop, not by the container
    guard this file's fix touches."""
    path = tmp_path / "groups.json"
    path.write_text(json.dumps({"overrides": {"key": "not-a-dict-rule"}}), encoding="utf-8")

    assert _load_device_groups(path)["overrides"] == {}


def test_truthy_non_dict_overrides_is_tolerated(tmp_path: Path) -> None:
    """`overrides` as a list, string, int, or bool must not raise -- only a
    dict of override rules is meaningful, so anything else is absent. Each
    case needs a VALID groups list alongside it, since a document without
    valid groups short-circuits to the seeded default before the overrides
    loop is ever reached."""
    for bad_overrides in [["x"], "weird", 5, True]:
        path = tmp_path / "groups.json"
        path.write_text(
            json.dumps({"groups": DEFAULT_DEVICE_GROUPS, "overrides": bad_overrides}),
            encoding="utf-8",
        )

        doc = _load_device_groups(path)

        assert doc["overrides"] == {}, f"failed for: {bad_overrides!r}"
        assert [g["id"] for g in doc["groups"]] == [g["id"] for g in DEFAULT_DEVICE_GROUPS]


def test_truthy_non_iterable_groups_is_tolerated(tmp_path: Path) -> None:
    """`groups` as an int, float, or bool is truthy but not iterable, so
    `payload.get("groups") or []` reaches a bare `for raw in <int>` and raises
    TypeError. A string or dict "groups" is iterable and already degrades
    harmlessly to an empty groups list (falling back to the seeded default),
    so this covers only the non-iterable truthy values that actually crash."""
    for bad_groups in [5, 5.5, True]:
        path = tmp_path / "groups.json"
        path.write_text(json.dumps({"groups": bad_groups}), encoding="utf-8")

        doc = _load_device_groups(path)

        assert [g["id"] for g in doc["groups"]] == [g["id"] for g in DEFAULT_DEVICE_GROUPS], (
            f"failed for: {bad_groups!r}"
        )
        assert doc["overrides"] == {}


from fastapi.testclient import TestClient

from src.python.web_app import create_app


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "switches.json"
    discovery.write_text(json.dumps({"count": 0, "switches": []}), encoding="utf-8")
    return TestClient(
        create_app(
            discovery_path=discovery,
            config_path=tmp_path / "missing.yaml",
            check_camera_ports=False,
            areas_path=tmp_path / "areas.json",
            device_groups_path=tmp_path / "groups.json",
        )
    )


def test_get_returns_the_seeded_document(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/device-groups").json()

    assert [g["id"] for g in payload["groups"]] == [g["id"] for g in DEFAULT_DEVICE_GROUPS]
    assert payload["overrides"] == {}


def test_create_accepts_name_icon_colour(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/device-groups", json={"name": "Movie Night", "icon": "movie", "color": "pink"})

    assert response.status_code == 200
    group = response.json()["group"]
    assert group["id"] == "movie-night"
    assert group["builtin"] is False
    # A user group starts with no rule; it gains members in Cycle 2.
    assert group["kinds"] == []


def test_create_rejects_duplicate_name_case_insensitively(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "LIGHTS"}).status_code == 409


def test_create_rejects_client_supplied_chrome_or_reading_filter(tmp_path: Path) -> None:
    """chrome and readingFilter exist only on seeded built-ins.

    These are schema violations caught by extra="forbid", so FastAPI's standard
    422 is correct. The routes' own semantic checks (bad colour, duplicate name)
    raise 400 explicitly.
    """
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "A", "chrome": ["lightScenes"]}).status_code == 422
    assert client.post("/api/device-groups", json={"name": "B", "readingFilter": "sensors"}).status_code == 422
    assert client.post("/api/device-groups", json={"name": "C", "builtin": True}).status_code == 422


def test_create_rejects_bad_colour_and_icon(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "D", "color": "red; background:url(x)"}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "E", "icon": 'x" onload="y'}).status_code == 400
    # The bare palette name is fine.
    assert client.post("/api/device-groups", json={"name": "F", "color": "red"}).status_code == 200


def test_create_rejects_empty_and_overlong_names(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "   "}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "x" * 41}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "!!!"}).status_code == 400


def test_patch_renames_and_recolours(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.patch("/api/device-groups/lights", json={"name": "Lamps", "color": "green"})

    assert response.status_code == 200
    assert response.json()["group"]["name"] == "Lamps"
    assert response.json()["group"]["color"] == "green"
    # The id never changes on rename, so overrides cannot be orphaned.
    assert response.json()["group"]["id"] == "lights"


def test_patch_rejects_bad_colour(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.patch("/api/device-groups/lights", json={"color": "octarine"}).status_code == 400


def test_delete_refuses_builtin_but_allows_user_groups(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/api/device-groups", json={"name": "Movie Night"})

    assert client.delete("/api/device-groups/lights").status_code == 409
    assert client.delete("/api/device-groups/movie-night").status_code == 200
    assert client.delete("/api/device-groups/movie-night").status_code == 404


def test_order_requires_a_permutation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ids = [g["id"] for g in DEFAULT_DEVICE_GROUPS]

    assert client.put("/api/device-groups/order", json={"ids": list(reversed(ids))}).status_code == 200
    assert client.put("/api/device-groups/order", json={"ids": ids[:-1]}).status_code == 400
    assert client.put("/api/device-groups/order", json={"ids": ids + ["extra"]}).status_code == 400
    assert client.put("/api/device-groups/order", json={"ids": [ids[0]] * len(ids)}).status_code == 400

    after = client.get("/api/device-groups").json()
    assert [g["id"] for g in after["groups"]] == list(reversed(ids))


def test_overrides_round_trip_and_validate(tmp_path: Path) -> None:
    client = _client(tmp_path)

    ok = client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:1.2.3.4", "include": ["climate"], "exclude": ["lights"]},
    )
    assert ok.status_code == 200
    assert ok.json()["overrides"]["dev:1.2.3.4"] == {"include": ["climate"], "exclude": ["lights"]}

    # Unknown group -> 404.
    assert client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:1.2.3.4", "include": ["nope"]},
    ).status_code == 404

    # Unknown device key is fine: the device may be offline or not yet discovered.
    assert client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:never-seen", "include": ["lights"]},
    ).status_code == 200

    # Empty include and exclude clears the entry.
    client.put("/api/device-groups/overrides", json={"device_key": "dev:1.2.3.4"})
    assert "dev:1.2.3.4" not in client.get("/api/device-groups").json()["overrides"]
