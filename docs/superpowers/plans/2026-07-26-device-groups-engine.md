# Device Groups Engine Implementation Plan (Cycle 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the seven hardcoded device groups into data — model, API, membership resolution, and a data-driven sidebar — with zero visible change to the dashboard.

**Architecture:** A new `dashboard_device_groups.json` mirrors `dashboard_areas.json` in shape and loading discipline, seeded to reproduce today's seven groups exactly. Membership is multi-valued: groups auto-collect by device kind, and per-device `include`/`exclude` overrides adjust that. The seven `<li>` sidebar entries stay in `index.html` as the seeded baseline; a pure planner function derives the desired nav from the loaded groups and a thin DOM applier syncs the markup to it, so the static HTML remains a no-JS fallback and existing HTML assertions keep working.

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest; vanilla JS (no build step); Node for the existing JS test harness.

**Spec:** `docs/superpowers/specs/2026-07-26-device-groups-engine-design.md`

## Global Constraints

- **Zero visible change.** The dashboard must look and behave exactly as it does today when this cycle lands. Any visible difference is a defect.
- No build step: `app.js`, `index.html`, `styles.css` are served as-is. No frameworks, no bundler, no package.json, no new runtime dependencies. A JS syntax error ships straight to users — always run `node --check`.
- Icons come from the already-loaded Tabler webfont (`<i class="ti ti-*">`). Do not add icon libraries.
- **The Sensors group's id is `tuya`, not `sensors`.** `data-view="tuya"` is what the sidebar uses and what `localStorage`'s `default_view` may already hold. Renaming it silently breaks a saved startup view.
- Group ids are exactly: `lights`, `plugs`, `ambient`, `humidifier`, `environment`, `tuya`, `climate`.
- Colour allowlist: `accent`, `amber`, `cyan`, `green`, `indigo`, `orange`, `pink`, `purple`, `red`, `slate`, `teal`. Invalid → 400 on write, coerced to `slate` on load.
- Icon pattern: `^[a-z0-9-]{1,32}$`. Invalid → 400 on write, coerced to `device-desktop` on load.
- Kind allowlist: `light`, `plug`, `sensor`, `camera`, `thermostat`, `ambient`, `humidifier`, `environment`.
- `readingFilter` allowlist: `environment`, `sensors`.
- `chrome`, `readingFilter` and `builtin` are never accepted from a client — 400 if sent.
- Config/state documents must tolerate missing file, `null` document, and `null` sub-keys, per the `d11e07e` pattern.
- Python 3; `pyproject.toml` sets `pythonpath = ["."]`; run `python3 -m pytest` from the project root.
- Pre-existing unrelated failures: **4 failed, 7 errors** (matter_bridge C++ WIP in the tree, a docker-permissions test, a tplink test). Do not attempt to fix these.
- A post-commit hook auto-deploys to the Pi and bumps `BUILD_COUNT` / `build_info.json` / `index.html` cache-bust values. Never include those three files in a commit; never revert them.

## File Structure

| File | Responsibility |
|---|---|
| `src/python/web_app.py` | `DEFAULT_DEVICE_GROUPS`, loader/saver with coercion, Pydantic request models, six routes |
| `src/python/web_static/app.js` | `environment` inventory kind, pure membership resolution, pure nav planner, thin DOM applier |
| `tests/python/test_device_groups_api.py` | New — model, loader tolerance, coercion, all six endpoints |
| `tests/python/test_device_groups_baseline.py` | New — the seeded doc reproduces today's sidebar exactly |
| `tests/python/test_device_groups_logic.py` | New — Node-harness tests for resolution and the nav planner |

---

### Task 1: Group document model, defaults and loader

**Files:**
- Modify: `src/python/web_app.py` (constants near `DEFAULT_AREAS` at `:40-50`; loader/saver near `_load_areas`/`_save_areas` at `:2938-2967`)
- Test: `tests/python/test_device_groups_api.py` (create)
- Test: `tests/python/test_device_groups_baseline.py` (create)

**Interfaces:**
- Consumes: `_area_slug(name)` (`web_app.py:2931`) — reuse it, do not write a second slugger.
- Produces:
  - `DEFAULT_DEVICE_GROUPS_PATH: Path`
  - `DEFAULT_DEVICE_GROUPS: list[dict]` — the seven seeded groups
  - `DEVICE_GROUP_COLORS: frozenset[str]`, `DEVICE_GROUP_KINDS: frozenset[str]`, `DEVICE_GROUP_READING_FILTERS: frozenset[str]`, `DEVICE_GROUP_CHROME: frozenset[str]`
  - `_load_device_groups(path: Path) -> dict[str, Any]` returning `{"groups": [...], "overrides": {...}}`
  - `_save_device_groups(path: Path, doc: dict) -> None`
  - `_coerce_group_color(value) -> str`, `_coerce_group_icon(value) -> str`

- [ ] **Step 1: Write the failing baseline test**

Create `tests/python/test_device_groups_baseline.py`:

