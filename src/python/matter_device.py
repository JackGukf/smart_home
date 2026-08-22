from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Matter Descriptor cluster device type IDs → (dashboard category, is_dimmable)
_DEVICE_TYPE_MAP: dict[int, tuple[str, bool]] = {
    0x0100: ("light_switch", False),   # On/Off Light
    0x0101: ("light_switch", True),    # Dimmable Light
    0x0103: ("light_switch", False),   # On/Off Light Switch
    0x0104: ("light_switch", True),    # Dimmer Switch
    0x010A: ("smart_plug",   False),   # On/Off Plug-In Unit
    0x010B: ("smart_plug",   True),    # Dimmable Plug-In Unit
    0x010D: ("light_switch", True),    # Extended Color Light
    0x0302: ("tuya_sensor",  False),   # Temperature Sensor
}

_ONOFF_CLUSTER = 6
_LEVEL_CLUSTER = 8
_ONOFF_ATTR = 0        # OnOff.onOff
_CURRENT_LEVEL_ATTR = 0  # LevelControl.currentLevel

# Commissioning over BLE routinely takes longer than a minute on a busy radio.
DEFAULT_COMMISSION_TIMEOUT = 180.0
DEFAULT_CONNECT_TIMEOUT = 15.0


class MatterServerUnavailable(RuntimeError):
    """Raised when the Matter Server cannot be reached."""


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
    endpoint_id: int = 1
    provider: str = "matter"


def _endpoint_device_type_ids(endpoint: Any) -> list[int]:
    """Return the Matter device type IDs declared by a MatterEndpoint."""
    ids: list[int] = []
    for device_type in getattr(endpoint, "device_types", None) or ():
        type_id = getattr(device_type, "device_type", None)
        if isinstance(type_id, int):
            ids.append(type_id)
    return ids


def _endpoint_attribute(endpoint: Any, cluster_id: int, attribute_id: int) -> Any:
    getter = getattr(endpoint, "get_attribute_value", None)
    if getter is None:
        return None
    try:
        return getter(cluster_id, attribute_id)
    except Exception:  # unknown cluster on this endpoint
        return None


def _detect_category(endpoint: Any) -> tuple[str, bool]:
    """Return (category, is_dimmable) for a MatterEndpoint.

    Falls back to the presence of the LevelControl cluster when the endpoint
    declares a device type we do not have an explicit mapping for.
    """
    for type_id in _endpoint_device_type_ids(endpoint):
        if type_id in _DEVICE_TYPE_MAP:
            return _DEVICE_TYPE_MAP[type_id]
    has_level = _endpoint_attribute(endpoint, _LEVEL_CLUSTER, _CURRENT_LEVEL_ATTR) is not None
    return ("smart_plug", has_level)


def primary_endpoint(node: Any) -> Any:
    """Pick the endpoint that represents the controllable device.

    Endpoint 0 is the Matter root node (no application clusters), so it is
    never the answer.  Prefer an endpoint whose device type we recognise, then
    any endpoint exposing the On/Off cluster, then simply the lowest one.
    """
    endpoints: dict[int, Any] = getattr(node, "endpoints", None) or {}
    candidates = [(eid, ep) for eid, ep in sorted(endpoints.items()) if eid != 0]
    if not candidates:
        return None
    for _eid, endpoint in candidates:
        if any(t in _DEVICE_TYPE_MAP for t in _endpoint_device_type_ids(endpoint)):
            return endpoint
    for _eid, endpoint in candidates:
        if _endpoint_attribute(endpoint, _ONOFF_CLUSTER, _ONOFF_ATTR) is not None:
            return endpoint
    return candidates[0][1]


def node_to_device(
    node: Any,
    name: str,
    room: str | None,
    category_override: str | None = None,
) -> MatterDeviceInfo:
    """Map a python-matter-server MatterNode to a dashboard MatterDeviceInfo."""
    endpoint = primary_endpoint(node)
    detected_category, detected_dimmable = (
        _detect_category(endpoint) if endpoint is not None else ("smart_plug", False)
    )
    category = category_override or detected_category
    is_dimmable = detected_dimmable and category in ("light_switch", "smart_plug")

    is_on = bool(_endpoint_attribute(endpoint, _ONOFF_CLUSTER, _ONOFF_ATTR))
    raw_level = _endpoint_attribute(endpoint, _LEVEL_CLUSTER, _CURRENT_LEVEL_ATTR)
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
        endpoint_id=getattr(endpoint, "endpoint_id", 1) if endpoint is not None else 1,
    )


