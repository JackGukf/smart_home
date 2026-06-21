from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

import yaml


@dataclass(frozen=True)
class SwitchDefinition:
    name: str
    host: str
    model: str | None = None
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class SwitchState:
    name: str
    host: str
    is_on: bool
    alias: str | None
    model: str | None
    brightness: int | None = None


DeviceFactory = Callable[[SwitchDefinition], Awaitable[Any] | Any]


async def _default_device_factory(switch: SwitchDefinition) -> Any:
    """Connect directly to the device, auto-detecting protocol."""
    from kasa import Credentials, Device, DeviceConfig

    username = switch.username or os.getenv("TPLINK_USERNAME")
    password = switch.password or os.getenv("TPLINK_PASSWORD")
    credentials = Credentials(username=username, password=password) if username and password else None

    # Try direct TCP connect first (legacy XOR protocol, port 9999).
    # For newer KLAP devices (port 80) this will raise, so fall back to
    # discover_single which auto-detects the protocol from the UDP handshake.
    try:
        config = DeviceConfig(host=switch.host, credentials=credentials)
        return await Device.connect(config=config)
    except Exception:
        pass

    from kasa import Discover
    kwargs: dict[str, Any] = {}
    if credentials:
        kwargs["username"] = credentials.username
        kwargs["password"] = credentials.password
    device = await Discover.discover_single(switch.host, **kwargs)
    if device is None:
        raise RuntimeError(f"No TP-Link/Kasa device found at {switch.host}")
    return device


class KasaLightSwitchController:
    """Controls TP-Link/Kasa switches with a persistent per-host connection cache.

    The web app creates a single controller instance (app.state.controller) that
    lives for the lifetime of the process.  Keeping connections open avoids the
    discovery + TCP handshake overhead on every toggle request.
    """

    def __init__(self, device_factory: DeviceFactory = _default_device_factory) -> None:
        self._device_factory = device_factory
        self._cache: dict[str, Any] = {}

    async def status(self, switch: SwitchDefinition) -> SwitchState:
        device = await self._get(switch)
        await device.update()
        return _state_from_device(switch, device)

    async def turn_on(self, switch: SwitchDefinition) -> SwitchState:
        return await self._run(switch, lambda d: d.turn_on())

    async def turn_off(self, switch: SwitchDefinition) -> SwitchState:
        return await self._run(switch, lambda d: d.turn_off())

    async def set_brightness(self, switch: SwitchDefinition, level: int) -> SwitchState:
        level = max(1, min(100, level))
        return await self._run(switch, lambda d: d.set_brightness(level))

    async def toggle(self, switch: SwitchDefinition) -> SwitchState:
        async def _toggle(device: Any) -> None:
            await device.update()
            if bool(getattr(device, "is_on")):
                await device.turn_off()
            else:
                await device.turn_on()
        return await self._run(switch, _toggle)

    async def _run(self, switch: SwitchDefinition, fn: Callable[[Any], Any]) -> SwitchState:
        """Execute a command, reconnecting once if the cached connection is stale."""
        for attempt in range(2):
            device = await self._get(switch)
            try:
                await fn(device)
                await device.update()
                return _state_from_device(switch, device)
            except Exception:
                # Evict the stale connection; second attempt will reconnect.
                await self._evict(switch.host)
                if attempt == 1:
                    raise

        raise RuntimeError("unreachable")

    async def _get(self, switch: SwitchDefinition) -> Any:
        if switch.host not in self._cache:
            device = self._device_factory(switch)
            if hasattr(device, "__await__"):
                device = await device
            self._cache[switch.host] = device
        return self._cache[switch.host]

    async def _evict(self, host: str) -> None:
        device = self._cache.pop(host, None)
        if device is not None:
            try:
                disconnect = getattr(device, "disconnect", None)
                if disconnect is not None:
                    await disconnect()
            except Exception:
                pass


def load_switches_from_config(path: Path) -> list[SwitchDefinition]:
    with path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    switches = config.get("tplink", {}).get("switches", [])
    return [_switch_from_mapping(item) for item in switches]


def find_switch(switches: Iterable[SwitchDefinition], name: str) -> SwitchDefinition:
    for switch in switches:
        if switch.name == name:
            return switch
    raise ValueError(f"Switch not found in config: {name}")


async def run_command(switch: SwitchDefinition, command: str) -> SwitchState:
    controller = KasaLightSwitchController()
    if command == "status":
        return await controller.status(switch)
    if command == "on":
        return await controller.turn_on(switch)
    if command == "off":
        return await controller.turn_off(switch)
    if command == "toggle":
        return await controller.toggle(switch)
    raise ValueError(f"Unsupported command: {command}")


def _switch_from_mapping(item: dict[str, Any]) -> SwitchDefinition:
    return SwitchDefinition(
        name=str(item["name"]),
        host=str(item["host"]),
        model=item.get("model"),
        username=item.get("username"),
        password=item.get("password"),
    )


def _state_from_device(switch: SwitchDefinition, device: Any) -> SwitchState:
    return SwitchState(
        name=switch.name,
        host=switch.host,
        is_on=bool(getattr(device, "is_on")),
        alias=getattr(device, "alias", None),
        model=getattr(device, "model", switch.model),
        brightness=getattr(device, "brightness", None),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control TP-Link/Kasa light switches.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--host", help="Switch IP address or hostname.")
    target.add_argument("--name", help="Switch name from the config file.")
    parser.add_argument(
        "command",
        choices=("status", "on", "off", "toggle"),
        help="Command to run against the switch.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/devices.local.yaml"),
        help="Device config path used with --name.",
    )
    parser.add_argument("--model", help="Optional model label for --host usage.")
    parser.add_argument("--username", help="TP-Link cloud username for newer devices.")
    parser.add_argument("--password", help="TP-Link cloud password for newer devices.")
    return parser.parse_args()


def _switch_from_args(args: argparse.Namespace) -> SwitchDefinition:
    if args.host:
        return SwitchDefinition(
            name=args.host,
            host=args.host,
            model=args.model,
            username=args.username,
            password=args.password,
        )

    switches = load_switches_from_config(args.config)
    return find_switch(switches, args.name)


def main() -> None:
    args = _parse_args()
    switch = _switch_from_args(args)
    state = asyncio.run(run_command(switch, args.command))
    print(json.dumps(asdict(state), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
