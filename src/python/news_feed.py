"""Headlines and market prices for the news line in the dashboard header.

The board fetches them, not the browser. The browser cannot read these sites
directly, and the wall panel should show exactly what any other screen shows, so
the choices live in one file on the board as well (``dashboard_news.json``).

Everything here is an allow-list. A source or a price is picked by id from the
tables below, never by a URL from the request, so the settings endpoint cannot be
used to make the board fetch an arbitrary address.

Feeds are untrusted input: responses are size-capped, parsed without network
access, and a feed that fails leaves the last good copy in place rather than
blanking the card.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

LOGGER = logging.getLogger(__name__)

HEADLINE_TTL_S = 300
QUOTE_TTL_S = 120
FETCH_TIMEOUT_S = 8
MAX_RESPONSE_BYTES = 2_000_000
# A top story from a breaking-news source counts as breaking while it is this
# fresh. The feeds have no "breaking" flag of their own.
BREAKING_WINDOW_S = 2 * 3600
# Top-story feeds keep some items for weeks (CBC's held one from August in
# mid-September), so a headline older than this is not shown at all.
MAX_HEADLINE_AGE_S = 24 * 3600
MAX_WORLD_HEADLINES = 6
MAX_FINANCE_HEADLINES = 4
SPARK_POINTS = 24
USER_AGENT = "Mozilla/5.0 (HomeOS dashboard)"


@dataclass(frozen=True)
class Feed:
    id: str
    name: str
    url: str


@dataclass(frozen=True)
class Market:
    id: str
    name: str
    symbol: str
    decimals: int


BREAKING_SOURCES = {
    f.id: f
    for f in (
        Feed("bbc_world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        Feed("cbc_top", "CBC News", "https://www.cbc.ca/webfeed/rss/rss-topstories"),
        Feed("global_news", "Global News", "https://globalnews.ca/feed/"),
    )
}

FINANCE_SOURCES = {
    f.id: f
    for f in (
        Feed("cnbc_markets", "CNBC Markets",
             "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),
        Feed("yahoo_finance", "Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
        Feed("marketwatch", "MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        Feed("cbc_business", "CBC Business", "https://www.cbc.ca/webfeed/rss/rss-business"),
    )
}

MARKETS = {
    m.id: m
    for m in (
        Market("sp500", "S&P 500", "^GSPC", 2),
        Market("nasdaq", "Nasdaq", "^IXIC", 2),
        Market("dow", "Dow Jones", "^DJI", 2),
        Market("tsx", "S&P/TSX", "^GSPTSE", 2),
        # Yahoo's CAD=X is quoted as Canadian dollars per US dollar.
        Market("usdcad", "USD/CAD", "CAD=X", 4),
        Market("gold", "Gold", "GC=F", 2),
        Market("oil", "Crude oil", "CL=F", 2),
        Market("bitcoin", "Bitcoin", "BTC-USD", 0),
    )
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "breaking": True,
    "finance": True,
    "markets": True,
    "breaking_sources": ["bbc_world", "cbc_top"],
    "finance_sources": ["cnbc_markets", "yahoo_finance"],
    "market_ids": ["sp500", "nasdaq", "tsx", "usdcad", "bitcoin"],
}


# ── Settings ──────────────────────────────────────────────────────────────────

def normalize_settings(raw: Any) -> dict[str, Any]:
    """Fill defaults and drop anything that is not in the allow-lists."""
    data = raw if isinstance(raw, dict) else {}
    settings = dict(DEFAULT_SETTINGS)
    for key in ("enabled", "breaking", "finance", "markets"):
        if isinstance(data.get(key), bool):
            settings[key] = data[key]
    for key, table in (
        ("breaking_sources", BREAKING_SOURCES),
        ("finance_sources", FINANCE_SOURCES),
        ("market_ids", MARKETS),
    ):
        value = data.get(key)
        if isinstance(value, list):
            seen: list[str] = []
            for item in value:
                if isinstance(item, str) and item in table and item not in seen:
                    seen.append(item)
            settings[key] = seen
    return settings


def load_settings(path: Path) -> dict[str, Any]:
    try:
        return normalize_settings(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return normalize_settings(None)


def save_settings(path: Path, raw: Any) -> dict[str, Any]:
    settings = normalize_settings(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return settings


def available_options() -> dict[str, Any]:
    return {
        "breaking_sources": [{"id": f.id, "name": f.name} for f in BREAKING_SOURCES.values()],
        "finance_sources": [{"id": f.id, "name": f.name} for f in FINANCE_SOURCES.values()],
        "markets": [{"id": m.id, "name": m.name} for m in MARKETS.values()],
        "breaking_window_minutes": BREAKING_WINDOW_S // 60,
    }


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_time(text: str | None) -> float | None:
    if not text:
        return None
    text = text.strip()
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(payload: bytes) -> list[dict[str, Any]]:
    """Title, link and publish time from an RSS 2.0 or Atom document."""
    root = ET.fromstring(payload)
    items: list[dict[str, Any]] = []
    for node in root.iter():
        name = _local_name(node.tag)
        if name not in ("item", "entry"):
            continue
        fields: dict[str, str] = {}
        link = ""
        for child in node:
            child_name = _local_name(child.tag)
            if child_name == "link":
                link = (child.text or child.get("href") or "").strip() or link
            elif child_name in ("title", "pubDate", "published", "updated") and child.text:
                fields.setdefault(child_name, child.text.strip())
        title = " ".join(fields.get("title", "").split())
        if not title:
            continue
        published = _parse_time(fields.get("pubDate") or fields.get("published") or fields.get("updated"))
        items.append({
            "title": title,
            "link": link if link.startswith(("https://", "http://")) else "",
            "published": published,
        })
    return items


def parse_chart(payload: bytes) -> dict[str, Any] | None:
    """Price, previous close and an intraday line from Yahoo's chart API."""
    data = json.loads(payload)
    results = (data.get("chart") or {}).get("result") or []
    if not results:
        return None
    result = results[0]
    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice")
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [float(c) for c in (quotes.get("close") or []) if isinstance(c, (int, float))]
    if not isinstance(price, (int, float)):
        if not closes:
            return None
        price = closes[-1]
    change = None
    if isinstance(previous, (int, float)) and previous:
        change = (float(price) - float(previous)) / float(previous) * 100
    if len(closes) > SPARK_POINTS:
        step = len(closes) / SPARK_POINTS
        closes = [closes[int(i * step)] for i in range(SPARK_POINTS)] + [closes[-1]]
    return {
        "price": float(price),
        "previous_close": float(previous) if isinstance(previous, (int, float)) else None,
        "change_percent": change,
        "spark": closes,
    }


