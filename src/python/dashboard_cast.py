"""Cast the dashboard to a TV through a DLNA renderer (the LLANO-S450 EZCast dongle).

The dongle cannot show a web page: it refuses every Google Cast receiver that
would (DashCast, Home Assistant's, even YouTube), and its Cast media receiver
accepts an image and never fetches it. What it does play is video over DLNA. So
the board renders the dashboard itself and sends it as a live stream:

    headless Chromium --(screenshots, FPS a second)--> ffmpeg libx264 --> MPEG-TS
        --> http://<board>:PORT/<token>.ts --> DLNA SetAVTransportURI + Play

It is a picture of the dashboard, not the dashboard: nothing on it can be
touched, and it runs a few seconds behind.

The unit is off unless someone turns it on in Settings, and when it is off
nothing runs at all. When it is on it idles as this one process, looking for the
renderer every WAIT_S seconds; Chromium and ffmpeg (about 1.5 cores at 4 fps,
measured 2026-09-18) start only while the renderer is reachable, idle, and
pulling the stream, and stop when it is not.

The switch is the systemd unit itself - `enable --now` / `disable --now` - so
the choice survives a reboot and there is no second source of truth. The
dashboard's side of that is `unit_state` / `set_enabled` / `read_status` below;
they are standard library only, so importing this module costs web_app nothing.
"""
from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

LOG = logging.getLogger("dashboard_cast")

UNIT = "dashboard-cast.service"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "devices.local.yaml"

WAIT_S = 30  # between searches while the renderer is off or busy
RETRY_S = 10  # before casting again after the renderer let go
CHECK_S = 5  # between checks while casting
START_GRACE_S = 25  # a renderer takes this long to open the stream and start playing
NO_CLIENT_S = 30  # the renderer has let go when nothing has pulled the stream this long
FIRST_FRAME_S = 30  # Chromium's first picture, or the session is abandoned
STALL_S = 20  # no new picture this long: restart Chromium, the stream carries on
MAX_CHROME_RESTARTS = 5  # stalls in one session, before giving it up
CHROME_REFRESH_S = 3600  # a fresh Chromium every hour; the stream carries on
# Chromium's renderer keeps decoded camera video in shared memory - 430 MiB and
# climbing after five minutes of the front door camera (2026-09-18). Shared
# memory is not reclaimable on a swapless board, so past this Chromium is
# replaced, mid-stream. Heap plus shared memory of this unit, in MiB.
MEMORY_REFRESH_MB = int(os.environ.get("DASHBOARD_CAST_MEMORY_MB", "900"))
RESTART_AFTER_S = 12 * 3600  # a fresh Chromium and session twice a day

AVTRANSPORT = "urn:schemas-upnp-org:service:AVTransport:1"
MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
IDLE_STATES = frozenset({"STOPPED", "NO_MEDIA_PRESENT"})


