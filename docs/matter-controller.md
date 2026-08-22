# Matter Controller — "Add Matter Device" on the dashboard

**Status:** dashboard code verified against a live Matter Server on the Orange Pi on 2026-08-22.
The board still needs the one-time install below (it requires `sudo`).

This is the **opposite direction** from [`matter-bridge.md`](matter-bridge.md):

| | Direction | Component |
|---|---|---|
| Matter **bridge** | our devices → Apple Home & other controllers | C++ `chip-bridge-app` |
| Matter **controller** (this doc) | third-party Matter devices → our dashboard | `python-matter-server` |

```
Dashboard "Add Matter Device"
        │ POST /api/matter/commission
        ▼
  src/python/matter_device.py  (DashboardMatterClient)
        │ WebSocket ws://localhost:5580/ws
        ▼
  matter-server  (systemd system unit, CHIP SDK + BLE + mDNS)
        │ BLE commissioning, then Matter over Wi-Fi
        ▼
   the new device
```

## Install on the board

```bash
./scripts/install-matter-server.sh
```

It creates a **dedicated venv** at `~/.venvs/matter-server` (the CHIP core wheel pins
`aiohttp`/`cryptography` versions we do not want to force onto the dashboard venv),
creates `/var/lib/matter` and `/data`, resolves the UB500's `hci` index from its MAC,
and installs/enables `configs/matter-server.service`.

Check it afterwards:

```bash
systemctl status matter-server
```

The dashboard's Matter card shows **Online** once `ws://localhost:5580/ws` answers.

## Things that bite

- **`/data` must exist and be writable.** The CHIP SDK writes `/data/chip_factory.ini`
  at startup and `abort()`s the whole process if it cannot — the traceback that
  surfaces is a misleading `Exception: CHIP handle has not been initialized!`.
- **BLE is required to commission a factory-fresh device.** The unit passes
  `--bluetooth-adapter`, resolved to the UB500 dongle rather than the onboard AX210.
  `hci` numbering can swap across reboots, so the installer resolves the index from
  the MAC in `BLE_ADAPTER`; re-run it if the adapters ever renumber.
- **`--primary-interface wlp1s0`** — Ubuntu's predictable interface name, not `wlan0`.
- **The client must keep `start_listening()` running.** python-matter-server only fills
  its node cache, and only resolves command futures, while that background task is
  alive. Connecting without it makes `get_nodes()` return an empty list and every
  command hang until it times out. `DashboardMatterClient` owns that task.
- **The client is generation-sensitive.** `commission_with_code()` returns a
  `MatterNodeData` (not a node id), and `send_device_command()` takes a
  `chip.clusters` command object — not `cluster_id`/`command_name`/`payload` kwargs.
- **Node attributes are typed.** Read them through `node.endpoints[id].get_attribute_value(...)`;
  `MatterNode` has no raw `attributes` dict.
- **Endpoint 0 is the root node.** The controllable clusters live on endpoint 1 or
  higher, and it is not always 1 — `primary_endpoint()` picks it per node.

## Pairing a device

1. Dashboard → Matter card → **Add Matter Device**.
2. Enter the 11-digit manual pairing code or the QR payload from the device.
3. Give it a name (and optionally a room) and press Pair.

On success the node id, name, and room are written into `configs/devices.local.yaml`
under `matter.devices`, and the device appears in the Lights/Plugs views with a
`MATTER` badge. Removing it from the dashboard decommissions it — the device then
needs a factory reset before it can be paired again.
