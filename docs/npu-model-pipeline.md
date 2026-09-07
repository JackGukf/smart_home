# Rebuilding the NPU detection model

The model `npu-detector.service` runs is not stock YOLOv8n and cannot be
downloaded. It is a PReLU variant, finetuned, decomposed into the handful of ops
the Zhouyi NPU implements, and quantised to INT8. This document is how to
rebuild it.

**It exists because the last one was lost.** The training, export and
quantisation for the original model lived only in `~/npu-test/` on the board;
the 2026-09-03 reflash destroyed them and the backups were config-only. The
scripts here are checked in for that reason — the artefacts are large and
disposable, the pipeline is not.

## Why the model has this shape

Three device facts force every choice, and all three are silent when violated:

- **Stock YOLOv8 cannot run at all.** `Mul(x, Sigmoid(x))` — SiLU — crashes the
  execution provider with `free(): invalid pointer` and then deadlocks every
  thread. Sigmoid alone is fine, `Mul` alone is fine, and `Mul(Sigmoid(a), b)`
  with independent inputs is fine; only the shared source is fatal. YOLOv8 uses
  SiLU in every conv block.
- **PReLU is not supported either**, but unlike SiLU it decomposes *exactly*:
  `PRelu(x, s) == Relu(x) - s * Relu(-x)`. `Neg` is also unsupported, so the
  negation is `Mul(x, -1.0)`. The identity is bit-exact — `export_rewrite.py`
  asserts a difference of `0`, not a tolerance.
- **The device runs INT8 QDQ only.** An FP32 graph does not get rejected; it
  corrupts the heap and hangs.

Swapping SiLU for PReLU without retraining scores **mAP50 0.0014** — noise. The
finetune is not an optimisation, it is what makes the model exist.

## The pipeline

Run on a workstation, not the board. Nothing here needs a GPU, and none of it
should compete with the services running the house.

```bash
python3 -m venv ~/npu-training/.venv
~/npu-training/.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
~/npu-training/.venv/bin/pip install ultralytics onnx onnxruntime onnxslim pycocotools
```

```bash
# 1. data -- downloads only the images it selects, not the 19 GB train2017.zip
python3 scripts/npu-model/fetch_coco_subset.py --train-images 16000 --val-images 1000

# 2. finetune -- swaps 57 SiLU for a PReLU each, then trains
python3 scripts/npu-model/train_prelu.py --data ~/npu-training/coco/coco-subset.yaml \
    --epochs 20 --fraction 0.5

# 3. export and decompose -- verifies the rewrite is bit-exact
python3 scripts/npu-model/export_rewrite.py --weights ~/npu-training/runs/prelu/weights/best.pt

# 4. quantise -- Conv-only INT8 QDQ
python3 scripts/npu-model/quantize.py --model ~/npu-training/export/prelu_ft_decomp.onnx

# 5. score every model through one path, stock included
python3 scripts/npu-model/evaluate.py \
    --model yolov8n.pt \
    --model ~/npu-training/export/prelu_ft_decomp.int8-conv.onnx
```

## Things that will cost you a day

**`Model.train()` silently discards an activation swap.** It rebuilds the
network from its yaml and then loads weights into the rebuilt copy, so PReLU
parameters do not match and are dropped — you get a SiLU model that trains
perfectly well and cannot run on the NPU. `train_prelu.py` hands the swapped
module to the trainer directly, which keeps it because
`BaseTrainer.setup_model()` returns early for an `nn.Module`. Check the export's
op counts: `PRelu: 57` before the rewrite, `0` after.

**A yaml-level `activation:` shares one instance across every Conv**, giving the
whole network a single learnable slope. The swap here builds a fresh scalar
PReLU per layer. Per-channel slopes are the other trap: they need a broadcasting
`Mul` against a `(C,1,1)` constant, on a device whose op support is narrow and
undocumented. Scalar keeps the rewritten graph to scalar constants.

**Calibration must use the deployed preprocessing.** `quantize.py` imports
`to_input` from `src/python/npu_detector.py` rather than reimplementing
letterbox-and-divide-by-255. Calibration ranges describe whatever distribution
you feed the model; a pipeline that drifts mis-scales every tensor and the model
still runs, just worse.

**Do not calibrate on the eval split.** The default calibration source is
`images/train2017`.

**SMT does not help.** Measured on a Ryzen 7 6800H: 16 threads took 656 s
against 566 s for 8 — the same lesson as the board's A720 pinning. Leave torch
at its physical-core default.

