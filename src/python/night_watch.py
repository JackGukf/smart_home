"""Night watch: a clip and a photo when something moves outside at night.

Asked for 2026-09-25, after a night when the front door's outdoor motion sensor
fired five times between 02:22 and 02:33 and nothing could say what it was -
the cameras watched, but nothing was kept.

What it listens to (MQTT - the Zigbee stack and the NPU detector publish there):

  * The outdoor motion sensors and the back door's vibration sensor, each mapped
    to the camera that sees that spot.
  * A person rising on an outdoor camera (npu-detector's smarthome/vision/<cam>).
  * The alarm speaker starting to sound - day or night - which records both
    indoor cameras: that is the moment a picture matters most.

What it does, at night (NIGHT_WATCH_HOURS, default 22:00-06:30):

  * Saves a snapshot, with the detector's boxes and confidences drawn on it when
    the trigger was the detector, and a 20 s clip (ffmpeg, stream copy - no
    re-encoding) under ~/night-clips/<date>/.
  * Sends the snapshot to Telegram, at most once per trigger per 5 minutes, so a
    sensor firing every two minutes on a windy night is one message, not five.
  * A motion or vibration sensor on its own is **not** believed: its clip is
    checked, and the photo is sent only if the camera saw something move - the
    moment of most movement, boxed. The front door's outdoor sensor fired 437
    times in the week to 2026-09-25, 88 of them at night, and at night a camera
    or the door agreed 3 times; the five of that evening showed nothing moving
    in 20 s of video. The clip and snapshot are kept either way.

It also keeps an *evidence* snapshot, locally and without Telegram, whenever an
indoor camera's person detection rises at night. That exists because the office
camera saw a "person" from 01:10 to 02:33 on 2026-09-25 while nobody was there:
the boxes on those pictures show what the detector mistakes for one.

Clips read go2rtc's local RTSP re-stream. For the cameras the detector already
watches, go2rtc shares its one camera connection, so a clip adds no Wi-Fi
traffic; the backyard camera is pulled only for the length of its clip.

Kept 14 days (NIGHT_WATCH_KEEP_DAYS) and at most 20 GB (NIGHT_WATCH_MAX_GB),
oldest first.

    python -m src.python.night_watch            # run (the systemd unit does this)
    python -m src.python.night_watch --test front_door_camera   # one snapshot + clip now
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any, Callable, Iterable

LOG = logging.getLogger("night_watch")

# Zigbee sensor (its zigbee2mqtt friendly name) -> (the property that means
# "tripped", the camera that sees that spot, what to call it).
SENSORS: dict[str, tuple[str, str, str]] = {
    "Motion sensor and TH front door": ("presence", "front_door_camera", "Front door motion"),
    "Motion sensor and TH Backyard": ("presence", "wyze_camera", "Backyard motion"),
    "Motion sensor and TH fence south": ("presence", "wyze_camera", "South fence motion"),
    "Vibration sensor backdoor": ("vibration", "wyze_camera", "Back door vibration"),
}
# Outdoor cameras whose own person detection is a trigger.
OUTDOOR_CAMERAS: dict[str, str] = {
    "front_door_camera": "Person at the front door",
    "frontyard_camera": "Person in the front yard",
    "garage_camera": "Person on the driveway",
}
# Indoor cameras: evidence snapshots at night; clips and photos when the siren sounds.
INDOOR_CAMERAS: dict[str, str] = {
    "office_camera": "Office",
    "family_room_camera": "Family room",
}
SPEAKER = "Alarm speaker"          # zigbee2mqtt friendly name; property "alarm"


@dataclass(frozen=True)
class Trigger:
    camera: str
    reason: str
    kind: str                          # "sensor", "person", "siren" or "evidence"
    detections: tuple[dict[str, Any], ...] = ()

    @property
    def any_time(self) -> bool:
        """The siren matters day or night; everything else only at night."""
        return self.kind == "siren"

    @property
    def tells_telegram(self) -> bool:
        return self.kind != "evidence"

    @property
    def records_clip(self) -> bool:
        return self.kind != "evidence"


# ---------------------------------------------------------------------- rules

def parse_hours(raw: str) -> tuple[dtime, dtime]:
    """"22:00-06:30" -> (22:00, 06:30). A bad value falls back to the default
    rather than taking the watch down."""
    try:
        start, end = raw.split("-")
        a, b = (datetime.strptime(x.strip(), "%H:%M").time() for x in (start, end))
        return a, b
    except ValueError:
        LOG.warning("NIGHT_WATCH_HOURS=%r is not HH:MM-HH:MM; using 22:00-06:30", raw)
        return dtime(22, 0), dtime(6, 30)


def is_night(now: datetime, hours: tuple[dtime, dtime]) -> bool:
    start, end = hours
    t = now.time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end          # across midnight


class EdgeDetector:
    """Rising edges per (topic, key). The first message seen on a topic is only a
    baseline: retained messages arrive on connect, and a retained "true" is not
    something that just happened."""

    def __init__(self) -> None:
        self._last: dict[tuple[str, str], bool] = {}

    def rose(self, topic: str, key: str, value: Any) -> bool:
        now = value is True
        seen = (topic, key) in self._last
        before = self._last.get((topic, key), False)
        self._last[(topic, key)] = now
        return seen and now and not before


def triggers_for(topic: str, payload: dict[str, Any], edges: EdgeDetector) -> list[Trigger]:
    """What one MQTT message sets off, if anything."""
    if topic.startswith("zigbee2mqtt/"):
        name = topic[len("zigbee2mqtt/"):]
        if name in SENSORS:
            key, camera, reason = SENSORS[name]
            if edges.rose(topic, key, payload.get(key)):
                return [Trigger(camera, reason, "sensor")]
        elif name == SPEAKER and edges.rose(topic, "alarm", payload.get("alarm")):
            return [Trigger(camera, f"Alarm speaker sounding - {room}", "siren")
                    for camera, room in INDOOR_CAMERAS.items()]
        return []
    camera = topic.rsplit("/", 1)[-1]
    if not edges.rose(topic, "person", payload.get("person")):
        return []
    people = tuple(d for d in payload.get("detections") or [] if d.get("label") == "person")
    if camera in OUTDOOR_CAMERAS:
        return [Trigger(camera, OUTDOOR_CAMERAS[camera], "person", people)]
    if camera in INDOOR_CAMERAS:
        return [Trigger(camera, f"{INDOOR_CAMERAS[camera]} camera saw a person", "evidence", people)]
    return []


class Cooldown:
    """At most one action per key per `seconds`."""

    def __init__(self, seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.seconds = seconds
        self.clock = clock
        self._last: dict[str, float] = {}

    def ready(self, key: str) -> bool:
        now = self.clock()
        if now - self._last.get(key, float("-inf")) < self.seconds:
            return False
        self._last[key] = now
        return True


def files_to_delete(files: Iterable[tuple[Path, float, int]], now: float,
                    keep_days: float, max_bytes: int) -> list[Path]:
    """(path, mtime, size) -> what to delete: everything older than keep_days,
    then the oldest of the rest until the total fits in max_bytes."""
    items = sorted(files, key=lambda f: f[1])
    cutoff = now - keep_days * 86400
    doomed = [f for f in items if f[1] < cutoff]
    kept = [f for f in items if f[1] >= cutoff]
    total = sum(f[2] for f in kept)
    for f in kept:
        if total <= max_bytes:
            break
        doomed.append(f)
        total -= f[2]
    return [f[0] for f in doomed]


def caption(trigger: Trigger, at: datetime, clip: bool) -> str:
    people = [f"{d.get('confidence', 0):.0%}" for d in trigger.detections]
    seen = f" (person {', '.join(people)})" if people else ""
    return (f"🌙 {trigger.reason}{seen} · {at:%H:%M:%S}"
            + ("\nA 20 s clip is saved on the board." if clip else ""))


def multipart(fields: dict[str, str], file_field: str, filename: str, data: bytes,
              content_type: str = "image/jpeg") -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
                     .encode("utf-8"))
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
                 f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8"))
    parts.append(data)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# ------------------------------------------------------------------- actions

@dataclass
class Settings:
    hours: tuple[dtime, dtime] = (dtime(22, 0), dtime(6, 30))
    out_dir: Path = Path.home() / "night-clips"
    clip_seconds: int = 20
    keep_days: float = 14
    max_bytes: int = 20 * 1024 ** 3
    go2rtc_url: str = "http://127.0.0.1:1984"
    rtsp_url: str = "rtsp://127.0.0.1:8554"
    telegram_token: str = ""
    telegram_chats: list[str] = field(default_factory=list)
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_password: str | None = None
    vision_topic: str = "smarthome/vision"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            hours=parse_hours(os.getenv("NIGHT_WATCH_HOURS", "22:00-06:30")),
            out_dir=Path(os.path.expanduser(os.getenv("NIGHT_WATCH_DIR", "~/night-clips"))),
            clip_seconds=int(os.getenv("NIGHT_WATCH_CLIP_S", "20")),
            keep_days=float(os.getenv("NIGHT_WATCH_KEEP_DAYS", "14")),
            max_bytes=int(float(os.getenv("NIGHT_WATCH_MAX_GB", "20")) * 1024 ** 3),
            go2rtc_url=os.getenv("GO2RTC_URL", "http://127.0.0.1:1984"),
            rtsp_url=os.getenv("GO2RTC_RTSP_URL", "rtsp://127.0.0.1:8554"),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chats=[c.strip() for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()],
            mqtt_host=os.getenv("MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_user=os.getenv("MQTT_USER") or None,
            mqtt_password=os.getenv("MQTT_PASSWORD") or None,
            vision_topic=os.getenv("NPU_BASE_TOPIC", "smarthome/vision"),
        )


class NightWatch:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.edges = EdgeDetector()
        self.telegram_cooldown = Cooldown(300)
        self.clip_cooldown = Cooldown(60)
        self.evidence_cooldown = Cooldown(60)
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nw")
        self.clips = threading.BoundedSemaphore(3)     # ffmpeg processes at once

    # MQTT ------------------------------------------------------------------
    def on_message(self, topic: str, raw: bytes) -> None:
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            return
        if not isinstance(payload, dict):
            return
        for trigger in triggers_for(topic, payload, self.edges):
            if trigger.any_time or is_night(datetime.now(), self.s.hours):
                self.pool.submit(self.handle, trigger)

    # One trigger -----------------------------------------------------------
    def handle(self, trigger: Trigger) -> None:
        key = f"{trigger.kind}:{trigger.camera}:{trigger.reason}"
        at = datetime.now()
        if trigger.kind == "evidence":
            if self.evidence_cooldown.ready(key):
                self.snapshot(trigger, at)
            return
        clip = trigger.records_clip and self.clip_cooldown.ready(trigger.camera)
        if trigger.kind == "sensor":
            image = self.snapshot(trigger, at)
            if clip:
                self.pool.submit(self.confirm_by_camera, trigger, at, key, image)
            return
        if clip:
            self.pool.submit(self.record, trigger, at)
        image = self.snapshot(trigger, at)
        if image and trigger.tells_telegram and self.telegram_cooldown.ready(key):
            self.send_photo(image, caption(trigger, at, clip))

    def _path(self, trigger: Trigger, at: datetime, suffix: str) -> Path:
        day = self.s.out_dir / f"{at:%Y-%m-%d}"
        day.mkdir(parents=True, exist_ok=True)
        slug = trigger.reason.lower().replace(" ", "-").replace("---", "-")
        return day / f"{at:%H%M%S}_{trigger.camera}_{slug}{suffix}"

    def snapshot(self, trigger: Trigger, at: datetime) -> bytes | None:
        url = f"{self.s.go2rtc_url}/api/frame.jpeg?src={trigger.camera}"
        try:
            with urllib.request.urlopen(url, timeout=12) as response:
                jpeg = response.read()
        except OSError as exc:
            LOG.warning("%s: no snapshot (%s)", trigger.camera, exc)
            return None
        if trigger.detections:
            jpeg = annotate(jpeg, trigger.detections)
        path = self._path(trigger, at, ".jpg")
        path.write_bytes(jpeg)
        LOG.info("%s: %s -> %s", trigger.camera, trigger.reason, path.name)
        return jpeg

    def record(self, trigger: Trigger, at: datetime) -> Path | None:
        """The clip's path, or None when there is none."""
        if not self.clips.acquire(blocking=False):
            LOG.warning("%s: clip skipped, %d already recording", trigger.camera, 3)
            return None
        try:
            path = self._path(trigger, at, ".mp4")
            command = ["ffmpeg", "-nostdin", "-loglevel", "error", "-rtsp_transport", "tcp",
                       "-i", f"{self.s.rtsp_url}/{trigger.camera}", "-t", str(self.s.clip_seconds),
                       "-map", "0:v:0", "-c", "copy", "-an", "-movflags", "+faststart", "-y", str(path)]
            result = subprocess.run(command, capture_output=True, timeout=self.s.clip_seconds + 40)
            if result.returncode != 0 or not path.exists() or path.stat().st_size == 0:
                # ffmpeg's own message, not the command: the URL is local, but
                # keep the habit of never logging a stream command line.
                LOG.warning("%s: clip failed: %s", trigger.camera,
                            result.stderr.decode("utf-8", "replace").strip()[-300:])
                path.unlink(missing_ok=True)
                return None
            return path
        except subprocess.TimeoutExpired:
            LOG.warning("%s: clip timed out", trigger.camera)
            return None
        finally:
            self.clips.release()

    def confirm_by_camera(self, trigger: Trigger, at: datetime, key: str, snapshot: bytes | None) -> None:
        """A sensor alone is not believed: send only if its clip shows movement."""
        path = self.record(trigger, at)
        if path is None:
            # No clip to judge by - better the snapshot than silence.
            if snapshot and self.telegram_cooldown.ready(key):
                self.send_photo(snapshot, caption(trigger, at, False) + "\n(no clip to confirm it)")
            return
        moved, frame = movement_in_clip(path)
        if not moved:
            LOG.info("%s: %s - nothing moved on camera, not sent", trigger.camera, trigger.reason)
            return
        if self.telegram_cooldown.ready(key):
            self.send_photo(frame or snapshot or b"", caption(trigger, at, True) + "\nThe camera saw movement.")

    def send_photo(self, jpeg: bytes, text: str) -> None:
        if not self.s.telegram_token or not self.s.telegram_chats:
            return
        for chat in self.s.telegram_chats:
            body, content_type = multipart({"chat_id": chat, "caption": text}, "photo", "night.jpg", jpeg)
            # Twice: the first test on 2026-09-25 stalled for 30 s and the same
            # upload a minute later took 1.3 s. One stall must not lose the photo.
            for attempt in (1, 2):
                request = urllib.request.Request(
                    f"https://api.telegram.org/bot{self.s.telegram_token}/sendPhoto",
                    data=body, headers={"Content-Type": content_type}, method="POST")
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        response.read()
                    break
                except OSError as exc:
                    # Never the URL: it carries the bot token.
                    LOG.warning("Telegram photo not sent (attempt %d): %s", attempt,
                                getattr(exc, "reason", type(exc).__name__))
                    if attempt == 1:
                        time.sleep(5)

    # Housekeeping ----------------------------------------------------------
    def tidy(self) -> None:
        if not self.s.out_dir.exists():
            return
        files = [(p, p.stat().st_mtime, p.stat().st_size) for p in self.s.out_dir.rglob("*") if p.is_file()]
        doomed = files_to_delete(files, time.time(), self.s.keep_days, self.s.max_bytes)
        for path in doomed:
            path.unlink(missing_ok=True)
        for day in self.s.out_dir.iterdir():
            if day.is_dir() and not any(day.iterdir()):
                day.rmdir()
        if doomed:
            LOG.info("tidied %d old file(s)", len(doomed))


