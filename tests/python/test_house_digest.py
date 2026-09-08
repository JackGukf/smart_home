"""The digest's arithmetic, which is the part the model is not allowed to do.

The whole design rests on Python computing every figure and the model only
retelling it, so these tests cover the figures. The prose is not tested and
cannot be: what is tested is that a wrong or absent fact never reaches the
model dressed up as a real one.
"""

from __future__ import annotations

import json
import time

from src.python.house_digest import (
    battery_report,
    board_report,
    build_digest,
    facts_to_prompt,
    gather_facts,
    headlines,
    motion_summary,
    read_motion_events,
    unavailable_report,
    write_digest,
)

DAY = 86400


def motion(ts: float, entity: str, name: str, state: str, duration: float | None = None) -> dict:
    event = {"ts": ts, "entity_id": entity, "name": name, "state": state}
    if duration is not None:
        event["duration_s"] = duration
    return event


def test_a_log_shorter_than_a_day_reports_no_baseline_rather_than_zero() -> None:
    """The trap this avoids: a log started yesterday gives every sensor an
    average of 0.0/day, against which any activity at all looks like an
    anomaly. A fabricated baseline is worse than none."""
    now = 1_000_000.0
    events = [motion(now - 3600, "binary_sensor.hall", "Hall", "on")]

    (entry,) = motion_summary(events, now)

    assert entry["events"] == 1
    assert entry["daily_average"] is None
    assert entry["unusual"] is False


def test_a_sensor_is_compared_with_its_own_history_not_the_others() -> None:
    now = 1_000_000.0
    events = []
    # Ten days of history: the hall trips twice a day, the loft never.
    for day in range(2, 12):
        for _ in range(2):
            events.append(motion(now - day * DAY, "binary_sensor.hall", "Hall", "on"))
    # Today the hall trips eight times - four times its normal.
    for _ in range(8):
        events.append(motion(now - 3600, "binary_sensor.hall", "Hall", "on"))
    events.append(motion(now - 1800, "binary_sensor.loft", "Loft", "on"))

    summary = {entry["name"]: entry for entry in motion_summary(events, now)}

    assert summary["Hall"]["daily_average"] == 2.0
    assert summary["Hall"]["unusual"] is True
    # The loft has no history of its own, so nothing is claimed about it even
    # though the hall next door has plenty.
    assert summary["Loft"]["daily_average"] == 0.0
    assert summary["Loft"]["unusual"] is False


def test_active_minutes_come_from_the_off_events() -> None:
    now = 1_000_000.0
    events = [
        motion(now - 7200, "binary_sensor.hall", "Hall", "on"),
        motion(now - 7000, "binary_sensor.hall", "Hall", "off", duration=200),
        motion(now - 3600, "binary_sensor.hall", "Hall", "on"),
        motion(now - 3400, "binary_sensor.hall", "Hall", "off", duration=100),
    ]

    (entry,) = motion_summary(events, now)

    assert entry["events"] == 2
    assert entry["active_minutes"] == 5.0


def test_a_malformed_line_does_not_lose_the_whole_log(tmp_path) -> None:
    path = tmp_path / "motion.jsonl"
    path.write_text(
        json.dumps(motion(500, "binary_sensor.hall", "Hall", "on")) + "\n"
        + "{not json at all\n"
        + json.dumps(motion(600, "binary_sensor.hall", "Hall", "on")) + "\n",
        encoding="utf-8")

    assert len(read_motion_events(path, 0)) == 2


def test_only_batteries_below_the_threshold_are_reported() -> None:
    states = [
        {"entity_id": "sensor.a", "state": "100",
         "attributes": {"device_class": "battery", "friendly_name": "Full"}},
        {"entity_id": "sensor.b", "state": "26",
         "attributes": {"device_class": "battery", "friendly_name": "Water sensor"}},
        {"entity_id": "sensor.c", "state": "43",
         "attributes": {"device_class": "battery", "friendly_name": "Fire alarm"}},
        # A battery that is not reporting has no percentage to compare.
        {"entity_id": "sensor.d", "state": "unavailable",
         "attributes": {"device_class": "battery", "friendly_name": "Dead"}},
    ]

    assert [(b["name"], b["percent"]) for b in battery_report(states)] == [
        ("Water sensor", 26), ("Fire alarm", 43)]


def test_dead_entities_are_grouped_by_device_not_by_first_word() -> None:
    """One-word grouping collapsed every unrelated sensor in this house into a
    single bogus "Motion" device, which is why the prefix is two words."""
    states = [
        {"entity_id": f"sensor.up_{i}", "state": "unavailable",
         "attributes": {"friendly_name": f"Motion sensor and TH Upstairs {i}"}}
        for i in range(3)
    ] + [
        {"entity_id": "sensor.illum", "state": "unavailable",
         "attributes": {"friendly_name": "Motion and TH Kitchen Occupancy"}},
        {"entity_id": "sensor.live", "state": "42",
         "attributes": {"friendly_name": "Something fine"}},
    ]

    report = unavailable_report(states)

    assert report["entities"] == 4
    assert report["devices"] == 2
    assert report["worst"][0] == {"device": "Motion sensor", "entities": 3}


