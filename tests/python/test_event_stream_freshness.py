"""Live updates must end with the true state of every light, not the cached one.

Measured on 2026-09-14 with "All lights on" from the Voice Panel: Home Assistant
reported every light within 0.1-1.8 s, but the dashboard's TP-Link cards come from
its own background poll, so the refresh each report triggered read the old state.
They corrected only 3-10 s later, when the Matter bridge's copies of the same
switches changed and happened to trigger another refresh. And the stream dropped
changes inside its coalescing window, so a scene of 10 changes reached the browser
as 3 or 4.
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


def _event(entity_id: str) -> dict:
    return {"type": "event", "event": {"data": {"entity_id": entity_id}}}


class Feed:
    """A websocket stand-in: messages pushed by the test, received with a timeout."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()

    async def receive(self, timeout: float) -> dict:
        return await asyncio.wait_for(self.queue.get(), timeout=timeout)


async def _frames(gen, count: int, within: float = 3.0) -> list[str]:
    out: list[str] = []

    async def take() -> None:
        async for frame in gen:
            out.append(frame)
            if len(out) >= count:
                return

    try:
        await asyncio.wait_for(take(), within)
    except (asyncio.TimeoutError, TimeoutError):
        pass
    return out


def _changed(frames: list[str]) -> list[str]:
    return [json.loads(f.split("data: ", 1)[1])["entity_id"] for f in frames if f.startswith("event: changed")]


@pytest.fixture(autouse=True)
def fast_windows(monkeypatch):
    monkeypatch.setattr(web_app, "_EVENT_COALESCE_SECONDS", 0.1)
    monkeypatch.setattr(web_app, "_EVENT_KEEPALIVE_SECONDS", 5.0)


@pytest.mark.asyncio
async def test_the_last_change_of_a_burst_is_delivered_not_dropped() -> None:
    feed = Feed()
    for entity in ("binary_sensor.door", "binary_sensor.window", "binary_sensor.smoke"):
        feed.queue.put_nowait(_event(entity))

    frames = await _frames(web_app._coalesced_changes(feed.receive), count=2, within=1.0)

    # One at once, one when the window closes - and that one is the latest.
    assert _changed(frames) == ["binary_sensor.door", "binary_sensor.smoke"]


@pytest.mark.asyncio
async def test_a_sensor_change_does_not_wait_for_the_switches() -> None:
    feed = Feed()
    calls: list[float] = []

    async def before_notify(since: float) -> bool:
        calls.append(since)
        return True

    feed.queue.put_nowait(_event("binary_sensor.door"))
    frames = await _frames(web_app._coalesced_changes(feed.receive, before_notify), count=2, within=0.5)

    assert _changed(frames) == ["binary_sensor.door"]
    assert calls == []


@pytest.mark.asyncio
async def test_a_light_change_is_sent_at_once_and_again_after_a_fresh_poll() -> None:
    feed = Feed()
    calls: list[float] = []

    async def before_notify(since: float) -> bool:
        calls.append(since)
        await asyncio.sleep(0.05)  # the switches being read
        return True

    sent = time.monotonic()
    feed.queue.put_nowait(_event("light.kitchen_light_switch"))
    frames = await _frames(web_app._coalesced_changes(feed.receive, before_notify), count=2)

    assert _changed(frames) == ["light.kitchen_light_switch", "light.kitchen_light_switch"]
    assert len(calls) == 1 and calls[0] >= sent, "the poll must be newer than the change"


@pytest.mark.asyncio
async def test_no_second_frame_when_the_poll_did_not_finish() -> None:
    feed = Feed()

    async def before_notify(since: float) -> bool:
        return False

    feed.queue.put_nowait(_event("switch.living_room_cabinet_led"))
    frames = await _frames(web_app._coalesced_changes(feed.receive, before_notify), count=2, within=0.5)

    assert _changed(frames) == ["switch.living_room_cabinet_led"]


