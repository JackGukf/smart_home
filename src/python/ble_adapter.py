"""Bluetooth adapter selection for BLE operations.

Kept free of heavy imports so both the dashboard and the standalone discovery
scripts can use it.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

BLE_ADAPTER_SYSFS = Path("/sys/class/bluetooth")

_HCI_NAME_RE = re.compile(r"^(hci\d+):")
_HCI_ADDRESS_RE = re.compile(r"BD Address:\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")


def ble_adapter_names(sysfs: Path | None = None) -> list[str]:
    """Bluetooth adapters present on the host, lowest hciN first."""
    root = sysfs or BLE_ADAPTER_SYSFS
    try:
        entries = [p.name for p in root.glob("hci*")]
    except OSError:
        entries = []
    if not entries:
        entries = list(_hciconfig_addresses())
    return sorted(entries, key=lambda name: (len(name), name))


def _hciconfig_addresses() -> dict[str, str]:
    """Map hciN -> MAC using hciconfig.

    Not every kernel exposes /sys/class/bluetooth/hciN/address — the Orange Pi
    6 Plus does not — so fall back to parsing hciconfig, which reports the BD
    Address for each adapter.
    """
    try:
        completed = subprocess.run(
            ["hciconfig"], capture_output=True, text=True, timeout=5
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return {}

    addresses: dict[str, str] = {}
    current: str | None = None
    for line in completed.stdout.splitlines():
        name_match = _HCI_NAME_RE.match(line)
        if name_match:
            current = name_match.group(1)
            continue
        address_match = _HCI_ADDRESS_RE.search(line)
        if address_match and current:
            addresses[current] = address_match.group(1).upper()
            current = None
    return addresses


def adapter_address(name: str, sysfs: Path | None = None) -> str | None:
    """MAC address of an adapter, or None when it cannot be determined."""
    root = sysfs or BLE_ADAPTER_SYSFS
    try:
        return root.joinpath(name, "address").read_text().strip().upper()
    except OSError:
        return _hciconfig_addresses().get(name)


def resolve_ble_adapter(sysfs: Path | None = None) -> str | None:
    """Resolve the BLE adapter to an hciN name, or None when none is present.

    BLE_ADAPTER accepts either an hciN name or a MAC address. Prefer the MAC:
    hciN numbering is assigned in probe order, so it can change across reboots
    on a host with more than one adapter (this board has an onboard Intel
    controller alongside the TP-Link UB500).

    When BLE_ADAPTER is unset the first adapter is used explicitly rather than
    letting bleak choose. bleak's BlueZ backend returns no devices at all when
    no adapter is given, so passing an explicit name is what makes discovery
    work at all.
    """
    configured = (os.getenv("BLE_ADAPTER") or "").strip()
    available = ble_adapter_names(sysfs)

    if configured and ":" not in configured:
        return configured

    if configured:
        want = configured.upper()
        for name in available:
            if adapter_address(name, sysfs) == want:
                return name
        return None

    return available[0] if available else None


def ble_kwargs(sysfs: Path | None = None) -> dict[str, Any]:
    """bleak keyword arguments pinning every operation to the chosen adapter."""
    adapter = resolve_ble_adapter(sysfs)
    return {"bluez": {"adapter": adapter}} if adapter else {}
