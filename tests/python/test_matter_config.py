from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch


def _import_helpers():
    from src.python import web_app
    return web_app._write_matter_device_to_config, web_app._remove_matter_device_from_config


def test_write_matter_device_creates_section(tmp_path):
    config = tmp_path / "devices.local.yaml"
    write_fn, _ = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        write_fn(1, "Kitchen Switch", "Kitchen")
    data = yaml.safe_load(config.read_text())
    assert data["matter"]["devices"][0] == {"node_id": 1, "name": "Kitchen Switch", "room": "Kitchen"}


def test_write_matter_device_no_room(tmp_path):
    config = tmp_path / "devices.local.yaml"
    write_fn, _ = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        write_fn(2, "Plug", None)
    data = yaml.safe_load(config.read_text())
    assert "room" not in data["matter"]["devices"][0]


def test_write_matter_device_overwrites_existing(tmp_path):
    config = tmp_path / "devices.local.yaml"
    config.write_text("matter:\n  devices:\n  - {node_id: 1, name: Old}\n")
    write_fn, _ = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        write_fn(1, "New Name", "Bedroom")
    data = yaml.safe_load(config.read_text())
    assert len(data["matter"]["devices"]) == 1
    assert data["matter"]["devices"][0]["name"] == "New Name"


def test_remove_matter_device(tmp_path):
    config = tmp_path / "devices.local.yaml"
    config.write_text("matter:\n  devices:\n  - {node_id: 1, name: Switch}\n  - {node_id: 2, name: Plug}\n")
    _, remove_fn = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        remove_fn(1)
    data = yaml.safe_load(config.read_text())
    assert len(data["matter"]["devices"]) == 1
    assert data["matter"]["devices"][0]["node_id"] == 2


def test_remove_matter_device_missing_config(tmp_path):
    config = tmp_path / "nonexistent.yaml"
    _, remove_fn = _import_helpers()
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        remove_fn(1)  # Must not raise


def test_matter_bridge_config_raises_linux_packet_buffer_capacity():
    config = Path("src/cpp/matter_bridge/CHIPProjectConfig.h")
    content = config.read_text()

    assert "#define CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE 0" in content
    assert "#define CHIP_SYSTEM_CONFIG_PACKETBUFFER_CAPACITY_MAX 9050" in content


def test_matter_bridge_keeps_the_example_dac_vendor_and_product_ids():
    """The bridge is named for the humans reading Apple Home, Home Assistant and
    matter-server -- all three showed it as the SDK's placeholder TEST_VENDOR /
    TEST_PRODUCT, which is also what the office Stick S3 advertises, and that
    collision put a wrong identification into the runbook on 2026-09-04.

    The IDs are a different matter: the example DAC attests VID 0xFFF1, so
    overriding CHIP_DEVICE_CONFIG_DEVICE_VENDOR_ID would fail attestation and
    stop commissioning at "Pairing failed" (Bug 3, docs/matter-bridge.md).
    """
    content = Path("src/cpp/matter_bridge/CHIPProjectConfig.h").read_text()

    assert 'CHIP_DEVICE_CONFIG_DEVICE_VENDOR_NAME  "Smart Home AI"' in content
    assert 'CHIP_DEVICE_CONFIG_DEVICE_PRODUCT_NAME "Dashboard Bridge"' in content
    # A #define, not a mention: the comment above those lines names both IDs to
    # explain why they are deliberately left alone.
    defines = [
        line.split()[1]
        for line in content.splitlines()
        if line.startswith("#define") and len(line.split()) > 1
    ]
    assert "CHIP_DEVICE_CONFIG_DEVICE_VENDOR_ID" not in defines
    assert "CHIP_DEVICE_CONFIG_DEVICE_PRODUCT_ID" not in defines


def test_deploy_creates_the_kvs_directory_the_bridge_needs():
    """--KVS names a file inside ~/matter-bridge-kvs. CHIP does not create the
    parent directory, so on a clean install the bridge restart-loops on a
    key-value store it cannot open."""
    unit = Path("configs/matter-bridge.service").read_text()
    deploy = Path("scripts/deploy-matter-bridge.sh").read_text()

    assert "--KVS /home/orangepi/matter-bridge-kvs/kvs" in unit
    assert "matter-bridge-kvs" in deploy, "deploy script must create the KVS dir"


def test_matter_bridge_unit_uses_the_orange_pi_interface_name():
    """Ubuntu's predictable names, not the Pi 4's wlan0. A wrong interface makes
    commissioning fail silently rather than loudly."""
    unit = Path("configs/matter-bridge.service").read_text()

    assert "--interface wlp1s0" in unit
    assert "--interface wlan0" not in unit

