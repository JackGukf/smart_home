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