```python
"""The seeded device groups must reproduce today's sidebar exactly.

This cycle's whole promise is "zero visible change". These assertions pin the
seeded document to the values currently hardcoded in index.html and styles.css,
so a drift is a test failure rather than something noticed on the dashboard.
"""

import re
from pathlib import Path

from src.python.web_app import DEFAULT_DEVICE_GROUPS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

EXPECTED_ORDER = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def _sidebar_children() -> list[tuple[str, str, str]]:
    """(data-view, icon, label) for each device-group child, in source order."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    views = html[
        html.index('<div class="sidebar-section">Views'):
        html.index('<div class="sidebar-section">Discovery')
    ]
    found = []
    for match in re.finditer(
        r'<li[^>]*device-group-item[^>]*data-view="([^"]+)"[^>]*>(.*?)</li>', views, re.S
    ):
        body = match.group(2)
        icon = re.search(r"ti ti-([a-z0-9-]+)", body)
        label = next(
            line.strip() for line in body.split("\n")
            if line.strip() and "<" not in line
        )
        found.append((match.group(1), icon.group(1), label))
    return found


def _css_group_colors() -> dict[str, str]:
    """view -> bare palette name, from the --group-color declarations."""
    css = re.sub(r"/\*.*?\*/", "", STYLES_CSS.read_text(encoding="utf-8"), flags=re.S)
    colors = {}
    for block in re.finditer(
        r"([^{}]+)\{([^{}]*--group-color\s*:\s*var\(--([a-z]+)\)[^{}]*)\}", css
    ):
        for view in re.findall(r'data-view="([^"]+)"', block.group(1)):
            colors[view] = block.group(3)
    return colors


def test_seeded_ids_and_order_match_the_sidebar() -> None:
    seeded = [g["id"] for g in DEFAULT_DEVICE_GROUPS]

    assert seeded == EXPECTED_ORDER
    assert [view for view, _icon, _label in _sidebar_children()] == EXPECTED_ORDER


def test_sensors_group_keeps_the_tuya_id() -> None:
    """data-view="tuya" may already be persisted as a user's default_view.
    Renaming the id to "sensors" would silently break that saved setting."""
    sensors = next(g for g in DEFAULT_DEVICE_GROUPS if g["name"] == "Sensors")

    assert sensors["id"] == "tuya"


def test_seeded_icons_and_labels_match_the_sidebar() -> None:
    by_id = {g["id"]: g for g in DEFAULT_DEVICE_GROUPS}

    for view, icon, label in _sidebar_children():
        assert by_id[view]["icon"] == icon, f"{view} icon drifted"
        assert by_id[view]["name"] == label, f"{view} label drifted"


def test_seeded_colors_match_the_stylesheet() -> None:
    by_id = {g["id"]: g for g in DEFAULT_DEVICE_GROUPS}
    css_colors = _css_group_colors()

    for group_id in EXPECTED_ORDER:
        assert by_id[group_id]["color"] == css_colors[group_id], f"{group_id} colour drifted"


def test_split_groups_carry_the_right_reading_filters() -> None:
    by_id = {g["id"]: g for g in DEFAULT_DEVICE_GROUPS}

    assert by_id["environment"]["readingFilter"] == "environment"
    assert by_id["tuya"]["readingFilter"] == "sensors"
    # Environment also collects the standalone Govee cloud sensors, which are a
    # separate inventory kind; readingFilter applies only to sensor-kind members.
    assert by_id["environment"]["kinds"] == ["sensor", "environment"]
    assert by_id["tuya"]["kinds"] == ["sensor"]


def test_only_lights_and_plugs_declare_chrome() -> None:
    with_chrome = {g["id"]: g["chrome"] for g in DEFAULT_DEVICE_GROUPS if g.get("chrome")}

    assert with_chrome == {
        "lights": ["lightScenes", "lightDragLock"],
        "plugs": ["plugActions"],
    }


def test_every_seeded_group_is_builtin() -> None:
    assert all(g["builtin"] for g in DEFAULT_DEVICE_GROUPS)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_device_groups_baseline.py -v`
Expected: `ImportError: cannot import name 'DEFAULT_DEVICE_GROUPS'`

- [ ] **Step 3: Add the constants**

In `src/python/web_app.py`, immediately after the `DEFAULT_AREAS` list (which ends around line 50):

```python
DEFAULT_DEVICE_GROUPS_PATH = PROJECT_ROOT / "dashboard_device_groups.json"

# Seeded to reproduce the sidebar exactly as it was before device groups became
# data. Sensors keeps the id "tuya" because data-view="tuya" may already be
# persisted as a user's default_view.
DEFAULT_DEVICE_GROUPS = [
    {"id": "lights", "name": "Lights", "icon": "bulb", "color": "amber",
     "kinds": ["light"], "chrome": ["lightScenes", "lightDragLock"], "builtin": True},
    {"id": "plugs", "name": "Plugs", "icon": "plug", "color": "accent",
     "kinds": ["plug"], "chrome": ["plugActions"], "builtin": True},
    {"id": "ambient", "name": "Ambient", "icon": "lamp-2", "color": "purple",
     "kinds": ["ambient"], "chrome": [], "builtin": True},
    {"id": "humidifier", "name": "Humidifiers", "icon": "droplet", "color": "cyan",
     "kinds": ["humidifier"], "chrome": [], "builtin": True},
    {"id": "environment", "name": "Environment", "icon": "temperature-celsius",
     "color": "teal", "kinds": ["sensor", "environment"],
     "readingFilter": "environment", "chrome": [], "builtin": True},
    {"id": "tuya", "name": "Sensors", "icon": "radar-2", "color": "indigo",
     "kinds": ["sensor"], "readingFilter": "sensors", "chrome": [], "builtin": True},
    {"id": "climate", "name": "Climate", "icon": "temperature", "color": "orange",
     "kinds": ["thermostat"], "chrome": [], "builtin": True},
]

DEVICE_GROUP_COLORS = frozenset(
    {"accent", "amber", "cyan", "green", "indigo", "orange", "pink", "purple", "red", "slate", "teal"}
)
DEVICE_GROUP_KINDS = frozenset(
    {"light", "plug", "sensor", "camera", "thermostat", "ambient", "humidifier", "environment"}
)
DEVICE_GROUP_READING_FILTERS = frozenset({"environment", "sensors"})
DEVICE_GROUP_CHROME = frozenset({"lightScenes", "lightDragLock", "plugActions"})
DEVICE_GROUP_ICON_PATTERN = re.compile(r"^[a-z0-9-]{1,32}$")
```

**`re` is not currently imported in `web_app.py`** (only `json`, at line 3). Add `import re` to the imports at the top of the file — `DEVICE_GROUP_ICON_PATTERN` needs it.

- [ ] **Step 4: Add the coercion helpers and loader**

Immediately after `_save_areas` (around line 2967):

