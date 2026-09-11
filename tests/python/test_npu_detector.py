"""Detection post-processing for the NPU camera service.

The NPU itself cannot be exercised here - it only exists on the board - so these
cover the parts that are wrong silently: mapping boxes back out of the letterbox,
suppressing duplicates without deleting overlapping objects of different classes,
and the payload shape Home Assistant binds to.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from src.python.npu_detector import (
    COCO_NAMES,
    Config,
    Detection,
    build_payload,
    decode,
    nms,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _yolo_output(boxes_scores: list[tuple[tuple[float, float, float, float], int, float]],
                 anchors: int = 8400) -> np.ndarray:
    """Build a [1, 84, anchors] tensor with the given xywh/class/score entries."""
    out = np.zeros((1, 84, anchors), dtype=np.float32)
    for i, ((cx, cy, w, h), cls, score) in enumerate(boxes_scores):
        out[0, 0, i], out[0, 1, i], out[0, 2, i], out[0, 3, i] = cx, cy, w, h
        out[0, 4 + cls, i] = score
    return out


def test_boxes_are_mapped_back_out_of_the_letterbox() -> None:
    """A 640x360 frame is padded top and bottom to reach 640x640.

    Forgetting the padding puts boxes at plausible-looking but wrong heights,
    which is the kind of bug that survives a demo.
    """
    frame_h, frame_w = 360, 640
    scale = min(640 / frame_h, 640 / frame_w)   # 1.0 for this frame
    pad_x, pad_y = 0, (640 - int(round(frame_h * scale))) // 2   # 140

    # A box centred in model space should come back centred in the source frame.
    out = _yolo_output([((320.0, 320.0, 100.0, 100.0), 0, 0.9)])
    dets = decode(out, scale, pad_x, pad_y, (frame_h, frame_w), conf_thr=0.3,
                  iou_thr=0.45, wanted={"person"})

    assert len(dets) == 1
    x1, y1, x2, y2 = dets[0].box
    assert dets[0].label == "person"
    assert (x1, x2) == (270, 370)
    # 320 in model space minus 140 of padding is 180, the middle of a 360px frame.
    assert (y1, y2) == (130, 230)


def test_boxes_are_clipped_to_the_frame() -> None:
    """Padding maps to negative coordinates, which must not escape as negatives."""
    out = _yolo_output([((50.0, 50.0, 200.0, 200.0), 0, 0.9)])
    dets = decode(out, 1.0, 0, 140, (360, 640), conf_thr=0.3, iou_thr=0.45, wanted=None)
    x1, y1, x2, y2 = dets[0].box
    assert x1 >= 0 and y1 >= 0
    assert x2 <= 639 and y2 <= 359


def test_low_confidence_boxes_are_dropped() -> None:
    out = _yolo_output([((320.0, 320.0, 50.0, 50.0), 0, 0.10)])
    assert decode(out, 1.0, 0, 0, (640, 640), conf_thr=0.35, iou_thr=0.45, wanted=None) == []


def test_class_filter_keeps_only_what_was_asked_for() -> None:
    out = _yolo_output([
        ((100.0, 100.0, 40.0, 40.0), 0, 0.9),   # person
        ((300.0, 300.0, 40.0, 40.0), 2, 0.9),   # car
    ])
    labels = {
        d.label
        for d in decode(out, 1.0, 0, 0, (640, 640), conf_thr=0.3, iou_thr=0.45,
                        wanted={"person"})
    }
    assert labels == {"person"}


def test_nms_suppresses_duplicates_of_the_same_class() -> None:
    boxes = np.array([[10, 10, 110, 110], [12, 12, 112, 112]], dtype=np.float32)
    scores = np.array([0.9, 0.8], dtype=np.float32)
    classes = np.array([0, 0])
    assert nms(boxes, scores, classes, iou_thr=0.45, max_det=10) == [0]


def test_nms_keeps_overlapping_objects_of_different_classes() -> None:
    """A person standing in front of a car must not delete the car."""
    boxes = np.array([[10, 10, 110, 110], [12, 12, 112, 112]], dtype=np.float32)
    scores = np.array([0.9, 0.8], dtype=np.float32)
    classes = np.array([0, 2])
    assert sorted(nms(boxes, scores, classes, iou_thr=0.45, max_det=10)) == [0, 1]


def test_payload_carries_a_plain_boolean_per_watched_class() -> None:
    """Automations bind to a boolean, not to a list they have to parse."""
    payload = json.loads(build_payload(
        "front_door_camera",
        [Detection("person", 0.91, (1, 2, 3, 4)), Detection("person", 0.72, (5, 6, 7, 8))],
        ["person", "car"],
    ))
    assert payload["camera"] == "front_door_camera"
    assert payload["person"] is True
    assert payload["car"] is False
    assert payload["counts"] == {"person": 2}
    assert len(payload["detections"]) == 2
    assert payload["detections"][0]["confidence"] == 0.91


def test_empty_payload_still_reports_the_class_as_false() -> None:
    """Silence must read as "nobody there", not as missing data."""
    payload = json.loads(build_payload("cam", [], ["person"]))
    assert payload["person"] is False
    assert payload["counts"] == {}


def test_coco_labels_are_the_yolov8_order() -> None:
    assert len(COCO_NAMES) == 80
    assert COCO_NAMES[0] == "person"
    assert COCO_NAMES[2] == "car"


def test_config_defaults_to_watching_for_people(monkeypatch) -> None:
    for key in ("NPU_CAMERAS", "NPU_CLASSES", "NPU_MODEL", "MQTT_USER"):
        monkeypatch.delenv(key, raising=False)
    cfg = Config.from_env()
    assert cfg.classes == {"person"}
    assert cfg.cameras == []
    assert cfg.mqtt_port == 1883


def test_config_reads_cameras_and_classes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("NPU_CAMERAS", "front_door_camera, family_room_camera ")
    monkeypatch.setenv("NPU_CLASSES", "person,car")
    cfg = Config.from_env()
    assert cfg.cameras == ["front_door_camera", "family_room_camera"]
    assert cfg.classes == {"person", "car"}


# ------------------------------------------------------------------- packaging

def test_detector_service_runs_the_project_script() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "npu-detector.service").read_text(
        encoding="utf-8"
    )
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/run-npu-detector.sh" in unit
    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit
    # Graph compilation costs ~14s, so a crash loop must not hammer the NPU.
    assert "RestartSec=15" in unit


def test_llama_server_service_runs_the_project_script() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "llama-server.service").read_text(
        encoding="utf-8"
    )
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/run-llama-server.sh" in unit
    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit


def test_llama_runner_pins_the_a720_cores_and_uses_the_tuned_build() -> None:
    """The two settings that carry the performance, per the 2026-09-02 benchmark.

    Unpinned costs 40% of generation throughput; the naive build costs 3x on
    prompt processing.
    """
    script = (PROJECT_ROOT / "scripts" / "run-llama-server.sh").read_text(encoding="utf-8")
    assert "0,1,6,7,8,9,10,11" in script
    assert "build-kleidi-off" in script
    assert "taskset" in script
    assert "Qwen3-4B-Q4_0.gguf" in script
    # Loopback: this is a single-user endpoint, like the Ollama service.
    assert 'LLAMA_HOST:-127.0.0.1' in script


def test_llama_build_script_spells_out_the_arch() -> None:
    """-mcpu=native yields zero ARM feature macros on this CPU and builds a
    baseline binary without warning."""
    script = (PROJECT_ROOT / "scripts" / "build-llama-server.sh").read_text(encoding="utf-8")
    assert "GGML_CPU_ARM_ARCH" in script
    assert "armv9-a+i8mm+dotprod+sve+bf16" in script
    assert "-DGGML_NATIVE=OFF" in script
    assert "-DGGML_CPU_KLEIDIAI=OFF" in script


def test_npu_runner_sets_up_the_compass_layerlib_and_uses_python_311() -> None:
    """Both are silent failures: a missing ./operator corrupts the heap, and the
    system Python cannot load the cp311 wheel at all."""
    script = (PROJECT_ROOT / "scripts" / "run-npu-detector.sh").read_text(encoding="utf-8")
    assert "operator" in script
    assert "npu-venv" in script
    assert "cd \"${NPU_WORKDIR}\"" in script


def test_detector_refuses_silent_cpu_fallback() -> None:
    """A detector quietly running on the CPU defeats the entire point."""
    source = (PROJECT_ROOT / "src" / "python" / "npu_detector.py").read_text(encoding="utf-8")
    assert "session.disable_cpu_ep_fallback" in source


def test_mqtt_client_supports_paho_2_callback_api() -> None:
    """paho 2.x warns on every start without an explicit callback API version,
    and 1.x rejects the argument, so both have to be handled."""
    source = (PROJECT_ROOT / "src" / "python" / "npu_detector.py").read_text(encoding="utf-8")
    assert "CallbackAPIVersion" in source
    assert 'hasattr(mqtt, "CallbackAPIVersion")' in source


# ------------------------------------------------- Home Assistant MQTT discovery

def _discovery(camera="front_door_camera", classes=("person",)):
    from src.python.npu_detector import discovery_messages

    return dict(
        discovery_messages(camera, classes, "smarthome/vision", "smarthome/vision/status")
    )


def test_discovery_publishes_a_binary_sensor_and_a_count_per_class() -> None:
    msgs = _discovery(classes=("person", "car"))
    topics = sorted(msgs)
    assert topics == sorted([
        "homeassistant/binary_sensor/npu_vision_front_door_camera/person/config",
        "homeassistant/sensor/npu_vision_front_door_camera/person_count/config",
        "homeassistant/binary_sensor/npu_vision_front_door_camera/car/config",
        "homeassistant/sensor/npu_vision_front_door_camera/car_count/config",
    ])


def test_binary_sensor_matches_the_json_the_detector_actually_publishes() -> None:
    """The template must render the booleans as true/false.

    A bare `value_json.person` renders Python's True/False, which never matches
    payload_on, so the entity would sit permanently off while detections flowed.
    """
    cfg = json.loads(_discovery()["homeassistant/binary_sensor/npu_vision_front_door_camera/person/config"])
    assert cfg["state_topic"] == "smarthome/vision/front_door_camera"
    assert cfg["payload_on"] == "true"
    assert cfg["payload_off"] == "false"
    assert "tojson" in cfg["value_template"]
    assert cfg["device_class"] == "occupancy"


def test_every_entity_carries_availability() -> None:
    """Without this a stopped detector leaves a retained "person: false" behind,
    so a blind camera looks exactly like an empty one."""
    for payload in _discovery(classes=("person", "car")).values():
        cfg = json.loads(payload)
        assert cfg["availability_topic"] == "smarthome/vision/status"
        assert cfg["payload_available"] == "online"
        assert cfg["payload_not_available"] == "offline"


def test_entities_are_grouped_under_one_device_per_camera() -> None:
    cfgs = [json.loads(p) for p in _discovery(classes=("person", "car")).values()]
    devices = {json.dumps(c["device"], sort_keys=True) for c in cfgs}
    assert len(devices) == 1
    device = cfgs[0]["device"]
    assert device["name"] == "Front Door Camera (NPU)"
    assert device["identifiers"] == ["npu_vision_front_door_camera"]


def test_unique_ids_do_not_collide_across_cameras_or_classes() -> None:
    ids = set()
    for camera in ("front_door_camera", "family_room_camera"):
        for payload in _discovery(camera, ("person", "car")).values():
            ids.add(json.loads(payload)["unique_id"])
    assert len(ids) == 8


def test_count_sensor_defaults_to_zero_when_the_class_is_absent() -> None:
    """counts only carries labels actually seen, so the template needs a default
    or the sensor goes unavailable every time nobody is there."""
    cfg = json.loads(
        _discovery()["homeassistant/sensor/npu_vision_front_door_camera/person_count/config"]
    )
    assert "default(0)" in cfg["value_template"]
    assert cfg["state_class"] == "measurement"


def test_stream_names_become_readable_entity_names() -> None:
    from src.python.npu_detector import friendly_name

    assert friendly_name("front_door_camera") == "Front Door Camera"
    assert friendly_name("wyze_camera") == "Wyze Camera"


def test_detector_announces_and_retracts_availability() -> None:
    """The will covers a crash; the explicit offline covers a clean stop."""
    source = (PROJECT_ROOT / "src" / "python" / "npu_detector.py").read_text(encoding="utf-8")
    assert "will_set" in source
    assert 'publish(cfg.availability_topic, "online", retain=True)' in source
    assert 'publish(cfg.availability_topic, "offline", retain=True)' in source


def test_discovery_can_be_turned_off(monkeypatch) -> None:
    monkeypatch.setenv("NPU_DISCOVERY", "0")
    assert Config.from_env().discovery is False
    monkeypatch.setenv("NPU_DISCOVERY", "1")
    assert Config.from_env().discovery is True


def test_entities_are_diagnostic_by_default() -> None:
    """Keeps them off Home Assistant's auto-generated dashboard.

    The category is presentation only - automations and templates still read
    these entities normally.
    """
    for payload in _discovery(classes=("person",)).values():
        assert json.loads(payload)["entity_category"] == "diagnostic"


def test_entity_category_can_be_cleared(monkeypatch) -> None:
    """An empty NPU_ENTITY_CATEGORY puts them back on the main dashboard."""
    from src.python.npu_detector import discovery_messages

    monkeypatch.setenv("NPU_ENTITY_CATEGORY", "")
    assert Config.from_env().entity_category is None

    msgs = dict(discovery_messages(
        "cam", ("person",), "smarthome/vision", "smarthome/vision/status",
        "homeassistant", None,
    ))
    for payload in msgs.values():
        assert "entity_category" not in json.loads(payload)


def test_entity_category_default_survives_an_unset_environment(monkeypatch) -> None:
    monkeypatch.delenv("NPU_ENTITY_CATEGORY", raising=False)
    assert Config.from_env().entity_category == "diagnostic"


# ------------------------------- keeping detections off the dashboard's views

def test_detection_entities_are_not_offered_as_tuya_devices() -> None:
    """Their occupancy device_class otherwise puts them in the Tuya list, and
    because the names contain "camera" the front end renders them as camera
    cards - three phantom cameras reading "Tuya camera stream is not
    configured" on the Cameras view.
    """
    from src.python.web_app import _is_tuya_home_assistant_entity

    detection = {
        "entity_id": "binary_sensor.front_door_camera_npu_person",
        "state": "off",
        "attributes": {
            "friendly_name": "Front Door Camera (NPU) Person",
            "device_class": "occupancy",
        },
    }
    assert _is_tuya_home_assistant_entity(detection) is False


def test_a_real_tuya_occupancy_sensor_is_still_offered() -> None:
    """The filter must be specific to our entities, not to occupancy sensors."""
    from src.python.web_app import _is_tuya_home_assistant_entity

    real = {
        "entity_id": "binary_sensor.hallway_motion_occupancy",
        "state": "off",
        "attributes": {"friendly_name": "Hallway motion", "device_class": "occupancy"},
    }
    assert _is_tuya_home_assistant_entity(real) is True


def test_npu_vision_entities_are_recognised() -> None:
    from src.python.web_app import _is_npu_vision_entity

    assert _is_npu_vision_entity("binary_sensor.front_door_camera_npu_person") is True
    assert _is_npu_vision_entity("sensor.office_camera_npu_person_count") is True
    assert _is_npu_vision_entity("binary_sensor.hallway_motion_occupancy") is False
    assert _is_npu_vision_entity("camera.front_door") is False
    assert _is_npu_vision_entity(None) is False


# ------------------------------------------------- per-camera independent loops

class _FakeFrameSource:
    """Stands in for the held-open RTSP consumer, with no camera in sight."""

    def __init__(self, read):
        self._read = read
        self.closed = False

    def read(self):
        return self._read()

    def close(self):
        self.closed = True

def test_a_slow_camera_does_not_delay_a_fast_one() -> None:
    """The whole point of the change.

    A shared loop made every camera wait for the slowest, so the 0.36s office
    camera updated at the 3s doorbell's pace. Independent threads decouple them.
    """
    import threading
    import time as _time
    from src.python.npu_detector import run_camera
    import src.python.npu_detector as nd

    delays = {"slow": 0.30, "fast": 0.01}

    def fake_source(camera, _rtsp_url, _timeout=8.0):
        return _FakeFrameSource(lambda: (_time.sleep(delays[camera]), object())[1])

    class FakeDetector:
        """Alternates seen/not-seen so every cycle is a state change.

        A detector that never sees anything now publishes nothing at all - the
        presence hold only emits on change - and this test measures loop rate
        through the publish rate.
        """

        def __init__(self) -> None:
            self.n = 0

        def detect(self, _frame, _cfg):
            self.n += 1
            return [Detection("person", 0.9, (0, 0, 1, 1))] if self.n % 2 else []

    published: dict[str, int] = {"slow": 0, "fast": 0}
    lock = threading.Lock()

    def publish(camera, _payload):
        with lock:
            published[camera] += 1

    # presence_hold=0: this is about thread independence, not debouncing, and a
    # hold would swallow the falling edges the count relies on.
    cfg = Config(model=Path("unused"), cameras=["slow", "fast"], interval=0.0,
                 fetch_timeout=1.0, presence_hold=0.0)
    original = nd.FrameSource
    nd.FrameSource = fake_source
    try:
        stop = threading.Event()
        npu_lock = threading.Lock()
        threads = [
            threading.Thread(target=run_camera,
                             args=(c, FakeDetector(), npu_lock, cfg, publish, stop),
                             daemon=True)
            for c in ("slow", "fast")
        ]
        for t in threads:
            t.start()
        _time.sleep(0.9)
        stop.set()
        for t in threads:
            t.join(timeout=3)
    finally:
        nd.FrameSource = original

    # The fast camera must have run many more cycles than the slow one; under a
    # shared loop the two counts would be identical.
    assert published["fast"] > published["slow"] * 3, published


def test_one_camera_failing_does_not_kill_its_thread() -> None:
    """A raising camera must keep being retried, not silently stop being watched."""
    import threading
    import time as _time
    from src.python.npu_detector import run_camera
    import src.python.npu_detector as nd

    calls = {"n": 0}

    def exploding_source(_camera, _rtsp_url, _timeout=8.0):
        def read():
            calls["n"] += 1
            raise RuntimeError("camera on fire")
        return _FakeFrameSource(read)

    cfg = Config(model=Path("unused"), cameras=["boom"], interval=0.0, fetch_timeout=1.0)
    original = nd.FrameSource
    nd.FrameSource = exploding_source
    try:
        stop = threading.Event()
        t = threading.Thread(target=run_camera,
                             args=("boom", None, threading.Lock(), cfg, lambda *a: None, stop),
                             daemon=True)
        t.start()
        _time.sleep(0.3)
        stop.set()
        t.join(timeout=3)
    finally:
        nd.FrameSource = original

    assert calls["n"] > 1, "thread stopped retrying after the first failure"
    assert not t.is_alive()


def test_inference_is_serialised_across_cameras() -> None:
    """One NPU, one session, and an execution provider that corrupts the heap on
    inputs it dislikes - concurrent Run calls are not worth the risk."""
    import threading
    import time as _time
    from src.python.npu_detector import run_camera
    import src.python.npu_detector as nd

    concurrent = {"now": 0, "max": 0}
    guard = threading.Lock()

    class CountingDetector:
        def detect(self, _frame, _cfg):
            with guard:
                concurrent["now"] += 1
                concurrent["max"] = max(concurrent["max"], concurrent["now"])
            _time.sleep(0.02)
            with guard:
                concurrent["now"] -= 1
            return []

    cfg = Config(model=Path("unused"), cameras=list("abcd"), interval=0.0, fetch_timeout=1.0)
    original = nd.FrameSource
    nd.FrameSource = lambda _c, _u, _t=8.0: _FakeFrameSource(object)
    try:
        stop = threading.Event()
        npu_lock = threading.Lock()
        detector = CountingDetector()
        threads = [
            threading.Thread(target=run_camera,
                             args=(c, detector, npu_lock, cfg, lambda *a: None, stop),
                             daemon=True)
            for c in cfg.cameras
        ]
        for t in threads:
            t.start()
        _time.sleep(0.4)
        stop.set()
        for t in threads:
            t.join(timeout=3)
    finally:
        nd.FrameSource = original

    assert concurrent["max"] == 1, f"NPU ran {concurrent['max']} inferences at once"


def test_fetch_timeout_is_configurable(monkeypatch) -> None:
    """A dead camera should be droppable faster than the 8s default."""
    monkeypatch.setenv("NPU_FETCH_TIMEOUT", "2.5")
    assert Config.from_env().fetch_timeout == 2.5
    monkeypatch.delenv("NPU_FETCH_TIMEOUT")
    assert Config.from_env().fetch_timeout == 8.0


# ------------------------------------------------------------- presence hold

def test_first_sight_of_a_person_is_published_immediately() -> None:
    """The edge that must never be delayed. A hold that made you wait to be
    noticed would be worse than the flapping it replaces."""
    from src.python.npu_detector import PresenceHold

    hold = PresenceHold(60.0)

    assert hold.update(1, now=0.0) == 1, "arrival was delayed"
    assert hold.published == 1


def test_a_second_person_joining_is_also_immediate() -> None:
    """A rise is a rise whatever it rises from - someone joining a room that is
    already occupied is exactly the event worth acting on."""
    from src.python.npu_detector import PresenceHold

    hold = PresenceHold(60.0)
    hold.update(1, now=0.0)

    assert hold.update(2, now=5.0) == 2, "the second person was not reported"


def test_a_dropout_shorter_than_the_hold_publishes_nothing() -> None:
    """Measured on the real detector: a person sitting still is seen for a
    median 0.8s and lost for a median 3s. Every one of those was a state change."""
    from src.python.npu_detector import PresenceHold

    hold = PresenceHold(60.0)
    hold.update(1, now=0.0)

    published = [hold.update(0, now=t) for t in (3.0, 6.0, 9.0, 30.0, 59.0)]

    assert published == [None] * 5, "a dropout leaked through the hold"
    assert hold.published == 1


def test_the_room_is_reported_empty_once_the_hold_expires() -> None:
    from src.python.npu_detector import PresenceHold

    hold = PresenceHold(60.0)
    hold.update(1, now=0.0)
    for t in (10.0, 30.0, 59.0):
        hold.update(0, now=t)

    assert hold.update(0, now=61.0) == 0
    assert hold.published == 0


def test_one_of_two_people_leaving_settles_to_one() -> None:
    """The count must come down as well as up, or a room that ever held two
    people reads as two for ever."""
    from src.python.npu_detector import PresenceHold

    hold = PresenceHold(10.0)
    hold.update(2, now=0.0)

    assert hold.update(1, now=2.0) is None, "the drop was believed too eagerly"
    assert hold.update(1, now=11.0) == 1, "the count never came down"
    assert hold.published == 1


def test_a_zero_hold_publishes_every_change() -> None:
    """The escape hatch, and what the old behaviour was."""
    from src.python.npu_detector import PresenceHold

    hold = PresenceHold(0.0)

    assert hold.update(1, now=0.0) == 1
    assert hold.update(0, now=0.5) == 0
    assert hold.update(1, now=1.0) == 1


def test_classes_are_held_independently() -> None:
    """A car in view must not keep `person` alive on its own."""
    from src.python.npu_detector import Detection, _apply_holds, PresenceHold

    holds = {"person": PresenceHold(60.0), "car": PresenceHold(60.0)}
    wanted = ["person", "car"]

    held, changed = _apply_holds(holds, [Detection("person", 0.9, (0, 0, 1, 1))],
                                 wanted, now=0.0)
    assert changed and held == {"person": 1, "car": 0}

    # Only the car is visible now; person must stay held, car must rise at once.
    held, changed = _apply_holds(holds, [Detection("car", 0.9, (0, 0, 1, 1))],
                                 wanted, now=1.0)
    assert changed and held == {"person": 1, "car": 1}


def test_the_payload_reports_held_counts_but_keeps_the_raw_frame() -> None:
    """Automations bind to the held count; tuning needs what the frame actually
    saw, so both are published."""
    import json

    from src.python.npu_detector import Detection, build_payload

    payload = json.loads(build_payload(
        "office", [], ["person"], held={"person": 1}))

    assert payload["person"] is True, "the held state was lost"
    assert payload["counts"] == {"person": 1}
    assert payload["raw_counts"] == {}, "the raw frame was not preserved"


# ------------------------------------------------------- held-open frame source

def test_frames_are_drained_between_inferences() -> None:
    """The reason the loop reads every frame rather than one per interval.

    Frames left in ffmpeg's buffer come back in order, so a loop that reads only
    when it wants to score would hand the model a picture that falls further
    into the past the longer the service runs - a nasty failure, because it goes
    on looking like it works. Reading every frame keeps the stream current.
    """
    import threading
    import time as _time

    import src.python.npu_detector as nd
    from src.python.npu_detector import run_camera

    reads = {"n": 0}
    scored: list[int] = []
    staleness: list[int] = []

    def source(_camera, _rtsp_url, _timeout=8.0):
        def read():
            reads["n"] += 1
            _time.sleep(0.005)
            return reads["n"]          # the frame *is* its sequence number
        return _FakeFrameSource(read)

    class RecordingDetector:
        def detect(self, frame, _cfg):
            scored.append(frame)
            # How many frames had arrived since the one being scored. A loop
            # working off the buffer would show this climbing.
            staleness.append(reads["n"] - frame)
            return []

    cfg = Config(model=Path("unused"), cameras=["cam"], interval=0.10,
                 fetch_timeout=1.0, presence_hold=0.0)
    original = nd.FrameSource
    nd.FrameSource = source
    try:
        stop = threading.Event()
        thread = threading.Thread(
            target=run_camera,
            args=("cam", RecordingDetector(), threading.Lock(), cfg, lambda *a: None, stop),
            daemon=True,
        )
        thread.start()
        _time.sleep(0.45)
        stop.set()
        thread.join(timeout=3)
    finally:
        nd.FrameSource = original

    assert reads["n"] > len(scored) * 2, (
        f"read {reads['n']} frames but scored {len(scored)} - the loop is not draining"
    )
    assert scored == sorted(scored)
    # The model must always see the frame that just arrived, never one pulled
    # out of a backlog - and that must hold for the last inference as firmly as
    # the first, which is exactly what drifts when the buffer is not drained.
    assert staleness == [0] * len(scored), f"scored stale frames: {staleness}"


def test_the_source_is_closed_when_the_loop_stops() -> None:
    """A leaked capture holds an RTSP consumer open against the camera."""
    import threading
    import time as _time

    import src.python.npu_detector as nd
    from src.python.npu_detector import run_camera

    made: list[_FakeFrameSource] = []

    def source(_camera, _rtsp_url, _timeout=8.0):
        made.append(_FakeFrameSource(lambda: object()))
        return made[-1]

    cfg = Config(model=Path("unused"), cameras=["cam"], interval=0.01, fetch_timeout=1.0)
    original = nd.FrameSource
    nd.FrameSource = source
    try:
        stop = threading.Event()
        thread = threading.Thread(
            target=run_camera,
            args=("cam", _NullDetector(), threading.Lock(), cfg, lambda *a: None, stop),
            daemon=True,
        )
        thread.start()
        _time.sleep(0.1)
        stop.set()
        thread.join(timeout=3)
    finally:
        nd.FrameSource = original

    assert made and made[0].closed, "the frame source was left open"


class _NullDetector:
    def detect(self, _frame, _cfg):
        return []


def test_the_rtsp_endpoint_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("GO2RTC_RTSP_URL", "rtsp://10.0.0.5:8554")
    assert Config.from_env().rtsp_url == "rtsp://10.0.0.5:8554"
    monkeypatch.delenv("GO2RTC_RTSP_URL")
    assert Config.from_env().rtsp_url == "rtsp://127.0.0.1:8554"


# --------------------------------------------------- per-camera confidence

def test_a_camera_can_be_made_harder_to_convince() -> None:
    """An outdoor camera at night sees headlights and branches an indoor one
    never does, so one threshold does not fit every view."""
    cfg = Config(model=Path("unused"), cameras=["garage_camera", "office_camera"],
                 conf=0.35, conf_overrides={"garage_camera": 0.55})
    assert cfg.conf_for("garage_camera") == 0.55
    assert cfg.conf_for("office_camera") == 0.35


def test_conf_overrides_parse_from_one_env_string(monkeypatch) -> None:
    monkeypatch.setenv("NPU_CONF_OVERRIDES", "garage_camera=0.55, frontyard_camera=0.5")
    overrides = Config.from_env().conf_overrides
    assert overrides == {"garage_camera": 0.55, "frontyard_camera": 0.5}


def test_a_typo_in_the_overrides_is_dropped_not_fatal(monkeypatch) -> None:
    """This is a tuning knob. A mistake in it must not stop the house watching."""
    monkeypatch.setenv("NPU_CONF_OVERRIDES", "garage_camera=high,frontyard_camera=0.5")
    assert Config.from_env().conf_overrides == {"frontyard_camera": 0.5}


def test_a_camera_says_its_state_once_at_startup() -> None:
    """Publishes are on change, so a newly added camera's entities sat at
    "unknown" in Home Assistant until somebody walked past it - and a condition
    on "unknown" is not false, it is broken."""
    import threading
    import time as _time

    import src.python.npu_detector as nd
    from src.python.npu_detector import run_camera

    published: list[str] = []

    cfg = Config(model=Path("unused"), cameras=["quiet"], interval=0.01,
                 fetch_timeout=1.0, presence_hold=60.0)
    original = nd.FrameSource
    nd.FrameSource = lambda _c, _u, _t=8.0: _FakeFrameSource(object)
    try:
        stop = threading.Event()
        thread = threading.Thread(
            target=run_camera,
            args=("quiet", _NullDetector(), threading.Lock(), cfg,
                  lambda _cam, payload: published.append(payload), stop),
            daemon=True,
        )
        thread.start()
        _time.sleep(0.2)
        stop.set()
        thread.join(timeout=3)
    finally:
        nd.FrameSource = original

    assert published, "an empty camera never said so"
    assert json.loads(published[0])["person"] is False
    # Exactly once: nothing changed after that, and a retained topic republished
    # every cycle would be noise on the broker and churn in the recorder.
    assert len(published) == 1, f"published {len(published)} times without a change"
