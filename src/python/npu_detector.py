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
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

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


class HeadDecoder:
    """The YOLOv8 detection head, in numpy, for models whose head was cut off.

    The head is a rounding error of the model's compute - a softmax, an anchor
    add, a stride multiply - and it is where INT8 quantisation goes wrong: a QDQ
    Concat forces its inputs to share one scale, so joining boxes (0-640) with
    scores (0-1), or a box centre with its size, erases the smaller of the two.
    Running it here in float removes the whole class of failure for a few
    milliseconds a frame.

    The constants come from the graph the model was cut from, saved beside it,
    so this cannot drift from the network it decodes.
    """

    def __init__(self, meta_path: Path) -> None:
        meta = np.load(str(meta_path))
        self.anchors = meta["anchors"].astype(np.float32)   # [1, 2, 8400]
        self.strides = meta["strides"].astype(np.float32)   # [1, 8400]
        # DFL weights are the bin centres 0..15; conv shape [1, 16, 1, 1].
        self.bins = meta["dfl"].astype(np.float32).reshape(1, 1, -1, 1)

    def __call__(self, outputs: list[np.ndarray]) -> np.ndarray:
        """Six raw conv outputs -> the [1, 84, 8400] tensor decode() expects."""
        box = np.concatenate([o.reshape(o.shape[0], o.shape[1], -1) for o in outputs[:3]], axis=2)
        cls = np.concatenate([o.reshape(o.shape[0], o.shape[1], -1) for o in outputs[3:]], axis=2)

        # Distribution Focal Loss: each of the four sides is a distribution over
        # 16 bins, and the distance is its expected value.
        batch, _, anchors = box.shape
        dist = box.reshape(batch, 4, -1, anchors)
        dist = dist - dist.max(axis=2, keepdims=True)        # stable softmax
        np.exp(dist, out=dist)
        dist /= dist.sum(axis=2, keepdims=True)
        dist = (dist * self.bins).sum(axis=2)                # [b, 4, 8400]

        left_top, right_bottom = dist[:, :2], dist[:, 2:]
        x1y1 = self.anchors - left_top
        x2y2 = self.anchors + right_bottom
        centre = (x1y1 + x2y2) / 2
        size = x2y2 - x1y1
        boxes = np.concatenate([centre, size], axis=1) * self.strides

        scores = 1.0 / (1.0 + np.exp(-cls))
        return np.concatenate([boxes, scores], axis=1).astype(np.float32)


def head_meta_for(model_path: Path) -> Path | None:
    """The head constants saved next to a model, if it was exported split."""
    candidate = Path(model_path).parent / "prelu_ft_decomp.head.npz"
    return candidate if candidate.is_file() else None


def merge_outputs(outputs: list[np.ndarray], head: "HeadDecoder | None" = None) -> np.ndarray:
    """Turn whatever shape this model emits into the [1, 84, 8400] decode() wants.

    Three forms exist and the board may hold any of them while a model is being
    rolled out: one decoded tensor, boxes and scores separately, or the six raw
    convolution outputs of a model whose head was cut off.
    """
    if len(outputs) == 1:
        return outputs[0]
    if len(outputs) == 2:
        return np.concatenate(outputs, axis=1)
    if head is None:
        raise ValueError(
            f"model has {len(outputs)} outputs, so its head was split off, but the "
            f"head constants (prelu_ft_decomp.head.npz) were not found beside it")
    return head(outputs)


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

def _parse_conf_overrides(raw: str) -> dict[str, float]:
    """"cam_a=0.5,cam_b=0.6" -> {"cam_a": 0.5, "cam_b": 0.6}.

    A bad entry is dropped with a warning rather than taken down the service:
    this is a tuning knob, and a typo in it must not stop the house watching.
    """
    overrides: dict[str, float] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        camera, _, value = chunk.partition("=")
        try:
            overrides[camera.strip()] = float(value)
        except ValueError:
            LOG.warning("NPU_CONF_OVERRIDES: ignoring %r, expected camera=number", chunk)
    return overrides


