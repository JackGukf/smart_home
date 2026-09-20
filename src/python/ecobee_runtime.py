"""Furnace runtime history from Ecobee's own API, for the gas model.

Home Assistant's ecobee integration reports `hvac_action` - heating or idle,
now. That is enough to accumulate runtime going forward, and nothing at all
about the past. Ecobee's **runtime report** holds every five-minute interval
for roughly the last two years, which is what makes the gas model fittable
against two years of bills today instead of after a winter of watching.

Read-only: the `smartRead` scope, no thermostat is ever written to.

## Getting in, once

**The easy way (2026-09-19).** Ecobee has stopped issuing developer keys
("we are not currently accepting new developer registrations"), but the library
Home Assistant's own ecobee integration uses can log in with the account's
email and password over ecobee's web sign-in. So:

    python -m src.python.ecobee_runtime --login

It asks for the email and password, then - because most accounts have
two-factor sign-in - for the one-time code from the authenticator app or the
text message. The password is held only long enough to sign in, and what is
saved is **tokens**, never the password, in
`ai-data/ecobee_web_session.json` (0600). This is a session of its own: Home
Assistant's tokens are left alone, because ecobee rotates a refresh token and
two clients sharing one would knock each other out.

**The old way**, if ecobee ever issues developer keys again:

    python -m src.python.ecobee_runtime --authorize --api-key YOUR_KEY

It prints a four-character PIN. In ecobee.com -> Menu -> My Apps -> Add
Application, paste the PIN and authorise, then press Enter here. The tokens
land in `ai-data/ecobee_tokens.json` (git-ignored, 0600); the refresh token is
long-lived and is used to mint an access token whenever one is needed.

To register the application: ecobee.com -> Developer -> Create New Application,
"ecobee PIN" authorisation method. It is free, and the key identifies the app,
not the house.

## Then

    python -m src.python.ecobee_runtime --fetch --days 730

Fetches the runtime report in 30-day pieces (the API's limit per call), adds up
the heating seconds in each five-minute interval into hours per day, and writes
them into the AI data database alongside the day's mean outdoor temperature -
which the gas model uses to fill in days the thermostat cannot account for.

Columns: `auxHeat1`/`auxHeat2` are a conventional furnace's stages, seconds run
in that interval; `compHeat1`/`compHeat2` are a heat pump's. This house is a
gas furnace, so auxHeat is the gas, but both are fetched and reported so a
mistaken assumption shows up as a number rather than as silence.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

API = "https://api.ecobee.com"
SCOPE = "smartRead"
CHUNK_DAYS = 30                 # the runtime report's limit per request
HEAT_COLUMNS = ("auxHeat1", "auxHeat2", "auxHeat3", "compHeat1", "compHeat2")
COLUMNS = (*HEAT_COLUMNS, "fan", "outdoorTemp", "zoneAveTemp")
INTERVAL_SECONDS = 300          # five-minute rows
TIMEOUT_S = 60

Fetch = Callable[[str, dict[str, str] | None, bytes | None], dict[str, Any]]


def _http(url: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, headers=headers or {})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 - ecobee's API
        return json.loads(response.read())


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: float
    api_key: str

    @classmethod
    def load(cls, path: Path) -> "Tokens":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(doc["access_token"], doc["refresh_token"], float(doc["expires_at"]), doc["api_key"])

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2) + "\n", encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # a refresh token is a key to the account

    @property
    def stale(self) -> bool:
        return time.time() > self.expires_at - 120


# ── authorising, once ──

def request_pin(api_key: str, fetch: Fetch = _http) -> dict[str, Any]:
    query = urllib.parse.urlencode({"response_type": "ecobeePin", "client_id": api_key, "scope": SCOPE})
    return fetch(f"{API}/authorize?{query}", None, None)


def exchange_pin(api_key: str, code: str, fetch: Fetch = _http, now: float | None = None) -> Tokens:
    query = urllib.parse.urlencode({"grant_type": "ecobeePin", "code": code, "client_id": api_key})
    doc = fetch(f"{API}/token?{query}", None, b"")
    return _tokens_from(doc, api_key, now)


def refresh(tokens: Tokens, fetch: Fetch = _http, now: float | None = None) -> Tokens:
    query = urllib.parse.urlencode({"grant_type": "refresh_token", "code": tokens.refresh_token,
                                    "client_id": tokens.api_key})
    doc = fetch(f"{API}/token?{query}", None, b"")
    return _tokens_from(doc, tokens.api_key, now)


def _tokens_from(doc: dict[str, Any], api_key: str, now: float | None = None) -> Tokens:
    if "access_token" not in doc:
        raise RuntimeError(f"ecobee refused: {doc.get('error_description') or doc}")
    return Tokens(doc["access_token"], doc["refresh_token"],
                  (now or time.time()) + float(doc.get("expires_in", 3600)), api_key)


def usable(path: Path, fetch: Fetch = _http) -> Tokens:
    """Tokens from disk, refreshed if the hour is up. The refresh is written
    back: ecobee rotates the refresh token, so losing it means authorising by
    hand again."""
    tokens = Tokens.load(path)
    if tokens.stale:
        tokens = refresh(tokens, fetch)
        tokens.save(path)
    return tokens


# ── reading ──

def thermostats(tokens: Tokens, fetch: Fetch = _http) -> list[dict[str, str]]:
    selection = {"selection": {"selectionType": "registered", "selectionMatch": "",
                               "includeRuntime": False}}
    query = urllib.parse.urlencode({"json": json.dumps(selection)})
    doc = fetch(f"{API}/1/thermostat?{query}", {"Authorization": f"Bearer {tokens.access_token}"}, None)
    return [{"identifier": t["identifier"], "name": t.get("name", "")}
            for t in doc.get("thermostatList", [])]


def runtime_report(tokens: Tokens, thermostat_id: str, start: date, end: date,
                   fetch: Fetch = _http) -> list[dict[str, Any]]:
    """Five-minute rows between two dates, at most CHUNK_DAYS apart."""
    selection = {
        "selection": {"selectionType": "thermostats", "selectionMatch": thermostat_id},
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "columns": ",".join(COLUMNS), "includeSensors": False,
    }
    query = urllib.parse.urlencode({"json": json.dumps(selection)})
    doc = fetch(f"{API}/1/runtimeReport?{query}", {"Authorization": f"Bearer {tokens.access_token}"}, None)
    status = (doc.get("status") or {}).get("code", 0)
    if status not in (0, None):
        raise RuntimeError(f"ecobee runtime report failed: {(doc.get('status') or {}).get('message')}")
    rows: list[dict[str, Any]] = []
    for report in doc.get("reportList", []):
        for line in report.get("rowList", []):
            parsed = _row(line)
            if parsed:
                rows.append(parsed)
    return rows


def _row(line: str) -> dict[str, Any] | None:
    """"2026-01-04,00:05:00,300,0,0,0,0,300,-4.5,21.1" -> a dict, blanks as None."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2 + len(COLUMNS):
        return None
    try:
        when = datetime.fromisoformat(f"{parts[0]}T{parts[1]}")
    except ValueError:
        return None
    values: dict[str, Any] = {"at": when}
    for name, raw in zip(COLUMNS, parts[2:]):
        try:
            values[name] = float(raw) if raw != "" else None
        except ValueError:
            values[name] = None
    return values


