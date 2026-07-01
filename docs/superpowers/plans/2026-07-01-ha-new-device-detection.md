# Home Assistant New-Device Detection & Auto-Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect newly-appeared Home Assistant `light`/`switch` entities, pop up a confirmation notification on the dashboard, and — once confirmed — place the device into the correct view (Lights or Plugs), removing it from the Sensors/Tuya tab where it currently lands by accident.

**Architecture:** A backend JSON registry (`home_assistant_known_entities.json`, seeded on first run) tracks which HA `light`/`switch` entity_ids have been handled. `/api/home-assistant/entities` flags unhandled ones as `is_new`. Two new endpoints let the frontend confirm (writes a `home_assistant_devices:` entry to `configs/devices.local.yaml`) or ignore (registry only) a device. Confirmed devices are merged into `/api/devices` (feeding Lights/Plugs) and excluded from the existing Tuya/Home-Assistant merge that feeds the Sensors tab. The frontend reuses its existing notification-banner system and Matter-modal pattern for the popup/confirm UI.

**Tech Stack:** FastAPI + Pydantic (backend), vanilla JS (frontend), pytest + FastAPI TestClient (tests).

## Global Constraints

- Only `light` and `switch` domain HA entities are in scope — see spec §Overview. All other domains keep their exact current behavior; do not touch code paths for `climate`, `sensor`, `binary_sensor`, `cover`, `fan`, `lock`.
- `configs/devices.local.yaml` is git-ignored; `configs/devices.example.yaml` documents its schema and IS committed.
- Persist the known-entity registry as `home_assistant_known_entities.json` at `PROJECT_ROOT` (same convention as `tplink_switches.json`), not in `devices.local.yaml`.
- Follow existing code conventions exactly: `yaml.safe_load`/`yaml.dump` for config I/O (no ruamel), module-level `DEFAULT_*_PATH` constants patched via `unittest.mock.patch` in tests, blocking HA HTTP calls wrapped in `asyncio.to_thread` when invoked from async route handlers.
- Reuse existing UI primitives: the notif-banner system (`pushNotification`/`renderNotifications`/`respondToNotification`) and the `.modal-overlay`/`.modal-card` CSS classes already used by `#matterModal` — no new CSS framework/classes needed.

---

### Task 1: Known-entity registry persistence

**Files:**
- Modify: `src/python/web_app.py` (add near line 36-37, alongside `DEFAULT_DISCOVERY_PATH`/`DEFAULT_CONFIG_PATH`; add functions near `_home_assistant_entity_domain` at line 1825)
- Test: Create `tests/python/test_home_assistant_new_devices.py`

