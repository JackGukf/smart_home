from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator
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
from pydantic import BaseModel
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
import yaml

from src.python.tplink_switch import KasaLightSwitchController, SwitchDefinition
from src.python.matter_device import DashboardMatterClient, node_to_device


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISCOVERY_PATH = PROJECT_ROOT / "tplink_switches.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "devices.local.yaml"
STATIC_DIR = PROJECT_ROOT / "src" / "python" / "web_static"
AMBIENT_LIGHT_RUNTIME_STATE: dict[str, dict[str, Any]] = {}

_raw_cfg: dict = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {} if DEFAULT_CONFIG_PATH.exists() else {}
_matter_cfg: dict = _raw_cfg.get("matter") or {}
_matter_server_url: str = _matter_cfg.get("server_url", "ws://localhost:5580/ws")
_matter_device_meta: dict[int, dict] = {
    int(d["node_id"]): d
    for d in (_matter_cfg.get("devices") or [])
    if "node_id" in d
}
_matter_client = DashboardMatterClient(_matter_server_url)


class _MatterCommissionBody(BaseModel):
    setup_code: str
    name: str
    room: str | None = None


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


class ClimateUpdateRequest(BaseModel):
    hvac_mode: str | None = None
    preset_mode: str | None = None
    preset_entity_id: str | None = None
    temperature: float | None = None
    target_temp_low: float | None = None
    target_temp_high: float | None = None


def create_app(
    discovery_path: Path = DEFAULT_DISCOVERY_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    controller: KasaLightSwitchController | None = None,
    check_camera_ports: bool = True,
) -> FastAPI:
    app = FastAPI(title="Smart Home Raspberry Pi 4 Dashboard")
    app.state.discovery_path = discovery_path
    app.state.config_path = config_path
    app.state.controller = controller or KasaLightSwitchController()
    app.state.check_camera_ports = check_camera_ports

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
                # Always allow login/logout and static assets
                if path in _SKIP_PATHS or path.startswith("/static/"):
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

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/devices")
    async def devices() -> dict[str, list[dict[str, Any]]]:
        return {"devices": await _device_cards(app)}

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
        return {"lights": _ambient_light_cards(app.state.config_path)}

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
        if light.provider != "govee_ble":
            raise HTTPException(status_code=400, detail=f"Unsupported ambient provider: {light.provider}")
        if not light.address:
            raise HTTPException(status_code=400, detail="Govee BLE light needs a Bluetooth address from Pi discovery before it can be controlled.")
        return await asyncio.to_thread(_govee_ble_command_payload, light, command, body or {})

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

    @app.post("/api/home-assistant/entities/{entity_id}/commands/{command}")
    async def home_assistant_command(entity_id: str, command: str) -> dict[str, Any]:
        return await asyncio.to_thread(_home_assistant_service_command, app.state.config_path, entity_id, command)

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
        )

    @app.get("/api/cameras/{camera_id}/snapshot.jpg")
    async def camera_snapshot(camera_id: str) -> Response:
        camera = _find_camera(_load_cameras(app.state.config_path), camera_id)
        if not camera.stream_url or not camera.stream_url.startswith(("rtsp://", "rtsps://")):
            raise HTTPException(status_code=400, detail="Camera does not have an RTSP stream URL")
        if not shutil.which("ffmpeg"):
            raise HTTPException(status_code=503, detail="ffmpeg is required for camera snapshots")

        return Response(
            _capture_rtsp_frame(camera.stream_url),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/devices/{host}/commands/{command}")
    async def command(host: str, command: str) -> dict[str, Any]:
        switch = _find_switch(_load_switches(app.state.discovery_path), host)
        controller = app.state.controller

        if command == "on":
            state = await controller.turn_on(switch)
        elif command == "off":
            state = await controller.turn_off(switch)
        elif command == "toggle":
            state = await controller.toggle(switch)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported command: {command}")

        return asdict(state)

    @app.post("/api/devices/{host}/brightness")
    async def set_brightness(host: str, body: dict[str, Any]) -> dict[str, Any]:
        level = int(body.get("level", 50))
        switch = _find_switch(_load_switches(app.state.discovery_path), host)
        state = await app.state.controller.set_brightness(switch, level)
        return asdict(state)

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

    return app


async def _device_cards(app: FastAPI) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for device in _load_switches(app.state.discovery_path):
        switch = device.switch
        try:
            state = await app.state.controller.status(switch)
            is_on = state.is_on
            brightness = state.brightness
        except Exception:
            is_on = None
            brightness = None

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
    return cards


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
    return Response(payload, media_type=content_type or "image/jpeg", headers={"Cache-Control": "no-store"})


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

    return StreamingResponse(chunks(), media_type=media_type, headers={"Cache-Control": "no-store"})


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
    cards = [
        _tuya_home_assistant_card(entity)
        for entity in states
        if _is_tuya_home_assistant_entity(entity, tplink_names)
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


def _is_tuya_home_assistant_entity(entity: dict[str, Any], tplink_names: set[str] | None = None) -> bool:
    entity_id = str(entity.get("entity_id") or "")
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
    for item in payload.get("ambient_lights", {}).get("devices", []):
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


def _ambient_light_id(light: AmbientLightDefinition) -> str:
    return quote(light.name, safe="")


def _is_real_ble_address(address: str | None) -> bool:
    if not address:
        return False
    value = address.strip().lower()
    return value not in {"replace_me", "todo", "none", "null", "unknown"}


def _ambient_light_card(light: AmbientLightDefinition) -> dict[str, Any]:
    runtime_state = AMBIENT_LIGHT_RUNTIME_STATE.get(light.address or light.name, {})
    if light.provider == "govee_ble":
        has_address = _is_real_ble_address(light.address)
        status = "configured" if has_address else "needs_ble_address"
        note = "BLE address configured" if has_address else "Run Govee BLE discovery on the Raspberry Pi and add the address."
        controllable = has_address
    elif light.provider == "alexa":
        status = "needs_alexa_bridge"
        note = "Lepro is reachable from Alexa, but dashboard control needs an Alexa routine/bridge path."
        controllable = False
    else:
        status = "unsupported"
        note = "Unsupported ambient light provider."
        controllable = False
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
            "power": light.provider == "govee_ble" and controllable,
            "brightness": light.provider == "govee_ble" and controllable,
            "color": light.provider == "govee_ble" and controllable,
        },
    }


