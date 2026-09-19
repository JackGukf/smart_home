"""Home Assistant's All lights on / off scripts, and what they switch.

The Voice Panel's All lights cards and "Okay Nabu, all lights off" run
script.panel_all_lights_on / _off. What they switch follows the dashboard's
Quick actions (Manage on the All lights sheets): the dashboard resolves its
devices to Home Assistant entities here and rewrites the two scripts
(web_app.py, /api/light-scenes/sync). scripts/install-panel-scenes.py builds
them with the same function, from the list the dashboard last synced.

Mapping a dashboard device to its Home Assistant entity:

    ha:<entity_id>   that entity
    matter:<node>    the Matter entity with the device's name (names are
                     unique there; the Matter *bridge*'s "_2" copies of the
                     TP-Link switches share names with the TP-Link ones, so
                     names are never matched outside the Matter integration)
    <ip address>     by MAC, among the TP-Link integration's entities and the
                     "Switch as light" wrappers on the same device: a light
                     before a switch (a wall switch shown as a light), then
                     the shortest id (not the device's "_led" indicator)

Anything else is reported, never guessed.
"""
from __future__ import annotations

from typing import Any

SCRIPT_ON = "panel_all_lights_on"
SCRIPT_OFF = "panel_all_lights_off"

# Every TP-Link, Switch-as-light and Matter light or switch, with its device's MACs.
ENTITY_TEMPLATE = """{%- set ns = namespace(out=[]) -%}
{%- for integration in ['tplink', 'switch_as_x', 'matter'] -%}
{%- for e in integration_entities(integration) if e.split('.')[0] in ['light', 'switch'] -%}
{%- set ns.out = ns.out + [{'entity_id': e, 'integration': integration,
    'name': state_attr(e, 'friendly_name'),
    'macs': (device_attr(e, 'connections') or []) | selectattr(0, 'eq', 'mac') | map(attribute=1) | map('lower') | list}] -%}
{%- endfor -%}{%- endfor -%}{{ ns.out | tojson }}"""


def domain(entity_id: str) -> str:
    return entity_id.split(".", 1)[0]


def match_entities(devices: list[dict[str, Any]], rows: list[dict[str, Any]],
                   known: set[str]) -> tuple[list[str], list[str]]:
    """(entity ids, names of devices that could not be matched), in device order.

    devices: {"host", "name", "mac"} from the dashboard; rows: ENTITY_TEMPLATE's
    output; known: every entity id Home Assistant has.
    """
    entities: list[str] = []
    unmatched: list[str] = []
    for device in devices:
        host = str(device.get("host") or "")
        name = str(device.get("name") or host)
        entity = None
        if host.startswith("ha:"):
            entity = host[3:] if host[3:] in known else None
        elif host.startswith("matter:"):
            found = [r["entity_id"] for r in rows
                     if r.get("integration") == "matter" and str(r.get("name") or "").lower() == name.lower()]
            entity = found[0] if len(found) == 1 else None
        elif device.get("mac"):
            mac = str(device["mac"]).lower()
            found = [r["entity_id"] for r in rows
                     if r.get("integration") in ("tplink", "switch_as_x") and mac in (r.get("macs") or [])]
            found.sort(key=lambda e: (domain(e) != "light", len(e), e))
            entity = found[0] if found else None
        if entity and entity not in entities:
            entities.append(entity)
        elif not entity:
            unmatched.append(name)
    return entities, unmatched


def all_lights_scripts(devices: list[str]) -> dict[str, dict[str, Any]]:
    """The two scripts for these entities. On only to what is off - "on" to a
    light already on makes some re-apply their level and flash (the owner's
    rule, 2026-09-18); off to all of them, each through its own domain."""
    return {
        SCRIPT_ON: {
            "alias": "All lights on",
            "icon": "mdi:lightbulb-group",
            "mode": "single",
            "sequence": [{"alias": f"{entity} on, if off",
                          "if": [{"condition": "state", "entity_id": entity, "state": "off"}],
                          "then": [{"action": f"{domain(entity)}.turn_on", "target": {"entity_id": entity}}]}
                         for entity in devices],
        },
        SCRIPT_OFF: {
            "alias": "All lights off",
            "icon": "mdi:lightbulb-group-off",
            "mode": "single",
            "sequence": [{"action": f"{d}.turn_off", "target": {"entity_id": [e for e in devices if domain(e) == d]}}
                         for d in ("light", "switch") if any(domain(e) == d for e in devices)],
        },
    }