class DashboardMatterClient:
    """Thin async wrapper around python-matter-server's WebSocket client.

    The upstream client only populates its node cache — and only pumps the
    WebSocket read loop that resolves command futures — while
    ``start_listening()`` is running.  Connecting without it leaves
    ``get_nodes()`` empty and makes every command hang forever, so this wrapper
    owns that background task for the lifetime of the connection.
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:5580/ws",
        commission_timeout: float = DEFAULT_COMMISSION_TIMEOUT,
    ) -> None:
        self._url = server_url
        self._client: Any = None
        self._session: Any = None
        self._listen_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.commission_timeout = commission_timeout

    # ── connection lifecycle ────────────────────────────────────────────

    def _connection_alive(self) -> bool:
        if self._client is None:
            return False
        if self._listen_task is not None and self._listen_task.done():
            return False
        connection = getattr(self._client, "connection", None)
        if connection is not None and not getattr(connection, "connected", True):
            return False
        return True

    async def _ensure_connected(self) -> Any:
        async with self._lock:
            if self._connection_alive():
                return self._client
            await self._teardown()
            try:
                await self._connect()
            except MatterServerUnavailable:
                await self._teardown()
                raise
            except Exception as exc:
                await self._teardown()
                raise MatterServerUnavailable(
                    f"Cannot reach Matter Server at {self._url}: {exc}"
                ) from exc
            return self._client

    async def _connect(self) -> None:
        import aiohttp
        from matter_server.client import MatterClient

        self._session = aiohttp.ClientSession()
        self._client = MatterClient(self._url, self._session)
        await self._client.connect()

        # start_listening() fetches the full node dump and then keeps reading
        # incoming messages; nothing else works until init_ready is set.
        init_ready = asyncio.Event()
        self._listen_task = asyncio.create_task(
            self._client.start_listening(init_ready)
        )
        ready = asyncio.ensure_future(init_ready.wait())
        try:
            await asyncio.wait(
                {ready, self._listen_task},
                timeout=DEFAULT_CONNECT_TIMEOUT,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            ready.cancel()

        if init_ready.is_set():
            return
        if self._listen_task.done():
            # Surface the real failure from the listener instead of a timeout.
            exc = self._listen_task.exception()
            raise MatterServerUnavailable(
                f"Matter Server listener stopped during startup: {exc}"
                if exc
                else "Matter Server closed the connection during startup"
            )
        raise MatterServerUnavailable(
            f"Timed out waiting for the Matter Server node dump from {self._url}"
        )

    async def _teardown(self) -> None:
        task, self._listen_task = self._listen_task, None
        client, self._client = self._client, None
        session, self._session = self._session, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                _LOGGER.debug("Matter client disconnect failed", exc_info=True)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if session is not None:
            try:
                await session.close()
            except Exception:
                _LOGGER.debug("Matter session close failed", exc_info=True)

    # ── operations ──────────────────────────────────────────────────────

    async def list_nodes(self) -> list[Any]:
        client = await self._ensure_connected()
        return list(client.get_nodes())

    async def commission(self, setup_code: str) -> int:
        """Commission a device. Returns the node_id assigned by Matter Server."""
        client = await self._ensure_connected()
        result = await asyncio.wait_for(
            client.commission_with_code(setup_code),
            timeout=self.commission_timeout,
        )
        return _extract_node_id(result)

    async def _endpoint_for(self, node_id: int, cluster_id: int) -> int:
        client = await self._ensure_connected()
        try:
            node = client.get_node(node_id)
        except Exception:
            return 1
        endpoint = primary_endpoint(node)
        if endpoint is None:
            return 1
        if _endpoint_attribute(endpoint, cluster_id, 0) is None:
            for eid, candidate in sorted((getattr(node, "endpoints", None) or {}).items()):
                if eid == 0:
                    continue
                if _endpoint_attribute(candidate, cluster_id, 0) is not None:
                    return eid
        return getattr(endpoint, "endpoint_id", 1)

    async def send_command(
        self,
        node_id: int,
        command: str,
        brightness: int | None = None,
    ) -> None:
        from chip.clusters import Objects as clusters

        client = await self._ensure_connected()
        if command in ("on", "off", "toggle"):
            cluster_command = {
                "on": clusters.OnOff.Commands.On,
                "off": clusters.OnOff.Commands.Off,
                "toggle": clusters.OnOff.Commands.Toggle,
            }[command]()
            endpoint_id = await self._endpoint_for(node_id, _ONOFF_CLUSTER)
        elif command == "brightness" and brightness is not None:
            level = max(1, min(254, round((brightness / 100) * 254)))
            cluster_command = clusters.LevelControl.Commands.MoveToLevelWithOnOff(
                level=level,
                transitionTime=0,
                optionsMask=0,
                optionsOverride=0,
            )
            endpoint_id = await self._endpoint_for(node_id, _LEVEL_CLUSTER)
        else:
            raise ValueError(f"Unsupported Matter command: {command}")

        await client.send_device_command(
            node_id=node_id,
            endpoint_id=endpoint_id,
            command=cluster_command,
        )

    async def remove_node(self, node_id: int) -> None:
        client = await self._ensure_connected()
        await client.remove_node(node_id)

    async def close(self) -> None:
        async with self._lock:
            await self._teardown()


def _extract_node_id(result: Any) -> int:
    """commission_with_code returns MatterNodeData; older builds returned an int."""
    if isinstance(result, int):
        return result
    node_id = getattr(result, "node_id", None)
    if node_id is None and isinstance(result, dict):
        node_id = result.get("node_id")
    if node_id is None:
        raise RuntimeError(f"Matter Server returned no node_id (got {result!r})")
    return int(node_id)
