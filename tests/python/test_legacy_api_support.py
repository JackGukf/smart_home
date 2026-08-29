"""Browser APIs the dashboard calls must exist on the baseline browser.

The deploy compiles modern *syntax* down to ES2019, which is why the file
parses on Safari 12.1. It does nothing for *APIs*: a method the browser lacks
is simply missing at run time and the call throws where it stands. Syntax is
all-or-nothing at parse; an API takes out only the feature that calls it,
which makes it quieter and easier to miss.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

# APIs newer than the baseline (Safari 12.1 / iOS 12.5). Each must be either
# polyfilled or guarded before use.
TOO_NEW_FOR_BASELINE = {
    "Promise.allSettled": "Safari 13.0",
    "Promise.any": "Safari 14.0",
    "ResizeObserver": "Safari 13.1",
    "structuredClone": "Safari 15.4",
    ".replaceAll(": "Safari 13.1",
    ".matchAll(": "Safari 13.0",
    "BroadcastChannel": "Safari 15.4",
    "requestIdleCallback": "unsupported in Safari",
}


def test_newer_apis_are_polyfilled_or_guarded() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    for api, since in sorted(TOO_NEW_FOR_BASELINE.items()):
        if api not in js:
            continue
        name = api.strip(".(")
        polyfilled = re.search(rf"typeof {re.escape(name)} !== \"function\"", js)
        guarded = re.search(rf"typeof {re.escape(name)} === \"undefined\"", js)
        assert polyfilled or guarded, (
            f"{api} is {since}, newer than the baseline browser, and is used "
            f"without a polyfill or a guard - the call will throw"
        )


def test_promise_allsettled_polyfill_matches_the_real_shape() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    fn = re.search(r"Promise\.allSettled = function.*?\n\};", js, re.S)
    assert fn, "no Promise.allSettled polyfill"
    body = fn.group(0)

    # It must never reject, and must report each outcome in the documented shape.
    assert '"fulfilled"' in body and '"rejected"' in body
    assert "value" in body and "reason" in body
    # Array.from, not spread on an iterable of unknown type.
    assert "Array.from(promises" in body


def test_drag_input_helpers_are_defined_before_their_first_use() -> None:
    """const is not hoisted; the dials call this from earlier in the file."""
    js = APP_JS.read_text(encoding="utf-8")

    definition = js.index("const HAS_POINTER_EVENTS")
    first_use = min(m.start() for m in re.finditer(r"onDragStart\(", js))
    assert definition < first_use, (
        "HAS_POINTER_EVENTS is used before it is initialised; a const in the "
        "temporal dead zone throws rather than reading as undefined"
    )


def test_both_dials_work_without_pointer_events() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    # The brightness dial and the thermostat dial were the last two controls
    # still bound only to pointerdown, so inert on an iOS 12 iPad.
    assert "wrap.addEventListener(\"pointerdown\"" not in js
    assert js.count("onDragStart(wrap") == 2

    # The dial's dead zone must stay scrollable, so it cannot preventDefault
    # before knowing the touch landed on the dial itself.
    brightness = js[js.index("function levelFromPointer") :]
    brightness = brightness[: brightness.index("trackDrag(")]
    assert brightness.index("if (lv === null) return;") < brightness.index("e.preventDefault();")


def test_hold_to_talk_reacts_to_touch() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    block = js[js.index("/* ── Hold-to-talk ──") :]
    block = block[: block.index("\n\n")] if "\n\n" in block else block

    assert '"touchstart"' in block and '"touchend"' in block
