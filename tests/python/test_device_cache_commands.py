"""A background poll must not undo a command that landed while it was running.

The dashboard serves a cached device list and re-polls behind it. A refresh
replaces that list wholesale, so a command issued while one was in flight was
silently reverted when it finished: the switch turned on, the card said on, and
then flipped back to off seconds later when a poll that had read the switch
*before* the command completed.

On this board the window is seconds wide - one unplugged switch used 6.00s of a
6.31s poll while the seven live ones answered in 0.1-0.95s - so toggling at any
speed landed inside it and the state jumped around.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from src.python import web_app
from src.python.tplink_switch import SwitchState

HOST = "1.1.1.1"


def _discovery(tmp_path: Path) -> Path:
    path = tmp_path / "switches.json"
    path.write_text(json.dumps({"count": 1, "switches": [{
        "alias": "Test", "name": "Test", "host": HOST,
        "model": "HS200", "device_type": "DeviceType.WallSwitch"}]}), encoding="utf-8")
    return path


class SlowPollController:
    """Reads the switch immediately, then takes its time answering.

    That order is the whole point: a poll of eight switches sitting behind one
    dead one reports what it saw seconds before it returns.
    """

    def __init__(self, poll_delay: float = 0.25) -> None:
        self.is_on = False
        self.poll_delay = poll_delay

    def _state(self, switch, is_on: bool, brightness=None) -> SwitchState:
        return SwitchState(name=switch.name, host=switch.host, is_on=is_on,
                           alias=None, model="HS200", brightness=brightness)

    async def status(self, switch):
        observed = self.is_on
        await asyncio.sleep(self.poll_delay)
        return self._state(switch, observed)

    async def turn_on(self, switch):
        self.is_on = True
        return self._state(switch, True)


async def _app_with_primed_cache(tmp_path: Path, controller) -> web_app.FastAPI:
    app = web_app.create_app(discovery_path=_discovery(tmp_path),
                             controller=controller, check_camera_ports=False)
    app.state.device_cache["cards"] = await web_app._device_cards(app)
    app.state.device_cache["at"] = time.monotonic()
    return app


@pytest.mark.asyncio
async def test_a_poll_in_flight_does_not_revert_a_command(tmp_path: Path) -> None:
    controller = SlowPollController()
    app = await _app_with_primed_cache(tmp_path, controller)
    assert app.state.device_cache["cards"][0]["is_on"] is False

    refresh = asyncio.create_task(web_app._refresh_device_cache(app))
    await asyncio.sleep(0.05)  # let the poll read the switch as off

    state = await controller.turn_on(web_app._load_switches(app.state.discovery_path)[0].switch)
    web_app._patch_device_cache(app, HOST, state)
    assert app.state.device_cache["cards"][0]["is_on"] is True

    await refresh

    assert app.state.device_cache["cards"][0]["is_on"] is True, \
        "the stale poll reverted the command"


@pytest.mark.asyncio
async def test_a_poll_that_started_after_the_command_still_wins(tmp_path: Path) -> None:
    """The hold is not a pin. A switch someone turned off at the wall must show
    as off on the next poll that could actually have seen it."""
    controller = SlowPollController()
    app = await _app_with_primed_cache(tmp_path, controller)

    state = await controller.turn_on(web_app._load_switches(app.state.discovery_path)[0].switch)
    web_app._patch_device_cache(app, HOST, state)

    # Somebody presses the physical switch, and a fresh poll goes out after.
    controller.is_on = False
    await asyncio.sleep(0.01)
    await web_app._refresh_device_cache(app)

    assert app.state.device_cache["cards"][0]["is_on"] is False


@pytest.mark.asyncio
async def test_a_command_is_remembered_even_with_no_cache_to_patch(tmp_path: Path) -> None:
    """The first command of a cold process has no card list yet, and is exactly
    the one most likely to race the very first refresh."""
    controller = SlowPollController()
    app = web_app.create_app(discovery_path=_discovery(tmp_path),
                             controller=controller, check_camera_ports=False)
    assert app.state.device_cache["cards"] is None

    state = await controller.turn_on(web_app._load_switches(app.state.discovery_path)[0].switch)
    web_app._patch_device_cache(app, HOST, state)

    assert HOST in app.state.device_commands


@pytest.mark.asyncio
async def test_brightness_survives_the_same_race(tmp_path: Path) -> None:
    controller = SlowPollController()
    app = await _app_with_primed_cache(tmp_path, controller)

    refresh = asyncio.create_task(web_app._refresh_device_cache(app))
    await asyncio.sleep(0.05)

    switch = web_app._load_switches(app.state.discovery_path)[0].switch
    web_app._patch_device_cache(app, HOST, controller._state(switch, True, brightness=65))
    await refresh

    card = app.state.device_cache["cards"][0]
    assert card["is_on"] is True
    assert card["brightness"] == 65


@pytest.mark.asyncio
async def test_a_failing_switch_is_given_a_much_shorter_timeout(tmp_path: Path) -> None:
    """One dead switch used to add its whole 6s timeout to every refresh, and
    at concurrency 4 that set the pace for everything behind it."""
    class DeadController:
        def __init__(self) -> None:
            self.waited: list[float] = []

        async def status(self, switch):
            started = time.monotonic()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.waited.append(time.monotonic() - started)
                raise

        async def forget(self, host):
            return None

    controller = DeadController()
    app = web_app.create_app(discovery_path=_discovery(tmp_path),
                             controller=controller, check_camera_ports=False)

    # Patch the timeouts down so the test does not take seven seconds to prove
    # a point about seconds.
    web_app.SWITCH_STATUS_TIMEOUT = 0.40
    web_app.SWITCH_STATUS_TIMEOUT_FAILING = 0.05
    try:
        switch = web_app._load_switches(app.state.discovery_path)[0].switch
        limit = asyncio.Semaphore(4)

        assert await web_app._switch_status(app, switch, limit) is None
        assert await web_app._switch_status(app, switch, limit) is None
    finally:
        web_app.SWITCH_STATUS_TIMEOUT = 6.0
        web_app.SWITCH_STATUS_TIMEOUT_FAILING = 1.5

    first, second = controller.waited
    assert first >= 0.35, "the first attempt should get the full timeout"
    assert second < 0.2, "a switch already known to be down must fail fast"