**Interfaces:**
- Produces: `DEFAULT_HA_KNOWN_ENTITIES_PATH: Path`, `_load_known_ha_entities(path: Path) -> set[str]`, `_save_known_ha_entities(path: Path, entity_ids: set[str]) -> None`, `_seed_known_ha_entities_if_missing(path: Path, states: list[dict[str, Any]]) -> None`, `_mark_ha_entity_known(path: Path, entity_id: str) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/python/test_home_assistant_new_devices.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from src.python.web_app import (
    _load_known_ha_entities,
    _save_known_ha_entities,
    _seed_known_ha_entities_if_missing,
    _mark_ha_entity_known,
)


def test_load_known_ha_entities_missing_file_returns_empty_set(tmp_path: Path) -> None:
    assert _load_known_ha_entities(tmp_path / "missing.json") == set()


def test_save_and_load_known_ha_entities_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    _save_known_ha_entities(path, {"light.a", "switch.b"})
    assert _load_known_ha_entities(path) == {"light.a", "switch.b"}


def test_load_known_ha_entities_survives_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    path.write_text("not json", encoding="utf-8")
    assert _load_known_ha_entities(path) == set()


def test_seed_known_ha_entities_only_seeds_light_and_switch_domains(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    states = [
        {"entity_id": "light.kitchen", "state": "on"},
        {"entity_id": "switch.north_bedroom_light_switch", "state": "off"},
        {"entity_id": "sensor.hallway_temp", "state": "21"},
        {"entity_id": "climate.living_room", "state": "heat"},
    ]
    _seed_known_ha_entities_if_missing(path, states)
    assert _load_known_ha_entities(path) == {"light.kitchen", "switch.north_bedroom_light_switch"}


def test_seed_known_ha_entities_skips_if_file_already_exists(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    _save_known_ha_entities(path, {"light.existing"})
    _seed_known_ha_entities_if_missing(path, [{"entity_id": "light.new_one", "state": "on"}])
    assert _load_known_ha_entities(path) == {"light.existing"}


def test_mark_ha_entity_known_adds_to_existing_set(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    _save_known_ha_entities(path, {"light.a"})
    _mark_ha_entity_known(path, "switch.b")
    assert _load_known_ha_entities(path) == {"light.a", "switch.b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: FAIL with `ImportError: cannot import name '_load_known_ha_entities'`

- [ ] **Step 3: Implement**

In `src/python/web_app.py`, add the constant next to the other `DEFAULT_*_PATH` constants (after line 37, `DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "devices.local.yaml"`):

```python
DEFAULT_HA_KNOWN_ENTITIES_PATH = PROJECT_ROOT / "home_assistant_known_entities.json"
```

Add the following functions immediately after `_home_assistant_entity_domain` (currently ending at line 1828):

```python
def _load_known_ha_entities(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return set(payload.get("known_entity_ids") or [])


def _save_known_ha_entities(path: Path, entity_ids: set[str]) -> None:
    path.write_text(
        json.dumps({"known_entity_ids": sorted(entity_ids)}, indent=2),
        encoding="utf-8",
    )


def _seed_known_ha_entities_if_missing(path: Path, states: list[dict[str, Any]]) -> None:
    if path.exists():
        return
    seed_ids = {
        str(entity.get("entity_id"))
        for entity in states
        if _home_assistant_entity_domain(entity.get("entity_id")) in {"light", "switch"}
    }
    _save_known_ha_entities(path, seed_ids)


def _mark_ha_entity_known(path: Path, entity_id: str) -> None:
    known = _load_known_ha_entities(path)
    known.add(entity_id)
    _save_known_ha_entities(path, known)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/python/web_app.py tests/python/test_home_assistant_new_devices.py
git commit -m "feat: add HA known-entity registry persistence"
```

---

### Task 2: `is_new` flag on Home Assistant entities

**Files:**
- Modify: `src/python/web_app.py` (add function near `_load_known_ha_entities`; modify `_home_assistant_payload` at line 1602-1632)
- Test: `tests/python/test_home_assistant_new_devices.py`

**Interfaces:**
- Consumes: `_load_known_ha_entities`, `_seed_known_ha_entities_if_missing`, `DEFAULT_HA_KNOWN_ENTITIES_PATH` (Task 1)
- Produces: `_mark_new_light_switch_entities(entities: list[dict[str, Any]], known_ids: set[str]) -> None` (mutates `entities` in place, adding `is_new` key)

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_home_assistant_new_devices.py`:

```python
from src.python.web_app import _mark_new_light_switch_entities


def test_mark_new_light_switch_entities_flags_only_unknown_light_and_switch() -> None:
    entities = [
        {"entity_id": "light.kitchen", "domain": "light"},
        {"entity_id": "switch.north_bedroom_light_switch", "domain": "switch"},
        {"entity_id": "sensor.hallway_temp", "domain": "sensor"},
    ]
    known_ids = {"light.kitchen"}

    _mark_new_light_switch_entities(entities, known_ids)

    assert entities[0]["is_new"] is False
    assert entities[1]["is_new"] is True
    assert "is_new" not in entities[2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py::test_mark_new_light_switch_entities_flags_only_unknown_light_and_switch -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement**

Add next to the other new functions in `src/python/web_app.py`:

```python
def _mark_new_light_switch_entities(entities: list[dict[str, Any]], known_ids: set[str]) -> None:
    for entity in entities:
        if entity.get("domain") in {"light", "switch"}:
            entity["is_new"] = entity.get("entity_id") not in known_ids
```

Modify `_home_assistant_payload` (currently lines 1602-1632) — insert before the `return` statement, after `entities.sort(...)`:

```python
def _home_assistant_payload(path: Path) -> dict[str, Any]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        return {
            "status": "needs_auth",
            "message": f"Set {config.token_env} in the dashboard environment.",
            "entities": [],
        }

    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Home Assistant API error: {exc}",
            "entities": [],
        }

    entities = [
        _home_assistant_entity_card(entity)
        for entity in states
        if _home_assistant_entity_domain(entity.get("entity_id")) in config.include_domains
        and not _is_ignored_home_assistant_entity(entity)
    ]
    entities.sort(key=lambda item: (item["domain"], item["name"].lower()))

    _seed_known_ha_entities_if_missing(DEFAULT_HA_KNOWN_ENTITIES_PATH, states)
    known_ids = _load_known_ha_entities(DEFAULT_HA_KNOWN_ENTITIES_PATH)
    _mark_new_light_switch_entities(entities, known_ids)

    return {
        "status": "ok",
        "source": "Home Assistant",
        "entities": entities,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 7 passed

- [ ] **Step 5: Write an end-to-end test through the API**

Append to `tests/python/test_home_assistant_new_devices.py`:

```python
from fastapi.testclient import TestClient

from src.python.web_app import create_app


class _FakeController:
    async def status(self, switch):
        raise AssertionError("not used in this test")


def _write_ha_config(path: Path) -> None:
    path.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "  include_domains: [light, switch]\n"
    )


def test_entities_endpoint_flags_is_new_for_unseen_light_switch(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    _write_ha_config(config)
    known_path = tmp_path / "known.json"
    monkeypatch.setattr("src.python.web_app.DEFAULT_HA_KNOWN_ENTITIES_PATH", known_path)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {"entity_id": "light.kitchen", "state": "on", "attributes": {"friendly_name": "Kitchen"}},
            {
                "entity_id": "switch.north_bedroom_light_switch",
                "state": "off",
                "attributes": {"friendly_name": "North bedroom light switch"},
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))

    first = client.get("/api/home-assistant/entities").json()
    assert {e["entity_id"]: e["is_new"] for e in first["entities"]} == {
        "light.kitchen": False,
        "switch.north_bedroom_light_switch": False,
    }

    def fake_home_assistant_get_with_new_device(home_assistant_config, token, path):
        return fake_home_assistant_get(home_assistant_config, token, path) + [
            {"entity_id": "switch.garage_plug", "state": "on", "attributes": {"friendly_name": "Garage Plug"}},
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get_with_new_device)
    second = client.get("/api/home-assistant/entities").json()
    flags = {e["entity_id"]: e["is_new"] for e in second["entities"]}
    assert flags["switch.garage_plug"] is True
    assert flags["light.kitchen"] is False
```

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 8 passed (this confirms seeding-on-first-call behavior: the first request seeds the registry so both starting entities report `is_new: False`, and only the entity added afterward reports `True`)

- [ ] **Step 6: Commit**

```bash
git add src/python/web_app.py tests/python/test_home_assistant_new_devices.py
git commit -m "feat: flag newly-seen HA light/switch entities as is_new"
```

---

### Task 3: Type mapping, config read/write, and confirm/ignore endpoints

**Files:**
- Modify: `src/python/web_app.py` (add near `_MatterCommissionBody` at line 52-55; add near `_write_matter_device_to_config` at line 2433; add routes near line 337-339)
- Modify: `configs/devices.example.yaml` (document schema)
- Test: `tests/python/test_home_assistant_new_devices.py`

**Interfaces:**
- Consumes: `DEFAULT_CONFIG_PATH`, `DEFAULT_HA_KNOWN_ENTITIES_PATH`, `_mark_ha_entity_known` (Task 1)
- Produces: `_ha_light_switch_dashboard_category(device_class: str | None) -> str`, `_load_home_assistant_devices(path: Path) -> list[dict[str, Any]]`, `_write_home_assistant_device_to_config(entity_id: str, name: str, room: str | None, category: str) -> None`, routes `POST /api/home-assistant/devices/{entity_id}/confirm`, `POST /api/home-assistant/devices/{entity_id}/ignore`

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_home_assistant_new_devices.py`:

```python
import yaml
from unittest.mock import patch

from src.python.web_app import (
    _ha_light_switch_dashboard_category,
    _load_home_assistant_devices,
    _write_home_assistant_device_to_config,
)


def test_ha_light_switch_dashboard_category_outlet_is_plug() -> None:
    assert _ha_light_switch_dashboard_category("outlet") == "smart_plug"


def test_ha_light_switch_dashboard_category_defaults_to_light() -> None:
    assert _ha_light_switch_dashboard_category(None) == "light_switch"
    assert _ha_light_switch_dashboard_category("switch") == "light_switch"


def test_load_home_assistant_devices_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_home_assistant_devices(tmp_path / "missing.yaml") == []


def test_write_home_assistant_device_creates_section(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        _write_home_assistant_device_to_config(
            "switch.north_bedroom_light_switch", "North bedroom light switch", "North Bedroom", "light_switch"
        )
    data = yaml.safe_load(config.read_text())
    assert data["home_assistant_devices"][0] == {
        "entity_id": "switch.north_bedroom_light_switch",
        "name": "North bedroom light switch",
        "room": "North Bedroom",
        "category": "light_switch",
    }


def test_write_home_assistant_device_overwrites_existing_entry(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant_devices:\n"
        "- {entity_id: switch.a, name: Old, category: light_switch}\n"
    )
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        _write_home_assistant_device_to_config("switch.a", "New Name", None, "smart_plug")
    data = yaml.safe_load(config.read_text())
    assert len(data["home_assistant_devices"]) == 1
    assert data["home_assistant_devices"][0]["name"] == "New Name"
    assert data["home_assistant_devices"][0]["category"] == "smart_plug"
    assert "room" not in data["home_assistant_devices"][0]


def test_confirm_endpoint_writes_config_and_marks_known(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    known_path = tmp_path / "known.json"
    monkeypatch.setattr("src.python.web_app.DEFAULT_HA_KNOWN_ENTITIES_PATH", known_path)
    from src.python.web_app import create_app
    from fastapi.testclient import TestClient

    class _FakeController:
        async def status(self, switch):
            raise AssertionError("not used")

    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))
        response = client.post(
            "/api/home-assistant/devices/switch.north_bedroom_light_switch/confirm",
            json={"name": "North bedroom light switch", "room": "North Bedroom", "category": "light_switch"},
        )
        assert response.status_code == 200
        data = yaml.safe_load(config.read_text())
        assert data["home_assistant_devices"][0]["entity_id"] == "switch.north_bedroom_light_switch"

    assert "switch.north_bedroom_light_switch" in _load_known_ha_entities(known_path)


def test_ignore_endpoint_marks_known_without_touching_config(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    known_path = tmp_path / "known.json"
    monkeypatch.setattr("src.python.web_app.DEFAULT_HA_KNOWN_ENTITIES_PATH", known_path)
    from src.python.web_app import create_app
    from fastapi.testclient import TestClient

    class _FakeController:
        async def status(self, switch):
            raise AssertionError("not used")

    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))
    response = client.post("/api/home-assistant/devices/switch.unwanted/ignore")

    assert response.status_code == 200
    assert not config.exists()
    assert "switch.unwanted" in _load_known_ha_entities(known_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: FAIL with `ImportError` for the new names

- [ ] **Step 3: Implement backend functions**

Add next to `_MatterCommissionBody` (after line 55) in `src/python/web_app.py`:

```python
class _HomeAssistantDeviceConfirmBody(BaseModel):
    name: str
    room: str | None = None
    category: str
```

Add next to `_write_matter_device_to_config`/`_remove_matter_device_from_config` (after line 2455):

```python
def _ha_light_switch_dashboard_category(device_class: str | None) -> str:
    if str(device_class or "").lower() == "outlet":
        return "smart_plug"
    return "light_switch"


def _load_home_assistant_devices(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return cfg.get("home_assistant_devices") or []


def _write_home_assistant_device_to_config(entity_id: str, name: str, room: str | None, category: str) -> None:
    cfg: dict = {}
    if DEFAULT_CONFIG_PATH.exists():
        cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text()) or {}
    devices: list[dict] = cfg.setdefault("home_assistant_devices", [])
    devices[:] = [d for d in devices if d.get("entity_id") != entity_id]
    entry: dict[str, Any] = {"entity_id": entity_id, "name": name, "category": category}
    if room:
        entry["room"] = room
    devices.append(entry)
    DEFAULT_CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False))
```

Add the two routes in `create_app`, next to the existing Home Assistant routes (after line 339, `home_assistant_command`):

```python
    @app.post("/api/home-assistant/devices/{entity_id}/confirm")
    async def home_assistant_device_confirm(
        entity_id: str, body: _HomeAssistantDeviceConfirmBody
    ) -> dict[str, Any]:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        room = (body.room or "").strip() or None
        await asyncio.to_thread(
            _write_home_assistant_device_to_config, entity_id, name, room, body.category
        )
        await asyncio.to_thread(_mark_ha_entity_known, DEFAULT_HA_KNOWN_ENTITIES_PATH, entity_id)
        return {"status": "ok"}

    @app.post("/api/home-assistant/devices/{entity_id}/ignore")
    async def home_assistant_device_ignore(entity_id: str) -> dict[str, Any]:
        await asyncio.to_thread(_mark_ha_entity_known, DEFAULT_HA_KNOWN_ENTITIES_PATH, entity_id)
        return {"status": "ok"}
```

- [ ] **Step 4: Document the config schema**

In `configs/devices.example.yaml`, add after the `matter:` section (after line 161):

```yaml

home_assistant_devices:
  # Written automatically when you confirm a new-device popup on the dashboard.
  # entity_id must match a Home Assistant light/switch entity_id.
  # category is either light_switch (Lights view) or smart_plug (Plugs view).
  # - entity_id: switch.north_bedroom_light_switch
  #   name: North bedroom light switch
  #   room: North Bedroom
  #   category: light_switch
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 15 passed

- [ ] **Step 6: Commit**

```bash
git add src/python/web_app.py configs/devices.example.yaml tests/python/test_home_assistant_new_devices.py
git commit -m "feat: add HA device type mapping and confirm/ignore endpoints"
```

---

### Task 4: Merge confirmed devices into Lights/Plugs view

**Files:**
- Modify: `src/python/web_app.py` (`_device_cards` at line 481-511)
- Test: `tests/python/test_home_assistant_new_devices.py`

**Interfaces:**
- Consumes: `_load_home_assistant_devices`, `_load_home_assistant_config`, `_home_assistant_get` (Task 3 / existing)
- Produces: `_home_assistant_device_cards(path: Path) -> list[dict[str, Any]]`

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_home_assistant_new_devices.py`:

```python
from src.python.web_app import _home_assistant_device_cards


def test_home_assistant_device_cards_empty_when_no_confirmed_devices(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    assert _home_assistant_device_cards(config) == []


def test_home_assistant_device_cards_shapes_card_from_config_and_live_state(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- entity_id: switch.north_bedroom_light_switch\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n"
        "  category: light_switch\n"
    )
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [{"entity_id": "switch.north_bedroom_light_switch", "state": "on", "attributes": {}}]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)

    cards = _home_assistant_device_cards(config)

    assert cards == [
        {
            "id": "switch.north_bedroom_light_switch",
            "name": "North bedroom light switch",
            "host": "ha:switch.north_bedroom_light_switch",
            "model": "Home Assistant",
            "type": "Home Assistant",
            "category": "light_switch",
            "is_dimmable": False,
            "room": "North Bedroom",
            "is_on": True,
            "brightness": None,
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py::test_home_assistant_device_cards_empty_when_no_confirmed_devices -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement**

Add next to `_camera_cards` (after line 539) in `src/python/web_app.py`:

```python
def _home_assistant_device_cards(path: Path) -> list[dict[str, Any]]:
    entries = _load_home_assistant_devices(path)
    if not entries:
        return []
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    states_by_id: dict[str, dict[str, Any]] = {}
    if token:
        try:
            states = _home_assistant_get(config, token, "/api/states")
            states_by_id = {str(e.get("entity_id")): e for e in states}
        except Exception:
            states_by_id = {}

    cards = []
    for entry in entries:
        entity_id = entry.get("entity_id")
        state_entity = states_by_id.get(entity_id)
        cards.append(
            {
                "id": entity_id,
                "name": entry.get("name") or entity_id,
                "host": f"ha:{entity_id}",
                "model": "Home Assistant",
                "type": "Home Assistant",
                "category": entry.get("category") or "light_switch",
                "is_dimmable": False,
                "room": entry.get("room") or "",
                "is_on": (state_entity.get("state") == "on") if state_entity else None,
                "brightness": None,
            }
        )
    return cards
```

Modify `_device_cards` (lines 481-511) to append these cards — change the `return cards` line at 511 to:

```python
    cards.extend(await asyncio.to_thread(_home_assistant_device_cards, app.state.config_path))
    return cards
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 17 passed

- [ ] **Step 5: Write an end-to-end test through `/api/devices`**

Append to `tests/python/test_home_assistant_new_devices.py`:

```python
def test_devices_endpoint_includes_confirmed_home_assistant_light_switch(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- entity_id: switch.north_bedroom_light_switch\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n"
        "  category: light_switch\n"
    )
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [{"entity_id": "switch.north_bedroom_light_switch", "state": "on", "attributes": {}}]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)

    from src.python.web_app import create_app
    from fastapi.testclient import TestClient

    class _FakeController:
        async def status(self, switch):
            raise AssertionError("no tplink switches configured")

    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))
    response = client.get("/api/devices")

    assert response.status_code == 200
    devices = response.json()["devices"]
    assert devices == [
        {
            "id": "switch.north_bedroom_light_switch",
            "name": "North bedroom light switch",
            "host": "ha:switch.north_bedroom_light_switch",
            "model": "Home Assistant",
            "type": "Home Assistant",
            "category": "light_switch",
            "is_dimmable": False,
            "room": "North Bedroom",
            "is_on": True,
            "brightness": None,
        }
    ]
```

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 18 passed

- [ ] **Step 6: Commit**

```bash
git add src/python/web_app.py tests/python/test_home_assistant_new_devices.py
git commit -m "feat: merge confirmed HA light/switch devices into Lights/Plugs view"
```

---

### Task 5: Exclude confirmed devices from the Sensors/Tuya tab

**Files:**
- Modify: `src/python/web_app.py` (`_is_tuya_home_assistant_entity` at line 826-870, `_tuya_cards_from_home_assistant` at line 791-807)
- Test: `tests/python/test_home_assistant_new_devices.py`

**Interfaces:**
- Consumes: `_load_home_assistant_devices` (Task 3)
- Produces: `_is_tuya_home_assistant_entity(entity, tplink_names=None, confirmed_entity_ids=None) -> bool` (signature extended, backward compatible)

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_home_assistant_new_devices.py`:

```python
from src.python.web_app import _is_tuya_home_assistant_entity


def test_is_tuya_home_assistant_entity_excludes_confirmed_entity_ids() -> None:
    entity = {"entity_id": "switch.north_bedroom_light_switch", "attributes": {"friendly_name": "North bedroom light switch"}}
    assert _is_tuya_home_assistant_entity(entity) is True
    assert (
        _is_tuya_home_assistant_entity(entity, confirmed_entity_ids={"switch.north_bedroom_light_switch"})
        is False
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py::test_is_tuya_home_assistant_entity_excludes_confirmed_entity_ids -v`
Expected: FAIL — `_is_tuya_home_assistant_entity() got an unexpected keyword argument 'confirmed_entity_ids'`

- [ ] **Step 3: Implement**

Modify the signature and add the exclusion check at the top of `_is_tuya_home_assistant_entity` (currently starting at line 826):

```python
def _is_tuya_home_assistant_entity(
    entity: dict[str, Any],
    tplink_names: set[str] | None = None,
    confirmed_entity_ids: set[str] | None = None,
) -> bool:
    entity_id = str(entity.get("entity_id") or "")
    if confirmed_entity_ids and entity_id in confirmed_entity_ids:
        return False
    domain = _home_assistant_entity_domain(entity_id)
    if domain not in {"light", "switch", "sensor", "binary_sensor", "cover", "fan", "lock"}:
        return False
    # ... rest of function unchanged
```

Modify `_tuya_cards_from_home_assistant` (lines 791-807) to load and pass the confirmed set:

```python
def _tuya_cards_from_home_assistant(path: Path, discovery_path: Path | None = None) -> list[dict[str, Any]]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        return []
    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception:
        return []
    tplink_names = _tplink_device_names(discovery_path)
    confirmed_entity_ids = {str(d.get("entity_id")) for d in _load_home_assistant_devices(path)}
    cards = [
        _tuya_home_assistant_card(entity)
        for entity in states
        if _is_tuya_home_assistant_entity(entity, tplink_names, confirmed_entity_ids)
    ]
    cards.sort(key=lambda item: (item["category"], item["name"].lower()))
    return cards
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_home_assistant_new_devices.py -v`
Expected: 19 passed

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

Run: `python3 -m pytest tests/python -v`
Expected: All tests pass (existing `_is_tuya_home_assistant_entity` callers in other test files must still pass since the new parameter is optional and defaults preserve current behavior)

- [ ] **Step 6: Commit**

```bash
git add src/python/web_app.py tests/python/test_home_assistant_new_devices.py
git commit -m "fix: exclude confirmed HA light/switch devices from Sensors/Tuya tab"
```

---

### Task 6: Frontend — command routing and new-device notifications

**Files:**
- Modify: `src/python/web_static/app.js` (`sendCommand` at line 2546-2556; `loadDevices` at line 2506-2542)

**Interfaces:**
- Consumes: `pushNotification(type, title, message, meta)` (existing, line 2222), `is_new` field on entities from `/api/home-assistant/entities` (Task 2)
- Produces: `notifySeenNewHomeAssistantDevices(entities)` called from `loadDevices()`

- [ ] **Step 1: Add the `ha:` branch to `sendCommand`**

Modify `sendCommand` (lines 2546-2556) in `src/python/web_static/app.js`:

```javascript
async function sendCommand(host, command, options = {}) {
  apiStatus.textContent = "Sending";
  if (host.startsWith("matter:")) {
    const nodeId = host.slice(7);
    await requestJson(`/api/matter/devices/${nodeId}/commands/${command}`, { method: "POST" });
  } else if (host.startsWith("ha:")) {
    const entityId = host.slice(3);
    await requestJson(`/api/home-assistant/entities/${encodeURIComponent(entityId)}/commands/${command}`, { method: "POST" });
  } else {
    await requestJson("/api/devices/" + host + "/commands/" + command, { method: "POST" });
  }
  logActivity("Switch " + host.split(".").pop() + " turned " + command);
  if (options.skipRefresh !== true) await loadDevices();
}
```

- [ ] **Step 2: Add new-device notification detection**

Add this function next to `notifyDoorbellEvents` (after line 2269) in `src/python/web_static/app.js`:

```javascript
function notifySeenNewHomeAssistantDevices(entities) {
  for (const entity of entities || []) {
    if (!entity.is_new) continue;
    pushNotification(
      "new_device",
      "New device found: " + entity.name,
      "Add it to your dashboard?",
      {
        entityId: entity.entity_id,
        suggestedName: entity.name,
        suggestedRoom: _guessRoomFromName(entity.name),
        suggestedCategory: entity.domain === "switch" && entity.device_class === "outlet" ? "smart_plug" : "light_switch",
      }
    );
  }
}

function _guessRoomFromName(name) {
  const firstWord = String(name || "").split(" switch")[0].split(" light")[0].trim();
  return firstWord;
}
```

- [ ] **Step 3: Call it from `loadDevices()`**

Modify `loadDevices()` (line 2521, right after `notifyDoorbellEvents(cameraData.cameras);`) in `src/python/web_static/app.js`:

```javascript
  notifyDoorbellEvents(cameraData.cameras);
  notifySeenNewHomeAssistantDevices(homeAssistantData.entities);
```

- [ ] **Step 4: Manually verify no console errors**

Use the browser preview: start the dev server (`preview_start`), open the dashboard, open browser console (`preview_console_logs`), confirm no errors on load. Since there's no real `is_new: true` entity in this dev environment (no live HA), this step only confirms `sendCommand`'s new branch and `notifySeenNewHomeAssistantDevices` don't throw when `homeAssistantData.entities` is present but has no new entities — verify via `preview_eval` calling `notifySeenNewHomeAssistantDevices([{is_new: false, entity_id: "light.x", name: "X", domain: "light"}])` and confirming no notification banner appears, then calling it with `is_new: true` and confirming one does.

- [ ] **Step 5: Commit**

```bash
git add src/python/web_static/app.js
git commit -m "feat: detect and notify on new HA light/switch entities"
```

---

### Task 7: Frontend — confirm/ignore modal

**Files:**
- Modify: `src/python/web_static/index.html` (add modal after `#matterModal`, i.e. after line 389)
- Modify: `src/python/web_static/app.js` (`respondToNotification` at line 2294-2309; notif click handlers at line 3100-3110)

**Interfaces:**
- Consumes: `notif.entityId`, `notif.suggestedName`, `notif.suggestedRoom`, `notif.suggestedCategory` (Task 6), `dismissNotification(id)`, `notifMap` (existing)
- Produces: `openNewDeviceModal(notif)`, `POST /api/home-assistant/devices/{entity_id}/confirm` and `/ignore` calls from the frontend

- [ ] **Step 1: Add the modal markup**

In `src/python/web_static/index.html`, add immediately after the `#matterModal` closing `</div>` (after line 389):

```html
<div class="modal-overlay" id="newDeviceModal" hidden aria-modal="true" role="dialog" aria-labelledby="newDeviceModalTitle">
  <div class="modal-card">
    <div class="modal-header">
      <span class="modal-title" id="newDeviceModalTitle">New Device Found</span>
      <button class="modal-close" id="closeNewDeviceModal" type="button" aria-label="Close">
        <i class="ti ti-x"></i>
      </button>
    </div>
    <label class="modal-label">
      Name
      <input class="modal-input" id="newDeviceName" type="text">
    </label>
    <label class="modal-label">
      Room
      <input class="modal-input" id="newDeviceRoom" type="text">
    </label>
    <label class="modal-label">
      Add to
      <select class="modal-input" id="newDeviceCategory">
        <option value="light_switch">Lights</option>
        <option value="smart_plug">Plugs</option>
      </select>
    </label>
    <div class="modal-actions">
      <button class="btn-secondary" id="newDeviceIgnore" type="button">Ignore</button>
      <button class="btn-primary" id="newDeviceConfirm" type="button">Add to Dashboard</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add the modal JS logic**

Add this next to the Matter modal IIFE (after `initMatterModal`'s closing, i.e. after the existing block ending near line 3310+) in `src/python/web_static/app.js`:

```javascript
/* ── NEW-DEVICE CONFIRMATION MODAL ── */
(function initNewDeviceModal() {
  const modal = document.querySelector("#newDeviceModal");
  if (!modal) return;
  let currentNotif = null;

  function openModal(notif) {
    currentNotif = notif;
    document.querySelector("#newDeviceName").value = notif.suggestedName || "";
    document.querySelector("#newDeviceRoom").value = notif.suggestedRoom || "";
    document.querySelector("#newDeviceCategory").value = notif.suggestedCategory || "light_switch";
    modal.hidden = false;
  }

  function closeModal() {
    modal.hidden = true;
    currentNotif = null;
  }

  document.querySelector("#closeNewDeviceModal")?.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  document.querySelector("#newDeviceIgnore")?.addEventListener("click", async () => {
    if (!currentNotif) return;
    const notif = currentNotif;
    closeModal();
    dismissNotification(notif.id);
    await requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/ignore`, { method: "POST" }).catch(console.error);
  });

  document.querySelector("#newDeviceConfirm")?.addEventListener("click", async () => {
    if (!currentNotif) return;
    const notif = currentNotif;
    const name = document.querySelector("#newDeviceName").value.trim();
    const room = document.querySelector("#newDeviceRoom").value.trim();
    const category = document.querySelector("#newDeviceCategory").value;
    if (!name) { document.querySelector("#newDeviceName").focus(); return; }
    closeModal();
    dismissNotification(notif.id);
    await requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, room: room || null, category }),
    }).catch(console.error);
    await loadDevices();
  });

  window.openNewDeviceModal = openModal;
})();
```

- [ ] **Step 3: Wire "Respond" and "Close" for `new_device` notifications**

Modify the notif click handler (lines 3100-3110) in `src/python/web_static/app.js`:

```javascript
document.addEventListener("click", (event) => {
  const closeBtn = event.target.closest("button[data-notif-close]");
  if (closeBtn) {
    const notif = notifMap.get(closeBtn.dataset.notifClose);
    if (notif?.type === "new_device" && notif.entityId) {
      requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/ignore`, { method: "POST" }).catch(console.error);
    }
    dismissNotification(closeBtn.dataset.notifClose);
    return;
  }

  const respondBtn = event.target.closest("button[data-notif-respond]");
  if (respondBtn) {
    const notif = notifMap.get(respondBtn.dataset.notifRespond);
    if (notif?.type === "new_device") {
      window.openNewDeviceModal(notif);
      return;
    }
    if (notif) respondToNotification(notif);
    dismissNotification(respondBtn.dataset.notifRespond);
  }
});
```

- [ ] **Step 4: Manually verify in the browser preview**

1. `preview_start` the dashboard.
2. `preview_eval`: `pushNotification("new_device", "New device found: Test Switch", "Add it to your dashboard?", {entityId: "switch.test", suggestedName: "Test Switch", suggestedRoom: "Test", suggestedCategory: "light_switch"})`
3. `preview_snapshot` — confirm a notification banner with "Respond"/"Close" buttons appears.
4. `preview_click` the "Respond" button — confirm the modal opens (`preview_snapshot`) with "Test Switch" / "Test" pre-filled.
5. `preview_network` — click "Add to Dashboard", confirm a `POST /api/home-assistant/devices/switch.test/confirm` request fires (it will 404/error since this dev environment has no real HA config — that's expected; the point is verifying the request is sent with the right body).

- [ ] **Step 5: Commit**

```bash
git add src/python/web_static/index.html src/python/web_static/app.js
git commit -m "feat: add new-device confirmation modal"
```

---

### Task 8: North bedroom light switch — one-off placement

This task is a data/config change on the live Raspberry Pi, not application code — there is nothing to unit test. It applies the same mechanism Task 3/4 built, directly, for the one device that already exists in Home Assistant today.

**Files:**
- Modify (live, on the Pi, NOT committed — `configs/devices.local.yaml` is git-ignored): add one `home_assistant_devices` entry
- Modify (live, on the Pi, NOT committed — `home_assistant_known_entities.json` is git-ignored): confirm the entity_id is present so it doesn't also pop up as "new"

- [ ] **Step 1: Find the real entity_id**

The exact HA `entity_id` for "North bedroom light switch" must be looked up from the live system — do not guess it. After deploying Tasks 1-7, query the running dashboard:

```bash
curl -s http://192.168.0.176:8000/api/home-assistant/entities | python3 -c "import json,sys; data=json.load(sys.stdin); print([e['entity_id'] for e in data['entities'] if 'north bedroom' in e['name'].lower()])"
```

Run this via `mcp__wsl-shell__run_command` (per project memory, the Pi is only reachable with WSL's SSH key — but this is a plain HTTP call to the dashboard's own port, so it should work from either shell as long as the machine can reach `192.168.0.176:8000`; use `mcp__wsl-shell__run_command` if it doesn't).

- [ ] **Step 2: Add the config entry on the Pi**

Using the `entity_id` found in Step 1, SSH into the Pi (via `mcp__wsl-shell__run_command`, matching the deploy script's access pattern) and append to `/home/smarthome/smart-home-rpi4/configs/devices.local.yaml`:

```yaml
home_assistant_devices:
- entity_id: <the real entity_id found above>
  name: North bedroom light switch
  room: North Bedroom
  category: light_switch
```

If a `home_assistant_devices:` section already exists (e.g. from testing), append to the existing list instead of creating a duplicate top-level key.

- [ ] **Step 3: Seed the known-entities file if needed**

Since the registry auto-seeds on the first `/api/home-assistant/entities` call after this feature deploys (Task 2), and that will have already happened during Step 1's curl call, this entity_id is already in `home_assistant_known_entities.json` — no separate action needed. Confirm with:

```bash
ssh smarthome@192.168.0.176 "grep -q '<the real entity_id>' /home/smarthome/smart-home-rpi4/home_assistant_known_entities.json && echo FOUND || echo MISSING"
```

If `MISSING` (e.g. the entity was added to HA after the seed already ran), add it manually:
```bash
ssh smarthome@192.168.0.176 "python3 -c \"import json,pathlib; p=pathlib.Path('/home/smarthome/smart-home-rpi4/home_assistant_known_entities.json'); d=json.loads(p.read_text()); d['known_entity_ids']=sorted(set(d['known_entity_ids'])|{'<the real entity_id>'}); p.write_text(json.dumps(d, indent=2))\""
```

- [ ] **Step 4: Restart the dashboard service and verify**

```bash
ssh smarthome@192.168.0.176 "HOME=/home/smarthome XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart smart-home-dashboard.service"
curl -s http://192.168.0.176:8000/api/devices | python3 -c "import json,sys; print([d['name'] for d in json.load(sys.stdin)['devices']])"
```

Confirm "North bedroom light switch" appears in the output, and separately confirm it's no longer in the Sensors/Tuya tab:

```bash
curl -s http://192.168.0.176:8000/api/tuya/devices | python3 -c "import json,sys; print([d['name'] for d in json.load(sys.stdin)['devices']])"
```

Confirm "North bedroom light switch" is absent from this second list.

- [ ] **Step 5: No commit needed**

Both modified files are git-ignored by design (per Global Constraints). Nothing to commit for this task.

---

## Post-Plan Verification

Run the full backend suite once more after all tasks are complete:

```bash
python3 -m pytest tests/python -v
```

Expected: all tests pass, including the new `tests/python/test_home_assistant_new_devices.py` (19 tests) and all pre-existing tests unaffected.

Then deploy per project convention (`bash scripts/deploy-dashboard.sh` via `mcp__wsl-shell__run_command`) before starting Task 8, since Task 8 depends on the new endpoints being live.
