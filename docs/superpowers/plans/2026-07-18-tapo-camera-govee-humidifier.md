# Tapo Camera + Govee H7140 Humidifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect a new Tapo camera (config-only) and a Govee H7140 humidifier (new `govee_cloud` provider + Humidifiers dashboard view) to the dashboard.

**Architecture:** The camera reuses the existing Tapo RTSP/go2rtc pipeline — example config only. The humidifier adds a `humidifiers:` config section, Govee Developer API v2 client helpers in `web_app.py` (runtime capability discovery, cached device list), two FastAPI endpoints, and a Humidifiers nav view mirroring the Ambient Lights pattern.

**Tech Stack:** Python 3 / FastAPI / urllib (stdlib HTTP, matching existing code), pytest + TestClient + monkeypatch, vanilla JS frontend.

**Spec:** `docs/superpowers/specs/2026-07-18-tapo-camera-govee-humidifier-design.md`

## Global Constraints

- Never commit secrets. API key comes only from the `GOVEE_API_KEY` environment variable.
- HTTP calls use `_URLRequest` + `urlopen` (stdlib), matching existing `web_app.py` code — no new dependencies.
- Tests never make live network calls; monkeypatch `_govee_cloud_request`.
- The working tree has unrelated uncommitted changes (`BUILD_COUNT`, `src/cpp/matter_bridge/*`, `src/python/web_static/build_info.json`, `index.html`) — `git add` only the specific files named in each commit step, never `git add -A`.
- Run tests from the project root: `python3 -m pytest` (WSL) or via Docker per CLAUDE.md.
- A dashboard-file edit means `scripts/deploy-dashboard.sh` runs at the end (user's standing preference).
- Govee Cloud API base: `https://openapi.api.govee.com`, auth header `Govee-API-Key`, endpoints `GET /router/api/v1/user/devices`, `POST /router/api/v1/device/state`, `POST /router/api/v1/device/control`.

---

### Task 1: Tapo camera example config entry

**Files:**
- Modify: `configs/devices.example.yaml` (the `tplink.cameras` list, after the `family_room_camera` entry)

**Interfaces:**
- Consumes: existing camera pipeline (no code changes).
- Produces: documented example the user copies into `devices.local.yaml` on the Pi.

- [ ] **Step 1: Add the example camera entry**

In `configs/devices.example.yaml`, append to `tplink.cameras` (directly after the `family_room_camera` entry, matching its indentation):

```yaml
    # Additional Tapo cameras follow the same pattern. Reuse the shared
    # TAPO_CAMERA_USERNAME / TAPO_CAMERA_PASSWORD env vars (the camera-account
    # credentials set in the Tapo app) unless the camera has its own account.
    - name: bedroom_camera
      host: 192.168.0.25
      model: Tapo C210
      room: Bedroom
      stream_name: bedroom_camera
      go2rtc_url: http://192.168.0.176:1984
      username_env: TAPO_CAMERA_USERNAME
      password_env: TAPO_CAMERA_PASSWORD
      stream_path: /stream2
      mjpeg_fps: 10
      mjpeg_width: 640
      mjpeg_quality: 7
```

- [ ] **Step 2: Verify the YAML still parses**

Run: `python3 -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('configs/devices.example.yaml').read_text()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add configs/devices.example.yaml
git commit -m "docs: add second Tapo camera example entry"
```

---

### Task 2: Humidifier config schema + loader

**Files:**
- Modify: `src/python/web_app.py` (dataclass near `AmbientLightDefinition` at ~line 144; loader near `_load_ambient_lights` at ~line 1213)
- Modify: `configs/devices.example.yaml` (new top-level `humidifiers:` section after `ambient_lights:`)
- Test: `tests/python/test_humidifiers.py` (new file)

**Interfaces:**
- Consumes: `yaml`, `Path`, existing `@dataclass(frozen=True)` pattern.
- Produces: `HumidifierDefinition(name: str, provider: str, model: str | None, room: str | None, device_id: str | None)` and `_load_humidifiers(path: Path) -> list[HumidifierDefinition]`. Later tasks import both.

- [ ] **Step 1: Write the failing tests**

Create `tests/python/test_humidifiers.py`:

```python
from pathlib import Path

from src.python.web_app import _load_humidifiers


def _write_humidifier_config(path: Path) -> None:
    path.write_text(
        """
humidifiers:
  devices:
    - name: Bedroom Humidifier
      provider: govee_cloud
      model: H7140
      room: Bedroom
      device_id: replace_me
    - name: Disabled Humidifier
      provider: govee_cloud
      model: H7141
      enabled: false
""",
        encoding="utf-8",
    )


def test_load_humidifiers_parses_entries_and_skips_disabled(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    _write_humidifier_config(config)

    humidifiers = _load_humidifiers(config)

    assert len(humidifiers) == 1
    assert humidifiers[0].name == "Bedroom Humidifier"
    assert humidifiers[0].provider == "govee_cloud"
    assert humidifiers[0].model == "H7140"
    assert humidifiers[0].room == "Bedroom"
    assert humidifiers[0].device_id == "replace_me"


def test_load_humidifiers_tolerates_missing_file_and_section(tmp_path: Path) -> None:
    missing = tmp_path / "devices.local.yaml"
    assert _load_humidifiers(missing) == []

    empty = tmp_path / "empty.yaml"
    empty.write_text("tplink: {}\n", encoding="utf-8")
    assert _load_humidifiers(empty) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: FAIL — `ImportError: cannot import name '_load_humidifiers'`

- [ ] **Step 3: Implement dataclass and loader**

In `src/python/web_app.py`, directly after the `AmbientLightDefinition` dataclass (~line 153):

```python
@dataclass(frozen=True)
class HumidifierDefinition:
    name: str
    provider: str
    model: str | None
    room: str | None
    device_id: str | None
```

Directly after `_load_ambient_lights` (~line 1233):

```python
def _load_humidifiers(path: Path) -> list[HumidifierDefinition]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices = []
    for item in payload.get("humidifiers", {}).get("devices", []):
        if item.get("enabled") is False:
            continue
        name = str(item.get("name") or item.get("id") or item.get("model") or "Humidifier")
        provider = str(item.get("provider") or "govee_cloud").lower()
        devices.append(
            HumidifierDefinition(
                name=name,
                provider=provider,
                model=str(item.get("model")) if item.get("model") else None,
                room=item.get("room"),
                device_id=str(item.get("device_id") or "") or None,
            )
        )
    return devices
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: 2 PASS

- [ ] **Step 5: Add the example config section**

In `configs/devices.example.yaml`, after the `ambient_lights:` section (before `mqtt:`):

```yaml
humidifiers:
  devices:
    # Govee humidifiers are controlled through the Govee Developer API v2.
    # Apply for a key in the Govee app (Settings -> Apply for API Key) and set
    # it as the GOVEE_API_KEY environment variable on the Pi — never here.
    # device_id is the "device" value from the Govee API device list. Leave
    # replace_me and the app matches by model when the account has exactly
    # one device of that model.
    - name: Bedroom Humidifier
      provider: govee_cloud
      model: H7140
      room: Bedroom
      device_id: replace_me
```

- [ ] **Step 6: Verify YAML parses and full suite still green**

Run: `python3 -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('configs/devices.example.yaml').read_text()); print('ok')" && python3 -m pytest tests/python/test_humidifiers.py tests/python/test_web_app.py -q`
Expected: `ok`, all tests pass

- [ ] **Step 7: Commit**

```bash
git add src/python/web_app.py configs/devices.example.yaml tests/python/test_humidifiers.py
git commit -m "feat: add humidifiers config schema and loader"
```

---

### Task 3: Govee Cloud API client + device matching

**Files:**
- Modify: `src/python/web_app.py` (new section after the Govee LAN block, ~line 1490, before `GOVEE_BLE_WRITE_UUIDS`)
- Test: `tests/python/test_humidifiers.py`

**Interfaces:**
- Consumes: `HumidifierDefinition` (Task 2), `_is_real_ble_address` (existing placeholder check, works for any string), `_URLRequest`/`urlopen`, `os.getenv`, `time`, `json`.
- Produces (later tasks call these exact names):
  - `_govee_api_key() -> str | None`
  - `_govee_cloud_request(path: str, payload: dict | None = None) -> dict` — raises on HTTP/network error
  - `_govee_cloud_devices(force: bool = False) -> list[dict]` — device list, cached `GOVEE_CLOUD_DEVICE_CACHE_TTL` (600 s) in `_GOVEE_CLOUD_CACHE`
  - `_match_govee_cloud_device(humidifier: HumidifierDefinition, devices: list[dict]) -> dict | None`
  - `_govee_mist_range(entry: dict) -> tuple[int, int]`
  - `_govee_gear_mode_value(entry: dict) -> int`
  - `_govee_humidifier_state(entry: dict) -> dict | None` — `{"online": bool, "is_on": bool, "mist_level": int, "humidity": number}` (keys present only when reported)
  - `_govee_cloud_control(entry: dict, capability_type: str, instance: str, value: Any) -> dict`
  - `HUMIDIFIER_RUNTIME_STATE: dict[str, dict[str, Any]]` — last-known state keyed by Govee device id

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_humidifiers.py` (add `import pytest` and extend the imports from `src.python.web_app` — full import line after this task:
`from src.python.web_app import _load_humidifiers, _match_govee_cloud_device, _govee_mist_range, _govee_gear_mode_value, _govee_humidifier_state, _govee_cloud_devices, HumidifierDefinition`
plus `from src.python import web_app`):

```python
FAKE_DEVICE_LIST = [
    {
        "sku": "H7140",
        "device": "AA:BB:CC:DD:EE:FF:11:22",
        "deviceName": "Bedroom Humidifier",
        "capabilities": [
            {"type": "devices.capabilities.on_off", "instance": "powerSwitch"},
            {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "parameters": {
                    "fields": [
                        {
                            "fieldName": "workMode",
                            "options": [{"name": "gearMode", "value": 1}, {"name": "Auto", "value": 3}],
                        },
                        {
                            "fieldName": "modeValue",
                            "options": [
                                {"name": "gearMode", "options": [{"value": 1}, {"value": 2}, {"value": 3}]},
                                {"name": "Auto", "value": 3},
                            ],
                        },
                    ]
                },
            },
        ],
    },
    {"sku": "H6076", "device": "11:22:33:44:55:66:77:88", "deviceName": "Floor Lamp", "capabilities": []},
]


@pytest.fixture(autouse=True)
def _reset_govee_cloud_state():
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.HUMIDIFIER_RUNTIME_STATE.clear()
    yield
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.HUMIDIFIER_RUNTIME_STATE.clear()


def _definition(device_id=None, model="H7140"):
    return HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model=model, room="Bedroom", device_id=device_id
    )


