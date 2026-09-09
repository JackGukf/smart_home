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

## Why `--all-ops` produced a model that detects nothing

This was the blocker from 2026-09-08, and the explanation in the handoff -
"per-tensor MinMax across the detection head destroys the score range" - is
**wrong**. Five quantisation configurations were tried and all five scored
mAP50 **0.0000** on the CPU:

| Variant | mAP50 |
| --- | ---: |
| MinMax, per-tensor (the original) | 0.0000 |
| Percentile, per-channel | 0.0000 |
| Percentile, symmetric int8 | 0.0000 |
| Percentile, excluding Softmax/Div/Sigmoid | 0.0000 |
| Percentile, excluding Mul/Sub | 0.0000 |
| Conv-only (for comparison) | **0.3482** |

Calibration was never the problem. Comparing the FP32 and INT8 outputs on one
image says exactly what is:

```
FP32 reference    boxes max 637.15   scores max 0.9230
Conv-only         boxes max 637.69   scores max 0.9485
every --all-ops   boxes max ~637     scores max 0.0000
```

The boxes are perfect and the scores are *exactly* zero. YOLOv8's head ends by
concatenating box coordinates with class scores into one `[1, 84, 8400]`
tensor, and **a QDQ `Concat` gives all of its inputs one shared scale**. Boxes
run to ~640 pixels and scores are probabilities in `[0, 1]`, so the shared scale
is set by the boxes: one INT8 step is ~2.5, and every class score in the model
rounds to zero. Excluding `Concat` alone restores them - 0.8203 against a 0.9230
reference.

**The general rule, which is not written down anywhere else:** under QDQ, a
`Concat` of tensors with different dynamic ranges destroys the smaller one. Look
for them before blaming the calibrator.

### The fix, and what is still broken

Excluding `Concat` from quantisation fixes the numbers but leaves float ops in
the graph, and this device cannot run those. So `export_rewrite.py` **removes
the head's final Concat entirely** (`--no-split-head` keeps it, only useful for
reproducing the failure): the model gets two outputs, boxes and scores, and
`merge_outputs()` in `src/python/npu_detector.py` rejoins them in numpy, which
costs nothing because concatenation is a memory copy.

That model is the first all-INT8 graph that both works and runs wholly on the
device:

| | |
| --- | --- |
| CPU accuracy | mAP50 **0.3466**, person AP50 0.5663 (Conv-only: 0.3482 / 0.6279) |
| On the NPU | **33.0 fps** with `disable_cpu_ep_fallback` set - twice Conv-only's 15.9 |
| Class scores | no longer saturated: **0** values at 1.0, against 284 before |
| On a real office frame | chair, book, tv, microwave - plausible, where it used to say zebra and parking meter at confidence 1.00 |

**Still wrong: the boxes.** Every detection comes back with zero height, and the
cause is the same one a level deeper. `/model.22/Concat_2` joins the box centre
(`Div_1`, grid units up to ~80) with its size (`Sub_1`, typically under 20)
before the stride multiply - different ranges, one scale, and the size collapses.

The next step is to cut the graph before the whole `dist2bbox` head rather than
at one Concat: quantise the backbone and neck, output the raw distance and class
tensors, and do the DFL softmax, `dist2bbox` and stride multiply in numpy. That
removes every range-mixing Concat and the `Softmax`/`Div` from the quantised
graph at once, and the arithmetic it moves to the CPU is trivial next to the
convolutions.

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

## Verified on the device, 2026-09-07 — and it does not work yet

The model was deployed to the board and checked on the NPU. **Placement and
speed are fine; the numbers it computes are not.** This section is the evidence,
because it overturns an assumption the rest of this document was written under.

### Placement is not correctness

`verify_on_npu.py` creates the session with
`session.disable_cpu_ep_fallback=1`, so a graph that cannot be placed entirely
on the NPU fails hard. Both variants pass that test and run at full speed:

