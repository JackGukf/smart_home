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
