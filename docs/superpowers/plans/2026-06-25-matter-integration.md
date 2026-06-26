# Matter Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Matter device support to the dashboard — commissioning, on/off/brightness control, and device card rendering — via Python Matter Server running as a systemd service on the Raspberry Pi 4.

**Architecture:** Python Matter Server manages the Matter fabric and exposes a local WebSocket API. `src/python/matter_device.py` wraps it. Four new FastAPI endpoints in `web_app.py` expose commissioning and control. A Discovery sidebar section and modal handle pairing. Matter devices are merged into the existing Lights, Plugs, and Sensors views by auto-detected category.

**Tech Stack:** python-matter-server[client/server], FastAPI, aiohttp, PyYAML, Tabler Icons, vanilla JS.

## Global Constraints

- Python 3.10+; all new code starts with `from __future__ import annotations`
- Follow existing `web_app.py` style: dataclasses, type hints, snake_case, no f-string secrets
- Existing device commands route via `host` field; Matter devices use `host = "matter:{node_id}"`
- No new JS libraries — vanilla JS only
- Matter device cards use existing `device-card new-style` CSS classes
- Config in `configs/devices.local.yaml`; never committed with secrets
- All tests in `tests/python/`; run with `python3 -m pytest`

---

### Task 1: Infrastructure — systemd service and install script

**Files:**
- Create: `configs/matter-server.service`
- Create: `scripts/install-matter-server.sh`

**Interfaces:**
- Produces: Python Matter Server running at `ws://localhost:5580/ws` on the Pi

- [ ] **Step 1: Create systemd unit file**

Create `configs/matter-server.service`:

```ini
[Unit]
Description=Python Matter Server
After=network.target

[Service]
ExecStart=/home/smarthome/.local/bin/matter-server --storage-path /var/lib/matter --port 5580
Restart=on-failure
RestartSec=5
User=smarthome

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create install script**

Create `scripts/install-matter-server.sh`:

```bash
#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Installing python-matter-server on the Pi..."
pip install --user "python-matter-server[server]"

echo "==> Creating Matter storage directory..."
sudo mkdir -p /var/lib/matter
sudo chown smarthome:smarthome /var/lib/matter

echo "==> Installing systemd service..."
sudo cp "$REPO_ROOT/configs/matter-server.service" /etc/systemd/system/matter-server.service
sudo systemctl daemon-reload
sudo systemctl enable matter-server
sudo systemctl start matter-server

echo "==> Waiting for Matter server to start..."
sleep 3
if systemctl is-active --quiet matter-server; then
  echo "==> Matter server is running at ws://localhost:5580/ws"
else
  echo "ERROR: Matter server failed to start."
  echo "Check logs: sudo journalctl -u matter-server -n 50"
  exit 1
fi
```

- [ ] **Step 3: Make executable and commit**

```bash
chmod +x scripts/install-matter-server.sh
git add configs/matter-server.service scripts/install-matter-server.sh
git commit -m "feat: add Python Matter Server systemd service and install script"
```

---

### Task 2: `src/python/matter_device.py` and tests

**Files:**
- Create: `src/python/matter_device.py`
- Create: `tests/python/test_matter_device.py`

**Interfaces:**
- Produces:
  - `MatterDeviceInfo` dataclass — fields: `node_id: int`, `name: str`, `room: str | None`, `category: str`, `is_dimmable: bool`, `is_on: bool`, `brightness: int`, `available: bool`, `provider: str = "matter"`
  - `_detect_category(attributes: dict) -> tuple[str, bool]`
  - `node_to_device(node, name, room, category_override=None) -> MatterDeviceInfo`
  - `DashboardMatterClient(server_url="ws://localhost:5580/ws")` with async methods: `list_nodes()`, `commission(setup_code)`, `send_command(node_id, command, brightness=None)`, `remove_node(node_id)`, `close()`

- [ ] **Step 1: Write failing tests**

Create `tests/python/test_matter_device.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.python.matter_device import (
    _detect_category,
    node_to_device,
    DashboardMatterClient,
)


def _make_node(node_id=1, attributes=None, available=True):
    node = MagicMock()
    node.node_id = node_id
    node.available = available
    node.attributes = attributes or {}
    return node


def test_detect_category_onoff_light():
    assert _detect_category({"1/29/0": [{"type": 0x0100}]}) == ("light_switch", False)


def test_detect_category_dimmable_light():
    assert _detect_category({"1/29/0": [{"type": 0x0101}]}) == ("light_switch", True)


def test_detect_category_plug():
    assert _detect_category({"1/29/0": [{"type": 0x010A}]}) == ("smart_plug", False)


def test_detect_category_temp_sensor():
    assert _detect_category({"1/29/0": [{"type": 0x0302}]}) == ("tuya_sensor", False)


def test_detect_category_unknown_defaults_to_plug():
    assert _detect_category({}) == ("smart_plug", False)


def test_node_to_device_basic():
    node = _make_node(attributes={"1/29/0": [{"type": 0x0100}], "1/6/0": True})
    info = node_to_device(node, "Kitchen Light", "Kitchen")
    assert info.is_on is True
    assert info.category == "light_switch"
    assert info.provider == "matter"
    assert info.node_id == 1
    assert info.name == "Kitchen Light"
    assert info.room == "Kitchen"