```python
def _coerce_group_color(value: Any) -> str:
    """Palette name, or slate. A hand-edited file must not break the dashboard,
    and the value reaches a CSS custom property, so it is never trusted raw."""
    text = str(value or "").strip().lower()
    return text if text in DEVICE_GROUP_COLORS else "slate"


def _coerce_group_icon(value: Any) -> str:
    """Tabler icon suffix, or a neutral default. Reaches a class attribute."""
    text = str(value or "").strip().lower()
    return text if DEVICE_GROUP_ICON_PATTERN.match(text) else "device-desktop"


def _default_device_groups_doc() -> dict[str, Any]:
    return {"groups": [dict(g) for g in DEFAULT_DEVICE_GROUPS], "overrides": {}}


def _load_device_groups(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_device_groups_doc()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_device_groups_doc()
    if not isinstance(payload, dict):
        return _default_device_groups_doc()

    groups = []
    for raw in payload.get("groups") or []:
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("name"):
            continue
        groups.append(
            {
                "id": str(raw["id"]),
                "name": str(raw["name"]),
                "icon": _coerce_group_icon(raw.get("icon")),
                "color": _coerce_group_color(raw.get("color")),
                "kinds": [k for k in (raw.get("kinds") or []) if k in DEVICE_GROUP_KINDS],
                "chrome": [c for c in (raw.get("chrome") or []) if c in DEVICE_GROUP_CHROME],
                "readingFilter": (
                    raw["readingFilter"]
                    if raw.get("readingFilter") in DEVICE_GROUP_READING_FILTERS
                    else None
                ),
                "builtin": bool(raw.get("builtin")),
            }
        )
    if not groups:
        return _default_device_groups_doc()

    known = {g["id"] for g in groups}
    overrides = {}
    for key, rule in (payload.get("overrides") or {}).items():
        if not isinstance(rule, dict):
            continue
        include = [g for g in (rule.get("include") or []) if g in known]
        exclude = [g for g in (rule.get("exclude") or []) if g in known]
        if include or exclude:
            overrides[str(key)] = {"include": include, "exclude": exclude}

    return {"groups": groups, "overrides": overrides}


def _save_device_groups(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
```

Dropping override entries that name unknown groups is how stale references from
a deleted group get pruned on the next save.

- [ ] **Step 5: Write the loader tests**

Create `tests/python/test_device_groups_api.py`:

```python
"""Tests for the device group document, its loader, and its API."""

import json
from pathlib import Path

from src.python.web_app import (
    DEFAULT_DEVICE_GROUPS,
    _coerce_group_color,
    _coerce_group_icon,
    _load_device_groups,
    _save_device_groups,
)


def test_missing_file_returns_the_seeded_default(tmp_path: Path) -> None:
    doc = _load_device_groups(tmp_path / "nope.json")

    assert [g["id"] for g in doc["groups"]] == [g["id"] for g in DEFAULT_DEVICE_GROUPS]
    assert doc["overrides"] == {}


def test_null_and_malformed_documents_fall_back(tmp_path: Path) -> None:
    for content in ["null", "[]", "{}", '{"groups": null}', '{"groups": []}', "not json at all"]:
        path = tmp_path / "groups.json"
        path.write_text(content, encoding="utf-8")

        doc = _load_device_groups(path)

        assert len(doc["groups"]) == len(DEFAULT_DEVICE_GROUPS), f"failed for: {content}"


def test_null_overrides_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    path.write_text(json.dumps({"groups": DEFAULT_DEVICE_GROUPS, "overrides": None}), encoding="utf-8")

    assert _load_device_groups(path)["overrides"] == {}


def test_hand_edited_bad_colour_is_coerced_not_fatal(tmp_path: Path) -> None:
    """The colour reaches a CSS custom property, so a hand-edited file must be
    neutralised rather than trusted or allowed to break the page."""
    path = tmp_path / "groups.json"
    groups = [dict(DEFAULT_DEVICE_GROUPS[0], color="red; background:url(x)")]
    path.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    assert _load_device_groups(path)["groups"][0]["color"] == "slate"


def test_hand_edited_bad_icon_is_coerced(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    groups = [dict(DEFAULT_DEVICE_GROUPS[0], icon='x" onload="alert(1)')]
    path.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    assert _load_device_groups(path)["groups"][0]["icon"] == "device-desktop"


def test_valid_colour_survives() -> None:
    assert _coerce_group_color("red") == "red"
    assert _coerce_group_icon("temperature-celsius") == "temperature-celsius"


def test_unknown_kinds_and_chrome_are_dropped(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    groups = [dict(DEFAULT_DEVICE_GROUPS[0], kinds=["light", "wormhole"], chrome=["lightScenes", "rm -rf"])]
    path.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    loaded = _load_device_groups(path)["groups"][0]

    assert loaded["kinds"] == ["light"]
    assert loaded["chrome"] == ["lightScenes"]


def test_overrides_naming_unknown_groups_are_pruned(tmp_path: Path) -> None:
    """A deleted group leaves override entries behind; they must be ignored,
    not fatal, and dropped on the next save."""
    path = tmp_path / "groups.json"
    path.write_text(
        json.dumps(
            {
                "groups": DEFAULT_DEVICE_GROUPS,
                "overrides": {
                    "dev:1.2.3.4": {"include": ["lights", "deleted-group"], "exclude": []},
                    "dev:5.6.7.8": {"include": ["gone"], "exclude": ["also-gone"]},
                },
            }
        ),
        encoding="utf-8",
    )

    overrides = _load_device_groups(path)["overrides"]

    assert overrides == {"dev:1.2.3.4": {"include": ["lights"], "exclude": []}}


def test_round_trip_through_save(tmp_path: Path) -> None:
    path = tmp_path / "groups.json"
    original = _load_device_groups(tmp_path / "missing.json")
    _save_device_groups(path, original)

    assert _load_device_groups(path)["groups"] == original["groups"]
```

- [ ] **Step 6: Run the tests**

Run: `python3 -m pytest tests/python/test_device_groups_api.py tests/python/test_device_groups_baseline.py -v`
Expected: 16 passed.

- [ ] **Step 7: Commit**

```bash
git add src/python/web_app.py tests/python/test_device_groups_api.py tests/python/test_device_groups_baseline.py
git commit -m "feat: seed the device group document model and loader"
```

---

### Task 2: Device group API

**Files:**
- Modify: `src/python/web_app.py` (Pydantic models near `AreaCreateRequest` at `:219-231`; `create_app` signature at `:234-246`; routes near the areas routes at `:348-412`)
- Test: `tests/python/test_device_groups_api.py` (extend)

