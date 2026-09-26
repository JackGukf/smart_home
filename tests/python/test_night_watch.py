"""Night watch: what counts as a trigger, when, and what it does about it."""
from __future__ import annotations

from datetime import datetime, time as dtime
from pathlib import Path

import pytest

from src.python import night_watch as nw
from src.python.night_watch import (Cooldown, EdgeDetector, NightWatch, Settings, Trigger, caption,
                                    files_to_delete, is_night, multipart, parse_hours, triggers_for)

NIGHT = (dtime(22, 0), dtime(6, 30))


def test_night_crosses_midnight():
    assert is_night(datetime(2026, 9, 25, 2, 22), NIGHT)
    assert is_night(datetime(2026, 9, 25, 22, 0), NIGHT)
    assert not is_night(datetime(2026, 9, 25, 6, 30), NIGHT)
    assert not is_night(datetime(2026, 9, 25, 14, 0), NIGHT)
    assert is_night(datetime(2026, 9, 25, 3, 0), (dtime(1, 0), dtime(5, 0)))


def test_bad_hours_fall_back_rather_than_stop_the_watch():
    assert parse_hours("22:00-06:30") == NIGHT
    assert parse_hours("nonsense") == NIGHT


def test_a_retained_message_on_connect_is_a_baseline_not_an_event():
    edges = EdgeDetector()
    assert not edges.rose("t", "presence", True)      # retained "true" at startup
    assert not edges.rose("t", "presence", True)
    assert not edges.rose("t", "presence", False)
    assert edges.rose("t", "presence", True)           # this one happened


def _prime(edges, topic, key):
    edges.rose(topic, key, False)


def test_an_outdoor_sensor_records_the_camera_that_sees_it():
    edges = EdgeDetector()
    topic = "zigbee2mqtt/Motion sensor and TH front door"
    _prime(edges, topic, "presence")
    [trigger] = triggers_for(topic, {"presence": True, "battery": 100}, edges)
    assert trigger == Trigger("front_door_camera", "Front door motion", "sensor")
    assert triggers_for(topic, {"presence": True}, edges) == []    # still on: not again


def test_the_back_door_vibration_goes_to_the_backyard_camera():
    edges = EdgeDetector()
    topic = "zigbee2mqtt/Vibration sensor backdoor"
    _prime(edges, topic, "vibration")
    [trigger] = triggers_for(topic, {"vibration": True}, edges)
    assert trigger.camera == "wyze_camera" and trigger.kind == "sensor"


def test_an_outdoor_person_carries_the_detectors_boxes():
    edges = EdgeDetector()
    topic = "smarthome/vision/front_door_camera"
    _prime(edges, topic, "person")
    box = {"label": "person", "confidence": 0.81, "box": [1, 2, 3, 4]}
    car = {"label": "car", "confidence": 0.9, "box": [5, 6, 7, 8]}
    [trigger] = triggers_for(topic, {"person": True, "detections": [box, car]}, edges)
    assert trigger.kind == "person" and trigger.detections == (box,)


def test_an_indoor_person_is_evidence_only_no_clip_no_telegram():
    """The office camera's false "person" of 2026-09-25: keep the picture with the
    boxes to see what it mistakes, but do not message anyone about it."""
    edges = EdgeDetector()
    topic = "smarthome/vision/office_camera"
    _prime(edges, topic, "person")
    [trigger] = triggers_for(topic, {"person": True, "detections": []}, edges)
    assert trigger.kind == "evidence"
    assert not trigger.tells_telegram and not trigger.records_clip and not trigger.any_time


def test_the_siren_records_both_indoor_cameras_day_or_night():
    edges = EdgeDetector()
    topic = "zigbee2mqtt/Alarm speaker"
    _prime(edges, topic, "alarm")
    triggers = triggers_for(topic, {"alarm": True}, edges)
    assert {t.camera for t in triggers} == set(nw.INDOOR_CAMERAS)
    assert all(t.any_time and t.tells_telegram and t.records_clip for t in triggers)


def test_unknown_topics_and_other_fields_do_nothing():
    edges = EdgeDetector()
    assert triggers_for("zigbee2mqtt/Some lamp", {"state": "ON"}, edges) == []
    assert triggers_for("smarthome/vision/wyze_camera", {"person": True}, edges) == []


def test_cooldown():
    now = [0.0]
    c = Cooldown(300, clock=lambda: now[0])
    assert c.ready("a") and not c.ready("a") and c.ready("b")
    now[0] = 301
    assert c.ready("a")