def status_path() -> Path:
    """Where the service reports what it is doing; tmpfs, so a reboot clears it."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "dashboard-cast.json"


# ── The switch, as the dashboard sees it ────────────────────────────────────

Runner = Callable[..., subprocess.CompletedProcess]


def _systemctl(args: list[str], run: Runner) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=20, env=env, check=False)


def unit_state(run: Runner = subprocess.run) -> dict[str, Any]:
    """Whether the unit is installed, switched on, and running."""
    enabled = _systemctl(["is-enabled", UNIT], run).stdout.strip()
    active = _systemctl(["is-active", UNIT], run).stdout.strip()
    return {
        # is-enabled prints nothing and fails when there is no such unit.
        "installed": enabled not in ("", "not-found"),
        "enabled": enabled == "enabled",
        "running": active in ("active", "activating", "reloading"),
    }


def set_enabled(enabled: bool, run: Runner = subprocess.run) -> dict[str, Any]:
    """Switch casting on or off, now and across reboots."""
    result = _systemctl(["enable" if enabled else "disable", "--now", UNIT], run)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "systemctl failed").strip().splitlines()[-1])
    return unit_state(run)


def read_status(path: Path | None = None) -> dict[str, Any] | None:
    try:
        return json.loads((path or status_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


STATE_WORDS = {
    "waiting": "Looking for the TV",
    "busy": "TV busy with something else",
    "casting": "Casting",
    "paused": "Stopped for now",
}


def status_text(doc: dict[str, Any]) -> str:
    """One line for a person: what casting is doing. The dashboard's Settings
    page words it the same way (app.js, renderCast)."""
    if not doc.get("installed", True):
        return "Not installed on the board"
    if not doc.get("enabled"):
        return "Off"
    if not doc.get("running"):
        return "Switched on, but not running"
    status = doc.get("status")
    if not status:
        return "Starting"
    text = STATE_WORDS.get(status.get("state"), status.get("state", ""))
    if status.get("state") == "casting":
        text += f" to {status.get('renderer')}"
    if status.get("detail") and status.get("state") != "casting":
        text += f": {status['detail']}"
    return text


# ── Home Assistant: switch.tv_cast, through MQTT discovery ──────────────────
# So anything that talks to Home Assistant - the Voice Panel, a script, a voice
# command - flips the same switch as Settings -> Cast to TV. The dashboard runs
# this, not the cast service: the service is not running while casting is off,
# which is exactly when somebody wants to switch it on.

MQTT_ROOT = "smart_home_ai/cast"
DISCOVERY_TOPIC = "homeassistant/switch/smart_home_ai/tv_cast/config"
MQTT_POLL_S = 10


def discovery_payload() -> dict[str, Any]:
    """`switch.tv_cast`, named "TV cast" - the device's name, as a one-entity device."""
    return {
        "name": None,
        "unique_id": "smart_home_ai_tv_cast",
        "default_entity_id": "switch.tv_cast",
        "command_topic": f"{MQTT_ROOT}/set",
        "state_topic": f"{MQTT_ROOT}/state",
        "json_attributes_topic": f"{MQTT_ROOT}/attributes",
        "availability_topic": f"{MQTT_ROOT}/availability",
        "payload_on": "ON",
        "payload_off": "OFF",
        "icon": "mdi:cast",
        "device": {
            "identifiers": ["smart_home_ai_tv_cast"],
            "name": "TV cast",
            "manufacturer": "smart_home_AI",
            "model": "Dashboard cast to the LLANO-S450 (dashboard-cast.service)",
        },
    }


class MQTTSwitch:
    """Publishes casting's state to Home Assistant and switches it on command.

    Discovery and state are retained, so Home Assistant has them after its own
    restart. The state is re-read every MQTT_POLL_S: the service changes what it
    is doing by itself (the TV goes off), and the switch can be flipped from the
    dashboard too.
    """

    def __init__(self, host: str, port: int, username: str | None, password: str | None,
                 run: Runner = subprocess.run, status_file: Path | None = None,
                 client_factory: Callable[[], Any] | None = None):
        self._run = run
        self._status_file = status_file
        self._last: tuple[str, str] | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._client = (client_factory or self._paho)()
        if username:
            self._client.username_pw_set(username, password)
        self._client.will_set(f"{MQTT_ROOT}/availability", "offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._host, self._port = host, port

    @staticmethod
    def _paho():
        import paho.mqtt.client as mqtt
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smart-home-ai-cast")

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()
        threading.Thread(target=self._poll, name="tv-cast-mqtt", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._client.publish(f"{MQTT_ROOT}/availability", "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def refresh(self, force: bool = False) -> None:
        """Publish the state now, if it changed (or always, when forced)."""
        state = unit_state(self._run)
        doc = {**state, "status": read_status(self._status_file) if state["running"] else None}
        payload = "ON" if doc["enabled"] else "OFF"
        attributes = json.dumps({"status": (doc["status"] or {}).get("state", "off" if payload == "OFF" else "starting"),
                                 "text": status_text(doc)})
        with self._lock:
            if not force and self._last == (payload, attributes):
                return
            self._last = (payload, attributes)
        self._client.publish(f"{MQTT_ROOT}/attributes", attributes, retain=True)
        self._client.publish(f"{MQTT_ROOT}/state", payload, retain=True)

    def _poll(self) -> None:
        while not self._stop.wait(MQTT_POLL_S):
            try:
                self.refresh()
            except Exception as error:  # noqa: BLE001 - a bad poll must not end the thread
                LOG.info("TV cast state not published: %s", error)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        client.subscribe(f"{MQTT_ROOT}/set")
        client.subscribe("homeassistant/status")
        client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload()), retain=True)
        client.publish(f"{MQTT_ROOT}/availability", "online", retain=True)
        self._refresh_later(force=True)

    def _on_message(self, client, userdata, message) -> None:
        if message.topic == "homeassistant/status":
            if message.payload == b"online":
                client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload()), retain=True)
                self._refresh_later(force=True)
            return
        if message.topic != f"{MQTT_ROOT}/set" or message.payload not in (b"ON", b"OFF"):
            return
        self._refresh_later(switch_to=message.payload == b"ON")

    def _refresh_later(self, force: bool = False, switch_to: bool | None = None) -> None:
        """Off paho's network thread: systemctl takes a second or two."""
        def work() -> None:
            try:
                if switch_to is not None:
                    set_enabled(switch_to, self._run)
                    LOG.info("TV cast switched %s from Home Assistant", "on" if switch_to else "off")
                self.refresh(force=True if switch_to is not None else force)
            except Exception as error:  # noqa: BLE001
                LOG.warning("TV cast switch failed: %s", error)
                self.refresh(force=True)  # put Home Assistant's switch back to the truth

        threading.Thread(target=work, daemon=True).start()