def _ambient_light_cards(path: Path) -> list[dict[str, Any]]:
    return [_ambient_light_card(light) for light in _load_ambient_lights(path)]


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
            "message": "Install bleak on the Raspberry Pi to scan Govee Bluetooth devices.",
            "error": str(exc),
            "devices": [],
        }

    async def _scan() -> list[dict[str, Any]]:
        found = await BleakScanner.discover(timeout=8.0)
        devices = []
        for item in found:
            name = item.name or ""
            text = f"{name} {item.address}".lower()
            if "govee" not in text and "h613a" not in text and "h6054" not in text:
                continue
            devices.append({"name": name, "address": item.address, "rssi": getattr(item, "rssi", None)})
        return devices

    return {"status": "ok", "devices": asyncio.run(_scan())}


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
            for other_address in list(self._clients):
                if other_address != light.address:
                    await self._drop_client(other_address)
            await asyncio.to_thread(_govee_ble_forget_cached_device, light.address)
            initial_delay = 5 if (light.model or "").upper() == "H613A" else 1
            await asyncio.sleep(initial_delay)
            device = await BleakScanner.find_device_by_address(light.address, timeout=8.0)
            target = device or light.address
            client = BleakClient(
                target,
                timeout=12.0,
                disconnected_callback=lambda _client: self._clients.pop(light.address or "", None),
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
        raise HTTPException(status_code=503, detail=f"Install bleak on the Raspberry Pi for Govee BLE control: {exc}") from exc

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
            status_detail = f"RTSP port {rtsp_port} is not reachable from the Raspberry Pi."

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


app = create_app()
