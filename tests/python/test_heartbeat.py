"""The heartbeat: what it tells healthchecks.io, and that it never leaks its URL."""
from __future__ import annotations

from pathlib import Path

from src.python import heartbeat as hb

NOW = 1_790_400_000.0
ROOT = Path(__file__).resolve().parents[2]


def _status(**overrides):
    doc = {"checked_at": NOW - 60, "paused": False, "report": ["zigbee: ok", "dashboard: ok"],
           "checks": {"zigbee": {"gave_up": False}, "dashboard": {"gave_up": False}}}
    doc.update(overrides)
    return doc


def test_all_well_is_a_normal_ping_with_the_report():
    healthy, body = hb.verdict(_status(), NOW)
    assert healthy and "All 2 checks" in body and "zigbee: ok" in body


def test_a_check_the_watchdog_gave_up_on_fails_the_ping():
    status = _status(checks={"zigbee": {"gave_up": True}, "dashboard": {"gave_up": False}})
    healthy, body = hb.verdict(status, NOW)
    assert not healthy and body.startswith("Needs a person: zigbee")


def test_a_stale_watchdog_fails_the_ping_even_when_paused():
    healthy, body = hb.verdict(_status(checked_at=NOW - 20 * 60, paused=True), NOW)
    assert not healthy and "has not run for 20 minutes" in body


def test_maintenance_pause_does_not_fail_on_a_give_up():
    status = _status(paused=True, checks={"zigbee": {"gave_up": True}})
    healthy, body = hb.verdict(status, NOW)
    assert healthy and body.startswith("Paused for maintenance")


def test_no_status_at_all_fails():
    assert hb.verdict(None, NOW)[0] is False


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"OK"


def test_ping_goes_to_fail_when_unhealthy_and_retries():
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, request.data))
        if len(calls) < 3:
            raise OSError("network down")
        return _Response()

    assert hb.ping("https://hc-ping.com/uuid", False, "Needs a person", sleep=lambda s: None, opener=opener)
    assert [url for url, _ in calls] == ["https://hc-ping.com/uuid/fail"] * 3
    assert calls[0][1] == b"Needs a person"


def test_a_healthy_ping_uses_the_plain_url():
    seen = []
    hb.ping("https://hc-ping.com/uuid/", True, "ok", opener=lambda r, timeout: seen.append(r.full_url) or _Response())
    assert seen == ["https://hc-ping.com/uuid"]


def test_the_url_never_reaches_the_log(capsys):
    def opener(request, timeout):
        raise OSError("down")

    assert not hb.ping("https://hc-ping.com/SECRET-UUID", True, "ok", sleep=lambda s: None, opener=opener)
    assert "SECRET-UUID" not in capsys.readouterr().err


def test_without_a_url_it_sends_nothing_and_does_not_fail(monkeypatch, capsys):
    monkeypatch.setattr(hb, "load_dotenv", lambda path: None)
    monkeypatch.delenv("HEALTHCHECKS_PING_URL", raising=False)
    assert hb.main([]) == 0
    assert "not set" in capsys.readouterr().err


def test_the_unit_uses_the_system_python_and_runs_every_five_minutes():
    unit = (ROOT / "deploy/systemd/user/heartbeat.service").read_text(encoding="utf-8")
    timer = (ROOT / "deploy/systemd/user/heartbeat.timer").read_text(encoding="utf-8")
    assert "ExecStart=/usr/bin/python3 -m src.python.heartbeat" in unit
    assert "WorkingDirectory=/home/orangepi/smart_home_AI" in unit
    assert "OnUnitActiveSec=5min" in timer and "WantedBy=timers.target" in timer


def test_standard_library_only():
    source = (ROOT / "src/python/heartbeat.py").read_text(encoding="utf-8")
    imports = [line.split()[1] for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert all(name.split(".")[0] in {"__future__", "argparse", "json", "os", "sys", "time", "urllib",
                                      "pathlib", "typing"} for name in imports)


def test_no_backup_set_up_yet_is_not_a_failure():
    ok, line = hb.backup_verdict(None, NOW)
    assert ok and "not set up" in line


def test_one_missed_night_warns_two_fail():
    last_night = {"last_ok": NOW - 20 * 3600, "ok": True}
    ok, line = hb.backup_verdict(last_night, NOW)
    assert ok and "20 h ago" in line
    failed_tonight = {"last_ok": NOW - 30 * 3600, "ok": False, "message": "restic backup failed"}
    ok, line = hb.backup_verdict(failed_tonight, NOW)
    assert ok and "last night failed: restic backup failed" in line
    two_nights = {"last_ok": NOW - 50 * 3600, "ok": False, "message": "restic backup failed"}
    ok, line = hb.backup_verdict(two_nights, NOW)
    assert not ok and line.startswith("Off-site backup has not succeeded for 50 h")
    never = {"ok": False, "message": "RESTIC_PASSWORD not in .env"}
    assert hb.backup_verdict(never, NOW)[0] is False


def test_a_stale_backup_fails_the_ping_through_main(monkeypatch, tmp_path, capsys):
    import json as _json
    status = tmp_path / "watchdog.json"
    status.write_text(_json.dumps(_status()), encoding="utf-8")
    backup = tmp_path / "offsite.json"
    backup.write_text(_json.dumps({"last_ok": 1.0, "ok": False, "message": "boom"}), encoding="utf-8")
    monkeypatch.setattr(hb, "STATUS_PATH", status)
    monkeypatch.setattr(hb, "BACKUP_STATUS_PATH", backup)
    monkeypatch.setattr(hb.time, "time", lambda: NOW)
    monkeypatch.setattr(hb, "load_dotenv", lambda path: None)
    assert hb.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("FAIL\nOff-site backup has not succeeded")


def test_the_nightly_backup_units():
    unit = (ROOT / "deploy/systemd/user/offsite-backup.service").read_text(encoding="utf-8")
    timer = (ROOT / "deploy/systemd/user/offsite-backup.timer").read_text(encoding="utf-8")
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/offsite-backup.sh" in unit and "Type=oneshot" in unit
    assert "OnCalendar=*-*-* 02:40:00 America/Vancouver" in timer and "Persistent=true" in timer
    job = (ROOT / "scripts/offsite-backup.sh").read_text(encoding="utf-8")
    assert "--keep-daily 14 --keep-weekly 8 --keep-monthly 12" in job
    assert "backup-smart-home.sh\" --local" in job and "</dev/null" in job


def test_an_unconfigured_backup_skips_quietly_rather_than_failing():
    """The timer was enabled before Google Drive was connected; a first 02:40
    run must not write a failure and page the owner."""
    job = (ROOT / "scripts/offsite-backup.sh").read_text(encoding="utf-8")
    skip = job.index("not set up yet")
    assert "exit 0" in job[skip:skip + 200]
    assert job.index("status()") < skip < job.index("backup-smart-home.sh\" --local")
