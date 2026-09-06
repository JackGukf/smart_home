#!/usr/bin/env python3
"""Finetune a PReLU variant of YOLOv8n for the Zhouyi NPU.

Why this model exists: the NPU's execution provider crashes outright on
``Mul(x, Sigmoid(x))`` -- SiLU -- with ``free(): invalid pointer``, and stock
YOLOv8 uses SiLU in every conv block.  PReLU is not supported either, but unlike
SiLU it rewrites *exactly* into ops that are (see export_rewrite.py), so it is
the activation that can actually reach the device.

Swapping the activation destroys the pretrained accuracy -- mAP50 falls to
0.0014, which is noise -- so the swap is only useful with a finetune after it.

Two things here are load-bearing and easy to get wrong:

1. ``Model.train()`` rebuilds the network from its yaml and then loads weights
   into it, which silently discards an activation swap done beforehand: the
   PReLU parameters simply do not match and are dropped.  So the swapped module
   is handed to the trainer directly, which uses it as-is because
   ``BaseTrainer.setup_model()`` returns early for an ``nn.Module``.

2. The activation is *per layer*, not per channel and not global.  A yaml-level
   ``activation:`` assigns one shared instance to every Conv, giving the whole
   network a single learnable slope.  Per-channel slopes go the other way and
   need a broadcasting ``Mul`` against a (C,1,1) constant on a device whose op
   support is narrow and undocumented.  A scalar slope per Conv keeps the
   rewritten graph to scalar constants, which is the shape most likely to
   survive the NPU compiler.

    python3 scripts/npu-model/train_prelu.py --data ~/npu-training/coco/coco-subset.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch import nn


def swap_silu_for_prelu(module: nn.Module, per_channel: bool = False) -> int:
    """Replace every SiLU with its own PReLU. Returns how many were replaced.

    A fresh instance per site is the point -- sharing one would give the network
    a single slope to learn.
    """
    replaced = 0
    for child in module.modules():
        for name, grandchild in list(child.named_children()):
            if isinstance(grandchild, nn.SiLU):
                width = 1
                if per_channel:
                    conv = getattr(child, "conv", None)
                    width = conv.out_channels if isinstance(conv, nn.Conv2d) else 1
                setattr(child, name, nn.PReLU(num_parameters=width, init=0.25))
                replaced += 1
    return replaced


def count_activations(module: nn.Module) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sub in module.modules():
        if isinstance(sub, (nn.SiLU, nn.PReLU, nn.ReLU)):
            counts[type(sub).__name__] = counts.get(type(sub).__name__, 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True, help="dataset yaml from fetch_coco_subset.py")
    ap.add_argument("--weights", default="yolov8n.pt", help="pretrained weights to start from")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--imgsz", type=int, default=640, help="must match the deployed input size")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--project", type=Path, default=Path.home() / "npu-training" / "runs")
    ap.add_argument("--name", default="prelu")
    ap.add_argument("--fraction", type=float, default=1.0, help="fraction of the train split, for smoke tests")
    ap.add_argument("--per-channel", action="store_true", help="per-channel slopes; harder on the NPU")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-val", action="store_true",
                    help="skip validation; for timing probes only -- best.pt selection needs it")
    args = ap.parse_args()

    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionTrainer

    print(f"loading {args.weights}")
    wrapper = YOLO(args.weights)
    model = wrapper.model
    print(f"  activations before: {count_activations(model)}")

    replaced = swap_silu_for_prelu(model, per_channel=args.per_channel)
    after = count_activations(model)
    print(f"  replaced {replaced} SiLU -> PReLU ({'per-channel' if args.per_channel else 'scalar per layer'})")
    print(f"  activations after:  {after}")
    if after.get("SiLU"):
        raise SystemExit(f"{after['SiLU']} SiLU remain; the NPU cannot run this graph")
    if not replaced:
        raise SystemExit("no SiLU found - wrong architecture?")

    # A fresh PReLU has no pretrained meaning, so let the trainer see it as a
    # normal parameter group. Nothing is frozen: the whole network has to adapt
    # to the new activation, which is why the swap alone scores 0.0014.
    overrides = dict(
        model=args.weights,
        data=str(args.data),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        workers=args.workers,
        project=str(args.project),
        name=args.name,
        exist_ok=True,
        seed=args.seed,
        deterministic=True,
        fraction=args.fraction,
        # CPU training: AMP is a GPU feature and its probe downloads another
        # model to run a check that cannot help here.
        amp=False,
        device="cpu",
        # 16k images at 640px will not fit in RAM as a cache.
        cache=False,
        val=not args.no_val,
        plots=True,
        patience=0,  # no early stop; every epoch writes best.pt, so stopping is a choice
    )

    trainer = DetectionTrainer(overrides=overrides)
    # Assigned after construction: setup_model() keeps an nn.Module as-is, which
    # is what preserves the swap. Going through Model.train() would rebuild from
    # yaml and drop it.
    trainer.model = model
    print(f"\ntraining on {args.data}")
    print(f"  torch threads: {torch.get_num_threads()}")
    trainer.train()

    best = Path(trainer.save_dir) / "weights" / "best.pt"
    print(f"\nbest weights: {best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
