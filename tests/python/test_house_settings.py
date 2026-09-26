"""Settings -> House rules: the registry, the board file, and the dashboard's API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import house_settings as hs
from src.python import web_app as web_app_module


def test_every_setting_is_well_formed():
    keys = [s.key for s in hs.SETTINGS]
    assert len(keys) == len(set(keys))
    for s in hs.SETTINGS:
        assert s.home in {"ha", "board"} and s.kind in {"number", "time"}
        if s.kind == "number":
            assert s.minimum <= s.default <= s.maximum and s.step > 0
            assert hs.validate(s.key, s.default) == s.default


def test_validate_keeps_to_the_range_and_the_step():
    assert hs.validate("freeze_below_c", "10.3") == 10.5          # nearest half degree
    with pytest.raises(ValueError, match="between 5 and 20"):
        hs.validate("freeze_below_c", 30)
    with pytest.raises(ValueError, match="a number"):
        hs.validate("freeze_below_c", "cold")
    with pytest.raises(ValueError, match="unknown"):
        hs.validate("nope", 1)


def test_the_rule_reads_the_helper_with_the_default_as_fallback():
    assert hs.ha_value("freeze_below_c") == "(states('input_number.house_freeze_below_c') | float(12))"


def test_helpers_are_created_without_initial():
    """`initial` would reset the owner's value on every Home Assistant restart."""
    for entity, message in hs.ha_helper_messages():
        assert "initial" not in message
        name_slug = message["name"].lower().replace(" ", "_")
        assert entity.split(".", 1)[1] == name_slug


def test_board_values_fall_back_to_the_default(tmp_path, monkeypatch):
    board = hs.Setting("clip_s", "Night", "Clip", "", "s", 20, 5, 60, 1, home="board")
    monkeypatch.setattr(hs, "SETTINGS", hs.SETTINGS + (board,))
    monkeypatch.setattr(hs, "BY_KEY", {**hs.BY_KEY, "clip_s": board})
    path = tmp_path / "house_settings.json"
    assert hs.value("clip_s", path) == 20                          # no file
    path.write_text(json.dumps({"clip_s": 999}))
    assert hs.value("clip_s", path) == 20                          # out of range
    assert hs.save_board("clip_s", 30, path) == 30
    assert hs.value("clip_s", path) == 30
    with pytest.raises(ValueError):
        hs.save_board("freeze_below_c", 10, path)                  # a Home Assistant one


def test_describe_marks_a_missing_helper_unavailable():
    groups = hs.describe({"input_number.house_freeze_below_c": "10.0"})
    freeze = next(s for g in groups for s in g["settings"] if s["key"] == "freeze_below_c")
    furnace = next(s for g in groups for s in g["settings"] if s["key"] == "furnace_fail_min")
    assert freeze["value"] == 10.0 and freeze["available"]
    assert furnace["value"] == 60 and not furnace["available"]


def _client(tmp_path, monkeypatch, states):
    calls = []
    monkeypatch.setattr(web_app_module, "_home_assistant_get", lambda config, token, path: states)
    monkeypatch.setattr(web_app_module, "_home_assistant_post",
                        lambda config, token, path, body: calls.append((path, body)) or [])
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "tok")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("home_assistant:\n  base_url: http://127.0.0.1:8123\n  token_env: HOME_ASSISTANT_TOKEN\n")
    disc = tmp_path / "disc.json"
    disc.write_text('{"count": 0, "switches": []}')
    app = web_app_module.create_app(discovery_path=disc, config_path=cfg, check_camera_ports=False)
    return TestClient(app), calls


def test_the_page_lists_the_groups_with_values(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, [{"entity_id": "input_number.house_freeze_below_c", "state": "11.5"}])
    groups = client.get("/api/house-settings").json()["groups"]
    assert groups[0]["name"] == "Freeze and furnace"
    assert groups[0]["settings"][0]["value"] == 11.5


def test_saving_sets_the_helper_and_refuses_nonsense(tmp_path, monkeypatch):
    client, calls = _client(tmp_path, monkeypatch, [])
    assert client.put("/api/house-settings/freeze_below_c", json={"value": 10}).json() == {"key": "freeze_below_c", "value": 10.0}
    assert calls == [("/api/services/input_number/set_value", {"entity_id": "input_number.house_freeze_below_c", "value": 10.0})]
    assert client.put("/api/house-settings/freeze_below_c", json={"value": 40}).status_code == 400
    assert client.put("/api/house-settings/nope", json={"value": 1}).status_code == 404


def test_the_heating_banner_says_why():
    [alert] = web_app_module._house_alerts([
        {"entity_id": "input_boolean.heating_alert", "state": "on"},
        {"entity_id": "input_text.heating_alert_reason", "state": "The house is at 11.5 °C, below 12 °C."},
    ])
    assert alert["id"] == "heating" and alert["message"] == "The house is at 11.5 °C, below 12 °C."
    assert alert["critical"]


def test_the_page_is_on_the_dashboard():
    root = Path(__file__).resolve().parents[2] / "src/python/web_static"
    assert 'data-view-panel="houserules"' in (root / "index.html").read_text(encoding="utf-8")
    assert "loadHouseRules" in (root / "app.js").read_text(encoding="utf-8")
