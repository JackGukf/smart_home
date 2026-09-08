# Handoff: local AI, 2026-09-06 → 08

Written to be picked up cold. The AI work is the point; the dashboard changes at
the end are recorded so nothing looks unexplained, and are already documented in
their own files.

## Board state

Read off `192.168.0.234` on 2026-09-08.

| | |
| --- | --- |
| Uptime | 4 days — **no resets this session** |
| BOOT markers in `~/resource-history.log` | 3, all from the 2026-09-03 rebuild |
| `RuntimeWatchdogUSec` | `0` ✅ |
| Memory | 8.9 GiB available of 15, **no swap** |
| `ollama.service` | **active**, serving `qwen3:4b-house` |
| `npu-detector.service` | **installed, stopped, disabled** — see the blocker |
| `llama-server.service` | not installed, deferred |

Everything the house runs — dashboard, go2rtc, Home Assistant, Zigbee, Matter
bridge, resource-logger — stayed up throughout.

## Step 1 — Ollama: done

`scripts/install-ollama.sh` (safe to re-run). Loopback only on `11434`.

- **15.6 tok/s** generation, **66 tok/s** prompt
- Idle unload verified: the cgroup falls **3.30 GiB → 0.05 GiB** and the board's
  available memory returns. That property, not speed, is why Ollama went first.
- Guards read back from systemd, not from the file: `MemoryMax=5G`,
  `OOMPolicy=stop`, `CPUAffinity=0-1 6-11`, loopback bind.

**Two traps, both in `docs/local-ai.md`.** Pinning the cgroup without also
setting `num_thread` makes it burn 720% CPU and emit *nothing* — no error, no
timeout. There is no `OLLAMA_NUM_THREADS`, so the count is baked into
`qwen3:4b-house` and the unpinned `qwen3:4b` tag is deleted so nothing can reach
the stall. And Ollama needs the *opposite* thinking handling from llama-server:
leave thinking on and give a generous `num_predict`; `"think": false` returns the
reasoning **as** the answer on a free-form call.

## Step 2 — the NPU detector: blocked, and this is the interesting part

The model was rebuilt from scratch (the 2026-09-03 reflash destroyed the
original and the backups never held it). Pipeline is checked in this time:
`scripts/npu-model/`, described in `docs/npu-model-pipeline.md`.

Trained on the workstation, CPU only — **that machine has no usable GPU**
(Ryzen 7 6800H, Radeon iGPU, no CUDA, no ROCm). 20 epochs over 8,000 COCO
images, 11.9 h. Scored on a regenerable 1,000-image held-out split:

| Model | mAP50 | mAP50-95 | person AP50 |
| --- | ---: | ---: | ---: |
| Stock YOLOv8n | 0.4468 | 0.3219 | 0.7158 |
| PReLU finetuned, FP32, decomposed | 0.3770 | 0.2583 | 0.6716 |
| **PReLU finetuned, INT8 Conv-only** | **0.3223** | 0.2136 | **0.6190** |

### The blocker

**The graph runs on the NPU at full speed and computes the wrong answer.**

`verify_on_npu.py` creates the session with `disable_cpu_ep_fallback=1`, so a
graph that cannot sit wholly on the device fails hard. Conv-only passes that and
runs at **15.9 fps** — almost exactly the 15.7 fps recorded for the lost model —
while returning saturated class scores (284 values at 1.0 against 0 on the CPU),
box coordinates hundreds of pixels out, and, on a real office frame, 100
detections at confidence 1.00 of zebra, parking meter and surfboard.

So `disable_cpu_ep_fallback` proves **where** a graph ran and says nothing about
**what it computed**. That distinction had not been drawn here before, and it is
why `verify_on_npu.py --compare-cpu` and `probe_npu_ops.py` now exist.

### What is and is not at fault

The model is fine. Same model, same frame, on the board's **own CPU provider**:

| Variant | CPU score max | CPU detections |
| --- | ---: | --- |
| Conv-only | 0.2559 | 2 weak — plausible for an empty office |
| all-ops | **0.0000** | 0 |

