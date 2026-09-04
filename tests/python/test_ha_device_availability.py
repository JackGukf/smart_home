"""A configured Home Assistant device that cannot be controlled must say so.

The north bedroom S505 is driven through Matter because python-kasa cannot speak
TPAP. When the Matter fabric was rebuilt its node was not re-commissioned, so
`light.bedroom_north_bedroom_light_switch` stopped existing in Home Assistant --
and the dashboard went on drawing a normal switch card for it. A missing entity
and a switch that is simply off both produced `is_on: None`, which the front end
rendered as "OFF" with a live-looking rocker, so nothing on screen said the
device was gone. It was found by someone walking over and pressing the switch.

These pin the three-way distinction that makes the difference visible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.python.web_app import _home_assistant_card_availability, _home_assistant_device_cards


ENTITY = "light.bedroom_north_bedroom_light_switch"


def test_missing_entity_is_unavailable_and_names_itself() -> None:
    """The actionable case: we reached Home Assistant and it has no such entity."""
    available, reason = _home_assistant_card_availability(ENTITY, None, states_read=True)

    assert available is False
    assert ENTITY in reason


def test_unreachable_home_assistant_is_unknown_not_unavailable() -> None:
    """Not being able to ask is a different problem from the device being gone.

    Collapsing them would cry wolf on every Home Assistant restart, which is the
    fastest way to teach someone to ignore the warning that matters.
    """
    available, _reason = _home_assistant_card_availability(ENTITY, None, states_read=False)

    assert available is None


def test_home_assistant_reporting_unavailable_is_unavailable() -> None:
    available, reason = _home_assistant_card_availability(
        ENTITY, {"state": "unavailable"}, states_read=True
    )

    assert available is False
    assert reason


@pytest.mark.parametrize("state", ["on", "off"])
def test_a_live_entity_is_available_in_either_position(state: str) -> None:
    available, reason = _home_assistant_card_availability(
        ENTITY, {"state": state}, states_read=True
    )

    assert available is True
    assert reason == ""


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "devices.local.yaml"
    path.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- category: light_switch\n"
        f"  entity_id: {ENTITY}\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n",
        encoding="utf-8",
    )
    return path


def test_card_for_a_vanished_entity_carries_the_reason(tmp_path: Path, monkeypatch) -> None:
    """The whole card, not just the helper: this is what the dashboard renders."""
    import src.python.web_app as web_app

    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "t0ken")
    # Home Assistant answers, and the configured entity is not among the states.
    monkeypatch.setattr(
        web_app, "_home_assistant_get", lambda *a, **k: [{"entity_id": "light.kitchen", "state": "on"}]
    )

    cards = _home_assistant_device_cards(_config(tmp_path))

    assert len(cards) == 1
    assert cards[0]["available"] is False
    assert ENTITY in cards[0]["unavailable_reason"]
    # Still None, which is exactly why is_on could not carry this on its own.
    assert cards[0]["is_on"] is None


def test_card_is_unknown_rather_than_dead_when_home_assistant_is_down(
    tmp_path: Path, monkeypatch
) -> None:
    import src.python.web_app as web_app

    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "t0ken")

    def _boom(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(web_app, "_home_assistant_get", _boom)

    cards = _home_assistant_device_cards(_config(tmp_path))

    assert cards[0]["available"] is None
