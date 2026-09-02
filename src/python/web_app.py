from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Literal
from urllib.parse import urlencode
from urllib.parse import quote
from urllib.parse import quote_plus
from urllib.parse import urlparse
from urllib.request import Request as _URLRequest
from urllib.request import urlopen

import hashlib
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope
import yaml

from src.python.ble_adapter import ble_kwargs as _ble_kwargs
from src.python.tplink_switch import KasaLightSwitchController, SwitchDefinition
from src.python.tplink_discovery import apply_discovered_hosts, discover_hosts_by_mac
from src.python.matter_device import (
    DEFAULT_COMMISSION_TIMEOUT,
    DashboardMatterClient,
    MatterServerUnavailable,
    node_to_device,
)
from src.python import bridge_sync

_matter_log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISCOVERY_PATH = PROJECT_ROOT / "tplink_switches.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "devices.local.yaml"
DEFAULT_HA_KNOWN_ENTITIES_PATH = PROJECT_ROOT / "home_assistant_known_entities.json"
DEFAULT_AREAS_PATH = PROJECT_ROOT / "dashboard_areas.json"
# Written by scripts/install-zigbee2mqtt.sh, git-ignored. Read only to hand the
# dashboard's own iframe a frontend token; see the /api/zigbee/frontend route.
DEFAULT_ZIGBEE_SECRET_PATH = PROJECT_ROOT / "deploy" / "zigbee" / "zigbee2mqtt" / "secret.yaml"
# Zigbee2MQTT's own web app. Not configurable in configuration.example.yaml
# either, so a constant rather than a setting.
ZIGBEE_FRONTEND_PORT = 8080
# Mirrors the areas defined in Home Assistant; seeded when no areas file exists yet.
DEFAULT_AREAS = [
    {"id": "living-room", "name": "Living Room", "icon": "sofa"},
    {"id": "kitchen", "name": "Kitchen", "icon": "chef-hat"},
    {"id": "bedroom", "name": "Bedroom", "icon": "bed"},
    {"id": "front-door", "name": "Front Door", "icon": "door"},
    {"id": "family-room", "name": "Family Room", "icon": "sofa"},
    {"id": "office", "name": "Office", "icon": "desk"},
    {"id": "utility-room", "name": "Utility Room", "icon": "tools"},
]
DEFAULT_DEVICE_GROUPS_PATH = PROJECT_ROOT / "dashboard_device_groups.json"

# python-kasa waits ~5s for a switch that has dropped off WiFi. The dashboard
# used to pay that serially for every switch, so a single dead device added 5s
# to every page load. Poll concurrently and cap what any one device can cost.
#
# Measured on the board: the first poll after the switches have been idle costs
# 3-5s per device, and settles to well under a second once they are awake. The
# cap has to clear that cold floor or every switch reads back unknown after a
# restart - it is not a page-load budget, because the cache below means only
# the very first request ever waits on a poll.
SWITCH_STATUS_TIMEOUT = 6.0
# Polling all of them at once makes each one slower: they share the board's
# WiFi, and the contention showed up as every device creeping past the cap.
SWITCH_POLL_CONCURRENCY = 4
# Only drop a cached connection after this many consecutive failures, so a
# merely slow switch is not forced to reconnect (and get slower) on every poll.
SWITCH_EVICT_AFTER_FAILURES = 2
# How long a cached device list is served before a background refresh is kicked
# off. The dashboard re-polls every 60s, so this keeps the cache warm without
# letting a burst of requests each start their own refresh.
DEVICE_CACHE_STALE_AFTER = 10.0
# A switch that misses this many consecutive polls may have been handed a new
# DHCP lease rather than died, so go looking for it. Set above
# SWITCH_EVICT_AFTER_FAILURES: reconnecting is the cheap explanation and is
# tried first, and a broadcast scan is only worth it once that has not helped.
SWITCH_REDISCOVER_AFTER_FAILURES = 3
# Floor between broadcast scans. A switch that is genuinely off keeps failing,
# and without this every poll cycle would kick off another scan.
SWITCH_REDISCOVER_MIN_INTERVAL = 300.0


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Poll the switches before anyone asks.

    The first poll after the devices have been idle is the expensive one, so
    pay it at startup rather than making the first page load wait for it.
    """
    _schedule_device_refresh(app)
    yield


class _CachedStaticFiles(StaticFiles):
    """Static assets served with cache headers.

    index.html references app.js/styles.css with a ?v=buildNNN query that
    deploy-dashboard.sh bumps on every deploy, so a versioned URL can be cached
    hard: the URL changes whenever the bytes do. Unversioned requests get a
    short TTL instead, so a stale asset can never pin itself in a phone's cache.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in {200, 304}:
            query = scope.get("query_string", b"").decode("latin-1")
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable" if "v=" in query else "public, max-age=300"
            )
        return response

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
STATIC_DIR = PROJECT_ROOT / "src" / "python" / "web_static"
# Last-known ambient-light state, keyed by BLE address or name. Live-readable
# providers (govee_lan) overwrite this with real device status; write-only BLE
# lamps rely on it, so it is persisted to disk to survive service restarts.
AMBIENT_LIGHT_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _ambient_state_file(config_path: Path) -> Path:
    return config_path.parent / "ambient_light_state.json"


def _load_ambient_runtime_state(config_path: Path) -> None:
    path = _ambient_state_file(config_path)
    if not path.exists():
        return
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    if isinstance(stored, dict):
        AMBIENT_LIGHT_RUNTIME_STATE.update(stored)


def _save_ambient_runtime_state(config_path: Path) -> None:
    try:
        _ambient_state_file(config_path).write_text(
            json.dumps(AMBIENT_LIGHT_RUNTIME_STATE), encoding="utf-8"
        )
    except OSError:
        pass

_raw_cfg: dict = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {} if DEFAULT_CONFIG_PATH.exists() else {}
_matter_cfg: dict = _raw_cfg.get("matter") or {}
_matter_server_url: str = _matter_cfg.get("server_url", "ws://localhost:5580/ws")
_matter_device_meta: dict[int, dict] = {
    int(d["node_id"]): d
    for d in (_matter_cfg.get("devices") or [])
    if "node_id" in d
}
_matter_commission_timeout: float = float(
    _matter_cfg.get("commission_timeout", DEFAULT_COMMISSION_TIMEOUT)
)
_matter_client = DashboardMatterClient(
    _matter_server_url, commission_timeout=_matter_commission_timeout
)


class _MatterCommissionBody(BaseModel):
    setup_code: str
    name: str
    room: str | None = None


class _HomeAssistantDeviceConfirmBody(BaseModel):
    name: str
    room: str | None = None
    category: Literal["light_switch", "smart_plug"]


@dataclass(frozen=True)
class DashboardDevice:
    switch: SwitchDefinition
    device_type: str | None


@dataclass(frozen=True)
class CameraDefinition:
    name: str
    host: str
    provider: str
    model: str | None
    room: str | None
    snapshot_url: str | None
    stream_url: str | None
    view_url: str | None
    mjpeg_fps: int
    mjpeg_width: int
    mjpeg_quality: int
    stream_name: str
    go2rtc_url: str | None
    battery_powered: bool


@dataclass(frozen=True)
class TuyaDefinition:
    name: str
    device_id: str
    host: str | None
    local_key: str | None
    version: float
    category: str
    room: str | None
    model: str | None
    power_dp: str | None
    cloud_power_code: str | None
    dps: dict[str, str]


@dataclass(frozen=True)
class AmbientLightDefinition:
    name: str
    provider: str
    model: str | None
    room: str | None
    address: str | None
    alexa_name: str | None


@dataclass(frozen=True)
class HumidifierDefinition:
    name: str
    provider: str
    model: str | None
    room: str | None
    device_id: str | None
    # Optional linked Govee thermometer (e.g. H5179) whose ambient humidity and
    # temperature are shown on the card. Falls back to a unique account sensor.
    thermometer_device_id: str | None = None
    thermometer_model: str | None = None
    temperature_unit: str = "C"


@dataclass(frozen=True)
class EnvironmentSensorDefinition:
    """A standalone temperature/humidity sensor (e.g. Govee H5140)."""
    name: str
    provider: str
    model: str | None
    room: str | None
    device_id: str | None


@dataclass(frozen=True)
class WeatherConfig:
    name: str
    latitude: float
    longitude: float
    timezone: str
    temperature_unit: str


@dataclass(frozen=True)
class EcobeeConfig:
    name: str
    thermostat_id: str | None
    room: str | None
    temperature_unit: str


@dataclass(frozen=True)
class HomeAssistantConfig:
    base_url: str
    token_env: str
    include_domains: set[str]


class CameraUpdateRequest(BaseModel):
    name: str


class AmbientLightUpdateRequest(BaseModel):
    name: str


class ClimateUpdateRequest(BaseModel):
    hvac_mode: str | None = None
    preset_mode: str | None = None
    preset_entity_id: str | None = None
    temperature: float | None = None
    target_temp_low: float | None = None
    target_temp_high: float | None = None


class AreaCreateRequest(BaseModel):
    name: str
    icon: str | None = None


class AreaUpdateRequest(BaseModel):
    name: str | None = None
    icon: str | None = None


class AreaAssignRequest(BaseModel):
    device_key: str
    area_id: str | None = None


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


