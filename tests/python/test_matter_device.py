from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.python.matter_device import (
    DashboardMatterClient,
    MatterServerUnavailable,
    _detect_category,
    _extract_node_id,
    node_to_device,
    primary_endpoint,
)


# ── fakes shaped like matter_server.client.models.node ──────────────────
#
# The real MatterNode exposes typed endpoints (not a raw attribute dict), so
# the doubles below mirror that API: device_types is a set of classes carrying
# a `device_type` int, and get_attribute_value takes (cluster_id, attribute_id).


def _device_type(type_id: int):
    return type("FakeDeviceType", (), {"device_type": type_id})


class FakeEndpoint:
    def __init__(self, endpoint_id: int, device_type_ids=(), attributes=None):
        self.endpoint_id = endpoint_id
        self.device_types = {_device_type(t) for t in device_type_ids}
        self._attributes = attributes or {}

    def get_attribute_value(self, cluster_id, attribute_id):
        return self._attributes.get((cluster_id, attribute_id))


class FakeNode:
    def __init__(self, node_id=1, endpoints=(), available=True):
        self.node_id = node_id
        self.available = available
        self.endpoints = {ep.endpoint_id: ep for ep in endpoints}


def _root_endpoint():
    """Endpoint 0 is the Matter root node; it must never be picked."""
    return FakeEndpoint(0, device_type_ids=(0x0016,))


def _light_node(node_id=1, device_type=0x0100, on=True, level=None, available=True):
    attributes = {(6, 0): on}
    if level is not None:
        attributes[(8, 0)] = level
    return FakeNode(
        node_id=node_id,
        endpoints=[_root_endpoint(), FakeEndpoint(1, (device_type,), attributes)],
        available=available,
    )


# ── category detection ──────────────────────────────────────────────────


def test_detect_category_onoff_light():
    assert _detect_category(FakeEndpoint(1, (0x0100,))) == ("light_switch", False)


def test_detect_category_dimmable_light():
    assert _detect_category(FakeEndpoint(1, (0x0101,))) == ("light_switch", True)


def test_detect_category_plug():
    assert _detect_category(FakeEndpoint(1, (0x010A,))) == ("smart_plug", False)


def test_detect_category_temp_sensor():
    assert _detect_category(FakeEndpoint(1, (0x0302,))) == ("tuya_sensor", False)


def test_detect_category_unknown_defaults_to_plug():
    assert _detect_category(FakeEndpoint(1)) == ("smart_plug", False)


def test_detect_category_unknown_with_level_cluster_is_dimmable():
    endpoint = FakeEndpoint(1, (0x0abc,), {(8, 0): 100})
    assert _detect_category(endpoint) == ("smart_plug", True)


# ── endpoint selection ──────────────────────────────────────────────────


def test_primary_endpoint_skips_root():
    node = _light_node()
    assert primary_endpoint(node).endpoint_id == 1


def test_primary_endpoint_prefers_known_device_type():
    node = FakeNode(endpoints=[
        _root_endpoint(),
        FakeEndpoint(1, (0xF000,)),
        FakeEndpoint(2, (0x0101,)),
    ])
    assert primary_endpoint(node).endpoint_id == 2


def test_primary_endpoint_falls_back_to_onoff_cluster():
    node = FakeNode(endpoints=[
        _root_endpoint(),
        FakeEndpoint(3, (0xF000,)),
        FakeEndpoint(7, (0xF001,), {(6, 0): False}),
    ])
    assert primary_endpoint(node).endpoint_id == 7


def test_primary_endpoint_none_when_only_root():
    assert primary_endpoint(FakeNode(endpoints=[_root_endpoint()])) is None


# ── node → dashboard device ─────────────────────────────────────────────


def test_node_to_device_basic():
    info = node_to_device(_light_node(), "Kitchen Light", "Kitchen")
    assert info.is_on is True
    assert info.category == "light_switch"
    assert info.provider == "matter"
    assert info.node_id == 1
    assert info.name == "Kitchen Light"
    assert info.room == "Kitchen"
    assert info.endpoint_id == 1


def test_node_to_device_off():
    assert node_to_device(_light_node(on=False), "Lamp", None).is_on is False


def test_node_to_device_category_override():
    node = _light_node(device_type=0x010A)
    info = node_to_device(node, "Switch", None, category_override="light_switch")
    assert info.category == "light_switch"


def test_node_to_device_brightness():
    node = _light_node(device_type=0x0101, level=127)
    info = node_to_device(node, "Dimmer", "Bedroom")
    assert info.brightness == round((127 / 254) * 100)
    assert info.is_dimmable is True


def test_node_to_device_no_brightness_attr_defaults_100():
    info = node_to_device(_light_node(device_type=0x0101), "Dimmer", None)
    assert info.brightness == 100


def test_node_to_device_unavailable():
    node = _light_node(available=False)
    assert node_to_device(node, "Offline", None).available is False


def test_node_to_device_uses_non_default_endpoint():
    node = FakeNode(endpoints=[
        _root_endpoint(),
        FakeEndpoint(4, (0x0101,), {(6, 0): True, (8, 0): 254}),
    ])
    info = node_to_device(node, "Bridged Light", None)
    assert info.endpoint_id == 4
    assert info.is_on is True
    assert info.brightness == 100


def test_node_to_device_root_only_node_is_safe():
    info = node_to_device(FakeNode(endpoints=[_root_endpoint()]), "Weird", None)
    assert info.category == "smart_plug"
    assert info.is_on is False
    assert info.endpoint_id == 1


# ── commission result unwrapping ────────────────────────────────────────


def test_extract_node_id_from_node_data():
    assert _extract_node_id(types.SimpleNamespace(node_id=12)) == 12