def test_node_to_device_off():
    node = _make_node(attributes={"1/29/0": [{"type": 0x0100}], "1/6/0": False})
    assert node_to_device(node, "Lamp", None).is_on is False


def test_node_to_device_category_override():
    node = _make_node(attributes={"1/29/0": [{"type": 0x010A}]})
    info = node_to_device(node, "Switch", None, category_override="light_switch")
    assert info.category == "light_switch"


def test_node_to_device_brightness():
    node = _make_node(attributes={
        "1/29/0": [{"type": 0x0101}],
        "1/6/0": True,
        "1/8/0": 127,
    })
    info = node_to_device(node, "Dimmer", "Bedroom")
    assert info.brightness == round((127 / 254) * 100)
    assert info.is_dimmable is True


def test_node_to_device_no_brightness_attr_defaults_100():
    node = _make_node(attributes={"1/29/0": [{"type": 0x0101}], "1/6/0": True})
    info = node_to_device(node, "Dimmer", None)
    assert info.brightness == 100


def test_node_to_device_unavailable():
    node = _make_node(available=False)
    assert node_to_device(node, "Offline", None).available is False


@pytest.mark.asyncio
async def test_client_list_nodes():
    mock_inner = MagicMock()
    mock_inner.get_nodes.return_value = [_make_node(node_id=1), _make_node(node_id=2)]
    client = DashboardMatterClient()
    client._client = mock_inner
    nodes = await client.list_nodes()
    assert len(nodes) == 2


@pytest.mark.asyncio
async def test_client_commission():
    mock_inner = AsyncMock()
    mock_inner.commission_with_code = AsyncMock(return_value=5)
    client = DashboardMatterClient()
    client._client = mock_inner
    node_id = await client.commission("34970112332")
    assert node_id == 5
    mock_inner.commission_with_code.assert_called_once_with("34970112332")


@pytest.mark.asyncio
async def test_client_send_on():
    mock_inner = AsyncMock()
    client = DashboardMatterClient()
    client._client = mock_inner
    await client.send_command(1, "on")
    mock_inner.send_device_command.assert_called_once_with(
        node_id=1, endpoint_id=1, cluster_id=6, command_name="on", payload={}
    )


@pytest.mark.asyncio
async def test_client_send_off():
    mock_inner = AsyncMock()
    client = DashboardMatterClient()
    client._client = mock_inner
    await client.send_command(1, "off")
    mock_inner.send_device_command.assert_called_once_with(
        node_id=1, endpoint_id=1, cluster_id=6, command_name="off", payload={}
    )


@pytest.mark.asyncio
async def test_client_send_brightness():
    mock_inner = AsyncMock()
    client = DashboardMatterClient()
    client._client = mock_inner
    await client.send_command(1, "brightness", brightness=50)
    kwargs = mock_inner.send_device_command.call_args.kwargs
    assert kwargs["cluster_id"] == 8
    assert kwargs["command_name"] == "moveToLevelWithOnOff"
    assert kwargs["payload"]["level"] == round(0.5 * 254)


@pytest.mark.asyncio
async def test_client_remove_node():
    mock_inner = AsyncMock()
    client = DashboardMatterClient()
    client._client = mock_inner
    await client.remove_node(3)
    mock_inner.remove_node.assert_called_once_with(3)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/python/test_matter_device.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.python.matter_device'`

- [ ] **Step 3: Create `src/python/matter_device.py`**

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

# Matter Descriptor cluster device type IDs → (dashboard category, is_dimmable)
_DEVICE_TYPE_MAP: dict[int, tuple[str, bool]] = {
    0x0100: ("light_switch", False),   # On/Off Light
    0x0101: ("light_switch", True),    # Dimmable Light
    0x010A: ("smart_plug",   False),   # On/Off Plug-In Unit
    0x0302: ("tuya_sensor",  False),   # Temperature Sensor
}

_ONOFF_CLUSTER = 6
_LEVEL_CLUSTER = 8


@dataclass
class MatterDeviceInfo:
    node_id: int
    name: str
    room: str | None
    category: str
    is_dimmable: bool
    is_on: bool
    brightness: int
    available: bool
    provider: str = "matter"


def _detect_category(attributes: dict[str, Any]) -> tuple[str, bool]:
    """Return (category, is_dimmable) from Matter Descriptor cluster attributes.

    Attribute key "1/29/0" = endpoint 1 / cluster 29 (Descriptor) / attribute 0 (DeviceTypeList).
    """
    device_types = attributes.get("1/29/0") or []
    for dt in device_types:
        type_id = dt.get("type") if isinstance(dt, dict) else dt
        if type_id in _DEVICE_TYPE_MAP:
            return _DEVICE_TYPE_MAP[type_id]
    return ("smart_plug", False)


def node_to_device(
    node: Any,
    name: str,
    room: str | None,
    category_override: str | None = None,
) -> MatterDeviceInfo:
    """Map a python-matter-server MatterNode to a dashboard MatterDeviceInfo."""
    attrs: dict[str, Any] = getattr(node, "attributes", {}) or {}
    detected_category, detected_dimmable = _detect_category(attrs)
    category = category_override or detected_category
    is_dimmable = detected_dimmable and category == "light_switch"

    is_on = bool(attrs.get("1/6/0", False))
    raw_level = attrs.get("1/8/0")
    brightness = round((raw_level / 254) * 100) if raw_level is not None else 100

    return MatterDeviceInfo(
        node_id=node.node_id,
        name=name,
        room=room,
        category=category,
        is_dimmable=is_dimmable,
        is_on=is_on,
        brightness=brightness,
        available=getattr(node, "available", True),
    )


