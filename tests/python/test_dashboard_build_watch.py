"""A deployed dashboard reaches browsers that are already open.

A deploy replaces app.js on the board but not the copy a browser is running, and
nothing tells that browser to look again. On a phone you reload without thinking
about it. The wall panel has nobody to do that, so it would hold the build it
booted with until something restarted Chromium.

The rules that matter, and that are easy to break by accident:

  * a changed build number reloads the page, an unchanged one does not;
  * the reload waits for the server to answer, because deploy-dashboard.sh
    restarts the service *after* copying the files - reloading into that gap
    replaces a stale-but-working panel with a Chromium error page;
  * a failed read is never mistaken for a change.

These drive the real functions out of app.js under node, with fetch, timers and
location stubbed, because the rules live in their control flow.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# `pick` has to know about `async function`, or it slices the keyword off and
# the extracted body has an await with no async around it.
HARNESS = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  let at = src.indexOf(`async function ${name}`);
  if (at < 0) at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};

const events = { reloads: 0, buildFetches: 0, healthFetches: 0, timers: 0, badge: null };
globalThis.loadedBuild = null;
globalThis.buildBadge = { set textContent(v) { events.badge = v; } };
globalThis.location = { reload: () => { events.reloads += 1; } };

// Timers run inline so a test does not wait on wall-clock time. The retry chain
// is bounded by the attempt counter in the code under test, not by the clock.
// Each firing is kept so `tick` can wait for the whole chain to unwind - the
// retries are async, so dropping the promises would measure a half-finished run.
const pending = [];
globalThis.setTimeout = (fn) => {
  events.timers += 1;
  pending.push(Promise.resolve().then(fn));
  return 0;
};
let intervalFn = null;
globalThis.setInterval = (fn) => { intervalFn = fn; return 0; };

// Each test sets these: the build the board reports, and whether it answers.
let boardBuild = 1;
let serverUp = true;
globalThis.fetch = async (url) => {
  if (String(url).startsWith('/static/build_info.json')) {
    events.buildFetches += 1;
    if (boardBuild === null) return { ok: false };
    return { ok: true, json: async () => ({ build: boardBuild }) };
  }
  if (String(url).startsWith('/api/health')) {
    events.healthFetches += 1;
    if (!serverUp) throw new Error('connection refused');
    return { ok: true };
  }
  throw new Error(`unexpected fetch: ${url}`);
};

// The poll interval comes from app.js too, so the test cannot drift from it.
eval(src.match(/const BUILD_POLL_MS = [^;]+;/)[0].replace('const ', 'globalThis.'));

eval(pick('fetchBuild') + pick('loadBuildInfo')
   + pick('reloadWhenServerAnswers') + pick('watchForNewBuild'));

const settle = async () => {
  while (pending.length) await Promise.all(pending.splice(0));
};
const tick = async () => { await intervalFn(); await settle(); };
"""


def _run(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS + "(async () => {\n" + script + "\n})();", encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def test_an_unchanged_build_does_not_reload(tmp_path: Path) -> None:
    result = _run("""
boardBuild = 196;
await loadBuildInfo();
watchForNewBuild();
await tick();
await tick();
console.log(JSON.stringify({ ...events, loadedBuild }));
""", tmp_path)
    assert result["reloads"] == 0
    assert result["loadedBuild"] == 196
    assert result["badge"] == "Build #196"


def test_a_new_build_reloads_the_page(tmp_path: Path) -> None:
    result = _run("""
boardBuild = 196;
await loadBuildInfo();
watchForNewBuild();
boardBuild = 197;          // a deploy lands
await tick();
console.log(JSON.stringify(events));
""", tmp_path)
    assert result["reloads"] == 1


def test_the_reload_waits_for_the_server_to_come_back(tmp_path: Path) -> None:
    """The service restarts after the files are copied. Reloading into that gap
    is how a wall panel ends up showing a Chromium error page instead."""
    result = _run("""
boardBuild = 196;
await loadBuildInfo();
watchForNewBuild();
boardBuild = 197;
serverUp = false;          // mid-restart: the new number is up, the server is not
await tick();
const during = { reloads: events.reloads, health: events.healthFetches };
console.log(JSON.stringify({ during }));
""", tmp_path)
    assert result["during"]["reloads"] == 0, "must not reload while the server is down"
    assert result["during"]["health"] > 1, "must keep retrying the health check"


def test_it_reloads_once_the_server_answers_again(tmp_path: Path) -> None:
    result = _run("""
boardBuild = 196;
await loadBuildInfo();
watchForNewBuild();
boardBuild = 197;
let calls = 0;
const realFetch = globalThis.fetch;
globalThis.fetch = async (url) => {
  if (String(url).startsWith('/api/health') && calls++ < 3) throw new Error('down');
  return realFetch(url);
};
await tick();
console.log(JSON.stringify(events));
""", tmp_path)
    assert result["reloads"] == 1


def test_a_failed_read_is_not_a_change(tmp_path: Path) -> None:
    """A flaky fetch must not be read as a deploy and reload the panel."""
    result = _run("""
boardBuild = 196;
await loadBuildInfo();
watchForNewBuild();
boardBuild = null;         // the read fails
await tick();
await tick();
console.log(JSON.stringify({ ...events, loadedBuild }));
""", tmp_path)
    assert result["reloads"] == 0
    assert result["loadedBuild"] == 196, "the known-good build must survive a failed read"


def test_a_failed_first_read_adopts_the_next_number_instead_of_reloading(tmp_path: Path) -> None:
    """If the page loads while a deploy is in flight there is no baseline yet.
    The first number actually seen is that baseline - it is not a change."""
    result = _run("""
boardBuild = null;         // the read at page load fails
await loadBuildInfo();
watchForNewBuild();
boardBuild = 197;
await tick();
console.log(JSON.stringify({ ...events, loadedBuild }));
""", tmp_path)
    assert result["reloads"] == 0
    assert result["loadedBuild"] == 197
    assert result["badge"] == "Build #197"