# Movement worth a message, on a 480x270 copy: a blob of at least 0.8% of the
# picture (a cat is several times that; the camera's ticking clock ~0.03%), and
# not a change of most of it (headlights, the camera switching to night mode).
MOVING_BLOB = 0.008
LIGHTING_CHANGE = 0.25


def movement_in_clip(path: Path, samples_per_s: float = 4.0) -> tuple[bool, bytes | None]:
    """(moved, the frame with the most movement, boxed, as JPEG)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return True, None                   # cannot judge: do not swallow the alert
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    step = max(1, int(round(fps / samples_per_s)))
    area = 480 * 270
    prev, index, best = None, 0, (0, None, None)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        index += 1
        if index % step:
            continue
        small = cv2.resize(frame, (480, 270))
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        if prev is not None:
            changed = cv2.absdiff(gray, prev) > 25
            if changed.mean() < LIGHTING_CHANGE:
                mask = cv2.dilate(changed.astype(np.uint8), np.ones((5, 5), np.uint8))
                n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
                if n > 1:
                    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                    blob = int(stats[i, cv2.CC_STAT_AREA])
                    if blob > best[0]:
                        scale = [frame.shape[1] / 480, frame.shape[0] / 270] * 2   # x, y, w, h
                        best = (blob, frame, stats[i, :4] * scale)
        prev = gray
    cap.release()
    blob, frame, box = best
    if blob < MOVING_BLOB * area or frame is None:
        return False, None
    x, y, w, h = (int(v) for v in box)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 255), 3)
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return True, (jpeg.tobytes() if ok else None)


def annotate(jpeg: bytes, detections: Iterable[dict[str, Any]]) -> bytes:
    """Draw the detector's boxes and confidences on the frame. If anything goes
    wrong the plain picture is better than none."""
    try:
        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return jpeg
        height, width = image.shape[:2]
        for d in detections:
            x1, y1, x2, y2 = (int(v) for v in d.get("box") or (0, 0, 0, 0))
            x1, x2 = max(0, min(width - 1, x1)), max(0, min(width - 1, x2))
            y1, y2 = max(0, min(height - 1, y1)), max(0, min(height - 1, y2))
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 3)
            label = f"{d.get('label', '?')} {float(d.get('confidence', 0)):.2f}"
            cv2.putText(image, label, (x1 + 4, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 0, 255), 2, cv2.LINE_AA)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        return encoded.tobytes() if ok else jpeg
    except Exception:  # noqa: BLE001 - a missing box beats a missing picture
        LOG.exception("could not draw the boxes")
        return jpeg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test", metavar="CAMERA", help="one snapshot, clip and Telegram photo now, then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if shutil.which("ffmpeg") is None:
        LOG.error("ffmpeg is not installed")
        return 1
    watch = NightWatch(settings)

    if args.test:
        trigger = Trigger(args.test, "Test", "sensor")
        at = datetime.now()
        watch.record(trigger, at)
        image = watch.snapshot(trigger, at)
        if image:
            watch.send_photo(image, caption(trigger, at, True))
        return 0 if image else 1

    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="night-watch")
    if settings.mqtt_user:
        client.username_pw_set(settings.mqtt_user, settings.mqtt_password)
    topics = ([f"zigbee2mqtt/{name}" for name in (*SENSORS, SPEAKER)]
              + [f"{settings.vision_topic}/{camera}" for camera in (*OUTDOOR_CAMERAS, *INDOOR_CAMERAS)])

    def on_connect(client, _userdata, _flags, reason, _properties=None):
        LOG.info("connected to MQTT (%s); watching %d topics, night %s-%s", reason, len(topics),
                 settings.hours[0].strftime("%H:%M"), settings.hours[1].strftime("%H:%M"))
        for topic in topics:
            client.subscribe(topic)

    client.on_connect = on_connect
    client.on_message = lambda _c, _u, message: watch.on_message(message.topic, message.payload)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    LOG.info("clips to %s, kept %g days / %.0f GB; Telegram %s", settings.out_dir, settings.keep_days,
             settings.max_bytes / 1024 ** 3, "on" if settings.telegram_token and settings.telegram_chats else "off")
    try:
        while True:
            watch.tidy()
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
