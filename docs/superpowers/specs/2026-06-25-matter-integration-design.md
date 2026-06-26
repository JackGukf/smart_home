# Matter Integration Design
**Date:** 2026-06-25
**Status:** Approved

## Overview

Add Matter protocol device support to the smart-home-rpi4 dashboard. The Raspberry Pi 4 runs Python Matter Server as a systemd service, which manages the Matter fabric and paired devices. A new `matter_device.py` module talks to it over a local WebSocket. Four new API endpoints in `web_app.py` expose commissioning and control to the frontend. Matter devices are merged into existing dashboard views (Lights, Plugs, Sensors) by category — no new views required.

## Architecture

```
Physical Device (Matter over WiFi)
        ↕  Matter protocol
Python Matter Server  ← systemd service on Pi, ws://localhost:5580/ws
                        owns the Matter fabric and persistent device state
        ↕  WebSocket (local)
src/python/matter_device.py
        ← thin async client: commission, list nodes, send commands, remove node
        ↕  function calls
web_app.py  ← 4 new API endpoints; reads matter: section from devices.local.yaml
        ↕  HTTP/JSON (same pattern as all other integrations)
Dashboard JS/HTML
        ← Discovery view + commissioning modal
        ← Matter devices merged into Lights/Plugs/Sensors by category
```

If Python Matter Server is offline, `GET /api/matter/devices` returns `[]` with a warning flag. The rest of the dashboard is unaffected.

## Backend — `src/python/matter_device.py`

### `MatterClient` class

Single class with a persistent WebSocket connection to Python Matter Server.

```python
class MatterClient:
    async def connect()
    async def list_nodes() -> list[MatterNode]
    async def commission(setup_code: str) -> MatterNode
    async def send_command(node_id: int, endpoint: int, cluster: str, command: str, params: dict)
    async def remove_node(node_id: int)
```

### `MatterNode` → dashboard device shape

Nodes returned by the Matter Server are mapped to the same dict shape that `GET /api/devices` returns for TP-Link devices, so existing JS render functions work without modification.

### Category auto-detection

Matter device type (from the Descriptor cluster) maps to dashboard category:

| Matter device type | Dashboard category | Notes |
|---|---|---|
| `0x0100` On/Off Light | `light_switch` | |
| `0x0101` Dimmable Light | `light_switch` | `is_dimmable: true` |
| `0x010A` On/Off Plug-In Unit | `smart_plug` | |
| `0x0302` Temperature Sensor | `tuya_sensor` | appears in Sensors view |
| Unknown | `smart_plug` | safe fallback |

Category can be overridden per-device in `devices.local.yaml`.

## API Endpoints

All added inside `web_app.py` alongside existing endpoints.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/matter/devices` | List all commissioned Matter nodes in dashboard device shape |
| `POST` | `/api/matter/commission` | Pair a new device; writes entry to `devices.local.yaml` |
| `POST` | `/api/matter/devices/{node_id}/commands/{command}` | on / off / brightness |
| `DELETE` | `/api/matter/devices/{node_id}` | Decommission and remove from config |

### Commission request body

```json
{
  "setup_code": "34970112332",
  "name": "Kitchen Switch",
  "room": "Kitchen"
}
```

Commission timeout: 30 seconds. Returns 408 on timeout.

### Error handling

- Matter Server offline → `GET /api/matter/devices` returns `{"devices": [], "matter_online": false}`
- Commission timeout → 408, modal shows inline error with Retry button
- Command fails → 503, dashboard shows toast notification (same as TP-Link error pattern)

## Configuration — `devices.local.yaml`

New top-level `matter:` section:

```yaml
matter:
  server_url: ws://localhost:5580/ws   # optional, this is the default
  devices:
    - node_id: 1
      name: "Kitchen Switch"
      room: "Kitchen"
      category: light_switch           # optional; auto-detected from Matter device type if absent
    - node_id: 2
      name: "Living Room Plug"
      room: "Living Room"
      # category auto-detected as smart_plug
```

`node_id` is assigned by Python Matter Server during commissioning and written to this file automatically. Users should not need to edit this section manually after pairing.

## Dashboard UI

### Sidebar

New "Discovery" section added between "Views" and "System":

```html
<div class="sidebar-section">Discovery</div>
<ul class="room-list">
  <li class="room-item" data-view="discovery">
    <span class="room-icon"><i class="ti ti-antenna"></i></span>
    Add Matter
  </li>
</ul>
```

### Discovery view panel

Shown in the main content area when "Add Matter" is selected:
- Matter Server status line: "Matter Server: Online" / "Matter Server: Offline"
- "Add Matter Device" button — opens commissioning modal
- List of already-commissioned Matter devices with decommission option

### Commissioning modal

**Step 1 — input:**
- 11-digit pairing code field (formatted as `XXXXX-XXXXX`)
- Name field
- Room field
- Greyed-out QR scan placeholder (clearly labelled "coming soon")
- Cancel / Pair Device buttons

**Step 2 — progress (same modal):**
- Spinner with sequential status: `Connecting… → Commissioning… → Done ✓`
- Auto-closes on success and triggers a device reload
- On failure: inline error message with Retry button

### Device cards in existing views

Matter devices are returned by `GET /api/matter/devices` in the same shape as TP-Link devices. The frontend merges them in `loadDevices()` so they appear in Lights, Plugs, or Sensors automatically.

A small `MATTER` badge is added to each Matter device card to distinguish it from TP-Link/Tuya devices visually.

## Infrastructure — Python Matter Server

### Installation (on the Pi)

```bash
pip install "python-matter-server[server]"
```

### systemd service

`/etc/systemd/system/matter-server.service`:

```ini
[Unit]
Description=Python Matter Server
After=network.target

[Service]
ExecStart=/usr/local/bin/matter-server --storage-path /var/lib/matter --port 5580
Restart=on-failure
User=smarthome

[Install]
WantedBy=multi-user.target
```

### `requirements.txt` additions

```
python-matter-server[client]
```

## Dependencies

- `python-matter-server[server]` — Pi system install (systemd service)
- `python-matter-server[client]` — added to `src/python/requirements.txt`
- No new JS dependencies

## Out of Scope

- Thread (802.15.4) devices — requires a USB 802.15.4 dongle not present on RPi 4
- QR code scanning via camera — placeholder slot in modal, implemented later
- Multi-admin / sharing Matter devices with the Tapo app simultaneously
- Matter device firmware updates