def create_app(
    discovery_path: Path = DEFAULT_DISCOVERY_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    controller: KasaLightSwitchController | None = None,
    check_camera_ports: bool = True,
    areas_path: Path = DEFAULT_AREAS_PATH,
    device_groups_path: Path = DEFAULT_DEVICE_GROUPS_PATH,
    zigbee_secret_path: Path = DEFAULT_ZIGBEE_SECRET_PATH,
) -> FastAPI:
    app = FastAPI(title="Smart Home Orange Pi 6 Plus Dashboard", lifespan=_lifespan)
    app.state.discovery_path = discovery_path
    app.state.config_path = config_path
    app.state.controller = controller or KasaLightSwitchController()
    app.state.check_camera_ports = check_camera_ports
    app.state.areas_path = areas_path
    app.state.device_groups_path = device_groups_path
    app.state.zigbee_secret_path = zigbee_secret_path
    # Last known device list, served instantly while a refresh runs behind it.
    app.state.device_cache = {"cards": None, "at": 0.0, "task": None}
    # Consecutive status failures per switch host, used to retire dead sockets
    # and to notice a switch that may have moved to a new address.
    app.state.switch_failures = {}
    app.state.rediscovery = {"task": None, "at": 0.0}
    _load_ambient_runtime_state(config_path)

    # app.js and styles.css are ~380KB of text served uncompressed otherwise.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    _raw_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    _raw_cfg = _raw_cfg or {}
    _auth_cfg = _raw_cfg.get("dashboard_auth")
    _auth_user: str | None = str(_auth_cfg["username"]) if _auth_cfg else None
    _auth_pass: str | None = str(_auth_cfg["password"]) if _auth_cfg else None
    _signer: URLSafeTimedSerializer | None = None
    _MAX_AGE = 30 * 24 * 3600  # 30 days
    if _auth_cfg:
        _secret = hashlib.sha256(f"smart-home-salt-{_auth_pass}".encode()).hexdigest()
        _signer = URLSafeTimedSerializer(_secret)

        # --- Auth middleware --------------------------------------------------
        _SKIP_PATHS = {"/login", "/logout"}

        class _AuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):  # type: ignore[override]
                path = request.url.path
                # Always allow login/logout, static assets, and bridge sync API
                # (bridge endpoints are internal-only, called from localhost by the C++ bridge)
                if path in _SKIP_PATHS or path.startswith("/static/") or path.startswith("/bridge/"):
                    return await call_next(request)

                # Validate session cookie
                token = request.cookies.get("session")
                valid = False
                if token and _signer is not None:
                    try:
                        _signer.loads(token, max_age=_MAX_AGE)
                        valid = True
                    except (SignatureExpired, BadSignature):
                        valid = False

                if valid:
                    return await call_next(request)

                # Unauthenticated: API → 401, HTML → redirect
                if path.startswith("/api/"):
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                return RedirectResponse(url="/login", status_code=303)

        app.add_middleware(_AuthMiddleware)

        # --- Login / logout routes --------------------------------------------
        from fastapi import Form as _Form

        @app.get("/login")
        async def login_page() -> Response:
            path = STATIC_DIR / "login.html"
            if not path.exists():
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": "login page not found"}, status_code=404)
            return FileResponse(path)

        @app.post("/login")
        async def login_post(
            username: str = _Form(...),
            password: str = _Form(...),
        ) -> RedirectResponse:
            if username == _auth_user and password == _auth_pass:
                token = _signer.dumps({"u": username})  # type: ignore[union-attr]
                response = RedirectResponse(url="/", status_code=303)
                response.set_cookie(
                    key="session",
                    value=token,
                    httponly=True,
                    samesite="lax",
                    max_age=_MAX_AGE,
                )
                return response
            return RedirectResponse(url="/login?error=1", status_code=303)

        @app.post("/logout")
        async def logout() -> RedirectResponse:
            response = RedirectResponse(url="/login", status_code=303)
            response.delete_cookie(key="session")
            return response

    app.mount("/static", _CachedStaticFiles(directory=STATIC_DIR), name="static")

    app.include_router(bridge_sync.router)
    import functools as _functools
    bridge_sync.register_handlers(
        get_devices_fn=_functools.partial(_bridge_device_list, controller=app.state.controller),
        execute_command_fn=_functools.partial(_bridge_execute_command, controller=app.state.controller),
    )

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/devices")
    async def devices() -> dict[str, list[dict[str, Any]]]:
        return {"devices": await _device_cards_cached(app)}

    @app.get("/api/areas")
    async def areas_get() -> dict[str, Any]:
        return _load_areas(app.state.areas_path)

    @app.post("/api/areas")
    async def areas_create(body: AreaCreateRequest) -> dict[str, Any]:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Area name cannot be empty")
        if len(name) > 40:
            raise HTTPException(status_code=400, detail="Area name is too long")
        doc = _load_areas(app.state.areas_path)
        area_id = _area_slug(name)
        if not area_id:
            raise HTTPException(status_code=400, detail="Area name must contain letters or digits")
        if any(a["id"] == area_id or a["name"].lower() == name.lower() for a in doc["areas"]):
            raise HTTPException(status_code=409, detail="An area with this name already exists")
        area = {"id": area_id, "name": name, "icon": (body.icon or "home").strip() or "home"}
        doc["areas"].append(area)
        _save_areas(app.state.areas_path, doc)
        return {"area": area}

    @app.patch("/api/areas/{area_id}")
    async def areas_update(area_id: str, body: AreaUpdateRequest) -> dict[str, Any]:
        doc = _load_areas(app.state.areas_path)
        area = next((a for a in doc["areas"] if a["id"] == area_id), None)
        if area is None:
            raise HTTPException(status_code=404, detail="Area not found")
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="Area name cannot be empty")
            if len(name) > 40:
                raise HTTPException(status_code=400, detail="Area name is too long")
            area["name"] = name
        if body.icon is not None:
            area["icon"] = body.icon.strip() or "home"
        _save_areas(app.state.areas_path, doc)
        return {"area": area}

    @app.delete("/api/areas/{area_id}")
    async def areas_delete(area_id: str) -> dict[str, Any]:
        doc = _load_areas(app.state.areas_path)
        if not any(a["id"] == area_id for a in doc["areas"]):
            raise HTTPException(status_code=404, detail="Area not found")
        doc["areas"] = [a for a in doc["areas"] if a["id"] != area_id]
        doc["assignments"] = {k: v for k, v in doc["assignments"].items() if v != area_id}
        _save_areas(app.state.areas_path, doc)
        return {"ok": True}

    @app.put("/api/areas/assignments")
    async def areas_assign(body: AreaAssignRequest) -> dict[str, Any]:
        device_key = body.device_key.strip()
        if not device_key:
            raise HTTPException(status_code=400, detail="device_key cannot be empty")
        doc = _load_areas(app.state.areas_path)
        if body.area_id:
            if not any(a["id"] == body.area_id for a in doc["areas"]):
                raise HTTPException(status_code=404, detail="Area not found")
            doc["assignments"][device_key] = body.area_id
        else:
            doc["assignments"].pop(device_key, None)
        _save_areas(app.state.areas_path, doc)
        return {"assignments": doc["assignments"]}

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
        if group_id == "auto:unassigned":
            raise HTTPException(status_code=400, detail="That group id is reserved")
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
        _find_group(doc, group_id)
        doc["groups"] = [g for g in doc["groups"] if g["id"] != group_id]
        for rule in doc["overrides"].values():
            rule["include"] = [g for g in rule["include"] if g != group_id]
            rule["exclude"] = [g for g in rule["exclude"] if g != group_id]
        doc["overrides"] = {k: v for k, v in doc["overrides"].items() if v["include"] or v["exclude"]}
        _save_device_groups(app.state.device_groups_path, doc)
        return {"ok": True}

    @app.get("/api/cameras")
    async def cameras() -> dict[str, list[dict[str, Any]]]:
        return {"cameras": _camera_cards(app.state.config_path, app.state.check_camera_ports)}

    @app.get("/api/home-assistant/cameras/{entity_id}/snapshot.jpg")
    async def home_assistant_camera_snapshot(entity_id: str) -> Response:
        return await asyncio.to_thread(_home_assistant_camera_snapshot, app.state.config_path, entity_id)

    @app.get("/api/home-assistant/cameras/{entity_id}/stream")
    async def home_assistant_camera_stream(entity_id: str) -> StreamingResponse:
        return _home_assistant_camera_stream(app.state.config_path, entity_id)

    @app.get("/api/alarm")
    async def alarm() -> dict[str, Any]:
        return await asyncio.to_thread(_alarm_payload, app.state.config_path)

    @app.post("/api/alarm/commands/{command}")
    async def alarm_command(command: str) -> dict[str, Any]:
        return await asyncio.to_thread(_home_assistant_alarm_command, app.state.config_path, command)

    @app.patch("/api/cameras/{camera_id}")
    async def update_camera(camera_id: str, update: CameraUpdateRequest) -> dict[str, Any]:
        name = update.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Camera name cannot be empty")
        if len(name) > 80:
            raise HTTPException(status_code=400, detail="Camera name is too long")
        camera_source = _rename_camera(app.state.config_path, camera_id, name)
        if camera_source == "tuya_camera":
            return _tuya_card(_find_tuya_device(_load_tuya_devices(app.state.config_path), camera_id), None)
        return _camera_card(_find_camera(_load_cameras(app.state.config_path), camera_id), app.state.check_camera_ports)

    @app.get("/api/tuya/devices")
    async def tuya_devices() -> dict[str, Any]:
        home_assistant_devices = await asyncio.to_thread(
            _tuya_cards_from_home_assistant, app.state.config_path, app.state.discovery_path
        )
        direct_devices = await _tuya_cards(app.state.config_path)
        if home_assistant_devices:
            supplements = _tuya_direct_sensor_supplements(direct_devices)
            return {"devices": home_assistant_devices + supplements, "source": "home_assistant"}
        return {"devices": direct_devices, "source": "direct"}

    @app.get("/api/ambient-lights")
    async def ambient_lights() -> dict[str, Any]:
        lights = _load_ambient_lights(app.state.config_path)
        await asyncio.to_thread(_refresh_ambient_live_state, lights)
        return {"lights": [_ambient_light_card(light) for light in lights]}

    @app.get("/api/ambient-lights/govee-ble/discover")
    async def ambient_govee_ble_discover() -> dict[str, Any]:
        return await asyncio.to_thread(_govee_ble_discovery_payload)

    @app.post("/api/ambient-lights/{light_id}/commands/{command}")
    async def ambient_light_command(light_id: str, command: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        light = _find_ambient_light(_load_ambient_lights(app.state.config_path), light_id)
        if command not in {"on", "off", "toggle", "brightness", "color"}:
            raise HTTPException(status_code=400, detail=f"Unsupported command: {command}")
        if light.provider == "alexa":
            raise HTTPException(status_code=501, detail="Lepro via Alexa needs an Alexa routine or bridge before dashboard commands can be sent.")
        if light.provider == "govee_lan":
            result = await asyncio.to_thread(_govee_lan_command_payload, light, command, body or {})
        elif light.provider != "govee_ble":
            raise HTTPException(status_code=400, detail=f"Unsupported ambient provider: {light.provider}")
        elif not light.address:
            raise HTTPException(status_code=400, detail="Govee BLE light needs a Bluetooth address from Pi discovery before it can be controlled.")
        else:
            result = await asyncio.to_thread(_govee_ble_command_payload, light, command, body or {})
        _save_ambient_runtime_state(app.state.config_path)
        return result

    @app.patch("/api/ambient-lights/{light_id}")
    async def update_ambient_light(light_id: str, update: AmbientLightUpdateRequest) -> dict[str, Any]:
        name = update.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Ambient light name cannot be empty")
        if len(name) > 80:
            raise HTTPException(status_code=400, detail="Ambient light name is too long")
        light = _rename_ambient_light(app.state.config_path, light_id, name)
        return _ambient_light_card(light)

    @app.get("/api/humidifiers")
    async def humidifiers() -> dict[str, Any]:
        return await asyncio.to_thread(_humidifier_cards, app.state.config_path)

    @app.get("/api/environment-sensors")
    async def environment_sensors() -> dict[str, Any]:
        return await asyncio.to_thread(_environment_sensor_cards, app.state.config_path)

    @app.post("/api/humidifiers/{humidifier_id}/commands/{command}")
    async def humidifier_command(
        humidifier_id: str, command: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            _humidifier_command_payload, app.state.config_path, humidifier_id, command, body or {}
        )

    @app.get("/api/weather")
    async def weather() -> dict[str, Any]:
        config = _load_weather_config(app.state.config_path)
        if not config:
            return {
                "status": "not_configured",
                "message": "Add weather latitude and longitude to configs/devices.local.yaml.",
            }
        return await asyncio.to_thread(_weather_payload, config)

    @app.get("/api/ecobee/thermostats")
    async def ecobee_thermostats() -> dict[str, Any]:
        return await asyncio.to_thread(_ecobee_payload, app.state.config_path)

    @app.get("/api/home-assistant/entities")
    async def home_assistant_entities() -> dict[str, Any]:
        return await asyncio.to_thread(_home_assistant_payload, app.state.config_path)

    @app.get("/api/network/devices")
    async def network_devices() -> dict[str, Any]:
        return await _connected_device_groups(app)

    @app.post("/api/network/devices/rescan")
    async def network_devices_rescan() -> dict[str, Any]:
        """Re-check every device now, and look for any that changed address.

        Asking explicitly overrides the automatic scan's rate limit: the point
        of the button is to act when the listing looks wrong, which is exactly
        when waiting out the interval is least useful.
        """
        await _rediscover_switch_hosts(app)
        app.state.rediscovery["at"] = time.monotonic()
        # Poll for real rather than serving what the cache already holds; the
        # addresses may have just been rewritten underneath it.
        await _refresh_device_cache(app)
        return await _connected_device_groups(app)

    @app.get("/api/bluetooth/devices")
    async def bluetooth_devices() -> dict[str, Any]:
        return await asyncio.to_thread(_bluetooth_devices_payload)

    @app.post("/api/bluetooth/scan")
    async def bluetooth_scan() -> dict[str, Any]:
        return await asyncio.to_thread(_bluetooth_scan_payload)

    @app.post("/api/bluetooth/devices/{mac}/connect")
    async def bluetooth_connect(mac: str) -> dict[str, Any]:
        if not _valid_bt_mac(mac):
            raise HTTPException(status_code=400, detail="Invalid Bluetooth address")
        return await asyncio.to_thread(_bluetooth_connect, mac)

    @app.post("/api/bluetooth/devices/{mac}/disconnect")
    async def bluetooth_disconnect(mac: str) -> dict[str, Any]:
        if not _valid_bt_mac(mac):
            raise HTTPException(status_code=400, detail="Invalid Bluetooth address")
        return await asyncio.to_thread(_bluetooth_disconnect, mac)

    @app.post("/api/home-assistant/entities/{entity_id}/commands/{command}")
    async def home_assistant_command(entity_id: str, command: str) -> dict[str, Any]:
        return await asyncio.to_thread(_home_assistant_service_command, app.state.config_path, entity_id, command)

    @app.post("/api/home-assistant/entities/{entity_id}/brightness")
    async def home_assistant_brightness(entity_id: str, body: dict[str, Any]) -> dict[str, Any]:
        level = int(body.get("level", 50))
        return await asyncio.to_thread(
            _home_assistant_brightness_command, app.state.config_path, entity_id, level
        )

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

    @app.post("/api/home-assistant/climate/{entity_id}")
    async def home_assistant_climate(entity_id: str, update: ClimateUpdateRequest) -> dict[str, Any]:
        return await asyncio.to_thread(_home_assistant_climate_update, app.state.config_path, entity_id, update)

    @app.post("/api/tuya/devices/{device_id}/commands/{command}")
    async def tuya_command(device_id: str, command: str) -> dict[str, Any]:
        device = _find_tuya_device(_load_tuya_devices(app.state.config_path), device_id)
        if command not in {"on", "off", "toggle"}:
            raise HTTPException(status_code=400, detail=f"Unsupported command: {command}")
        if not device.power_dp and not device.cloud_power_code:
            raise HTTPException(status_code=400, detail="Tuya device does not define a local or cloud power control")

        current = await asyncio.to_thread(_tuya_current_status, device)
        current_value = _tuya_power_value(current, device.power_dp)
        if current_value is None and device.cloud_power_code:
            cloud_value = _tuya_status_values(current).get(device.cloud_power_code)
            current_value = cloud_value if isinstance(cloud_value, bool) else None
        next_value = not current_value if command == "toggle" and current_value is not None else command == "on"
        await asyncio.to_thread(_tuya_set_power, device, next_value)
        return _tuya_card(device, await asyncio.to_thread(_tuya_current_status, device))

    @app.get("/api/cameras/{camera_id}/mjpeg")
    async def camera_mjpeg(camera_id: str) -> StreamingResponse:
        camera = _find_camera(_load_cameras(app.state.config_path), camera_id)
        if not camera.stream_url or not camera.stream_url.startswith(("rtsp://", "rtsps://")):
            raise HTTPException(status_code=400, detail="Camera does not have an RTSP stream URL")
        if not shutil.which("ffmpeg"):
            raise HTTPException(status_code=503, detail="ffmpeg is required for camera streaming")

        return StreamingResponse(
            _mjpeg_frames(camera.stream_url, camera),
            media_type="multipart/x-mixed-replace; boundary=frame",
            # Already-compressed JPEG frames, and gzip would buffer the stream.
            headers={"Content-Encoding": "identity"},
        )

    @app.get("/api/cameras/{camera_id}/snapshot.jpg")
    async def camera_snapshot(camera_id: str) -> Response:
        camera = _find_camera(_load_cameras(app.state.config_path), camera_id)

        # Prefer go2rtc, which reuses the session it already holds. Cameras like
        # the Wyze RTSP build serve one client at a time, so grabbing the still
        # with our own ffmpeg would open a competing session to the same camera.
        frame = await asyncio.to_thread(_capture_go2rtc_frame, camera)
        if not frame:
            if not camera.stream_url or not camera.stream_url.startswith(("rtsp://", "rtsps://")):
                raise HTTPException(status_code=400, detail="Camera does not have an RTSP stream URL")
            if not shutil.which("ffmpeg"):
                raise HTTPException(status_code=503, detail="ffmpeg is required for camera snapshots")
            frame = await asyncio.to_thread(_capture_rtsp_frame, camera.stream_url)

        return Response(
            frame,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store", "Content-Encoding": "identity"},
        )

    @app.post("/api/devices/{host}/commands/{command}")
    async def command(host: str, command: str) -> dict[str, Any]:
        switch = _find_switch(_load_switches(app.state.discovery_path), host)
        controller = app.state.controller

        try:
            if command == "on":
                state = await controller.turn_on(switch)
            elif command == "off":
                state = await controller.turn_off(switch)
            elif command == "toggle":
                state = await controller.toggle(switch)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported command: {command}")
        except HTTPException:
            raise
        except Exception as exc:
            raise _switch_command_error(switch.host, exc)

        _patch_device_cache(app, switch.host, state)
        return asdict(state)

    @app.post("/api/devices/{host}/brightness")
    async def set_brightness(host: str, body: dict[str, Any]) -> dict[str, Any]:
        level = int(body.get("level", 50))
        switch = _find_switch(_load_switches(app.state.discovery_path), host)
        try:
            state = await app.state.controller.set_brightness(switch, level)
        except Exception as exc:
            raise _switch_command_error(switch.host, exc)
        _patch_device_cache(app, switch.host, state)
        return asdict(state)

    @app.get("/api/zigbee/frontend")
    async def zigbee_frontend() -> dict[str, Any]:
        """Hand the dashboard what it needs to embed the Zigbee2MQTT web app.

        Zigbee2MQTT runs on its own port, so its UI is a cross-origin iframe and
        cannot reach the token the browser stored for that origin.  Its frontend
        accepts ?token= for exactly this case, so the token is returned here
        rather than baked into index.html - this route sits behind the same
        dashboard login as everything else.

        The port is returned instead of a whole URL because only the browser
        knows which address it reached the board on.
        """
        token = _zigbee_frontend_token(app.state.zigbee_secret_path)
        return {"available": token is not None, "port": ZIGBEE_FRONTEND_PORT, "token": token}

    @app.get("/api/zigbee/bridge")
    async def zigbee_bridge() -> dict[str, Any]:
        """State of the Zigbee coordinator itself, for the card on the Zigbee view.

        These are the entities deliberately kept out of the device grid by
        _is_zigbee_bridge_entity; this is where they surface instead.
        """
        return _zigbee_bridge_payload(app.state.config_path)

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
        except Exception as exc:
            _matter_log.debug("Matter Server unavailable: %s", exc)
            return {"devices": [], "matter_online": False, "error": str(exc)}

    @app.post("/api/matter/commission")
    async def _matter_commission(body: _MatterCommissionBody) -> dict:
        try:
            node_id = await _matter_client.commission(body.setup_code)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail=(
                    f"Commissioning timed out after {int(_matter_commission_timeout)} s. "
                    "Put the device back in pairing mode and try again."
                ),
            )
        except MatterServerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        _write_matter_device_to_config(node_id, body.name, body.room)
        meta_entry: dict = {"node_id": node_id, "name": body.name}
        if body.room:
            meta_entry["room"] = body.room
        _matter_device_meta[node_id] = meta_entry
        return {"node_id": node_id, "name": body.name}

    @app.post("/api/matter/devices/{node_id}/commands/{command}")
    async def _matter_command(
        node_id: int, command: str, brightness: int | None = None
    ) -> dict:
        try:
            await _matter_client.send_command(node_id, command, brightness=brightness)
            return {"status": "ok"}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.delete("/api/matter/devices/{node_id}")
    async def _matter_decommission(node_id: int) -> dict:
        try:
            await _matter_client.remove_node(node_id)
        except MatterServerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        _matter_device_meta.pop(node_id, None)
        _remove_matter_device_from_config(node_id)
        return {"status": "ok"}

    return app


async def _switch_status(
    app: FastAPI, switch: SwitchDefinition, limit: asyncio.Semaphore
) -> Any:
    """Poll one switch, giving up quickly so it cannot stall the whole page.

    Returns None when the switch does not answer in time; the caller renders
    that as an unknown state rather than failing the request.
    """
    failures = app.state.switch_failures
    try:
        async with limit:
            state = await asyncio.wait_for(
                app.state.controller.status(switch), timeout=SWITCH_STATUS_TIMEOUT
            )
    except Exception:
        count = failures.get(switch.host, 0) + 1
        failures[switch.host] = count
        # A power-cycled switch answers on a fresh connection but not on the
        # dead one we cached, so let go of that socket once the failures look
        # real. Waiting for a second failure keeps a slow-but-healthy switch
        # from being forced through a reconnect on every poll.
        forget = getattr(app.state.controller, "forget", None)
        if forget is not None and count >= SWITCH_EVICT_AFTER_FAILURES:
            try:
                await forget(switch.host)
            except Exception:
                pass
        # Reconnecting did not bring it back, so the switch may not be at this
        # address any more. Look for it by MAC instead of writing it off.
        if count >= SWITCH_REDISCOVER_AFTER_FAILURES:
            _schedule_switch_rediscovery(app)
        return None
    failures.pop(switch.host, None)
    return state


async def _device_cards(app: FastAPI) -> list[dict[str, Any]]:
    devices = _load_switches(app.state.discovery_path)

    # Poll every switch at once, and fetch the Home Assistant devices alongside
    # them, so the request costs as long as the slowest source rather than the
    # sum of all of them. gather preserves order, so cards stay in config order.
    limit = asyncio.Semaphore(SWITCH_POLL_CONCURRENCY)
    states, ha_cards = await asyncio.gather(
        asyncio.gather(*(_switch_status(app, device.switch, limit) for device in devices)),
        asyncio.to_thread(_home_assistant_device_cards, app.state.config_path),
    )

    cards: list[dict[str, Any]] = []
    for device, state in zip(devices, states):
        switch = device.switch
        is_on = state.is_on if state is not None else None
        brightness = state.brightness if state is not None else None

        # Keep bridge state cache fresh so GET /bridge/state/all is never stale.
        if is_on is not None:
            bridge_sync.update_state_cache(f"kasa:{switch.host}", {"on": is_on})

        cards.append(
            {
                "id": switch.host,
                "name": switch.name,
                "host": switch.host,
                "model": switch.model,
                "type": _friendly_type(device.device_type or switch.model),
                "category": _device_category(device.device_type or switch.model),
                "is_dimmable": "dimmer" in str(device.device_type or "").lower(),
                "room": _room_from_name(switch.name),
                "is_on": is_on,
                "brightness": brightness,
            }
        )
    cards.extend(ha_cards)
    return cards


async def _device_cards_cached(app: FastAPI) -> list[dict[str, Any]]:
    """Serve the last known device list immediately, refreshing behind it.

    A cold call polls for real, so the first load of a fresh process is
    accurate. After that the dashboard paints from cache while a background
    task re-polls, which trades up to DEVICE_CACHE_STALE_AFTER seconds of
    staleness for a response that no longer waits on the devices themselves.
    Commands patch the cache directly, so a switch the user just toggled never
    reads back stale.
    """
    cache = app.state.device_cache
    if cache["cards"] is None:
        # Nothing cached yet, so this one call has to wait - but share the poll
        # that startup already began rather than racing a second one against it.
        _schedule_device_refresh(app)
        await cache["task"]
        return cache["cards"] or []

    if time.monotonic() - cache["at"] >= DEVICE_CACHE_STALE_AFTER:
        _schedule_device_refresh(app)
    return cache["cards"]


def _schedule_device_refresh(app: FastAPI) -> None:
    """Start a background re-poll unless one is already in flight."""
    cache = app.state.device_cache
    task = cache.get("task")
    if task is not None and not task.done():
        return
    cache["task"] = asyncio.create_task(_refresh_device_cache(app))


async def _refresh_device_cache(app: FastAPI) -> None:
    try:
        cards = await _device_cards(app)
    except Exception:
        _matter_log.exception("Background device refresh failed; keeping previous cache")
        return
    app.state.device_cache["cards"] = cards
    app.state.device_cache["at"] = time.monotonic()


def _patch_device_cache(app: FastAPI, host: str, state: Any) -> None:
    """Fold a just-executed command into the cache.

    Without this the cached card would keep reporting the pre-command state
    until the next background refresh, and the toggle would look like it failed.
    """
    cards = app.state.device_cache.get("cards")
    if not cards:
        return
    for card in cards:
        if card.get("host") == host:
            card["is_on"] = state.is_on
            if state.brightness is not None:
                card["brightness"] = state.brightness
            break


_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _is_ip_host(host: Any) -> bool:
    """True for a real LAN address, false for ids like 'ha:...' or 'matter:1'."""
    return bool(_IPV4.match(str(host or "")))


async def _connected_device_groups(app: FastAPI) -> dict[str, Any]:
    """Every device the dashboard can address directly, grouped by how.

    Only devices with an address of their own are listed. Entities proxied
    through Home Assistant or Matter are deliberately left out: they have no
    IP or MAC to show, so a row for them would be an empty promise.
    """
    switches = [card for card in await _device_cards_cached(app) if _is_ip_host(card.get("host"))]
    cameras = [
        card
        for card in await asyncio.to_thread(
            _camera_cards, app.state.config_path, app.state.check_camera_ports
        )
        if _is_ip_host(card.get("host"))
    ]
    lights = await asyncio.to_thread(_load_ambient_lights, app.state.config_path)

    network = [
        {
            "name": card.get("name"),
            "address": card.get("host"),
            "detail": " · ".join(part for part in (card.get("model"), card.get("room")) if part),
            "icon": "ti-plug" if card.get("category") == "smart_plug" else "ti-bulb",
            # is_on is None when the switch did not answer its last poll.
            "online": card.get("is_on") is not None,
        }
        for card in switches
    ] + [
        {
            "name": card.get("name"),
            "address": card.get("host"),
            "detail": " · ".join(
                part for part in (card.get("model") or card.get("provider"), card.get("room")) if part
            ),
            "icon": "ti-camera",
            "online": card.get("status") == "ready",
        }
        for card in cameras
    ]

    bluetooth = [
        {
            "name": light.name,
            "address": light.address,
            "detail": " · ".join(
                part for part in (light.model, _AMBIENT_PROVIDER_LABELS.get(light.provider, light.provider)) if part
            ),
            "icon": "ti-bulb",
            "online": None,  # Ambient lights are write-only; reachability is unknown.
        }
        for light in lights
        if light.address
    ]

    # bluetoothctl can be slow or absent; a paired speaker is a bonus here, not
    # a reason to fail the whole listing.
    try:
        paired = await asyncio.to_thread(_bluetooth_devices_payload)
    except Exception:
        paired = {"status": "error", "devices": []}
    known = {str(item["address"]).upper() for item in bluetooth}
    for device in paired.get("devices") or []:
        if str(device.get("mac", "")).upper() in known:
            continue
        bluetooth.append(
            {
                "name": device.get("name"),
                "address": device.get("mac"),
                "detail": device.get("type") or "Bluetooth",
                "icon": "ti-bluetooth",
                "online": bool(device.get("connected")),
            }
        )

    return {
        "groups": [
            {"id": "network", "label": "Wi-Fi / Ethernet", "devices": network},
            {"id": "bluetooth", "label": "Bluetooth", "devices": bluetooth},
        ],
        "total": len(network) + len(bluetooth),
    }