Conv-only is correct on two independent runtimes (the workstation's ORT 1.23 and
the board's ORT 1.20) and wrong only on the Zhouyi provider. All-ops is a
*separate* fault: dead on the CPU too, so its quantisation is broken upstream of
the device — per-tensor MinMax across the detection head (Softmax, Div, Sigmoid)
destroys the score range.

**Cause: Conv-only quantisation is partly FP32.** It quantises the convolutions
and leaves the PReLU decomposition's `Relu`/`Mul`/`Sub` in float, and this device
cannot do FP32. Probing confirmed it, and is itself a warning:

```
relu     placed on NPU, max abs diff 0.000975 vs CPU   (not exact)
sigmoid  ZHOUYI graph execute error. Error code: 81
         [ERROR][aipu_finish_job_umd:113][UMD].Timeout on polling job's status
```

**Do not probe this device with FP32 graphs.** It errors and times out the job
queue. Recoverable — the NPU worked again immediately and the board never reset
— but nothing useful is learned.

### Ruled out, by test rather than argument

- **ORT version mismatch.** The board's ORT 1.20 CPU provider runs the
  1.23-produced QDQ graph correctly, so the graph is not the problem.
- **Asymmetric quantisation.** Rebuilt with `--symmetric` (int8 activations,
  zero-point 0). Still garbage: 1187 saturated values, worst diff 747.7.

### Where to start next session

All-ops is the only variant whose NPU output tracked the CPU — box coordinate
maxima matched exactly — because it has no float sections. **It is also twice as
fast: 32.9 fps against 15.9.** So the path is to make all-ops *correct*, not to
keep pushing Conv-only:

1. Re-quantise all-ops with the detection head handled properly — entropy or
   percentile calibration, and per-channel weights — until it scores sanely
   **on the CPU**. `scripts/npu-model/quantize.py --all-ops` is where that lives;
   it currently uses per-tensor MinMax.
2. Score it with `scripts/npu-model/evaluate.py` before going near the board.
3. Re-verify on the device, and do not trust a mAP measured off it:

   ```bash
   cd ~/smart_home_AI/deploy/npu
   PYTHONPATH=~/smart_home_AI ~/npu-venv/bin/python \
     ~/smart_home_AI/scripts/npu-model/verify_on_npu.py \
     --model <path> --compare-cpu --frame-from office_camera
   ```
4. Only then `systemctl --user enable --now npu-detector`.

### One claim in the old docs is now in doubt

The lost model's table lists Conv-only at 15.7 fps and mAP50 0.3774. Ours
reproduces the speed almost exactly and is garbage on the device. Those accuracy
figures were almost certainly CPU-measured, as ours were, and there is no record
of that model's *output* ever being checked on the NPU. Treat "Conv-only worked
on the device" as unverified.

### Where the artefacts are

| | |
| --- | --- |
| Workstation venv | `~/npu-training/.venv` (Python 3.10, torch CPU, ultralytics) |
| ORT 1.20 venv | `~/npu-training/.venv-q120`, for matching the board's runtime |
| COCO subset | `~/npu-training/coco` (3.8 GB, regenerate with `--seed 0`) |
| Trained weights | `~/npu-training/runs/prelu/weights/best.pt` (6.3 MB) |
| Exports | `~/npu-training/export/*.onnx` |
| On the board | `/home/orangepi/npu-test/prelu_ft_decomp.int8-{conv,conv-sym,all}.onnx` |
| Detector env | `~/npu-venv` on the board (Python 3.11 — the wheel is cp311) |

## Step 3 — llama-server: still deferred

**Run one LLM, not both.** 5.0 GiB held permanently plus 3.5 GiB loaded leaves
~0.4 GiB for the house services on a board with no swap.
`scripts/install-ollama.sh` refuses to start beside a live `llama-server`.

## Using the LLM

`scripts/author_automation.py` is the "LLM authors, rules execute" shape, built
and working: describe a rule in English, it drafts a Home Assistant automation,
checks every entity and service against the real house, and writes a **proposal
file** — `automations.yaml` is never touched.

Its ceiling is documented honestly in `docs/local-ai.md`: simple single-clause
requests come out right in about ten seconds; compound ones drop clauses. One
case — `numeric_state` thresholds — it would not fix even after two repair
attempts, so the review hints are the backstop.

## Dashboard work this session

Committed and documented in their own files; listed so nothing looks unexplained.

- **Motion group** under Devices, plus a motion log with its own always-on
  Home Assistant subscription (`/api/events/stream` is per-browser and coalesced,
  so it cannot back a log). The log is JSONL on disk, 14-day retention.
- **Security card** on Home (renamed from Alarm), built-in so it reaches every
  device, showing a server-side choice of sensors defaulting to doors, fire and
  water. Fire, water, gas and CO are now alarm zones at all — they were not.
- **Media view** for the Bluetooth/Music panel.
- **Matter naming**: nodes are named from what they announce, and our own bridge
  is marked as a bridge instead of appearing as a light to switch on.
- **Stale Tuya devices** disabled after the Zigbee migration
  (`scripts/disable-orphan-ha-devices.py`); the front-door template stopgap
  removed. Both recorded in `docs/restore-runbook.md`.

**`WATER SENSOR` and `Temperature and humidity sensor` are not orphans** — flat
batteries, deliberately kept. Do not disable them.

## Open items

- The NPU blocker above.
- Two NPU model variants on the board are known-bad and can be deleted once a
  working one exists.
- The three NPU person entities in Home Assistant stay `unavailable` until the
  detector runs; the dashboard already filters them out of its own views.
- `scripts/list-tuya-cloud-devices.py` cannot enumerate the account —
  `TUYA_USERNAME`, `TUYA_PASSWORD`, `TUYA_COUNTRY_CODE` and `TUYA_APP_TYPE` are
  unset, so it returns `[]` and that empty result means nothing.
- Everything from `docs/handoff-2026-09-03-recovery.md` that was still open:
  the NVMe in a native slot, the default password, weak Wi-Fi.

## Related

- `docs/local-ai.md` — the services, the traps, the measurements
- `docs/npu-model-pipeline.md` — rebuilding the detection model, and the device findings
- `docs/handoff-2026-09-03-recovery.md` — the reset incident and the rebuild
- `docs/restore-runbook.md` — rebuilding the stack from backup