**Interfaces:**
- Consumes: `_load_device_groups`, `_save_device_groups`, `_coerce_group_color`, `_coerce_group_icon`, the four allowlist frozensets, `_area_slug`, and `DEFAULT_DEVICE_GROUPS_PATH` from Task 1.
- Produces:
  - `create_app(..., device_groups_path: Path = DEFAULT_DEVICE_GROUPS_PATH)` and `app.state.device_groups_path`
  - Routes: `GET/POST /api/device-groups`, `PATCH/DELETE /api/device-groups/{group_id}`, `PUT /api/device-groups/order`, `PUT /api/device-groups/overrides`
  - Request models `DeviceGroupCreateRequest`, `DeviceGroupUpdateRequest`, `DeviceGroupOrderRequest`, `DeviceGroupOverrideRequest`

- [ ] **Step 1: Write the failing API tests**

Append to `tests/python/test_device_groups_api.py`:

```python
from fastapi.testclient import TestClient

from src.python.web_app import create_app


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "switches.json"
    discovery.write_text(json.dumps({"count": 0, "switches": []}), encoding="utf-8")
    return TestClient(
        create_app(
            discovery_path=discovery,
            config_path=tmp_path / "missing.yaml",
            check_camera_ports=False,
            areas_path=tmp_path / "areas.json",
            device_groups_path=tmp_path / "groups.json",
        )
    )


def test_get_returns_the_seeded_document(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/device-groups").json()

    assert [g["id"] for g in payload["groups"]] == [g["id"] for g in DEFAULT_DEVICE_GROUPS]
    assert payload["overrides"] == {}


def test_create_accepts_name_icon_colour(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/device-groups", json={"name": "Movie Night", "icon": "movie", "color": "pink"})

    assert response.status_code == 200
    group = response.json()["group"]
    assert group["id"] == "movie-night"
    assert group["builtin"] is False
    # A user group starts with no rule; it gains members in Cycle 2.
    assert group["kinds"] == []


def test_create_rejects_duplicate_name_case_insensitively(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "LIGHTS"}).status_code == 409


def test_create_rejects_client_supplied_chrome_or_reading_filter(tmp_path: Path) -> None:
    """chrome and readingFilter exist only on seeded built-ins."""
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "A", "chrome": ["lightScenes"]}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "B", "readingFilter": "sensors"}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "C", "builtin": True}).status_code == 400


def test_create_rejects_bad_colour_and_icon(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "D", "color": "red; background:url(x)"}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "E", "icon": 'x" onload="y'}).status_code == 400
    # The bare palette name is fine.
    assert client.post("/api/device-groups", json={"name": "F", "color": "red"}).status_code == 200


def test_create_rejects_empty_and_overlong_names(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.post("/api/device-groups", json={"name": "   "}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "x" * 41}).status_code == 400
    assert client.post("/api/device-groups", json={"name": "!!!"}).status_code == 400


def test_patch_renames_and_recolours(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.patch("/api/device-groups/lights", json={"name": "Lamps", "color": "green"})

    assert response.status_code == 200
    assert response.json()["group"]["name"] == "Lamps"
    assert response.json()["group"]["color"] == "green"
    # The id never changes on rename, so overrides cannot be orphaned.
    assert response.json()["group"]["id"] == "lights"


def test_patch_rejects_bad_colour(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.patch("/api/device-groups/lights", json={"color": "octarine"}).status_code == 400


def test_delete_refuses_builtin_but_allows_user_groups(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/api/device-groups", json={"name": "Movie Night"})

    assert client.delete("/api/device-groups/lights").status_code == 409
    assert client.delete("/api/device-groups/movie-night").status_code == 200
    assert client.delete("/api/device-groups/movie-night").status_code == 404


def test_order_requires_a_permutation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ids = [g["id"] for g in DEFAULT_DEVICE_GROUPS]

    assert client.put("/api/device-groups/order", json={"ids": list(reversed(ids))}).status_code == 200
    assert client.put("/api/device-groups/order", json={"ids": ids[:-1]}).status_code == 400
    assert client.put("/api/device-groups/order", json={"ids": ids + ["extra"]}).status_code == 400
    assert client.put("/api/device-groups/order", json={"ids": [ids[0]] * len(ids)}).status_code == 400

    after = client.get("/api/device-groups").json()
    assert [g["id"] for g in after["groups"]] == list(reversed(ids))


def test_overrides_round_trip_and_validate(tmp_path: Path) -> None:
    client = _client(tmp_path)

    ok = client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:1.2.3.4", "include": ["climate"], "exclude": ["lights"]},
    )
    assert ok.status_code == 200
    assert ok.json()["overrides"]["dev:1.2.3.4"] == {"include": ["climate"], "exclude": ["lights"]}

    # Unknown group -> 404.
    assert client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:1.2.3.4", "include": ["nope"]},
    ).status_code == 404

    # Unknown device key is fine: the device may be offline or not yet discovered.
    assert client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:never-seen", "include": ["lights"]},
    ).status_code == 200

    # Empty include and exclude clears the entry.
    client.put("/api/device-groups/overrides", json={"device_key": "dev:1.2.3.4"})
    assert "dev:1.2.3.4" not in client.get("/api/device-groups").json()["overrides"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_device_groups_api.py -v -k "get_returns or create or patch or delete or order or overrides"`
Expected: FAIL — `create_app() got an unexpected keyword argument 'device_groups_path'`

- [ ] **Step 3: Add the request models**

In `src/python/web_app.py`, immediately after `AreaAssignRequest` (around line 231):

```python
class DeviceGroupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    icon: str | None = None
    color: str | None = None


class DeviceGroupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    icon: str | None = None
    color: str | None = None


class DeviceGroupOrderRequest(BaseModel):
    ids: list[str]


class DeviceGroupOverrideRequest(BaseModel):
    device_key: str
    include: list[str] = []
    exclude: list[str] = []
```

`extra="forbid"` is what rejects `chrome`, `readingFilter` and `builtin` from a
client. The import at `web_app.py:26` is currently `from pydantic import BaseModel`
— change it to `from pydantic import BaseModel, ConfigDict`.

FastAPI returns 422 for a Pydantic validation error, but the tests expect 400.
Add an exception handler inside `create_app`, immediately after the `app` is
constructed, so a malformed body reads as a bad request:

```python
    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/api/device-groups"):
            return JSONResponse(status_code=400, content={"detail": exc.errors()[0]["msg"]})
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
```

