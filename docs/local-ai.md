# Local AI on the Orange Pi 6 Plus

Everything the board runs locally: two LLM endpoints on the CPU, and camera
object detection on the Zhouyi NPU. All measured on the board 2026-09-02 —
where a number appears here it was observed, not quoted from a spec sheet.

## Where this stands (2026-09-06)

The 2026-09-03 rebuild restored the house services but not the AI stack, and the
old NVMe was reflashed, so **every AI artifact on the board was lost** — the
tuned llama.cpp build, the GGUF weights, `~/npu-venv`, and `~/npu-test/` with the
finetuned PReLU YOLOv8n and its INT8 quant. The backups are config-only and
never contained them. Anything below that describes a model file describes
something that has to be rebuilt, not restored.

The restore is staged one service at a time, with a soak between each, so an
unexpected reset points at a single change rather than three:

| Step | Service | State |
| --- | --- | --- |
| 1 | `ollama.service` | **installed 2026-09-06**, idle-unload verified, soaking |
| 2 | `npu-detector.service` | **installed, stopped** — model trained and on the board, but the NPU
        miscomputes it. Start at `docs/handoff-2026-09-08-local-ai.md` |
| 3 | `llama-server.service` | deferred; only on evidence that something needs the latency |

**Run one LLM, not both.** `llama-server` holds ~5.0 GiB for the life of the
process and Ollama loading a model is ~3.5 GiB more. Together they leave roughly
0.4 GiB for Home Assistant, Zigbee2MQTT, go2rtc, matter-server and the dashboard
on a board with **no swap**, where pressure does not degrade — it hits a wall and
the kernel kills whichever process asks for memory next. `install-ollama.sh`
refuses to start beside a running `llama-server` for that reason.

Ollama goes first despite being the slower of the two because it **unloads an
idle model and gives the memory back**, which outranks throughput on a box whose
day job is running the house. Measured on the rebuilt board, going idle
after a request: the service cgroup falls from **3.30 GiB to 0.05 GiB** and the
board's available memory rises from 5543 MiB to 8895 MiB. It really does hand
back all of it, which is the whole basis for choosing it.

## What runs

| Service | Scope | Endpoint | What |
| --- | --- | --- | --- |
| `ollama.service` | system | `127.0.0.1:11434` | `qwen3:4b-house` (Qwen3-4B Q4_K_M), Ollama's own API |
| `llama-server.service` | user | `127.0.0.1:8081` | Qwen3-4B **Q4_0**, OpenAI-compatible API |
| `npu-detector.service` | user | → MQTT | YOLOv8n on the NPU, publishes detections |
| `resource-logger.service` | user | → `~/resource-history.log` | memory/thermal history that survives a reboot |

Both LLMs are loopback-only on purpose. Reach them over SSH rather than widening
the bind address:

```bash
ssh -N -L 11434:127.0.0.1:11434 orangepi@<board>   # ollama
ssh -N -L  8081:127.0.0.1:8081  orangepi@<board>   # llama-server
```

Install Ollama with `scripts/install-ollama.sh`, and the two user units with
`scripts/install-ai-services.sh`. Both are safe to re-run. `install-ollama.sh`
asserts `RuntimeWatchdogUSec=0` before *and* after the vendor installer runs,
because that installer writes system units and the watchdog is the one setting
on this board that must never come back.

### Ollama or llama-server?

They *can* run side by side — Ollama bundles its own llama.cpp, so replacing its
runner would be undone by the next Ollama update, and a separate service is
reversible. But on this board, **do not run both at once**: see "Where this
stands". They did coexist before the rebuild; that was measured, not safe.

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

### Two traps that are specific to Ollama

Both were hit on 2026-09-06 bringing it back, and neither announces itself.