class DashboardMatterClient:
    """Thin async wrapper around python-matter-server's WebSocket client."""

    def __init__(self, server_url: str = "ws://localhost:5580/ws") -> None:
        self._url = server_url
        self._client: Any = None
        self._session: Any = None

    async def _ensure_connected(self) -> Any:
        if self._client is not None:
            return self._client
        import aiohttp
        from matter_server.client import MatterClient
        self._session = aiohttp.ClientSession()
        self._client = MatterClient(self._url, self._session)
        await self._client.connect()
        return self._client

    async def list_nodes(self) -> list[Any]:
        client = await self._ensure_connected()
        return list(client.get_nodes())

    async def commission(self, setup_code: str) -> int:
        """Commission a device. Returns the node_id assigned by Matter Server."""
        client = await self._ensure_connected()
        return await asyncio.wait_for(
            client.commission_with_code(setup_code),
            timeout=30.0,
        )

    async def send_command(
        self,
        node_id: int,
        command: str,
        brightness: int | None = None,
    ) -> None:
        client = await self._ensure_connected()
        if command in ("on", "off"):
            await client.send_device_command(
                node_id=node_id,
                endpoint_id=1,
                cluster_id=_ONOFF_CLUSTER,
                command_name=command,
                payload={},
            )
        elif command == "brightness" and brightness is not None:
            level = round((brightness / 100) * 254)
            await client.send_device_command(
                node_id=node_id,
                endpoint_id=1,
                cluster_id=_LEVEL_CLUSTER,
                command_name="moveToLevelWithOnOff",
                payload={
                    "level": level,
                    "transitionTime": 0,
                    "optionsMask": 0,
                    "optionsOverride": 0,
                },
            )

    async def remove_node(self, node_id: int) -> None:
        client = await self._ensure_connected()
        await client.remove_node(node_id)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        if self._session:
            await self._session.close()
            self._session = None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/python/test_matter_device.py -v
```

Expected: all 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/matter_device.py tests/python/test_matter_device.py
git commit -m "feat: add matter_device.py with DashboardMatterClient and node mapping"
```

---

### Task 3: `web_app.py` endpoints, config helpers, and dependencies

**Files:**
- Modify: `src/python/web_app.py`
- Modify: `src/python/requirements.txt`
- Modify: `configs/devices.example.yaml`

**Interfaces:**
- Consumes: `DashboardMatterClient`, `MatterDeviceInfo`, `node_to_device` from `src.python.matter_device`
- Produces:
  - `GET /api/matter/devices` → `{"devices": [...], "matter_online": bool}`
    - Each device dict: `host`, `name`, `room`, `is_on`, `is_dimmable`, `brightness`, `category`, `provider`, `node_id`, `available`
  - `POST /api/matter/commission` body `{"setup_code", "name", "room?"}` → `{"node_id": int, "name": str}`
  - `POST /api/matter/devices/{node_id}/commands/{command}?brightness=N` → `{"status": "ok"}`
  - `DELETE /api/matter/devices/{node_id}` → `{"status": "ok"}`

- [ ] **Step 1: Add dependency to `requirements.txt`**

Append to `src/python/requirements.txt`:

```
python-matter-server[client]
```

- [ ] **Step 2: Add matter section to `devices.example.yaml`**

Append to `configs/devices.example.yaml`:

```yaml
matter:
  # server_url defaults to ws://localhost:5580/ws
  # server_url: ws://localhost:5580/ws
  devices:
    # Written automatically when you commission a device from the dashboard.
    # Optional: add category override (light_switch / smart_plug / tuya_sensor).
    # - node_id: 1
    #   name: Kitchen Switch
    #   room: Kitchen
    #   category: light_switch
```

- [ ] **Step 3: Write tests for config helpers**

Create `tests/python/test_matter_config.py`:

```python
from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch


def _import_helpers():
    from src.python import web_app
    return web_app._write_matter_device_to_config, web_app._remove_matter_device_from_config


def test_write_matter_device_creates_section(tmp_path):
    config = tmp_path / "devices.local.yaml"
    write_fn, _ = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        write_fn(1, "Kitchen Switch", "Kitchen")
    data = yaml.safe_load(config.read_text())
    assert data["matter"]["devices"][0] == {"node_id": 1, "name": "Kitchen Switch", "room": "Kitchen"}


def test_write_matter_device_no_room(tmp_path):
    config = tmp_path / "devices.local.yaml"
    write_fn, _ = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        write_fn(2, "Plug", None)
    data = yaml.safe_load(config.read_text())
    assert "room" not in data["matter"]["devices"][0]


def test_write_matter_device_overwrites_existing(tmp_path):
    config = tmp_path / "devices.local.yaml"
    config.write_text("matter:\n  devices:\n  - {node_id: 1, name: Old}\n")
    write_fn, _ = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        write_fn(1, "New Name", "Bedroom")
    data = yaml.safe_load(config.read_text())
    assert len(data["matter"]["devices"]) == 1
    assert data["matter"]["devices"][0]["name"] == "New Name"


def test_remove_matter_device(tmp_path):
    config = tmp_path / "devices.local.yaml"
    config.write_text("matter:\n  devices:\n  - {node_id: 1, name: Switch}\n  - {node_id: 2, name: Plug}\n")
    _, remove_fn = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        remove_fn(1)
    data = yaml.safe_load(config.read_text())
    assert len(data["matter"]["devices"]) == 1
    assert data["matter"]["devices"][0]["node_id"] == 2


def test_remove_matter_device_missing_config(tmp_path):
    config = tmp_path / "nonexistent.yaml"
    _, remove_fn = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        remove_fn(1)  # Must not raise
```

