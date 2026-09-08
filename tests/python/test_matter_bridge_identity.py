"""Naming a Matter node, and keeping our own bridge out of the light switches.

The bridge was listed as "Matter Device 3" while announcing "Smart Home AI /
Dashboard Bridge" in an attribute nothing read, and it appeared among the
lights as something to switch on -- which it is not: it is the thing that
publishes the lights.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASIC_INFO = 40
VENDOR, PRODUCT, NODE_LABEL = 1, 3, 5


class _Endpoint:
    def __init__(self, attributes: dict[tuple[int, int], object], device_types=()) -> None:
        self._attributes = attributes
        self.device_types = [SimpleNamespace(device_type=t) for t in device_types]

    def get_attribute_value(self, cluster_id: int, attribute_id: int):
        return self._attributes.get((cluster_id, attribute_id))


def _node(node_id: int, *, vendor="", product="", label="", is_bridge=False, extra=None):
    root = _Endpoint({(BASIC_INFO, VENDOR): vendor,
                      (BASIC_INFO, PRODUCT): product,
                      (BASIC_INFO, NODE_LABEL): label})
    endpoints = {0: root}
    endpoints.update(extra or {})
    return SimpleNamespace(node_id=node_id, endpoints=endpoints, is_bridge=is_bridge, available=True)


def test_a_node_is_named_from_what_it_announces() -> None:
    from src.python.matter_device import node_display_name

    # The case that started this: vendor and product were there all along.
    assert node_display_name(_node(3, vendor="Smart Home AI", product="Dashboard Bridge")) \
        == "Smart Home AI Dashboard Bridge"
    # A label its owner set beats anything derived.
    assert node_display_name(_node(3, vendor="Smart Home AI", product="Dashboard Bridge",
                                   label="Hall bridge")) == "Hall bridge"
    # Product often already carries the maker; "TP-Link TP-Link ..." reads badly.
    assert node_display_name(_node(2, vendor="TP-Link", product="TP-Link Smart Switch")) \
        == "TP-Link Smart Switch"
    assert node_display_name(_node(2, vendor="", product="Smart Wi-Fi Switch")) == "Smart Wi-Fi Switch"


def test_the_chip_sdk_placeholders_do_not_become_names() -> None:
    """More than one node here still advertises TEST_VENDOR/TEST_PRODUCT -- the
    collision the bridge runbook warns about. A name several nodes share is
    worse than a numbered one, so those fall back to the number."""
    from src.python.matter_device import node_display_name

    assert node_display_name(_node(1, vendor="TEST_VENDOR", product="TEST_PRODUCT")) == "Matter Device 1"
    assert node_display_name(_node(9)) == "Matter Device 9"
    # No endpoints at all is still a name, not a crash.
    assert node_display_name(SimpleNamespace(node_id=4, endpoints={})) == "Matter Device 4"


def test_our_own_bridge_is_not_a_light_to_switch_on() -> None:
    from src.python.matter_device import is_bridge_node, node_to_device

    bridge = _node(3, vendor="Smart Home AI", product="Dashboard Bridge", is_bridge=True,
                   extra={1: _Endpoint({}, device_types=(14,))})   # 14 = Aggregator
    assert is_bridge_node(bridge)

    info = node_to_device(bridge, name="Smart Home AI Dashboard Bridge", room=None)
    # Without this it fell through _detect_category and was called a plug.
    assert info.category == "bridge"
    assert info.is_dimmable is False

    # A real light is unaffected.
    light = _node(2, product="Smart Wi-Fi Switch",
                  extra={1: _Endpoint({(6, 0): True}, device_types=(256,))})
    assert not is_bridge_node(light)
    assert node_to_device(light, name="x", room=None).category == "light_switch"


def test_the_bridge_is_grouped_with_the_other_radios() -> None:
    """Zigbee coordinator, Tuya gateway and now the Matter bridge read as one
    set under Bridges, using the same tile shape."""
    source = (PROJECT_ROOT / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")

    assert "function isMatterBridgeDevice(device)" in source
    assert "function matterBridgeDevice(device)" in source

    inventory = source.split("function collectHomeInventory()")[1].split("\n/* ── Device group")[0]
    assert "isMatterBridgeDevice(device)" in inventory, "the bridge still lands among the lights"
    assert 'kind: "bridge"' in inventory
    # Same shape the other two bridges produce, so bridgeTileHtml needs no branch.
    tile = source.split("function matterBridgeDevice(device)")[1].split("\nfunction ")[0]
    for field in ("id:", "name:", "icon:", "state:", "label:", "meta:"):
        assert field in tile, f"bridge tile is missing {field}"


def test_the_api_reports_whether_a_node_is_a_bridge() -> None:
    source = (PROJECT_ROOT / "src" / "python" / "web_app.py").read_text(encoding="utf-8")

    assert '"is_bridge": is_bridge_node(node),' in source
    # The node's own name is asked for before falling back to its number.
    assert 'name=meta.get("name") or node_display_name(node),' in source