def test_an_ignored_entity_is_not_counted_as_dead() -> None:
    """Two sensors here are deliberately left on flat batteries, so they must
    not be reported as a problem every single morning."""
    states = [{"entity_id": "sensor.known_flat", "state": "unavailable",
               "attributes": {"friendly_name": "Water sensor"}}]

    assert unavailable_report(states, frozenset({"sensor.known_flat"}))["entities"] == 0


def test_the_board_report_finds_the_worst_moment_not_the_last_one(tmp_path) -> None:
    path = tmp_path / "resource-history.log"
    path.write_text(
        "2026-09-08T01:00:00+00:00 mem_used=6000M avail=9000M load=1.00/1.0 temp=40C\n"
        "2026-09-08T02:00:00+00:00 mem_used=11000M avail=3800M load=10.79/9.0 temp=64C\n"
        "2026-09-08T03:00:00+00:00 mem_used=6100M avail=8900M load=2.00/2.0 temp=41C\n",
        encoding="utf-8")

    report = board_report(path, since=0)

    assert report["samples"] == 3
    assert report["min_available_mb"] == 3800
    assert report["max_temp_c"] == 64
    assert report["peak_load"] == 10.79
    assert report["reboots"] == 0


def test_lines_older_than_the_window_are_left_out(tmp_path) -> None:
    path = tmp_path / "resource-history.log"
    path.write_text(
        "2026-09-01T01:00:00+00:00 mem_used=15000M avail=100M load=20.0/20.0 temp=90C\n"
        "2026-09-08T02:00:00+00:00 mem_used=6000M avail=9000M load=1.00/1.0 temp=40C\n",
        encoding="utf-8")

    since = time.mktime(time.strptime("2026-09-07", "%Y-%m-%d"))
    report = board_report(path, since=since)

    # The 90C spike a week ago is real history, and not this morning's news.
    assert report["samples"] == 1
    assert report["max_temp_c"] == 40


def test_the_prompt_never_shows_a_number_the_facts_do_not_have(tmp_path) -> None:
    facts = gather_facts([], tmp_path / "none.jsonl", tmp_path / "none.log",
                         now=1_000_000.0)

    prompt = facts_to_prompt(facts)

    assert "Motion: no sensors reported." in prompt
    assert "none below the warning level" in prompt


def test_a_digest_is_still_written_when_the_model_cannot_be_reached(tmp_path) -> None:
    """The model is the optional part. A digest with notes and no prose beats
    no digest at all, so a failure there must not propagate."""
    facts = gather_facts([], tmp_path / "none.jsonl", tmp_path / "none.log",
                         now=1_000_000.0)

    digest = build_digest(facts, endpoint="http://127.0.0.1:9/api/chat", timeout=1,
                          with_prose=True)

    assert digest["summary"] == ""
    assert digest["error"]
    assert digest["facts_text"]

    latest = tmp_path / "house_digest.json"
    write_digest(digest, latest, tmp_path / "house_digest.jsonl")
    assert json.loads(latest.read_text())["facts_text"] == digest["facts_text"]
    assert (tmp_path / "house_digest.jsonl").read_text().count("\n") == 1


def test_the_model_is_not_called_by_default(tmp_path) -> None:
    """Prose is opt-in: Qwen3-4B failed this job four different ways, so the
    default path must not depend on it - or even wait for it."""
    facts = gather_facts([], tmp_path / "none.jsonl", tmp_path / "none.log",
                         now=1_000_000.0)

    # An endpoint that would refuse instantly if it were ever contacted.
    digest = build_digest(facts, endpoint="http://127.0.0.1:9/api/chat", timeout=1)

    assert digest["summary"] == ""
    assert digest["error"] == ""


def test_the_notes_are_the_briefing_and_survive_without_a_model(tmp_path) -> None:
    """What the digest is actually worth is decided here, not by the model."""
    states = [
        {"entity_id": "sensor.b", "state": "26",
         "attributes": {"device_class": "battery", "friendly_name": "Water sensor"}},
        {"entity_id": "sensor.gone", "state": "unavailable",
         "attributes": {"friendly_name": "Doorbell Camera Battery"}},
    ]
    motion_log = tmp_path / "motion.jsonl"
    motion_log.write_text(json.dumps(
        {"ts": 1_000_000.0 - 60, "entity_id": "binary_sensor.hall",
         "name": "Hall", "state": "on"}) + "\n", encoding="utf-8")

    facts = gather_facts(states, motion_log, tmp_path / "none.log", now=1_000_000.0)
    notes = headlines(facts)

    assert "Hall triggered 1 times" in notes
    assert any("Water sensor" in note and "26" in note for note in notes)
    assert any("not reporting" in note for note in notes)