**Pinning the cgroup without also fixing the thread count makes it stop
answering.** There is no `OLLAMA_NUM_THREADS`; Ollama's bundled llama-server
picks a thread count from the *machine's* CPUs, not from the cgroup's cpuset. So
`CPUAffinity=0 1 6 7 8 9 10 11` in the unit pinned it to 8 cores while it still
started enough compute threads to oversubscribe them — and llama.cpp spin-waits
at every graph barrier, so it burned **720% CPU and emitted zero tokens in 200
seconds**. No error, no timeout, no log line: it simply never finishes.

`run-llama-server.sh` never had this problem because it passes `taskset` **and**
`-t 8` together. The thread count is the other half of the pinning, and it is
the half that is easy to forget.

The board therefore serves **`qwen3:4b-house`**, which carries `num_thread 8`
baked in, and the un-parameterised `qwen3:4b` tag is deleted so nothing can
reach the stall. `install-ollama.sh` derives that 8 from `CPUAffinity` rather
than repeating it, and its smoke test is time-bounded so the fault reports
itself instead of hanging. Measured after the fix: **15.6 tok/s generation,
66 tok/s prompt** — the generation figure matches the tuned llama-server build.

**Do not disable thinking the way you would on llama-server.** The two need
opposite handling, measured on Ollama 0.33.3 with Qwen3-4B:

| Request | `message.content` | |
| --- | --- | --- |
| `"think": false` | the reasoning text | ✗ stops separating it and returns it *as* the answer |
| `/no_think` suffix | empty | ✗ Qwen3 treats it as part of the question |
| default, `num_predict` 400 | `ready` | ✓ reasoning in `message.thinking` |

So: leave thinking on, read `message.content`, and give it a **generous
`num_predict`** — a small budget is spent reasoning and returns empty content.
Budget for it: a one-word answer cost 194 tokens and 17 s.

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

### `scripts/author_automation.py`

That shape, built. Describe a rule in English; it drafts a Home Assistant
automation, checks it against your actual house, and writes a **proposal file**.
It never touches `automations.yaml` — nothing it produces is live until you copy
it in.

```bash
# on the board: Home Assistant and Ollama are both loopback-only
python3 scripts/author_automation.py "turn off the office switch every night at 11pm"
```

Three layers, because the model is wrong often enough to need all of them:

1. **The entity list comes from `/api/states`,** not the model's imagination —
   entity ids are what an LLM invents most readily. The ~25 most relevant are
   put in the prompt (all 218 would crowd a 4096-token context), `unavailable`
   ones excluded since nothing can act on them.
2. **Validation against the real house.** Every `entity_id` must exist, every
   service must exist in `/api/services`, and the automation must be
   structurally capable of firing. Failures are fed back to the model and it
   retries — the deterministic checker is the arbiter, not the model.
3. **Review hints** for what validation cannot judge: intent. Warnings only,
   never blocking, and written into the proposal's header.

**What it gets right and wrong**, measured against the real house:

| Request | Result |
| --- | --- |
| "turn off the office switch every night at 11pm" | correct, ~10 s |
| "when motion after sunset, switch on for 5 minutes" | valid, but dropped the sunset condition, made 5 minutes into 5 seconds, and never turned it off — all four flagged |
| "notify when bedroom humidity goes above 70 percent" | wrong: a `state` trigger instead of `numeric_state above: 70`, and it would not fix this even after two repair attempts — flagged |

So: **simple single-clause requests come out right; compound ones need editing.**
That is the ceiling of a 4B model, and the reason this writes a proposal for a
human rather than installing anything. Read the hints — every one of them was a
real defect it produced.

Mistakes it makes that are worth recognising, all caught mechanically now: a
`delay` *service* (there is none — `delay` is a step key), a state trigger with
`from == to` (loads, never fires), and `at: sunset` on a time trigger (a
restriction is a condition; as a trigger it also fires at sunset on its own).

## Wiring the LLM into the house

