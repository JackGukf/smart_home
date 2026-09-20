"""One card per thermostat on the wall.

The ecobee arrives twice - over HomeKit locally, and through its cloud
integration - and the Home view's Climate card stacked two dials in a space
sized for one (2026-09-19).
"""
from __future__ import annotations

from src.python import web_app


def climate(entity_id, name, temperature, **attributes):
    return {"entity_id": entity_id, "state": "heat",
            "attributes": {"friendly_name": name, "current_temperature": temperature, **attributes}}


def test_the_same_thermostat_twice_becomes_one():
    homekit = climate("climate.my_ecobee", "My ecobee", 23.5, hvac_modes=["off", "heat"])
    cloud = climate("climate.my_ecobee_2", "My ecobee", 23.5, hvac_modes=["heat", "off"],
                    preset_modes=["home", "away", "sleep"], equipment_running="", current_humidity=57)

    [kept] = web_app._one_per_thermostat([homekit, cloud])
    assert kept["entity_id"] == "climate.my_ecobee_2", "the one that knows about presets wins"
    # And the other way round in the list: the choice is about the entity, not the order.
    [kept] = web_app._one_per_thermostat([cloud, homekit])
    assert kept["entity_id"] == "climate.my_ecobee_2"


def test_two_real_thermostats_are_both_kept():
    upstairs = climate("climate.upstairs", "Upstairs", 21.0)
    downstairs = climate("climate.downstairs", "Downstairs", 19.5)
    assert len(web_app._one_per_thermostat([upstairs, downstairs])) == 2

    # Same name but reading differently: two devices, and both are shown.
    twin_a = climate("climate.a", "Hallway", 20.0)
    twin_b = climate("climate.b", "Hallway", 22.0)
    assert len(web_app._one_per_thermostat([twin_a, twin_b])) == 2


def test_the_choice_does_not_wander_between_refreshes():
    """Two entities equally rich: the same one must win every time, or the card
    would flicker between them as the dashboard polls."""
    first = climate("climate.a", "Hallway", 20.0, hvac_modes=["heat"])
    second = climate("climate.b", "Hallway", 20.0, hvac_modes=["heat"])
    assert [e["entity_id"] for e in web_app._one_per_thermostat([first, second])] == \
           [e["entity_id"] for e in web_app._one_per_thermostat([second, first])]


def test_the_home_card_lays_several_dials_across_and_names_them():
    """One dial needs no name - the card is titled Climate - and several go
    side by side, so the card stays one dial tall however many there are."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")
    css = (Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    assert "const alone = latestThermostats.length === 1;" in js
    assert 'alone ? "" : `<div class="home-dial-name">' in js
    assert 'home-fit-row' in js and 'data-design-w="${CLIMATE_DESIGN_W * across}"' in js
    # The fit scales to however wide the row actually is.
    assert "const designW = Number(inner.dataset.designW) || CLIMATE_DESIGN_W;" in js
    assert "availW / designW" in js and "availW - designW * scale" in js
    assert ".home-fit-row {" in css and "flex-direction: row;" in css