| Variant | Compile | NPU speed | Verdict |
| --- | ---: | ---: | --- |
| INT8 Conv-only | 18.1 s | 15.9 fps | placed, **computes garbage** |
| INT8 all-ops | 6.7 s | 32.9 fps | placed, agrees with CPU, but the model itself is dead |

So the device will happily run a graph at the documented speed and return
numbers unrelated to the model. `disable_cpu_ep_fallback` proves *where* the
graph ran and says nothing about *what it computed* — a distinction this project
had not previously drawn, and the reason `verify_on_npu.py --compare-cpu` and
`probe_npu_ops.py` exist.

Conv-only on the NPU, same input as the CPU provider:

```
class scores  NPU max 0.9995  mean 0.0034  | 284 values saturated at 1.0
class scores  CPU max 0.1085  mean 0.0000  |   0 saturated
box coords    NPU max 874.0              | CPU max 643.2
worst abs diff over 3 inputs: 626.5
```

On a real office frame it returned 100 detections at confidence 1.00 — zebra,
parking meter, surfboard, bed. Those reached MQTT and Home Assistant as person
detections before the service was stopped.

### The model is fine; the device is computing it wrong

Worth isolating carefully, because "the model is bad" and "the device is bad"
lead to completely different work. Same model, same frame, **the board's own CPU
provider**:

| Variant | CPU score max | CPU detections |
| --- | ---: | --- |
| Conv-only | 0.2559 | 2 weak (vase 0.26, tv 0.25) — plausible for an empty office |
| all-ops | **0.0000** | 0 |

Conv-only is correct on two independent CPU runtimes (the workstation's ORT
1.23 and the board's ORT 1.20) and wrong only on the Zhouyi provider. This also
eliminates the obvious version explanation: the board's ORT 1.20 reads the
1.23-produced QDQ graph correctly, so the graph is not the problem.

All-ops is a *separate* fault — dead on the CPU too, so its quantisation is
broken upstream of the device. Per-tensor MinMax across the detection head
(Softmax, Div, Sigmoid) destroys the score range.

### Why: Conv-only leaves FP32 in the graph, and this device cannot do FP32

`docs/local-ai.md` already says INT8 QDQ only, and that an FP32 graph corrupts
the heap rather than being rejected. What was not obvious is that **Conv-only
quantisation is partly FP32** — it quantises the convolutions and leaves the
PReLU decomposition's `Relu`/`Mul`/`Sub` in float. Those float sections are what
the NPU miscomputes.

Confirmed by probing FP32 micro-graphs, which is also a warning not to:

```
relu     placed on NPU, max abs diff 0.000975 vs CPU   (not exact)
sigmoid  ZHOUYI graph execute error. Error code: 81
         [ERROR][aipu_finish_job_umd:113][UMD].Timeout on polling job's status
```

So do not probe this device with FP32 graphs. It errors and times out the job
queue. It is recoverable — the NPU worked again immediately afterwards, and the
board never reset — but nothing useful is learned.

The all-ops variant, having no float sections, is the only one whose NPU output
tracked the CPU. **That is the shape the device can compute**, which makes fixing
all-ops quantisation the path forward rather than Conv-only.

### One claim in this document is now in doubt

The lost model's table lists Conv-only at 15.7 fps and mAP50 0.3774. Our
Conv-only reproduces the speed almost exactly (15.9 fps) and is garbage on the
device. The accuracy figures were almost certainly measured on the CPU, as ours
were, and there is no record of the old model's *output* ever being verified on
the NPU. Treat "Conv-only worked on the device" as unverified rather than
established.

### Next steps

1. Re-quantise all-ops with the detection head handled properly — entropy or
   percentile calibration, and per-channel weights — until it scores sanely on
   the CPU. It already agrees with the NPU, so a correct all-ops model is
   probably a working model.
2. Re-verify with `verify_on_npu.py --compare-cpu --frame-from <camera>` before
   enabling the service. Do not trust a mAP number measured off-device.
3. `npu-detector.service` is installed but **stopped and disabled**, and the
   retained `smarthome/vision/*` topics were cleared, so Home Assistant shows
   the entities unavailable rather than falsely occupied.

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