@dataclass
class Config:
    model: Path
    cameras: list[str]
    go2rtc_url: str = "http://127.0.0.1:1984"
    # go2rtc re-serves every camera over RTSP locally. Reading that, and holding
    # it open, is what makes a frame 130ms old instead of 1.1s - see FrameSource.
    rtsp_url: str = "rtsp://127.0.0.1:8554"
    interval: float = 2.0
    conf: float = 0.35
    # Per-camera confidence, for the ones a single threshold does not suit. An
    # outdoor camera at night sees headlights and branches that an indoor one
    # never does, so it may need to be surer before it says "person".
    conf_overrides: dict[str, float] = field(default_factory=dict)
    iou: float = 0.45
    classes: set[str] = field(default_factory=lambda: {"person"})
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_password: str | None = None
    base_topic: str = "smarthome/vision"
    discovery: bool = True
    discovery_prefix: str = "homeassistant"
    entity_category: str | None = "diagnostic"
    fetch_timeout: float = 8.0
    # Seconds a watched class may go undetected before it is reported gone. A
    # rise is never held; see PresenceHold.
    presence_hold: float = 60.0

    @property
    def availability_topic(self) -> str:
        return f"{self.base_topic}/status"

    def conf_for(self, camera: str) -> float:
        return self.conf_overrides.get(camera, self.conf)

    @classmethod
    def from_env(cls) -> "Config":
        cameras = [c.strip() for c in os.getenv("NPU_CAMERAS", "").split(",") if c.strip()]
        classes = {c.strip() for c in os.getenv("NPU_CLASSES", "person").split(",") if c.strip()}
        return cls(
            model=Path(os.getenv("NPU_MODEL", "/home/orangepi/npu-test/prelu_ft_decomp.int8.onnx")),
            cameras=cameras,
            go2rtc_url=os.getenv("GO2RTC_URL", "http://127.0.0.1:1984"),
            rtsp_url=os.getenv("GO2RTC_RTSP_URL", "rtsp://127.0.0.1:8554"),
            interval=float(os.getenv("NPU_INTERVAL", "2.0")),
            conf=float(os.getenv("NPU_CONF", "0.35")),
            conf_overrides=_parse_conf_overrides(os.getenv("NPU_CONF_OVERRIDES", "")),
            # Seconds a person may go undetected before the room is called
            # empty. 0 disables the hold and publishes every frame, which is
            # what produced 2,289 state changes a day from one camera.
            presence_hold=float(os.getenv("NPU_PRESENCE_HOLD", "60")),
            iou=float(os.getenv("NPU_IOU", "0.45")),
            classes=classes,
            mqtt_host=os.getenv("MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_user=os.getenv("MQTT_USER") or None,
            mqtt_password=os.getenv("MQTT_PASSWORD") or None,
            base_topic=os.getenv("NPU_BASE_TOPIC", "smarthome/vision"),
            discovery=os.getenv("NPU_DISCOVERY", "1").lower() not in {"0", "false", "no"},
            discovery_prefix=os.getenv("NPU_DISCOVERY_PREFIX", "homeassistant"),
            entity_category=os.getenv("NPU_ENTITY_CATEGORY", "diagnostic") or None,
            fetch_timeout=float(os.getenv("NPU_FETCH_TIMEOUT", "8.0")),
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

        # A model exported with its head split off emits six raw tensors and
        # needs the constants saved beside it to make detections of them.
        meta = head_meta_for(model)
        self._head = HeadDecoder(meta) if meta else None
        outputs = len(self.session.get_outputs())
        if outputs > 2 and self._head is None:
            raise RuntimeError(
                f"{model.name} has {outputs} outputs, so its head was split off, but "
                f"prelu_ft_decomp.head.npz is not beside it - detections cannot be decoded"
            )
        LOG.info("NPU session ready in %.1fs (%s, %d output%s%s)",
                 time.time() - started, model.name, outputs, "" if outputs == 1 else "s",
                 ", head decoded here" if self._head else "")

    def detect(self, frame: np.ndarray, cfg: Config) -> list[Detection]:
        blob, scale, pad_x, pad_y = to_input(frame)
        output = merge_outputs(self.session.run(None, {self.input_name: blob}), self._head)
        return decode(output, scale, pad_x, pad_y, frame.shape[:2], cfg.conf, cfg.iou,
                      cfg.classes)


def run_camera(camera: str, detector: "Detector", npu_lock: "threading.Lock", cfg: Config,
               publish: "Callable[[str, str], None]", stop: "threading.Event") -> None:
    """Watch one camera on its own cadence until stop is set.

    One thread per camera rather than a single loop over all of them, so an
    unreachable camera cannot stall the rest while its reconnect backs off.

    The loop consumes every frame the stream delivers and runs the model on a
    schedule - see FrameSource for why reading every frame is what keeps the
    picture current rather than slowly falling behind.

    Inference is serialised behind npu_lock. There is one NPU and one session,
    and this execution provider is not one to take chances with concurrently -
    it corrupts the heap on inputs it dislikes. Serialising costs nothing here:
    64ms per frame is ~15 inferences a second against a handful of cameras
    wanting one every couple of seconds.
    """
    conf = cfg.conf_for(camera)
    LOG.info("%s: watching every %.1fs (presence hold %.0fs, conf %.2f)",
             camera, cfg.interval, cfg.presence_hold, conf)
    # One hold per watched class, per camera: a car appearing must not be able
    # to keep "person" alive, and vice versa.
    holds = {label: PresenceHold(cfg.presence_hold) for label in cfg.classes}
    source = FrameSource(camera, cfg.rtsp_url, cfg.fetch_timeout)
    camera_cfg = replace(cfg, conf=conf)
    last_inference = 0.0
    # Publishes are on change, which leaves a newly added camera's entities
    # "unknown" in Home Assistant until somebody happens to walk past it. Say
    # the state once at startup so a condition on it means something from the
    # first minute rather than the first visitor.
    said_anything = False

    try:
        while not stop.is_set():
            try:
                frame = source.read()
                if frame is None:
                    # Reconnecting. Wait a beat rather than spinning on a camera
                    # that is off, which on a five-camera board is a busy loop
                    # per dead camera.
                    stop.wait(min(cfg.interval, 2.0))
                    continue

                now = time.monotonic()
                if now - last_inference < cfg.interval:
                    continue        # drain: keep the stream current, do not score
                last_inference = now

                with npu_lock:
                    detections = detector.detect(frame, camera_cfg)

                held, changed = _apply_holds(holds, detections, cfg.classes,
                                             time.monotonic())
                if changed or not said_anything:
                    publish(camera, build_payload(camera, detections, cfg.classes, held))
                    said_anything = True
                LOG.debug("%s: %d detection(s)%s  infer %.0fms",
                          camera, len(detections), "" if changed else " (held)",
                          (time.monotonic() - now) * 1000)
            except Exception:
                # One camera failing must not take its thread down and silently
                # stop watching that view for the life of the process.
                LOG.exception("%s: detection cycle failed", camera)
                source.close()
                stop.wait(min(cfg.interval, 2.0))
    finally:
        source.close()
    LOG.info("%s: stopped", camera)


class FrameSource:
    """A camera's video, held open.

    The detector used to ask go2rtc for one JPEG per cycle. That is a fresh
    consumer every time, and go2rtc has to wait for the camera's next keyframe
    before it can answer, so a frame cost 0.6-3.2s on these cameras - measured,
    not guessed. The model needs 64ms. Nearly all the latency was in asking.

    That is fine for "is anyone in the office", and useless for following
    somebody up the drive: at a second a frame they reach the door before the
    picture of them at the gate arrives.

    Holding one RTSP consumer open instead drops it to ~2ms a frame, because the
    frames are already arriving - go2rtc re-serves each camera on :8554, so this
    costs the camera nothing extra. The price is ~15% of one core per camera to
    keep decoding, against twelve cores on this board.

    Read *every* frame, and infer on a schedule. Reading only when the detector
    wants one leaves the rest in ffmpeg's buffer, and read() then returns those
    in order - the picture scored would drift further into the past the longer
    the service ran, which is a nasty way to be wrong: it looks like it works.
    """

    def __init__(self, camera: str, rtsp_url: str, timeout: float = 8.0) -> None:
        self.camera = camera
        self.url = f"{rtsp_url.rstrip('/')}/{camera}"
        self.timeout = timeout
        self._capture: Any = None
        self._opened_at = 0.0

    def _open(self) -> bool:
        import cv2

        if self._capture is not None:
            self._capture.release()
            self._capture = None
        capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not capture.isOpened():
            capture.release()
            LOG.warning("%s: could not open %s", self.camera, self.url)
            return False
        # Advisory - the FFMPEG backend may ignore it. Reading every frame is
        # what actually keeps the buffer empty; this only helps if it is heeded.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture = capture
        self._opened_at = time.monotonic()
        LOG.info("%s: reading %s", self.camera, self.url)
        return True

    def read(self) -> "np.ndarray | None":
        """The next frame, reconnecting if the stream has gone away."""
        if self._capture is None and not self._open():
            return None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            # Cameras drop out - a reboot, a lost Wi-Fi packet on the frontyard
            # camera's weak link. Reopen rather than going quiet for ever.
            LOG.warning("%s: stream ended after %.0fs, reconnecting",
                        self.camera, time.monotonic() - self._opened_at)
            self.close()
            return None
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


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
    entity_category: str | None = "diagnostic",
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
        # "diagnostic" keeps these off Home Assistant's auto-generated dashboard
        # and tucks them under the device instead. Automations and templates can
        # still use them normally - the category only affects presentation.
        # Set NPU_ENTITY_CATEGORY="" to put them back on the main dashboard.
        #
        # Changing this later does NOT take effect by republishing: Home
        # Assistant applies entity_category when it first registers an entity
        # and a later discovery update leaves the registry entry alone. To move
        # existing entities, retract each config topic (publish an empty
        # retained payload to it), let HA drop them, then restart this service
        # to re-register. The unique_ids are stable, so entity_ids survive.
        if entity_category:
            common["entity_category"] = entity_category
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


class PresenceHold:
    """Turn per-frame detections into an enter/leave signal, per camera.

    The detector sees a person for a median of 0.8s and then loses them for a
    median of 3s while they sit perfectly still at a desk. Published raw, that
    was 2,289 state changes a day from one camera - 87% of the motion log across
    two of them, an automation firing 2,357 times, and a digest reporting "2,358
    sightings" of an empty room.

    The rule is asymmetric on purpose:

    * **A rise is published immediately.** First sight of a person, or a second
      person joining one already there, is never delayed and never suppressed.
      That is the edge automations care about and the one that must not be lost.
    * **A fall waits.** The published count is the highest seen in the last
      `hold` seconds, so a dropout has to persist before it is believed.

    So the only thing the hold can ever do is report a room occupied for up to
    `hold` seconds after it emptied. Measured against real gaps, 60s bridges
    94% of dropouts; 10s bridges 74%.
    """

    def __init__(self, hold: float) -> None:
        self.hold = hold
        self.published = 0
        self._seen: list[tuple[float, int]] = []

    def update(self, count: int, now: float) -> int | None:
        """Feed one frame's count. Returns the count to publish, or None."""
        self._seen.append((now, count))
        cutoff = now - self.hold
        self._seen = [(t, c) for t, c in self._seen if t >= cutoff]

        # Highest count still inside the window - what we are prepared to
        # believe. A rise overrides it, because a rise is never held back.
        target = max((c for _, c in self._seen), default=0)
        if count > self.published:
            target = count
        if target == self.published:
            return None
        self.published = target
        return target


def _apply_holds(holds: dict[str, PresenceHold], detections: Sequence[Detection],
                 wanted: Iterable[str], now: float) -> tuple[dict[str, int], bool]:
    """Feed this frame to each class's hold. Returns (held counts, anything changed)."""
    seen: dict[str, int] = {}
    for d in detections:
        seen[d.label] = seen.get(d.label, 0) + 1

    changed = False
    held: dict[str, int] = {}
    for label in wanted:
        hold = holds[label]
        if hold.update(seen.get(label, 0), now) is not None:
            changed = True
        held[label] = hold.published
    return held, changed


def build_payload(camera: str, detections: Sequence[Detection], wanted: Iterable[str],
                  held: dict[str, int] | None = None) -> str:
    """The MQTT payload. `held` is the debounced count Home Assistant sees.

    `detections` stays raw - the boxes and scores of the frame that caused this
    publish - because that is what is useful for tuning and for anything that
    wants to look at the picture. Only the per-class counts and booleans are
    held, and those are what automations bind to.
    """
    counts: dict[str, int] = {}
    for d in detections:
        counts[d.label] = counts.get(d.label, 0) + 1
    reported = counts if held is None else held
    payload = {
        "camera": camera,
        "detections": [d.as_dict() for d in detections],
        "counts": reported,
        "raw_counts": counts,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    # A plain boolean per watched class is what an automation actually binds to.
    for label in wanted:
        payload[label] = reported.get(label, 0) > 0
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
                    cfg.discovery_prefix, cfg.entity_category,
                ):
                    # Retained: Home Assistant reads these when it starts, which
                    # is usually long after this service did.
                    client.publish(topic, payload, retain=True)
                    published += 1
            LOG.info("published %d Home Assistant discovery configs under %s/",
                     published, cfg.discovery_prefix)

    def publish(camera: str, payload: str) -> None:
        if client is not None:
            # Retained: a restarted broker or a newly started Home Assistant
            # should see the last known state rather than nothing.
            client.publish(f"{cfg.base_topic}/{camera}", payload, retain=True)
        else:
            print(payload, flush=True)

    npu_lock = threading.Lock()

    if args.once:
        # Sequential and deterministic: --once is for checking a setup, where
        # interleaved output would be harder to read than it is worth.
        for camera in cfg.cameras:
            frame = grab_frame(cfg.go2rtc_url, camera, cfg.fetch_timeout)
            if frame is None:
                continue
            publish(camera, build_payload(camera, detector.detect(frame, cfg), cfg.classes))
    else:
        stop_event = threading.Event()

        def stop(_signum: int, _frame: Any) -> None:
            stop_event.set()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        LOG.info("watching %d camera(s) on independent %.1fs cycles for %s",
                 len(cfg.cameras), cfg.interval, ", ".join(sorted(cfg.classes)))
        threads = [
            threading.Thread(
                target=run_camera,
                args=(camera, detector, npu_lock, cfg, publish, stop_event),
                name=f"cam-{camera}",
                daemon=True,
            )
            for camera in cfg.cameras
        ]
        for thread in threads:
            thread.start()
        try:
            while not stop_event.wait(1.0):
                pass
        except KeyboardInterrupt:  # pragma: no cover - interactive only
            stop_event.set()
        # Generous: a thread may be inside a fetch that has not timed out yet.
        for thread in threads:
            thread.join(timeout=cfg.fetch_timeout + 5)

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
