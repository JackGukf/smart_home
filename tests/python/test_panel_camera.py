"""The Voice Panel's camera relay: answer at once, decode only while watched."""

from __future__ import annotations

import asyncio

import pytest

from src.python import panel_camera as relay


def _jpeg(tag: bytes) -> bytes:
    return relay.SOI + b"\x00" + tag + b"\x00" + relay.EOI


# --- parsing -----------------------------------------------------------------

def test_complete_frames_are_split_and_the_tail_is_kept() -> None:
    a, b = _jpeg(b"a"), _jpeg(b"b")
    frames, rest = relay.split_jpeg_frames(a + b + relay.SOI + b"partial")
    assert frames == [a, b]
    assert rest == relay.SOI + b"partial"


def test_bytes_before_a_frame_are_skipped() -> None:
    frames, rest = relay.split_jpeg_frames(b"junk" + _jpeg(b"a"))
    assert frames == [_jpeg(b"a")] and rest == b""


def test_a_buffer_with_no_frame_start_keeps_nothing() -> None:
    assert relay.split_jpeg_frames(b"no marker here") == ([], b"")


def test_ffmpeg_reads_go2rtc_locally_at_the_panels_exact_size() -> None:
    cmd = relay.ffmpeg_command("front_door_camera", rtsp_base="rtsp://127.0.0.1:8554/",
                               width=432, height=243, fps=4)
    assert "rtsp://127.0.0.1:8554/front_door_camera" in cmd
    assert "fps=4,scale=432:243" in cmd
    assert cmd[cmd.index("-f") + 1] == "mjpeg" and cmd[-1] == "pipe:1"
    assert not any("@" in part for part in cmd), "no camera credentials on the command line"


def test_only_named_streams_are_served() -> None:
    assert relay.settings_from_env({}).streams == {"front_door_camera"}
    settings = relay.settings_from_env({"PANEL_CAMERA_STREAMS": "front_door_camera, garage_camera,../etc,A B"})
    assert settings.streams == {"front_door_camera", "garage_camera"}


# --- the feed ----------------------------------------------------------------

class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeProcess:
    def __init__(self, chunks: list[bytes]) -> None:
        self.stdout = asyncio.StreamReader()
        for chunk in chunks:
            self.stdout.feed_data(chunk)
        self.returncode = None
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        return self.returncode


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(relay, "READ_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(relay, "RESTART_BACKOFF_SECONDS", 0.01)


def _feeds(clock, processes: list[FakeProcess]):
    spawned: list[list[str]] = []

    async def spawn(command):
        spawned.append(command)
        return processes[min(len(spawned), len(processes)) - 1]

    settings = relay.settings_from_env({})
    feed = relay.CameraFeed("front_door_camera", settings, clock=clock, spawn=spawn)
    return {"front_door_camera": feed}, feed, spawned


@pytest.mark.asyncio
async def test_an_unknown_camera_is_404_and_starts_nothing() -> None:
    feeds, _, spawned = _feeds(FakeClock(), [FakeProcess([])])
    status, _, _ = relay.frame_response(feeds, "garage_camera")
    await asyncio.sleep(0.02)
    assert status == 404 and spawned == []


@pytest.mark.asyncio
async def test_the_first_request_is_answered_at_once_and_starts_decoding() -> None:
    clock = FakeClock()
    process = FakeProcess([_jpeg(b"one") + _jpeg(b"two")])
    feeds, feed, spawned = _feeds(clock, [process])

    status, body, headers = relay.frame_response(feeds, "front_door_camera")
    assert status == 503 and headers["Retry-After"] == "1"   # never made to wait

    await asyncio.sleep(0.02)
    assert len(spawned) == 1
    status, body, headers = relay.frame_response(feeds, "front_door_camera")
    assert status == 200 and body == _jpeg(b"two") and headers["Content-Type"] == "image/jpeg"
    assert headers["Cache-Control"] == "no-store"

    clock.now += relay.IDLE_STOP_SECONDS + 1          # the panel leaves the page
    await asyncio.wait_for(feed.task, 1.0)


@pytest.mark.asyncio
async def test_an_old_frame_is_not_shown_as_current() -> None:
    clock = FakeClock()
    feeds, feed, _ = _feeds(clock, [FakeProcess([_jpeg(b"old")])])
    relay.frame_response(feeds, "front_door_camera")
    await asyncio.sleep(0.02)

    clock.now += relay.STALE_AFTER_SECONDS + 0.5       # the camera stopped sending
    status, _, _ = relay.frame_response(feeds, "front_door_camera")
    assert status == 503

    clock.now += relay.IDLE_STOP_SECONDS + 1
    await asyncio.wait_for(feed.task, 1.0)


@pytest.mark.asyncio
async def test_decoding_stops_when_nobody_is_watching() -> None:
    clock = FakeClock()
    process = FakeProcess([_jpeg(b"a")])
    feeds, feed, _ = _feeds(clock, [process])
    relay.frame_response(feeds, "front_door_camera")
    await asyncio.sleep(0.02)

    clock.now += relay.IDLE_STOP_SECONDS + 1
    await asyncio.wait_for(feed.task, 1.0)

    assert process.terminated
    assert feed.frame is None, "the next viewer must not be shown a frame from minutes ago"


@pytest.mark.asyncio
async def test_a_dead_ffmpeg_is_restarted_while_someone_is_watching() -> None:
    clock = FakeClock()
    dead = FakeProcess([])
    dead.stdout.feed_eof()
    alive = FakeProcess([_jpeg(b"back")])
    feeds, feed, spawned = _feeds(clock, [dead, alive])

    relay.frame_response(feeds, "front_door_camera")
    for _ in range(50):
        await asyncio.sleep(0.01)
        if feed.frame is not None:
            break
    assert len(spawned) >= 2
    assert relay.frame_response(feeds, "front_door_camera")[1] == _jpeg(b"back")

    clock.now += relay.IDLE_STOP_SECONDS + 1
    await asyncio.wait_for(feed.task, 1.0)
