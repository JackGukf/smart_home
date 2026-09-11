"""The Home Assistant auth block that logs the wall panel in.

Writing this block is the part of scripts/kiosk/configure-autologin.py that can
be wrong in a way nobody notices until they are standing in front of a panel
that wants a password. Two properties are load-bearing, and neither is obvious
from reading the YAML:

  * trusted_networks must come FIRST. The frontend renders providers[0] as the
    login form and pushes the rest under "Or log in with", so with the
    homeassistant provider first the panel shows a password box and a link that
    nobody is there to tap. This was observed, not guessed.
  * the homeassistant provider must still be listed. Declaring auth_providers
    at all replaces Home Assistant's implicit default, so dropping it locks
    password login out of the house from every device at once.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "kiosk" / "configure-autologin.py"

# Hyphenated filename, so it cannot be imported by name.
_spec = importlib.util.spec_from_file_location("configure_autologin", SCRIPT)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)

_auth_block = _module._auth_block
BEGIN, END = _module.BEGIN, _module.END

KIOSK = "192.168.0.176/32"
USER_ID = "2d255500a6a6490686f8b1c8dbb45309"


def _providers() -> list[dict]:
    block = _auth_block(KIOSK, USER_ID, "panel@example.com")
    return yaml.safe_load(block)["homeassistant"]["auth_providers"]


def test_trusted_networks_is_the_first_provider():
    """Second place means the panel gets a password form it cannot fill in."""
    assert _providers()[0]["type"] == "trusted_networks"


def test_the_password_provider_is_still_listed():
    """Without it, declaring auth_providers locks everyone out of the house."""
    assert any(p["type"] == "homeassistant" for p in _providers())


def test_the_panel_is_pinned_to_one_user():
    """An unpinned trusted network shows a user picker instead of logging in."""
    trusted = _providers()[0]
    assert trusted["trusted_networks"] == [KIOSK]
    assert trusted["trusted_users"] == {KIOSK: USER_ID}
    assert trusted["allow_bypass_login"] is True


def test_the_block_is_delimited_so_re_running_replaces_it():
    block = _auth_block(KIOSK, USER_ID, "panel@example.com")
    assert block.startswith(BEGIN)
    assert block.rstrip().endswith(END)


def test_the_block_is_valid_yaml_on_its_own():
    yaml.safe_load(_auth_block(KIOSK, USER_ID, "panel@example.com"))


def test_a_quoted_user_name_cannot_break_the_comment():
    """The user name is interpolated into a comment line - keep it on one line."""
    block = _auth_block(KIOSK, USER_ID, "someone@example.com")
    comment_lines = [ln for ln in block.splitlines() if ln.startswith("#")]
    assert any("someone@example.com" in ln for ln in comment_lines)
    yaml.safe_load(block)