- [ ] **Step 4: Run tests — verify they fail**

```bash
python3 -m pytest tests/python/test_matter_config.py -v
```

Expected: `AttributeError: module 'web_app' has no attribute '_write_matter_device_to_config'`

- [ ] **Step 5: Add import at top of `web_app.py`**

After the existing import on line 30:
```python
from src.python.tplink_switch import KasaLightSwitchController, SwitchDefinition
```

Add:
```python
from src.python.matter_device import DashboardMatterClient, node_to_device
```

- [ ] **Step 6: Add matter config loading at module level in `web_app.py`**

Find the block that reads `_raw_cfg = yaml.safe_load(...)` and parses integration configs. After the last existing config parse block (search for the last `_raw_cfg.get(` call before route registrations), add:

```python
_matter_cfg: dict = _raw_cfg.get("matter") or {}
_matter_server_url: str = _matter_cfg.get("server_url", "ws://localhost:5580/ws")
_matter_device_meta: dict[int, dict] = {
    int(d["node_id"]): d
    for d in (_matter_cfg.get("devices") or [])
    if "node_id" in d
}
_matter_client = DashboardMatterClient(_matter_server_url)
```

- [ ] **Step 7: Add config helper functions to `web_app.py`**

Find the `def _device_category(value: str | None) -> str:` function (near line 2337). Insert the two helpers before it:

```python
def _write_matter_device_to_config(node_id: int, name: str, room: str | None) -> None:
    cfg: dict = {}
    if DEFAULT_CONFIG_PATH.exists():
        cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text()) or {}
    matter = cfg.setdefault("matter", {})
    devices: list[dict] = matter.setdefault("devices", [])
    devices[:] = [d for d in devices if int(d.get("node_id", -1)) != node_id]
    entry: dict[str, Any] = {"node_id": node_id, "name": name}
    if room:
        entry["room"] = room
    devices.append(entry)
    DEFAULT_CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False))


def _remove_matter_device_from_config(node_id: int) -> None:
    if not DEFAULT_CONFIG_PATH.exists():
        return
    cfg: dict = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text()) or {}
    devices: list[dict] = cfg.get("matter", {}).get("devices", [])
    cfg.setdefault("matter", {})["devices"] = [
        d for d in devices if int(d.get("node_id", -1)) != node_id
    ]
    DEFAULT_CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False))
```

- [ ] **Step 8: Run config helper tests — verify they pass**

```bash
python3 -m pytest tests/python/test_matter_config.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 9: Add the 4 API endpoints to `web_app.py`**

Find the last `@app.post(...)` route (around line 379, the brightness endpoint). Add after it:

```python
class _MatterCommissionBody(BaseModel):
    setup_code: str
    name: str
    room: str | None = None


@app.get("/api/matter/devices")
async def _matter_devices_list() -> dict:
    try:
        nodes = await _matter_client.list_nodes()
        devices = []
        for node in nodes:
            meta = _matter_device_meta.get(node.node_id, {})
            info = node_to_device(
                node,
                name=meta.get("name", f"Matter Device {node.node_id}"),
                room=meta.get("room"),
                category_override=meta.get("category"),
            )
            devices.append({
                "host": f"matter:{info.node_id}",
                "name": info.name,
                "room": info.room,
                "is_on": info.is_on,
                "is_dimmable": info.is_dimmable,
                "brightness": info.brightness,
                "category": info.category,
                "provider": "matter",
                "node_id": info.node_id,
                "available": info.available,
            })
        return {"devices": devices, "matter_online": True}
    except Exception:
        return {"devices": [], "matter_online": False}


