"""Furnace runtime from Ecobee's own API: the PIN authorisation, the runtime
report, and turning five-minute intervals into hours a day.

No network: every test drives the module's `fetch` seam.
"""
from __future__ import annotations

import json
import sys
import types
import urllib.parse
from datetime import date, datetime
from pathlib import Path

import pytest

from src.python import ecobee_runtime as er


class FakeEcobee:
    """Enough of the API to answer what this module asks it."""

    def __init__(self):
        self.calls: list[str] = []
        self.rows_per_day = 288          # five-minute intervals
        self.refused = False

    def __call__(self, url, headers=None, body=None):
        self.calls.append(url)
        if "/authorize" in url:
            return {"ecobeePin": "ABCD", "code": "the-code", "expires_in": 9, "scope": "smartRead"}
        if "/token" in url:
            if self.refused:
                return {"error": "authorization_pending", "error_description": "waiting for the PIN"}
            return {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}
        if "/1/thermostat?" in url:
            return {"thermostatList": [{"identifier": "511", "name": "My ecobee"}]}
        if "/1/runtimeReport" in url:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            selection = json.loads(query["json"][0])
            start = date.fromisoformat(selection["startDate"])
            rows = []
            # Two hours of heat at 06:00 on the first day, nothing after.
            for interval in range(self.rows_per_day):
                minutes = interval * 5
                seconds = 300 if 360 <= minutes < 480 else 0
                rows.append(f"{start.isoformat()},{minutes // 60:02d}:{minutes % 60:02d}:00,"
                            f"{seconds},0,0,0,0,{seconds},28.4,70.5")
            return {"status": {"code": 0}, "reportList": [{"rowList": rows}]}
        raise AssertionError(url)


def test_the_pin_dance(tmp_path):
    api = FakeEcobee()
    pin = er.request_pin("KEY", api)
    assert pin["ecobeePin"] == "ABCD"
    assert "response_type=ecobeePin" in api.calls[0] and "scope=smartRead" in api.calls[0]

    tokens = er.exchange_pin("KEY", pin["code"], api, now=1000.0)
    assert tokens.access_token == "AT" and tokens.expires_at == 1000.0 + 3600

    path = tmp_path / "ecobee_tokens.json"
    tokens.save(path)
    assert oct(path.stat().st_mode)[-3:] == "600", "a refresh token is a key to the account"
    assert er.Tokens.load(path).refresh_token == "RT"


def test_a_pin_not_yet_entered_is_an_error_a_person_can_read():
    api = FakeEcobee()
    api.refused = True
    with pytest.raises(RuntimeError, match="waiting for the PIN"):
        er.exchange_pin("KEY", "the-code", api)


def test_stale_tokens_are_refreshed_and_written_back(tmp_path):
    api = FakeEcobee()
    path = tmp_path / "t.json"
    er.Tokens("old", "RT-old", 0.0, "KEY").save(path)          # expired
    tokens = er.usable(path, api)
    assert tokens.access_token == "AT"
    assert er.Tokens.load(path).access_token == "AT", "the rotated refresh token must survive"
    assert any("grant_type=refresh_token" in call for call in api.calls)


def test_runtime_rows_become_hours_a_day_in_celsius():
    api = FakeEcobee()
    tokens = er.Tokens("AT", "RT", 9e9, "KEY")
    rows = er.runtime_report(tokens, "511", date(2026, 1, 5), date(2026, 1, 5), api)
    assert len(rows) == 288

    [day] = er.daily_runtime(rows)
    assert day["day"] == "2026-01-05"
    assert day["furnace_hours"] == 2.0                      # 06:00 to 08:00
    assert day["outdoor_mean_c"] == pytest.approx(-2.0, abs=0.05)   # 28.4F
    assert er.stage_totals(rows) == {"auxHeat1": 2.0}       # and not compHeat: this is a furnace