def test_match_by_device_id_beats_model() -> None:
    match = _match_govee_cloud_device(_definition(device_id="AA:BB:CC:DD:EE:FF:11:22"), FAKE_DEVICE_LIST)
    assert match["deviceName"] == "Bedroom Humidifier"


def test_match_falls_back_to_unique_model_when_id_is_placeholder() -> None:
    match = _match_govee_cloud_device(_definition(device_id="replace_me"), FAKE_DEVICE_LIST)
    assert match["sku"] == "H7140"


def test_match_returns_none_for_ambiguous_model() -> None:
    doubled = FAKE_DEVICE_LIST + [dict(FAKE_DEVICE_LIST[0], device="other")]
    assert _match_govee_cloud_device(_definition(device_id=None), doubled) is None


def test_mist_range_and_gear_mode_come_from_capabilities() -> None:
    assert _govee_mist_range(FAKE_DEVICE_LIST[0]) == (1, 3)
    assert _govee_gear_mode_value(FAKE_DEVICE_LIST[0]) == 1
    # Unknown capability shape falls back to a safe default.
    assert _govee_mist_range(FAKE_DEVICE_LIST[1]) == (1, 8)
    assert _govee_gear_mode_value(FAKE_DEVICE_LIST[1]) == 1


def test_device_list_is_cached(monkeypatch) -> None:
    calls = []

    def fake_request(path, payload=None):
        calls.append(path)
        return {"code": 200, "data": FAKE_DEVICE_LIST}

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    assert _govee_cloud_devices() == FAKE_DEVICE_LIST
    assert _govee_cloud_devices() == FAKE_DEVICE_LIST
    assert calls == ["/router/api/v1/user/devices"]