## Comparing models

**The previous model's numbers cannot be reproduced.** They were measured on a
held-out split that lived only on the board, so nothing new can be compared
against them, only against models re-scored here. `fetch_coco_subset.py`
regenerates its split from `--seed`, which is the fix; `evaluate.py` puts `.pt`
and `.onnx` through the same inference and decode so the only difference between
two rows is the graph.

Scores come from the CPU provider, so they measure the quantisation, not the
NPU. Device throughput needs the board.

### Measured 2026-09-07 — the rebuilt model

Trained on this workstation (CPU only): 20 epochs over 8,000 COCO images, 12.0 h.
All three rows scored by `evaluate.py` on the same 1,000-image held-out split
(`--seed 0`), through the same inference and decode, so the rows are comparable
to each other.

| Model | mAP50 | mAP50-95 | person AP50 | % of stock mAP50 | % of stock person |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stock YOLOv8n (SiLU) | 0.4468 | 0.3219 | 0.7158 | 100% | 100% |
| PReLU finetuned, FP32, decomposed | 0.3770 | 0.2583 | 0.6716 | 84.4% | 93.8% |
| **PReLU finetuned, INT8, Conv-only** | **0.3223** | 0.2136 | **0.6190** | 72.1% | 86.5% |

**Person AP holds up far better than mean mAP**, which is the whole point for a
camera: 86.5% of stock against 72.1% overall.

Two cautions on reading these:

- **They are lower in absolute terms than published YOLOv8n figures** because
  the decode here is `argmax` over classes — one label per box, matching
  `npu_detector.py` — while ultralytics' own validation is multi-label and
  scores higher. Ultralytics reported mAP50 0.4332 for the same FP32 weights
  that score 0.3770 here. Neither is wrong; this one measures the deployed
  pipeline, and stock is measured the same way, so the comparison holds.
- **Scores come from the CPU provider**, so they measure the quantisation, not
  the device. Throughput on the NPU needs the board.

**Quantisation costs more here than it did before**: -0.0547 mAP50 and -0.0526
person AP50 from FP32, against roughly -0.045 for the lost model. Per-tensor
MinMax calibration is the likely reason. Per-channel weight scales
(`quantize.py --per-channel`) and entropy calibration are the untried levers —
per-channel usually recovers most of a gap like this, but it needs a
broadcasting scale the Zhouyi compiler has not been shown to accept, so it has
to be verified on the device rather than assumed.

### The lost model, for reference only

Measured on its own, unreproducible split:

| Model | mAP50 | mAP50-95 | person AP50 | NPU fps |
| --- | ---: | ---: | ---: | ---: |
| Stock YOLOv8n (SiLU) | 0.5557 | 0.4099 | 0.7619 | cannot run |
| PReLU swap, no finetune | 0.0014 | 0.0005 | 0.0079 | — |
| PReLU finetuned, FP32 | 0.4221 | 0.2920 | 0.6987 | — |
| PReLU finetuned, INT8, Conv-only | 0.3774 | 0.2565 | 0.6804 | 15.7 |
| PReLU finetuned, INT8, all ops | 0.3631 | 0.2280 | 0.6300 | 23.0 |

**Prefer Conv-only.** Person AP is what a camera needs and it holds up far
better; the all-ops variant buys frames the detector does not need, since frames
arrive twice a second.

Relative to stock on its *own* split, the lost model retained 67.9% of mAP50 and
89.3% of person AP50; the rebuilt one retains 72.1% and 86.5%. Slightly better
overall, slightly worse on person — not the clean win more training should have
bought, which points at the quantisation step rather than the finetune.

## Deploying

`npu_detector.py` expects a `[1, 3, 640, 640]` input and a `[1, 84, 8400]`
output, and defaults to `NPU_MODEL=/home/orangepi/npu-test/prelu_ft_decomp.int8.onnx`.
Copy the chosen `.int8-conv.onnx` there, or point `NPU_MODEL` at it.

The detector needs its own Python 3.11 environment on the board —
`onnxruntime_zhouyi` is a cp311 wheel and the board runs 3.12. See
`docs/local-ai.md` and `scripts/install-ai-services.sh`.

## Related

- `docs/local-ai.md` — the services, op support, and the measurements behind all of this
- `src/python/npu_detector.py` — the deployed detector, and the source of the preprocessing
- `tests/python/test_npu_model_pipeline.py` — including the bit-exactness of the rewrite
