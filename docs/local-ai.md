# Local AI on the Orange Pi 6 Plus

Everything the board runs locally: two LLM endpoints on the CPU, and camera
object detection on the Zhouyi NPU. All measured on the board 2026-09-02 —
where a number appears here it was observed, not quoted from a spec sheet.

## What runs

| Service | Scope | Endpoint | What |
| --- | --- | --- | --- |
| `ollama.service` | system | `127.0.0.1:11434` | Qwen3-4B Q4_K_M, Ollama's own API |
| `llama-server.service` | user | `127.0.0.1:8081` | Qwen3-4B **Q4_0**, OpenAI-compatible API |
| `npu-detector.service` | user | → MQTT | YOLOv8n on the NPU, publishes detections |
| `resource-logger.service` | user | → `~/resource-history.log` | memory/thermal history that survives a reboot |

Both LLMs are loopback-only on purpose. Reach them over SSH rather than widening
the bind address:

```bash
ssh -N -L 11434:127.0.0.1:11434 orangepi@<board>   # ollama
ssh -N -L  8081:127.0.0.1:8081  orangepi@<board>   # llama-server
```

Install with `scripts/install-ai-services.sh` (safe to re-run).

### Ollama or llama-server?

They run side by side deliberately. Ollama bundles its own llama.cpp, so
replacing its runner would be undone by the next Ollama update; a separate
service is reversible.

| | Ollama | llama-server |
| --- | --- | --- |
| Prompt processing | 30 t/s | **87 t/s** |
| Idle memory | **~0** (unloads after ~5 min) | 5.0 GiB, always resident |
| First request after idle | slow reload | **instant** |
| API | Ollama-native | OpenAI-compatible |

`scripts/qwen_intent_demo.py` targets Ollama's `/api/chat`. The two APIs have
different request and response shapes, so it is not a drop-in swap.

**Qwen3 is a thinking model.** A small `max_tokens` returns an *empty* reply
because reasoning consumed the budget. Pass
`"chat_template_kwargs": {"enable_thinking": false}` for direct answers.

## CPU: getting the LLM fast

Two settings carry nearly all of it. Benchmarked on Qwen3-4B, 8 threads:

| Build | Quant | prompt t/s | generation t/s |
| --- | --- | ---: | ---: |
| `-mcpu=native` (the default) | Q4_K_M | 16.8 | 11.4 |
| explicit `-march`, KleidiAI off | Q4_K_M | 52.6 | 14.6 |
| explicit `-march`, KleidiAI on | Q4_K_M | 53.0 | 13.3 |
| unpinned, 12 threads | Q4_K_M | 48.1 | 9.3 |
| **explicit `-march`, KleidiAI off** | **Q4_0** | **86.9** | **15.4** |

**`-mcpu=native` is silently broken here.** GCC 13 cannot identify this
heterogeneous A720+A520 CPU, so it compiles happily while emitting *zero* ARM
feature macros — every ggml probe fails and you get a baseline armv8-a binary
with no warning. Verify with:

```bash
echo | gcc -mcpu=native -dM -E - | grep __ARM_FEATURE     # prints nothing
```

Always spell the arch out: `-DGGML_NATIVE=OFF
-DGGML_CPU_ARM_ARCH=armv9-a+i8mm+dotprod+sve+bf16`. See
`scripts/build-llama-server.sh`.

**KleidiAI does not help on this board.** ~1% on prompt processing, and it
consistently *cost* generation throughput. Left off.

**Pin to the big cores.** They are interleaved, and the numbering is not what
CIX's docs assume:

- **A720 (big), 8:** cpu0, cpu1 @2.6GHz · cpu6, cpu7 @2.3 · cpu8, cpu9 @2.2 · cpu10, cpu11 @2.5
- **A520 (little), 4:** cpu2, cpu3, cpu4, cpu5 @1.8GHz

So `taskset -c 0,1,6,7,8,9,10,11 -t 8`. CIX's documented
`0,5,6,7,8,9,10,11` includes a little core and drops a fast one — worth 31% of
generation throughput. Read `midr_el1` per core to confirm (`0x410fd811` = A720,
`0x410fd801` = A520); do not infer it from a shell glob of `cpufreq`, whose
order misleads.

**Generation is memory-bandwidth bound**, not compute bound: 2.2 GiB of weights
at ~15 tok/s is ~33 GB/s. That is why compute flags triple prompt processing but
barely move generation. If 15 tok/s is not enough, the lever is a smaller model.