def _schedule_switch_rediscovery(app: FastAPI) -> None:
    """Kick off a background scan for switches that moved, at most one at a time.

    A broadcast scan takes seconds, so it never runs inside a request: the poll
    that noticed the failure returns an unknown state immediately, and a later
    poll picks up the corrected address.
    """
    rediscovery = app.state.rediscovery
    task = rediscovery.get("task")
    if task is not None and not task.done():
        return
    if time.monotonic() - rediscovery["at"] < SWITCH_REDISCOVER_MIN_INTERVAL:
        return
    rediscovery["at"] = time.monotonic()
    rediscovery["task"] = asyncio.create_task(_rediscover_switch_hosts(app))


async def _rediscover_switch_hosts(app: FastAPI) -> None:
    """Re-point stored switches at the addresses their MACs answer on now."""
    path = app.state.discovery_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    switches = payload.get("switches") or []
    if not any(switch.get("mac") for switch in switches):
        # Nothing to match on; tplink_switches.json predates MAC recording.
        _matter_log.warning(
            "Skipping switch rediscovery: %s has no MAC addresses. "
            "Re-run scripts/discover_tplink_switches.py to record them.",
            path,
        )
        return

    try:
        found = await discover_hosts_by_mac()
    except Exception:
        _matter_log.exception("Switch rediscovery scan failed")
        return

    moves = apply_discovered_hosts(switches, found)
    if not moves:
        return

    payload["switches"] = switches
    try:
        _write_json_atomic(path, payload)
    except Exception:
        _matter_log.exception("Could not persist rediscovered switch addresses")
        return

    forget = getattr(app.state.controller, "forget", None)
    for name, old_host, new_host in moves:
        _matter_log.info("Switch %r moved from %s to %s", name, old_host, new_host)
        # Drop any connection and failure history filed under either address.
        for host in (old_host, new_host):
            app.state.switch_failures.pop(host, None)
            if forget is not None:
                try:
                    await forget(host)
                except Exception:
                    pass

    # The cached cards still carry the old addresses, so rebuild them now.
    await _refresh_device_cache(app)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write via a temp file so a crash cannot truncate the device list."""
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _load_switches(path: Path) -> list[DashboardDevice]:
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    devices = []
    for item in payload.get("switches", []):
        if not _is_supported_tplink_device(item):
            continue
        devices.append(
            DashboardDevice(
                switch=SwitchDefinition(
                    name=item.get("alias") or item["name"],
                    host=item["host"],
                    model=item.get("model"),
                ),
                device_type=item.get("device_type"),
            )
        )
    return devices


def _switch_command_error(host: str, exc: Exception) -> HTTPException:
    """Turn a Kasa control failure into an actionable HTTP error.

    Newer Kasa firmware (KLAP) rejects unauthenticated local control; without
    this the dashboard surfaces a bare 500 with no hint about credentials.
    """
    try:
        from kasa.exceptions import AuthenticationError
    except ImportError:
        AuthenticationError = ()  # type: ignore[assignment]

    cause: BaseException | None = exc
    while cause is not None:
        if isinstance(cause, AuthenticationError):
            return HTTPException(
                status_code=503,
                detail=(
                    f"Device {host} requires TP-Link account credentials (newer Kasa "
                    "firmware). Set TPLINK_USERNAME and TPLINK_PASSWORD in the "
                    "dashboard environment (.env) and restart the service."
                ),
            )
        cause = cause.__cause__ or cause.__context__
    return HTTPException(status_code=502, detail=f"Device {host} command failed: {exc}")


# Home Assistant signals dimming through supported_color_modes: every mode
# except "onoff" implies brightness support.  "unknown" is what HA reports
# before a light has been reached for the first time.
_HA_NON_DIMMING_COLOR_MODES = {"onoff", "unknown"}
_HA_MAX_BRIGHTNESS = 255


def _home_assistant_supports_brightness(
    entity_id: str | None, attributes: dict[str, Any]
) -> bool:
    """Whether an HA entity can be dimmed.

    Only the light domain dims — a switch is on/off however capable the
    hardware behind it is.
    """
    if _home_assistant_entity_domain(entity_id) != "light":
        return False
    modes = attributes.get("supported_color_modes")
    if isinstance(modes, (list, tuple)) and any(
        str(mode).lower() not in _HA_NON_DIMMING_COLOR_MODES for mode in modes
    ):
        return True
    # Older integrations omit supported_color_modes; a live brightness reading
    # is proof enough.  It is absent while the light is off, so this can only
    # ever add capability, never remove it.
    return attributes.get("brightness") is not None


def _home_assistant_brightness_percent(attributes: dict[str, Any]) -> int | None:
    """Convert HA's 0–255 brightness to the dashboard's percent scale.

    Returns None when the light is off — HA drops the attribute entirely then.
    """
    raw = attributes.get("brightness")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, round(value / _HA_MAX_BRIGHTNESS * 100)))


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
        # Bridge controls belong to the Zigbee view, not the device grid. Filter
        # here as well as at confirmation time, because an entry added before
        # this existed is still sitting in devices.local.yaml.
        if _is_zigbee_bridge_entity(entity_id):
            continue
        state_entity = states_by_id.get(entity_id)
        attributes: dict[str, Any] = (state_entity or {}).get("attributes") or {}
        cards.append(
            {
                "id": entity_id,
                "name": entry.get("name") or entity_id,
                "host": f"ha:{entity_id}",
                "model": "Home Assistant",
                "type": "Home Assistant",
                "category": entry.get("category") or "light_switch",
                "is_dimmable": _home_assistant_supports_brightness(entity_id, attributes),
                "room": entry.get("room") or "",
                "is_on": {"on": True, "off": False}.get(state_entity.get("state")) if state_entity else None,
                "brightness": _home_assistant_brightness_percent(attributes),
            }
        )
    return cards


def _camera_cards(path: Path, check_ports: bool = True) -> list[dict[str, Any]]:
    cards = [_camera_card(camera, check_ports) for camera in _load_cameras(path)]
    cards.extend(_home_assistant_camera_cards(path))
    return _dedupe_camera_cards(cards)


def _dedupe_camera_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for card in cards:
        key = str(card.get("id") or card.get("host") or card.get("name"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
    return deduped


def _home_assistant_camera_cards(path: Path) -> list[dict[str, Any]]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        return []
    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception:
        return []

    cards = []
    for entity in states:
        entity_id = str(entity.get("entity_id") or "")
        if _home_assistant_entity_domain(entity_id) != "camera":
            continue
        attributes = entity.get("attributes") or {}
        name = str(attributes.get("friendly_name") or entity_id)
        is_doorbell = _is_doorbell_camera(entity_id, name)
        cards.append(
            {
                "id": entity_id,
                "entity_id": entity_id,
                "name": name,
                "host": "Home Assistant",
                "provider": "home_assistant",
                "model": "Doorbell camera" if is_doorbell else "Tuya camera",
                "room": _room_from_name(name),
                "snapshot_url": f"/api/home-assistant/cameras/{quote(entity_id, safe='')}/snapshot.jpg",
                "stream_url": None,
                "view_url": f"/api/home-assistant/cameras/{quote(entity_id, safe='')}/stream",
                "view_type": "doorbell" if is_doorbell else "mjpeg",
                "requires_proxy": False,
                "status": "ready" if entity.get("state") not in {"unavailable", "unknown", None} else "unavailable",
                "status_detail": "Home Assistant camera entity is available.",
                "stream_name": entity_id,
                "webrtc_url": None,
                "hls_url": None,
                "battery": _home_assistant_camera_battery(name, states),
                "battery_powered": is_doorbell or _home_assistant_camera_battery(name, states) is not None,
                "signal": 2,
                "events": _home_assistant_camera_events(name, states),
            }
        )
    return cards


def _is_doorbell_camera(entity_id: str, name: str) -> bool:
    text = f"{entity_id} {name}".lower()
    return "doorbell" in text or "门铃" in text or "men_ling" in text


def _home_assistant_camera_battery(name: str, states: list[dict[str, Any]]) -> int | None:
    camera_name = name.lower()
    for entity in states:
        entity_id = str(entity.get("entity_id") or "").lower()
        attributes = entity.get("attributes") or {}
        friendly = str(attributes.get("friendly_name") or "").lower()
        if "battery" not in entity_id and "battery" not in friendly:
            continue
        if camera_name and camera_name in friendly:
            try:
                return _normalize_battery_percent(float(entity.get("state")), entity_id, friendly)
            except (TypeError, ValueError):
                return None
    return None


def _normalize_battery_percent(value: float, entity_id: str, friendly_name: str) -> int:
    normalized = max(0, min(100, value))
    text = f"{entity_id} {friendly_name}".lower()
    if normalized <= 10 and ("tuya" in text or "doorbell" in text or "men_ling" in text or "门铃" in text):
        normalized *= 10
    return int(round(max(0, min(100, normalized))))


def _home_assistant_camera_events(name: str, states: list[dict[str, Any]]) -> list[dict[str, str]]:
    camera_name = name.lower()
    events = []
    for entity in states:
        entity_id = str(entity.get("entity_id") or "")
        attributes = entity.get("attributes") or {}
        friendly = str(attributes.get("friendly_name") or entity_id)
        haystack = f"{entity_id} {friendly}".lower()
        if _home_assistant_entity_domain(entity_id) != "event":
            continue
        if camera_name and camera_name.lower() not in haystack:
            continue
        events.append({"type": "ring" if "doorbell" in haystack else "motion", "label": friendly, "time": "Home Assistant"})
    return events


def _home_assistant_camera_snapshot(path: Path, entity_id: str) -> Response:
    config, token = _home_assistant_auth(path)
    payload, content_type = _home_assistant_camera_fetch(config, token, f"/api/camera_proxy/{entity_id}")
    return Response(
        payload,
        media_type=content_type or "image/jpeg",
        headers={"Cache-Control": "no-store", "Content-Encoding": "identity"},
    )


def _home_assistant_camera_stream(path: Path, entity_id: str) -> StreamingResponse:
    config, token = _home_assistant_auth(path)
    request = _URLRequest(
        f"{config.base_url}/api/camera_proxy_stream/{entity_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    response = urlopen(request, timeout=20)
    media_type = response.headers.get("Content-Type") or "multipart/x-mixed-replace"

    def chunks() -> Iterator[bytes]:
        with response:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        chunks(),
        media_type=media_type,
        headers={"Cache-Control": "no-store", "Content-Encoding": "identity"},
    )


def _home_assistant_camera_fetch(config: HomeAssistantConfig, token: str, ha_path: str) -> tuple[bytes, str | None]:
    request = _URLRequest(
        f"{config.base_url}{ha_path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=20) as response:
        return response.read(), response.headers.get("Content-Type")


def _home_assistant_auth(path: Path) -> tuple[HomeAssistantConfig, str]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        raise HTTPException(status_code=503, detail=f"{config.token_env} is not configured")
    return config, token
def _load_cameras(path: Path) -> list[CameraDefinition]:
    if not path.exists():
        return []

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cameras = []
    raw_cameras = []
    raw_cameras.extend(payload.get("tplink", {}).get("cameras", []))
    raw_cameras.extend(payload.get("cameras", []))
    for item in raw_cameras:
        go2rtc_url = None
        if item.get("go2rtc_enabled") is not False:
            go2rtc_url = item.get("go2rtc_url") or payload.get("media_gateway", {}).get("go2rtc_url")
        cameras.append(
            CameraDefinition(
                name=str(item["name"]),
                host=str(item["host"]),
                provider=str(item.get("provider") or "tplink"),
                model=item.get("model"),
                room=item.get("room"),
                snapshot_url=item.get("snapshot_url"),
                stream_url=item.get("stream_url") or _rtsp_url_from_config(item),
                view_url=item.get("view_url"),
                mjpeg_fps=int(item.get("mjpeg_fps", 10)),
                mjpeg_width=int(item.get("mjpeg_width", 640)),
                mjpeg_quality=int(item.get("mjpeg_quality", 7)),
                stream_name=str(item.get("stream_name") or _stream_name(item["name"])),
                go2rtc_url=go2rtc_url,
                battery_powered=bool(item.get("battery_powered", False)),
            )
        )
    return cameras


def _rename_camera(path: Path, camera_id: str, name: str) -> str:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Camera not found: {camera_id}")

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    camera_sections = [
        payload.get("tplink", {}).get("cameras", []),
        payload.get("cameras", []),
    ]
    for section in camera_sections:
        for item in section:
            if _config_camera_matches(item, camera_id):
                item["name"] = name
                path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
                return "camera"

    for item in payload.get("tuya", {}).get("devices", []):
        if item.get("enabled") is False:
            continue
        category = str(item.get("category") or "").lower()
        if category == "tuya_camera" and _config_camera_matches(item, camera_id):
            item["name"] = name
            path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            return "tuya_camera"

    raise HTTPException(status_code=404, detail=f"Camera not found: {camera_id}")


def _config_camera_matches(item: dict[str, Any], camera_id: str) -> bool:
    values = [
        item.get("host"),
        item.get("name"),
        item.get("stream_name"),
        item.get("device_id"),
        item.get("id"),
    ]
    return any(str(value) == camera_id for value in values if value is not None)


async def _tuya_cards(path: Path) -> list[dict[str, Any]]:
    devices = _load_tuya_devices(path)
    cloud_semaphore = asyncio.Semaphore(4)
    return await asyncio.gather(*[_tuya_card_async(device, cloud_semaphore) for device in devices])


def _tuya_direct_sensor_supplements(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [card for card in cards if _is_tuya_direct_sensor_supplement(card)]


def _is_tuya_direct_sensor_supplement(card: dict[str, Any]) -> bool:
    category = str(card.get("category") or "").lower()
    if "camera" in category or "alarm" in category or "switch" in category or "light" in category:
        return False
    values = card.get("values")
    if not isinstance(values, dict) or not values:
        return False
    metric_terms = (
        "temperature",
        "temp",
        "humidity",
        "illuminance",
        "lux",
        "motion",
        "occupancy",
        "presence",
        "pir",
    )
    text = " ".join(str(key).lower() for key in values)
    return any(term in text for term in metric_terms)


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


def _tplink_device_names(discovery_path: Path | None) -> set[str]:
    """Return lowercase friendly names of TP-Link switches/plugs to exclude from the Tuya sensor view."""
    if not discovery_path or not discovery_path.exists():
        return set()
    try:
        payload = json.loads(discovery_path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for item in payload.get("switches", []):
            alias = str(item.get("alias") or item.get("name") or "").strip()
            if alias and not alias.startswith("192.") and not alias.startswith("10.") and not alias.startswith("172."):
                names.add(alias.lower())
        return names
    except Exception:
        return set()


def _is_npu_vision_entity(entity_id: str | None) -> bool:
    """Is this one of the NPU camera detector's own entities?

    src/python/npu_detector.py publishes them over MQTT discovery with a device
    named "<Camera> (NPU)", so Home Assistant derives ids like
    binary_sensor.front_door_camera_npu_person. They belong to the Zigbee-style
    "our own service" category rather than to any vendor integration, and in
    particular they are not cameras - they are what a camera detected.

    Matched on the entity_id rather than an attribute because /api/states
    exposes no origin or device information to filter on.
    """
    return "_npu_" in str(entity_id or "").lower()


def _is_tuya_home_assistant_entity(
    entity: dict[str, Any],
    tplink_names: set[str] | None = None,
    confirmed_entity_ids: set[str] | None = None,
) -> bool:
    entity_id = str(entity.get("entity_id") or "")
    if confirmed_entity_ids and entity_id in confirmed_entity_ids:
        return False
    # Our own camera detections are not Tuya devices. Left in, their occupancy
    # device_class puts them in this list, and because their names contain
    # "camera" the front end's isTuyaCamera() then renders them as camera cards
    # on the Cameras view - three phantom cameras reading "stream not
    # configured". Same reasoning as _is_zigbee_bridge_entity.
    if _is_npu_vision_entity(entity_id):
        return False
    domain = _home_assistant_entity_domain(entity_id)
    if domain not in {"light", "switch", "sensor", "binary_sensor", "cover", "fan", "lock"}:
        return False
    attributes = entity.get("attributes") or {}
    name = str(attributes.get("friendly_name") or entity_id).lower()
    entity_text = entity_id.lower()
    ignored_prefixes = (
        "sensor.iphone_",
        "sensor.backup_",
        "sensor.sun_",
    )
    ignored_terms = (
        "ecobee",
        "camera flip",
        "motion alarm",
        "motion recording",
        "motion tracking",
        "privacy mode",
        "time watermark",
        "video recording",
        "use motion detection zone",
        "arm beep",
        "siren",
    )
    if any(entity_text.startswith(prefix) for prefix in ignored_prefixes):
        return False
    if any(term in name or term.replace(" ", "_") in entity_text for term in ignored_terms):
        return False
    # Exclude TP-Link devices (they appear in Lights / Plugs view instead)
    if tplink_names:
        for tplink_name in tplink_names:
            # Match exact name or names derived from a TP-Link device (e.g. "Kitchen light switch LED")
            if name == tplink_name or name.startswith(tplink_name + " ") or name.startswith(tplink_name + "_"):
                return False
    device_class = str(attributes.get("device_class") or "").lower()
    useful_sensor_classes = {"battery", "humidity", "temperature", "illuminance", "moisture", "door", "occupancy", "smoke", "tamper", "problem"}
    if domain in {"sensor", "binary_sensor"} and device_class in useful_sensor_classes:
        return True
    if domain in {"light", "cover", "fan", "lock"}:
        return True
    if domain == "switch":
        return "camera" not in name and "doorbell" not in name and "men_ling" not in entity_text
    return False


def _tuya_home_assistant_card(entity: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(entity.get("entity_id") or "")
    domain = _home_assistant_entity_domain(entity_id)
    attributes = entity.get("attributes") or {}
    name = str(attributes.get("friendly_name") or entity_id)
    state = entity.get("state")
    unit = attributes.get("unit_of_measurement")
    category = _home_assistant_tuya_category(domain, attributes)
    value = _home_assistant_display_value(state, unit)
    is_on = state == "on" if domain in {"light", "switch", "fan"} else None
    return {
        "id": entity_id,
        "entity_id": entity_id,
        "domain": domain,
        "name": name,
        "host": "Home Assistant",
        "model": attributes.get("device_class") or domain,
        "device_class": attributes.get("device_class"),
        "type": _friendly_tuya_category(category),
        "category": category,
        "room": _room_from_name(name),
        "is_on": is_on,
        "state": state,
        "online": state not in {"unavailable", "unknown", None},
        "status": "online" if state not in {"unavailable", "unknown", None} else "unavailable",
        "source": "home_assistant",
        "values": {"State": value} if domain not in {"light", "switch", "fan"} else {},
        "controllable": domain in {"light", "switch", "fan"},
    }


def _home_assistant_tuya_category(domain: str, attributes: dict[str, Any]) -> str:
    device_class = str(attributes.get("device_class") or "").lower()
    if domain == "light":
        return "tuya_light"
    if domain == "switch":
        return "tuya_switch"
    if domain == "binary_sensor":
        return f"tuya_{device_class or 'binary_sensor'}"
    if domain == "sensor":
        return f"tuya_{device_class or 'sensor'}"
    return f"tuya_{domain}"


def _home_assistant_display_value(state: Any, unit: Any) -> Any:
    if state in {None, ""}:
        return "unknown"
    if unit:
        return f"{state} {unit}".strip()
    return state


async def _tuya_card_async(device: TuyaDefinition, cloud_semaphore: asyncio.Semaphore | None = None) -> dict[str, Any]:
    status_payload = None
    source = None
    if device.host and device.local_key:
        try:
            status_payload = await asyncio.wait_for(asyncio.to_thread(_tuya_status, device), timeout=2.5)
            source = "local"
        except Exception:
            status_payload = None
    if status_payload is None and cloud_semaphore is not None:
        try:
            async with cloud_semaphore:
                status_payload = await asyncio.wait_for(asyncio.to_thread(_tuya_cloud_status, device), timeout=12)
                if status_payload is not None:
                    source = "cloud"
        except Exception:
            status_payload = None
    return _tuya_card(device, status_payload, source)


def _load_ambient_lights(path: Path) -> list[AmbientLightDefinition]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices = []
    for item in (payload.get("ambient_lights") or {}).get("devices") or []:
        if item.get("enabled") is False:
            continue
        name = str(item.get("name") or item.get("id") or item.get("model") or "Ambient light")
        provider = str(item.get("provider") or "manual").lower()
        devices.append(
            AmbientLightDefinition(
                name=name,
                provider=provider,
                model=str(item.get("model")) if item.get("model") else None,
                room=item.get("room"),
                address=str(item.get("address") or item.get("mac") or "") or None,
                alexa_name=str(item.get("alexa_name") or item.get("alexa_device") or "") or None,
            )
        )
    return devices


def _load_humidifiers(path: Path) -> list[HumidifierDefinition]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices = []
    for item in (payload.get("humidifiers") or {}).get("devices") or []:
        if item.get("enabled") is False:
            continue
        name = str(item.get("name") or item.get("id") or item.get("model") or "Humidifier")
        provider = str(item.get("provider") or "govee_cloud").lower()
        unit = str(item.get("temperature_unit") or "C").strip().upper()
        devices.append(
            HumidifierDefinition(
                name=name,
                provider=provider,
                model=str(item.get("model")) if item.get("model") else None,
                room=item.get("room"),
                device_id=str(item.get("device_id") or "") or None,
                thermometer_device_id=str(item.get("thermometer_device_id") or "") or None,
                thermometer_model=str(item.get("thermometer_model") or "") or None,
                temperature_unit="F" if unit.startswith("F") else "C",
            )
        )
    return devices


def _load_environment_sensors(path: Path) -> list[EnvironmentSensorDefinition]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sensors = []
    for item in (payload.get("environment") or {}).get("sensors") or []:
        if item.get("enabled") is False:
            continue
        sensors.append(
            EnvironmentSensorDefinition(
                name=str(item.get("name") or item.get("model") or "Environment sensor"),
                provider=str(item.get("provider") or "govee_cloud").lower(),
                model=str(item.get("model")) if item.get("model") else None,
                room=item.get("room"),
                device_id=str(item.get("device_id") or "") or None,
            )
        )
    return sensors


def _ambient_light_id(light: AmbientLightDefinition) -> str:
    return quote(light.name, safe="")


def _is_real_ble_address(address: str | None) -> bool:
    if not address:
        return False
    value = address.strip().lower()
    return value not in {"replace_me", "todo", "none", "null", "unknown"}


# How each ambient provider is described in the connected-devices listing.
_AMBIENT_PROVIDER_LABELS = {
    "govee_ble": "Govee BLE",
    # Reached over Wi-Fi, but Govee exposes only a MAC, so it is listed beside
    # the MAC-addressed devices rather than the ones with an IP.
    "govee_lan": "Govee LAN (Wi-Fi)",
    "alexa": "Alexa",
}


def _ambient_light_card(light: AmbientLightDefinition) -> dict[str, Any]:
    runtime_state = AMBIENT_LIGHT_RUNTIME_STATE.get(light.address or light.name, {})
    if light.provider == "govee_ble":
        has_address = _is_real_ble_address(light.address)
        status = "configured" if has_address else "needs_ble_address"
        note = "BLE address configured" if has_address else "Run Govee BLE discovery on the Orange Pi and add the address."
        controllable = has_address
    elif light.provider == "govee_lan":
        has_id = _is_real_ble_address(light.address) or bool(light.model)
        status = "configured" if has_id else "needs_lan_setup"
        note = (
            "Govee LAN control over Wi-Fi."
            if has_id
            else "Enable LAN Control in the Govee app and set the device model/address."
        )
        controllable = has_id
    elif light.provider == "alexa":
        status = "needs_alexa_bridge"
        note = "Lepro is reachable from Alexa, but dashboard control needs an Alexa routine/bridge path."
        controllable = False
    else:
        status = "unsupported"
        note = "Unsupported ambient light provider."
        controllable = False
    supports_full = controllable and light.provider in ("govee_ble", "govee_lan")
    return {
        "id": light.name,
        "name": light.name,
        "provider": light.provider,
        "model": light.model,
        "room": light.room,
        "address": light.address,
        "alexa_name": light.alexa_name,
        "status": status,
        "note": note,
        "controllable": controllable,
        "is_on": runtime_state.get("is_on"),
        "brightness": runtime_state.get("brightness"),
        "color": runtime_state.get("color"),
        "capabilities": {
            "power": supports_full,
            "brightness": supports_full,
            "color": supports_full,
        },
    }


def _ambient_light_cards(path: Path) -> list[dict[str, Any]]:
    return [_ambient_light_card(light) for light in _load_ambient_lights(path)]


def _refresh_ambient_live_state(lights: list[AmbientLightDefinition]) -> None:
    """Update the runtime-state cache with real status from live-readable providers."""
    for light in lights:
        if light.provider == "govee_lan":
            status = _govee_lan_status(light)
            if status is not None:
                AMBIENT_LIGHT_RUNTIME_STATE[light.address or light.name] = status


def _rename_ambient_light(path: Path, light_id: str, name: str) -> AmbientLightDefinition:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Ambient light not found: {light_id}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for item in payload.get("ambient_lights", {}).get("devices", []):
        item_name = str(item.get("name") or item.get("id") or item.get("model") or "")
        if item_name == light_id or quote(item_name, safe="") == light_id:
            item["name"] = name
            path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            return _find_ambient_light(_load_ambient_lights(path), quote(name, safe=""))
    raise HTTPException(status_code=404, detail=f"Ambient light not found: {light_id}")


# ── Govee LAN (Wi-Fi) control ──
# Newer Govee models (e.g. H6076) ignore the legacy BLE 0x33 protocol but expose
# Govee's documented LAN API: a multicast scan on :4001 (replies on :4002) and
# JSON commands sent by unicast UDP to the device on :4003.
GOVEE_LAN_MCAST = "239.255.255.250"
GOVEE_LAN_SCAN_PORT = 4001
GOVEE_LAN_RECV_PORT = 4002
GOVEE_LAN_CMD_PORT = 4003
_GOVEE_LAN_IP_CACHE: dict[str, str] = {}


def _govee_lan_command_json(command: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    if command == "on":
        return {"msg": {"cmd": "turn", "data": {"value": 1}}}
    if command == "off":
        return {"msg": {"cmd": "turn", "data": {"value": 0}}}
    if command == "brightness":
        value = _bounded_byte(body.get("brightness", body.get("value", 100)), minimum=1, maximum=100)
        return {"msg": {"cmd": "brightness", "data": {"value": value}}}
    if command == "color":
        red = _bounded_byte(body.get("red", body.get("r", 255)))
        green = _bounded_byte(body.get("green", body.get("g", 255)))
        blue = _bounded_byte(body.get("blue", body.get("b", 255)))
        return {"msg": {"cmd": "colorwc", "data": {"color": {"r": red, "g": green, "b": blue}, "colorTemInKelvin": 0}}}
    raise HTTPException(status_code=400, detail=f"Unsupported Govee LAN command: {command}")


def _govee_lan_scan(timeout: float = 3.0) -> dict[str, dict[str, Any]]:
    """Return {ip: scan_data} for Govee devices with LAN Control enabled."""
    devices: dict[str, dict[str, Any]] = {}
    recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        recv.bind(("0.0.0.0", GOVEE_LAN_RECV_PORT))
        recv.settimeout(timeout)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        try:
            request = json.dumps({"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}).encode()
            sender.sendto(request, (GOVEE_LAN_MCAST, GOVEE_LAN_SCAN_PORT))
        finally:
            sender.close()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = recv.recvfrom(2048)
            except socket.timeout:
                break
            try:
                payload = json.loads(data).get("msg", {}).get("data", {})
            except (ValueError, AttributeError):
                continue
            if payload.get("sku"):
                devices[addr[0]] = payload
    finally:
        recv.close()
    return devices


def _govee_lan_resolve_ip(light: AmbientLightDefinition, force: bool = False) -> str | None:
    """Find the device's current LAN IP by scanning, matching on device id or model."""
    key = light.address or light.name
    if not force and key in _GOVEE_LAN_IP_CACHE:
        return _GOVEE_LAN_IP_CACHE[key]
    target = (light.address or "").replace(":", "").lower()
    model = str(light.model or "").upper()
    for ip, data in _govee_lan_scan().items():
        device_id = str(data.get("device", "")).replace(":", "").lower()
        sku = str(data.get("sku", "")).upper()
        if target and device_id.endswith(target):
            _GOVEE_LAN_IP_CACHE[key] = ip
            return ip
        if not target and model and sku == model:
            _GOVEE_LAN_IP_CACHE[key] = ip
            return ip
    return None