Until 2026-09-08 the model was an island: Ollama ran, and nothing in the house
could reach it. The dashboard had no LLM endpoint at all, Home Assistant's
`ollama` integration was not configured, and `author_automation.py` was
reachable only over SSH. That is now closed, in three pieces.

Everything below is set up by `scripts/setup-ha-ollama.py`, which is idempotent
and refuses to guess:

```bash
~/smart_home_AI/.venv/bin/python scripts/setup-ha-ollama.py            # dry run
~/smart_home_AI/.venv/bin/python scripts/setup-ha-ollama.py --apply
~/smart_home_AI/.venv/bin/python scripts/setup-ha-ollama.py --apply --reconfigure
```

`--reconfigure` pushes the settings in the script onto subentries that already
exist. Without it the script only creates, so a setting changed in the file
would never reach a board where the subentry was made by an earlier run.

**Home Assistant runs on the host network**, so it reaches `127.0.0.1:11434`
directly. The loopback bind did not have to be widened for any of this.

### What it creates

| Entity | Sees the house? | Where it is used |
| --- | --- | --- |
| `conversation.local_qwen` | no | the **default** Assist pipeline, as a fallback |
| `conversation.local_qwen_control` | yes, `llm_hass_api: assist` | its own "Local Qwen (control)" pipeline |
| `ai_task.local_qwen_task` | no | available to `ai_task.generate_data` from automations |

### Two agents, because `prefer_local_intents` is not what it sounds like

The default pipeline has `prefer_local_intents` on, so Home Assistant's own
sentence matcher answers first and the model only sees what it could not
parse. But the filter narrows as soon as the agent advertises CONTROL — which
it does the moment it is given `llm_hass_api`. Then
`_async_local_fallback_intent_filter` restricts the local-first path to
`GetState` and `MediaSearchAndPlay`, and everything else, "turn on the office
light" included, goes to the model.

On this board that is exactly backwards, so the default pipeline gets the agent
*without* house access. Measured through a real pipeline with
`scripts/check-assist-routing.py`:

| Sentence | Handled by | Time |
| --- | --- | ---: |
| "is the door sensor front door open" | local matcher | **0.03 s** |
| "how many lights are on" | local matcher | **0.01 s** |
| "what humidity should a bedroom be at night" | `conversation.local_qwen` | 22.3 s |

That is the whole design in three lines: the house stays instant, and the model
only costs time on questions nothing else could answer.

**The matcher matches names and aliases, not paraphrases.** "is the front door
open" does *not* match, because the entity is called "Door sensor front door";
it falls through to the model, which correctly says it cannot check. Anything
you want answered instantly needs an alias that matches how you actually say
it. That is a bigger win than any model setting.

### The controlling agent is not practical on this board

It exists, on its own pipeline, opt-in. It is also unusable, and the reason is
structural rather than a tuning problem: Home Assistant allows
`MAX_TOOL_ITERATIONS = 10`, and each iteration is a full pass over a prompt
carrying every exposed entity. With this house's ~45 exposed entities, one
question — "how many lights are on" — ran for **over 18 minutes** without
finishing with thinking on, and still exceeded 5.5 minutes with thinking off.

So `think` is set per agent, not globally:

| Agent | `think` | Why |
| --- | --- | --- |
| `local_qwen` | **on** | free-form prose; with it off, Ollama returns the reasoning *as* the answer |
| `local_qwen_control` | **off** | it pays per tool iteration, up to ten of them |
| `local_qwen_task` | on | free-form prose again |

If you want the controlling agent to be usable, the lever is **exposing fewer
entities to Assist**, not a model setting. Nothing else on this board moves it.

### Two Home Assistant defaults that are wrong here

**`keep_alive` defaults to `-1`** — keep the model loaded for ever. That pins
~3.3 GiB and destroys the single property Ollama was chosen for on a swapless
board. The script sends 300 seconds; verified by watching available memory
return from 4591 MiB to 8877 MiB after a conversation went idle.