## NPU: what actually works

The Zhouyi NPU is reachable today through the preinstalled `cix-npu-onnxruntime`
package's **ZhouyiExecutionProvider**. There is **no NPU path for LLMs** — CIX's
own AI Model Hub documents only CPU and GPU for every Qwen variant.

### Four things that are not documented anywhere

1. **INT8 QDQ models only.** An FP32 graph corrupts the heap and hangs.
2. **The Compass runtime resolves its layer library from `./operator` relative
   to the working directory.** Without it: `[ERROR][init:145]Cannot find
   layerlib`, then heap corruption. `run-npu-detector.sh` symlinks it.
3. **`onnxruntime_zhouyi` is a cp311 wheel** and the board runs Python 3.12, so
   the detector has its own 3.11 environment at `~/npu-venv`, created with `uv`
   (no root needed).
4. **A model that runs is not proof it ran on the NPU.** Unsupported nodes fall
   back to CPU silently. Always set
   `session.disable_cpu_ep_fallback = "1"`, which turns fallback into a hard
   error. This reversed an earlier wrong conclusion here.

### Op support, measured with fallback disabled

- **Supported:** ReLU, Sigmoid, Conv, MaxPool, Resize, Split, Concat, Mul, Sub
- **Not supported:** PReLU, LeakyReLU, ReLU6/Clip, ELU, HardSigmoid, Neg

With many unsupported nodes the partition fragments and compilation dies with
`[ERROR][check_graph:241]Connected graph is required!`.

**The blocking bug: `Mul(x, Sigmoid(x))` — SiLU — crashes the execution
provider** with `free(): invalid pointer`, then deadlocks every thread. Sigmoid
alone passes, Mul alone passes, and `Mul(Sigmoid(a), b)` with independent inputs
passes; only the shared-source SiLU pattern fails. That blocks stock YOLOv8 and
YOLOv5, which use SiLU in every conv block.

**PReLU can be rewritten exactly into supported ops** (verified bit-exact,
max abs diff 0.0 across the full graph):

```
PRelu(x, s)  ==  Relu(x) - s * Relu(-x)
```

Negate with `Mul(x, -1.0)`, never `Neg`.

### The detection model

Stock YOLOv8n cannot run (SiLU). The model in use is a PReLU variant finetuned
to recover accuracy, then rewritten to supported ops. Scored on a held-out
1000-image split of COCO val2017 — the stock model was scored on the *same*
images, so these compare to each other but **not** to published COCO numbers:

| Model | mAP50 | mAP50-95 | person AP50 | NPU fps |
| --- | ---: | ---: | ---: | ---: |
| Stock YOLOv8n (SiLU) | 0.5557 | 0.4099 | 0.7619 | cannot run |
| PReLU swap, no finetune | 0.0014 | 0.0005 | 0.0079 | — |
| PReLU finetuned, FP32 | 0.4221 | 0.2920 | 0.6987 | — |
| **PReLU finetuned, INT8, Conv-only quant** | **0.3774** | 0.2565 | **0.6804** | **15.7** |
| PReLU finetuned, INT8, all ops quant | 0.3631 | 0.2280 | 0.6300 | 23.0 |

**Person AP holds up far better than mean mAP** — 89% of stock — which is what
matters for a camera. Prefer the Conv-only variant.

Training was CPU-only (no CUDA): 16 epochs, 4000 images, 640px, ~3.5 h, and the
curve was **still climbing** at the end. A GPU and full COCO would land much
closer to stock. Artifacts live in `/home/orangepi/npu-test/`.

The NPU is worth it for the reason it was chosen: the same model needs 8 A720
cores to reach 5.4 fps, versus 15.6 fps on the NPU with the CPU ~88% idle. Vision
does not compete with the LLM for cores.

## The camera detector

`src/python/npu_detector.py`. Pulls JPEG frames from go2rtc
(`/api/frame.jpeg?src=<stream>`), runs the model, publishes to
`smarthome/vision/<camera>`.

**One thread per camera.** Frame fetch dominates and varies enormously — 0.25s
when go2rtc serves a stream natively, 3–4s when it must spawn ffmpeg for an
`rtsps` source. A shared loop made every camera wait for the slowest. With
independent loops, measured over 30s at `NPU_INTERVAL=0.5`:

```
office_camera        ~0.50s        (was ~4.0s under the shared loop)
family_room_camera   ~0.50s
front_door_camera    ~2.73s        (fetch-bound, drags nothing with it)
NPU load: 4.4 inferences/sec of ~15.6 capacity
```

Inference is serialised behind a lock: one NPU, one session, and an execution
provider that corrupts the heap on inputs it dislikes.

### Configuration, in `.env`

| Variable | Meaning |
| --- | --- |
| `NPU_CAMERAS` | go2rtc **stream** names, comma separated |
| `NPU_CLASSES` | default `person`; e.g. `person,car,dog` |
| `NPU_INTERVAL` | seconds; a floor, not a guarantee |
| `NPU_CONF` / `NPU_IOU` | detection and NMS thresholds |
| `NPU_FETCH_TIMEOUT` | drop a dead camera faster than the 8s default |
| `NPU_DISCOVERY` | `0` disables Home Assistant discovery |
| `NPU_ENTITY_CATEGORY` | `diagnostic` by default; `""` puts entities on the main dashboard |

### Home Assistant entities

Each camera arrives as a device with `binary_sensor.<camera>_npu_person`
(device_class `occupancy`) and `sensor.<camera>_npu_person_count`. Entities go
`unavailable` when the service stops — a last will on
`smarthome/vision/status` — so a blind camera is distinguishable from an empty
one.

Three traps found the hard way:

- **HA derives entity_ids from the device and entity names, not from
  `object_id`.** They are named after the camera, not the `npu_vision_*` node
  id. Grep for `npu`, not `npu_vision`.
- **`entity_category` applies only at first registration.** Republishing the
  discovery config does nothing to an already-registered entity. To change it,
  retract each config topic with an empty retained payload, let HA drop the
  entity, then restart to re-register. `/api/states` does not expose the field —
  check via the websocket `config/entity_registry/list`.
- **An `occupancy` device_class put the detections in the dashboard's *Tuya*
  list**, and the front end's `isTuyaCamera()` matches any name containing
  "camera", so they rendered as phantom camera cards. `_is_npu_vision_entity`
  filters them now. Checking `/api/cameras` alone does **not** tell you what the
  Cameras view renders.

## Using the LLM safely

Keep device control deterministic. `scripts/qwen_intent_demo.py` is the pattern:
schema-constrained output, an explicit device allow-list, `temperature: 0`, and
it deliberately calls nothing.

**Do not put the model in a trigger path.** Detection fires every 0.5s; Qwen
generates at ~13 tok/s, so a decision costs seconds and can be wrong on any
given call — slower *and* less reliable than the rule it would replace.

The valuable shape is **the LLM authors, rules execute**: describe a rule in
English, have Qwen emit an automation config, review it, and let Home Assistant
run it deterministically thereafter.

## Operational notes

**Memory is the binding constraint.** `llama-server` holds ~5.0 GiB for the life
of the process and never releases it. With Ollama idle that leaves ~5.6 GiB
free; if Ollama also loads a model that is another ~3.5 GiB. There is **no swap
configured**, so pressure does not degrade — it hits a wall.

**journald on this image is `Storage=volatile`.** The previous boot's logs are
discarded at reboot, which made a 2026-09-02 hang undiagnosable. `rsyslog` keeps
`/var/log/syslog`, but only root can read it. Worth fixing:

```bash
sudo mkdir -p /var/log/journal
sudo sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

**The hard lockup detector is disabled**, so a hang will not self-recover.
`/dev/watchdog` exists; enabling `RuntimeWatchdogSec=60s` in
`/etc/systemd/system.conf` would let the board reboot itself instead of waiting
for a power cycle.

`resource-logger.service` records memory, load, temperature and the three
largest processes to `~/resource-history.log` every 30s with `BOOT` markers, so
the next unexplained reboot leaves evidence.

**Do not run Wi-Fi and Ethernet on the same subnet.** Both up gives two
addresses but only one connected route, so replies to the Wi-Fi address leave
via Ethernet — asymmetric routing that makes SSH drop constantly. Turn Wi-Fi off
once Ethernet is in (`nmcli radio wifi off`); it also removes a 22 dBm 2.4 GHz
transmitter sitting next to the Zigbee coordinator.

## Related

- `docs/setup-orangepi6.md` — board facts and first-time setup
- `scripts/build-llama-server.sh`, `scripts/install-ai-services.sh`
- `src/python/npu_detector.py`, `tests/python/test_npu_detector.py`
