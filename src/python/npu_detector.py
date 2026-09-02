"""Object detection on the Orange Pi 6 Plus NPU, published over MQTT.

Pulls JPEG frames from go2rtc, runs a YOLOv8n-shaped model on the Arm China
Zhouyi NPU, and publishes detections so Home Assistant can act on them. The
point of using the NPU is that it leaves all twelve CPU cores free: the same
model on eight A720 cores runs at 5.4 fps and saturates them, versus 15.6 fps on
the NPU with the CPU ~88% idle.

Three board-specific constraints shape this file:

  * The model must be INT8 QDQ and must not contain SiLU. Feeding the Zhouyi
    execution provider an FP32 graph corrupts the heap, and `Mul(x, Sigmoid(x))`
    crashes its graph compiler outright - which is why the model here is a
    PReLU variant with the PReLU rewritten into Relu/Mul/Sub.

  * The Compass runtime looks for its layer library under `./operator` relative
    to the *current working directory*, so this process must run somewhere that
    resolves. run-npu-detector.sh sets that up.

  * onnxruntime-zhouyi ships as a cp311 wheel, so this runs on its own
    Python 3.11 environment, not the board's 3.12.

Run standalone for a one-shot check:
    python -m src.python.npu_detector --once
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

LOG = logging.getLogger("npu_detector")

# COCO, in the order YOLOv8 emits them.
COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in the source image

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "box": list(self.box),
        }


# --------------------------------------------------------------- preprocessing

def letterbox(image: np.ndarray, size: int = 640) -> tuple[np.ndarray, float, int, int]:
    """Resize preserving aspect ratio onto a grey canvas.

    Returns the canvas plus the scale and padding, which are what map a box in
    model space back onto the source frame. Getting this wrong puts boxes in
    plausible-looking but wrong places, so it is returned rather than recomputed.
    """
    import cv2

    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = cv2.resize(image, (nw, nh))
    return canvas, scale, left, top


def to_input(image: np.ndarray, size: int = 640) -> tuple[np.ndarray, float, int, int]:
    canvas, scale, left, top = letterbox(image, size)
    blob = canvas.astype(np.float32) / 255.0
    return np.transpose(blob, (2, 0, 1))[None, ...], scale, left, top


# -------------------------------------------------------------- postprocessing

def nms(boxes: np.ndarray, scores: np.ndarray, classes: np.ndarray, iou_thr: float,
        max_det: int) -> list[int]:
    keep: list[int] = []
    order = scores.argsort()[::-1]
    while order.size and len(keep) < max_det:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        tl = np.maximum(boxes[i, :2], boxes[rest, :2])
        br = np.minimum(boxes[i, 2:], boxes[rest, 2:])
        inter = np.prod(np.clip(br - tl, 0, None), axis=1)
        area = lambda b: (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1])  # noqa: E731
        iou = inter / (area(boxes[i]) + area(boxes[rest]) - inter + 1e-9)
        # Only suppress within the same class, so a person standing in front of a
        # car does not delete the car.
        order = rest[~((iou > iou_thr) & (classes[rest] == classes[i]))]
    return keep


def decode(output: np.ndarray, scale: float, pad_x: int, pad_y: int,
           frame_shape: tuple[int, int], conf_thr: float, iou_thr: float,
           wanted: set[str] | None, max_det: int = 100) -> list[Detection]:
    """Turn a [1, 84, 8400] YOLOv8 output into detections in source coordinates."""
    pred = output[0].T                                   # [8400, 84]
    scores = pred[:, 4:].max(axis=1)
    classes = pred[:, 4:].argmax(axis=1)
    mask = scores > conf_thr
    if not mask.any():
        return []
    pred, scores, classes = pred[mask], scores[mask], classes[mask]

    xy, wh = pred[:, :2], pred[:, 2:4]
    boxes = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1)

    out: list[Detection] = []
    for i in nms(boxes, scores, classes, iou_thr, max_det):
        label = COCO_NAMES[int(classes[i])] if int(classes[i]) < len(COCO_NAMES) else str(classes[i])
        if wanted and label not in wanted:
            continue
        x1, y1, x2, y2 = boxes[i]
        # Undo the letterbox: remove padding first, then the scale.
        h, w = frame_shape
        bx = (
            int(np.clip((x1 - pad_x) / scale, 0, w - 1)),
            int(np.clip((y1 - pad_y) / scale, 0, h - 1)),
            int(np.clip((x2 - pad_x) / scale, 0, w - 1)),
            int(np.clip((y2 - pad_y) / scale, 0, h - 1)),
        )
        out.append(Detection(label, float(scores[i]), bx))
    return out


# ---------------------------------------------------------------------- runtime

@dataclass
class Config:
    model: Path
    cameras: list[str]
    go2rtc_url: str = "http://127.0.0.1:1984"
    interval: float = 2.0
    conf: float = 0.35
    iou: float = 0.45
    classes: set[str] = field(default_factory=lambda: {"person"})
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_password: str | None = None
    base_topic: str = "smarthome/vision"
    discovery: bool = True
    discovery_prefix: str = "homeassistant"

    @property
    def availability_topic(self) -> str:
        return f"{self.base_topic}/status"

    @classmethod
    def from_env(cls) -> "Config":
        cameras = [c.strip() for c in os.getenv("NPU_CAMERAS", "").split(",") if c.strip()]
        classes = {c.strip() for c in os.getenv("NPU_CLASSES", "person").split(",") if c.strip()}
        return cls(
            model=Path(os.getenv("NPU_MODEL", "/home/orangepi/npu-test/prelu_ft_decomp.int8.onnx")),
            cameras=cameras,
            go2rtc_url=os.getenv("GO2RTC_URL", "http://127.0.0.1:1984"),
            interval=float(os.getenv("NPU_INTERVAL", "2.0")),
            conf=float(os.getenv("NPU_CONF", "0.35")),
            iou=float(os.getenv("NPU_IOU", "0.45")),
            classes=classes,
            mqtt_host=os.getenv("MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_user=os.getenv("MQTT_USER") or None,
            mqtt_password=os.getenv("MQTT_PASSWORD") or None,
            base_topic=os.getenv("NPU_BASE_TOPIC", "smarthome/vision"),
            discovery=os.getenv("NPU_DISCOVERY", "1").lower() not in {"0", "false", "no"},
            discovery_prefix=os.getenv("NPU_DISCOVERY_PREFIX", "homeassistant"),
        )


class Detector:
    """Owns the NPU session. Created once: compiling the graph takes ~14s."""

    def __init__(self, model: Path, strict_npu: bool = True) -> None:
        import onnxruntime as ort

        if "ZhouyiExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError(
                "ZhouyiExecutionProvider is not available. This needs the cp311 "
                "onnxruntime-zhouyi wheel from /usr/share/cix/pypi."
            )
        options = ort.SessionOptions()
        if strict_npu:
            # Without this, ops the NPU cannot take fall back to CPU silently and
            # the service looks like it works while running on the cores it was
            # meant to leave free.
            options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        started = time.time()
        self.session = ort.InferenceSession(
            str(model), options, providers=["ZhouyiExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        LOG.info("NPU session ready in %.1fs (%s)", time.time() - started, model.name)

    def detect(self, frame: np.ndarray, cfg: Config) -> list[Detection]:
        blob, scale, pad_x, pad_y = to_input(frame)
        output = self.session.run(None, {self.input_name: blob})[0]
        return decode(output, scale, pad_x, pad_y, frame.shape[:2], cfg.conf, cfg.iou,
                      cfg.classes)


def grab_frame(go2rtc_url: str, camera: str, timeout: float = 8.0) -> np.ndarray | None:
    import cv2
    import requests

    url = f"{go2rtc_url.rstrip('/')}/api/frame.jpeg"
    try:
        response = requests.get(url, params={"src": camera}, timeout=timeout)
        response.raise_for_status()
    except Exception as error:  # a camera being unreachable is routine
        LOG.warning("%s: frame fetch failed: %s", camera, error)
        return None
    buffer = np.frombuffer(response.content, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        LOG.warning("%s: response was not a decodable JPEG", camera)
    return frame


def friendly_name(stream: str) -> str:
    """go2rtc stream name -> something a person wants to see in Home Assistant."""
    return stream.replace("_", " ").strip().title()


def discovery_messages(
    camera: str,
    classes: Iterable[str],
    base_topic: str,
    availability_topic: str,
    discovery_prefix: str = "homeassistant",
) -> list[tuple[str, str]]:
    """Home Assistant MQTT discovery configs for one camera.

    Each watched class gets a binary_sensor (what an automation triggers on) and
    a count sensor (how many, for conditions like "more than one person").

    Every entity carries the availability topic. Without it a stopped detector
    leaves its last retained "person: false" in place forever, so a blind camera
    is indistinguishable from an empty one - the same silent failure that let the
    Zigbee bridge sit dead for an hour.
    """
    node = f"npu_vision_{camera}"
    device = {
        "identifiers": [node],
        "name": f"{friendly_name(camera)} (NPU)",
        "manufacturer": "smart_home_AI",
        "model": "YOLOv8n on Zhouyi NPU",
    }
    origin = {"name": "npu-detector"}
    state_topic = f"{base_topic}/{camera}"

    messages: list[tuple[str, str]] = []
    for label in sorted(classes):
        slug = label.replace(" ", "_")
        common = {
            "availability_topic": availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device,
            "origin": origin,
            "state_topic": state_topic,
        }
        messages.append((
            f"{discovery_prefix}/binary_sensor/{node}/{slug}/config",
            json.dumps({
                **common,
                "name": friendly_name(label),
                "unique_id": f"{node}_{slug}",
                "object_id": f"{node}_{slug}",
                # "occupancy" rather than "motion": this reports presence in
                # frame, not that something moved.
                "device_class": "occupancy",
                "payload_on": "true",
                "payload_off": "false",
                # tojson keeps the booleans as true/false rather than Python's
                # True/False, which HA would not match.
                "value_template": "{{ value_json." + slug + " | tojson }}",
            }),
        ))
        messages.append((
            f"{discovery_prefix}/sensor/{node}/{slug}_count/config",
            json.dumps({
                **common,
                "name": f"{friendly_name(label)} count",
                "unique_id": f"{node}_{slug}_count",
                "object_id": f"{node}_{slug}_count",
                "state_class": "measurement",
                "value_template": "{{ value_json.counts['" + label + "'] | default(0) }}",
            }),
        ))
    return messages


def build_payload(camera: str, detections: Sequence[Detection], wanted: Iterable[str]) -> str:
    counts: dict[str, int] = {}
    for d in detections:
        counts[d.label] = counts.get(d.label, 0) + 1
    payload = {
        "camera": camera,
        "detections": [d.as_dict() for d in detections],
        "counts": counts,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    # A plain boolean per watched class is what an automation actually binds to.
    for label in wanted:
        payload[label] = counts.get(label, 0) > 0
    return json.dumps(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="one pass over the cameras, then exit")
    parser.add_argument("--no-mqtt", action="store_true", help="print instead of publishing")
    parser.add_argument("--camera", action="append", help="override NPU_CAMERAS")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.getenv("NPU_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = Config.from_env()
    if args.camera:
        cfg.cameras = args.camera
    if not cfg.cameras:
        LOG.error("No cameras configured. Set NPU_CAMERAS to go2rtc stream names.")
        return 2
    if not cfg.model.is_file():
        LOG.error("Model not found: %s", cfg.model)
        return 2

    detector = Detector(cfg.model)

    client = None
    if not args.no_mqtt:
        import paho.mqtt.client as mqtt

        # paho 2.x requires an explicit callback API version and warns loudly
        # without one; 1.x has no such argument. Support both rather than
        # pinning, since the board installs whatever is current.
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        else:  # pragma: no cover - paho 1.x
            client = mqtt.Client()
        if cfg.mqtt_user:
            client.username_pw_set(cfg.mqtt_user, cfg.mqtt_password or "")
        # Registered before connecting so the broker publishes it if this process
        # dies without a clean disconnect - which is the case that matters.
        client.will_set(cfg.availability_topic, "offline", retain=True)
        client.connect(cfg.mqtt_host, cfg.mqtt_port, keepalive=60)
        client.loop_start()
        client.publish(cfg.availability_topic, "online", retain=True)
        LOG.info("publishing to %s/<camera> on %s:%s", cfg.base_topic, cfg.mqtt_host, cfg.mqtt_port)

        if cfg.discovery:
            published = 0
            for camera in cfg.cameras:
                for topic, payload in discovery_messages(
                    camera, cfg.classes, cfg.base_topic, cfg.availability_topic,
                    cfg.discovery_prefix,
                ):
                    # Retained: Home Assistant reads these when it starts, which
                    # is usually long after this service did.
                    client.publish(topic, payload, retain=True)
                    published += 1
            LOG.info("published %d Home Assistant discovery configs under %s/",
                     published, cfg.discovery_prefix)

    running = True

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    LOG.info("watching %s every %.1fs for %s",
             ", ".join(cfg.cameras), cfg.interval, ", ".join(sorted(cfg.classes)))
    while running:
        cycle_started = time.time()
        for camera in cfg.cameras:
            frame = grab_frame(cfg.go2rtc_url, camera)
            if frame is None:
                continue
            started = time.time()
            detections = detector.detect(frame, cfg)
            elapsed = (time.time() - started) * 1000
            payload = build_payload(camera, detections, cfg.classes)
            if client is not None:
                # Retained: a restarted broker or a newly started Home Assistant
                # should see the last known state rather than nothing.
                client.publish(f"{cfg.base_topic}/{camera}", payload, retain=True)
            else:
                print(payload)
            LOG.debug("%s: %d detection(s) in %.0f ms", camera, len(detections), elapsed)
        if args.once:
            break
        slack = cfg.interval - (time.time() - cycle_started)
        if slack > 0:
            time.sleep(slack)

    if client is not None:
        # A clean disconnect suppresses the will, so mark it offline explicitly -
        # otherwise a deliberate stop leaves the entities looking live.
        info = client.publish(cfg.availability_topic, "offline", retain=True)
        try:
            info.wait_for_publish(timeout=5)
        except Exception:  # broker already gone; the will covers it
            pass
        client.loop_stop()
        client.disconnect()
    LOG.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