**`think` defaults to `False`**, and that is the trap already documented above,
reached through a different door. The integration handles thinking correctly
when it is *on* — it files the reasoning under `thinking_content` and leaves
`content` clean.

⚠️ **`num_ctx` is 8192 and the cgroup measures 4.55 GiB against
`MemoryMax=5G`.** That is a narrow margin, and `OOMPolicy=stop` means crossing
it stops Ollama rather than degrading it. Lower `NUM_CTX` in the script to 4096
if anything ever trips it; the KV cache is most of the difference.

### Four things about the config-entry API that are not documented

Found the hard way, all in `setup-ha-ollama.py`:

- **The REST entry listing serialises `subentries` as `null`** however many the
  entry has. Idempotency checks must use the websocket
  `config_entries/subentries/list`, or the script creates a duplicate on every
  run.
- **Creating a subentry reloads the config entry**, and a flow opened before
  that reload is discarded — the next POST returns "Invalid flow specified".
  Wait for the entry to be `loaded` before opening each flow.
- **An `ai_task_data` subentry takes no `prompt`.** `prompt` and `llm_hass_api`
  are only added to the schema for `subentry_type == "conversation"`; sending
  one is rejected with "extra keys not allowed".
- Assist pipelines are a storage collection, so the commands are
  `assist_pipeline/pipeline/{list,create,update,set_preferred}`, and `update`
  requires every field, not just the changed one.

## Drafting automations from the dashboard

`author_automation.py`'s drafting now lives in `src/python/automation_author.py`
so the command line and the dashboard produce the same proposal from the same
sentence. The dashboard's **Automations** view is the same three layers
described above, with a button on the end:

| Endpoint | |
| --- | --- |
| `POST /api/automations/draft` | draft, validate, save a proposal file |
| `GET /api/automations/proposals` | list them |
| `POST /api/automations/proposals/{name}/install` | hand it to Home Assistant |
| `DELETE /api/automations/proposals/{name}` | discard it |

Installing goes through Home Assistant's own
`POST /api/config/automation/config/{id}`, not an append to `automations.yaml`.
That gets the same validator the UI uses — a second, authoritative check after
ours — and Home Assistant writes the file and reloads automations itself. A
draft that passes our checker can still be refused there, and that refusal is
the one to believe.

Drafting holds a lock: one at a time. Ollama serialises requests anyway, so a
second concurrent draft would not start sooner, it would just hold a worker
thread for a minute to find that out.

## The morning digest

`house-digest.timer` fires at 04:00 — the quietest hour on this board — and
writes `house_digest.json`, which the dashboard serves at `/api/digest` and
shows on the **Status** view. Install it with
`scripts/install-house-digest.sh`.

This is the shape a slow local model is genuinely good at, and the division of
labour is the opposite of the usual one:

> **Python computes every number, and decides which ones are worth saying.**

The model is never asked how many times the front door opened. It cannot be
wrong about a figure it did not calculate — which was meant to turn its
unreliability from a correctness problem into a style problem, and in the end
removed the need for it altogether (see below). The full fact sheet is stored
beside the notes in the same file and is one click away in the UI.

What it computes, all in `src/python/house_digest.py`:

- **Camera sightings**, kept apart from motion sensors. They arrive on the same
  Home Assistant feed with the same `occupancy` device_class, but they are not
  the same evidence: a PIR says something warm moved, the NPU detector says it
  recognised a person. Ranked together, three PIR trips would bury the one
  camera that actually saw somebody.

- **Motion**, per sensor, against *its own* previous days rather than against
  the other sensors.
- **Batteries** below 50%.
- **What is not reporting**, grouped by device rather than listed as 49 entity
  ids nobody can act on.
- **The board**: lowest free memory, peak temperature, peak load, and any
  reboots the resource logger recorded.

### Qwen3-4B could not write the summary, four ways

