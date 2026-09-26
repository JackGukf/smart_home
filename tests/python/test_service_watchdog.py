"""The service watchdog: act only on a real hang, never loop, always say so."""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import service_watchdog as wd
from src.python import web_app

ROOT = Path(__file__).resolve().parents[2]
HUNG = """[2026-09-24 08:15:39] error: z2m: Publish 'set' 'brightness' to 'Ikea family room cabinet LED lower' failed: 'Error: ZCL command 0x64028ffffe64de32/1 genLevelCtrl.moveToLevelWithOnOff failed (SRSP - AF - dataRequest after 6000ms)'
[2026-09-24 08:15:45] error: z2m: Publish 'set' 'state' to 'Ikea family room cabinet LED upper' failed: 'Error: ZCL command genOnOff.off failed (SRSP - AF - dataRequest after 6000ms)'
[2026-09-24 08:15:51] error: z2m: Publish 'set' 'brightness' to 'Ikea family room cabinet LED lower' failed: (SRSP - AF - dataRequest after 6000ms)'
[2026-09-24 08:18:15] info: z2m:mqtt: MQTT publish: topic 'zigbee2mqtt/bridge/health', payload '{"response_time":1790263095071}'
"""
QUIET_BUT_HUNG = "[2026-09-24 08:18:15] info: z2m:mqtt: MQTT publish: topic 'zigbee2mqtt/bridge/health', payload '{}'\n"
WORKING = QUIET_BUT_HUNG + "[2026-09-24 08:28:01] info: z2m:mqtt: MQTT publish: topic 'zigbee2mqtt/Motion sensor and TH Entry', payload '{\"presence\":true}'\n"


def test_the_zigbee_verdict_reads_this_mornings_outage():
    assert wd.zigbee_verdict(HUNG, uptime=86400).healthy is False
    # The bridge's own health messages kept flowing while the coordinator was hung: not devices.
    assert wd.zigbee_verdict(QUIET_BUT_HUNG, uptime=86400).healthy is False
    assert wd.zigbee_verdict(WORKING, uptime=86400).healthy is True
    assert wd.zigbee_verdict(QUIET_BUT_HUNG, uptime=60).healthy is None      # still starting


def test_house_memory_is_stale_after_half_an_hour():
    assert wd.house_memory_verdict(1000.0, 1000.0 + 600).healthy is True
    assert wd.house_memory_verdict(1000.0, 1000.0 + 3600).healthy is False
    assert wd.house_memory_verdict(None, 0).healthy is None


class Fake:
    def __init__(self, results):
        self.results = list(results)
        self.acted = 0

    def probe(self):
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]

    def act(self):
        self.acted += 1
        return "restarted it"


def _check(fake, **kw):
    return wd.Check("svc", "Service", fake.probe, fake.act, **kw)


def test_it_acts_after_the_needed_failures_and_reports_it():
    fake = Fake([wd.Result(False, "no answer")])
    check, state = _check(fake, needed=2), {}
    assert wd.run_checks([check], state, now=0).events == []            # one failure: wait
    out = wd.run_checks([check], state, now=120)
    assert fake.acted == 1 and out.events[0]["kind"] == "restarted"
    assert "no answer - restarted it" in out.events[0]["message"]


def test_it_waits_out_the_cooldown_and_gives_up_after_three_restarts():
    fake = Fake([wd.Result(False, "hung")])
    check, state, now = _check(fake, needed=1, cooldown=1200), {}, 0
    kinds = []
    for _ in range(60):                                                  # two hours, a pass every 2 min
        kinds += [e["kind"] for e in wd.run_checks([check], state, now).events]
        now += 120
    assert fake.acted == wd.MAX_ACTIONS
    assert kinds.count("restarted") == 3 and kinds.count("needs_person") == 1   # said once, not every pass
    # Recovery clears it and says so.
    fake.results = [wd.Result(True, "fine")]
    assert [e["kind"] for e in wd.run_checks([check], state, now).events] == ["recovered"]
    assert state["svc"]["gave_up"] is False


def test_a_check_with_no_fix_tells_a_person_once():
    check = wd.Check("disk", "Disk space", lambda: wd.Result(False, "2 GB free"), None, needed=1, advice="Free space.")
    state = {}
    first = wd.run_checks([check], state, now=0).events
    assert first[0]["kind"] == "needs_person" and "Free space." in first[0]["message"]
    assert wd.run_checks([check], state, now=120).events == []


def test_a_failing_dependency_skips_the_checks_that_need_it():
    ha = Fake([wd.Result(False, "down")])
    memory = Fake([wd.Result(False, "stale")])
    checks = [wd.Check("home_assistant", "HA", ha.probe, ha.act, needed=5),
              wd.Check("house_memory", "Memory", memory.probe, memory.act, needed=1, depends=("home_assistant",))]
    out = wd.run_checks(checks, {}, now=0)
    assert memory.acted == 0 and any("house_memory: skipped" in line for line in out.report)