Add `from fastapi.exceptions import RequestValidationError`, `from fastapi import Request`
and `from fastapi.responses import JSONResponse` to the imports if not present.

- [ ] **Step 4: Wire the path into `create_app`**

Add the parameter to the signature (after `areas_path`):

```python
    device_groups_path: Path = DEFAULT_DEVICE_GROUPS_PATH,
```

and the state assignment beside `app.state.areas_path = areas_path`:

```python
    app.state.device_groups_path = device_groups_path
```

- [ ] **Step 5: Add the routes**

In `create_app`, immediately after the `@app.put("/api/areas/assignments")` handler:

```python
    def _find_group(doc: dict[str, Any], group_id: str) -> dict[str, Any]:
        group = next((g for g in doc["groups"] if g["id"] == group_id), None)
        if group is None:
            raise HTTPException(status_code=404, detail="Device group not found")
        return group

    def _validated_name(raw: str, doc: dict[str, Any], *, exclude_id: str | None = None) -> tuple[str, str]:
        name = raw.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Group name cannot be empty")
        if len(name) > 40:
            raise HTTPException(status_code=400, detail="Group name is too long")
        group_id = _area_slug(name)
        if not group_id:
            raise HTTPException(status_code=400, detail="Group name must contain letters or digits")
        for existing in doc["groups"]:
            if existing["id"] == exclude_id:
                continue
            if existing["id"] == group_id or existing["name"].lower() == name.lower():
                raise HTTPException(status_code=409, detail="A group with this name already exists")
        return group_id, name

    def _validated_color(raw: str | None) -> str | None:
        if raw is None:
            return None
        value = raw.strip().lower()
        if value not in DEVICE_GROUP_COLORS:
            raise HTTPException(status_code=400, detail=f"Unknown colour: {raw}")
        return value

    def _validated_icon(raw: str | None) -> str | None:
        if raw is None:
            return None
        value = raw.strip().lower()
        if not DEVICE_GROUP_ICON_PATTERN.match(value):
            raise HTTPException(status_code=400, detail=f"Invalid icon: {raw}")
        return value

    @app.get("/api/device-groups")
    async def device_groups_get() -> dict[str, Any]:
        return _load_device_groups(app.state.device_groups_path)

    @app.post("/api/device-groups")
    async def device_groups_create(body: DeviceGroupCreateRequest) -> dict[str, Any]:
        doc = _load_device_groups(app.state.device_groups_path)
        group_id, name = _validated_name(body.name, doc)
        group = {
            "id": group_id,
            "name": name,
            "icon": _validated_icon(body.icon) or "device-desktop",
            "color": _validated_color(body.color) or "slate",
            "kinds": [],
            "chrome": [],
            "readingFilter": None,
            "builtin": False,
        }
        doc["groups"].append(group)
        _save_device_groups(app.state.device_groups_path, doc)
        return {"group": group}

    @app.patch("/api/device-groups/{group_id}")
    async def device_groups_update(group_id: str, body: DeviceGroupUpdateRequest) -> dict[str, Any]:
        doc = _load_device_groups(app.state.device_groups_path)
        group = _find_group(doc, group_id)
        if body.name is not None:
            # The id is deliberately left alone so overrides cannot be orphaned.
            _, group["name"] = _validated_name(body.name, doc, exclude_id=group_id)
        icon = _validated_icon(body.icon)
        if icon is not None:
            group["icon"] = icon
        color = _validated_color(body.color)
        if color is not None:
            group["color"] = color
        _save_device_groups(app.state.device_groups_path, doc)
        return {"group": group}

    @app.delete("/api/device-groups/{group_id}")
    async def device_groups_delete(group_id: str) -> dict[str, Any]:
        doc = _load_device_groups(app.state.device_groups_path)
        group = _find_group(doc, group_id)
        if group["builtin"]:
            raise HTTPException(
                status_code=409,
                detail="Built-in groups cannot be deleted; their device kinds would have no home.",
            )
        doc["groups"] = [g for g in doc["groups"] if g["id"] != group_id]
        for rule in doc["overrides"].values():
            rule["include"] = [g for g in rule["include"] if g != group_id]
            rule["exclude"] = [g for g in rule["exclude"] if g != group_id]
        doc["overrides"] = {k: v for k, v in doc["overrides"].items() if v["include"] or v["exclude"]}
        _save_device_groups(app.state.device_groups_path, doc)
        return {"ok": True}

    @app.put("/api/device-groups/order")
    async def device_groups_order(body: DeviceGroupOrderRequest) -> dict[str, Any]:
        doc = _load_device_groups(app.state.device_groups_path)
        current = [g["id"] for g in doc["groups"]]
        if sorted(body.ids) != sorted(current):
            raise HTTPException(
                status_code=400, detail="Order must be a permutation of the existing group ids"
            )
        by_id = {g["id"]: g for g in doc["groups"]}
        doc["groups"] = [by_id[i] for i in body.ids]
        _save_device_groups(app.state.device_groups_path, doc)
        return {"groups": doc["groups"]}

    @app.put("/api/device-groups/overrides")
    async def device_groups_overrides(body: DeviceGroupOverrideRequest) -> dict[str, Any]:
        device_key = body.device_key.strip()
        if not device_key:
            raise HTTPException(status_code=400, detail="device_key cannot be empty")
        doc = _load_device_groups(app.state.device_groups_path)
        known = {g["id"] for g in doc["groups"]}
        for group_id in [*body.include, *body.exclude]:
            if group_id not in known:
                raise HTTPException(status_code=404, detail=f"Device group not found: {group_id}")
        if body.include or body.exclude:
            doc["overrides"][device_key] = {"include": body.include, "exclude": body.exclude}
        else:
            doc["overrides"].pop(device_key, None)
        _save_device_groups(app.state.device_groups_path, doc)
        return {"overrides": doc["overrides"]}
```

Note the route ordering: `/api/device-groups/order` and
`/api/device-groups/overrides` are declared **after** `/api/device-groups/{group_id}`
in the source, but FastAPI matches literal path segments before parameterised
ones only when the literal route is declared first. Declare `order` and
`overrides` **before** the `{group_id}` routes, or a PUT to `/order` will be
captured as `group_id="order"`. Move them accordingly and verify with the tests.