# ── DLNA: finding the renderer and talking to it ────────────────────────────

@dataclass(frozen=True)
class Renderer:
    name: str
    host: str
    control_url: str  # AVTransport control endpoint
    location: str = ""  # its device description, to find it again without SSDP


def parse_ssdp_response(data: bytes) -> dict[str, str]:
    """Headers of one SSDP reply, lower-cased; empty when it is not one."""
    lines = data.decode("utf-8", "replace").split("\r\n")
    if not lines or not lines[0].upper().startswith("HTTP/1.1 200"):
        return {}
    headers = {}
    for line in lines[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers[key.strip().lower()] = value.strip()
    return headers


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_description(xml_text: str, location: str) -> Renderer | None:
    """The renderer behind a device description, or None when it has no AVTransport."""
    root = ET.fromstring(xml_text)
    base = next((el.text for el in root.iter() if _local(el.tag) == "URLBase" and el.text), location)
    for device in (el for el in root.iter() if _local(el.tag) == "device"):
        fields = {_local(child.tag): (child.text or "").strip() for child in device}
        for service in (el for el in device.iter() if _local(el.tag) == "service"):
            info = {_local(child.tag): (child.text or "").strip() for child in service}
            if info.get("serviceType", "").startswith("urn:schemas-upnp-org:service:AVTransport:"):
                control = urllib.parse.urljoin(base, info.get("controlURL", ""))
                return Renderer(fields.get("friendlyName", ""), urllib.parse.urlparse(control).hostname or "",
                                control, location)
    return None


def describe(location: str) -> Renderer | None:
    """The renderer at a known description URL, or None when it does not answer."""
    try:
        with urllib.request.urlopen(location, timeout=4) as response:
            return parse_description(response.read().decode("utf-8", "replace"), location)
    except (OSError, ET.ParseError):
        return None


def discover(name: str, timeout: float = 3.0) -> Renderer | None:
    """The first DLNA renderer whose friendly name contains `name`.

    The EZCast often leaves an SSDP search unanswered while it is busy, so a
    caller that knows where it was should try `describe` first.
    """
    query = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\n"
             f"MX: 2\r\nST: {MEDIA_RENDERER}\r\n\r\n").encode()
    locations: list[str] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.5)
        sock.sendto(query, ("239.255.255.250", 1900))
        sock.sendto(query, ("239.255.255.250", 1900))  # UDP: one retry is cheap
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            location = parse_ssdp_response(data).get("location")
            if location and location not in locations:
                locations.append(location)
    for location in locations:
        renderer = describe(location)
        if renderer and name.lower() in renderer.name.lower():
            return renderer
    return None


