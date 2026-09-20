"""The overlap checker itself: what it looks for, and what it refuses to do.

The check that matters runs a browser (scripts/check-card-overlap.py, on the
board). These tests hold the parts that can be wrong without a browser: the
device sizes it covers, and the two rules that decide whether a finding is
real - clipped text is not an overlap, and a login page is not a clean report.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-card-overlap.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_card_overlap", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_card_overlap"] = module      # dataclasses needs it registered
    spec.loader.exec_module(module)
    return module


def test_it_covers_the_screens_this_house_reads_the_dashboard_on():
    check = _module()
    assert check.DEVICES["iphone15"] == (393, 852, 3.0)
    assert check.DEVICES["wallpanel"] == (1920, 1080, 1.0)
    assert check.DEVICES["ipad13"][0] == 1024
    # Every view in the sidebar, or a card could collide unseen on one of them.
    for view in ("home", "energy", "climate", "status", "ai"):
        assert view in check.VIEWS


def test_clipped_text_is_not_an_overlap():
    """A caption with overflow:hidden that ellipses its own text has a box
    running past the edge that hides it. Measuring boxes alone reported it as
    printing over its neighbour, which it does not (2026-09-20)."""
    finder = _module()._FINDER
    assert "getBoundingClientRect" in finder
    assert 's.overflow === "visible"' in finder, "the rect is cut down by clipping ancestors"
    assert "box.right <= box.left" in finder


def test_a_login_page_is_an_error_not_a_pass():
    """The first run of this reported no overlaps while looking at the login
    form. Silence has to mean 'checked and clean', never 'saw nothing'."""
    check = _module()
    assert issubclass(check.NotSignedIn, RuntimeError)
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'seen.get("path", "").startswith("/login")' in source
    assert 'not seen.get("views")' in source, "an empty page is not a clean page either"
    assert "session_cookie" in source, "it signs in the way the TV cast does"


def test_layered_text_is_left_alone():
    """A badge on a tile or a label inside a dial is meant to sit over
    something. Only text that shares the ordinary flow is compared."""
    assert "layered" in _module()._FINDER


def test_the_script_says_how_to_run_it_and_fails_loudly():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "scripts/check-card-overlap.py" in source
    assert "return 1 if findings else 0" in source, "a finding must fail the run"