def test_extract_node_id_from_dict():
    assert _extract_node_id({"node_id": 7}) == 7


def test_extract_node_id_from_int():
    assert _extract_node_id(5) == 5


def test_extract_node_id_rejects_garbage():
    with pytest.raises(RuntimeError):
        _extract_node_id(object())


# ── client wrapper ──────────────────────────────────────────────────────


@pytest.fixture
def fake_chip_clusters(monkeypatch):
    """Stub chip.clusters.Objects; the real wheel is aarch64/py3.12 only."""

    def _command(name, cluster_id):
        return type(name, (), {"cluster_id": cluster_id, "__init__": _init})

    def _init(self, **kwargs):
        self.__dict__.update(kwargs)

    objects = types.SimpleNamespace(
        OnOff=types.SimpleNamespace(
            Commands=types.SimpleNamespace(
                On=_command("On", 6),
                Off=_command("Off", 6),
                Toggle=_command("Toggle", 6),
            )
        ),
        LevelControl=types.SimpleNamespace(
            Commands=types.SimpleNamespace(
                MoveToLevelWithOnOff=_command("MoveToLevelWithOnOff", 8),
            )
        ),
    )
    chip = types.ModuleType("chip")
    chip_clusters = types.ModuleType("chip.clusters")
    chip_clusters.Objects = objects
    chip.clusters = chip_clusters
    monkeypatch.setitem(sys.modules, "chip", chip)
    monkeypatch.setitem(sys.modules, "chip.clusters", chip_clusters)
    return objects


def _connected_client(inner):
    client = DashboardMatterClient()
    client._client = inner
    # a live listener task is what _connection_alive() looks for
    client._listen_task = asyncio.get_event_loop().create_future()
    inner.connection = MagicMock(connected=True)
    return client


@pytest.mark.asyncio
async def test_client_list_nodes():
    inner = MagicMock()
    inner.get_nodes.return_value = [_light_node(1), _light_node(2)]
    client = _connected_client(inner)
    assert len(await client.list_nodes()) == 2


@pytest.mark.asyncio
async def test_client_commission_returns_node_id_from_node_data():
    inner = AsyncMock()
    inner.commission_with_code = AsyncMock(
        return_value=types.SimpleNamespace(node_id=5)
    )
    client = _connected_client(inner)
    assert await client.commission("34970112332") == 5
    inner.commission_with_code.assert_awaited_once_with("34970112332")


@pytest.mark.asyncio
async def test_client_send_on(fake_chip_clusters):
    inner = AsyncMock()
    inner.get_node = MagicMock(return_value=_light_node())
    client = _connected_client(inner)
    await client.send_command(1, "on")
    kwargs = inner.send_device_command.call_args.kwargs
    assert kwargs["node_id"] == 1
    assert kwargs["endpoint_id"] == 1
    assert type(kwargs["command"]).__name__ == "On"


@pytest.mark.asyncio
async def test_client_send_off(fake_chip_clusters):
    inner = AsyncMock()
    inner.get_node = MagicMock(return_value=_light_node())
    client = _connected_client(inner)
    await client.send_command(1, "off")
    assert type(inner.send_device_command.call_args.kwargs["command"]).__name__ == "Off"


@pytest.mark.asyncio
async def test_client_send_brightness(fake_chip_clusters):
    inner = AsyncMock()
    inner.get_node = MagicMock(return_value=_light_node(device_type=0x0101, level=10))
    client = _connected_client(inner)
    await client.send_command(1, "brightness", brightness=50)
    command = inner.send_device_command.call_args.kwargs["command"]
    assert type(command).__name__ == "MoveToLevelWithOnOff"
    assert command.level == round(0.5 * 254)


@pytest.mark.asyncio
async def test_client_send_brightness_zero_stays_in_matter_range(fake_chip_clusters):
    inner = AsyncMock()
    inner.get_node = MagicMock(return_value=_light_node(device_type=0x0101, level=10))
    client = _connected_client(inner)
    await client.send_command(1, "brightness", brightness=0)
    assert inner.send_device_command.call_args.kwargs["command"].level == 1


@pytest.mark.asyncio
async def test_client_send_command_targets_the_devices_endpoint(fake_chip_clusters):
    node = FakeNode(endpoints=[_root_endpoint(), FakeEndpoint(6, (0x0100,), {(6, 0): True})])
    inner = AsyncMock()
    inner.get_node = MagicMock(return_value=node)
    client = _connected_client(inner)
    await client.send_command(1, "on")
    assert inner.send_device_command.call_args.kwargs["endpoint_id"] == 6


@pytest.mark.asyncio
async def test_client_rejects_unknown_command(fake_chip_clusters):
    inner = AsyncMock()
    inner.get_node = MagicMock(return_value=_light_node())
    client = _connected_client(inner)
    with pytest.raises(ValueError):
        await client.send_command(1, "explode")


@pytest.mark.asyncio
async def test_client_remove_node():
    inner = AsyncMock()
    client = _connected_client(inner)
    await client.remove_node(3)
    inner.remove_node.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_client_reconnects_when_listener_died():
    """A dead listener means stale nodes and hung commands: force a reconnect."""
    inner = MagicMock()
    inner.connection = MagicMock(connected=True)
    client = DashboardMatterClient()
    client._client = inner
    dead = asyncio.get_event_loop().create_future()
    dead.set_result(None)
    client._listen_task = dead
    assert client._connection_alive() is False


@pytest.mark.asyncio
async def test_client_surfaces_unavailable_server():
    client = DashboardMatterClient("ws://127.0.0.1:1/ws")

    async def _boom() -> None:
        raise OSError("connection refused")

    client._connect = _boom  # type: ignore[method-assign]
    with pytest.raises(MatterServerUnavailable):
        await client.list_nodes()