- [ ] **Step 6: Run the tests**

Run: `python3 -m pytest tests/python/test_device_groups_api.py -v`
Expected: all pass.

- [ ] **Step 7: Confirm nothing else regressed**

Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7 as before. Investigate any other change.

- [ ] **Step 8: Commit**

```bash
git add src/python/web_app.py tests/python/test_device_groups_api.py
git commit -m "feat: add the device group CRUD, ordering and overrides API"
```

---

### Task 3: Add the missing `environment` inventory kind

`collectHomeInventory()` produces `light`, `plug`, `sensor`, `camera`, `thermostat`, `ambient` and `humidifier` — but not the standalone Govee cloud sensors, which are absent from the shared inventory entirely. The Environment group cannot collect them by rule until they exist there.

**Files:**
- Modify: `src/python/web_static/app.js` (`collectHomeInventory`, ~`:4310`)
- Test: `tests/python/test_device_groups_logic.py` (create)

**Interfaces:**
- Consumes: `latestEnvironmentSensors` (module-level array, populated by `loadEnvironmentSensors`).
- Produces: inventory entries `{key: "env:<name>", kind: "environment", name, room, data}`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_device_groups_logic.py`:

```python
"""Node-harness tests for the JS device-group logic.

The repo has no JS toolchain and adding one is out of scope, so these extract
the functions under test from app.js and run them under node. String-grep
assertions cannot catch a wrong rule; these can.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

HARNESS_PRELUDE = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
"""


