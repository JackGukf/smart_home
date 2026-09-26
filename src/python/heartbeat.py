"""The board's heartbeat to healthchecks.io - the one watcher outside the house.

Everything else that watches the house runs on this board: the service
watchdog, the alerts, the Telegram bot. When the board dies, loses power or
loses the internet, none of them can say so. So every 5 minutes this pings
HEALTHCHECKS_PING_URL (from .env), and healthchecks.io messages the owner on
Telegram - through its own bot, not the house's - when the pings stop.

The ping also carries the service watchdog's verdict:

  * all well                -> a normal ping, with the watchdog's report as its body
  * the watchdog gave up on something ("needs a person"), or has not written its
    status for 15 minutes   -> a /fail ping, so the owner hears of it off the board
    even when Home Assistant or the house's Telegram bot is what is down

While the watchdog is paused (deploy/watchdog/.paused, during maintenance) a
give-up does not fail the ping; a stale watchdog still does.

Standard library only, run by the system python3: a broken project virtualenv
must not silence the one thing that reports breakage. And if this stops, the
pings stop, which is itself the alert.

    python3 -m src.python.heartbeat            # one ping (the timer runs this)
    python3 -m src.python.heartbeat --dry-run  # show what it would send
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = PROJECT_ROOT / "service_watchdog.json"
WATCHDOG_STALE_S = 15 * 60
ATTEMPTS = 3


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def verdict(status: dict[str, Any] | None, now: float) -> tuple[bool, str]:
    """(healthy, body). The body is what healthchecks.io shows beside the ping."""
    if not status:
        return False, "The service watchdog has never written its status (service_watchdog.json)."
    checked_at = float(status.get("checked_at") or 0)
    age = now - checked_at
    report = [str(line) for line in status.get("report") or []]
    if age > WATCHDOG_STALE_S:
        return False, (f"The service watchdog has not run for {age / 60:.0f} minutes - "
                       "service-watchdog.timer may have stopped.\n" + "\n".join(report))
    stuck = sorted(name for name, check in (status.get("checks") or {}).items()
                   if isinstance(check, dict) and check.get("gave_up"))
    if stuck and not status.get("paused"):
        return False, (f"Needs a person: {', '.join(stuck)} - the watchdog could not fix "
                       f"{'it' if len(stuck) == 1 else 'them'}.\n" + "\n".join(report))
    head = "Paused for maintenance (deploy/watchdog/.paused). " if status.get("paused") else ""
    return True, head + f"All {len(report)} checks reported.\n" + "\n".join(report)


def ping(url: str, healthy: bool, body: str, timeout: float = 10.0,
         sleep=time.sleep, opener=urllib.request.urlopen) -> bool:
    target = url.rstrip("/") + ("" if healthy else "/fail")
    data = body.encode("utf-8")[:10_000]          # healthchecks.io keeps the first 10 kB
    for attempt in range(1, ATTEMPTS + 1):
        try:
            request = urllib.request.Request(target, data=data, method="POST",
                                             headers={"Content-Type": "text/plain; charset=utf-8"})
            with opener(request, timeout=timeout) as response:
                response.read()
            return True
        except (urllib.error.URLError, OSError) as exc:
            # Never the URL: the uuid in it is what lets anyone ping as this board.
            print(f"heartbeat attempt {attempt} failed: {getattr(exc, 'reason', type(exc).__name__)}",
                  file=sys.stderr)
            if attempt < ATTEMPTS:
                sleep(5 * attempt)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent; send nothing")
    args = ap.parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env")
    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status = None
    healthy, body = verdict(status, time.time())
    if args.dry_run:
        print(("OK" if healthy else "FAIL") + "\n" + body)
        return 0
    url = os.getenv("HEALTHCHECKS_PING_URL", "").strip()
    if not url:
        print("HEALTHCHECKS_PING_URL is not set in .env - nothing sent", file=sys.stderr)
        return 0
    sent = ping(url, healthy, body)
    print(("sent OK" if healthy else "sent FAIL") if sent else "not sent")
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
