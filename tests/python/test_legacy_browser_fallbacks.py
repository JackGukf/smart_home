"""Fallbacks for browsers that predate the CSS the dashboard is written in.

An iPad mini on iOS 12.5 (Safari 12.1) rendered the dashboard with cameras at
natural size and tile contents off-centre. Both come from aspect-ratio, which
Safari only shipped in 15: a box whose height comes solely from a ratio has no
height at all without it, so children sized at 100% fall back to their natural
size and centred content has nothing to be centred within.

CSS fails silently, which is why this went unnoticed until someone looked at
the screen. These tests are the substitute for that pair of eyes.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

# Every selector that gets its height from aspect-ratio alone.
ASPECT_RATIO_SELECTORS = (
    ".camera-frame",
    ".home-camera-frame",
    ".area-icon-choice",
    ".custom-light-tile",
    ".temp-sensor-tile",
)


def _inline_scripts(html: str) -> list[str]:
    return re.findall(r"<script>(.*?)</script>", html, flags=re.S)


def test_every_aspect_ratio_rule_has_a_fallback() -> None:
    css = STYLES.read_text(encoding="utf-8")

    used = {
        css[css.rfind("{", 0, m.start()) : m.start()]
        for m in re.finditer(r"aspect-ratio\s*:", css)
    }
    assert used, "no aspect-ratio rules found; this guard may be obsolete"

    for selector in ASPECT_RATIO_SELECTORS:
        assert f"html.no-aspect-ratio {selector}" in css, (
            f"{selector} sizes itself with aspect-ratio but has no fallback"
        )


def test_fallbacks_are_gated_so_modern_browsers_are_untouched() -> None:
    css = STYLES.read_text(encoding="utf-8")

    # Bounded at the next section banner: more CSS has been appended since,
    # and an unbounded slice would police unrelated rules.
    start = css.index("Fallbacks for browsers without aspect-ratio")
    end = css.find("/* \u2500\u2500", start)
    fallbacks = css[start : end if end != -1 else len(css)]
    rules = re.findall(r"^(\S[^{]*)\{", fallbacks, flags=re.M)
    for rule in rules:
        assert "no-aspect-ratio" in rule, (
            f"unscoped rule in the fallback block would hit every browser: {rule.strip()!r}"
        )


def test_detection_runs_before_paint_and_is_es5() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    head = html[: html.index("</head>")]
    assert "no-aspect-ratio" in head, "detection must run in <head>, before first paint"

    script = next(s for s in _inline_scripts(head) if "no-aspect-ratio" in s)
    # The deploy's esbuild step only compiles app.js, so inline script is
    # shipped verbatim and must already be parseable by the oldest browser.
    #
    # String literals are stripped first: the feature probe deliberately holds
    # modern syntax as a *string* for new Function, which never reaches this
    # file's own parse. Only executable syntax is checked.
    code = re.sub(r'"[^"]*"|\'[^\']*\'', '""', script)
    for token in ("=>", "const ", "let ", "?.", "??", "`"):
        assert token not in code, f"inline detection uses {token!r}, which is not ES5"


def test_inset_shorthand_always_has_longhand_beside_it() -> None:
    css = STYLES.read_text(encoding="utf-8")

    # inset: is Safari 14.1+; without the longhand, absolutely positioned
    # children of a collapsed frame end up unpositioned as well.
    for match in re.finditer(r"^[ \t]*inset:\s*([^;]+);", css, flags=re.M):
        preceding = css[max(0, match.start() - 200) : match.start()]
        assert "top:" in preceding and "left:" in preceding, (
            f"inset: {match.group(1)} at offset {match.start()} has no longhand fallback"
        )


@pytest.mark.skipif(shutil.which("npx") is None, reason="needs Node.js to run esbuild")
def test_inline_detection_parses_as_es5() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = next(s for s in _inline_scripts(html) if "no-aspect-ratio" in s)

    result = subprocess.run(
        ["npx", "--yes", "esbuild", "--loader=js", "--target=es5"],
        input=script, capture_output=True, text=True, timeout=300,
    )

    assert result.returncode == 0, f"inline script is not ES5-parseable:\n{result.stderr}"
