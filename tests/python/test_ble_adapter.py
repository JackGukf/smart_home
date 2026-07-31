import subprocess
from pathlib import Path

import pytest

from src.python import ble_adapter as ble_adapter_module
from src.python.ble_adapter import (
    adapter_address,
    ble_adapter_names,
    ble_kwargs,
    resolve_ble_adapter,
)

# Real `hciconfig` output from the Orange Pi 6 Plus, trimmed.
HCICONFIG_OUTPUT = """hci1:\tType: Primary  Bus: USB
\tBD Address: 20:E1:5D:68:2B:DB  ACL MTU: 1021:6  SCO MTU: 255:12
\tUP RUNNING
\tRX bytes:1607 acl:0 sco:0 events:175 errors:0

hci0:\tType: Primary  Bus: USB
\tBD Address: E0:D5:5D:9D:38:97  ACL MTU: 1021:4  SCO MTU: 96:6
\tUP RUNNING
\tRX bytes:18454 acl:0 sco:0 events:2966 errors:0
"""


@pytest.fixture()
def sysfs_without_address(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The Orange Pi layout: hciN entries exist but expose no `address` file."""
    for name in ("hci0", "hci1"):
        (tmp_path / name).mkdir()

    def fake_run(cmd, **kwargs):
        assert cmd == ["hciconfig"]
        return subprocess.CompletedProcess(cmd, 0, stdout=HCICONFIG_OUTPUT, stderr="")

    monkeypatch.setattr(ble_adapter_module.subprocess, "run", fake_run)
    return tmp_path


@pytest.fixture()
def sysfs(tmp_path: Path) -> Path:
    """Fake /sys/class/bluetooth with two adapters, mirroring the Orange Pi."""
    for name, address in (
        ("hci0", "E0:D5:5D:9D:38:97"),  # onboard Intel AX210
        ("hci1", "20:E1:5D:68:2B:DB"),  # TP-Link UB500
    ):
        adapter = tmp_path / name
        adapter.mkdir()
        (adapter / "address").write_text(address + "\n", encoding="utf-8")
    return tmp_path


def test_lists_adapters_lowest_first(sysfs: Path) -> None:
    assert ble_adapter_names(sysfs) == ["hci0", "hci1"]


def test_lists_adapters_numerically_not_lexically(tmp_path: Path) -> None:
    for name in ("hci0", "hci2", "hci10"):
        (tmp_path / name).mkdir()
    # Lexical sorting would put hci10 before hci2.
    assert ble_adapter_names(tmp_path) == ["hci0", "hci2", "hci10"]


def test_missing_sysfs_yields_no_adapters(tmp_path: Path) -> None:
    assert ble_adapter_names(tmp_path / "absent") == []


def test_unset_selects_first_adapter(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLE_ADAPTER", raising=False)
    assert resolve_ble_adapter(sysfs) == "hci0"


def test_mac_resolves_to_interface_name(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "20:E1:5D:68:2B:DB")
    assert resolve_ble_adapter(sysfs) == "hci1"


def test_mac_match_is_case_insensitive(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "20:e1:5d:68:2b:db")
    assert resolve_ble_adapter(sysfs) == "hci1"


def test_mac_survives_renumbering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole point of configuring a MAC: hciN order can swap on reboot."""
    for name, address in (
        ("hci0", "20:E1:5D:68:2B:DB"),  # UB500 now enumerated first
        ("hci1", "E0:D5:5D:9D:38:97"),
    ):
        adapter = tmp_path / name
        adapter.mkdir()
        (adapter / "address").write_text(address + "\n", encoding="utf-8")
    monkeypatch.setenv("BLE_ADAPTER", "20:E1:5D:68:2B:DB")
    assert resolve_ble_adapter(tmp_path) == "hci0"


def test_interface_name_is_used_verbatim(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "hci1")
    assert resolve_ble_adapter(sysfs) == "hci1"


def test_unknown_mac_resolves_to_none(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "AA:BB:CC:DD:EE:FF")
    assert resolve_ble_adapter(sysfs) is None


def test_no_adapters_resolves_to_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLE_ADAPTER", raising=False)
    assert resolve_ble_adapter(tmp_path) is None


def test_blank_value_falls_back_to_first(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "   ")
    assert resolve_ble_adapter(sysfs) == "hci0"


def test_kwargs_pin_the_adapter(sysfs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "20:E1:5D:68:2B:DB")
    assert ble_kwargs(sysfs) == {"bluez": {"adapter": "hci1"}}


def test_kwargs_empty_when_no_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never pass bluez={'adapter': None} — bleak treats that as no adapter."""
    monkeypatch.delenv("BLE_ADAPTER", raising=False)
    assert ble_kwargs(tmp_path) == {}


# --- hciconfig fallback -----------------------------------------------------
# The Orange Pi 6 Plus kernel exposes /sys/class/bluetooth/hciN but no
# `address` attribute inside it, so MAC lookup must fall back to hciconfig.


def test_address_falls_back_to_hciconfig(sysfs_without_address: Path) -> None:
    assert adapter_address("hci1", sysfs_without_address) == "20:E1:5D:68:2B:DB"
    assert adapter_address("hci0", sysfs_without_address) == "E0:D5:5D:9D:38:97"


def test_mac_resolves_via_hciconfig(
    sysfs_without_address: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "20:E1:5D:68:2B:DB")
    assert resolve_ble_adapter(sysfs_without_address) == "hci1"


def test_kwargs_pin_adapter_via_hciconfig(
    sysfs_without_address: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLE_ADAPTER", "20:E1:5D:68:2B:DB")
    assert ble_kwargs(sysfs_without_address) == {"bluez": {"adapter": "hci1"}}


def test_names_recovered_from_hciconfig_when_sysfs_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=HCICONFIG_OUTPUT, stderr="")

    monkeypatch.setattr(ble_adapter_module.subprocess, "run", fake_run)
    assert ble_adapter_names(tmp_path / "absent") == ["hci0", "hci1"]


def test_missing_hciconfig_binary_is_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("hciconfig")

    monkeypatch.setattr(ble_adapter_module.subprocess, "run", fake_run)
    monkeypatch.setenv("BLE_ADAPTER", "20:E1:5D:68:2B:DB")
    assert adapter_address("hci0", tmp_path) is None
    assert resolve_ble_adapter(tmp_path) is None