def daily_runtime(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hours the furnace ran on each day, and how cold it was outside.

    Ecobee reports °F in the runtime report regardless of the thermostat's
    display units, so outdoor temperature is converted here and the database
    only ever holds Celsius."""
    heat: dict[date, float] = defaultdict(float)
    outdoor: dict[date, list[float]] = defaultdict(list)
    stages: dict[str, float] = defaultdict(float)
    for row in rows:
        day = row["at"].date()
        seconds = sum(row.get(column) or 0.0 for column in HEAT_COLUMNS)
        heat[day] += min(seconds, INTERVAL_SECONDS * len(HEAT_COLUMNS))
        for column in HEAT_COLUMNS:
            stages[column] += row.get(column) or 0.0
        if row.get("outdoorTemp") is not None:
            outdoor[day].append((row["outdoorTemp"] - 32) * 5 / 9)
    days = []
    for day in sorted(heat):
        temps = outdoor.get(day) or []
        days.append({"day": day.isoformat(), "furnace_hours": round(heat[day] / 3600, 3),
                     "outdoor_mean_c": round(sum(temps) / len(temps), 2) if temps else None})
    return days


def stage_totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Hours per stage over the whole fetch: which stages this house actually
    uses, so "the furnace never ran" can be told from "we read the wrong column"."""
    totals: dict[str, float] = {}
    for column in HEAT_COLUMNS:
        seconds = sum(row.get(column) or 0.0 for row in rows)
        if seconds:
            totals[column] = round(seconds / 3600, 2)
    return totals


def fetch_history(tokens: Tokens, thermostat_id: str, days: int = 730,
                  fetch: Fetch = _http, today: date | None = None,
                  on_chunk: Callable[[date, date, int], None] | None = None) -> list[dict[str, Any]]:
    """The whole history, in pieces the API will accept."""
    end = today or date.today()
    start = end - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:      # <=, or the last piece - which holds today - is never asked for
        stop = min(cursor + timedelta(days=CHUNK_DAYS - 1), end)
        chunk = runtime_report(tokens, thermostat_id, cursor, stop, fetch)
        rows.extend(chunk)
        if on_chunk:
            on_chunk(cursor, stop, len(chunk))
        cursor = stop + timedelta(days=1)
    return rows


# ── ecobee's web sign-in, the way Home Assistant's integration does it ──

WEB_SESSION = "ecobee_web_session.json"


def web_login(username: str, password: str, store: Path,
              ask_code: Callable[[str], str] | None = None) -> Any:
    """Sign in as the account and keep the tokens (never the password).

    An account with two-factor sign-in - which is most of them now - stops
    half way: ecobee's Auth0 raises a challenge, and the one-time code
    finishes it. `ask_code` is how the caller gets that code from the person;
    it is handed the kind of challenge ("otp" for an app, "sms" for a text).
    """
    import pyecobee
    from pyecobee.const import ECOBEE_PASSWORD, ECOBEE_USERNAME
    from pyecobee.errors import EcobeeAuthMfaRequiredError

    store.parent.mkdir(parents=True, exist_ok=True)
    session = pyecobee.Ecobee(config={ECOBEE_USERNAME: username, ECOBEE_PASSWORD: password})
    try:
        ok = session.request_tokens_web()
    except EcobeeAuthMfaRequiredError as challenge_error:
        challenge = challenge_error.args[0]
        if ask_code is None:
            raise RuntimeError("this account needs a one-time code, and there is nobody to ask") from challenge_error
        ok = session.submit_mfa_code(challenge, ask_code(getattr(challenge, "mfa_type", "otp")).strip())
    if not ok:
        raise RuntimeError("ecobee refused the sign-in")
    session.config_filename = str(store)
    session._write_config()
    _only_owner(store)
    return session


def web_session(store: Path) -> Any:
    """A signed-in session from the saved tokens, refreshed by the library."""
    import pyecobee

    session = pyecobee.Ecobee(config_filename=str(store))
    session.update()
    return session


def _only_owner(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def web_runtime_report(session: Any, start: date, end: date) -> list[dict[str, Any]]:
    """The same runtime report, over the library's signed-in session."""
    selection = {
        "selection": {"selectionType": "registered", "selectionMatch": ""},
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "columns": ",".join(COLUMNS), "includeSensors": False,
    }
    raw = session._request("GET", "1/runtimeReport", "get runtime report",
                           params={"json": json.dumps(selection)})
    doc = raw if isinstance(raw, dict) else json.loads(raw or "{}")
    status = (doc.get("status") or {}).get("code", 0)
    if status not in (0, None):
        raise RuntimeError(f"ecobee runtime report failed: {(doc.get('status') or {}).get('message')}")
    rows: list[dict[str, Any]] = []
    for report in doc.get("reportList", []):
        for line in report.get("rowList", []):
            parsed = _row(line)
            if parsed:
                rows.append(parsed)
    return rows


def web_fetch_history(session: Any, days: int = 730, today: date | None = None,
                      on_chunk: Callable[[date, date, int], None] | None = None) -> list[dict[str, Any]]:
    end = today or date.today()
    cursor = end - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    while cursor <= end:
        stop = min(cursor + timedelta(days=CHUNK_DAYS - 1), end)
        chunk = web_runtime_report(session, cursor, stop)
        rows.extend(chunk)
        if on_chunk:
            on_chunk(cursor, stop, len(chunk))
        cursor = stop + timedelta(days=1)
    return rows


# ── the command line ──

def _token_path(project_root: Path) -> Path:
    return Path(os.getenv("ECOBEE_TOKENS", project_root / "ai-data" / "ecobee_tokens.json"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    project_root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--login", action="store_true",
                    help="sign in with the ecobee account's email and password (the usual way now)")
    ap.add_argument("--authorize", action="store_true", help="get a PIN and swap it for tokens (needs a developer key)")
    ap.add_argument("--fetch", action="store_true", help="fetch runtime history into the AI data database")
    ap.add_argument("--api-key", default=os.getenv("ECOBEE_API_KEY"), help="your ecobee developer app key")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--thermostat", help="identifier, if the account has more than one")
    ap.add_argument("--db", default=str(project_root / "ai-data" / "gas.db"))
    args = ap.parse_args(argv)
    tokens_path = _token_path(project_root)

    web_store = tokens_path.with_name(WEB_SESSION)

    if args.login:
        import getpass

        username = input("ecobee email: ").strip()
        password = getpass.getpass("ecobee password (not stored): ")

        def ask_code(kind: str) -> str:
            where = "your authenticator app" if kind == "otp" else "the text message"
            return input(f"ecobee sent a challenge - the one-time code from {where}: ")

        session = web_login(username, password, web_store, ask_code)
        print(f"signed in; tokens in {web_store}")
        for thermostat in session.thermostats:
            print(f"  thermostat {thermostat['identifier']}  {thermostat.get('name', '')}")
        return 0

    if args.authorize:
        if not args.api_key:
            print("--api-key is needed (ecobee.com -> Developer -> Create New Application, "
                  "authorisation method 'ecobee PIN')", file=sys.stderr)
            return 1
        pin = request_pin(args.api_key)
        print(f"\n  PIN: {pin['ecobeePin']}\n\n"
              f"  In ecobee.com -> Menu -> My Apps -> Add Application, paste that PIN and authorise.\n"
              f"  It is valid for {int(pin.get('expires_in', 9))} minutes.")
        input("  Press Enter once you have done it... ")
        tokens = exchange_pin(args.api_key, pin["code"])
        tokens.save(tokens_path)
        print(f"authorised; tokens in {tokens_path}")
        for thermostat in thermostats(tokens):
            print(f"  thermostat {thermostat['identifier']}  {thermostat['name']}")
        return 0

    if not args.fetch:
        ap.print_help()
        return 0

    from src.python import ai_data

    if web_store.is_file():
        # The web sign-in, which is what an account without a developer key has.
        session = web_session(web_store)

        def say_web(start: date, stop: date, count: int) -> None:
            print(f"  {start} to {stop}: {count} intervals")

        rows = web_fetch_history(session, args.days, on_chunk=say_web)
        days = daily_runtime(rows)
        stages = stage_totals(rows)
        print(f"{len(rows)} intervals, {len(days)} days")
        print("stages used: " + (", ".join(f"{k} {v} h" for k, v in stages.items())
                                 or "none - the furnace never ran in this window"))
        db = ai_data.connect(args.db)
        print(f"wrote {ai_data.record_runtime(db, days, 'ecobee')} days into {args.db}")
        return 0

    if not tokens_path.is_file():
        print(f"no ecobee session yet - run --login (or --authorize with a developer key)", file=sys.stderr)
        return 1
    tokens = usable(tokens_path)
    identifier = args.thermostat
    if not identifier:
        found = thermostats(tokens)
        if len(found) != 1:
            print(f"say which thermostat with --thermostat: {found}", file=sys.stderr)
            return 1
        identifier = found[0]["identifier"]

    def say(start: date, stop: date, count: int) -> None:
        print(f"  {start} to {stop}: {count} intervals")

    rows = fetch_history(tokens, identifier, args.days, on_chunk=say)
    days = daily_runtime(rows)
    stages = stage_totals(rows)
    print(f"{len(rows)} intervals, {len(days)} days")
    print("stages used: " + (", ".join(f"{k} {v} h" for k, v in stages.items()) or "none - the furnace never ran"))

    db = ai_data.connect(args.db)
    written = ai_data.record_runtime(db, days, "ecobee")
    print(f"wrote {written} days into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