@pytest.mark.asyncio
async def test_a_switch_in_the_burst_is_what_the_trailing_frame_names() -> None:
    """A Matter light first, then a TP-Link switch, then a door: the held frame
    must still ask for the switch poll, which the switch change required."""
    feed = Feed()
    calls: list[float] = []

    async def before_notify(since: float) -> bool:
        calls.append(since)
        return True

    feed.queue.put_nowait(_event("binary_sensor.presence"))
    feed.queue.put_nowait(_event("light.family_room_switch"))
    feed.queue.put_nowait(_event("binary_sensor.door"))
    frames = await _frames(web_app._coalesced_changes(feed.receive, before_notify), count=3)

    assert _changed(frames) == ["binary_sensor.presence", "light.family_room_switch", "light.family_room_switch"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_an_idle_stream_still_sends_keepalives(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "_EVENT_KEEPALIVE_SECONDS", 0.05)
    feed = Feed()
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=1, within=0.5)
    assert frames == [": keepalive\n\n"]


@pytest.mark.asyncio
async def test_other_messages_are_ignored() -> None:
    feed = Feed()
    feed.queue.put_nowait({"type": "result", "success": True})
    feed.queue.put_nowait(_event("sensor.uptime"))
    feed.queue.put_nowait(_event("light.stick_s3"))
    frames = await _frames(web_app._coalesced_changes(feed.receive), count=1, within=0.5)
    assert _changed(frames) == ["light.stick_s3"]


# --- the switch poll the second frame waits for ------------------------------

def _discovery(tmp_path: Path) -> Path:
    path = tmp_path / "switches.json"
    path.write_text(json.dumps({"count": 1, "switches": [{
        "alias": "Test", "name": "Test", "host": HOST,
        "model": "HS200", "device_type": "DeviceType.WallSwitch"}]}), encoding="utf-8")
    return path


class SlowPollController:
    """Reads the switch immediately, then takes its time answering."""

    def __init__(self, poll_delay: float = 0.2) -> None:
        self.is_on = False
        self.poll_delay = poll_delay

    async def status(self, switch):
        observed = self.is_on
        await asyncio.sleep(self.poll_delay)
        return SwitchState(name=switch.name, host=switch.host, is_on=observed,
                           alias=None, model="HS200", brightness=None)


async def _primed(tmp_path: Path, controller) -> web_app.FastAPI:
    app = web_app.create_app(discovery_path=_discovery(tmp_path),
                             controller=controller, check_camera_ports=False)
    await web_app._refresh_device_cache(app)
    return app


@pytest.mark.asyncio
async def test_a_poll_already_running_when_the_switch_changed_is_not_trusted(tmp_path: Path) -> None:
    controller = SlowPollController()
    app = await _primed(tmp_path, controller)

    in_flight = asyncio.create_task(web_app._refresh_device_cache(app))
    app.state.device_cache["task"] = in_flight
    await asyncio.sleep(0.02)          # it has read the switch as off
    controller.is_on = True            # Home Assistant turns it on
    changed_at = time.monotonic()

    assert await web_app._fresh_device_cache(app, changed_at, timeout=2.0) is True
    assert app.state.device_cache["cards"][0]["is_on"] is True
    assert app.state.device_cache["started"] >= changed_at


@pytest.mark.asyncio
async def test_a_poll_that_already_saw_the_change_is_not_repeated(tmp_path: Path) -> None:
    controller = SlowPollController()
    controller.is_on = True
    changed_at = time.monotonic()
    app = await _primed(tmp_path, controller)   # this poll began after the change
    task = app.state.device_cache.get("task")

    assert await web_app._fresh_device_cache(app, changed_at, timeout=1.0) is True
    assert app.state.device_cache.get("task") is task


@pytest.mark.asyncio
async def test_giving_up_is_bounded_when_the_switches_do_not_answer(tmp_path: Path) -> None:
    controller = SlowPollController(poll_delay=0.01)
    app = await _primed(tmp_path, controller)
    controller.poll_delay = 5.0

    started = time.monotonic()
    assert await web_app._fresh_device_cache(app, time.monotonic(), timeout=0.2) is False
    assert time.monotonic() - started < 1.0
