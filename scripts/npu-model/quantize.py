#!/usr/bin/env python3
"""Quantise the decomposed model to INT8 QDQ for the Zhouyi NPU.

The NPU runs INT8 QDQ models only.  Handing it an FP32 graph does not raise --
it corrupts the heap and hangs, which is a much worse failure than a rejection.

Two choices here are deliberate:

* **Conv-only by default.**  Quantising every op is faster on the device (23.0
  vs 15.7 fps measured) but costs real accuracy, and person AP is the number
  that matters for a camera: 0.6804 Conv-only against 0.6300 all-ops on the
  previous model.  Frames arrive twice a second; accuracy is the scarcer
  resource.
* **Calibration uses the detector's own preprocessing**, imported from
  ``src/python/npu_detector.py`` rather than reimplemented.  Calibration ranges
  describe the activations produced by a particular input distribution, so a
  calibration pipeline that drifts from the deployed one quietly mis-scales
  every tensor.  Importing it makes drift impossible.

    python3 scripts/npu-model/quantize.py --model ~/npu-training/export/prelu_ft_decomp.onnx
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


class ImageCalibrationReader:
    """Feeds real frames through the deployed preprocessing, once each."""

    def __init__(self, images: list[Path], input_name: str, imgsz: int) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        from src.python.npu_detector import to_input  # deployed preprocessing

        self._to_input = to_input
        self._images = images
        self._input_name = input_name
        self._imgsz = imgsz
        self._index = 0

    def get_next(self) -> dict[str, np.ndarray] | None:
        import cv2

        while self._index < len(self._images):
            path = self._images[self._index]
            self._index += 1
            frame = cv2.imread(str(path))
            if frame is None:
                continue  # a truncated JPEG should not abort a 300-image pass
            if self._index % 50 == 0:
                print(f"    calibrated on {self._index}/{len(self._images)}", flush=True)
            blob, _, _, _ = self._to_input(frame, self._imgsz)
            return {self._input_name: blob}
        return None

    def rewind(self) -> None:
        self._index = 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, required=True, help="decomposed FP32 onnx")
    ap.add_argument("--calib-dir", type=Path, default=Path.home() / "npu-training" / "coco" / "images" / "train2017",
                    help="calibration images -- must NOT be the eval split")
    ap.add_argument("--calib-count", type=int, default=300)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--all-ops", action="store_true", help="quantise everything, not just Conv")
    ap.add_argument("--per-channel", action="store_true",
                    help="per-channel weight scales; narrower device support")
    ap.add_argument("--symmetric", action="store_true",
                    help="symmetric int8 activations with zero_point 0. ORT defaults to "
                         "asymmetric uint8, which the Zhouyi provider appears to mishandle: "
                         "the graph runs on the NPU and produces saturated scores and "
                         "box coordinates hundreds of pixels out")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import onnxruntime as ort
    from onnxruntime.quantization import CalibrationMethod, QuantFormat, QuantType, quantize_static
    from onnxruntime.quantization.shape_inference import quant_pre_process

    suffix = "all" if args.all_ops else "conv"
    if args.symmetric:
        suffix += "-sym"
    out = args.out or args.model.with_name(f"{args.model.stem}.int8-{suffix}.onnx")

    images = sorted(p for p in args.calib_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not images:
        print(f"no calibration images in {args.calib_dir}", file=sys.stderr)
        return 1
    images = random.Random(args.seed).sample(images, min(args.calib_count, len(images)))
    print(f"calibrating on {len(images)} images from {args.calib_dir}")

    # Shape inference first: quantize_static needs known shapes, and without this
    # it fails in ways that point at the wrong thing.
    prepped = args.model.with_name(f"{args.model.stem}.prepped.onnx")
    quant_pre_process(str(args.model), str(prepped), skip_symbolic_shape=False)

    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    input_name = ort.InferenceSession(str(prepped), opts, providers=["CPUExecutionProvider"]).get_inputs()[0].name

    reader = ImageCalibrationReader(images, input_name, args.imgsz)
    op_types = None if args.all_ops else ["Conv"]
    print(f"quantising ({'all ops' if args.all_ops else 'Conv only'}, "
          f"{'per-channel' if args.per_channel else 'per-tensor'})")

    # Symmetric puts zero_point at 0 for both activations and weights, which is
    # what a device that assumes symmetric quantisation needs. Asymmetric uint8
    # activations are ORT's default and score well on the CPU provider, so this
    # difference is invisible until the model reaches the board.
    extra: dict[str, bool] = {}
    if args.symmetric:
        extra = {"ActivationSymmetric": True, "WeightSymmetric": True}

    quantize_static(
        model_input=str(prepped),
        model_output=str(out),
        calibration_data_reader=reader,
        quant_format=QuantFormat.QDQ,
        op_types_to_quantize=op_types,
        per_channel=args.per_channel,
        activation_type=QuantType.QInt8 if args.symmetric else QuantType.QUInt8,
        weight_type=QuantType.QInt8,
        calibrate_method=CalibrationMethod.MinMax,
        extra_options=extra or None,
    )
    prepped.unlink(missing_ok=True)

    import onnx

    counts: dict[str, int] = {}
    for node in onnx.load(str(out)).graph.node:
        counts[node.op_type] = counts.get(node.op_type, 0) + 1
    print(f"\nwrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"  ops: {dict(sorted(counts.items()))}")
    if "QuantizeLinear" not in counts:
        print("  ! no QuantizeLinear nodes - this is not a QDQ model and the NPU will hang on it")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