def test_humidifier_state_parses_capability_values(monkeypatch) -> None:
    def fake_request(path, payload=None):
        assert path == "/router/api/v1/device/state"
        assert payload["payload"]["sku"] == "H7140"
        return {
            "payload": {
                "capabilities": [
                    {"type": "devices.capabilities.online", "instance": "online", "state": {"value": True}},
                    {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "state": {"value": 1}},
                    {"type": "devices.capabilities.property", "instance": "humidity", "state": {"value": 45}},
                    {
                        "type": "devices.capabilities.work_mode",
                        "instance": "workMode",
                        "state": {"value": {"workMode": 1, "modeValue": 2}},
                    },
                ]
            }
        }

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)

    state = _govee_humidifier_state(FAKE_DEVICE_LIST[0])
    assert state == {"online": True, "is_on": True, "humidity": 45, "mist_level": 2}


def test_humidifier_state_returns_none_on_cloud_error(monkeypatch) -> None:
    def fake_request(path, payload=None):
        raise OSError("boom")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    assert _govee_humidifier_state(FAKE_DEVICE_LIST[0]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: FAIL — `ImportError: cannot import name '_match_govee_cloud_device'`

- [ ] **Step 3: Implement the client helpers**

In `src/python/web_app.py`, after the Govee LAN block ends (just before `GOVEE_BLE_WRITE_UUIDS`, ~line 1499), add:

```python
# ── Govee Cloud (Developer API v2) — humidifiers ──
# Govee humidifiers (e.g. H7140) do not speak the LAN or BLE light protocols;
# control goes through the cloud API with a per-account key (GOVEE_API_KEY).
# Capabilities are discovered from the device list at runtime, not hardcoded.
GOVEE_CLOUD_BASE = "https://openapi.api.govee.com"
GOVEE_CLOUD_DEVICE_CACHE_TTL = 600.0
_GOVEE_CLOUD_CACHE: dict[str, Any] = {"devices": None, "fetched": 0.0}
# Last-known state per Govee device id, served when the cloud is unreachable.
HUMIDIFIER_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _govee_api_key() -> str | None:
    return os.getenv("GOVEE_API_KEY") or None


def _govee_cloud_request(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    key = _govee_api_key()
    if not key:
        raise RuntimeError("GOVEE_API_KEY is not configured")
    body = json.dumps(payload).encode() if payload is not None else None
    request = _URLRequest(
        f"{GOVEE_CLOUD_BASE}{path}",
        data=body,
        headers={"Govee-API-Key": key, "Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _govee_cloud_devices(force: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    cached = _GOVEE_CLOUD_CACHE.get("devices")
    if not force and cached is not None and now - _GOVEE_CLOUD_CACHE["fetched"] < GOVEE_CLOUD_DEVICE_CACHE_TTL:
        return cached
    payload = _govee_cloud_request("/router/api/v1/user/devices")
    devices = payload.get("data") or []
    _GOVEE_CLOUD_CACHE["devices"] = devices
    _GOVEE_CLOUD_CACHE["fetched"] = now
    return devices


def _match_govee_cloud_device(
    humidifier: HumidifierDefinition, devices: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if _is_real_ble_address(humidifier.device_id):
        for entry in devices:
            if str(entry.get("device") or "").lower() == humidifier.device_id.lower():
                return entry
        return None
    if humidifier.model:
        matches = [e for e in devices if str(e.get("sku") or "").upper() == humidifier.model.upper()]
        if len(matches) == 1:
            return matches[0]
    return None


def _govee_work_mode_fields(entry: dict[str, Any]) -> list[dict[str, Any]]:
    for cap in entry.get("capabilities") or []:
        if cap.get("instance") == "workMode":
            return (cap.get("parameters") or {}).get("fields") or []
    return []


def _govee_gear_mode_value(entry: dict[str, Any]) -> int:
    for field in _govee_work_mode_fields(entry):
        if field.get("fieldName") != "workMode":
            continue
        for option in field.get("options") or []:
            if option.get("name") == "gearMode" and option.get("value") is not None:
                return int(option["value"])
    return 1


def _govee_mist_range(entry: dict[str, Any]) -> tuple[int, int]:
    for field in _govee_work_mode_fields(entry):
        if field.get("fieldName") != "modeValue":
            continue
        for option in field.get("options") or []:
            if option.get("name") != "gearMode":
                continue
            nested = option.get("options") or []
            values = [int(o["value"]) for o in nested if isinstance(o, dict) and o.get("value") is not None]
            if values:
                return min(values), max(values)
            rng = option.get("range")
            if isinstance(rng, dict) and rng.get("min") is not None and rng.get("max") is not None:
                return int(rng["min"]), int(rng["max"])
    return 1, 8


def _govee_humidifier_state(entry: dict[str, Any]) -> dict[str, Any] | None:
    try:
        payload = _govee_cloud_request(
            "/router/api/v1/device/state",
            {
                "requestId": "smart-home-rpi4",
                "payload": {"sku": entry.get("sku"), "device": entry.get("device")},
            },
        )
    except Exception:
        return None
    state: dict[str, Any] = {}
    for cap in (payload.get("payload") or {}).get("capabilities") or []:
        instance = cap.get("instance")
        value = (cap.get("state") or {}).get("value")
        if instance == "online":
            state["online"] = bool(value)
        elif instance == "powerSwitch":
            state["is_on"] = value == 1
        elif instance == "humidity" and isinstance(value, (int, float)):
            state["humidity"] = value
        elif instance == "workMode" and isinstance(value, dict) and value.get("modeValue") is not None:
            state["mist_level"] = value["modeValue"]
    return state


def _govee_cloud_control(
    entry: dict[str, Any], capability_type: str, instance: str, value: Any
) -> dict[str, Any]:
    return _govee_cloud_request(
        "/router/api/v1/device/control",
        {
            "requestId": "smart-home-rpi4",
            "payload": {
                "sku": entry.get("sku"),
                "device": entry.get("device"),
                "capability": {"type": capability_type, "instance": instance, "value": value},
            },
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: all PASS (Task 2's tests included)

- [ ] **Step 5: Commit**

```bash
git add src/python/web_app.py tests/python/test_humidifiers.py
git commit -m "feat: add Govee Cloud API v2 client with capability discovery"
```

---

### Task 4: Humidifier cards + GET /api/humidifiers

**Files:**
- Modify: `src/python/web_app.py` (card builders after `_govee_cloud_control`; endpoint in `create_app` after the ambient-lights routes, ~line 468)
- Test: `tests/python/test_humidifiers.py`

**Interfaces:**
- Consumes: everything from Tasks 2–3.
- Produces:
  - `_humidifier_card(humidifier: HumidifierDefinition) -> dict` — keys: `id`, `name`, `provider`, `model`, `room`, `status` (`configured` | `needs_api_key` | `not_found` | `cloud_unreachable` | `unsupported`), `note`, `controllable: bool`, `is_on`, `mist_level`, `humidity`, `online`, `capabilities: {"power": bool, "mist_level": {"min": int, "max": int} | None}`
  - `_humidifier_cards(path: Path) -> dict` returning `{"humidifiers": [...]}`
  - `GET /api/humidifiers` → that payload
  - `_find_humidifier(humidifiers, humidifier_id) -> HumidifierDefinition` (404 on miss; id is the URL-quoted name, matching ambient lights)

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_humidifiers.py`. Reuse the `FakeController` / `_write_discovery` pattern from `tests/python/test_web_app.py` — copy these imports and helpers into the file:

```python
import json

from fastapi.testclient import TestClient

from src.python.web_app import create_app


class FakeController:
    async def statuses(self, definitions):
        return []


def _write_discovery(path: Path) -> None:
    path.write_text(json.dumps({"switches": []}), encoding="utf-8")


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "tplink.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_humidifier_config(config)
    return TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController())
    )


def test_humidifiers_endpoint_without_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOVEE_API_KEY", raising=False)
    client = _client(tmp_path)

    payload = client.get("/api/humidifiers").json()

    card = payload["humidifiers"][0]
    assert card["status"] == "needs_api_key"
    assert card["controllable"] is False
    assert "GOVEE_API_KEY" in card["note"]


def test_humidifiers_endpoint_healthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    def fake_request(path, payload=None):
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": FAKE_DEVICE_LIST}
        if path == "/router/api/v1/device/state":
            return {
                "payload": {
                    "capabilities": [
                        {"instance": "online", "state": {"value": True}},
                        {"instance": "powerSwitch", "state": {"value": 1}},
                        {"instance": "workMode", "state": {"value": {"workMode": 1, "modeValue": 2}}},
                    ]
                }
            }
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    client = _client(tmp_path)

    card = client.get("/api/humidifiers").json()["humidifiers"][0]

    assert card["status"] == "configured"
    assert card["controllable"] is True
    assert card["is_on"] is True
    assert card["mist_level"] == 2
    assert card["capabilities"] == {"power": True, "mist_level": {"min": 1, "max": 3}}


def test_humidifiers_endpoint_serves_cache_when_cloud_unreachable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    # With the cloud down no device entry can be matched, so the runtime-state
    # key falls back to the humidifier name (see _humidifier_runtime_key).
    web_app.HUMIDIFIER_RUNTIME_STATE["Bedroom Humidifier"] = {"is_on": True, "mist_level": 1}

    def fake_request(path, payload=None):
        raise OSError("rate limited")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    client = _client(tmp_path)

    card = client.get("/api/humidifiers").json()["humidifiers"][0]

    assert card["status"] == "cloud_unreachable"
    assert card["controllable"] is False
    assert card["is_on"] is True  # served from cache
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: new tests FAIL — 404 on `/api/humidifiers`

- [ ] **Step 3: Implement card builders and endpoint**

In `src/python/web_app.py`, after `_govee_cloud_control`:

```python
def _humidifier_id(humidifier: HumidifierDefinition) -> str:
    return quote(humidifier.name, safe="")


def _find_humidifier(
    humidifiers: list[HumidifierDefinition], humidifier_id: str
) -> HumidifierDefinition:
    for humidifier in humidifiers:
        if humidifier.name == humidifier_id or _humidifier_id(humidifier) == humidifier_id:
            return humidifier
    raise HTTPException(status_code=404, detail=f"Humidifier not found: {humidifier_id}")


def _humidifier_runtime_key(humidifier: HumidifierDefinition, entry: dict[str, Any] | None) -> str:
    if entry and entry.get("device"):
        return str(entry["device"])
    return humidifier.name


def _humidifier_card(humidifier: HumidifierDefinition) -> dict[str, Any]:
    entry: dict[str, Any] | None = None
    mist_range: tuple[int, int] | None = None
    if humidifier.provider != "govee_cloud":
        status, note, controllable = (
            "unsupported",
            "Unsupported humidifier provider.",
            False,
        )
    elif not _govee_api_key():
        status = "needs_api_key"
        note = (
            "Set the GOVEE_API_KEY environment variable on the Pi. Apply for a key in "
            "the Govee app: Settings -> Apply for API Key."
        )
        controllable = False
    else:
        try:
            devices = _govee_cloud_devices()
        except Exception:
            devices = None
        if devices is None:
            status, note, controllable = (
                "cloud_unreachable",
                "Govee cloud temporarily unavailable; showing last known state.",
                False,
            )
        else:
            entry = _match_govee_cloud_device(humidifier, devices)
            if entry is None:
                status = "not_found"
                note = (
                    "No matching device on the Govee account. Set device_id in "
                    "configs/devices.local.yaml to the API device id."
                )
                controllable = False
            else:
                status, note, controllable = "configured", "Govee cloud control.", True
                mist_range = _govee_mist_range(entry)
                state = _govee_humidifier_state(entry)
                if state is not None:
                    HUMIDIFIER_RUNTIME_STATE[_humidifier_runtime_key(humidifier, entry)] = state
    runtime = HUMIDIFIER_RUNTIME_STATE.get(_humidifier_runtime_key(humidifier, entry), {})
    return {
        "id": humidifier.name,
        "name": humidifier.name,
        "provider": humidifier.provider,
        "model": humidifier.model,
        "room": humidifier.room,
        "status": status,
        "note": note,
        "controllable": controllable,
        "is_on": runtime.get("is_on"),
        "mist_level": runtime.get("mist_level"),
        "humidity": runtime.get("humidity"),
        "online": runtime.get("online"),
        "capabilities": {
            "power": controllable,
            "mist_level": {"min": mist_range[0], "max": mist_range[1]} if mist_range else None,
        },
    }


def _humidifier_cards(path: Path) -> dict[str, Any]:
    return {"humidifiers": [_humidifier_card(h) for h in _load_humidifiers(path)]}
```

In `create_app`, after the ambient-lights routes (after the `update_ambient_light` handler, ~line 468):

```python
    @app.get("/api/humidifiers")
    async def humidifiers() -> dict[str, Any]:
        return await asyncio.to_thread(_humidifier_cards, app.state.config_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/web_app.py tests/python/test_humidifiers.py
git commit -m "feat: add humidifier cards and GET /api/humidifiers endpoint"
```

---

### Task 5: Command endpoint POST /api/humidifiers/{id}/commands/{command}

**Files:**
- Modify: `src/python/web_app.py` (payload function after `_humidifier_cards`; route after the `humidifiers` route)
- Test: `tests/python/test_humidifiers.py`

**Interfaces:**
- Consumes: Tasks 2–4 symbols.
- Produces:
  - `_humidifier_command_payload(config_path: Path, humidifier_id: str, command: str, body: dict) -> dict`
  - `POST /api/humidifiers/{humidifier_id}/commands/{command}` — commands `on`, `off`, `mist_level` (JSON body `{"level": N}`); errors: 404 unknown id / no cloud match, 501 non-govee_cloud provider, 503 missing key or cloud failure, 400 unknown command or missing level.

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_humidifiers.py`:

```python
def _healthy_cloud(monkeypatch, control_log):
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    def fake_request(path, payload=None):
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": FAKE_DEVICE_LIST}
        if path == "/router/api/v1/device/control":
            control_log.append(payload["payload"]["capability"])
            return {"code": 200}
        if path == "/router/api/v1/device/state":
            return {"payload": {"capabilities": []}}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)


def test_humidifier_on_off_commands(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/on").status_code == 200
    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/off").status_code == 200

    assert control_log == [
        {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "value": 1},
        {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "value": 0},
    ]


def test_humidifier_mist_level_clamped_to_reported_range(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    response = client.post(
        "/api/humidifiers/Bedroom%20Humidifier/commands/mist_level", json={"level": 99}
    )

    assert response.status_code == 200
    # FAKE_DEVICE_LIST reports gearMode range 1-3; workMode value 1 is gearMode.
    assert control_log == [
        {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": {"workMode": 1, "modeValue": 3},
        }
    ]


def test_humidifier_command_error_paths(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    assert client.post("/api/humidifiers/Nope/commands/on").status_code == 404
    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/dance").status_code == 400
    assert (
        client.post("/api/humidifiers/Bedroom%20Humidifier/commands/mist_level", json={}).status_code
        == 400
    )

    monkeypatch.delenv("GOVEE_API_KEY")
    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/on").status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: new tests FAIL — 404/405 on the commands route

- [ ] **Step 3: Implement the command payload + route**

In `src/python/web_app.py`, after `_humidifier_cards`:

```python
def _humidifier_command_payload(
    config_path: Path, humidifier_id: str, command: str, body: dict[str, Any]
) -> dict[str, Any]:
    humidifier = _find_humidifier(_load_humidifiers(config_path), humidifier_id)
    if humidifier.provider != "govee_cloud":
        raise HTTPException(status_code=501, detail="Only govee_cloud humidifiers are controllable.")
    if not _govee_api_key():
        raise HTTPException(status_code=503, detail="GOVEE_API_KEY is not configured")
    try:
        devices = _govee_cloud_devices()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Govee cloud unavailable: {error}")
    entry = _match_govee_cloud_device(humidifier, devices)
    if entry is None:
        raise HTTPException(
            status_code=404, detail="No matching device on the Govee account; set device_id."
        )
    runtime_key = _humidifier_runtime_key(humidifier, entry)
    if command in ("on", "off"):
        value = 1 if command == "on" else 0
        capability: dict[str, Any] = {
            "type": "devices.capabilities.on_off",
            "instance": "powerSwitch",
            "value": value,
        }
        state_update = {"is_on": command == "on"}
    elif command == "mist_level":
        raw_level = body.get("level")
        if raw_level is None:
            raise HTTPException(status_code=400, detail="mist_level requires a JSON body with 'level'.")
        low, high = _govee_mist_range(entry)
        level = max(low, min(high, int(raw_level)))
        capability = {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": {"workMode": _govee_gear_mode_value(entry), "modeValue": level},
        }
        state_update = {"mist_level": level}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported humidifier command: {command}")
    try:
        _govee_cloud_control(entry, capability["type"], capability["instance"], capability["value"])
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Govee command failed: {error}")
    cached = dict(HUMIDIFIER_RUNTIME_STATE.get(runtime_key, {}))
    cached.update(state_update)
    HUMIDIFIER_RUNTIME_STATE[runtime_key] = cached
    return {"ok": True, "command": command, **state_update}
```

In `create_app`, after the `humidifiers` route:

```python
    @app.post("/api/humidifiers/{humidifier_id}/commands/{command}")
    async def humidifier_command(
        humidifier_id: str, command: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            _humidifier_command_payload, app.state.config_path, humidifier_id, command, body or {}
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest`
Expected: all PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/python/web_app.py tests/python/test_humidifiers.py
git commit -m "feat: add humidifier command endpoint (on/off/mist level)"
```

---

### Task 6: Humidifiers dashboard view (nav, panel, cards, handlers)

**Files:**
- Modify: `src/python/web_static/index.html` (nav item after the `ambient` item ~line 65; view panel after the ambient panel ~line 229)
- Modify: `src/python/web_static/app.js` (loader/renderer near `loadAmbientLights` ~line 819; click/slider handlers after the ambient handlers ~line 4710; startup call next to `loadAmbientLights()` in the init IIFE ~line 4552)
- Test: `tests/python/test_humidifiers.py`

**Interfaces:**
- Consumes: `GET /api/humidifiers` and `POST /api/humidifiers/{id}/commands/{command}` (Tasks 4–5); existing `requestJson`, `escapeHtml`, `logActivity`, `apiStatus` globals in app.js; existing `.ambient-*` CSS classes (reused — no styles.css changes).
- Produces: nav view `data-view="humidifier"`, grid `#humidifierGrid`, badge `#humidifierCount`, functions `loadHumidifiers()` / `renderHumidifiers(payload)` / `humidifierCard(humidifier)`.

- [ ] **Step 1: Write the failing static-content tests**

Append to `tests/python/test_humidifiers.py`:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_humidifier_view_exists_in_sidebar_and_panels() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view="humidifier"' in html
    assert 'id="humidifierCount"' in html
    assert 'data-view-panel="humidifier"' in html
    assert 'id="humidifierGrid"' in html


def test_app_js_wires_humidifier_api() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    assert '"/api/humidifiers"' in js
    assert "data-humidifier-command" in js
    assert "data-humidifier-mist" in js
    assert "loadHumidifiers()" in js
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_humidifiers.py -v`
Expected: the two new static-content tests FAIL; all earlier tests still PASS

- [ ] **Step 3: Add the nav item and view panel**

In `src/python/web_static/index.html`, after the `ambient` nav `<li>` (before the `tuya` one):

```html
      <li class="room-item" data-view="humidifier">
        <span class="room-icon"><i class="ti ti-droplet"></i></span>
        Humidifiers
        <span class="room-badge" id="humidifierCount">–</span>
      </li>
```

After the ambient view panel `</div>` (before the Tuya panel comment):

```html
    <!-- ── HUMIDIFIERS VIEW ── -->
    <div class="view-panel" data-view-panel="humidifier">
      <div class="section-header">
        <span class="section-title">Humidifiers</span>
        <span class="section-meta">Govee · Cloud API</span>
      </div>
      <div class="ambient-grid" id="humidifierGrid">
        <div class="loading-msg"><i class="ti ti-loader-2 spin"></i> Loading…</div>
      </div>
    </div>
```

- [ ] **Step 4: Add loader, renderer, and card template to app.js**

In `src/python/web_static/app.js`, directly after the `renderAmbientLights`/`ambientLightCard` block:

```javascript
/* ── Humidifiers (Govee cloud) ── */
async function loadHumidifiers() {
  const payload = await requestJson("/api/humidifiers");
  renderHumidifiers(payload);
}

function renderHumidifiers(payload) {
  const humidifiers = payload.humidifiers || [];
  const grid = document.querySelector("#humidifierGrid");
  const badge = document.querySelector("#humidifierCount");
  if (badge) badge.textContent = String(humidifiers.length);
  if (!grid) return;
  if (humidifiers.length === 0) {
    grid.innerHTML = '<div class="empty">No humidifiers configured yet. Add a humidifiers: section to configs/devices.local.yaml.</div>';
    return;
  }
  grid.innerHTML = humidifiers.map(humidifierCard).join("");
}

function humidifierCard(humidifier) {
  const isOn = humidifier.is_on === true;
  const statusClass = humidifier.status === "configured" ? (isOn ? "on" : "") : "setup";
  const onActive = isOn ? " active" : "";
  const offActive = humidifier.is_on === false ? " active" : "";
  const mist = humidifier.capabilities && humidifier.capabilities.mist_level;
  const level = humidifier.mist_level ?? (mist ? mist.min : 1);
  const actions = humidifier.controllable
    ? '<div class="ambient-actions"><button class="command primary' + onActive + '" data-humidifier-command="on" data-humidifier-id="' + escapeHtml(humidifier.id) + '">On</button><button class="command' + offActive + '" data-humidifier-command="off" data-humidifier-id="' + escapeHtml(humidifier.id) + '">Off</button></div>'
    : '<div class="ambient-actions"><button class="command" disabled>Setup needed</button></div>';
  const mistRow = humidifier.controllable && mist
    ? '<div class="ambient-control-row"><i class="ti ti-droplet"></i><input type="range" min="' + mist.min + '" max="' + mist.max + '" value="' + level + '" data-humidifier-mist data-humidifier-id="' + escapeHtml(humidifier.id) + '"><span>' + level + "/" + mist.max + '</span></div>'
    : "";
  const humidityRow = humidifier.humidity != null
    ? '<div class="ambient-control-row"><i class="ti ti-cloud-rain"></i><span>Humidity ' + escapeHtml(String(humidifier.humidity)) + '%</span></div>'
    : "";
  return [
    '<article class="ambient-card ' + statusClass + '">',
    '<div class="ambient-glow"></div>',
    '<div class="ambient-top">',
    '<div class="ambient-name-row"><h3>' + escapeHtml(humidifier.name) + "</h3></div>",
    '<span class="ambient-status">' + escapeHtml(humidifier.status === "configured" ? (isOn ? "On" : humidifier.is_on === false ? "Off" : "Ready") : humidifier.note) + "</span>",
    "</div>",
    '<p class="ambient-meta">' + escapeHtml([humidifier.model, humidifier.room].filter(Boolean).join(" · ")) + "</p>",
    actions,
    mistRow,
    humidityRow,
    "</article>",
  ].join("");
}
```

- [ ] **Step 5: Add the command and slider handlers**

In `src/python/web_static/app.js`, after the ambient rename handler block (after ~line 4710):

```javascript
/* ── Humidifier actions ── */
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-humidifier-command]");
  if (!btn) return;
  const humidifierId = btn.dataset.humidifierId;
  const command = btn.dataset.humidifierCommand;
  const card = btn.closest(".ambient-card");
  const buttons = card ? [...card.querySelectorAll("button[data-humidifier-command]")] : [btn];
  const status = card?.querySelector(".ambient-status");
  buttons.forEach((item) => { item.disabled = true; item.classList.remove("active"); });
  btn.classList.add("active");
  if (status) status.textContent = command === "on" ? "Turning on..." : "Turning off...";
  apiStatus.textContent = "Sending";
  try {
    await requestJson("/api/humidifiers/" + encodeURIComponent(humidifierId) + "/commands/" + command, { method: "POST" });
    await loadHumidifiers();
    apiStatus.textContent = "Online";
    logActivity("Humidifier turned " + command);
  } catch (error) {
    buttons.forEach((item) => { item.disabled = false; });
    if (status) status.textContent = "Command failed";
    apiStatus.textContent = "Error";
    logActivity("Humidifier command unavailable", "warn");
    console.error(error);
  }
});

