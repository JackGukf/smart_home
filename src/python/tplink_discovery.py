"""Finding TP-Link/Kasa switches again after their IP address changes.

The dashboard addresses switches by IP, but DHCP hands out a new lease now and
then. A switch whose address moved is indistinguishable from one that died: it
just stops answering, and every poll pays a timeout for a device sitting
happily on the LAN under a different number.

Discovery is a UDP broadcast, so it finds a device wherever it landed, and the
MAC address ties it back to the switch we already know about. The broadcast
reply carries the MAC on its own, so none of this needs `update()` or cloud
credentials - which matters because KLAP devices tell us nothing else
identifying until they have authenticated.
"""

from __future__ import annotations

import os
import re
from typing import Any

MAC_KEY = "mac"


def normalize_mac(mac: Any) -> str | None:
    """Canonicalise a MAC so values from different sources compare equal.

    python-kasa reports colon-separated uppercase, config files have been seen
    with dashes or lowercase. Returns None for anything that is not 12 hex
    digits, so a malformed entry can never collide with a real device.
    """
    if not mac:
        return None
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", str(mac))
    if len(cleaned) != 12:
        return None
    return ":".join(cleaned[index : index + 2] for index in range(0, 12, 2)).upper()


async def discover_hosts_by_mac(timeout: int = 8) -> dict[str, str]:
    """Broadcast for Kasa devices, returning {normalized MAC: current host}."""
    from kasa import Discover

    kwargs: dict[str, Any] = {}
    username = os.getenv("TPLINK_USERNAME")
    password = os.getenv("TPLINK_PASSWORD")
    if username and password:
        kwargs["username"] = username
        kwargs["password"] = password

    devices = await Discover.discover(timeout=timeout, **kwargs)
    found: dict[str, str] = {}
    try:
        for host, device in devices.items():
            mac = normalize_mac(getattr(device, "mac", None))
            if mac:
                found[mac] = host
    finally:
        for device in devices.values():
            disconnect = getattr(device, "disconnect", None)
            if disconnect is None:
                continue
            try:
                await disconnect()
            except Exception:
                pass
    return found


def apply_discovered_hosts(
    switches: list[dict[str, Any]], found: dict[str, str]
) -> list[tuple[str, str, str]]:
    """Point each stored switch at the host its MAC was just found on.

    Mutates `switches` in place and returns the moves as
    (name, old host, new host). A switch with no stored MAC, or whose MAC did
    not answer the broadcast, is left alone - a device that is genuinely off
    must not be rewritten to some other device's address.
    """
    moves: list[tuple[str, str, str]] = []
    for switch in switches:
        mac = normalize_mac(switch.get(MAC_KEY))
        if not mac:
            continue
        host = found.get(mac)
        if not host or host == switch.get("host"):
            continue
        moves.append((switch.get("alias") or switch.get("name") or mac, switch.get("host"), host))
        switch["host"] = host
    return moves