@app.post("/api/matter/commission")
async def _matter_commission(body: _MatterCommissionBody) -> dict:
    try:
        node_id = await asyncio.wait_for(
            _matter_client.commission(body.setup_code), timeout=35.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Commission timed out after 30 s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    _write_matter_device_to_config(node_id, body.name, body.room)
    _matter_device_meta[node_id] = {"node_id": node_id, "name": body.name, "room": body.room}
    return {"node_id": node_id, "name": body.name}


@app.post("/api/matter/devices/{node_id}/commands/{command}")
async def _matter_command(
    node_id: int, command: str, brightness: int | None = None
) -> dict:
    try:
        await _matter_client.send_command(node_id, command, brightness=brightness)
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.delete("/api/matter/devices/{node_id}")
async def _matter_decommission(node_id: int) -> dict:
    try:
        await _matter_client.remove_node(node_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    _matter_device_meta.pop(node_id, None)
    _remove_matter_device_from_config(node_id)
    return {"status": "ok"}
```

- [ ] **Step 10: Run all tests**

```bash
python3 -m pytest tests/python/ -v
```

Expected: all tests PASS

- [ ] **Step 11: Commit**

```bash
git add src/python/web_app.py src/python/requirements.txt configs/devices.example.yaml tests/python/test_matter_config.py
git commit -m "feat: add Matter API endpoints and config helpers to web_app"
```

---

### Task 4: HTML — Discovery sidebar, view panel, and commissioning modal

**Files:**
- Modify: `src/python/web_static/index.html`

**Interfaces:**
- Produces:
  - `data-view="discovery"` sidebar nav item in new "Discovery" section
  - `data-view-panel="discovery"` content panel with `id="matterServerStatus"`, `id="openMatterModal"`, `id="matterDeviceList"`
  - `id="matterModal"` commissioning modal with `id="matterStep1"`, `id="matterStep2"`, `id="matterPairingCode"`, `id="matterDeviceName"`, `id="matterDeviceRoom"`, `id="matterSpinner"`, `id="matterStatusText"`, `id="matterError"`, `id="matterErrorText"`

- [ ] **Step 1: Add Discovery sidebar section**

In `index.html`, find `<div class="sidebar-section">System</div>`. Insert immediately before it:

```html
    <div class="sidebar-section">Discovery</div>
    <ul class="room-list">
      <li class="room-item" data-view="discovery">
        <span class="room-icon"><i class="ti ti-antenna"></i></span>
        Add Matter
      </li>
    </ul>

```

- [ ] **Step 2: Add Discovery view panel**

Find `<!-- ── THEME VIEW ── -->`. Insert the Discovery panel immediately before it:

```html
    <!-- ── DISCOVERY VIEW ── -->
    <div class="view-panel" data-view-panel="discovery">
      <div class="section-header">
        <span class="section-title">Discovery</span>
        <span class="section-meta">Pair new Matter devices</span>
      </div>
      <div class="discovery-panel">
        <div class="discovery-server-row">
          <span class="discovery-server-label">Matter Server</span>
          <span class="discovery-server-badge" id="matterServerStatus">Checking…</span>
        </div>
        <button class="discovery-add-btn" id="openMatterModal" type="button">
          <i class="ti ti-circle-plus"></i>
          Add Matter Device
        </button>
        <div id="matterDeviceList" class="discovery-device-list"></div>
      </div>
    </div>

```

- [ ] **Step 3: Add commissioning modal**

Find `</main>`. Insert the modal immediately before it:

```html
<!-- ── MATTER COMMISSIONING MODAL ── -->
<div class="modal-overlay" id="matterModal" hidden aria-modal="true" role="dialog" aria-labelledby="matterModalTitle">
  <div class="modal-card">
    <div class="modal-header">
      <span class="modal-title" id="matterModalTitle">Add Matter Device</span>
      <button class="modal-close" id="closeMatterModal" type="button" aria-label="Close">
        <i class="ti ti-x"></i>
      </button>
    </div>

    <!-- Step 1: Input -->
    <div id="matterStep1">
      <label class="modal-label">
        Pairing code
        <input class="modal-input" id="matterPairingCode" type="text"
               placeholder="34970112332" maxlength="11" inputmode="numeric" autocomplete="off">
      </label>
      <label class="modal-label">
        Name
        <input class="modal-input" id="matterDeviceName" type="text" placeholder="Kitchen Switch">
      </label>
      <label class="modal-label">
        Room
        <input class="modal-input" id="matterDeviceRoom" type="text" placeholder="Kitchen">
      </label>
      <div class="modal-qr-placeholder">
        <i class="ti ti-qrcode"></i>
        <span>QR code scanning coming soon</span>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" id="cancelMatterModal" type="button">Cancel</button>
        <button class="btn-primary" id="submitMatterCommission" type="button">Pair Device</button>
      </div>
    </div>

    <!-- Step 2: Progress -->
    <div id="matterStep2" hidden>
      <div class="modal-progress">
        <div class="modal-spinner" id="matterSpinner"></div>
        <span class="modal-status-text" id="matterStatusText">Connecting…</span>
      </div>
      <div class="modal-error" id="matterError" hidden>
        <span id="matterErrorText"></span>
        <button class="btn-secondary" id="retryMatterCommission" type="button">Retry</button>
      </div>
    </div>
  </div>
</div>

```

- [ ] **Step 4: Bump CSS version string**

Find:
```html
  <link rel="stylesheet" href="/static/styles.css?v=20260625-theme-preview">
```

Replace with:
```html
  <link rel="stylesheet" href="/static/styles.css?v=20260625-matter">
```

- [ ] **Step 5: Commit**

```bash
git add src/python/web_static/index.html
git commit -m "feat: add Discovery sidebar, view panel, and Matter commissioning modal HTML"
```

---

### Task 5: CSS — Discovery panel, modal, and Matter badge

**Files:**
- Modify: `src/python/web_static/styles.css`

**Interfaces:**
- Produces: `.discovery-panel`, `.discovery-server-badge.online/.offline`, `.discovery-add-btn`, `.discovery-device-list`, `.discovery-device-row`, `.discovery-remove-btn`, `.modal-overlay`, `.modal-card`, `.modal-label`, `.modal-input`, `.modal-spinner`, `.modal-error`, `.btn-primary`, `.btn-secondary`, `.matter-badge`

- [ ] **Step 1: Add all new styles**

Find `/* ── BOTTOM ROW ── */` in `styles.css`. Insert the entire block before it:

```css
/* ── DISCOVERY PANEL ── */
.discovery-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 480px;
}

.discovery-server-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.discovery-server-label { color: var(--muted); }

.discovery-server-badge {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 20px;
  background: var(--surface2);
  color: var(--muted);
}

.discovery-server-badge.online {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.discovery-server-badge.offline {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.discovery-add-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface2);
  color: var(--fg);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  align-self: flex-start;
}

.discovery-add-btn:hover {
  background: var(--card);
  border-color: var(--t-accent);
  color: var(--t-accent);
}

.discovery-device-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.discovery-device-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  font-size: 13px;
}

