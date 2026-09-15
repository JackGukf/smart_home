"""Near-live camera frames for the Voice Panel.

The panel shows a camera by downloading a JPEG and decoding it itself - the ESP32-S3
cannot decode video. Asked of go2rtc directly, a snapshot took 1.2-2.2 s: go2rtc
sends nothing until the camera's next full frame arrives. And ESPHome's online_image
waits for the response headers *inside the device's main loop*, so every snapshot
froze the panel for that long. Measured 2026-09-14 with a snapshot every 2 s: voice
commands spoken on the camera page reached Home Assistant as " Turn off." and
" Turn on, turn on, turn on, switch 2.", and the screen flickered.

This relay keeps a frame ready instead. While the panel is looking, an ffmpeg
process decodes the go2rtc stream to small JPEGs (432x243, 4 per second: 0.7 s to
the first frame, ~17 KB each, 23% of one core on this board) and the latest one is
kept in memory. A request is answered at once - with that frame, or with 503 when
none is fresh yet, so the panel is never made to wait. Nobody asking for 20 s stops
ffmpeg.

It reads go2rtc's own RTSP output on 127.0.0.1, which needs no camera credentials,
and it serves only the streams it is told to (PANEL_CAMERA_STREAMS: front door and
garage by default). Like go2rtc's
own API it answers the LAN without authentication, because the panel has no way to
log in; it exposes nothing but those frames.

The last frame is kept when ffmpeg stops, and saved to disk, so a panel opening
the page can show the last view at once instead of "Loading..." for the 2-3 s
ffmpeg needs to start (a frame is ~17 KB).

    python -m src.python.panel_camera            # scripts/run-panel-camera.sh
    GET http://<board>:1985/camera/front_door_camera.jpg        a fresh frame, or 503
    GET http://<board>:1985/camera/front_door_camera/last.jpg   the last frame, any age, or 404
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

LOG = logging.getLogger("panel_camera")

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
STREAM_NAME = re.compile(r"^[a-z0-9_]{1,64}$")

DEFAULT_PORT = 1985
DEFAULT_WIDTH = 432
DEFAULT_HEIGHT = 243
DEFAULT_FPS = 4
# The Voice Panel's Cameras page. The garage camera sends a full frame only every
# 8 s, so its first live frame takes ~9 s; its saved last view covers that wait.
DEFAULT_STREAMS = "front_door_camera,garage_camera"
DEFAULT_RTSP_BASE = "rtsp://127.0.0.1:8554"
DEFAULT_SAVE_DIR = Path.home() / ".cache" / "panel-camera"

# Nobody has asked for a frame for this long: stop decoding.
IDLE_STOP_SECONDS = 20.0
# A frame older than this is not shown as current; the panel gets 503 and retries.
STALE_AFTER_SECONDS = 3.0
# ffmpeg sent nothing for this long: restart it.
READ_TIMEOUT_SECONDS = 5.0
# ...but a new ffmpeg gets longer for its first frame: it can only start at the
# camera's next keyframe, and the garage camera sends one every 8 s. With the
# 5 s limit its ffmpeg was killed just before each first frame, for ever.
STARTUP_READ_TIMEOUT_SECONDS = 15.0
RESTART_BACKOFF_SECONDS = 2.0
# A stream that never closes a frame must not grow the buffer without bound.
MAX_PARTIAL_BYTES = 2_000_000
# While watched, the last frame is also written to disk this often, so a crash or
# a reboot still leaves a recent one.
SAVE_EVERY_SECONDS = 60.0


def split_jpeg_frames(buffer: bytes) -> tuple[list[bytes], bytes]:
    """Complete JPEGs in an MJPEG byte stream, and the unfinished tail to keep.

    ffmpeg's mjpeg output is bare JPEGs back to back. A JPEG's entropy-coded data
    byte-stuffs 0xFF, so the end-of-image marker cannot appear inside a frame.
    """
    frames: list[bytes] = []
    while True:
        start = buffer.find(SOI)
        if start < 0:
            return frames, b""
        end = buffer.find(EOI, start + 2)
        if end < 0:
            return frames, buffer[start:]
        frames.append(buffer[start:end + 2])
        buffer = buffer[end + 2:]


def ffmpeg_command(stream: str, *, rtsp_base: str, width: int, height: int, fps: int) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-rtsp_transport", "tcp",
        "-i", f"{rtsp_base.rstrip('/')}/{stream}",
        "-an",
        # An exact size: the panel decodes into a fixed 432x243 image, and
        # scale=432:-2 would round 243 up to 244.
        "-vf", f"fps={fps},scale={width}:{height}",
        "-q:v", "7",
        "-f", "mjpeg", "pipe:1",
    ]


@dataclass(frozen=True)
class Settings:
    streams: frozenset[str]
    port: int = DEFAULT_PORT
    bind: str = "0.0.0.0"
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: int = DEFAULT_FPS
    rtsp_base: str = DEFAULT_RTSP_BASE
    save_dir: Path | None = field(default=None)


def settings_from_env(env: Mapping[str, str]) -> Settings:
    names = [n.strip() for n in env.get("PANEL_CAMERA_STREAMS", DEFAULT_STREAMS).split(",")]
    streams = frozenset(n for n in names if STREAM_NAME.match(n))
    for rejected in sorted({n for n in names if n and not STREAM_NAME.match(n)}):
        LOG.warning("ignoring camera stream name %r", rejected)
    return Settings(
        streams=streams,
        port=int(env.get("PANEL_CAMERA_PORT", DEFAULT_PORT)),
        bind=env.get("PANEL_CAMERA_BIND", "0.0.0.0"),
        fps=int(env.get("PANEL_CAMERA_FPS", DEFAULT_FPS)),
        rtsp_base=env.get("PANEL_CAMERA_RTSP", DEFAULT_RTSP_BASE),
        save_dir=Path(env["PANEL_CAMERA_SAVE_DIR"]) if env.get("PANEL_CAMERA_SAVE_DIR") else DEFAULT_SAVE_DIR,
    )


Spawn = Callable[[list[str]], Awaitable[Any]]


async def _spawn_ffmpeg(command: list[str]) -> Any:
    return await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)


class CameraFeed:
    """One stream: ffmpeg decoding it while someone is looking, and its latest frame."""

    def __init__(self, stream: str, settings: Settings,
                 clock: Callable[[], float] = time.monotonic,
                 spawn: Spawn = _spawn_ffmpeg) -> None:
        self.stream = stream
        self.settings = settings
        self.clock = clock
        self.spawn = spawn
        self.frame: bytes | None = None
        self.frame_at = float("-inf")
        self.last_request = float("-inf")
        self.task: asyncio.Task | None = None
        # The most recent frame of any age: kept when ffmpeg stops, and on disk.
        self.last: bytes | None = self._load_saved()
        self.saved_at = float("-inf")

    @property
    def saved_path(self) -> Path | None:
        return self.settings.save_dir / f"{self.stream}.jpg" if self.settings.save_dir else None

    def _load_saved(self) -> bytes | None:
        path = self.saved_path
        try:
            return path.read_bytes() if path is not None and path.is_file() else None
        except OSError:
            return None

    def save(self) -> None:
        """Write the last frame to disk, atomically. Failure is logged, not raised."""
        path = self.saved_path
        if path is None or self.last is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(self.last)
            os.replace(tmp, path)
            self.saved_at = self.clock()
        except OSError as exc:
            LOG.warning("%s: could not save the last frame: %s", self.stream, exc)

    def request_last(self) -> bytes | None:
        """Note that someone is looking, and return the last frame of any age."""
        self.request()
        return self.last

    def request(self) -> bytes | None:
        """Note that someone is looking, and return the latest frame if it is fresh."""
        self.last_request = self.clock()
        if self.task is None or self.task.done():
            self.task = asyncio.get_running_loop().create_task(self._run())
        if self.frame is not None and self.clock() - self.frame_at <= STALE_AFTER_SECONDS:
            return self.frame
        return None

    def watched(self) -> bool:
        return self.clock() - self.last_request < IDLE_STOP_SECONDS

    async def _run(self) -> None:
        command = ffmpeg_command(self.stream, rtsp_base=self.settings.rtsp_base,
                                 width=self.settings.width, height=self.settings.height,
                                 fps=self.settings.fps)
        while self.watched():
            LOG.info("%s: starting ffmpeg", self.stream)
            proc = await self.spawn(command)
            buffer = b""
            started = False
            try:
                while self.watched():
                    limit = READ_TIMEOUT_SECONDS if started else STARTUP_READ_TIMEOUT_SECONDS
                    try:
                        chunk = await asyncio.wait_for(proc.stdout.read(65536), limit)
                    except (asyncio.TimeoutError, TimeoutError):
                        LOG.warning("%s: no data from ffmpeg for %.0f s", self.stream, limit)
                        break
                    if not chunk:
                        LOG.warning("%s: ffmpeg exited", self.stream)
                        break
                    frames, buffer = split_jpeg_frames(buffer + chunk)
                    if len(buffer) > MAX_PARTIAL_BYTES:
                        buffer = b""
                    if frames:
                        started = True
                        self.frame = self.last = frames[-1]
                        self.frame_at = self.clock()
                        if self.clock() - self.saved_at >= SAVE_EVERY_SECONDS:
                            self.save()
            finally:
                await _stop(proc)
            if self.watched():
                await asyncio.sleep(RESTART_BACKOFF_SECONDS)
        LOG.info("%s: nobody watching, ffmpeg stopped", self.stream)
        self.save()
        self.frame = None


async def _stop(proc: Any) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), 3)
    except (asyncio.TimeoutError, TimeoutError):
        proc.kill()
        await proc.wait()


def frame_response(feeds: Mapping[str, CameraFeed], stream: str) -> tuple[int, bytes, dict[str, str]]:
    """Status, body and headers for GET /camera/<stream>.jpg. Never waits."""
    feed = feeds.get(stream)
    if feed is None:
        return 404, b"unknown camera\n", {"Content-Type": "text/plain"}
    frame = feed.request()
    if frame is None:
        return 503, b"starting\n", {"Content-Type": "text/plain", "Retry-After": "1",
                                    "Cache-Control": "no-store"}
    return 200, frame, {"Content-Type": "image/jpeg", "Cache-Control": "no-store"}


def last_response(feeds: Mapping[str, CameraFeed], stream: str) -> tuple[int, bytes, dict[str, str]]:
    """Status, body and headers for GET /camera/<stream>/last.jpg. Never waits.

    Also starts decoding, so the panel's first request on opening the page both
    gets something to show and has the fresh frames on their way.
    """
    feed = feeds.get(stream)
    if feed is None:
        return 404, b"unknown camera\n", {"Content-Type": "text/plain"}
    frame = feed.request_last()
    if frame is None:
        return 404, b"no frame yet\n", {"Content-Type": "text/plain", "Cache-Control": "no-store"}
    return 200, frame, {"Content-Type": "image/jpeg", "Cache-Control": "no-store"}


def main() -> None:
    from aiohttp import web

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = settings_from_env(os.environ)
    feeds = {name: CameraFeed(name, settings) for name in sorted(settings.streams)}

    async def camera(request: web.Request) -> web.Response:
        status, body, headers = frame_response(feeds, request.match_info["name"])
        return web.Response(status=status, body=body, headers=headers)

    async def last(request: web.Request) -> web.Response:
        status, body, headers = last_response(feeds, request.match_info["name"])
        return web.Response(status=status, body=body, headers=headers)

    app = web.Application()
    app.router.add_get("/camera/{name}.jpg", camera)
    app.router.add_get("/camera/{name}/last.jpg", last)
    LOG.info("serving %s on %s:%d", ", ".join(sorted(feeds)) or "no cameras", settings.bind, settings.port)
    web.run_app(app, host=settings.bind, port=settings.port, print=None)


if __name__ == "__main__":
    main()