def test_a_dry_run_or_a_pause_changes_nothing():
    fake = Fake([wd.Result(False, "hung")])
    out = wd.run_checks([_check(fake, needed=1)], {}, now=0, act=False)
    assert fake.acted == 0 and out.events == [] and "svc: would act now" in out.report


def test_a_probe_that_throws_does_not_stop_the_others():
    def broken():
        raise RuntimeError("boom")
    fine = Fake([wd.Result(True, "ok")])
    out = wd.run_checks([wd.Check("a", "A", broken, None), wd.Check("b", "B", fine.probe, None)], {}, now=0)
    assert out.report[0].startswith("a: ? - probe failed") and out.report[1].startswith("b: ok")


def test_every_hang_that_breaks_control_has_a_check():
    names = {c.name for c in wd.build_checks("token")}
    assert {"zigbee", "mosquitto", "home_assistant", "ha_mqtt", "dashboard", "go2rtc",
            "house_memory", "matter_server", "docker", "disk"} <= names


def test_the_units_run_every_two_minutes_after_boot_settles():
    timer = (ROOT / "deploy/systemd/user/service-watchdog.timer").read_text(encoding="utf-8")
    service = (ROOT / "deploy/systemd/user/service-watchdog.service").read_text(encoding="utf-8")
    assert "OnBootSec=5min" in timer and "OnUnitActiveSec=2min" in timer and "WantedBy=timers.target" in timer
    assert "Type=oneshot" in service and "WorkingDirectory=/home/orangepi/smart_home_AI" in service
    assert "ExecStart=/home/orangepi/smart_home_AI/.venv/bin/python -m src.python.service_watchdog" in service
    rule = (ROOT / "deploy/polkit/51-smart-home-watchdog.rules").read_text(encoding="utf-8")
    assert '"matter-server.service"' in rule and 'lookup("verb") == "restart"' in rule


def test_the_dashboard_serves_the_status_and_shows_it(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    status = tmp_path / "service_watchdog.json"
    wd.save_status({"checked_at": 5.0, "report": ["zigbee: ok - 40 device messages in 15m"],
                    "events": [{"id": "zigbee-1", "check": "zigbee", "label": "Zigbee", "kind": "restarted",
                                "message": "Zigbee: hung - restarted the zigbee2mqtt container", "at": 1.0}],
                    "checks": {"zigbee": {"failures": 0, "actions": [1.0], "gave_up": False}}}, status)
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False, watchdog_status_path=status))
    doc = client.get("/api/watchdog").json()
    assert doc["events"][0]["kind"] == "restarted" and doc["checks"]["zigbee"] == {"failures": 0, "gave_up": False}
    empty = web_app.create_app(config_path=cfg, check_camera_ports=False, watchdog_status_path=tmp_path / "none.json")
    assert TestClient(empty).get("/api/watchdog").json()["checked_at"] is None
    js = (ROOT / "src/python/web_static/app.js").read_text(encoding="utf-8")
    assert 'pushNotification("watchdog"' in js and 'id="watchdogCard"' in (ROOT / "src/python/web_static/index.html").read_text()


def test_the_history_counts_restarts_by_age_and_keeps_ninety_days():
    day = 86400
    now = 100 * day
    events = [{"check": "zigbee", "kind": "restarted", "at": now - 3600},
              {"check": "zigbee", "kind": "recovered", "at": now - 3500}]      # not a restart
    history = [["zigbee", "restarted", now - 3 * day], ["zigbee", "restarted", now - 20 * day],
               ["zigbee", "needs_person", now - 20 * day], ["zigbee", "restarted", now - 95 * day],
               ["home_assistant", "action_failed", now - 2 * day]]
    kept = wd.record_history(history, events, now)
    assert ["zigbee", "restarted", now - 95 * day] not in kept and ["zigbee", "restarted", now - 3600] in kept
    table = wd.reliability(kept, now)
    assert table["zigbee"] == {"day": 1, "week": 2, "month": 3, "last": now - 3600, "needs_person": 1}
    assert table["home_assistant"]["week"] == 1                            # a failed fix is still an attempt


def test_the_dashboard_serves_the_reliability_table(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    status = tmp_path / "service_watchdog.json"
    import time
    wd.save_status({"checked_at": time.time(), "since": 1.0, "history": [["zigbee", "restarted", time.time() - 60]]}, status)
    doc = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False,
                                        watchdog_status_path=status)).get("/api/watchdog").json()
    assert doc["reliability"]["zigbee"]["day"] == 1 and doc["since"] == 1.0
    js = (ROOT / "src/python/web_static/app.js").read_text(encoding="utf-8")
    assert "Last restart" in js and "doc.reliability" in js


# ── Action list B4: what was added that week must not stop silently ─────────

import importlib.util  # noqa: E402
import json  # noqa: E402

ROOT_B4 = Path(__file__).resolve().parents[2]


