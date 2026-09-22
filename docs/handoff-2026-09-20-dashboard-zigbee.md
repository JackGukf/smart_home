# Dashboard live-update and Zigbee noise reduction

**Date:** 2026-09-20  
**Dashboard build:** 307

## Problem

Frequent Home Assistant state-change events could make every open dashboard call
all nine refresh endpoints. The slow Home Assistant and Tuya reads made a simple
occupancy, contact, or leak transition appear delayed. Zigbee link-quality and
other attribute-only updates increased the event volume without changing a
visible state.

## Change

- The event stream now ignores attribute-only Home Assistant events. A live
  update is sent only when the entity's state itself changes.
- A browser batches real events for 250 ms and reads only the affected
  Home Assistant-backed card through
  `/api/home-assistant/entities/{entity_id}/card`.
- The normal 60-second full refresh remains as a reconciliation path.
- The Zigbee control under **Discovery!’ Add Zigbee** controls both
  Zigbee2MQTT and its USB-adapter watchdog. It is enabled by default.

## Result

Motion, contact, leak, and occupancy changes no longer wait for Tuya, weather,
camera, thermostat, and unrelated device reads. Link-quality, last-seen, and
other attribute-only events do not trigger live dashboard work.

Zigbee2MQTT does not have a safe global threshold for link-quality changes.
Illuminance reporting thresholds, when available, are model-specific and should
be changed only after confirming the individual device exposes that setting.

## Validation

- `python3 -m pytest tests/python/test_event_stream_freshness.py
  tests/python/test_web_app.py tests/python/test_command_refresh_scope.py -q`
   86 passed.
- `python3 -m py_compile src/python/web_app.py`  passed.
- Deployed through `scripts/deploy-dashboard.sh`; dashboard service active.

## Ecobee source pairing (2026-09-21)

The physical Ecobee appears in Home Assistant as climate.my_ecobee (HomeKit, local) and climate.my_ecobee_2 (cloud). The dashboard now pairs the two by their shared friendly name and Home Assistants numeric duplicate-id convention, rather than their current temperature. The cloud entity is displayed while it is available because it supplies presets, equipment state, and room sensors; the local HomeKit entity becomes the displayed card automatically if the cloud entity is unavailable.

This avoids duplicate Climate dials when the two integrations refresh at different times, while retaining local control during an internet outage. Focused tests cover differing temperatures, deterministic ordering, and the unavailable-cloud fallback.

## Grouped Sensors page (2026-09-21)

The Devices -> Sensors page groups physical sensor cards as Safety & entry,
Presence, Room conditions, and Other sensors. A multi-sensor card appears
once, using safety, presence, then room conditions as its priority. The
section headers alternate only the dashboard accent and amber colours; red
remains reserved for a real device alert.

Option B is active: cards inherit their groups alternating accent or amber colour and use opposing rounded-corner shapes. Alert cards keep their red treatment.

## Environment gauges and air quality (2026-09-21)

Devices -> Environment now renders every temperature and humidity sensor as a
paired gauge card. Each semicircle retains the dashboard slate theme and uses a
white leading edge, green filled reading, and red remaining range. The green
annular fill ends at the live temperature or humidity value, matching the
chosen reference treatment while keeping the familiar dashboard colours.

CO2-capable monitors use a dedicated breathing-orb card. The orb colour follows
the existing fresh/okay/stuffy/poor CO2 classification and keeps the current
reading, status, temperature, humidity, and CO2 history available. Generic
sensor tiles remain in area details, where their compact format is more useful.

Focused dashboard regression checks cover the Environment split, CO2 monitor,
and grouped-device rendering.