def test_history_is_fetched_in_pieces_the_api_accepts():
    api = FakeEcobee()
    tokens = er.Tokens("AT", "RT", 9e9, "KEY")
    seen: list[tuple] = []
    er.fetch_history(tokens, "511", days=90, fetch=api, today=date(2026, 3, 1),
                     on_chunk=lambda a, b, n: seen.append((a, b)))
    # Pieces the API will accept, covering the window once and contiguously.
    assert all((b - a).days < er.CHUNK_DAYS for a, b in seen)
    assert seen[0][0] == date(2025, 12, 1) and seen[-1][1] == date(2026, 3, 1)
    for (_, before), (after, _) in zip(seen, seen[1:]):
        assert (after - before).days == 1, "no gap and no overlap between pieces"


def test_a_bad_row_is_skipped_not_fatal():
    assert er._row("nonsense") is None
    assert er._row("2026-01-05,00:05:00,300") is None               # too few columns
    row = er._row("2026-01-05,00:05:00,300,0,0,0,0,300,,21.1")
    assert row["auxHeat1"] == 300 and row["outdoorTemp"] is None
    assert row["at"] == datetime(2026, 1, 5, 0, 5)


class FakeWebSession:
    """The signed-in session python-ecobee-api hands back, as far as this uses it."""

    def __init__(self):
        self.requests: list[tuple] = []
        self.thermostats = [{"identifier": "511", "name": "My ecobee"}]

    def _request(self, method, endpoint, log_msg_action, params=None, body=None):
        self.requests.append((method, endpoint, json.loads(params["json"])))
        selection = json.loads(params["json"])
        start = date.fromisoformat(selection["startDate"])
        rows = [f"{start.isoformat()},06:00:00,300,0,0,0,0,300,28.4,70.5",
                f"{start.isoformat()},06:05:00,300,0,0,0,0,300,28.4,70.5"]
        return {"status": {"code": 0}, "reportList": [{"rowList": rows}]}


def test_the_web_session_reads_the_same_runtime_report():
    """Ecobee stopped issuing developer keys, so the account's own sign-in is
    the way in; the report and the parsing are unchanged."""
    session = FakeWebSession()
    rows = er.web_runtime_report(session, date(2026, 1, 5), date(2026, 1, 5))
    assert len(rows) == 2 and rows[0]["auxHeat1"] == 300

    [day] = er.daily_runtime(rows)
    assert day["furnace_hours"] == pytest.approx(10 / 60, abs=0.001)   # two five-minute intervals
    method, endpoint, selection = session.requests[0]
    assert (method, endpoint) == ("GET", "1/runtimeReport")
    assert selection["columns"].startswith("auxHeat1") and selection["includeSensors"] is False


def test_web_history_is_chunked_too():
    session = FakeWebSession()
    seen: list[tuple] = []
    er.web_fetch_history(session, days=70, today=date(2026, 3, 1), on_chunk=lambda a, b, n: seen.append((a, b)))
    assert all((b - a).days < er.CHUNK_DAYS for a, b in seen)
    assert seen[0][0] == date(2025, 12, 21) and seen[-1][1] == date(2026, 3, 1)


def test_the_password_is_never_written_down(tmp_path, monkeypatch):
    """Only tokens are kept, and only the owner can read them."""
    written = {}

    class FakeEcobee:
        def __init__(self, config=None, config_filename=None):
            self.config = config or {}
            self.config_filename = config_filename
            self.thermostats = [{"identifier": "511", "name": "My ecobee"}]

        def request_tokens_web(self):
            return True

        def _write_config(self):
            written["path"] = self.config_filename
            Path(self.config_filename).write_text(json.dumps({"ACCESS_TOKEN": "AT", "REFRESH_TOKEN": "RT"}))

    fake = types.ModuleType("pyecobee")
    fake.Ecobee = FakeEcobee
    const = types.ModuleType("pyecobee.const")
    const.ECOBEE_USERNAME, const.ECOBEE_PASSWORD = "USERNAME", "PASSWORD"
    monkeypatch.setitem(sys.modules, "pyecobee", fake)
    monkeypatch.setitem(sys.modules, "pyecobee.const", const)

    store = tmp_path / "ecobee_web_session.json"
    er.web_login("someone@example.com", "hunter2", store)
    assert store.is_file() and oct(store.stat().st_mode)[-3:] == "600"
    assert "hunter2" not in store.read_text()
