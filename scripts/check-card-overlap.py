#!/usr/bin/env python3
"""Look for text sitting on top of other text, at every size the house uses.

A card that reads perfectly on the wall panel can collide on a phone: the
Temperatures card's own labels landed on its chart on an iPhone (2026-09-20),
and nothing in the test suite could have caught it, because overlap is a
question about *layout* and layout needs a browser.

So this drives the board's own Chromium over the DevTools protocol, loads the
dashboard at each device size, and asks the page which pieces of text overlap
each other. It reports:

  * **overlap** - two elements that each hold their own text, whose boxes
    intersect. This is the one that looks broken.
  * **clipped** - text wider than the box it is in, cut off mid-word.
  * **spill**   - text outside its card's bounds, which is how a chart drawn
    at a fixed height escapes a short row.

Run it on the board, where Chromium lives and the dashboard trusts loopback:

    .venv/bin/python scripts/check-card-overlap.py                  # every view, every size
    .venv/bin/python scripts/check-card-overlap.py --view home --device iphone15
    .venv/bin/python scripts/check-card-overlap.py --json           # for a machine

Exit status is 1 when anything overlaps, so it can gate a deploy.

The dashboard asks everyone to log in. This signs itself in the way the TV cast
does - a session cookie minted from the configured password
(`dashboard_cast.session_cookie`) - and **stops if it lands on the login page
anyway**: a checker that silently examines a login form reports no overlaps and
means nothing, which is exactly what happened the first time this ran.
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The screens this house actually reads the dashboard on.
DEVICES: dict[str, tuple[int, int, float]] = {
    "iphone15": (393, 852, 3.0),      # the owner's phone, portrait
    "iphone15-landscape": (852, 393, 3.0),
    "ipad13": (1024, 1366, 2.0),      # iPad Air 13", portrait
    "wallpanel": (1920, 1080, 1.0),   # the hallway Raspberry Pi
    "voicepanel": (480, 480, 1.0),    # not the dashboard, but a useful narrow case
    "laptop": (1440, 900, 1.0),
    "desktop": (2560, 1440, 1.0),
}

VIEWS = ("home", "cameras", "energy", "devices", "alarm", "climate", "status", "ai", "settings")

# Text that is meant to sit over something else: a badge on a tile, a label
# inside a dial. Each is an element whose own CSS says it is layered.
_FINDER = r"""
(() => {
  // What a person can actually see of an element: its box, cut down by every
  // ancestor that clips. Without this, a caption with `overflow: hidden` that
  // ellipses its own text is reported as overlapping its neighbour, because
  // the text's box runs on past the edge that hides it.
  const RECTS = (el) => {
    const r = el.getBoundingClientRect();
    let box = { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    for (let n = el.parentElement; n && n !== document.documentElement; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.overflow === "visible" && s.overflowX === "visible" && s.overflowY === "visible") continue;
      const rn = n.getBoundingClientRect();
      box = { left: Math.max(box.left, rn.left), top: Math.max(box.top, rn.top),
              right: Math.min(box.right, rn.right), bottom: Math.min(box.bottom, rn.bottom) };
      if (box.right <= box.left || box.bottom <= box.top) break;
    }
    box.width = Math.max(0, box.right - box.left);
    box.height = Math.max(0, box.bottom - box.top);
    return box;
  };
  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || Number(s.opacity) < 0.05) return false;
    const r = RECTS(el);
    return r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0;
  };
  // An element "holds text" when it has a non-empty text node of its own.
  const ownText = (el) => {
    let text = "";
    for (const node of el.childNodes) {
      if (node.nodeType === 3) text += node.textContent;
    }
    return text.trim();
  };
  const layered = (el) => {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.position === "absolute" || s.position === "fixed" || s.position === "sticky") return true;
      if (Number(s.zIndex) > 0) return true;
    }
    return false;
  };
  const overlap = (a, b) => {
    const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    return x > 1.5 && y > 1.5 ? { x, y } : null;
  };
  const where = (el) => {
    const card = el.closest("[data-home-card], .panel, .app-tile, .view-panel");
    return (card?.dataset?.homeCard || card?.dataset?.viewPanel || card?.className || "page").toString().slice(0, 40);
  };
  const label = (el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}` +
    `${el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : ""}`;

  const panel = document.querySelector(".view-panel.active") || document.body;
  const texts = [...panel.querySelectorAll("*")].filter((el) => visible(el) && ownText(el) && !layered(el));

  const findings = [];
  for (let i = 0; i < texts.length; i++) {
    const a = texts[i], ra = RECTS(a);
    // Text cut off by the box it is in.
    const style = getComputedStyle(a);
    if (style.overflow !== "visible" && a.scrollWidth > a.clientWidth + 2 && style.textOverflow !== "ellipsis") {
      findings.push({ kind: "clipped", where: where(a), a: label(a), text: ownText(a).slice(0, 40),
                      by: Math.round(a.scrollWidth - a.clientWidth) });
    }
    // Text outside the card it belongs to.
    const card = a.closest("[data-home-card], .panel");
    if (card) {
      const rc = RECTS(card);
      const out = Math.max(rc.top - ra.top, ra.bottom - rc.bottom);
      if (out > 3) {
        findings.push({ kind: "spill", where: where(a), a: label(a), text: ownText(a).slice(0, 40),
                        by: Math.round(out) });
      }
    }
    for (let j = i + 1; j < texts.length; j++) {
      const b = texts[j];
      if (a.contains(b) || b.contains(a)) continue;
      const hit = overlap(ra, RECTS(b));
      if (hit) {
        findings.push({ kind: "overlap", where: where(a), a: label(a), b: label(b),
                        text: ownText(a).slice(0, 30), other: ownText(b).slice(0, 30),
                        by: Math.round(Math.min(hit.x, hit.y)) });
      }
    }
  }
  return findings;
})()
"""


@dataclass
class Finding:
    device: str
    view: str
    kind: str
    where: str
    detail: str
    by: int

    def line(self) -> str:
        return f"  {self.kind:8} {self.device:18} {self.view:9} {self.where:22} {self.detail} (by {self.by}px)"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Chromium:
    """Headless Chromium over the DevTools protocol, without a driver library."""

    def __init__(self, binary: str, port: int):
        self.binary = binary
        self.port = port
        self.profile = tempfile.mkdtemp(prefix="overlap-")
        self.process: subprocess.Popen | None = None

    def __enter__(self) -> "Chromium":
        self.process = subprocess.Popen(
            [self.binary, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
             "--mute-audio", "--password-store=basic", f"--remote-debugging-port={self.port}",
             f"--user-data-dir={self.profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=1).read()
                return self
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("Chromium did not open its debugging port")

    def __exit__(self, *_: Any) -> None:
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def page_url(self) -> str:
        """A fresh tab. Chromium wants PUT here since 111; GET answers 405."""
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/json/new?about:blank",
                                         method="PUT")
        return json.loads(urllib.request.urlopen(request, timeout=10).read())["webSocketDebuggerUrl"]


class Page:
    """One tab, driven over the DevTools protocol with aiohttp - which the
    board already has, unlike a websocket library or a browser driver."""

    def __init__(self, session: Any, ws: Any):
        self.session = session
        self.ws = ws
        self.id = 0

    @classmethod
    async def open(cls, url: str) -> "Page":
        import aiohttp

        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        ws = await session.ws_connect(url, max_msg_size=64 * 1024 * 1024)
        return cls(session, ws)

    async def send(self, method: str, **params: Any) -> dict[str, Any]:
        self.id += 1
        await self.ws.send_json({"id": self.id, "method": method, "params": params})
        while True:
            message = await self.ws.receive_json()
            if message.get("id") == self.id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    async def close(self) -> None:
        await self.ws.close()
        await self.session.close()


def _cookie(config_path: Path) -> str:
    """The dashboard session the TV cast uses, so this sees the dashboard
    rather than its login form."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.python.dashboard_cast import session_cookie

    try:
        return session_cookie(config_path)
    except (OSError, KeyError, ValueError):
        return ""


class NotSignedIn(RuntimeError):
    """The browser is looking at the login page, so any finding would be a lie."""


async def _check(url: str, devices: list[str], views: list[str], binary: str,
                 settle: float, cookie: str = "") -> list[Finding]:
    import asyncio

    findings: list[Finding] = []
    with Chromium(binary, _free_port()) as browser:
        page = await Page.open(browser.page_url())
        try:
            await page.send("Page.enable")
            await page.send("Runtime.enable")
            await page.send("Network.enable")
            if cookie:
                await page.send("Network.setCookie", name="session", value=cookie, url=url)
            for device in devices:
                width, height, scale = DEVICES[device]
                await page.send("Emulation.setDeviceMetricsOverride", width=width, height=height,
                                deviceScaleFactor=scale, mobile=width < 500)
                await page.send("Page.navigate", url=url)
                await asyncio.sleep(settle)
                landed = await page.send("Runtime.evaluate", returnByValue=True, expression=(
                    "({path: location.pathname,"
                    " views: document.querySelectorAll('.view-panel').length})"))
                seen = landed.get("result", {}).get("value") or {}
                if seen.get("path", "").startswith("/login") or not seen.get("views"):
                    raise NotSignedIn(
                        f"the dashboard showed {seen.get('path') or 'nothing'} rather than its views - "
                        "check dashboard_auth in the config, or pass --config")
                for view in views:
                    await page.send("Runtime.evaluate", expression=(
                        f'document.querySelector(\'[data-view="{view}"]\')?.click()'), awaitPromise=False)
                    await asyncio.sleep(1.0)
                    result = await page.send("Runtime.evaluate", expression=_FINDER, returnByValue=True)
                    for row in result.get("result", {}).get("value") or []:
                        detail = (f"{row['a']} over {row['b']}: {row['text']!r} / {row['other']!r}"
                                  if row["kind"] == "overlap" else f"{row['a']}: {row['text']!r}")
                        findings.append(Finding(device, view, row["kind"], row["where"], detail, row["by"]))
        finally:
            await page.close()
    return findings


def check(url: str, devices: list[str], views: list[str], binary: str,
          settle: float = 3.0, cookie: str = "") -> list[Finding]:
    import asyncio

    return asyncio.run(_check(url, devices, views, binary, settle, cookie))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000/?screen=tv")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "configs" / "devices.local.yaml"),
                    help="where the dashboard's login lives, for the session cookie")
    ap.add_argument("--device", action="append", choices=sorted(DEVICES), help="default: all of them")
    ap.add_argument("--view", action="append", choices=VIEWS, help="default: all of them")
    ap.add_argument("--chromium", default=shutil.which("chromium") or shutil.which("chromium-browser") or "")
    ap.add_argument("--kind", action="append", choices=("overlap", "clipped", "spill"),
                    help="default: overlap only, which is the one that looks broken")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.chromium:
        print("no chromium found; run this on the board, or pass --chromium", file=sys.stderr)
        return 2


    kinds = set(args.kind or ["overlap"])
    try:
        findings = [f for f in check(args.url, args.device or list(DEVICES), args.view or list(VIEWS),
                                     args.chromium, cookie=_cookie(Path(args.config))) if f.kind in kinds]
    except NotSignedIn as error:
        print(f"not signed in: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=1))
    elif findings:
        print(f"{len(findings)} finding(s):")
        for finding in sorted(findings, key=lambda f: (f.kind, f.device, f.view)):
            print(finding.line())
    else:
        print(f"no {', '.join(sorted(kinds))} findings on "
              f"{len(args.device or DEVICES)} device(s) x {len(args.view or VIEWS)} view(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