document.addEventListener("change", async (event) => {
  const slider = event.target.closest("input[data-humidifier-mist]");
  if (!slider) return;
  const humidifierId = slider.dataset.humidifierId;
  const level = Number(slider.value);
  apiStatus.textContent = "Sending";
  try {
    await requestJson("/api/humidifiers/" + encodeURIComponent(humidifierId) + "/commands/mist_level", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level }),
    });
    await loadHumidifiers();
    apiStatus.textContent = "Online";
    logActivity("Humidifier mist level → " + level);
  } catch (error) {
    apiStatus.textContent = "Error";
    logActivity("Humidifier command unavailable", "warn");
    console.error(error);
  }
});
```

- [ ] **Step 6: Call loadHumidifiers at startup**

In the init IIFE (~line 4552), directly after `loadAmbientLights().catch((error) => console.error(error));` add:

```javascript
  loadHumidifiers().catch((error) => console.error(error));
```

Then grep for the other `loadAmbientLights()` call sites (`grep -n "loadAmbientLights()" src/python/web_static/app.js`, ~lines 4077/4626/4693) and add the same `loadHumidifiers()` call beside each one that is part of a periodic/refresh path (same style as the neighboring call: `.catch(...)` where ambient uses it, `await` where ambient is awaited).

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_humidifiers.py tests/python/test_dashboard_layout.py -v`
Expected: all PASS (layout tests confirm the Views list order is intact — `status` stays the last view item because the humidifier entry is inserted mid-list)