# ── Fetching ──────────────────────────────────────────────────────────────────

def http_get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=FETCH_TIMEOUT_S) as response:  # noqa: S310 - allow-listed URLs only
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"response over {MAX_RESPONSE_BYTES} bytes")
    return body


def chart_url(symbol: str) -> str:
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?range=1d&interval=15m"


class NewsService:
    """Caches each feed and each price on its own, so one slow site cannot
    hold up the rest and one failing site does not blank the card."""

    def __init__(self, fetch: Callable[[str], bytes] = http_get, clock: Callable[[], float] = time.time):
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cached(self, key: str, ttl: float, load: Callable[[], Any]) -> Any:
        now = self._clock()
        with self._lock:
            hit = self._cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        try:
            value = load()
        except Exception as error:  # noqa: BLE001 - any feed failure keeps the last good copy
            LOGGER.warning("news: %s failed: %s", key, error)
            return hit[1] if hit else None
        with self._lock:
            self._cache[key] = (now, value)
        return value

    def _feed(self, feed: Feed) -> list[dict[str, Any]]:
        items = self._cached(f"feed:{feed.id}", HEADLINE_TTL_S, lambda: parse_feed(self._fetch(feed.url)))
        return items or []

    def _market(self, market: Market) -> dict[str, Any] | None:
        quote_data = self._cached(
            f"quote:{market.id}", QUOTE_TTL_S, lambda: parse_chart(self._fetch(chart_url(market.symbol)))
        )
        if not quote_data:
            return None
        return {"id": market.id, "name": market.name, "decimals": market.decimals, **quote_data}

    def payload(self, settings: dict[str, Any]) -> dict[str, Any]:
        settings = normalize_settings(settings)
        result: dict[str, Any] = {"settings": settings, "headlines": [], "markets": [], "generated_at": self._clock()}
        if not settings["enabled"]:
            return result

        jobs: list[tuple[str, Any]] = []
        if settings["breaking"]:
            jobs += [("breaking", BREAKING_SOURCES[i]) for i in settings["breaking_sources"]]
        if settings["finance"]:
            jobs += [("finance", FINANCE_SOURCES[i]) for i in settings["finance_sources"]]
        markets = [MARKETS[i] for i in settings["market_ids"]] if settings["markets"] else []

        with ThreadPoolExecutor(max_workers=8) as pool:
            feed_futures = [(kind, feed, pool.submit(self._feed, feed)) for kind, feed in jobs]
            market_futures = [pool.submit(self._market, m) for m in markets]
            feeds = [(kind, feed, future.result()) for kind, feed, future in feed_futures]
            result["markets"] = [q for q in (f.result() for f in market_futures) if q]

        result["headlines"] = select_headlines(feeds, self._clock())
        return result


