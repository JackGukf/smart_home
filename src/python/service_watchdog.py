"""Catch the services that hang - running, but no longer working - and restart them.

Crashes are handled already: every service here is a systemd unit with
Restart=always or a container with restart: unless-stopped. What nothing
caught was a *hang*. On 2026-09-23 the Zigbee coordinator stopped answering
at 12:39; the containers stayed "Up", Zigbee2MQTT kept publishing its health,
and motion and every Zigbee command were dead for 20 hours until someone
noticed. `docker restart zigbee2mqtt` fixed it in a minute.

So each check here asks the working question, not "is it running":

  zigbee          devices are sending, and commands are not timing out (SRSP)
  mosquitto       the broker accepts a connection
  home_assistant  the API answers
  ha_mqtt         Home Assistant sees the Zigbee bridge (its MQTT link is up)
  dashboard       the dashboard answers HTTP
  go2rtc          the camera relay answers HTTP
  house_memory    the house memory has recorded an event lately
  matter_server   the Matter controller accepts a connection
  docker          the Docker daemon answers        (tells a person; needs root)
  disk            the NVMe has room                (tells a person)

A check acts only after `needed` failures in a row (one run is two minutes),
at most once per `cooldown`, and at most MAX_ACTIONS times in ACTION_WINDOW.
Past that it stops and says a person is needed, rather than restart-looping a
service that is broken for a reason a restart cannot fix. A check whose
dependency is failing is skipped: Home Assistant down is not a house-memory
fault. Every action and every give-up is written to the status file the
dashboard shows as a banner, and posted as a Home Assistant notification.

    python -m src.python.service_watchdog            # one pass (the timer runs this)
    python -m src.python.service_watchdog --dry-run  # probe and report, change nothing

Pause it - e.g. while re-flashing the dongle or upgrading Home Assistant - by
creating deploy/watchdog/.paused; probes still run and report, nothing acts.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = PROJECT_ROOT / "service_watchdog.json"
PAUSE_FLAG = PROJECT_ROOT / "deploy" / "watchdog" / ".paused"
ZIGBEE_PAUSE_FLAG = PROJECT_ROOT / "deploy" / "zigbee" / ".autostart-disabled"
HOUSE_MEMORY_DB = Path(os.getenv("HOUSE_MEMORY_DB", str(Path.home() / "house-memory" / "events.db")))

MAX_ACTIONS = 3
ACTION_WINDOW = 6 * 3600
EVENTS_KEPT = 50
# Every restart and every give-up, kept by age rather than by count: the Status
# view's reliability table counts them over 24 hours, 7 and 30 days.
HISTORY_DAYS = 90
COUNTED = ("restarted", "action_failed", "needs_person")

# Zigbee: the window must be longer than the quietest real gap. Measured
# overnight, the house's sensors send 500+ messages an hour, so fifteen
# minutes of none is not a quiet house.
ZIGBEE_WINDOW = "15m"
ZIGBEE_WINDOW_S = 900
ZIGBEE_SRSP_LIMIT = 3
STARTUP_GRACE = 600          # a container younger than this is still starting
HOUSE_MEMORY_STALE = 1800


@dataclass
class Result:
    healthy: bool | None     # None: could not tell, or skipped
    detail: str


@dataclass
class Check:
    name: str
    label: str
    probe: Callable[[], Result]
    action: Callable[[], str] | None = None      # None: tell a person
    needed: int = 2
    cooldown: int = 1200
    depends: tuple[str, ...] = ()
    advice: str = ""


# ── Probes ──

def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _container(name: str) -> tuple[bool, float]:
    """(running, seconds since it started)."""
    out = _run(["docker", "inspect", "-f", "{{.State.Running}} {{.State.StartedAt}}", name])
    if out.returncode:
        return False, 0.0
    running, started = out.stdout.split()
    at = datetime.fromisoformat(started[:26].rstrip("Z") + ("" if "+" in started[19:] else "+00:00"))
    return running == "true", (datetime.now(timezone.utc) - at).total_seconds()


def _tcp(port: int, host: str = "127.0.0.1", timeout: float = 5) -> Result:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return Result(True, f"port {port} accepts connections")
    except OSError as error:
        return Result(False, f"port {port} refuses: {error}")


def _http_alive(url: str, timeout: float = 15) -> Result:
    """Any HTTP answer is alive - a 401 or 404 still means the server is serving.
    A hang is no answer at all."""
    try:
        with urlopen(url, timeout=timeout) as response:
            return Result(True, f"HTTP {response.status}")
    except HTTPError as error:
        return Result(error.code < 500, f"HTTP {error.code}")
    except (URLError, OSError) as error:
        return Result(False, f"no answer: {getattr(error, 'reason', error)}")


def _ha(path: str, token: str, body: dict | None = None, timeout: float = 20) -> Any:
    request = Request(f"http://127.0.0.1:8123{path}", headers={"Authorization": f"Bearer {token}",
                                                             "Content-Type": "application/json"},
                      data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST")
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def zigbee_verdict(log: str, uptime: float) -> Result:
    """From Zigbee2MQTT's recent log: are devices talking, and do commands get through?

    Zigbee2MQTT logs every message it forwards as "MQTT publish: topic
    'zigbee2mqtt/<device>'" at log level info (the setting on the board); its
    own bridge/ topics are not devices, and it keeps sending those while the
    coordinator is hung. "SRSP ... after 6000ms" is the coordinator not
    answering on the serial link."""
    srsp = log.count("SRSP")
    devices = sum(1 for line in log.splitlines()
                  if "MQTT publish: topic 'zigbee2mqtt/" in line and "zigbee2mqtt/bridge/" not in line)
    if srsp >= ZIGBEE_SRSP_LIMIT:
        return Result(False, f"the coordinator is not answering ({srsp} command timeouts in {ZIGBEE_WINDOW})")
    if uptime < STARTUP_GRACE:
        return Result(None, "Zigbee2MQTT is still starting")
    if devices == 0:
        return Result(False, f"no message from any Zigbee device in {ZIGBEE_WINDOW}")
    return Result(True, f"{devices} device messages in {ZIGBEE_WINDOW}")


def probe_zigbee() -> Result:
    if ZIGBEE_PAUSE_FLAG.exists():
        return Result(None, "paused by deploy/zigbee/.autostart-disabled")
    running, uptime = _container("zigbee2mqtt")
    if not running:
        return Result(None, "not running - zigbee-adapter-watch brings it back")
    # Only this run of the container: after a restart, the old run's timeouts
    # are still in the last 15 minutes of the log and are not about now.
    window = int(min(ZIGBEE_WINDOW_S, max(uptime, 1)))
    out = _run(["docker", "logs", "--since", f"{window}s", "zigbee2mqtt"])
    return zigbee_verdict(out.stdout + out.stderr, uptime)


def probe_mosquitto() -> Result:
    running, _ = _container("mosquitto")
    return _tcp(1883) if running else Result(None, "not running - Docker restarts it")


def probe_home_assistant(token: str) -> Result:
    running, uptime = _container("homeassistant")
    if not running:
        return Result(None, "not running - Docker restarts it")
    if uptime < STARTUP_GRACE:
        return Result(None, "Home Assistant is still starting")
    try:
        _ha("/api/", token)
        return Result(True, "the API answers")
    except HTTPError as error:
        return Result(error.code < 500, f"HTTP {error.code}")
    except (URLError, OSError, ValueError) as error:
        return Result(False, f"the API does not answer: {getattr(error, 'reason', error)}")


def probe_ha_mqtt(token: str) -> Result:
    try:
        state = _ha("/api/states/binary_sensor.zigbee2mqtt_bridge_connection_state", token)
    except (HTTPError, URLError, OSError, ValueError) as error:
        return Result(None, f"cannot read the bridge state: {error}")
    value = state.get("state")
    if value == "on":
        return Result(True, "Home Assistant sees the Zigbee bridge")
    return Result(False, f"Home Assistant sees the Zigbee bridge as {value!r} - its MQTT link is down")


def reload_ha_mqtt(token: str) -> str:
    entries = _ha("/api/config/config_entries/entry?domain=mqtt", token) or []
    for entry in entries:
        _ha(f"/api/config/config_entries/entry/{entry['entry_id']}/reload", token, body={})
    return f"reloaded Home Assistant's MQTT integration ({len(entries)} entr{'y' if len(entries) == 1 else 'ies'})"


def house_memory_verdict(newest: float | None, now: float) -> Result:
    if newest is None:
        return Result(None, "the house memory is empty")
    age = now - newest
    if age > HOUSE_MEMORY_STALE:
        return Result(False, f"no event recorded for {age / 60:.0f} minutes")
    return Result(True, f"last event {age / 60:.0f} min ago")


def probe_house_memory() -> Result:
    if not HOUSE_MEMORY_DB.exists():
        return Result(None, "no house memory yet")
    try:
        conn = sqlite3.connect(f"file:{HOUSE_MEMORY_DB}?mode=ro", uri=True, timeout=10)
        try:
            newest = conn.execute("SELECT max(ts) FROM events").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as error:
        return Result(None, f"cannot read the house memory: {error}")
    return house_memory_verdict(newest, time.time())


def probe_docker() -> Result:
    try:
        out = _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
    except (OSError, subprocess.TimeoutExpired) as error:
        return Result(False, f"docker does not answer: {error}")
    return Result(out.returncode == 0, "the daemon answers" if out.returncode == 0 else out.stderr.strip()[:200])


def probe_disk(path: str = "/", min_free_gb: float = 10.0) -> Result:
    st = os.statvfs(path)
    free = st.f_bavail * st.f_frsize / 1e9
    total = st.f_blocks * st.f_frsize / 1e9
    ok = free >= min_free_gb and free / total >= 0.05
    return Result(ok, f"{free:.0f} GB free of {total:.0f} GB")


def restart_container(name: str) -> Callable[[], str]:
    def act() -> str:
        out = _run(["docker", "restart", name], timeout=120)
        if out.returncode:
            raise RuntimeError(out.stderr.strip()[:200])
        return f"restarted the {name} container"
    return act


def restart_unit(unit: str, user: bool = True) -> Callable[[], str]:
    def act() -> str:
        args = ["systemctl"] + (["--user"] if user else []) + ["restart", "--no-ask-password", unit]
        out = _run(args, timeout=120)
        if out.returncode:
            raise RuntimeError(out.stderr.strip()[:200] or f"systemctl exited {out.returncode}")
        return f"restarted {unit}"
    return act


def build_checks(token: str) -> list[Check]:
    return [
        Check("docker", "Docker", probe_docker, None, needed=2,
              advice="The containers (Home Assistant, Zigbee, MQTT) depend on it. Run: sudo systemctl restart docker"),
        Check("mosquitto", "MQTT broker", probe_mosquitto, restart_container("mosquitto"), depends=("docker",)),
        Check("zigbee", "Zigbee", probe_zigbee, restart_container("zigbee2mqtt"), needed=1,
              depends=("docker", "mosquitto"),
              advice="If a restart does not bring it back, unplug the Zigbee dongle for ten seconds."),
        Check("home_assistant", "Home Assistant", lambda: probe_home_assistant(token),
              restart_container("homeassistant"), needed=3, cooldown=1800, depends=("docker",)),
        Check("ha_mqtt", "Home Assistant's Zigbee link", lambda: probe_ha_mqtt(token),
              lambda: reload_ha_mqtt(token), depends=("home_assistant", "mosquitto", "zigbee")),
        Check("dashboard", "Dashboard", lambda: _http_alive("http://127.0.0.1:8000/api/health"),
              restart_unit("smart-home-dashboard.service")),
        Check("go2rtc", "Cameras (go2rtc)", lambda: _http_alive("http://127.0.0.1:1984/api/streams"),
              restart_unit("go2rtc.service")),
        Check("house_memory", "House memory", probe_house_memory, restart_unit("house-memory.service"),
              needed=1, cooldown=3600, depends=("home_assistant",)),
        Check("matter_server", "Matter controller", lambda: _tcp(5580),
              restart_unit("matter-server.service", user=False),
              advice="It is a system service: if restarting it is refused, run scripts/install-service-watchdog.sh once with sudo."),
        Check("disk", "Disk space", probe_disk, None, needed=1,
              advice="Free space on the NVMe: old camera recordings, Docker images (docker system prune)."),
    ]


# ── The decision, kept apart from the probes so it can be tested ──

@dataclass
class Outcome:
    events: list[dict[str, Any]] = field(default_factory=list)
    report: list[str] = field(default_factory=list)


def run_checks(checks: list[Check], state: dict[str, Any], now: float, act: bool = True) -> Outcome:
    """One pass. `state` is updated in place: per check, failures in a row,
    the times it acted, and whether it has given up."""
    outcome = Outcome()
    health: dict[str, bool | None] = {}
    for check in checks:
        s = state.setdefault(check.name, {"failures": 0, "actions": [], "gave_up": False})
        if any(health.get(dep) is False for dep in check.depends):
            health[check.name] = None
            outcome.report.append(f"{check.name}: skipped, depends on {'/'.join(check.depends)}")
            continue
        try:
            result = check.probe()
        except Exception as error:  # noqa: BLE001 - a broken probe must not stop the others
            result = Result(None, f"probe failed: {error}")
        health[check.name] = result.healthy
        outcome.report.append(f"{check.name}: {'ok' if result.healthy else 'FAIL' if result.healthy is False else '?'} - {result.detail}")
        if result.healthy is None:
            continue
        if result.healthy:
            if s["gave_up"] or s["failures"] >= check.needed:
                outcome.events.append(_event(check, "recovered", f"{check.label} is working again", now))
            s.update(failures=0, gave_up=False)
            continue
        s["failures"] += 1
        s["last_detail"] = result.detail
        if s["failures"] < check.needed or s["gave_up"]:
            continue
        s["actions"] = [t for t in s["actions"] if now - t < ACTION_WINDOW]
        if check.action is None:
            s["gave_up"] = True
            outcome.events.append(_event(check, "needs_person", f"{check.label}: {result.detail}. {check.advice}", now))
            continue
        if s["actions"] and now - s["actions"][-1] < check.cooldown:
            continue
        if len(s["actions"]) >= MAX_ACTIONS:
            s["gave_up"] = True
            outcome.events.append(_event(
                check, "needs_person",
                f"{check.label} is still failing after {MAX_ACTIONS} restarts in {ACTION_WINDOW // 3600} h: "
                f"{result.detail}. {check.advice}".strip(), now))
            continue
        if not act:
            outcome.report.append(f"{check.name}: would act now")
            continue
        try:
            done = check.action()
            s["actions"].append(now)
            s["failures"] = 0
            outcome.events.append(_event(check, "restarted", f"{check.label}: {result.detail} - {done}", now))
        except Exception as error:  # noqa: BLE001
            s["actions"].append(now)
            outcome.events.append(_event(check, "action_failed",
                                         f"{check.label}: {result.detail}; the fix failed: {error}. {check.advice}".strip(), now))
    return outcome


def _event(check: Check, kind: str, message: str, now: float) -> dict[str, Any]:
    return {"id": f"{check.name}-{int(now)}", "check": check.name, "label": check.label,
            "kind": kind, "message": message, "at": now}


def record_history(history: list[list[Any]], events: list[dict[str, Any]], now: float) -> list[list[Any]]:
    """[check, kind, at] for every restart and give-up, the last HISTORY_DAYS."""
    kept = [h for h in history if now - h[2] < HISTORY_DAYS * 86400]
    return kept + [[e["check"], e["kind"], e["at"]] for e in events if e["kind"] in COUNTED]


def reliability(history: list[list[Any]], now: float) -> dict[str, dict[str, Any]]:
    """Per check: restarts in the last 24 h, 7 and 30 days, the last one, and
    how often it needed a person in 30 days."""
    table: dict[str, dict[str, Any]] = {}
    for check, kind, at in history:
        row = table.setdefault(check, {"day": 0, "week": 0, "month": 0, "last": None, "needs_person": 0})
        age = now - at
        if kind == "needs_person":
            row["needs_person"] += age < 30 * 86400
            continue
        row["day"] += age < 86400
        row["week"] += age < 7 * 86400
        row["month"] += age < 30 * 86400
        row["last"] = max(row["last"] or 0, at)
    return table


# ── State, the dashboard's status file, and Home Assistant ──

def load_status(path: Path = STATUS_PATH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"checks": {}, "events": [], "report": []}


def save_status(doc: dict[str, Any], path: Path = STATUS_PATH) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(path)


def notify_home_assistant(token: str, events: list[dict[str, Any]]) -> None:
    """Best effort: when Home Assistant is the thing that is down, the status
    file (and so the dashboard) still has it."""
    for event in events:
        title = {"restarted": "Watchdog fixed something", "recovered": "Working again",
                 "needs_person": "Needs attention", "action_failed": "Watchdog could not fix it"}[event["kind"]]
        try:
            _ha("/api/services/persistent_notification/create", token, body={
                "notification_id": f"service_watchdog_{event['check']}",
                "title": f"{title}: {event['label']}", "message": event["message"]})
        except (HTTPError, URLError, OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="probe and report; restart nothing, save nothing")
    args = ap.parse_args(argv)

    from src.python.automation_author import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("HOME_ASSISTANT_TOKEN", "")
    doc = load_status()
    paused = PAUSE_FLAG.exists()
    now = time.time()
    outcome = run_checks(build_checks(token), doc.setdefault("checks", {}), now, act=not (args.dry_run or paused))
    for line in outcome.report:
        print(line)
    if paused:
        print("paused by deploy/watchdog/.paused: nothing acted")
    if args.dry_run:
        return 0
    doc["events"] = (doc.get("events", []) + outcome.events)[-EVENTS_KEPT:]
    doc["history"] = record_history(doc.get("history", []), outcome.events, now)
    doc.setdefault("since", now)
    doc["report"] = outcome.report
    doc["checked_at"] = now
    doc["paused"] = paused
    save_status(doc)
    for event in outcome.events:
        print(f"EVENT {event['kind']}: {event['message']}")
    notify_home_assistant(token, outcome.events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