.discovery-device-row-name { font-weight: 500; color: var(--fg); }
.discovery-device-row-room { font-size: 11px; color: var(--muted); margin-top: 2px; }

.discovery-remove-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 14px;
  flex-shrink: 0;
  transition: color 0.15s, border-color 0.15s;
}
.discovery-remove-btn:hover { color: #ef4444; border-color: #ef4444; }

/* ── COMMISSIONING MODAL ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-overlay[hidden] { display: none; }

.modal-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--fg);
}

.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border: none;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 16px;
  border-radius: 6px;
  transition: color 0.15s;
}
.modal-close:hover { color: var(--fg); }

#matterStep1 { display: flex; flex-direction: column; gap: 14px; }

.modal-label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
  letter-spacing: 0.04em;
}

.modal-input {
  padding: 9px 12px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--fg);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.modal-input:focus { border-color: var(--t-accent); }

.modal-qr-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--muted);
  font-size: 13px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.btn-primary {
  padding: 9px 18px;
  background: var(--t-accent);
  color: #000;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary:hover { opacity: 0.85; }

.btn-secondary {
  padding: 9px 18px;
  background: var(--surface2);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-secondary:hover { background: var(--card); }

.modal-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 24px 0;
}

.modal-spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--t-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.modal-status-text { font-size: 14px; color: var(--muted); }

.modal-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #ef4444;
  font-size: 13px;
  text-align: center;
  padding: 12px 0;
}
.modal-error[hidden] { display: none; }

/* ── MATTER BADGE ── */
.matter-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.18);
  color: #818cf8;
  vertical-align: middle;
  margin-left: 4px;
  line-height: 1.6;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/python/web_static/styles.css
