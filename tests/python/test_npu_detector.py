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