def soap_envelope(action: str, args: dict[str, Any]) -> str:
    body = "".join(f"<{key}>{html.escape(str(value), quote=False)}</{key}>" for key, value in args.items())
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{action} xmlns:u="{AVTRANSPORT}">{body}</u:{action}></s:Body></s:Envelope>')


def didl_for(url: str) -> str:
    """Metadata for a live MPEG-TS stream. The EZCast plays without it, but DLNA says send it."""
    return ('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
            '<item id="dashboard" parentID="0" restricted="1"><dc:title>Dashboard</dc:title>'
            '<upnp:class>object.item.videoItem</upnp:class>'
            f'<res protocolInfo="http-get:*:video/mp2t:*">{html.escape(url)}</res></item></DIDL-Lite>')


def _soap(renderer: Renderer, action: str, args: dict[str, Any]) -> str:
    request = urllib.request.Request(
        renderer.control_url, soap_envelope(action, args).encode(),
        {"Content-Type": 'text/xml; charset="utf-8"', "SOAPACTION": f'"{AVTRANSPORT}#{action}"'})
    with urllib.request.urlopen(request, timeout=6) as response:
        return response.read().decode("utf-8", "replace")


def _field(xml_text: str, name: str) -> str:
    match = re.search(rf"<{name}>(.*?)</{name}>", xml_text, re.S)
    return html.unescape(match.group(1)) if match else ""


def renderer_now(renderer: Renderer) -> tuple[str, str]:
    """(transport state, current URI). Raises OSError when the renderer is gone."""
    state = _field(_soap(renderer, "GetTransportInfo", {"InstanceID": 0}), "CurrentTransportState")
    uri = _field(_soap(renderer, "GetMediaInfo", {"InstanceID": 0}), "CurrentURI")
    return state, uri


def play(renderer: Renderer, url: str) -> None:
    _soap(renderer, "SetAVTransportURI", {"InstanceID": 0, "CurrentURI": url, "CurrentURIMetaData": didl_for(url)})
    _soap(renderer, "Play", {"InstanceID": 0, "Speed": 1})


def stop(renderer: Renderer) -> None:
    _soap(renderer, "Stop", {"InstanceID": 0})


def may_cast(state: str, uri: str, own_prefix: str) -> bool:
    """Only an idle renderer is ours to take. Someone casting from a phone is left alone.

    A renderer still holding one of our own earlier streams - the session ended,
    or the service restarted - is ours to replace, whatever state it reports.
    """
    return state in IDLE_STATES or not uri or uri.startswith(own_prefix)


def taken_over(uri: str, token: str) -> bool:
    """Somebody cast something else over this stream.

    The only renderer answer trusted to end a session. Its transport state is
    not: the EZCast reports STOPPED while it opens a stream, and times out on
    requests while it decodes one, so whether it still pulls the stream is what
    says it is still playing.
    """
    return bool(uri) and token not in uri


# ── The picture: Chromium, ffmpeg and a small HTTP server ───────────────────

def session_cookie(config_path: Path) -> str:
    """A dashboard session, signed by the signer web_app.create_app uses
    (dashboard_session). tests/python/test_dashboard_cast.py checks this cookie
    against the real middleware.
    """
    import yaml

    from src.python.dashboard_session import session_signer

    auth = (yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}).get("dashboard_auth")
    if not auth:
        return ""  # no login configured: the dashboard lets everyone in
    username = str(auth["username"])
    return session_signer(config_path, username, str(auth["password"])).dumps({"u": username})


def unit_memory_mb() -> int | None:
    """Heap plus shared memory of this service's cgroup - the part that cannot
    be reclaimed. Page cache is left out: the kernel takes that back itself."""
    try:
        line = Path("/proc/self/cgroup").read_text(encoding="utf-8").strip().splitlines()[-1]
        stat = (Path("/sys/fs/cgroup") / line.split("::", 1)[1].lstrip("/") / "memory.stat").read_text(encoding="utf-8")
    except (OSError, IndexError):
        return None
    fields = dict(line.split() for line in stat.splitlines() if line.count(" ") == 1)
    return (int(fields.get("anon", 0)) + int(fields.get("shmem", 0))) // (1 << 20)