git commit -m "feat: add Discovery panel, commissioning modal, and matter badge CSS"
```

---

### Task 6: JS — device merge, command routing, Discovery view, and modal logic

**Files:**
- Modify: `src/python/web_static/app.js`

**Interfaces:**
- Consumes:
  - `GET /api/matter/devices` → `{devices, matter_online}`
  - `POST /api/matter/commission`
  - `POST /api/matter/devices/{node_id}/commands/{command}?brightness=N`
  - `DELETE /api/matter/devices/{node_id}`
  - `renderDevices(devices, cameras)` at line 672
  - `sendCommand(host, command)` at line 2516
  - `sendBrightness(host, level)` at line 422
  - `activateView(viewName)` at line 2566
  - `loadDevices()` at line 2479
- Produces: Matter devices rendered in Lights/Plugs grids with MATTER badge; command routing for `host` values starting with `"matter:"`; Discovery view with live server status and device list; commissioning modal

- [ ] **Step 1: Merge Matter devices in `loadDevices()` (line 2479)**

Replace the destructured `Promise.all` at the top of `loadDevices()` with:

```javascript
async function loadDevices() {
  if (statusDot) statusDot.classList.remove("online");
  apiStatus.textContent = "Refreshing";

  const [deviceData, cameraData, tuyaData, weatherData, ecobeeData, homeAssistantData, alarmData, matterData] = await Promise.all([
    requestJson("/api/devices"),
    requestJson("/api/cameras"),
    requestJson("/api/tuya/devices"),
    requestJson("/api/weather"),
    requestJson("/api/ecobee/thermostats"),
    requestJson("/api/home-assistant/entities"),
    requestJson("/api/alarm"),
    requestJson("/api/matter/devices").catch(() => ({ devices: [], matter_online: false })),
  ]);
```

Then find the `renderDevices(deviceData.devices, cameraData.cameras);` call and replace with:

```javascript
  renderDevices(deviceData.devices, cameraData.cameras, matterData.devices || []);
```

After the `renderAlarmSection(alarmData);` line add:

```javascript
  _updateMatterServerStatus(matterData.matter_online ?? false);
  _renderMatterDeviceList(matterData.devices || []);
```

- [ ] **Step 2: Update `renderDevices()` to accept and merge Matter devices (line 672)**

Replace the `renderDevices` function signature and first two lines:

```javascript
function renderDevices(devices, cameras, matterDevices = []) {
  const matterLights = matterDevices.filter((d) => d.category === "light_switch");
  const matterPlugs  = matterDevices.filter((d) => d.category === "smart_plug");

  const lightDevices = [...devices.filter((d) => d.category === "light_switch"), ...matterLights];
  const plugDevices  = [...devices.filter((d) => d.category === "smart_plug"),   ...matterPlugs];

  deviceCount.textContent    = String(devices.length + matterDevices.length);
  onCount.textContent        = String([...devices, ...matterDevices].filter((d) => d.is_on === true).length);
  lightCount.textContent     = String(lightDevices.length);
  plugCount.textContent      = String(plugDevices.length);
  cameraTabCount.textContent = String(cameras.length);

  renderLightScenes(lightDevices);
  renderLightDragLock();
  renderDeviceGroup(lightGrid, applyDeviceOrder(lightDevices, "light_switch"), "No light switches found.");
  renderPlugSection(plugDevices);
}
```

- [ ] **Step 3: Add MATTER badge in `renderDeviceGroup()` (line 882)**

Inside `renderDeviceGroup`, find the template literal that contains `<h3 class="device-name">`. Change it to:

```javascript
        <h3 class="device-name">${escapeHtml(device.name)}${device.provider === "matter" ? '<span class="matter-badge">MATTER</span>' : ""}</h3>
```

Apply the identical change in the plug card template if `renderPlugSection` uses a separate template (search for `device-name` in `renderPlugSection` or `renderPlugGroup`).

- [ ] **Step 4: Add Matter command routing in `sendCommand()` (line 2516)**

Replace the body of `sendCommand`:

```javascript
async function sendCommand(host, command, options = {}) {
  apiStatus.textContent = "Sending";
  if (host.startsWith("matter:")) {
    const nodeId = host.slice(7);
    await requestJson(`/api/matter/devices/${nodeId}/commands/${command}`, { method: "POST" });
  } else {
    await requestJson("/api/devices/" + host + "/commands/" + command, { method: "POST" });
  }
  logActivity("Switch " + host.split(".").pop() + " turned " + command);
  if (options.skipRefresh !== true) await loadDevices();
}
```

- [ ] **Step 5: Add Matter routing in `sendBrightness()` (line 422)**

Replace the body of `sendBrightness`:

```javascript
async function sendBrightness(host, level) {
  recordManualLightOverride(host, { type: "brightness", level });
  if (host.startsWith("matter:")) {
    const nodeId = host.slice(7);
    const resp = await fetch(`/api/matter/devices/${nodeId}/commands/brightness?brightness=${level}`, {
      method: "POST",
    });
    if (!resp.ok) throw new Error("Brightness set failed: " + resp.status);
    return resp.json();
  }
  const resp = await fetch("/api/devices/" + encodeURIComponent(host) + "/brightness", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level }),
  });
  if (!resp.ok) throw new Error("Brightness set failed: " + resp.status);
  return resp.json();
}
```

- [ ] **Step 6: Add Matter routing in light scene dispatch (line ~2973)**

Find the lambda inside `Promise.allSettled(lightCards.map(...))` that calls `/api/devices/`. Replace the inner `return requestJson(...)` with:

```javascript
        if (host.startsWith("matter:")) {
          const nodeId = host.slice(7);
          return requestJson(`/api/matter/devices/${nodeId}/commands/${command}`, { method: "POST" });
        }
        return requestJson("/api/devices/" + host + "/commands/" + command, { method: "POST" });
```

- [ ] **Step 7: Hook Discovery view into `activateView()` (line 2566)**

Add one line inside `activateView` after the existing body:

```javascript
function activateView(viewName) {
  railButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  });
  viewPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === viewName);
  });
  document.body.classList.toggle("home-assistant-mode", viewName === "homeassistant");
  if (viewName === "discovery") {
    requestJson("/api/matter/devices")
      .then((data) => {
        _updateMatterServerStatus(data.matter_online ?? false);
        _renderMatterDeviceList(data.devices || []);
      })
      .catch(() => _updateMatterServerStatus(false));
  }
}
```

- [ ] **Step 8: Add Discovery helper functions**

Add these two functions before the `loadDevices()` call near line 3150:

```javascript
function _updateMatterServerStatus(online) {
  const badge = document.querySelector("#matterServerStatus");
  if (!badge) return;
  badge.textContent = online ? "Online" : "Offline";
  badge.className = "discovery-server-badge " + (online ? "online" : "offline");
}