def _govee_lan_send(ip: str, message: dict[str, Any]) -> None:
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sender.sendto(json.dumps(message).encode(), (ip, GOVEE_LAN_CMD_PORT))
    finally:
        sender.close()


def _govee_lan_command_payload(light: AmbientLightDefinition, command: str, body: dict[str, Any]) -> dict[str, Any]:
    if command == "toggle":
        raise HTTPException(status_code=400, detail="Govee LAN toggle needs device state support; use on or off.")
    message = _govee_lan_command_json(command, body)
    ip = _govee_lan_resolve_ip(light)
    if not ip:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Govee LAN device '{light.name}' was not found on the network. "
                "Confirm it is on 2.4GHz Wi-Fi and that LAN Control is enabled in the Govee app."
            ),
        )
    try:
        _govee_lan_send(ip, message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Govee LAN command failed for {light.name}: {exc}") from exc
    _remember_ambient_light_command(light, command, body)
    return {"status": "ok", "name": light.name, "ip": ip, "command": command, "light": _ambient_light_card(light)}


def _govee_lan_status(light: AmbientLightDefinition, timeout: float = 1.0) -> dict[str, Any] | None:
    """Query a Govee LAN device's real state (devStatus). Returns None if unreachable."""
    ip = _govee_lan_resolve_ip(light)
    if not ip:
        return None
    recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        recv.bind(("0.0.0.0", GOVEE_LAN_RECV_PORT))
        recv.settimeout(timeout)
        _govee_lan_send(ip, {"msg": {"cmd": "devStatus", "data": {}}})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = recv.recvfrom(2048)
            except socket.timeout:
                break
            if addr[0] != ip:
                continue
            try:
                message = json.loads(data).get("msg", {})
            except (ValueError, AttributeError):
                continue
            if message.get("cmd") != "devStatus":
                continue
            payload = message.get("data", {})
            return {
                "is_on": bool(payload.get("onOff")),
                "brightness": payload.get("brightness"),
                "color": payload.get("color"),
            }
    except OSError:
        return None
    finally:
        recv.close()
    return None


def _find_ambient_light(lights: list[AmbientLightDefinition], light_id: str) -> AmbientLightDefinition:
    decoded = light_id
    for light in lights:
        if light.name == decoded or _ambient_light_id(light) == decoded:
            return light
    raise HTTPException(status_code=404, detail=f"Ambient light not found: {light_id}")


def _govee_ble_discovery_payload() -> dict[str, Any]:
    try:
        from bleak import BleakScanner  # type: ignore
    except Exception as exc:
        return {
            "status": "bleak_missing",
            "message": "Install bleak on the Orange Pi to scan Govee Bluetooth devices.",
            "error": str(exc),
            "devices": [],
        }

    async def _scan() -> list[dict[str, Any]]:
        found = await BleakScanner.discover(timeout=8.0, **_ble_kwargs())
        devices = []
        for item in found:
            name = item.name or ""
            text = f"{name} {item.address}".lower()
            if "govee" not in text and "h613a" not in text and "h6054" not in text:
                continue
            devices.append({"name": name, "address": item.address, "rssi": getattr(item, "rssi", None)})
        return devices

    return {"status": "ok", "devices": asyncio.run(_scan())}


# ── Govee Cloud (Developer API v2) — humidifiers ──
# Govee humidifiers (e.g. H7140) do not speak the LAN or BLE light protocols;
# control goes through the cloud API with a per-account key (GOVEE_API_KEY).
# Capabilities are discovered from the device list at runtime, not hardcoded.
GOVEE_CLOUD_BASE = "https://openapi.api.govee.com"
GOVEE_CLOUD_DEVICE_CACHE_TTL = 600.0
_GOVEE_CLOUD_CACHE: dict[str, Any] = {"devices": None, "fetched": 0.0}
# Last-known state keyed by configured device_id (or humidifier name if device_id is unset),
# served when the cloud is unreachable.
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
        payload = json.loads(response.read().decode("utf-8"))
    code = payload.get("code")
    if code is not None and int(code) != 200:
        raise RuntimeError(f"Govee API error {code}: {payload.get('message') or 'unknown error'}")
    return payload


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
                "requestId": "smart-home-ai",
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
        elif instance == "nightlightToggle":
            state["nightlight_on"] = value == 1
        elif instance == "brightness" and isinstance(value, (int, float)):
            state["nightlight_brightness"] = int(value)
        elif instance == "colorRgb" and isinstance(value, (int, float)):
            state["nightlight_color"] = int(value)
        elif instance == "nightlightScene" and isinstance(value, (int, float)):
            state["nightlight_scene"] = int(value)
    return state


def _device_has_instance(entry: dict[str, Any], instance: str) -> bool:
    return any(cap.get("instance") == instance for cap in entry.get("capabilities") or [])


def _match_govee_thermometer(
    humidifier: HumidifierDefinition, devices: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Resolve the linked thermometer, trying three stages in order:

    1. humidifier.thermometer_device_id, if it's a real (non-placeholder) id.
    2. humidifier.thermometer_model, if exactly one device on the account has
       that sku.
    3. Fallback: the account's sole ambient-humidity sensor. When more than
       one humidity sensor exists, sensors that also report
       carbonDioxideConcentration are excluded first (a CO2 combo monitor,
       e.g. the H5140, shouldn't out-compete a plain thermo-hygrometer for
       this fallback).

    That fallback only resolves unambiguously when the account has exactly
    one humidity sensor, or when every *extra* humidity sensor also reports
    CO2. Two plain (non-CO2) humidity sensors on the same account defeat it
    and the linked temperature/humidity readout silently disappears from the
    card — see
    test_humidifiers.py::test_thermometer_fallback_is_ambiguous_with_two_non_co2_sensors.
    Pin thermometer_device_id (or thermometer_model) so the lookup does not
    depend on that tie-break holding; see
    test_humidifiers.py::test_pinned_thermometer_device_id_is_unambiguous,
    test_humidifiers.py::test_pinned_thermometer_model_is_unambiguous, and
    test_humidifiers.py::test_co2_tiebreak_resolves_real_account_pair (which
    guards the CO2 tie-break itself against future regression).
    """
    if _is_real_ble_address(humidifier.thermometer_device_id):
        for entry in devices:
            if str(entry.get("device") or "").lower() == humidifier.thermometer_device_id.lower():
                return entry
    if humidifier.thermometer_model:
        matches = [e for e in devices if str(e.get("sku") or "").upper() == humidifier.thermometer_model.upper()]
        if len(matches) == 1:
            return matches[0]
    sensors = [e for e in devices if _device_has_instance(e, "sensorHumidity")]
    if len(sensors) > 1:
        # Multiple humidity sensors (e.g. a thermo-hygrometer and a CO2 monitor):
        # prefer the plain thermo-hygrometer that doesn't also measure CO2.
        pure = [e for e in sensors if not _device_has_instance(e, "carbonDioxideConcentration")]
        sensors = pure or sensors
    if len(sensors) == 1:
        return sensors[0]
    return None


def _govee_thermometer_reading(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Ambient humidity (%) and temperature (°F, as Govee reports it) from a sensor."""
    try:
        payload = _govee_cloud_request(
            "/router/api/v1/device/state",
            {"requestId": "smart-home-ai", "payload": {"sku": entry.get("sku"), "device": entry.get("device")}},
        )
    except Exception:
        return None
    reading: dict[str, Any] = {}
    for cap in (payload.get("payload") or {}).get("capabilities") or []:
        instance = cap.get("instance")
        value = (cap.get("state") or {}).get("value")
        if instance == "sensorHumidity" and isinstance(value, (int, float)):
            reading["humidity"] = float(value)
        elif instance == "sensorTemperature" and isinstance(value, (int, float)):
            reading["temperature_f"] = float(value)
    return reading or None


ENVIRONMENT_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _match_environment_sensor(
    sensor: EnvironmentSensorDefinition, devices: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Explicit device id wins; otherwise match a unique model. No account-wide
    fallback — that ambiguity is what breaks the humidifier's linked thermometer."""
    if _is_real_ble_address(sensor.device_id):
        for entry in devices:
            if str(entry.get("device") or "").lower() == sensor.device_id.lower():
                return entry
        return None
    if sensor.model:
        matches = [e for e in devices if str(e.get("sku") or "").upper() == sensor.model.upper()]
        if len(matches) == 1:
            return matches[0]
    return None


def _fahrenheit_to_celsius(value: float) -> float:
    return round((value - 32.0) * 5.0 / 9.0, 1)


def _environment_sensor_card(sensor: EnvironmentSensorDefinition) -> dict[str, Any]:
    card = {
        "name": sensor.name,
        "room": sensor.room,
        "model": sensor.model,
        "temperature": None,
        "humidity": None,
        "online": False,
        "status": "ok",
        "note": None,
    }

    if sensor.provider != "govee_cloud":
        card["status"] = "unsupported"
        card["note"] = "Unsupported environment sensor provider."
        return card

    if not _govee_api_key():
        card["status"] = "needs_api_key"
        card["note"] = "Set GOVEE_API_KEY on the Pi to read this sensor."
        return card

    runtime_key = sensor.device_id if _is_real_ble_address(sensor.device_id) else sensor.name

    try:
        entry = _match_environment_sensor(sensor, _govee_cloud_devices())
    except Exception:
        entry = None

    if entry is None:
        cached = ENVIRONMENT_RUNTIME_STATE.get(runtime_key)
        if cached:
            card.update(cached)
            card["online"] = False
            card["note"] = "Showing last known reading; sensor unreachable."
        else:
            card["status"] = "not_found"
            card["note"] = "Sensor not found in the Govee account."
        return card

    reading = _govee_thermometer_reading(entry)
    if reading is None:
        cached = ENVIRONMENT_RUNTIME_STATE.get(runtime_key)
        if cached:
            card.update(cached)
        card["online"] = False
        card["note"] = "Sensor did not report a reading."
        return card

    values: dict[str, Any] = {}
    if reading.get("temperature_f") is not None:
        values["temperature"] = _fahrenheit_to_celsius(float(reading["temperature_f"]))
    if reading.get("humidity") is not None:
        values["humidity"] = reading["humidity"]

    ENVIRONMENT_RUNTIME_STATE[runtime_key] = values
    card.update(values)
    card["online"] = True
    return card


def _environment_sensor_cards(path: Path) -> dict[str, Any]:
    return {"sensors": [_environment_sensor_card(s) for s in _load_environment_sensors(path)]}


def _govee_nightlight_caps(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Night-light control instances this device advertises (toggle/color/brightness)."""
    caps: dict[str, dict[str, Any]] = {}
    for cap in entry.get("capabilities") or []:
        instance = cap.get("instance")
        ctype = cap.get("type")
        if instance == "nightlightToggle":
            caps["toggle"] = {"type": ctype, "instance": instance}
        elif instance == "colorRgb":
            caps["color"] = {"type": ctype, "instance": instance}
        elif instance == "brightness":
            rng = (cap.get("parameters") or {}).get("range") or {}
            caps["brightness"] = {
                "type": ctype,
                "instance": instance,
                "min": int(rng.get("min", 1)),
                "max": int(rng.get("max", 100)),
            }
        elif instance == "nightlightScene":
            options = (cap.get("parameters") or {}).get("options") or []
            scenes = [
                {"name": o.get("name"), "value": int(o["value"])}
                for o in options
                if isinstance(o, dict) and o.get("value") is not None
            ]
            if scenes:
                caps["scene"] = {"type": ctype, "instance": instance, "options": scenes}
    return caps


def _rgb_int_from_body(body: dict[str, Any]) -> int:
    """Coerce a request body into a Govee colorRgb integer (0..0xFFFFFF)."""
    if body.get("value") is not None:
        return max(0, min(0xFFFFFF, int(body["value"])))
    red = _bounded_byte(body.get("red", body.get("r", 255)))
    green = _bounded_byte(body.get("green", body.get("g", 255)))
    blue = _bounded_byte(body.get("blue", body.get("b", 255)))
    return (red << 16) | (green << 8) | blue


def _govee_cloud_control(
    entry: dict[str, Any], capability_type: str, instance: str, value: Any
) -> dict[str, Any]:
    return _govee_cloud_request(
        "/router/api/v1/device/control",
        {
            "requestId": "smart-home-ai",
            "payload": {
                "sku": entry.get("sku"),
                "device": entry.get("device"),
                "capability": {"type": capability_type, "instance": instance, "value": value},
            },
        },
    )


def _humidifier_id(humidifier: HumidifierDefinition) -> str:
    return quote(humidifier.name, safe="")


def _find_humidifier(
    humidifiers: list[HumidifierDefinition], humidifier_id: str
) -> HumidifierDefinition:
    for humidifier in humidifiers:
        if humidifier.name == humidifier_id or _humidifier_id(humidifier) == humidifier_id:
            return humidifier
    raise HTTPException(status_code=404, detail=f"Humidifier not found: {humidifier_id}")


def _humidifier_runtime_key(humidifier: HumidifierDefinition, entry: dict[str, Any] | None = None) -> str:
    if _is_real_ble_address(humidifier.device_id):
        return humidifier.device_id
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
                # Merge in the linked thermometer's ambient humidity + temperature.
                thermometer = _match_govee_thermometer(humidifier, devices)
                if thermometer is not None:
                    reading = _govee_thermometer_reading(thermometer)
                    if reading:
                        cached = HUMIDIFIER_RUNTIME_STATE.setdefault(
                            _humidifier_runtime_key(humidifier, entry), {}
                        )
                        if reading.get("humidity") is not None:
                            cached["humidity"] = round(reading["humidity"])
                        if reading.get("temperature_f") is not None:
                            temp_f = reading["temperature_f"]
                            temp = temp_f if humidifier.temperature_unit == "F" else (temp_f - 32) * 5 / 9
                            cached["temperature"] = round(temp, 1)
                            cached["temperature_unit"] = humidifier.temperature_unit
                        cached["thermometer"] = thermometer.get("deviceName") or "Govee Thermometer"
    runtime = HUMIDIFIER_RUNTIME_STATE.get(_humidifier_runtime_key(humidifier, entry), {})
    nightlight_caps = _govee_nightlight_caps(entry) if entry else {}
    nightlight = {
        "toggle": "toggle" in nightlight_caps,
        "color": "color" in nightlight_caps,
        "brightness": (
            {
                "min": nightlight_caps["brightness"]["min"],
                "max": nightlight_caps["brightness"]["max"],
            }
            if "brightness" in nightlight_caps
            else None
        ),
        "scene": nightlight_caps["scene"]["options"] if "scene" in nightlight_caps else None,
    } if nightlight_caps else None
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
        "temperature": runtime.get("temperature"),
        "temperature_unit": runtime.get("temperature_unit"),
        "thermometer": runtime.get("thermometer"),
        "online": runtime.get("online"),
        "nightlight_on": runtime.get("nightlight_on"),
        "nightlight_brightness": runtime.get("nightlight_brightness"),
        "nightlight_color": runtime.get("nightlight_color"),
        "nightlight_scene": runtime.get("nightlight_scene"),
        "capabilities": {
            "power": controllable,
            "mist_level": {"min": mist_range[0], "max": mist_range[1]} if mist_range else None,
            "nightlight": nightlight,
        },
    }


def _humidifier_cards(path: Path) -> dict[str, Any]:
    return {"humidifiers": [_humidifier_card(h) for h in _load_humidifiers(path)]}


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
    elif command in ("nightlight_on", "nightlight_off"):
        nl = _govee_nightlight_caps(entry)
        if "toggle" not in nl:
            raise HTTPException(status_code=400, detail="This humidifier has no controllable night light.")
        turn_on = command == "nightlight_on"
        capability = {
            "type": nl["toggle"]["type"],
            "instance": nl["toggle"]["instance"],
            "value": 1 if turn_on else 0,
        }
        state_update = {"nightlight_on": turn_on}
    elif command == "nightlight_brightness":
        nl = _govee_nightlight_caps(entry)
        if "brightness" not in nl:
            raise HTTPException(status_code=400, detail="This night light has no brightness control.")
        raw = body.get("level", body.get("value", body.get("brightness")))
        if raw is None:
            raise HTTPException(status_code=400, detail="nightlight_brightness requires 'level'.")
        low, high = nl["brightness"]["min"], nl["brightness"]["max"]
        value = max(low, min(high, int(raw)))
        capability = {"type": nl["brightness"]["type"], "instance": nl["brightness"]["instance"], "value": value}
        state_update = {"nightlight_brightness": value}
    elif command == "nightlight_color":
        nl = _govee_nightlight_caps(entry)
        if "color" not in nl:
            raise HTTPException(status_code=400, detail="This night light has no color control.")
        value = _rgb_int_from_body(body)
        capability = {"type": nl["color"]["type"], "instance": nl["color"]["instance"], "value": value}
        state_update = {"nightlight_color": value}
    elif command == "nightlight_scene":
        nl = _govee_nightlight_caps(entry)
        if "scene" not in nl:
            raise HTTPException(status_code=400, detail="This night light has no scene control.")
        raw = body.get("value", body.get("scene"))
        if raw is None:
            raise HTTPException(status_code=400, detail="nightlight_scene requires 'value'.")
        valid = {opt["value"] for opt in nl["scene"]["options"]}
        value = int(raw)
        if value not in valid:
            raise HTTPException(status_code=400, detail=f"Unknown night-light scene: {value}")
        capability = {"type": nl["scene"]["type"], "instance": nl["scene"]["instance"], "value": value}
        state_update = {"nightlight_scene": value}
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


GOVEE_BLE_WRITE_UUIDS = (
    "00010203-0405-0607-0809-0a0b0c0d2b11",
    "02f00000-0000-0000-0000-00000000ff01",
)


def _govee_ble_command_bytes(command: str, body: dict[str, Any] | None = None) -> bytes:
    body = body or {}
    if command == "on":
        payload = [0x33, 0x01, 0x01]
    elif command == "off":
        payload = [0x33, 0x01, 0x00]
    elif command == "brightness":
        value = _bounded_byte(body.get("brightness", body.get("value", 100)), minimum=1, maximum=100)
        payload = [0x33, 0x04, value]
    elif command == "color":
        red = _bounded_byte(body.get("red", body.get("r", 255)))
        green = _bounded_byte(body.get("green", body.get("g", 255)))
        blue = _bounded_byte(body.get("blue", body.get("b", 255)))
        payload = [0x33, 0x05, 0x02, red, green, blue]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported Govee BLE command: {command}")

    if len(payload) > 19:
        raise HTTPException(status_code=500, detail="Govee BLE command payload is too long")
    packet = payload + [0x00] * (19 - len(payload))
    checksum = 0
    for value in packet:
        checksum ^= value
    packet.append(checksum)
    return bytes(packet)


def _bounded_byte(value: Any, minimum: int = 0, maximum: int = 255) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Expected numeric value, got {value!r}") from exc
    return max(minimum, min(maximum, number))


async def _govee_ble_write_packet(
    client: Any,
    characteristic: str,
    packet: bytes,
    response: bool,
) -> int:
    write_count = 2 if not response and packet[:2] == bytes((0x33, 0x01)) else 1
    for write_index in range(write_count):
        await client.write_gatt_char(characteristic, packet, response=response)
        if write_index + 1 < write_count:
            await asyncio.sleep(0.12)
    return write_count

class _GoveeBleManager:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._clients: dict[str, Any] = {}
        self._thread = threading.Thread(target=self._run_loop, name="govee-ble", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def write(self, light: AmbientLightDefinition, packet: bytes) -> dict[str, Any]:
        future = asyncio.run_coroutine_threadsafe(self._write_with_retry(light, packet), self._loop)
        return future.result(timeout=90)

    async def _write_with_retry(self, light: AmbientLightDefinition, packet: bytes) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await self._write_once(light, packet)
            except Exception as exc:
                last_error = exc
                await self._drop_client(light.address)
                if attempt < 2 and light.address:
                    await asyncio.to_thread(_govee_ble_forget_cached_device, light.address)
        assert last_error is not None
        raise last_error

    async def _write_once(self, light: AmbientLightDefinition, packet: bytes) -> dict[str, Any]:
        from bleak import BleakClient, BleakScanner  # type: ignore

        assert light.address is not None
        client = self._clients.get(light.address)
        reused_connection = client is not None and client.is_connected
        if not reused_connection:
            # The UB500 (BT 5.0) handles multiple simultaneous connections, so we keep
            # every lamp's connection warm instead of dropping the others. After the
            # first connect per lamp, subsequent commands reuse the link (~0.1s vs ~7s).
            await asyncio.to_thread(_govee_ble_forget_cached_device, light.address)
            initial_delay = 5 if (light.model or "").upper() == "H613A" else 1
            await asyncio.sleep(initial_delay)
            ble_kwargs = _ble_kwargs()
            device = await BleakScanner.find_device_by_address(
                light.address, timeout=8.0, **ble_kwargs
            )
            target = device or light.address
            client = BleakClient(
                target,
                timeout=12.0,
                disconnected_callback=lambda _client: self._clients.pop(light.address or "", None),
                **ble_kwargs,
            )
            await client.connect()
            self._clients[light.address] = client

        characteristic, response = _govee_ble_write_target(client)
        write_count = await _govee_ble_write_packet(client, characteristic, packet, response)
        return {
            "status": "ok",
            "name": light.name,
            "address": light.address,
            "characteristic": characteristic,
            "response": response,
            "write_count": write_count,
            "reused_connection": reused_connection,
        }

    async def _drop_client(self, address: str | None) -> None:
        if not address:
            return
        client = self._clients.pop(address, None)
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except Exception:
                pass


_GOVEE_BLE_MANAGER: _GoveeBleManager | None = None
_GOVEE_BLE_MANAGER_LOCK = threading.Lock()


def _get_govee_ble_manager() -> _GoveeBleManager:
    global _GOVEE_BLE_MANAGER
    with _GOVEE_BLE_MANAGER_LOCK:
        if _GOVEE_BLE_MANAGER is None:
            _GOVEE_BLE_MANAGER = _GoveeBleManager()
        return _GOVEE_BLE_MANAGER


def _govee_ble_command_payload(light: AmbientLightDefinition, command: str, body: dict[str, Any]) -> dict[str, Any]:
    if not _is_real_ble_address(light.address):
        raise HTTPException(status_code=400, detail="Run Govee BLE discovery and configure the light address first.")
    if command == "toggle":
        raise HTTPException(status_code=400, detail="Govee BLE toggle needs device state support; use on or off.")
    try:
        import bleak  # noqa: F401  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Install bleak on the Orange Pi for Govee BLE control: {exc}") from exc

    packet = _govee_ble_command_bytes(command, body)
    try:
        result = _get_govee_ble_manager().write(light, packet)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Govee BLE command failed for {light.name}: {type(exc).__name__}: {exc!r}",
        ) from exc

    _remember_ambient_light_command(light, command, body)
    result["command"] = command
    result["light"] = _ambient_light_card(light)
    return result


def _remember_ambient_light_command(light: AmbientLightDefinition, command: str, body: dict[str, Any]) -> None:
    key = light.address or light.name
    state = AMBIENT_LIGHT_RUNTIME_STATE.setdefault(key, {})
    if command == "on":
        state["is_on"] = True
    elif command == "off":
        state["is_on"] = False
    elif command == "brightness":
        state["brightness"] = _bounded_byte(body.get("brightness", body.get("value", 100)), minimum=1, maximum=100)
    elif command == "color":
        state["color"] = {
            "red": _bounded_byte(body.get("red", body.get("r", 255))),
            "green": _bounded_byte(body.get("green", body.get("g", 255))),
            "blue": _bounded_byte(body.get("blue", body.get("b", 255))),
        }

def _govee_ble_forget_cached_device(address: str) -> None:
    try:
        subprocess.run(["bluetoothctl", "remove", address], check=False, capture_output=True, text=True, timeout=6)
    except Exception:
        pass


def _govee_ble_write_target(client: Any) -> tuple[str, bool]:
    services = getattr(client, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Govee BLE services were not available after connect")

    writable = []
    for service in services:
        for characteristic in service.characteristics:
            props = set(characteristic.properties)
            if "write" in props or "write-without-response" in props:
                writable.append((str(characteristic.uuid).lower(), props))

    for uuid in GOVEE_BLE_WRITE_UUIDS:
        for candidate, props in writable:
            if candidate == uuid:
                return candidate, "write-without-response" not in props

    for candidate, props in writable:
        if not candidate.startswith("00002a"):
            return candidate, "write-without-response" not in props

    raise HTTPException(status_code=503, detail="No writable Govee BLE characteristic found")


def _load_tuya_devices(path: Path) -> list[TuyaDefinition]:
    if not path.exists():
        return []

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_devices = []
    raw_devices.extend(payload.get("tuya", {}).get("devices", []))
    raw_devices.extend(payload.get("tuya", {}).get("sensors", []))

    devices = []
    for item in raw_devices:
        if item.get("enabled") is False:
            continue
        device_id = str(item.get("device_id") or item.get("id") or "")
        if not device_id or device_id == "replace_me":
            continue
        power_dp = item.get("power_dp")
        category = item.get("category") or ("tuya_switch" if power_dp else "tuya_sensor")
        devices.append(
            TuyaDefinition(
                name=str(item.get("name") or device_id),
                device_id=device_id,
                host=item.get("host"),
                local_key=_secret_from_config(item, "local_key"),
                version=float(item.get("version", 3.4)),
                category=str(category),
                room=item.get("room"),
                model=item.get("model"),
                power_dp=str(power_dp) if power_dp else None,
                cloud_power_code=str(item.get("cloud_power_code")) if item.get("cloud_power_code") else None,
                dps={str(key): str(value) for key, value in (item.get("dps") or {}).items()},
            )
        )
    return devices


def _tuya_card(device: TuyaDefinition, status_payload: dict[str, Any] | None, source: str | None = None) -> dict[str, Any]:
    dps_values = _tuya_status_values(status_payload)
    is_on = _tuya_power_value(status_payload, device.power_dp) if device.power_dp else None
    if is_on is None and device.cloud_power_code:
        cloud_value = dps_values.get(device.cloud_power_code)
        is_on = cloud_value if isinstance(cloud_value, bool) else None
    configured = bool(device.host and device.local_key)
    cloud_linked = bool(device.local_key and not device.host)
    cloud_configured = bool(device.cloud_power_code or cloud_linked or device.local_key)
    return {
        "id": device.device_id,
        "name": device.name,
        "host": device.host,
        "model": device.model,
        "type": _friendly_tuya_category(device.category),
        "category": device.category,
        "room": device.room or _room_from_name(device.name),
        "is_on": is_on,
        "online": status_payload is not None if configured or cloud_configured else None,
        "status": "online" if status_payload else ("configured" if configured else ("cloud_linked" if cloud_linked else "needs_config")),
        "source": source,
        "values": _tuya_named_values(device.dps, dps_values),
        "controllable": bool((device.power_dp and configured) or device.cloud_power_code),
    }


def _tuya_status(device: TuyaDefinition) -> dict[str, Any]:
    tuya = _tinytuya_device(device)
    return tuya.status()


def _tuya_current_status(device: TuyaDefinition) -> dict[str, Any] | None:
    if device.host and device.local_key:
        try:
            return _tuya_status(device)
        except Exception:
            pass
    return _tuya_cloud_status(device)


def _tuya_set_power(device: TuyaDefinition, value: bool) -> None:
    if device.host and device.local_key and device.power_dp:
        tuya = _tinytuya_device(device)
        tuya.set_value(device.power_dp, value)
        return
    if device.cloud_power_code:
        cloud = _tuya_cloud_client()
        if cloud is None:
            raise HTTPException(status_code=503, detail="Tuya Cloud credentials are not configured")
        payload = {"commands": [{"code": device.cloud_power_code, "value": value}]}
        result = cloud.sendcommand(device.device_id, payload)
        if isinstance(result, dict) and result.get("success") is False:
            raise HTTPException(status_code=502, detail=f"Tuya Cloud command failed: {result.get('msg') or result}")
        return
    raise HTTPException(status_code=400, detail="Tuya device does not define a local or cloud power control")


def _tuya_cloud_client():
    try:
        import tinytuya
    except ImportError:
        return None

    api_region = os.getenv("TUYA_API_REGION") or os.getenv("TUYA_REGION")
    api_key = os.getenv("TUYA_ACCESS_ID") or os.getenv("TUYA_API_KEY")
    api_secret = os.getenv("TUYA_ACCESS_SECRET") or os.getenv("TUYA_API_SECRET")
    api_device_id = os.getenv("TUYA_DEVICE_ID") or os.getenv("TUYA_API_DEVICE_ID")
    if not api_region or not api_key or not api_secret:
        return None
    kwargs = {"apiRegion": api_region, "apiKey": api_key, "apiSecret": api_secret}
    if api_device_id:
        kwargs["apiDeviceID"] = api_device_id
    return tinytuya.Cloud(**kwargs)


def _tuya_cloud_status(device: TuyaDefinition) -> dict[str, Any] | None:
    cloud = _tuya_cloud_client()
    if cloud is None:
        return None
    payload = cloud.getstatus(device.device_id)
    if isinstance(payload, dict) and payload.get("success") is False:
        return None
    return payload


def _tinytuya_device(device: TuyaDefinition):
    try:
        import tinytuya
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="tinytuya is required for Tuya local control") from exc

    tuya = tinytuya.Device(device.device_id, device.host, device.local_key)
    tuya.set_version(device.version)
    if hasattr(tuya, "set_socketTimeout"):
        tuya.set_socketTimeout(1.5)
    return tuya


def _tuya_power_value(status_payload: dict[str, Any] | None, power_dp: str | None) -> bool | None:
    if not status_payload or not power_dp:
        return None
    dps_values = _tuya_status_values(status_payload)
    value = dps_values.get(str(power_dp))
    return value if isinstance(value, bool) else None


def _tuya_named_values(mapping: dict[str, str], dps_values: dict[str, Any]) -> dict[str, Any]:
    if mapping:
        return {name: dps_values.get(dp) for name, dp in mapping.items() if dp in dps_values}
    return {key: value for key, value in list(dps_values.items())[:8]}


def _tuya_status_values(status_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not status_payload:
        return {}
    dps = status_payload.get("dps")
    if isinstance(dps, dict):
        return {str(key): value for key, value in dps.items()}
    result = status_payload.get("result")
    if isinstance(result, list):
        return {str(item.get("code")): item.get("value") for item in result if isinstance(item, dict) and item.get("code")}
    if isinstance(result, dict):
        return {str(key): value for key, value in result.items()}
    return {}


def _alarm_payload(path: Path) -> dict[str, Any]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        return {"status": "needs_auth", "source": "Home Assistant", "controls": [], "zones": []}
    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception as exc:
        return {"status": "error", "message": f"Home Assistant API error: {exc}", "controls": [], "zones": []}

    panel = _home_assistant_alarm_panel(states)
    controls = [_home_assistant_alarm_control(entity) for entity in states if _is_home_assistant_alarm_control(entity)]
    zones = [_home_assistant_alarm_zone(entity) for entity in states if _is_home_assistant_alarm_zone(entity)]
    controls = [control for control in controls if control]
    zones = [zone for zone in zones if zone]
    controls.sort(key=lambda item: item["name"].lower())
    zones.sort(key=lambda item: item["name"].lower())
    return {
        "status": "ok",
        "source": "Home Assistant",
        "panel": panel or {
            "name": _home_assistant_alarm_panel_name(controls),
            "entity_id": None,
            "state": "connected" if controls else "not_found",
            "supported_features": 0,
        },
        "controls": controls,
        "zones": zones,
    }


def _home_assistant_alarm_panel(states: list[dict[str, Any]]) -> dict[str, Any] | None:
    panels = [entity for entity in states if _home_assistant_entity_domain(entity.get("entity_id")) == "alarm_control_panel"]
    if not panels:
        return None
    panels.sort(key=lambda entity: 0 if _is_real_alarm_panel(entity) else 1)
    entity = panels[0]
    attributes = entity.get("attributes") or {}
    state = entity.get("state")
    return {
        "id": entity.get("entity_id"),
        "entity_id": entity.get("entity_id"),
        "name": str(attributes.get("friendly_name") or entity.get("entity_id") or "Alarm panel"),
        "state": state,
        "status": "online" if state not in {"unavailable", "unknown", None} else "unavailable",
        "supported_features": attributes.get("supported_features") or 0,
    }


def _is_real_alarm_panel(entity: dict[str, Any]) -> bool:
    entity_id = str(entity.get("entity_id") or "").lower()
    attributes = entity.get("attributes") or {}
    name = str(attributes.get("friendly_name") or "").lower()
    text = f"{entity_id} {name}"
    return any(term in text for term in ("duo_gong_neng_bao_jing_zhu_ji", "报警主机", "alarm system", "alarm host"))
def _is_home_assistant_alarm_control(entity: dict[str, Any]) -> bool:
    entity_id = str(entity.get("entity_id") or "").lower()
    domain = _home_assistant_entity_domain(entity_id)
    if domain not in {"switch", "select"}:
        return False
    attributes = entity.get("attributes") or {}
    name = str(attributes.get("friendly_name") or entity_id).lower()
    text = f"{entity_id} {name}"
    alarm_terms = ("multi_mode_gateway", "duo_gong_neng_bao_jing_zhu_ji", "报警主机", "alarm system", "alarm host", "siren", "arm beep")
    camera_terms = ("camera", "doorbell", "men_ling", "门铃")
    return any(term in text for term in alarm_terms) and not any(term in text for term in camera_terms)


def _home_assistant_alarm_control(entity: dict[str, Any]) -> dict[str, Any] | None:
    entity_id = str(entity.get("entity_id") or "")
    domain = _home_assistant_entity_domain(entity_id)
    if domain not in {"switch", "select"}:
        return None
    attributes = entity.get("attributes") or {}
    state = entity.get("state")
    return {
        "id": entity_id,
        "entity_id": entity_id,
        "domain": domain,
        "name": str(attributes.get("friendly_name") or entity_id),
        "state": state,
        "status": "online" if state not in {"unavailable", "unknown", None} else "unavailable",
        "controllable": domain == "switch",
        "options": attributes.get("options") or [],
    }


def _home_assistant_alarm_panel_name(controls: list[dict[str, Any]]) -> str:
    for control in controls:
        name = str(control.get("name") or "")
        for suffix in (" Arm beep", " Siren"):
            if name.endswith(suffix):
                return name[: -len(suffix)]
    return "Tuya alarm system"


def _is_home_assistant_alarm_zone(entity: dict[str, Any]) -> bool:
    entity_id = str(entity.get("entity_id") or "").lower()
    domain = _home_assistant_entity_domain(entity_id)
    if domain != "binary_sensor":
        return False
    attributes = entity.get("attributes") or {}
    device_class = str(attributes.get("device_class") or "").lower()
    return device_class in {"door", "window", "occupancy", "motion"}


def _home_assistant_alarm_zone(entity: dict[str, Any]) -> dict[str, Any] | None:
    entity_id = str(entity.get("entity_id") or "")
    attributes = entity.get("attributes") or {}
    device_class = str(attributes.get("device_class") or "").lower()
    state = str(entity.get("state") or "unknown")
    zone_type = "motion" if device_class in {"occupancy", "motion"} else device_class or "zone"
    return {
        "id": entity_id,
        "name": str(attributes.get("friendly_name") or entity_id),
        "type": zone_type,
        "state": "motion" if zone_type == "motion" and state == "on" else ("open" if state == "on" else "closed" if zone_type != "motion" else "clear"),
        "time": "Home Assistant",
    }
def _load_weather_config(path: Path) -> WeatherConfig | None:
    if not path.exists():
        return None

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    weather = payload.get("weather") or {}
    if "latitude" not in weather or "longitude" not in weather:
        return None

    return WeatherConfig(
        name=str(weather.get("name") or "Home"),
        latitude=float(weather["latitude"]),
        longitude=float(weather["longitude"]),
        timezone=str(weather.get("timezone") or "auto"),
        temperature_unit=str(weather.get("temperature_unit") or "fahrenheit"),
    )


def _load_ecobee_config(path: Path) -> list[EcobeeConfig]:
    if not path.exists():
        return []

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ecobee = payload.get("ecobee") or {}
    default_unit = str(ecobee.get("temperature_unit") or payload.get("weather", {}).get("temperature_unit") or "celsius")
    thermostats = ecobee.get("thermostats") or []
    configs = []
    for item in thermostats:
        if item.get("enabled") is False:
            continue
        thermostat_id = item.get("thermostat_id") or item.get("id")
        configs.append(
            EcobeeConfig(
                name=str(item.get("name") or thermostat_id or "Ecobee thermostat"),
                thermostat_id=str(thermostat_id) if thermostat_id else None,
                room=item.get("room"),
                temperature_unit=str(item.get("temperature_unit") or default_unit),
            )
        )
    return configs


def _load_home_assistant_config(path: Path) -> HomeAssistantConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    payload = payload or {}
    config = payload.get("home_assistant") or {}
    domains = config.get("include_domains") or ["alarm_control_panel", "climate", "light", "switch", "sensor", "binary_sensor", "cover", "fan", "lock", "camera"]
    return HomeAssistantConfig(
        base_url=str(config.get("base_url") or "http://127.0.0.1:8123").rstrip("/"),
        token_env=str(config.get("token_env") or "HOME_ASSISTANT_TOKEN"),
        include_domains={str(domain) for domain in domains},
    )


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


def _home_assistant_service_command(path: Path, entity_id: str, command: str) -> dict[str, Any]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        raise HTTPException(status_code=503, detail=f"{config.token_env} is not configured")
    domain = _home_assistant_entity_domain(entity_id)
    if domain not in {"light", "switch", "fan", "cover", "lock"}:
        raise HTTPException(status_code=400, detail=f"Unsupported Home Assistant command domain: {domain}")
    if command not in {"on", "off", "toggle"}:
        raise HTTPException(status_code=400, detail=f"Unsupported Home Assistant command: {command}")
    service = {
        "on": "turn_on",
        "off": "turn_off",
        "toggle": "toggle",
    }[command]
    if domain in {"cover", "lock"} and command == "toggle":
        raise HTTPException(status_code=400, detail=f"{domain} does not support toggle")
    if domain == "cover":
        service = "open_cover" if command == "on" else "close_cover"
    if domain == "lock":
        service = "lock" if command == "on" else "unlock"
    payload = _home_assistant_post(config, token, f"/api/services/{domain}/{service}", {"entity_id": entity_id})
    return {"status": "ok", "result": payload}


def _home_assistant_brightness_command(
    path: Path, entity_id: str, level: int
) -> dict[str, Any]:
    """Set an HA light's brightness via light.turn_on with brightness_pct.

    Note HA treats brightness_pct 0 as "off", unlike the Matter path which
    clamps to the lowest on-level.  That is HA's own semantics; passing it
    through keeps the dashboard and Home Assistant in agreement.
    """
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        raise HTTPException(status_code=503, detail=f"{config.token_env} is not configured")
    domain = _home_assistant_entity_domain(entity_id)
    if domain != "light":
        raise HTTPException(
            status_code=400,
            detail=f"Brightness is only supported for light entities, not {domain or 'unknown'}",
        )
    level = max(0, min(100, int(level)))
    payload = _home_assistant_post(
        config,
        token,
        "/api/services/light/turn_on",
        {"entity_id": entity_id, "brightness_pct": level},
    )
    return {"status": "ok", "brightness": level, "result": payload}


def _home_assistant_climate_update(path: Path, entity_id: str, update: ClimateUpdateRequest) -> dict[str, Any]:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        raise HTTPException(status_code=503, detail=f"{config.token_env} is not configured")
    if _home_assistant_entity_domain(entity_id) != "climate":
        raise HTTPException(status_code=400, detail="Climate controls require a climate entity")

    results = []
    if update.hvac_mode is not None:
        if update.hvac_mode not in {"off", "heat", "cool", "heat_cool", "auto"}:
            raise HTTPException(status_code=400, detail=f"Unsupported HVAC mode: {update.hvac_mode}")
        results.append(
            _home_assistant_post(
                config,
                token,
                "/api/services/climate/set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": update.hvac_mode},
            )
        )
    if update.preset_mode is not None:
        if not update.preset_mode.strip():
            raise HTTPException(status_code=400, detail="preset_mode cannot be empty.")
        if update.preset_entity_id:
            if _home_assistant_entity_domain(update.preset_entity_id) != "select":
                raise HTTPException(status_code=400, detail="Preset entity must be a select entity.")
            results.append(
                _home_assistant_post(
                    config,
                    token,
                    "/api/services/select/select_option",
                    {"entity_id": update.preset_entity_id, "option": update.preset_mode},
                )
            )
        else:
            results.append(
                _home_assistant_post(
                    config,
                    token,
                    "/api/services/climate/set_preset_mode",
                    {"entity_id": entity_id, "preset_mode": update.preset_mode},
                )
            )

    temperature_payload: dict[str, Any] = {"entity_id": entity_id}
    if update.temperature is not None:
        temperature_payload["temperature"] = update.temperature
    if update.target_temp_low is not None:
        temperature_payload["target_temp_low"] = update.target_temp_low
    if update.target_temp_high is not None:
        temperature_payload["target_temp_high"] = update.target_temp_high
    if len(temperature_payload) > 1:
        results.append(_home_assistant_post(config, token, "/api/services/climate/set_temperature", temperature_payload))

    if not results:
        raise HTTPException(status_code=400, detail="No climate update was provided")
    return {"status": "ok", "result": results}


def _home_assistant_alarm_command(path: Path, command: str) -> dict[str, Any]:
    config, token = _home_assistant_auth(path)
    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Home Assistant API error: {exc}") from exc
    panel = _home_assistant_alarm_panel(states)
    if not panel or not panel.get("entity_id"):
        raise HTTPException(status_code=404, detail="No Home Assistant alarm control panel was found")
    service = {
        "disarmed": "alarm_disarm",
        "disarm": "alarm_disarm",
        "home": "alarm_arm_home",
        "away": "alarm_arm_away",
    }.get(command)
    if not service:
        raise HTTPException(status_code=400, detail=f"Unsupported alarm command: {command}")
    payload = _home_assistant_post(
        config,
        token,
        f"/api/services/alarm_control_panel/{service}",
        {"entity_id": panel["entity_id"]},
    )
    return {"status": "ok", "entity_id": panel["entity_id"], "command": command, "result": payload}
def _home_assistant_get(config: HomeAssistantConfig, token: str, path: str) -> Any:
    request = _URLRequest(
        f"{config.base_url}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _home_assistant_post(config: HomeAssistantConfig, token: str, path: str, body: dict[str, Any]) -> Any:
    request = _URLRequest(
        f"{config.base_url}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=12) as response:
        text = response.read().decode("utf-8")
    return json.loads(text) if text else None


def _home_assistant_entity_card(entity: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(entity.get("entity_id") or "")
    attributes = entity.get("attributes") or {}
    domain = _home_assistant_entity_domain(entity_id)
    state = entity.get("state")
    card = {
        "id": entity_id,
        "entity_id": entity_id,
        "domain": domain,
        "name": str(attributes.get("friendly_name") or entity_id),
        "state": state,
        "status": "online" if state not in {"unavailable", "unknown", None} else "unavailable",
        "unit": attributes.get("temperature_unit") if domain == "climate" else attributes.get("unit_of_measurement"),
        "device_class": attributes.get("device_class"),
        "controllable": domain in {"light", "switch", "fan"},
        "attributes": {},
    }
    if domain == "climate":
        card["attributes"] = {
            "current_temperature": attributes.get("current_temperature"),
            "temperature": attributes.get("temperature"),
            "target_temp_low": attributes.get("target_temp_low"),
            "target_temp_high": attributes.get("target_temp_high"),
            "current_humidity": attributes.get("current_humidity"),
            "hvac_action": attributes.get("hvac_action"),
            "hvac_modes": attributes.get("hvac_modes") or [],
            "preset_mode": attributes.get("preset_mode"),
            "preset_modes": attributes.get("preset_modes") or [],
        }
    elif domain in {"sensor", "binary_sensor"}:
        card["attributes"] = {
            "battery": attributes.get("battery_level"),
            "last_seen": attributes.get("last_seen"),
        }
    return card


def _is_ignored_home_assistant_entity(entity: dict[str, Any]) -> bool:
    entity_id = str(entity.get("entity_id") or "").lower()
    attributes = entity.get("attributes") or {}
    name = str(attributes.get("friendly_name") or entity_id).lower()
    ignored_prefixes = (
        "sensor.iphone_",
        "binary_sensor.iphone_",
        "device_tracker.iphone_",
        "sensor.sun_",
        "binary_sensor.sun_",
    )
    ignored_name_terms = (
        "iphone 15",
        "sun next",
    )
    return any(entity_id.startswith(prefix) for prefix in ignored_prefixes) or any(term in name for term in ignored_name_terms)


def _home_assistant_entity_domain(entity_id: str | None) -> str:
    if not entity_id or "." not in entity_id:
        return ""
    return entity_id.split(".", 1)[0]


def _area_slug(name: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.strip().lower())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _default_areas_doc() -> dict[str, Any]:
    return {"areas": [dict(a) for a in DEFAULT_AREAS], "assignments": {}}


def _zigbee_frontend_token(path: Path) -> str | None:
    """Read the Zigbee2MQTT frontend token, or None if the stack is not set up.

    A missing file is the normal state on a machine where the Zigbee stack was
    never installed, so it is not an error - the dashboard just shows the panel
    as unavailable rather than framing a login prompt nobody can satisfy.
    """
    if not path.exists():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    token = payload.get("frontend_token") if isinstance(payload, dict) else None
    return str(token) if token else None


def _load_areas(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_areas_doc()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_areas_doc()
    areas = [
        {
            "id": str(a.get("id") or ""),
            "name": str(a.get("name") or ""),
            "icon": str(a.get("icon") or "home"),
        }
        for a in (payload.get("areas") or [])
        if isinstance(a, dict) and a.get("id") and a.get("name")
    ]
    assignments = {
        str(k): str(v)
        for k, v in (payload.get("assignments") or {}).items()
        if v
    }
    return {"areas": areas, "assignments": assignments}


def _save_areas(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


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
    # Normalize so every group carries a "readingFilter" key (None when unset),
    # matching the shape _load_device_groups produces on a save/reload round
    # trip -- DEFAULT_DEVICE_GROUPS itself omits the key where it doesn't apply.
    return {
        "groups": [dict({"readingFilter": None}, **g) for g in DEFAULT_DEVICE_GROUPS],
        "overrides": {},
    }


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
    # `or []` alone only catches falsy values -- a truthy non-list "groups"
    # (e.g. an int or bool) is not iterable and would raise TypeError here.
    raw_groups = payload.get("groups")
    for raw in raw_groups if isinstance(raw_groups, list) else []:
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
    # `or {}` alone only catches falsy values -- a truthy non-dict "overrides"
    # (e.g. a list, string, int, or bool) has no `.items()` and would raise
    # AttributeError here. Treat anything that isn't actually a dict as absent.
    raw_overrides = payload.get("overrides")
    for key, rule in (raw_overrides if isinstance(raw_overrides, dict) else {}).items():
        if not isinstance(rule, dict):
            continue
        include = [g for g in (rule.get("include") or []) if g in known]
        exclude = [g for g in (rule.get("exclude") or []) if g in known]
        if include or exclude:
            overrides[str(key)] = {"include": include, "exclude": exclude}

    return {"groups": groups, "overrides": overrides}


def _save_device_groups(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


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


def _clean_ha_state(value: Any) -> Any:
    """Turn Home Assistant's absent-value sentinels into None.

    HA reports a dropped entity as the literal string "unavailable" (or
    "unknown"), which reads as real data everywhere it is displayed verbatim.
    """
    return None if str(value).lower() in {"unavailable", "unknown", "none"} else value


def _zigbee_bridge_payload(path: Path) -> dict[str, Any]:
    """Collect the coordinator's own entities from Home Assistant.

    Degrades to available: False whenever Home Assistant is unreachable or the
    MQTT integration has not been added, so the Zigbee view can say so instead of
    rendering an empty card.
    """
    empty: dict[str, Any] = {"available": False, "permit_join": None, "connected": None,
                             "version": None, "permit_join_entity": None,
                             "connection_changed": None}
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        return empty
    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception:
        return empty

    bridge = {
        str(entity.get("entity_id")): entity
        for entity in states
        if _is_zigbee_bridge_entity(entity.get("entity_id"))
    }
    if not bridge:
        return empty

    def _state(entity_id: str) -> Any:
        entity = bridge.get(entity_id)
        return entity.get("state") if entity else None

    permit = _state("switch.zigbee2mqtt_bridge_permit_join")
    connection = _state("binary_sensor.zigbee2mqtt_bridge_connection_state")
    # How long the bridge has been in its current state. A dead bridge is silent
    # rather than noisy - one replug went unnoticed for 66 minutes - so the
    # health tile needs to say "offline since when", not just "offline".
    connection_entity = bridge.get("binary_sensor.zigbee2mqtt_bridge_connection_state")
    return {
        "available": True,
        # None rather than False when the entity is missing, so the card can tell
        # "closed" apart from "no such control".
        "permit_join": {"on": True, "off": False}.get(str(permit)) if permit is not None else None,
        "connected": {"on": True, "off": False}.get(str(connection)) if connection is not None else None,
        # Home Assistant reports a dropped sensor as the literal strings
        # "unavailable"/"unknown". Passed through, the health tile reads
        # "Zigbee2MQTT unavailable" as if that were a version number.
        "version": _clean_ha_state(_state("sensor.zigbee2mqtt_bridge_version")),
        "permit_join_entity": "switch.zigbee2mqtt_bridge_permit_join"
        if "switch.zigbee2mqtt_bridge_permit_join" in bridge
        else None,
        "connection_changed": (connection_entity or {}).get("last_changed"),
    }


def _is_zigbee_bridge_entity(entity_id: str | None) -> bool:
    """Is this one of Zigbee2MQTT's own bridge controls rather than a device?

    Zigbee2MQTT publishes controls for the coordinator itself - permit join, log
    level, restart, connection state. Home Assistant marks them
    entity_category: config/diagnostic, but that lives in the entity registry and
    never appears in /api/states, so the entity_id is what we have to go on.

    They matter because `switch.zigbee2mqtt_bridge_permit_join` is a switch
    domain entity, so without this it is offered as a new device and then renders
    as a light switch on the Devices view.
    """
    return "zigbee2mqtt_bridge" in str(entity_id or "").lower()


def _mark_new_light_switch_entities(entities: list[dict[str, Any]], known_ids: set[str]) -> None:
    for entity in entities:
        # Never offer the coordinator's own controls as a household device.
        if _is_zigbee_bridge_entity(entity.get("entity_id")):
            entity["is_new"] = False
            continue
        if entity.get("domain") in {"light", "switch"}:
            entity["is_new"] = entity.get("entity_id") not in known_ids


def _ecobee_payload(path: Path) -> dict[str, Any]:
    configs = _load_ecobee_config(path)
    if not configs:
        home_assistant_payload = _ecobee_payload_from_home_assistant(path)
        if home_assistant_payload is not None:
            return home_assistant_payload
        return {
            "status": "not_configured",
            "message": "Add an ecobee.thermostats section to configs/devices.local.yaml.",
            "thermostats": [],
        }

    if not os.getenv("ECOBEE_CLIENT_ID"):
        home_assistant_payload = _ecobee_payload_from_home_assistant(path)
        if home_assistant_payload is not None:
            return home_assistant_payload
        return {
            "status": "needs_auth",
            "message": "Set ECOBEE_CLIENT_ID and ECOBEE_ACCESS_TOKEN or ECOBEE_REFRESH_TOKEN in the dashboard environment, or connect Ecobee through Home Assistant.",
            "thermostats": [_ecobee_setup_card(config) for config in configs],
        }

    try:
        thermostats = _ecobee_api_thermostats()
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Ecobee API error: {exc}",
            "thermostats": [_ecobee_setup_card(config, "offline") for config in configs],
        }

    return {
        "status": "ok",
        "source": "Ecobee",
        "thermostats": [_ecobee_card(config, thermostats) for config in configs],
    }


def _ecobee_payload_from_home_assistant(path: Path) -> dict[str, Any] | None:
    config = _load_home_assistant_config(path)
    token = os.getenv(config.token_env)
    if not token:
        return None
    try:
        states = _home_assistant_get(config, token, "/api/states")
    except Exception:
        return None
    climates = [
        entity
        for entity in states
        if _home_assistant_entity_domain(entity.get("entity_id")) == "climate"
    ]
    if not climates:
        return None
    return {
        "status": "ok",
        "source": "Home Assistant",
        "thermostats": [_ecobee_card_from_home_assistant(entity, states) for entity in climates],
    }


def _ecobee_card_from_home_assistant(entity: dict[str, Any], states: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    entity_id = str(entity.get("entity_id") or "")
    attributes = entity.get("attributes") or {}
    preset_entity = _home_assistant_ecobee_preset_entity(entity, states or [])
    preset_attributes = preset_entity.get("attributes") if preset_entity else {}
    unit = attributes.get("temperature_unit") or attributes.get("unit_of_measurement") or "°C"
    return {
        "id": entity_id,
        "name": str(attributes.get("friendly_name") or entity_id or "Ecobee thermostat"),
        "room": _room_from_name(str(attributes.get("friendly_name") or entity_id)),
        "status": "online" if entity.get("state") not in {"unavailable", "unknown", None} else "unavailable",
        "temperature": attributes.get("current_temperature"),
        "temperature_unit": unit,
        "hvac_mode": entity.get("state"),
        "hvac_modes": attributes.get("hvac_modes") or [],
        "preset_entity_id": preset_entity.get("entity_id") if preset_entity else None,
        "preset_mode": attributes.get("preset_mode") or (preset_entity.get("state") if preset_entity else None),
        "preset_modes": attributes.get("preset_modes") or preset_attributes.get("options") or [],
        "equipment_status": attributes.get("hvac_action") or "idle",
        "desired_heat": attributes.get("target_temp_low") or attributes.get("temperature"),
        "desired_cool": attributes.get("target_temp_high") or attributes.get("temperature"),
        "humidity": attributes.get("current_humidity"),
        "online": entity.get("state") not in {"unavailable", "unknown", None},
        "sensors": _ecobee_sensors_from_ha_states(entity_id, states or []),
    }


_ROOM_KEYWORDS: list[tuple[str, str]] = [
    ("living room", "Living Room"),
    ("master bedroom", "Master Bedroom"),
    ("family room", "Family Room"),
    ("dining room", "Dining Room"),
    ("master", "Master Bedroom"),
    ("bedroom", "Bedroom"),
    ("kitchen", "Kitchen"),
    ("office", "Office"),
    ("garage", "Garage"),
    ("dining", "Dining Room"),
    ("basement", "Basement"),
    ("attic", "Attic"),
    ("hallway", "Hallway"),
    ("bathroom", "Bathroom"),
    ("nursery", "Nursery"),
    ("sunroom", "Sunroom"),
    ("playroom", "Playroom"),
]


def _ecobee_sensors_from_ha_states(climate_entity_id: str, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find per-room temperature/occupancy sensor entities from HA states for an Ecobee thermostat.

    Matches the ecobee built-in sensor by entity_id prefix, and other room sensors
    by room keywords in their friendly names (works regardless of integration source).
    """
    climate_slug = climate_entity_id.split(".", 1)[-1].lower()

    occ_by_room: dict[str, bool] = {}
    temp_entries: list[dict[str, Any]] = []
    seen_rooms: set[str] = set()

    for entity in states:
        entity_id = str(entity.get("entity_id") or "")
        attrs = entity.get("attributes") or {}
        domain = _home_assistant_entity_domain(entity_id)
        slug = entity_id.split(".", 1)[-1].lower()
        friendly = str(attrs.get("friendly_name") or entity_id)

        if domain == "sensor" and (
            attrs.get("device_class") == "temperature"
            or attrs.get("unit_of_measurement") in ("°F", "°C")
        ):
            clean = friendly[: -len(" Temperature")].strip() if friendly.lower().endswith(" temperature") else friendly
            clean_lower = clean.lower()

            # Ecobee built-in: entity slug starts with the climate entity slug
            if slug.startswith(climate_slug + "_"):
                room_name = "Living Room"
            else:
                room_name = None
                for keyword, rname in _ROOM_KEYWORDS:
                    if keyword in clean_lower:
                        room_name = rname
                        break

            if room_name is None:
                continue  # not a room sensor we recognize

            try:
                temperature: float | None = float(entity.get("state"))
            except (TypeError, ValueError):
                temperature = None

            temp_entries.append({"id": slug, "name": room_name, "temperature": temperature,
                                  "builtin": slug.startswith(climate_slug + "_")})

        if domain == "binary_sensor" and attrs.get("device_class") == "occupancy":
            clean = friendly[: -len(" Occupancy")].strip() if friendly.lower().endswith(" occupancy") else friendly
            for keyword, rname in _ROOM_KEYWORDS:
                if keyword in clean.lower():
                    occ_by_room[rname] = entity.get("state") == "on"
                    break

    # Built-in sensor wins if the same room appears from multiple sources
    temp_entries.sort(key=lambda e: (0 if e["builtin"] else 1))

    sensors = []
    for entry in temp_entries:
        room = entry["name"]
        if room in seen_rooms:
            continue
        seen_rooms.add(room)
        sensors.append({
            "id": entry["id"],
            "name": room,
            "temperature": entry["temperature"],
            "occupied": occ_by_room.get(room),
        })

    sensors.sort(key=lambda s: (0 if s["name"] == "Living Room" else 1, s["name"]))
    return sensors


def _home_assistant_ecobee_preset_entity(
    climate_entity: dict[str, Any], states: list[dict[str, Any]]
) -> dict[str, Any] | None:
    climate_entity_id = str(climate_entity.get("entity_id") or "")
    climate_name = str((climate_entity.get("attributes") or {}).get("friendly_name") or climate_entity_id).lower()
    climate_slug = climate_entity_id.split(".", 1)[-1].lower()
    candidates = []
    for entity in states:
        entity_id = str(entity.get("entity_id") or "")
        if _home_assistant_entity_domain(entity_id) != "select":
            continue
        attributes = entity.get("attributes") or {}
        options = attributes.get("options") or []
        if not options:
            continue
        name = str(attributes.get("friendly_name") or entity_id).lower()
        entity_slug = entity_id.split(".", 1)[-1].lower()
        if "current mode" in name and (climate_slug in entity_slug or "ecobee" in name or "ecobee" in entity_slug):
            candidates.append(entity)
            continue
        if climate_name and climate_name in name and ("mode" in name or "preset" in name):
            candidates.append(entity)
    return candidates[0] if candidates else None


def _ecobee_setup_card(config: EcobeeConfig, status: str = "needs_auth") -> dict[str, Any]:
    return {
        "id": config.thermostat_id or config.name,
        "name": config.name,
        "room": config.room or _room_from_name(config.name),
        "status": status,
        "temperature": None,
        "temperature_unit": _ecobee_unit_symbol(config.temperature_unit),
        "hvac_mode": None,
        "hvac_modes": [],
        "preset_entity_id": None,
        "preset_mode": None,
        "preset_modes": [],
        "equipment_status": None,
        "desired_heat": None,
        "desired_cool": None,
        "humidity": None,
        "online": False,
        "sensors": [],
    }


def _ecobee_api_thermostats() -> list[dict[str, Any]]:
    access_token = os.getenv("ECOBEE_ACCESS_TOKEN")
    if not access_token and os.getenv("ECOBEE_REFRESH_TOKEN"):
        access_token = _ecobee_refresh_access_token()
    if not access_token:
        raise RuntimeError("ECOBEE_ACCESS_TOKEN or ECOBEE_REFRESH_TOKEN is required")

    selection = {
        "selection": {
            "selectionType": "registered",
            "selectionMatch": "",
            "includeRuntime": True,
            "includeSettings": True,
            "includeEquipmentStatus": True,
            "includeRemoteSensors": True,
        }
    }
    query = urlencode({"format": "json", "body": json.dumps(selection)})
    request = _URLRequest(
        f"https://api.ecobee.com/1/thermostat?{query}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("thermostatList") or []


def _ecobee_refresh_access_token() -> str:
    client_id = os.getenv("ECOBEE_CLIENT_ID")
    refresh_token = os.getenv("ECOBEE_REFRESH_TOKEN")
    if not client_id or not refresh_token:
        raise RuntimeError("ECOBEE_CLIENT_ID and ECOBEE_REFRESH_TOKEN are required")
    data = urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
    ).encode("utf-8")
    request = _URLRequest(
        "https://api.ecobee.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Ecobee token refresh did not return an access token")
    return str(token)


def _ecobee_card(config: EcobeeConfig, thermostats: list[dict[str, Any]]) -> dict[str, Any]:
    thermostat = _match_ecobee_thermostat(config, thermostats)
    if thermostat is None:
        card = _ecobee_setup_card(config, "not_found")
        card["online"] = None
        return card

    runtime = thermostat.get("runtime") or {}
    settings = thermostat.get("settings") or {}
    unit = _ecobee_unit_symbol(config.temperature_unit)
    return {
        "id": str(thermostat.get("identifier") or config.thermostat_id or config.name),
        "name": config.name or str(thermostat.get("name") or "Ecobee thermostat"),
        "room": config.room or _room_from_name(config.name),
        "status": "online",
        "temperature": _ecobee_temperature(runtime.get("actualTemperature"), config.temperature_unit),
        "temperature_unit": unit,
        "hvac_mode": settings.get("hvacMode"),
        "hvac_modes": ["off", "heat", "cool", "heat_cool"],
        "preset_entity_id": None,
        "preset_mode": None,
        "preset_modes": [],
        "equipment_status": thermostat.get("equipmentStatus") or "idle",
        "desired_heat": _ecobee_temperature(runtime.get("desiredHeat"), config.temperature_unit),
        "desired_cool": _ecobee_temperature(runtime.get("desiredCool"), config.temperature_unit),
        "humidity": runtime.get("actualHumidity"),
        "online": True,
        "sensors": _ecobee_sensors_from_api(thermostat, config.temperature_unit),
    }


def _ecobee_sensors_from_api(thermostat: dict[str, Any], temperature_unit: str) -> list[dict[str, Any]]:
    """Extract per-room sensor readings from Ecobee API remoteSensors data."""
    sensors = []
    for sensor in thermostat.get("remoteSensors") or []:
        caps = {c["type"]: c.get("value") for c in (sensor.get("capability") or []) if "type" in c}
        temp_raw = caps.get("temperature")
        temperature = None
        if temp_raw is not None and temp_raw != "unknown":
            try:
                temperature = _ecobee_temperature(temp_raw, temperature_unit)
            except (TypeError, ValueError):
                pass
        occupied_raw = caps.get("occupancy")
        occupied = (occupied_raw == "true") if occupied_raw is not None else None
        # Built-in thermostat sensor lives in the living room per user config
        name = "Living Room" if sensor.get("type") == "thermostat" else str(sensor.get("name") or "")
        sensors.append({
            "id": str(sensor.get("id") or name),
            "name": name,
            "temperature": temperature,
            "occupied": occupied,
        })
    return sensors


def _match_ecobee_thermostat(config: EcobeeConfig, thermostats: list[dict[str, Any]]) -> dict[str, Any] | None:
    if config.thermostat_id:
        for thermostat in thermostats:
            if str(thermostat.get("identifier")) == config.thermostat_id:
                return thermostat
    if len(thermostats) == 1:
        return thermostats[0]
    for thermostat in thermostats:
        if str(thermostat.get("name") or "").lower() == config.name.lower():
            return thermostat
    return None


def _ecobee_temperature(value: Any, unit: str) -> float | None:
    if value is None:
        return None
    fahrenheit = float(value) / 10
    if unit.lower().startswith("c"):
        return round((fahrenheit - 32) * 5 / 9, 1)
    return round(fahrenheit, 1)


def _ecobee_unit_symbol(unit: str) -> str:
    return "°C" if unit.lower().startswith("c") else "°F"


def _weather_payload(config: WeatherConfig) -> dict[str, Any]:
    query = urlencode(
        {
            "latitude": config.latitude,
            "longitude": config.longitude,
            "timezone": config.timezone,
            "temperature_unit": config.temperature_unit,
            "wind_speed_unit": "mph" if config.temperature_unit == "fahrenheit" else "kmh",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,surface_pressure",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max,sunrise,sunset,uv_index_max",
            "forecast_days": 7,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{query}"
    with urlopen(url, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    current = payload.get("current", {})
    units = payload.get("current_units", {})
    daily = payload.get("daily", {})
    weather_code = current.get("weather_code")
    return {
        "status": "ok",
        "source": "Open-Meteo",
        "location": config.name,
        "time": current.get("time"),
        "temperature": current.get("temperature_2m"),
        "temperature_unit": units.get("temperature_2m", "deg"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_unit": units.get("wind_speed_10m", ""),
        "pressure": current.get("surface_pressure"),
        "pressure_unit": units.get("surface_pressure", "hPa"),
        "condition": _weather_condition(weather_code),
        "weather_code": weather_code,
        "high": _first_value(daily.get("temperature_2m_max")),
        "low": _first_value(daily.get("temperature_2m_min")),
        "precipitation_probability": _first_value(daily.get("precipitation_probability_max")),
        "sunrise": _first_value(daily.get("sunrise")),
        "sunset": _first_value(daily.get("sunset")),
        "uv_index": _first_value(daily.get("uv_index_max")),
        "forecast": [
            {
                "date": date,
                "high": high,
                "low": low,
                "weather_code": code,
                "condition": _weather_condition(code),
                "precipitation_probability": precip,
            }
            for date, high, low, code, precip in zip(
                daily.get("time", []),
                daily.get("temperature_2m_max", []),
                daily.get("temperature_2m_min", []),
                daily.get("weather_code", []),
                daily.get("precipitation_probability_max", []),
            )
        ],
    }


def _first_value(values: Any) -> Any:
    if isinstance(values, list) and values:
        return values[0]
    return None


def _weather_condition(code: Any) -> str:
    conditions = {
        0: "Clear",
        1: "Mostly clear",
        2: "Partly cloudy",
        3: "Cloudy",
        45: "Fog",
        48: "Rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        80: "Light showers",
        81: "Showers",
        82: "Heavy showers",
        95: "Thunderstorm",
    }
    return conditions.get(code, "Unknown")


def _camera_card(camera: CameraDefinition, check_ports: bool = True) -> dict[str, Any]:
    view_url = camera.view_url or _browser_view_url(camera)
    view_type = _camera_view_type(camera)
    status = "ready" if view_url else "not_configured"
    status_detail = "Camera source is configured." if view_url else "Camera source is missing credentials or a browser-viewable URL."

    if check_ports and view_type in {"mjpeg", "snapshot_proxy"} and camera.stream_url:
        rtsp_port = _rtsp_port(camera.stream_url)
        if not _tcp_reachable(camera.host, rtsp_port):
            view_url = None
            view_type = "unavailable"
            status = "offline"
            status_detail = f"RTSP port {rtsp_port} is not reachable from the Orange Pi."

    card = {
        "id": camera.host,
        "name": camera.name,
        "host": camera.host,
        "provider": camera.provider,
        "model": camera.model,
        "room": camera.room or _room_from_name(camera.name),
        "snapshot_url": camera.snapshot_url,
        "stream_url": camera.stream_url if view_type == "stream" else None,
        "view_url": view_url,
        "view_type": view_type,
        "requires_proxy": view_type == "rtsp",
        "status": status,
        "status_detail": status_detail,
        "stream_name": camera.stream_name,
        "webrtc_url": _go2rtc_player_url(camera, "webrtc"),
        "hls_url": _go2rtc_player_url(camera, "hls"),
    }
    if camera.battery_powered:
        card["battery_powered"] = True
        card["battery"] = None
    return card


def _browser_view_url(camera: CameraDefinition) -> str | None:
    if camera.snapshot_url:
        return camera.snapshot_url
    if camera.go2rtc_url and (camera.stream_url or camera.stream_name):
        return _go2rtc_player_url(camera, "webrtc")
    if camera.stream_url and camera.stream_url.startswith(("rtsp://", "rtsps://")):
        return f"/api/cameras/{camera.host}/mjpeg"
    if camera.stream_url and camera.stream_url.startswith(("http://", "https://")):
        return camera.stream_url
    return None


def _camera_view_type(camera: CameraDefinition) -> str:
    if camera.snapshot_url:
        return "snapshot"
    if camera.go2rtc_url and (camera.stream_url or camera.stream_name):
        return "webrtc"
    if camera.stream_url and camera.stream_url.startswith(("rtsp://", "rtsps://")):
        return "mjpeg"
    if camera.stream_url:
        return "stream"
    if camera.view_url:
        return "link"
    return "unknown"


def _rtsp_url_from_config(item: dict[str, Any]) -> str | None:
    username = _secret_from_config(item, "username")
    password = _secret_from_config(item, "password")
    if not username or not password:
        return None

    host = str(item["host"])
    scheme = str(item.get("rtsp_scheme", "rtsp")).rstrip(":/").lower()
    if scheme not in {"rtsp", "rtsps"}:
        scheme = "rtsp"
    default_port = 322 if scheme == "rtsps" else 554
    port = int(item.get("rtsp_port", default_port))
    stream_path = str(item.get("stream_path", "/stream1"))
    if not stream_path.startswith("/"):
        stream_path = f"/{stream_path}"

    return f"{scheme}://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}{stream_path}"


def _secret_from_config(item: dict[str, Any], key: str) -> str | None:
    direct_value = item.get(key)
    if direct_value:
        return _valid_secret(str(direct_value))

    env_name = item.get(f"{key}_env")
    if env_name:
        value = os.getenv(str(env_name))
        return _valid_secret(value) if value else None

    return None


def _valid_secret(value: str) -> str | None:
    stripped = value.strip()
    if not stripped or stripped == "replace_me":
        return None
    return stripped


def _stream_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in str(value)).strip("_")


def _go2rtc_player_url(camera: CameraDefinition, mode: str) -> str | None:
    if not camera.go2rtc_url:
        return None

    base_url = camera.go2rtc_url.rstrip("/")
    stream = quote_plus(camera.stream_name)
    if mode == "hls":
        return f"{base_url}/stream.html?src={stream}&mode=hls"
    return f"{base_url}/webrtc.html?src={stream}"


def _go2rtc_frame_url(camera: CameraDefinition) -> str | None:
    if not camera.go2rtc_url:
        return None

    base_url = camera.go2rtc_url.rstrip("/")
    return f"{base_url}/api/frame.jpeg?src={quote_plus(camera.stream_name)}"


def _capture_go2rtc_frame(camera: CameraDefinition) -> bytes | None:
    """Return a still from go2rtc, or None when it cannot supply one.

    go2rtc answers 200 with an empty body while a stream has no producer yet,
    so an empty response counts as "no frame" and the caller falls back to
    reading the camera directly.
    """
    url = _go2rtc_frame_url(camera)
    if not url:
        return None

    try:
        with urlopen(_URLRequest(url, headers={"Accept": "image/jpeg"}), timeout=15) as response:
            if response.status != 200:
                return None
            return response.read() or None
    except Exception:
        return None


def _rtsp_port(rtsp_url: str) -> int:
    parsed = urlparse(rtsp_url)
    if parsed.port:
        return parsed.port
    return 322 if parsed.scheme == "rtsps" else 554


def _tcp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _is_supported_tplink_device(item: dict[str, Any]) -> bool:
    device_type = str(item.get("device_type") or "").lower()
    model = str(item.get("model") or "").lower()
    return (
        "wallswitch" in device_type
        or "dimmer" in device_type
        or "plug" in device_type
        or model in {"hs103", "hs200", "hs220"}
    )


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


def _device_category(value: str | None) -> str:
    normalized = str(value or "").lower()
    if "plug" in normalized or normalized in {"hs103"}:
        return "smart_plug"
    return "light_switch"


def _find_switch(devices: list[DashboardDevice], host: str) -> SwitchDefinition:
    for device in devices:
        if device.switch.host == host:
            return device.switch
    raise HTTPException(status_code=404, detail=f"Device not found: {host}")


def _find_camera(cameras: list[CameraDefinition], camera_id: str) -> CameraDefinition:
    for camera in cameras:
        if camera.host == camera_id or camera.name == camera_id:
            return camera
    raise HTTPException(status_code=404, detail=f"Camera not found: {camera_id}")


def _find_tuya_device(devices: list[TuyaDefinition], device_id: str) -> TuyaDefinition:
    for device in devices:
        if device.device_id == device_id:
            return device
    raise HTTPException(status_code=404, detail=f"Tuya device not found: {device_id}")


def _mjpeg_frames(rtsp_url: str, camera: CameraDefinition) -> Iterator[bytes]:
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-analyzeduration",
            "1000000",
            "-probesize",
            "32768",
            "-rtsp_transport",
            "tcp",
            "-i",
            rtsp_url,
            "-an",
            "-vf",
            f"fps={camera.mjpeg_fps},scale={camera.mjpeg_width}:-1",
            "-q:v",
            str(camera.mjpeg_quality),
            "-f",
            "mpjpeg",
            "-boundary_tag",
            "frame",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        while process.stdout:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            yield chunk
    finally:
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()


def _capture_rtsp_frame(rtsp_url: str) -> bytes:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                rtsp_url,
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=502, detail="Timed out reading a camera frame") from exc
    if result.returncode != 0 or not result.stdout:
        raise HTTPException(status_code=502, detail="Could not read a camera frame")
    return result.stdout


def _friendly_type(value: str | None) -> str:
    if not value:
        return "Switch"
    if "." in value:
        return value.rsplit(".", 1)[-1]
    return value


def _friendly_tuya_category(value: str | None) -> str:
    normalized = str(value or "tuya_device").replace("_", " ")
    return normalized.title()


def _room_from_name(name: str) -> str:
    first_word = name.split(" switch", 1)[0].split(" light", 1)[0]
    if first_word.lower().endswith(" room"):
        return first_word.title()
    if "bedroom" in first_word.lower():
        return first_word.title()
    return first_word.title()


def _valid_bt_mac(mac: str) -> bool:
    parts = mac.split(":")
    return len(parts) == 6 and all(
        len(p) == 2 and all(c in "0123456789abcdefABCDEF" for c in p) for p in parts
    )


def _bluetoothctl(args: list[str], timeout: int) -> subprocess.CompletedProcess | None:
    """Run a bluetoothctl command; None when BlueZ is unavailable or times out."""
    try:
        return subprocess.run(
            ["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


_BT_UNAVAILABLE = {
    "status": "unavailable",
    "message": "Bluetooth is not available on this host",
    "devices": [],
}


_BT_ICON_LABELS = {
    "audio-card": "Speaker",
    "audio-headset": "Headset",
    "audio-headphones": "Headphones",
    "input-keyboard": "Keyboard",
    "input-mouse": "Mouse",
    "input-gaming": "Game controller",
    "phone": "Phone",
    "computer": "Computer",
    "video-display": "TV / Display",
    "camera-photo": "Camera",
    "watch": "Watch",
    "printer": "Printer",
}


def _bluetooth_devices_payload() -> dict[str, Any]:
    listing = _bluetoothctl(["devices"], timeout=10)
    if listing is None:
        return dict(_BT_UNAVAILABLE)
    devices = []
    for line in listing.stdout.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) < 3 or parts[0] != "Device" or not _valid_bt_mac(parts[1]):
            continue
        mac, listing_name = parts[1], parts[2]
        info = _bluetoothctl(["info", mac], timeout=10)
        text = info.stdout if info else ""
        fields = {}
        for info_line in text.splitlines():
            stripped = info_line.strip()
            for key in ("Name:", "Alias:", "Icon:"):
                if stripped.startswith(key):
                    fields[key[:-1].lower()] = stripped.split(":", 1)[1].strip()
        name = fields.get("name") or fields.get("alias") or listing_name
        paired = "Paired: yes" in text
        connected = "Connected: yes" in text
        icon = fields.get("icon", "")
        type_label = _BT_ICON_LABELS.get(icon, "")
        # BlueZ shows the dashed MAC as the name until it is resolved; those
        # are almost always anonymous BLE advertisers — hide them unless we
        # know something about them (paired, connected, or a device class).
        unresolved = name.replace("-", ":").upper() == mac.upper()
        if unresolved and not (paired or connected or type_label):
            continue
        if unresolved:
            name = f"Unknown {type_label.lower()}" if type_label else "Unknown device"
        devices.append(
            {
                "mac": mac,
                "name": name,
                "type": type_label,
                "paired": paired,
                "connected": connected,
                "icon": icon,
            }
        )
    devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return {"status": "ok", "devices": devices}


def _bluetooth_scan_payload() -> dict[str, Any]:
    _bluetoothctl(["power", "on"], timeout=10)  # idempotent; scans need a powered adapter
    scan = _bluetoothctl(["--timeout", "8", "scan", "on"], timeout=25)
    if scan is None:
        return dict(_BT_UNAVAILABLE)
    return _bluetooth_devices_payload()


def _bluetooth_connect(mac: str) -> dict[str, Any]:
    if _bluetoothctl(["show"], timeout=10) is None:
        return dict(_BT_UNAVAILABLE)
    _bluetoothctl(["pair", mac], timeout=30)  # no-op if already paired
    _bluetoothctl(["trust", mac], timeout=10)
    result = _bluetoothctl(["connect", mac], timeout=30)
    output = result.stdout if result else ""
    if "Connection successful" in output or "already connected" in output.lower():
        return {"status": "ok", "message": f"Connected to {mac}"}
    detail = output.strip().splitlines()[-1] if output.strip() else "bluetoothctl connect failed"
    return {"status": "error", "message": detail}


def _bluetooth_disconnect(mac: str) -> dict[str, Any]:
    result = _bluetoothctl(["disconnect", mac], timeout=15)
    if result is None:
        return dict(_BT_UNAVAILABLE)
    output = result.stdout
    if "Successful" in output or "not connected" in output.lower():
        return {"status": "ok", "message": f"Disconnected {mac}"}
    detail = output.strip().splitlines()[-1] if output.strip() else "bluetoothctl disconnect failed"
    return {"status": "error", "message": detail}


def _bridge_allowlist() -> set[str] | None:
    """Return the set of device_ids to expose, or None to expose all.

    Set BRIDGE_DEVICE_ALLOWLIST=kasa:192.168.0.73,kasa:192.168.0.110 to restrict
    which devices the C++ Matter bridge sees.  Unset (or empty) → all devices.
    """
    raw = os.environ.get("BRIDGE_DEVICE_ALLOWLIST", "").strip()
    if not raw:
        return None
    return {s.strip() for s in raw.split(",") if s.strip()}


async def _bridge_device_list(controller: KasaLightSwitchController | None = None) -> list[dict]:
    """Return bridgeable dashboard devices without doing live device I/O.

    Matter calls this during startup/rescan. Live Kasa status reads can block the
    FastAPI event loop long enough that even cache-only /bridge/state/all times
    out, which makes Apple Home mark the bridge No Response. State freshness is
    handled by dashboard polling and command-authoritative cache updates.
    """
    del controller
    allowlist = _bridge_allowlist()

    devices: list[dict] = []
    for dash_dev in _load_switches(DEFAULT_DISCOVERY_PATH):
        sw = dash_dev.switch
        device_id = f"kasa:{sw.host}"
        if allowlist is not None and device_id not in allowlist:
            continue

        state = bridge_sync.cached_state_for(device_id) or {"on": False}
        bridge_sync.update_state_cache(device_id, state)
        devices.append({
            "device_id": device_id,
            "name": sw.name,
            "room": _room_from_name(sw.name),
            "category": "light_switch",
            "dimmable": False,
            "state": state,
        })

    # Tuya devices
    for tuya_dev in _load_tuya_devices(DEFAULT_CONFIG_PATH):
        if allowlist is not None and tuya_dev.device_id not in allowlist:
            continue
        category = tuya_dev.category or "tuya_switch"
        bridge_sync.update_state_cache(tuya_dev.device_id, {"on": False})
        devices.append({
            "device_id": tuya_dev.device_id,
            "name": tuya_dev.name,
            "room": tuya_dev.room,
            "category": category,
            "dimmable": False,
            "state": {"on": False},
        })

    if allowlist is not None:
        devices = [d for d in devices if d["device_id"] in allowlist]
    return devices


async def _bridge_execute_command(device_id: str, command: str, controller: KasaLightSwitchController | None = None) -> None:
    """Route a command from the C++ bridge to the appropriate device controller."""
    if device_id.startswith("kasa:"):
        host = device_id[len("kasa:"):]
        _ctrl = controller or KasaLightSwitchController()
        # Look up the switch in the same discovery file the dashboard uses
        sw = next(
            (d.switch for d in _load_switches(DEFAULT_DISCOVERY_PATH) if d.switch.host == host),
            None,
        )
        if sw is None:
            raise KeyError(device_id)
        if command == "on":
            await _ctrl.turn_on(sw)
            bridge_sync.update_state_cache(device_id, {"on": True}, authoritative=True)
        elif command == "off":
            await _ctrl.turn_off(sw)
            bridge_sync.update_state_cache(device_id, {"on": False}, authoritative=True)
        elif command == "toggle":
            await _ctrl.toggle(sw)
            try:
                st = await _ctrl.status(sw)
                if st:
                    bridge_sync.update_state_cache(device_id, {"on": st.is_on}, authoritative=True)
            except Exception:  # noqa: BLE001
                pass
        else:
            raise ValueError(f"Unknown command: {command}")
        return

    # Tuya
    tuya_devices = _load_tuya_devices(DEFAULT_CONFIG_PATH)
    tuya_dev = next((d for d in tuya_devices if d.device_id == device_id), None)
    if tuya_dev is None:
        raise KeyError(device_id)
    if command not in {"on", "off", "toggle"}:
        raise ValueError(f"Unknown command: {command}")
    current = await asyncio.to_thread(_tuya_current_status, tuya_dev)
    current_value = _tuya_power_value(current, tuya_dev.power_dp)
    next_value = not current_value if command == "toggle" else command == "on"
    await asyncio.to_thread(_tuya_set_power, tuya_dev, next_value)


app = create_app()