def board_address(peer: str) -> str:
    """Our address on the route to the renderer - what it has to fetch the stream from."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((peer, 9))
        return sock.getsockname()[0]


@dataclass
class Settings:
    renderer: str = "LLANO-S450"
    fps: int = 4
    port: int = 8765
    # ?screen=tv: the page asks for the TV remote's events (Voice Panel, TV cast).
    url: str = "http://127.0.0.1:8000/?screen=tv"
    devtools_port: int = 9333
    config_path: Path = DEFAULT_CONFIG_PATH
    # The page's clock and "3 min ago" follow the browser's zone. The board runs
    # on UTC, so without this the TV showed the time seven hours ahead.
    timezone: str = "America/Vancouver"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            renderer=env.get("DASHBOARD_CAST_RENDERER", cls.renderer),
            fps=max(1, min(10, int(env.get("DASHBOARD_CAST_FPS", cls.fps)))),
            port=int(env.get("DASHBOARD_CAST_PORT", cls.port)),
            url=env.get("DASHBOARD_CAST_URL", cls.url),
            devtools_port=int(env.get("DASHBOARD_CAST_DEVTOOLS_PORT", cls.devtools_port)),
            config_path=Path(env.get("DASHBOARD_CAST_CONFIG", str(DEFAULT_CONFIG_PATH))),
            timezone=env.get("DASHBOARD_CAST_TZ", cls.timezone),
        )


class Stream:
    """Chromium and ffmpeg, alive only while a renderer is being fed.

    Capturing and encoding are decoupled. Chromium's screenshots update
    `latest`; a feeder hands ffmpeg that frame at a steady `fps` whatever
    Chromium is doing. A slow or stuck Chromium then freezes the picture for a
    moment instead of starving the stream - and a starved stream is what the
    renderer drops, ending the cast. Chromium itself can be replaced mid-stream.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.token = secrets.token_urlsafe(12)
        self.clients: set[asyncio.Queue] = set()
        self.last_client = time.monotonic()
        self.latest: bytes | None = None
        self.last_frame_at = time.monotonic()
        self.frames = 0
        self.chrome_restarts = 0  # stalls only; routine refreshes are not failures
        self.chrome_started = time.monotonic()
        self._ffmpeg: subprocess.Popen | None = None
        self._chrome: subprocess.Popen | None = None
        self._capture_task: asyncio.Task | None = None
        self._tasks: list[asyncio.Task] = []
        self._profile = ""

    async def start(self) -> None:
        s = self.settings
        # The feeder sets the pace, so timestamps come from the frame count.
        # repeat-headers: the renderer joins mid-stream, and without SPS/PPS on
        # every keyframe it can decode nothing it did not see from the start.
        self._ffmpeg = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "image2pipe", "-framerate", str(s.fps), "-c:v", "mjpeg", "-i", "-",
             "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
             "-g", str(s.fps * 2), "-x264-params", "repeat-headers=1",
             "-pix_fmt", "yuv420p", "-b:v", "3M", "-maxrate", "4M", "-bufsize", "4M", "-f", "mpegts", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True)
        self._tasks = [asyncio.create_task(self._pump()), asyncio.create_task(self._feed())]
        await self._start_chrome()

    async def stop(self) -> None:
        await self._stop_chrome()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        if self._ffmpeg:
            _kill_group(self._ffmpeg)
        for queue in list(self.clients):
            queue.put_nowait(b"")  # ends that client's response

    async def restart_chrome(self, stalled: bool = True) -> None:
        if stalled:
            self.chrome_restarts += 1
        await self._stop_chrome()
        await self._start_chrome()

    def failed(self) -> str | None:
        """Why the stream itself died, if it did. Chromium is not the stream."""
        if self._ffmpeg and self._ffmpeg.poll() is not None:
            return f"ffmpeg exited ({self._ffmpeg.returncode})"
        for task in self._tasks:
            if task.done() and not task.cancelled():
                return f"stream stopped: {task.exception()!r}"
        return None

    def capture_stalled(self) -> str | None:
        """Why Chromium needs replacing, if it does."""
        if self._chrome and self._chrome.poll() is not None:
            return f"Chromium exited ({self._chrome.returncode})"
        task = self._capture_task
        if task and task.done() and not task.cancelled():
            return f"capture failed: {task.exception()!r}"
        if time.monotonic() - self.last_frame_at > STALL_S:
            return f"no new picture for {STALL_S} s"
        return None

    async def _start_chrome(self) -> None:
        s = self.settings
        self._profile = tempfile.mkdtemp(prefix="dashboard-cast-")
        # The systemd user manager on this board carries the desktop's session
        # (DISPLAY, WAYLAND_DISPLAY, the session bus). Given those, Chromium asks
        # the GNOME keyring for a password store and hangs there, silently, before
        # it opens DevTools - it worked from ssh and never from the unit
        # (2026-09-18). So: no desktop, and no keyring.
        env = {k: v for k, v in os.environ.items()
               if k not in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XAUTHORITY")}
        env["TZ"] = s.timezone
        # A new session, so one signal takes down every Chromium helper.
        self._chrome = subprocess.Popen(
            ["chromium", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--mute-audio",
             "--no-first-run", "--disable-background-networking", "--password-store=basic",
             f"--remote-debugging-port={s.devtools_port}", "--remote-debugging-address=127.0.0.1",
             "--window-size=1920,1080", f"--user-data-dir={self._profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, start_new_session=True)
        self.last_frame_at = self.chrome_started = time.monotonic()  # the stall clock starts now
        self._capture_task = asyncio.create_task(self._capture())

    async def _stop_chrome(self) -> None:
        if self._capture_task:
            self._capture_task.cancel()
            await asyncio.gather(self._capture_task, return_exceptions=True)
            self._capture_task = None
        if self._chrome:
            await asyncio.to_thread(_kill_group, self._chrome)
            self._chrome = None
        if self._profile:
            shutil.rmtree(self._profile, ignore_errors=True)
            self._profile = ""

    async def _pump(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            chunk = await loop.run_in_executor(None, self._ffmpeg.stdout.read1, 65536)
            if not chunk:
                raise ConnectionError("ffmpeg closed its output")
            for queue in list(self.clients):
                if queue.qsize() < 256:  # a stalled client drops data, it does not grow memory
                    queue.put_nowait(chunk)

    async def _feed(self) -> None:
        loop = asyncio.get_running_loop()
        period, due = 1 / self.settings.fps, time.monotonic()
        while True:
            if self.latest is not None:
                # Off the event loop: a blocking write here stalls the loop that
                # drains ffmpeg's output, and the two deadlock.
                await loop.run_in_executor(None, _write, self._ffmpeg, self.latest)
            due += period
            now = time.monotonic()
            if due < now - 1:
                due = now  # fell behind (a slow write); do not burst to catch up
            await asyncio.sleep(max(0.0, due - now))

    async def _capture(self) -> None:
        import aiohttp

        s = self.settings
        devtools = f"http://127.0.0.1:{s.devtools_port}"
        cookie = session_cookie(s.config_path)
        async with aiohttp.ClientSession() as http:
            for _ in range(100):
                try:
                    await (await http.get(f"{devtools}/json/version")).json()
                    break
                except (aiohttp.ClientError, ValueError):
                    await asyncio.sleep(0.2)
            else:
                raise RuntimeError("Chromium started but never opened DevTools")
            # A fresh tab: on this board the initial about:blank tab's renderer
            # can spin and never answer DevTools (seen 2026-09-18).
            tab = await (await http.put(f"{devtools}/json/new?about:blank")).json()
            async with http.ws_connect(tab["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                ids = iter(range(1, 1 << 62))

                async def cmd(method: str, **params: Any) -> dict:
                    msg_id = next(ids)
                    await ws.send_json({"id": msg_id, "method": method, "params": params})
                    async for message in ws:
                        data = json.loads(message.data)
                        if data.get("id") == msg_id:
                            if "error" in data:
                                raise RuntimeError(f"{method}: {data['error']}")
                            return data.get("result", {})
                    raise ConnectionError("DevTools closed")

                await cmd("Emulation.setDeviceMetricsOverride", width=1920, height=1080,
                          deviceScaleFactor=1, mobile=False)
                if cookie:
                    await cmd("Network.setCookie", name="session", value=cookie, url=s.url)
                await cmd("Page.navigate", url=s.url)
                await asyncio.sleep(4)  # the dashboard's first data
                period, due = 1 / s.fps, time.monotonic()
                while True:
                    shot = await asyncio.wait_for(cmd("Page.captureScreenshot", format="jpeg", quality=80), 15)
                    self.latest = base64.b64decode(shot["data"])
                    self.last_frame_at = time.monotonic()
                    self.frames += 1
                    due += period
                    now = time.monotonic()
                    if due < now - 1:
                        due = now
                    await asyncio.sleep(max(0.0, due - now))


def _write(proc: subprocess.Popen, data: bytes) -> None:
    proc.stdin.write(data)
    proc.stdin.flush()


def _kill_group(proc: subprocess.Popen) -> None:
    for sig, wait in ((signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(wait)
        except subprocess.TimeoutExpired:
            pass


# ── The service ─────────────────────────────────────────────────────────────

class Caster:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.stream: Stream | None = None
        self.allowed_peer = ""
        self.casting_to: Renderer | None = None
        self.known: Renderer | None = None

    def report(self, state: str, detail: str = "", renderer: Renderer | None = None) -> None:
        doc = {"state": state, "detail": detail, "since": int(time.time()),
               "renderer": renderer.name if renderer else self.settings.renderer,
               "host": renderer.host if renderer else None, "fps": self.settings.fps}
        path = status_path()
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass
        LOG.info("%s%s", state, f" - {detail}" if detail else "")

    async def serve(self, request):
        from aiohttp import web

        stream = self.stream
        # Only the renderer being fed may pull the stream, and only by this
        # session's token: it is a live picture of the house.
        if (stream is None or request.match_info["token"] != stream.token
                or request.remote not in (self.allowed_peer, "127.0.0.1")):
            raise web.HTTPNotFound()
        response = web.StreamResponse(headers={
            "Content-Type": "video/mp2t", "Cache-Control": "no-cache",
            "transferMode.dlna.org": "Streaming",
            "contentFeatures.dlna.org": "DLNA.ORG_OP=00;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000"})
        await response.prepare(request)
        queue: asyncio.Queue = asyncio.Queue()
        stream.clients.add(queue)
        try:
            while chunk := await queue.get():
                await response.write(chunk)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            stream.clients.discard(queue)
            stream.last_client = time.monotonic()
        return response

    async def run(self) -> None:
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/{token}.ts", self.serve)
        runner = web.AppRunner(app, shutdown_timeout=2)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", self.settings.port).start()
        # Switching off is a SIGTERM from systemd: finish cleanly, so the TV is
        # told to stop instead of being left on the last frame.
        main = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, main.cancel)
        try:
            while True:
                try:
                    await self._one_session()
                except (OSError, RuntimeError, ValueError) as error:
                    # One bad session - a renderer that vanished mid-request, a
                    # description that did not parse - is not a reason to die.
                    LOG.warning("session failed: %r", error)
                    await asyncio.sleep(RETRY_S)
        except asyncio.CancelledError:
            pass
        finally:
            if self.stream:
                await self.stream.stop()
            if self.casting_to:
                try:
                    await asyncio.to_thread(stop, self.casting_to)
                except OSError:
                    pass
            await runner.cleanup()

    async def _find(self) -> Renderer | None:
        """Where it was last, then a network search. The EZCast often leaves SSDP
        unanswered while busy, which read as "not on the network" for a minute."""
        if self.known:
            found = await asyncio.to_thread(describe, self.known.location)
            if found:
                return found
        found = await asyncio.to_thread(discover, self.settings.renderer)
        if found:
            self.known = found
        return found

    async def _one_session(self) -> None:
        s = self.settings
        renderer = await self._find()
        if renderer is None:
            self.report("waiting", f"{s.renderer} is not on the network - is the TV on?")
            await asyncio.sleep(WAIT_S)
            return
        own_prefix = f"http://{board_address(renderer.host)}:{s.port}/"
        try:
            state, uri = await asyncio.to_thread(renderer_now, renderer)
        except OSError:
            self.report("waiting", f"{renderer.name} is not answering", renderer)
            await asyncio.sleep(RETRY_S)
            return
        if not may_cast(state, uri, own_prefix):
            self.report("busy", "Something else is playing on it", renderer)
            await asyncio.sleep(WAIT_S)
            return

        self.allowed_peer = renderer.host
        self.stream = stream = Stream(s)
        url = f"{own_prefix}{stream.token}.ts"
        why = ""
        try:
            await stream.start()
            deadline = time.monotonic() + FIRST_FRAME_S
            # Only a real failure ends this wait early; "no new picture" is the
            # stall rule, and a Chromium loading a dashboard that is itself
            # restarting (a deploy) needs longer than a stall is allowed.
            while (stream.latest is None and time.monotonic() < deadline
                   and not (stream.capture_stalled() or "").startswith(("Chromium exited", "capture failed"))):
                await asyncio.sleep(0.5)
            if stream.latest is None:
                why = f"no first picture ({stream.capture_stalled() or 'timed out'})"
            else:
                why = await self._cast(stream, renderer, url)
        finally:
            await stream.stop()
            self.stream = None
            self.casting_to = None
            self.report("paused", why, renderer)
        await asyncio.sleep(WAIT_S if why == "the TV is showing something else" else RETRY_S)

    async def _cast(self, stream: Stream, renderer: Renderer, url: str) -> str:
        """Play the stream on the renderer and keep it fed; returns why it ended."""
        await asyncio.sleep(2)  # a keyframe or two in the pipe before the renderer asks
        for attempt in (1, 2, 3):
            try:
                await asyncio.to_thread(play, renderer, url)
                break
            except OSError as error:  # slow to answer, or refused
                if attempt == 3:
                    return f"the TV did not take the stream ({error})"
                await asyncio.sleep(3)
        started = stream.last_client = time.monotonic()
        self.casting_to = renderer
        self.report("casting", "", renderer)
        while True:
            await asyncio.sleep(CHECK_S)
            since = time.monotonic() - started
            if failure := stream.failed():
                return failure
            if stall := stream.capture_stalled():
                if stream.chrome_restarts >= MAX_CHROME_RESTARTS:
                    return f"Chromium keeps failing ({stall})"
                LOG.warning("restarting Chromium: %s", stall)
                await stream.restart_chrome()
                self.report("casting", f"recovered from: {stall}", renderer)
                continue
            memory = unit_memory_mb()
            if (memory or 0) > MEMORY_REFRESH_MB or time.monotonic() - stream.chrome_started > CHROME_REFRESH_S:
                reason = f"memory {memory} MiB" if (memory or 0) > MEMORY_REFRESH_MB else "hourly refresh"
                LOG.info("fresh Chromium: %s", reason)
                await stream.restart_chrome(stalled=False)
                continue
            try:
                _, uri = await asyncio.to_thread(renderer_now, renderer)
                if taken_over(uri, stream.token):
                    return "the TV is showing something else"
            except OSError:
                pass  # busy decoding; whether it still pulls the stream decides
            if (since > START_GRACE_S and not stream.clients
                    and time.monotonic() - stream.last_client > NO_CLIENT_S):
                return "the TV stopped pulling the stream"
            if since > RESTART_AFTER_S:
                return "twice-daily refresh"

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    caster = Caster(Settings.from_env())
    try:
        asyncio.run(caster.run())
    finally:
        status_path().unlink(missing_ok=True)


if __name__ == "__main__":
    main()