- [ ] **Step 8: Run the full suite**

Run: `python3 -m pytest`
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add src/python/web_static/index.html src/python/web_static/app.js tests/python/test_humidifiers.py
git commit -m "feat: add Humidifiers dashboard view wired to Govee cloud API"
```

---

### Task 7: Deploy and verify on the Pi

**Files:**
- None modified — deployment + smoke check only.

**Interfaces:**
- Consumes: `scripts/deploy-dashboard.sh` (existing deploy path; the user's standing preference is to run it whenever dashboard files change).

- [ ] **Step 1: Deploy the dashboard**

Run: `./scripts/deploy-dashboard.sh`
Expected: script completes without error.

- [ ] **Step 2: Smoke-check the new endpoint on the Pi**

Run: `curl -s http://<pi-host>:8000/api/humidifiers` (use the Pi address from `scripts/connect-pi.sh`; if auth is enabled, check via the browser dashboard instead)
Expected: JSON with a `humidifiers` list. Before the user adds real config + `GOVEE_API_KEY` to the Pi, an empty list `{"humidifiers": []}` is the correct result.

- [ ] **Step 3: Report remaining user actions**

Tell the user what only they can do:
1. Add the real camera entry (actual IP) to `configs/devices.local.yaml` on the Pi, with `TAPO_CAMERA_USERNAME`/`TAPO_CAMERA_PASSWORD` set in the Pi's environment.
2. Apply for a Govee API key in the Govee app (Settings → Apply for API Key) and set `GOVEE_API_KEY` in the Pi's environment (e.g. the systemd unit's `.env`).
3. Add the real `humidifiers:` entry to `configs/devices.local.yaml` (copy from `devices.example.yaml`; `device_id: replace_me` is fine for a single H7140).
4. Restart the dashboard service, then check the Humidifiers view.