def _installer(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT_B4 / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_watched_rule_is_one_an_installer_creates():
    safety = _installer("install-safety-alerts")
    doors = _installer("install-door-alerts")
    security = _installer("install-security-response")
    modes = _installer("install-house-modes")
    installed = ({a["id"] for a in safety.everything([])["automations"]}
                 | {a["id"] for a in doors.automations([])}
                 | {a["id"] for a in security.automations()}
                 | {a["id"] for a in modes.automations()})
    assert set(wd.ALERT_RULES) <= installed, set(wd.ALERT_RULES) - installed
    scripts = ({f"script.{k}" for k in safety.everything([])["scripts"]}
               | {doors.SCRIPT, security.INTRUSION_SCRIPT})
    assert set(wd.ALERT_SCRIPTS) <= scripts


def _rule(rule_id, state="on"):
    return {"entity_id": f"automation.{rule_id}", "state": state, "attributes": {"id": rule_id}}


def test_a_switched_off_or_missing_rule_asks_for_a_person():
    states = [_rule(r) for r in wd.ALERT_RULES] + [{"entity_id": s, "state": "off"} for s in wd.ALERT_SCRIPTS]
    assert wd.alert_rules_verdict(states).healthy is True
    states[0] = _rule(wd.ALERT_RULES[0], "off")
    result = wd.alert_rules_verdict(states)
    assert result.healthy is False and f"switched off: {wd.ALERT_RULES[0]}" in result.detail
    result = wd.alert_rules_verdict(states[1:])
    assert "missing" in result.detail
    check = next(c for c in wd.build_checks("tok") if c.name == "alert_rules")
    assert check.action is None and check.needed == 1          # never switched back on by itself


def _cam(name, state):
    return {"entity_id": f"binary_sensor.{name}_npu_person", "state": state}


def test_one_camera_down_is_a_person_all_down_is_the_detector():
    ok, _ = wd.cameras_verdict([_cam("garage_camera", "off"), _cam("office_camera", "on")])
    assert ok.healthy is True
    some, everything = wd.cameras_verdict([_cam("garage_camera", "unavailable"), _cam("office_camera", "off")])
    assert some.healthy is False and "garage_camera" in some.detail and not everything
    alld, everything = wd.cameras_verdict([_cam("garage_camera", "unavailable"), _cam("office_camera", "unavailable")])
    assert alld.healthy is False and everything
    assert wd.cameras_verdict([{"entity_id": "light.x", "state": "on"}])[0].healthy is None


def test_a_camera_blip_is_not_a_fault():
    """Streams broke up for 3.5 minutes on 2026-09-25: five passes (10 min) first."""
    check = next(c for c in wd.build_checks("tok") if c.name == "cameras")
    assert check.needed * 2 >= 10


def test_the_detector_is_restarted_only_when_every_camera_is_down(monkeypatch):
    restarted = []
    monkeypatch.setattr(wd, "restart_unit", lambda unit, user=True: lambda: restarted.append(unit) or "ok")
    monkeypatch.setattr(wd, "_ha", lambda path, token: [_cam("a", "unavailable"), _cam("b", "on")])
    try:
        wd.restart_detector_if_all_down("tok")
        raise AssertionError("should have refused")
    except RuntimeError as error:
        assert "need a person" in str(error)
    monkeypatch.setattr(wd, "_ha", lambda path, token: [_cam("a", "unavailable"), _cam("b", "unavailable")])
    wd.restart_detector_if_all_down("tok")
    assert restarted == ["npu-detector.service"]


def test_night_watch_stale_or_disconnected_is_restarted():
    now = 1_000_000.0
    assert wd.night_watch_verdict(None, now).healthy is None
    assert wd.night_watch_verdict({"alive_at": now - 30, "mqtt_connected": True}, now).healthy is True
    assert wd.night_watch_verdict({"alive_at": now - 600, "mqtt_connected": True}, now).healthy is False
    assert wd.night_watch_verdict({"alive_at": now - 30, "mqtt_connected": False}, now).healthy is False
    check = next(c for c in wd.build_checks("tok") if c.name == "night_watch")
    assert check.action is not None


def test_only_installed_timers_count_and_stopped_ones_are_started():
    enabled = {t: "enabled" for t in wd.TIMERS} | {"energy-forecast.timer": "not-found"}
    active = {t: "active" for t in wd.TIMERS} | {"offsite-backup.timer": "inactive", "energy-forecast.timer": "inactive"}
    result = wd.timers_verdict(enabled, active)
    assert result.healthy is False and result.detail == "stopped: offsite-backup.timer"
    assert wd.timers_verdict(enabled, {t: "active" for t in wd.TIMERS}).healthy is True


def test_the_dashboard_names_every_check():
    app_js = (ROOT_B4 / "src/python/web_static/app.js").read_text(encoding="utf-8")
    labels = app_js[app_js.index("const WATCHDOG_LABELS"):app_js.index("};", app_js.index("const WATCHDOG_LABELS"))]
    for check in wd.build_checks("tok"):
        assert f"{check.name}:" in labels, check.name
