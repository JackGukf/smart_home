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
