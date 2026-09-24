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
