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
