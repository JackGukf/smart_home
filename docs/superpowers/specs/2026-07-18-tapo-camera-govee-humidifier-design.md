# Tapo Camera + Govee H7140 Humidifier — Design

**Date:** 2026-07-18
**Status:** Approved

## Goal

Connect two newly added devices to the dashboard:

1. A new TP-Link Tapo camera — config-only, following the existing Tapo C200 pattern.
2. A Govee H7140 smart humidifier — new `govee_cloud` provider using the Govee
   Developer API v2, with a dedicated **Humidifiers** dashboard view.

## Part 1: Tapo camera (config-only)

No code changes. The existing camera pipeline (RTSP substream via go2rtc, MJPEG
proxy fallback) already supports Tapo cameras.

- Add a documented example entry to `configs/devices.example.yaml` under
  `tplink.cameras` (the existing Tapo location) showing a second Tapo camera.
- The user adds the real entry to `configs/devices.local.yaml` on the Pi:
  `name`, `host` (camera IP), `model`, `room`, `stream_name`,
  `go2rtc_url: http://192.168.0.176:1984`, `stream_path: /stream2`,
  `username_env: TAPO_CAMERA_USERNAME`, `password_env: TAPO_CAMERA_PASSWORD`.
- Credentials are the camera-account username/password set in the Tapo app,
  supplied via environment variables on the Pi — never committed.

## Part 2: Govee H7140 humidifier (`govee_cloud` provider)

### Decision

Use the **Govee Developer API v2** (`https://openapi.api.govee.com`) with
**runtime capability discovery**: query the account's device list, match the
configured humidifier, and render controls from the capability list the API
reports rather than hardcoding H7140 behavior. Rejected alternatives:
hardcoding SKU capabilities (brittle across firmware variants) and routing
through Home Assistant (extra hop, more moving parts).

### Config schema

New top-level section in `devices.example.yaml`:

```yaml
humidifiers:
  devices:
    - name: Bedroom Humidifier
      provider: govee_cloud
      model: H7140
      room: Bedroom
      # Device ID from the Govee API device list. Leave replace_me and the app
      # will match by model if the account has exactly one H7140.
      device_id: replace_me
```

API key comes from the `GOVEE_API_KEY` environment variable (applied for in
the Govee app: Settings → Apply for API Key). Never stored in config files.

### Backend (`src/python/web_app.py`)

Mirrors the ambient-lights structure:

- `HumidifierDefinition` dataclass: `name`, `provider`, `model`, `room`,
  `device_id`.
- `_load_humidifiers(path)` — parse `humidifiers.devices` from
  `devices.local.yaml`; skip `enabled: false` entries.
- Govee Cloud client helpers:
  - `GET /router/api/v1/user/devices` with `Govee-API-Key` header — device
    list, cached in-process for ~10 minutes.
  - `POST /router/api/v1/device/state` — current state (power, mist level,
    humidity if the device reports it).
  - `POST /router/api/v1/device/control` — send capability commands.
  - Device matching: exact `device_id` if configured and real; otherwise fall
    back to unique model match (`H7140`); ambiguous or no match → card shows a
    setup note.
- Card builder `_humidifier_card` returns `id`, `name`, `model`, `room`,
  `status`, `note`, `controllable`, `is_on`, `mist_level`, `humidity`, and a
  `capabilities` map derived from the API's reported capability list
  (`on_off`, `mist_level` with its min/max range, `humidity` read-only).
- Endpoints:
  - `GET /api/humidifiers` — list of cards.
  - `POST /api/humidifiers/{id}/{command}` — `on`, `off`, `mist_level`
    (body: `{"level": N}` clamped to the API-reported range).

### Error handling

- Missing `GOVEE_API_KEY` → status `needs_api_key`, note explains how to get
  one; dashboard never crashes.
- Govee 429 / rate limit (10k req/day, per-minute caps) → serve last cached
  state with note "cloud temporarily unavailable"; do not fail the whole
  refresh.
- Network/timeout errors → same cached-state fallback; commands surface an
  HTTP error with a readable message.

### Frontend

- `index.html`: new nav rail item **Humidifiers** (`data-view="humidifier"`)
  with count badge, placed after Ambient; new view panel with
  `humidifierGrid`.
- `app.js`: `loadHumidifiers()` / `renderHumidifiers()` / card template with
  on/off buttons and a mist-level slider whose min/max come from the card's
  capability range; command handlers POST to `/api/humidifiers/...`.
- `styles.css`: reuse the ambient-card visual language for humidifier cards.

### Testing

pytest in `tests/python/`, Govee API fully mocked (no live calls):

- Config loader: parses entries, skips disabled, tolerates missing section.
- Device matching: device_id match, unique-model fallback, ambiguous match.
- Card status mapping: no API key, API error, healthy state.
- Command endpoint: on/off, mist level clamped to reported range, unknown
  command → 400.

## Out of scope

- Govee humidifier LAN/BLE control (not supported by Govee for this class).
- Scheduling/automation of the humidifier.
- Changes to the C++ Matter bridge.
