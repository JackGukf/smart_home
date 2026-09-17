"""Two small pieces of logic in app.js that are easy to break quietly.

  * parseYoutubeLink: only a real 11-character video id may come out of a pasted
    link, whatever form the link takes, and anything else is refused;
  * skyPhase: the Weather card's sky follows the forecast's sunrise and sunset,
    not fixed hours.

Driven under node with the real functions sliced out of app.js, like
test_dashboard_build_watch.py.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
const constant = (name) => {
  const m = new RegExp(`const ${name} = [^\\\\n]*;`).exec(src);
  if (!m) throw new Error(`missing const ${name}`);
  return m[0];
};
eval([constant('YOUTUBE_ID'), constant('SKY_TWILIGHT_MIN'),
      pick('youtubeStartSeconds'), pick('parseYoutubeLink'),
      pick('minutesOfDay'), pick('skyPhase')].join('\\n') + `
const cases = JSON.parse(process.argv[3]);
const at = (hh, mm) => { const d = new Date(2026, 8, 16, hh, mm); return d; };
const weather = { sunrise: '2026-09-16T06:50', sunset: '2026-09-16T19:22' };
console.log(JSON.stringify({
  links: cases.links.map((l) => parseYoutubeLink(l)),
  phases: cases.times.map(([h, m]) => skyPhase(at(h, m), weather)),
  fallback: skyPhase(at(12, 0), null),
}));
`);
"""


def _run(tmp_path: Path, links: list[str], times: list[tuple[int, int]]) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS), json.dumps({"links": links, "times": times})],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_every_common_link_form_yields_the_video_id(tmp_path: Path) -> None:
    links = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "youtube.com/watch?v=dQw4w9WgXcQ&list=PL123&t=90",
        "https://youtu.be/dQw4w9WgXcQ?t=1m30s",
        "https://m.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ?si=abc",
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=45",
        "  dQw4w9WgXcQ  ",
    ]
    result = _run(tmp_path, links, [])["links"]

    assert [r["id"] for r in result] == ["dQw4w9WgXcQ"] * len(links)
    assert [r["start"] for r in result] == [0, 90, 90, 0, 0, 45, 0]


def test_anything_that_is_not_a_youtube_video_is_refused(tmp_path: Path) -> None:
    links = [
        "https://evil.test/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ\"><script>",
        "https://www.youtube.com/@somechannel",
        "not a link",
        "",
    ]
    assert _run(tmp_path, links, [])["links"] == [None] * len(links)


def test_the_sky_follows_sunrise_and_sunset(tmp_path: Path) -> None:
    # Sunrise 06:50, sunset 19:22, with a 75-minute twilight either side.
    times = [(3, 0), (6, 30), (7, 30), (13, 0), (18, 30), (19, 40), (23, 15)]
    result = _run(tmp_path, [], times)

    assert result["phases"] == ["night", "dawn", "dawn", "day", "dusk", "dusk", "night"]
    assert result["fallback"] == "day"
