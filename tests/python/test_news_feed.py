"""The header news line's data: parsing, what counts as breaking, and the settings.

The rules that matter:

  * sources and prices are picked by id from an allow-list, never by URL, so the
    settings endpoint cannot make the board fetch an arbitrary address;
  * "Breaking" is a top story under two hours old - the feeds have no flag;
  * a feed that fails keeps its last good copy rather than blanking the card;
  * switched off means nothing is fetched at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.python import news_feed
from src.python.web_app import create_app

NOW = 1_789_640_000.0  # a fixed "now" for age arithmetic

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>BBC</title>
  <item><title>Fresh story</title><link>https://example.test/a</link>
        <pubDate>Thu, 17 Sep 2026 05:00:18 GMT</pubDate></item>
  <item><title>  Older
        story </title><link>javascript:alert(1)</link>
        <pubDate>Wed, 16 Sep 2026 18:36:16 GMT</pubDate></item>
  <item><title></title><pubDate>Wed, 16 Sep 2026 18:36:16 GMT</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Atom story</title><link href="https://example.test/b"/>
         <updated>2026-09-16T16:47:40Z</updated></entry>
</feed>"""

CHART = json.dumps({"chart": {"result": [{
    "meta": {"regularMarketPrice": 7551.81, "chartPreviousClose": 7585.73},
    "indicators": {"quote": [{"close": [7598.8, None, 7600.6] + [7550.0 + i for i in range(40)]}]},
}]}}).encode()


def test_rss_items_are_parsed_and_unsafe_links_dropped() -> None:
    items = news_feed.parse_feed(RSS)

    assert [i["title"] for i in items] == ["Fresh story", "Older story"]
    assert items[0]["link"] == "https://example.test/a"
    assert items[1]["link"] == ""  # a javascript: link must never reach the page
    assert items[0]["published"] > items[1]["published"]


def test_atom_entries_and_iso_dates_are_parsed() -> None:
    items = news_feed.parse_feed(ATOM)

    assert items == [{"title": "Atom story", "link": "https://example.test/b",
                      "published": items[0]["published"]}]
    assert items[0]["published"] is not None


def test_chart_gives_price_change_and_a_bounded_sparkline() -> None:
    quote = news_feed.parse_chart(CHART)

    assert quote["price"] == 7551.81
    assert round(quote["change_percent"], 2) == -0.45
    assert None not in quote["spark"]
    assert len(quote["spark"]) <= news_feed.SPARK_POINTS + 1
    assert quote["spark"][-1] == 7589.0  # the latest close is always kept


def _feed(fid: str) -> news_feed.Feed:
    return news_feed.Feed(fid, fid.upper(), f"https://example.test/{fid}")


def test_only_a_fresh_top_story_is_breaking_and_it_comes_first() -> None:
    world = [
        {"title": "Old world", "link": "", "published": NOW - 5 * 3600},
        {"title": "Fresh world", "link": "", "published": NOW - 30 * 60},
    ]
    money = [{"title": "Fed hikes", "link": "", "published": NOW - 3600}]

    picked = news_feed.select_headlines(
        [("breaking", _feed("bbc"), world), ("finance", _feed("cnbc"), money)], NOW
    )

    assert [(h["title"], h["kind"]) for h in picked] == [
        ("Fresh world", "breaking"),
        ("Fed hikes", "finance"),
        ("Old world", "world"),
    ]


def test_sources_take_turns_and_stale_stories_are_dropped() -> None:
    busy = [{"title": f"Busy {i}", "link": "", "published": NOW - 3 * 3600 - i} for i in range(5)]
    quiet = [
        {"title": "Weeks old", "link": "", "published": NOW - 30 * 24 * 3600},
        {"title": "Quiet 0", "link": "", "published": NOW - 7 * 3600},
    ]

    picked = news_feed.select_headlines(
        [("breaking", _feed("busy"), busy), ("breaking", _feed("quiet"), quiet)], NOW
    )
    titles = [h["title"] for h in picked]

    assert titles[:3] == ["Busy 0", "Quiet 0", "Busy 1"]
    assert "Weeks old" not in titles