def _round_robin(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    depth = max((len(g) for g in groups), default=0)
    for i in range(depth):
        merged.extend(g[i] for g in groups if i < len(g))
    return merged


def select_headlines(
    feeds: list[tuple[str, Feed, list[dict[str, Any]]]], now: float
) -> list[dict[str, Any]]:
    """Breaking stories first, then world and finance stories, source by source.

    Each feed's first items are its editors' top stories, so only the top few
    from each are considered, in the feed's own order. Sources take turns, so
    one busy feed cannot crowd the others out - sorting everything by time did
    exactly that. Top-story feeds can hold an item for weeks, so anything older
    than a day is dropped, and the same headline from two feeds shows once.
    """
    breaking: list[list[dict[str, Any]]] = []
    world: list[list[dict[str, Any]]] = []
    finance: list[list[dict[str, Any]]] = []
    seen: set[str] = set()
    for kind, feed, items in feeds:
        fresh_list: list[dict[str, Any]] = []
        rest: list[dict[str, Any]] = []
        for item in items[:5]:
            published = item.get("published")
            if published is not None and now - published > MAX_HEADLINE_AGE_S:
                continue
            key = item["title"].casefold()
            if key in seen:
                continue
            seen.add(key)
            entry = {
                "title": item["title"],
                "link": item.get("link", ""),
                "source": feed.name,
                "published": published,
                "kind": kind,
            }
            if kind == "breaking":
                if published is not None and 0 <= now - published <= BREAKING_WINDOW_S:
                    fresh_list.append(entry)
                else:
                    entry["kind"] = "world"
                    rest.append(entry)
            else:
                rest.append(entry)
        if kind == "breaking":
            breaking.append(fresh_list)
            world.append(rest)
        else:
            finance.append(rest)

    world_list = (_round_robin(breaking) + _round_robin(world))[:MAX_WORLD_HEADLINES]
    finance_list = _round_robin(finance)[:MAX_FINANCE_HEADLINES]

    # Interleave so a long run of one kind does not hide the other.
    merged: list[dict[str, Any]] = []
    while world_list or finance_list:
        if world_list:
            merged.append(world_list.pop(0))
        if finance_list:
            merged.append(finance_list.pop(0))
    return merged
