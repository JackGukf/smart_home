# Lepro + Govee BLE Dashboard Control — Design

Date: 2026-07-18
Status: Approved by user (conversation), pending spec review

## Background

A TP-Link UB500 USB Bluetooth 5.0 adapter is now the Pi's sole Bluetooth adapter
(onboard BT disabled via `dtoverlay=disable-bt`). The dashboard already controls
Govee lights over BLE via the `govee_ble` ambient-light provider in
`src/python/web_app.py` (on/off/brightness/color, cached connections, retries).

The "Lepro S1 AI LED" is configured with the display-only `alexa` provider. BLE
probing shows the lamp (advertises as `LP`, address `B8:F8:62:DB:79:46`) accepts
connections and exposes a vendor GATT service:

- service `1e2aa501-7292-4263-a8f1-be907f039a1f`
- write char `1e2aa502-…` (`write`, `write-without-response`)
- notify char `1e2aa503-…` (`notify`, `indicate`)

The command protocol is proprietary and has no public reverse-engineering. The
user controls it from an iPhone (no Mac available), so phone-side packet capture
is not practical. The chosen route is direct probing from the Pi.

## Goals

1. Verify the existing Govee lights (H613A strip, H6054) work through the UB500.
2. Add the Govee H6076 floor lamp (`E8:6E:80:C6:2F:18`) to the dashboard config
   as a `govee_ble` light and verify control. (Identify the `GCVC9608…` device
   informationally; do not add it.)
3. Reverse-engineer the Lepro S1 BLE protocol by interactive probing, then add a
   `lepro_ble` provider so the dashboard can control it (power at minimum;
   brightness/color if the protocol yields them).

## Non-goals

- No Wi-Fi/Tuya/Alexa control path for the Lepro.
- No refactor of the BLE layer into a separate module (Approach C rejected for
  regression risk to the stabilized Govee path).
- No state *reading* from the lamps beyond what already exists (optimistic
  runtime state cache).

## Approach (chosen: A — generalize the existing manager)

`_GoveeBleManager` is already protocol-neutral (connect, cache client, write
bytes, retry). Generalize it into a shared BLE light manager used by both
providers; add a per-provider protocol layer:

- `govee_ble`: existing packet builder (`_govee_ble_command_bytes`) and
  write-target selection — behavior unchanged.
- `lepro_ble`: new packet builder (from probe findings) writing to
  `1e2aa502-…`; per-provider quirks (e.g. the Govee-specific
  `bluetoothctl remove` cache-forget and H613A connect delay) apply only to
  Govee unless probing shows the Lepro needs them.

Alternatives considered: (B) a parallel copied Lepro manager — duplicates
~100 lines of connection/retry plumbing; (C) extract `ble_lights.py` module —
cleanest structure but moves battle-tested code; rejected.

## Phase 1 — Protocol probing (interactive)

New standalone script `scripts/probe-lepro-ble.py` (runs on the Pi, uses the
dashboard venv's bleak):

- Connects to the S1, subscribes to `1e2aa503-…` notifications and logs them.
- Writes candidate packets one at a time from known LED-controller families
  (checksummed 20-byte Govee-style frames, 0x7E-prefixed generic RGB frames,
  Triones/HappyLighting `CC 23 33`-style frames, plain ASCII, etc.), pausing so
  the user can report lamp reactions.
- Any notification traffic after a write is logged verbatim to guide decoding.

Constraint: the lamp accepts one BLE connection — the iPhone Lepro app must be
closed during probing.

**Failure exit:** if no candidate family produces a reaction (protocol
encrypted or handshake-gated), stop; the Lepro stays display-only on the
`alexa` provider and only the Govee work ships.

## Phase 2 — Integration

1. `web_app.py`: generalize the manager; add `lepro_ble` packet builder and
   provider wiring in `_ambient_light_card` (status/note/capabilities),
   `_ambient_light_command` endpoint dispatch, and runtime state cache.
   Capabilities reflect what probing actually decoded.
2. Config on the Pi (`configs/devices.local.yaml`, git-ignored): switch the
   Lepro S1 to `provider: lepro_ble` with its BLE address; add the H6076 as
   `govee_ble`. Mirror schema in `configs/devices.example.yaml`.
3. Frontend (`web_static/`): no structural change expected — cards are driven
   by provider-agnostic `capabilities`; verify and adjust labels/notes only.
4. Tests (`tests/python/`): unit tests for the Lepro packet builder and the
   provider dispatch (mirroring existing Govee encoder tests if present; add
   both if absent). No live-BLE tests in CI.
5. Deploy via `scripts/deploy-dashboard.sh`; verify from the dashboard UI:
   Govee H613A, H6054, H6076, and Lepro S1 respond to power (and
   brightness/color where supported).

## Error handling

- Lepro command failures surface as HTTP 502 with detail, same pattern as
  Govee; unsupported commands → 400.
- A `lepro_ble` light without a real BLE address renders as
  `needs_ble_address`, mirroring Govee.

## Open questions resolved during probing

- Which packet family the S1 speaks (or none → failure exit).
- Whether brightness/color are attainable or power-only.
- Whether the second `LP` device (`10:20:BA:30:2A:7A`) is the same product;
  it refused connection during the initial probe.