def test_retention_drops_old_days_then_the_oldest_until_it_fits():
    day = 86400
    now = 100 * day
    files = [(Path("old.mp4"), now - 20 * day, 10), (Path("a.mp4"), now - 3 * day, 60),
             (Path("b.mp4"), now - 2 * day, 30), (Path("c.jpg"), now - 1 * day, 20)]
    assert files_to_delete(files, now, keep_days=14, max_bytes=1000) == [Path("old.mp4")]
    assert files_to_delete(files, now, keep_days=14, max_bytes=60) == [Path("old.mp4"), Path("a.mp4")]


def test_caption_says_what_when_and_how_sure():
    trigger = Trigger("front_door_camera", "Person at the front door", "person",
                      ({"label": "person", "confidence": 0.81},))
    text = caption(trigger, datetime(2026, 9, 26, 2, 22, 50), clip=True)
    assert text.startswith("🌙 Person at the front door (person 81%) · 02:22:50")
    assert "clip is saved" in text


def test_multipart_carries_the_fields_and_the_photo():
    body, content_type = multipart({"chat_id": "42", "caption": "hi"}, "photo", "n.jpg", b"\xff\xd8JPEG")
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}".encode()) and body.endswith(f"--{boundary}--\r\n".encode())
    assert b'name="chat_id"\r\n\r\n42' in body and b"\xff\xd8JPEG" in body


class _Recording(NightWatch):
    """handle() without cameras, ffmpeg or Telegram."""

    def __init__(self):
        super().__init__(Settings(telegram_token="t", telegram_chats=["1"]))
        self.snaps, self.clips_made, self.photos = [], [], []
        self.pool.submit = lambda fn, *a: fn(*a)          # run inline

    def snapshot(self, trigger, at):
        self.snaps.append(trigger.camera)
        return b"jpeg"

    def record(self, trigger, at):
        self.clips_made.append(trigger.camera)

    def send_photo(self, jpeg, text):
        self.photos.append(text)


def test_a_sensor_firing_every_two_minutes_is_one_message_not_five():
    watch = _Recording()
    trigger = Trigger("front_door_camera", "Front door motion", "sensor")
    for _ in range(5):
        watch.handle(trigger)
    assert len(watch.snaps) == 5          # every picture is kept
    assert len(watch.photos) == 1         # one Telegram message
    assert len(watch.clips_made) == 1     # one clip per camera per minute


def test_evidence_is_kept_locally_only():
    watch = _Recording()
    watch.handle(Trigger("office_camera", "Office camera saw a person", "evidence"))
    assert watch.snaps == ["office_camera"] and watch.photos == [] and watch.clips_made == []


def test_daytime_sensors_do_nothing_but_the_siren_always_counts(monkeypatch):
    watch = _Recording()
    watch.pool.submit = lambda fn, *a: watch.snaps.append(("queued", a[0].kind))

    class _Noon(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 25, 12, 0)

    monkeypatch.setattr(nw, "datetime", _Noon)
    watch.on_message("zigbee2mqtt/Motion sensor and TH front door", b'{"presence": false}')
    watch.on_message("zigbee2mqtt/Motion sensor and TH front door", b'{"presence": true}')
    watch.on_message("zigbee2mqtt/Alarm speaker", b'{"alarm": false}')
    watch.on_message("zigbee2mqtt/Alarm speaker", b'{"alarm": true}')
    assert watch.snaps == [("queued", "siren"), ("queued", "siren")]


def test_boxes_are_drawn_on_the_photo():
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    ok, jpeg = cv2.imencode(".jpg", np.full((120, 160, 3), 255, np.uint8))
    drawn = nw.annotate(jpeg.tobytes(), [{"label": "person", "confidence": 0.4, "box": [10, 10, 60, 100]}])
    image = cv2.imdecode(np.frombuffer(drawn, np.uint8), cv2.IMREAD_COLOR)
    assert image[10, 30][2] > 200 and image[10, 30][0] < 80     # red edge where the box is


def test_a_broken_picture_is_sent_as_it_is():
    assert nw.annotate(b"not a jpeg", [{"box": [0, 0, 1, 1]}]) == b"not a jpeg"


def test_one_stalled_upload_is_retried(monkeypatch):
    calls = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def urlopen(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise TimeoutError("stalled")
        return _Response()

    monkeypatch.setattr(nw.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(nw.time, "sleep", lambda s: None)
    watch = NightWatch(Settings(telegram_token="tok", telegram_chats=["1"]))
    watch.send_photo(b"jpeg", "hi")
    assert len(calls) == 2


def test_the_token_never_reaches_the_log(monkeypatch, caplog):
    def urlopen(request, timeout):
        raise TimeoutError("stalled")

    monkeypatch.setattr(nw.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(nw.time, "sleep", lambda s: None)
    NightWatch(Settings(telegram_token="SECRET123", telegram_chats=["1"])).send_photo(b"j", "hi")
    assert "SECRET123" not in caplog.text and "not sent" in caplog.text