def test_the_same_headline_from_two_feeds_shows_once() -> None:
    story = {"title": "Same Story", "link": "", "published": NOW - 60}
    picked = news_feed.select_headlines(
        [("breaking", _feed("a"), [story]), ("breaking", _feed("b"), [dict(story, title="same story")])], NOW
    )

    assert len(picked) == 1


def test_settings_keep_only_known_ids_and_fill_defaults() -> None:
    settings = news_feed.normalize_settings({
        "enabled": True,
        "finance": "yes",  # not a bool: ignored, default kept
        "breaking_sources": ["bbc_world", "https://evil.test/feed", "bbc_world"],
        "market_ids": ["sp500", "nope"],
    })

    assert settings["finance"] is True
    assert settings["breaking_sources"] == ["bbc_world"]
    assert settings["market_ids"] == ["sp500"]
    assert settings["finance_sources"] == news_feed.DEFAULT_SETTINGS["finance_sources"]


def test_a_failing_feed_keeps_its_last_good_copy() -> None:
    clock = [NOW]
    calls = {"n": 0}

    def fetch(url: str) -> bytes:
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("network down")
        return RSS

    service = news_feed.NewsService(fetch=fetch, clock=lambda: clock[0])
    settings = dict(news_feed.DEFAULT_SETTINGS, finance=False, markets=False, breaking_sources=["bbc_world"])

    first = service.payload(settings)
    clock[0] += news_feed.HEADLINE_TTL_S + 1
    second = service.payload(settings)

    assert calls["n"] == 2
    assert [h["title"] for h in second["headlines"]] == [h["title"] for h in first["headlines"]]
    assert second["headlines"]


def test_switched_off_fetches_nothing() -> None:
    def fetch(url: str) -> bytes:
        raise AssertionError(f"fetched {url} while news is off")

    service = news_feed.NewsService(fetch=fetch, clock=lambda: NOW)
    result = service.payload(dict(news_feed.DEFAULT_SETTINGS, enabled=False))

    assert result["headlines"] == [] and result["markets"] == []


def test_markets_are_fetched_by_symbol_from_the_table() -> None:
    urls: list[str] = []

    def fetch(url: str) -> bytes:
        urls.append(url)
        return CHART

    service = news_feed.NewsService(fetch=fetch, clock=lambda: NOW)
    result = service.payload(dict(news_feed.DEFAULT_SETTINGS, breaking=False, finance=False, market_ids=["sp500", "usdcad"]))

    assert [m["id"] for m in result["markets"]] == ["sp500", "usdcad"]
    assert any("%5EGSPC" in u for u in urls)
    assert any("CAD%3DX" in u for u in urls)


class _NoNetworkService(news_feed.NewsService):
    def __init__(self) -> None:
        super().__init__(fetch=lambda url: (_ for _ in ()).throw(AssertionError(url)), clock=lambda: NOW)


def test_settings_endpoint_saves_on_the_board(tmp_path: Path) -> None:
    path = tmp_path / "dashboard_news.json"
    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
        news_settings_path=path,
        news_service=_NoNetworkService(),
    ))

    initial = client.get("/api/news/settings").json()
    assert initial["settings"] == news_feed.DEFAULT_SETTINGS
    assert {s["id"] for s in initial["available"]["markets"]} >= {"sp500", "usdcad", "bitcoin"}

    body = dict(news_feed.DEFAULT_SETTINGS, enabled=False, breaking_sources=["cbc_top", "made_up"])
    saved = client.put("/api/news/settings", json=body).json()

    assert saved["settings"]["enabled"] is False
    assert saved["settings"]["breaking_sources"] == ["cbc_top"]
    assert json.loads(path.read_text())["enabled"] is False
    # Switched off, /api/news answers without touching the network.
    assert client.get("/api/news").json()["headlines"] == []


def test_settings_endpoint_refuses_unknown_fields(tmp_path: Path) -> None:
    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
        news_settings_path=tmp_path / "dashboard_news.json",
        news_service=_NoNetworkService(),
    ))

    body = dict(news_feed.DEFAULT_SETTINGS, feed_url="https://evil.test/")
    assert client.put("/api/news/settings", json=body).status_code == 422