def _run_node(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS_PRELUDE + script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_environment_sensors_reach_the_shared_inventory(tmp_path: Path) -> None:
    """Without this kind the Environment group cannot collect the H5140 by rule."""
    script = """
globalThis.latestSwitchDevices = [];
globalThis.latestMatterDevices = [];
globalThis.latestTuyaDevices = [];
globalThis.latestCameras = [];
globalThis.latestThermostats = [];
globalThis.latestAmbientLights = [];
globalThis.latestHumidifiers = [];
globalThis.latestEnvironmentSensors = [
  { name: 'Govee Thermo-Hygrometer', room: 'Bedroom', temperature: 21.5, humidity: 44 }
];
eval(pick('isTuyaCamera') + pick('sensorBaseName') + pick('areaSlug')
   + pick('groupSensorDevices') + pick('isAlertDetected') + pick('cameraIdFor')
   + pick('tuyaCameraCard') + pick('collectHomeInventory'));
const inv = collectHomeInventory();
console.log(JSON.stringify(inv.map((i) => ({ key: i.key, kind: i.kind, name: i.name }))));
"""
    inventory = _run_node(script, tmp_path)

    assert inventory == [
        {"key": "env:govee-thermo-hygrometer", "kind": "environment", "name": "Govee Thermo-Hygrometer"}
    ]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_device_groups_logic.py -v`
Expected: FAIL — the inventory is empty, because environment sensors are not collected.

- [ ] **Step 3: Add the inventory entries**

In `src/python/web_static/app.js`, inside `collectHomeInventory()`, immediately after the humidifier loop and before `return inventory;`:

```js
  for (const sensor of latestEnvironmentSensors) {
    inventory.push({
      key: `env:${areaSlug(sensor.name || "environment sensor")}`,
      kind: "environment",
      name: sensor.name,
      room: sensor.room || "",
      data: sensor,
    });
  }
```

`areaSlug` is the existing helper used for sensor keys; reuse it rather than
adding a second slugger.

- [ ] **Step 4: Run the test and the syntax check**

Run: `python3 -m pytest tests/python/test_device_groups_logic.py -v`
Expected: PASS

Run: `node --check src/python/web_static/app.js`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_device_groups_logic.py
git commit -m "feat: include Govee environment sensors in the shared device inventory"
```

---

### Task 4: Membership resolution and the nav planner

Two pure functions, so both are testable without a DOM.

**Files:**
- Modify: `src/python/web_static/app.js` (add near `collectHomeInventory`)
- Test: `tests/python/test_device_groups_logic.py` (extend)

**Interfaces:**
- Consumes: inventory entries `{key, kind, name, room, data}` from Task 3.
- Produces:
  - `resolveDeviceGroupMembers(group, inventory, overrides) -> array` — the inventory entries belonging to `group`
  - `deviceGroupNavPlan(groups) -> array of {id, name, icon, color}` — the desired sidebar order
  - `GROUP_COLOR_VARS` — an object mapping each allowed palette name to its CSS variable string

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_device_groups_logic.py`:

```python
GROUPS_JS = """
const groups = [
  { id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] },
  { id: 'climate', name: 'Climate', icon: 'temperature', color: 'orange', kinds: ['thermostat'] },
  { id: 'environment', name: 'Environment', icon: 'temperature-celsius', color: 'teal',
    kinds: ['sensor', 'environment'], readingFilter: 'environment' },
  { id: 'tuya', name: 'Sensors', icon: 'radar-2', color: 'indigo',
    kinds: ['sensor'], readingFilter: 'sensors' },
];
const inventory = [
  { key: 'dev:1', kind: 'light', name: 'Hall light' },
  { key: 'thermo:1', kind: 'thermostat', name: 'Upstairs' },
  { key: 'sensor:hub', kind: 'sensor', name: 'Hub' },
  { key: 'env:govee', kind: 'environment', name: 'Govee' },
];
const members = (id, overrides) => resolveDeviceGroupMembers(
  groups.find((g) => g.id === id), inventory, overrides || {}
).map((m) => m.key);
"""


def test_type_rule_collects_matching_devices(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
console.log(JSON.stringify({{
  lights: members('lights'),
  climate: members('climate'),
}}));
"""
    result = _run_node(script, tmp_path)

    assert result["lights"] == ["dev:1"]
    assert result["climate"] == ["thermo:1"]


def test_a_sensor_appears_in_both_split_groups(tmp_path: Path) -> None:
    """Environment and Sensors are two views of one device's readings, not two
    competing homes. Environment also collects the standalone Govee sensor."""
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
console.log(JSON.stringify({{
  environment: members('environment'),
  sensors: members('tuya'),
}}));
"""
    result = _run_node(script, tmp_path)

    assert result["environment"] == ["sensor:hub", "env:govee"]
    assert result["sensors"] == ["sensor:hub"]


def test_exclude_override_removes_an_auto_collected_device(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
const ov = {{ 'dev:1': {{ include: [], exclude: ['lights'] }} }};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == []


def test_include_override_adds_a_device_its_kind_does_not_match(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
const ov = {{ 'thermo:1': {{ include: ['lights'], exclude: [] }} }};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == ["dev:1", "thermo:1"]


def test_overrides_for_unknown_devices_and_groups_are_harmless(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
const ov = {{
  'dev:never-seen': {{ include: ['lights'], exclude: [] }},
  'dev:1': {{ include: ['deleted-group'], exclude: [] }},
}};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == ["dev:1"]


def test_nav_plan_preserves_order_and_maps_colours(tmp_path: Path) -> None:
    script = f"""
eval(pick('deviceGroupNavPlan') + 'const x=0;');
{GROUPS_JS}
console.log(JSON.stringify(deviceGroupNavPlan(groups)));
"""
    plan = _run_node(script, tmp_path)

    assert [p["id"] for p in plan] == ["lights", "climate", "environment", "tuya"]
    assert plan[0]["color"] == "var(--amber)"


def test_nav_plan_neutralises_an_unknown_colour(tmp_path: Path) -> None:
    """The colour reaches a CSS custom property, so an unexpected value must
    resolve to a known variable rather than being passed through."""
    script = """
eval(pick('deviceGroupNavPlan') + 'const x=0;');
const groups = [{ id: 'x', name: 'X', icon: 'bulb', color: 'red; background:url(y)', kinds: [] }];
console.log(JSON.stringify(deviceGroupNavPlan(groups)));
"""
    plan = _run_node(script, tmp_path)

    assert plan[0]["color"] == "var(--slate)"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/python/test_device_groups_logic.py -v`
Expected: FAIL — `missing function resolveDeviceGroupMembers`

- [ ] **Step 3: Add the two pure functions**

In `src/python/web_static/app.js`, immediately after `collectHomeInventory()`:

```js
/* ── Device group membership ──
   Membership is multi-valued on purpose: a 4-in-1 sensor belongs in both
   Environment and Sensors, because those are two views of its readings rather
   than two competing homes. A per-device override adds or removes one group
   without disturbing the others. */
function resolveDeviceGroupMembers(group, inventory, overrides) {
  const kinds = new Set(group.kinds || []);
  const rules = overrides || {};
  return inventory.filter((item) => {
    const rule = rules[item.key] || {};
    if ((rule.exclude || []).includes(group.id)) return false;
    if ((rule.include || []).includes(group.id)) return true;
    return kinds.has(item.kind);
  });
}

/* Palette names the sidebar and tiles may use. The value that reaches the DOM
   is always chosen from this table, never built from the stored string. */
const GROUP_COLOR_VARS = {
  accent: "var(--accent)", amber: "var(--amber)", cyan: "var(--cyan)",
  green: "var(--green)", indigo: "var(--indigo)", orange: "var(--orange)",
  pink: "var(--pink)", purple: "var(--purple)", red: "var(--red)",
  slate: "var(--slate)", teal: "var(--teal)",
};

const GROUP_ICON_PATTERN = /^[a-z0-9-]{1,32}$/;

function deviceGroupNavPlan(groups) {
  return (groups || []).map((group) => ({
    id: group.id,
    name: group.name,
    icon: GROUP_ICON_PATTERN.test(String(group.icon || "")) ? group.icon : "device-desktop",
    color: GROUP_COLOR_VARS[group.color] || GROUP_COLOR_VARS.slate,
  }));
}
```

- [ ] **Step 4: Run the tests and the syntax check**

Run: `python3 -m pytest tests/python/test_device_groups_logic.py -v`
Expected: all pass.

Run: `node --check src/python/web_static/app.js`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_device_groups_logic.py
git commit -m "feat: resolve device group membership from kind rules and overrides"
```

---

### Task 5: Drive the sidebar from the loaded groups

The seven `<li>` entries stay in `index.html` as the seeded baseline — they are the no-JS fallback and what the existing HTML assertions check. `syncDeviceGroupNav()` reconciles them with the loaded document: it relabels, recolours, reorders, and appends any group the markup does not have.

**Files:**
- Modify: `src/python/web_static/app.js` (loader + sync near `renderDeviceGroupNav`; `DEVICE_GROUP_VIEWS` at `:249`)
- Test: `tests/python/test_device_groups_logic.py` (extend)

**Interfaces:**
- Consumes: `deviceGroupNavPlan(groups)` from Task 4; `requestJson(url)`; `activateView(viewName)`.
- Produces: `latestDeviceGroups` (module-level array), `loadDeviceGroups()`, `syncDeviceGroupNav()`, and `DEVICE_GROUP_VIEWS` derived from the loaded groups rather than hardcoded.

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_device_groups_logic.py`:

```python
def test_device_group_views_is_derived_not_hardcoded(tmp_path: Path) -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "let DEVICE_GROUP_VIEWS" in javascript, "must be reassignable once groups load"
    assert 'requestJson("/api/device-groups")' in javascript
    assert "function syncDeviceGroupNav" in javascript


def test_nav_sync_uses_the_dom_api_not_markup_strings(tmp_path: Path) -> None:
    """color and icon originate in a hand-editable JSON file and reach a CSS
    custom property and a class attribute. Neither may be interpolated into
    markup."""
    javascript = APP_JS.read_text(encoding="utf-8")
    at = javascript.index("function syncDeviceGroupNav")
    depth, i, body = 0, javascript.index("{", at), None
    for j in range(i, len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    assert "setProperty(\"--group-color\"" in body
    assert "classList.add" in body
    assert "innerHTML" not in body, "nav sync must not build markup strings"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/python/test_device_groups_logic.py -v -k derived or dom_api`
Expected: FAIL — `let DEVICE_GROUP_VIEWS` not found.

- [ ] **Step 3: Make `DEVICE_GROUP_VIEWS` reassignable**

In `src/python/web_static/app.js`, change line 249 from:

```js
const DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"];
```

to:

```js
/* Seeded to the built-in groups so the sidebar works before the group document
   loads; replaced by the loaded ids once it arrives. */
let DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"];
let latestDeviceGroups = [];
```

- [ ] **Step 4: Add the loader and the sync**

Add immediately after `deviceGroupNavPlan` (from Task 4):

```js
/* ── Device group navigation ── */
async function loadDeviceGroups() {
  const payload = await requestJson("/api/device-groups");
  latestDeviceGroups = payload.groups || [];
  if (latestDeviceGroups.length) {
    DEVICE_GROUP_VIEWS = latestDeviceGroups.map((group) => group.id);
  }
  syncDeviceGroupNav();
}

/* The seven <li> elements ship in index.html as the seeded baseline, so the
   sidebar is correct before any JavaScript runs. This reconciles them with the
   loaded document rather than rebuilding the list, which keeps that fallback
   intact. Values reach the DOM through the API, never through markup strings. */
function syncDeviceGroupNav() {
  const parent = document.querySelector("#devicesGroupToggle");
  const list = parent?.parentElement;
  if (!list) return;

  const existing = new Map(
    [...list.querySelectorAll(".device-group-item")].map((el) => [el.dataset.view, el])
  );
  let anchor = parent;

  deviceGroupNavPlan(latestDeviceGroups).forEach((entry) => {
    let item = existing.get(entry.id);
    if (!item) {
      item = document.createElement("li");
      item.className = "room-item device-group-item";
      item.dataset.view = entry.id;
      const icon = document.createElement("span");
      icon.className = "room-icon";
      icon.appendChild(document.createElement("i"));
      item.appendChild(icon);
      item.appendChild(document.createTextNode(""));
      item.addEventListener("click", () => {
        arrivedFromDevices = false;
        activateView(entry.id);
      });
    }
    existing.delete(entry.id);

    const glyph = item.querySelector(".room-icon i");
    if (glyph) {
      glyph.className = "";
      glyph.classList.add("ti", `ti-${entry.icon}`);
    }
    const label = [...item.childNodes].find((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
    if (label) label.textContent = ` ${entry.name} `;
    item.style.setProperty("--group-color", entry.color);

    anchor.after(item);
    anchor = item;
  });

  // Any child left in the map is no longer a group; drop it.
  existing.forEach((el) => el.remove());
}
```

- [ ] **Step 5: Load the groups on startup**

In the `initDefaultView` IIFE, beside the other startup loads:

```js
  loadDeviceGroups().catch((error) => console.error(error));
```

It must run **before** `activateView(getDefaultView())` would be affected — but
since it only relabels and reorders existing items, ordering is not critical.
Place it with the other loaders.

- [ ] **Step 6: Run the tests and the syntax check**

Run: `python3 -m pytest tests/python/test_device_groups_logic.py -v`
Expected: all pass.

Run: `node --check src/python/web_static/app.js`
Expected: no output, exit 0.

- [ ] **Step 7: Confirm the whole suite still matches baseline**

Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7. Every previously-passing dashboard test must still pass; the static `<li>` elements are unchanged, so the HTML assertions in `test_dashboard_devices_group.py`, `test_devices_view_polish.py` and `test_dashboard_layout.py` should be unaffected. Investigate any that are not.

- [ ] **Step 8: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_device_groups_logic.py
git commit -m "feat: sync the device group sidebar from the loaded group document"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Part 1 — document shape, seeded groups, `tuya` id, array order | 1 |
| Part 2 — multi-valued membership, `overrides` include/exclude | 4 |
| Part 2 — sensor-split limitation (rule-driven in Cycle 1) | 4 (tests assert dual membership; no UI writes overrides) |
| Part 2 — `collectHomeInventory` gains `environment` | 3 |
| Part 3 — GET/POST/PATCH/DELETE/order/overrides, creation policy, validation | 2 |
| Part 3 — stale overrides tolerated and pruned | 1 (loader) and 2 (delete) |
| Part 4 — colour/icon validated on write and on load, DOM API, lookup table | 1 (load), 2 (write), 4 (`GROUP_COLOR_VARS`), 5 (`setProperty`/`classList`) |
| Part 5 — sidebar from data, `DEVICE_GROUP_VIEWS` derived | 5 |
| Part 6 — built-in panels untouched | All — no task modifies a built-in renderer or panel |
| Testing — baseline fidelity, `tuya` startup view, resolution, API, tolerance | 1, 2, 4 |

No spec requirement is unassigned.

**Placeholder scan:** no TBD/TODO. Every code step carries complete code.

**Type consistency:** `resolveDeviceGroupMembers(group, inventory, overrides)` is defined in Task 4 and used only there in Cycle 1. `deviceGroupNavPlan(groups)` is defined in Task 4 and consumed in Task 5. `GROUP_COLOR_VARS` is defined in Task 4 and consumed by `deviceGroupNavPlan`. `latestDeviceGroups` and `DEVICE_GROUP_VIEWS` are declared in Task 5 Step 3 and used in Step 4. The loader returns `{"groups", "overrides"}` in Task 1 and every API route in Task 2 assumes exactly those keys.

**Two risks the spec did not spell out, now handled:**

1. **FastAPI route ordering.** `/api/device-groups/order` and `/overrides` would be swallowed by `/api/device-groups/{group_id}` if declared after it. Task 2 Step 5 calls this out explicitly and the order tests would fail loudly if it were got wrong.

2. **Existing tests assert static HTML and the `--group-color` CSS block.** Rebuilding the sidebar from scratch in JS would strand them, and Python cannot assert JS-rendered DOM. Task 5 therefore *reconciles* the existing `<li>` elements rather than replacing them, so `index.html` stays the seeded baseline, the no-JS fallback survives, and `test_dashboard_devices_group.py`, `test_devices_view_polish.py` and `test_dashboard_layout.py` keep passing untouched.

**One accepted Cycle 1 limitation:** a group created through the API gets a sidebar entry but no panel, because built-in panels stay hardcoded and the generic renderer is Cycle 2. There is no UI to create groups in this cycle, so this is reachable only by calling the API directly.

**Ordering note for the executor:** Task 4 depends on Task 3's inventory kind; Task 5 depends on Task 4's planner. Run in order rather than in parallel. Tasks 1 and 2 are backend-only and independent of 3-5, but Task 2 depends on Task 1.
