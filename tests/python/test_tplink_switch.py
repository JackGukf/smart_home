from pathlib import Path

import pytest

from src.python.tplink_switch import (
    KasaLightSwitchController,
    SwitchDefinition,
    load_switches_from_config,
)


class FakeDevice:
    def __init__(self, *, is_on: bool = False, alias: str = "Desk Switch", model: str = "HS200") -> None:
        self.is_on = is_on
        self.alias = alias
        self.model = model
        self.update_count = 0
        self.turn_on_count = 0
        self.turn_off_count = 0

    async def update(self) -> None:
        self.update_count += 1

    async def turn_on(self) -> None:
        self.turn_on_count += 1
        self.is_on = True

    async def turn_off(self) -> None:
        self.turn_off_count += 1
        self.is_on = False


@pytest.mark.asyncio
async def test_status_reads_switch_state_without_changing_power() -> None:
    device = FakeDevice(is_on=True)

    async def factory(switch: SwitchDefinition) -> FakeDevice:
        assert switch.host == "192.168.1.10"
        return device

    controller = KasaLightSwitchController(device_factory=factory)

    state = await controller.status(SwitchDefinition(name="living_room", host="192.168.1.10"))

    assert state.name == "living_room"
    assert state.host == "192.168.1.10"
    assert state.alias == "Desk Switch"
    assert state.model == "HS200"
    assert state.is_on is True
    assert device.update_count == 1
    assert device.turn_on_count == 0
    assert device.turn_off_count == 0


@pytest.mark.asyncio
async def test_turn_on_sends_command_and_refreshes_state() -> None:
    device = FakeDevice(is_on=False)
    controller = KasaLightSwitchController(device_factory=lambda switch: device)

    state = await controller.turn_on(SwitchDefinition(name="hallway", host="192.168.1.11"))

    assert state.is_on is True
    assert device.turn_on_count == 1
    assert device.update_count == 2


@pytest.mark.asyncio
async def test_toggle_turns_off_when_switch_is_on() -> None:
    device = FakeDevice(is_on=True)
    controller = KasaLightSwitchController(device_factory=lambda switch: device)

    state = await controller.toggle(SwitchDefinition(name="porch", host="192.168.1.12"))

    assert state.is_on is False
    assert device.turn_off_count == 1
    assert device.update_count == 2


def test_load_switches_from_config_reads_tplink_switches(tmp_path: Path) -> None:
    config = tmp_path / "devices.yaml"
    config.write_text(
        """
tplink:
  switches:
    - name: living_room_switch
      host: 192.168.1.10
      model: HS200
    - name: porch_switch
      host: 192.168.1.11
""",
        encoding="utf-8",
    )

    switches = load_switches_from_config(config)

    assert switches == [
        SwitchDefinition(name="living_room_switch", host="192.168.1.10", model="HS200"),
        SwitchDefinition(name="porch_switch", host="192.168.1.11", model=None),
    ]