function _renderMatterDeviceList(devices) {
  const list = document.querySelector("#matterDeviceList");
  if (!list) return;
  if (!devices.length) {
    list.innerHTML = '<p style="font-size:13px;color:var(--muted)">No Matter devices paired yet.</p>';
    return;
  }
  list.innerHTML = devices.map((d) => `
    <div class="discovery-device-row">
      <div>
        <div class="discovery-device-row-name">${escapeHtml(d.name)}</div>
        ${d.room ? `<div class="discovery-device-row-room">${escapeHtml(d.room)}</div>` : ""}
      </div>
      <button class="discovery-remove-btn"
              data-matter-remove="${d.node_id}"
              title="Remove ${escapeHtml(d.name)}"
              type="button">
        <i class="ti ti-trash"></i>
      </button>
    </div>
  `).join("");
}
```

- [ ] **Step 9: Add commissioning modal logic**

Add the following block immediately before the `loadDevices().catch(...)` call near the end of the file:

```javascript
/* ── MATTER COMMISSIONING MODAL ── */
(function initMatterModal() {
  const modal      = document.querySelector("#matterModal");
  const step1      = document.querySelector("#matterStep1");
  const step2      = document.querySelector("#matterStep2");
  const spinner    = document.querySelector("#matterSpinner");
  const statusText = document.querySelector("#matterStatusText");
  const errorBox   = document.querySelector("#matterError");
  const errorText  = document.querySelector("#matterErrorText");
  if (!modal) return;

  function openModal() {
    modal.hidden = false;
    _showMatterStep(1);
    document.querySelector("#matterPairingCode").value = "";
    document.querySelector("#matterDeviceName").value  = "";
    document.querySelector("#matterDeviceRoom").value  = "";
  }

  function closeModal() { modal.hidden = true; }

  function _showMatterStep(n) {
    step1.hidden = n !== 1;
    step2.hidden = n !== 2;
    errorBox.hidden = true;
    spinner.style.display = "block";
  }

  function _showMatterError(msg) {
    spinner.style.display = "none";
    errorBox.hidden = false;
    errorText.textContent = msg;
  }

  document.querySelector("#openMatterModal")?.addEventListener("click", openModal);
  document.querySelector("#closeMatterModal")?.addEventListener("click", closeModal);
  document.querySelector("#cancelMatterModal")?.addEventListener("click", closeModal);
  document.querySelector("#retryMatterCommission")?.addEventListener("click", () => _showMatterStep(1));
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  document.querySelector("#submitMatterCommission")?.addEventListener("click", async () => {
    const code = document.querySelector("#matterPairingCode").value.trim();
    const name = document.querySelector("#matterDeviceName").value.trim();
    const room = document.querySelector("#matterDeviceRoom").value.trim();
    if (!code) { document.querySelector("#matterPairingCode").focus(); return; }
    if (!name) { document.querySelector("#matterDeviceName").focus(); return; }

    _showMatterStep(2);
    statusText.textContent = "Connecting…";

    const steps = ["Connecting…", "Pairing…", "Commissioning…"];
    let stepIdx = 0;
    const timer = setInterval(() => {
      if (stepIdx < steps.length - 1) statusText.textContent = steps[++stepIdx];
    }, 8000);

    try {
      const resp = await fetch("/api/matter/commission", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setup_code: code, name, room: room || null }),
      });
      clearInterval(timer);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${resp.status}`);
      }
      spinner.style.display = "none";
      statusText.textContent = "Done ✓";
      setTimeout(() => { closeModal(); loadDevices(); }, 1200);
    } catch (e) {
      clearInterval(timer);
      _showMatterError(e.message);
    }
  });

  document.querySelector("#matterDeviceList")?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-matter-remove]");
    if (!btn) return;
    const nodeId = btn.dataset.matterRemove;
    if (!confirm("Remove this Matter device? It will need to be factory reset to pair again.")) return;
    try {
      await fetch(`/api/matter/devices/${nodeId}`, { method: "DELETE" });
      loadDevices();
    } catch {
      logActivity("Failed to remove Matter device", "error");
    }
  });
})();
```

- [ ] **Step 10: Commit**

```bash
git add src/python/web_static/app.js
git commit -m "feat: integrate Matter devices into dashboard — merge, command routing, modal"
```

---

### Task 7: Deploy and smoke test on the Pi

**Files:** none (deployment only)

- [ ] **Step 1: Install Python Matter Server on the Pi**

```bash
ssh smarthome@192.168.0.176 "bash -s" < scripts/install-matter-server.sh
```

Expected final line: `==> Matter server is running at ws://localhost:5580/ws`

- [ ] **Step 2: Deploy dashboard**

```bash
bash scripts/deploy-dashboard.sh
```

- [ ] **Step 3: Verify Discovery view**

Open `http://192.168.0.176:8000`. Click "Add Matter" in the sidebar. Verify:
- Matter Server badge shows **Online** in green
- "Add Matter Device" button is visible
- "No Matter devices paired yet." message appears

- [ ] **Step 4: Verify existing views are unaffected**

Navigate to Lights, Plugs, Sensors, Climate. Confirm all TP-Link and Tuya devices still appear and controls respond correctly.

- [ ] **Step 5: Commission a device (requires a factory-reset Matter switch in pairing mode)**

1. Factory reset the Tapo switch — hold the button until the LED flashes rapidly
2. Click "Add Matter Device"
3. Enter the 11-digit pairing code from the label
4. Enter a name (e.g. "Kitchen Switch") and room (e.g. "Kitchen")
5. Click "Pair Device"
6. Watch: `Connecting… → Pairing… → Commissioning… → Done ✓`
7. Modal closes and device list reloads

- [ ] **Step 6: Verify the new device in Lights view**

Navigate to Lights. The new device should appear with a purple `MATTER` badge. Click its rocker switch — verify the physical light responds.

- [ ] **Step 7: Verify `devices.local.yaml` was updated**

```bash
ssh smarthome@192.168.0.176 "grep -A5 'matter:' ~/smart-home-rpi4/configs/devices.local.yaml"
```

Expected output includes the newly paired device with its `node_id`, `name`, and `room`.
