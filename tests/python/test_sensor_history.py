"""Hourly history for the Temperatures card's sparklines.

The rules that matter:

  * entity ids come from the browser, so anything but a plain sensor id is
    refused before it reaches a URL;
  * a sensor that has not reported yet in the window does not count, rather
    than pulling the average towards zero;
  * a sensor that goes unavailable stops counting from that moment;
  * every screen showing the card costs one Home Assistant query per five
    minutes, not one per render.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import sensor_history
from src.python.web_app import create_app

START = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)


def _at(minutes: int) -> str:
    return (START + timedelta(minutes=minutes)).isoformat()


def test_only_plain_sensor_ids_in_known_groups_are_accepted() -> None:
    ok = sensor_history.validate_groups({"indoor_temperature": ["sensor.a_1", "sensor.a_1"]})
    assert ok == {"indoor_temperature": ["sensor.a_1"]}

    for bad in (
        {"indoor_temperature": ["sensor.a&filter_entity_id=lock.front"]},
        {"indoor_temperature": ["lock.front_door"]},
        {"indoor_temperature": ["../api/states"]},
        {"attic": ["sensor.a"]},
        {"indoor_temperature": [f"sensor.s{i}" for i in range(41)]},
    ):
        with pytest.raises(sensor_history.HistoryRequestError):
            sensor_history.validate_groups(bad)


def test_the_group_average_ignores_a_sensor_until_its_first_reading() -> None:
    readings = sensor_history._readings([
        [{"entity_id": "sensor.a", "state": "20", "last_changed": _at(0)}],
        [{"entity_id": "sensor.b", "state": "30", "last_changed": _at(60)}],
    ])

    series = sensor_history.hourly_series(readings, ["sensor.a", "sensor.b"], START, 2)

    assert series == [20.0, 25.0]


def test_an_unavailable_sensor_stops_counting() -> None:
    readings = sensor_history._readings([
        [
            {"entity_id": "sensor.a", "state": "20", "last_changed": _at(0)},
            {"state": "unavailable", "last_changed": _at(60)},
        ],
        [{"entity_id": "sensor.b", "state": "24", "last_changed": _at(0)}],
    ])

    series = sensor_history.hourly_series(readings, ["sensor.a", "sensor.b"], START, 2)

    assert series == [22.0, 24.0]


def test_an_hour_with_no_readings_at_all_is_a_gap_not_zero() -> None:
    readings = sensor_history._readings([
        [{"entity_id": "sensor.a", "state": "18.5", "last_changed": _at(90)}],
    ])

    assert sensor_history.hourly_series(readings, ["sensor.a"], START, 3)[0] is None


def test_the_answer_is_cached_per_grouping() -> None:
    calls: list[str] = []
    clock = [START.timestamp() + 24 * 3600]

    def fetch(url: str, headers: dict[str, str]):
        calls.append(url)
        assert headers["Authorization"] == "Bearer token"
        return [[{"entity_id": "sensor.a", "state": "21", "last_changed": _at(0)}]]

    service = sensor_history.SensorHistory("http://ha", lambda: "token", fetch=fetch, clock=lambda: clock[0])
    groups = {"indoor_temperature": ["sensor.a"]}

    first = service.hourly(groups)
    service.hourly(groups)
    clock[0] += sensor_history.CACHE_SECONDS + 1
    service.hourly(groups)

    assert len(calls) == 2
    assert first["status"] == "ok"
    assert len(first["hours"]) == 24
    assert "filter_entity_id=sensor.a" in calls[0]


def test_without_a_token_nothing_is_fetched() -> None:
    def fetch(url, headers):
        raise AssertionError("fetched without a token")

    service = sensor_history.SensorHistory("http://ha", lambda: None, fetch=fetch)
    assert service.hourly({"indoor_temperature": ["sensor.a"]})["status"] == "needs_auth"


def test_the_endpoint_refuses_a_bad_entity_id(tmp_path: Path) -> None:
    service = sensor_history.SensorHistory("http://ha", lambda: "token", fetch=lambda u, h: [])
    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
        history_service=service,
    ))

    bad = client.post("/api/sensors/history", json={"groups": {"indoor_temperature": ["lock.front_door"]}})
    good = client.post("/api/sensors/history", json={"groups": {"indoor_temperature": ["sensor.a"]}})

    assert bad.status_code == 400
    assert good.status_code == 200 and good.json()["status"] == "ok"
