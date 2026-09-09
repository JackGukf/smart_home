#!/usr/bin/env python3
"""Score a detection model on the held-out COCO split, with COCO's own metrics.

Takes ``.pt`` or ``.onnx`` and puts both through the *same* inference and decode
path, because the point of this script is comparing models to each other.  A
``.pt`` is exported to ONNX first rather than scored through ultralytics, so
"stock YOLOv8n" and "our INT8 graph" differ only in the graph.

That matters more than usual here.  The previous model's numbers were measured
on a held-out split that lived only on the board and died with it, so they
cannot be reproduced and nothing new can be compared against them.  Every model
in a comparison must be re-scored on the split ``fetch_coco_subset.py``
regenerates from its seed.

Preprocessing and NMS are imported from ``src/python/npu_detector.py`` -- the
deployed code -- so the score reflects the pipeline that will actually run.  The
one deliberate difference is that boxes stay floating point here; the detector
rounds them to integer pixels, which costs a little accuracy but is invisible on
a camera.

INT8 graphs are executed on the CPU provider, so this measures the quantisation,
not the NPU.  Device numbers need the board.

    python3 scripts/npu-model/evaluate.py --model a.onnx --model yolov8n.pt
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.python.npu_detector import (  # noqa: E402  deployed code
    COCO_NAMES, HeadDecoder, head_meta_for, merge_outputs, nms, to_input,
)


def coco_category_ids(ann_file: Path) -> list[int]:
    """Dense YOLO index -> COCO category id (ids run 1..90 with gaps)."""
    data = json.loads(ann_file.read_text())
    return sorted(c["id"] for c in data["categories"])


def decode_for_eval(output: np.ndarray, scale: float, pad_x: int, pad_y: int,
                    shape: tuple[int, int], conf: float, iou: float, max_det: int):
    """Same shape of decode as the detector, but without the integer rounding."""
    pred = output[0].T
    scores = pred[:, 4:].max(axis=1)
    classes = pred[:, 4:].argmax(axis=1)
    keep_mask = scores > conf
    if not keep_mask.any():
        return np.empty((0, 4)), np.empty(0), np.empty(0, dtype=int)
    pred, scores, classes = pred[keep_mask], scores[keep_mask], classes[keep_mask]

    xy, wh = pred[:, :2], pred[:, 2:4]
    boxes = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1)
    keep = nms(boxes, scores, classes, iou, max_det)
    boxes, scores, classes = boxes[keep], scores[keep], classes[keep]

    h, w = shape
    boxes[:, [0, 2]] = np.clip((boxes[:, [0, 2]] - pad_x) / scale, 0, w)
    boxes[:, [1, 3]] = np.clip((boxes[:, [1, 3]] - pad_y) / scale, 0, h)
    return boxes, scores, classes


def as_onnx(model: Path, imgsz: int, tmpdir: Path) -> Path:
    if model.suffix == ".onnx":
        return model
    from ultralytics import YOLO

    print(f"  exporting {model.name} to ONNX for a like-for-like comparison")
    with contextlib.redirect_stdout(io.StringIO()):
        exported = YOLO(str(model)).export(format="onnx", imgsz=imgsz, opset=12,
                                           dynamic=False, simplify=True, nms=False, verbose=False)
    target = tmpdir / f"{model.stem}.onnx"
    target.write_bytes(Path(exported).read_bytes())
    return target


def run_model(model_path: Path, images: list[tuple[int, Path]], cat_ids: list[int],
              imgsz: int, conf: float, iou: float, max_det: int) -> tuple[list[dict], float]:
    import cv2
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    meta = head_meta_for(model_path)
    head = HeadDecoder(meta) if meta and len(session.get_outputs()) > 2 else None

    results: list[dict] = []
    total = 0.0
    for done, (image_id, path) in enumerate(images, 1):
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        blob, scale, pad_x, pad_y = to_input(frame, imgsz)
        started = time.perf_counter()
        output = merge_outputs(session.run(None, {input_name: blob}), head)
        total += time.perf_counter() - started
        boxes, scores, classes = decode_for_eval(output, scale, pad_x, pad_y,
                                                 frame.shape[:2], conf, iou, max_det)
        for (x1, y1, x2, y2), score, cls in zip(boxes, scores, classes):
            results.append({
                "image_id": image_id,
                "category_id": cat_ids[int(cls)],
                "bbox": [round(float(x1), 2), round(float(y1), 2),
                         round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
                "score": round(float(score), 5),
            })
        if done % 200 == 0:
            print(f"    {done}/{len(images)}", flush=True)
    return results, total / max(len(images), 1)


def score(ann_file: Path, image_ids: list[int], detections: list[dict]) -> dict[str, float]:
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    with contextlib.redirect_stdout(io.StringIO()):
        coco = COCO(str(ann_file))
        if not detections:
            return {"mAP50": 0.0, "mAP50-95": 0.0, "person_AP50": 0.0}
        loaded = coco.loadRes(detections)
        evaluator = COCOeval(coco, loaded, "bbox")
        evaluator.params.imgIds = image_ids
        evaluator.evaluate()
        evaluator.accumulate()
        evaluator.summarize()

    # precision is [iou, recall, category, area, maxdets]; index 0 is IoU 0.50
    # and the last maxdets entry is 100, which is what the summary uses.
    precision = evaluator.eval["precision"]
    person_index = list(evaluator.params.catIds).index(1)
    person = precision[0, :, person_index, 0, 2]
    person_ap50 = float(np.mean(person[person > -1])) if (person > -1).any() else 0.0

    return {
        "mAP50-95": float(evaluator.stats[0]),
        "mAP50": float(evaluator.stats[1]),
        "person_AP50": person_ap50,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, action="append", required=True,
                    help="repeatable; .pt or .onnx")
    ap.add_argument("--root", type=Path, default=Path.home() / "npu-training" / "coco")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.001, help="low, as COCO scoring expects")
    ap.add_argument("--iou", type=float, default=0.7)
    ap.add_argument("--max-det", type=int, default=300)
    ap.add_argument("--limit", type=int, default=0, help="score fewer images, for a quick check")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    ann_file = args.root / "annotations" / "instances_val2017.json"
    image_dir = args.root / "images" / "val2017"
    cat_ids = coco_category_ids(ann_file)

    data = json.loads(ann_file.read_text())
    present = {}
    for image in data["images"]:
        path = image_dir / image["file_name"]
        if path.exists():
            present[image["id"]] = path
    images = sorted(present.items())
    if args.limit:
        images = images[: args.limit]
    print(f"scoring on {len(images)} held-out images from {image_dir}\n")

    table: dict[str, dict[str, float]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for model in args.model:
            print(f"{model.name}")
            onnx_path = as_onnx(model, args.imgsz, Path(tmp))
            detections, per_image = run_model(onnx_path, images, cat_ids,
                                              args.imgsz, args.conf, args.iou, args.max_det)
            metrics = score(ann_file, [i for i, _ in images], detections)
            metrics["cpu_s_per_image"] = round(per_image, 4)
            metrics["detections"] = len(detections)
            table[model.name] = metrics
            print(f"  mAP50 {metrics['mAP50']:.4f} | mAP50-95 {metrics['mAP50-95']:.4f} | "
                  f"person AP50 {metrics['person_AP50']:.4f} | {per_image * 1000:.0f} ms/img (CPU)\n")

    print(f"{'model':<44} {'mAP50':>8} {'mAP50-95':>9} {'person':>8}")
    for name, m in table.items():
        print(f"{name:<44} {m['mAP50']:>8.4f} {m['mAP50-95']:>9.4f} {m['person_AP50']:>8.4f}")

    if args.out:
        args.out.write_text(json.dumps({"images": len(images), "results": table}, indent=2))
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