This is the one part of the plan that did not work, and it is worth recording
precisely because the failures were varied and none of them looked like a
failure. Measured on this board, asking it to turn the computed notes into a
short briefing:

| Attempt | Result |
| --- | --- |
| free-form, thinking **on** | 3000 tokens generated, **content empty** (`done_reason=length` — all of it was reasoning) |
| schema, thinking **off** | it wrote its **reasoning into the `summary` field** |
| schema, thinking **on** | 2500 tokens on a **206-token** prompt, **empty again** |
| schema, thinking off, short notes | **copied the notes back verbatim** |

Two conclusions, and the first corrects something stated earlier in this file:

- **"A schema makes `think: false` safe" holds only when the schema's fields
  are typed tightly enough to leave no room for prose.** That is true of
  `author_automation.py`, whose schema is a dozen typed automation fields. It
  is not true of a single free-text string, which accepts reasoning just as
  happily as an answer.
- **When the thing you want *is* prose, there is nothing left to constrain.**
  The model reasons without bound about a task that needs no reasoning, and
  more budget only buys more of it.

So **prose is off by default** (`--prose` turns it on). The path stays in the
code for a larger model, and `headlines()` — which picks the handful of things
worth saying — is the briefing in the meantime. That is not a consolation
prize: the notes are what the model was only ever going to reword, and they are
correct by construction.

Two things the digest deliberately refuses to do:

- **It will not invent a baseline.** The motion log was only added recently, so
  until there is more than a day of history before the window every sensor
  reports "no baseline yet" rather than an average of 0.0/day — against which
  any activity at all would look like an anomaly.
- **It will not fail because the model did.** If Ollama is unreachable or slow,
  the digest is still written with the facts and no prose, and the UI says so.
  A morning report must not depend on the least reliable component in it.

## Vision and the LLM

The plan was that the NPU would detect, rules would act instantly, and the LLM
would asynchronously write a description into the event log. Two of those three
are live; the third is not, and deliberately.

**What runs.** Detections reach Home Assistant as
`binary_sensor.<camera>_npu_person`, and because those carry the `occupancy`
device_class they flow into the motion log with no extra wiring - which means
they reach the morning digest as well. `automation.office_person_detected_...`
acts on them directly, in Home Assistant, in milliseconds.

**What does not, and why.** Having the model narrate detections is the same job
the digest prose turned out to be, and Qwen3-4B failed that four different ways
(see above). It would also be the wrong shape: the model is text-only, so it
could not describe an *image* - only retell counts and timestamps that Python
already states exactly. There is no version of this where the model adds
information rather than rephrasing it.

So the deterministic path is the whole path. The model stays out of it, and the
rule that made it worth trying still holds: **the LLM authors, rules execute** -
and here the rules needed no authoring.

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

**⚠️ Never set `RuntimeWatchdogSec` on this board.** An earlier revision of this
section told you to enable `RuntimeWatchdogSec=60s` so a hang would self-recover.
Do not. This board's SBSA Generic Watchdog has a **fixed 10-second timeout that
`SETTIMEOUT` cannot raise**, so a 60 s setting makes systemd ping every 30 s
against a timer that fires at 10 — it resets the board roughly every 80 s, with
no kernel panic and an empty `pstore`, which is exactly the 2026-09-02 loop that
cost a full rebuild. `RuntimeWatchdogUSec=0` is the correct state:

```bash
systemctl show -p RuntimeWatchdogUSec    # must print 0
```

The full analysis, including why the AI services and the NVMe were both wrongly
suspected, is in `docs/handoff-2026-09-03-recovery.md` under "Best current
theory (revised)". The hard lockup detector stays disabled, so a genuine hang
still needs a power cycle — that is the accepted trade, because the alternative
on this hardware is a guaranteed reset loop.

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
- `docs/npu-model-pipeline.md` — **rebuilding the detection model**: why it has
  this shape, the pipeline, and the traps that are silent when violated
