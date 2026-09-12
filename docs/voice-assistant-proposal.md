# Proposal: a voice assistant for the house

Investigated 2026-09-12 against the running hardware. Every figure below with a
unit was measured on the board or the panel that day unless it says *estimate*,
and the estimates are the ones stage 2 exists to replace.

## The answer

**Neither board, and both.** "Orange Pi or Raspberry Pi" is the wrong split —
the question hiding inside it is *where the microphone goes*, and that is not the
same place as where the speech recognition runs.

- **The pipeline runs on the Orange Pi 6 Plus.** It has the cores, the memory and
  already runs Home Assistant, which is the thing the pipeline plugs into.
- **The microphone does not go on the Raspberry Pi 4.** It is the wall panel, and
  the panel's whole job is decoding video. Adding speech recognition to the same
  four cores contends with exactly the thing that makes it work.
- **The microphone goes where you stand and talk**, on its own small device.

## What is there today

| | Orange Pi 6 Plus | Raspberry Pi 4 (panel) |
| --- | --- | --- |
| Cores / load | 12 / **4.23** | 4 / **2.80** |
| Memory available | 7.8 GiB of 15, no swap | 2.7 GiB of 3.8 |
| Capture device | **yes** — ALC269VC analog, `card 0` | **none at all** — `arecord -l` is empty |
| Playback | ALC269VC analog + 2× I2S/DP | bcm2835 headphones + HDMI |
| Free USB | yes — only the Zigbee CP210x and the UB500 BT adapter are in | yes |
| Network | `wlp1s0`, power save **on**, `enp97s0` down | `wlan0`, `eth0` down |
| Busy with | HA, MQTT, zigbee2mqtt, go2rtc, Ollama, NPU detector | Chromium at ~117% of 400%, 5 camera streams |

The panel's 2.80 load average is it doing *nothing but being a panel*. The
wall-panel handoff already measured where that ends: six streams play, eight
freeze. There is no room there and the room it has is already spoken for.

### What Home Assistant has, and what it is missing

HA **2026.6.3**, and the voice framework is entirely present: `assist_pipeline`,
`assist_satellite`, `stt`, `tts`, `conversation` are all loaded. What is missing
is every engine that would make it do anything:

| | |
| --- | --- |
| Speech-to-text engines | **none** |
| Text-to-speech engines | `tts.google_translate_en_com` only — **cloud**, and dies with the WAN |
| Wake word | none |
| Satellites | none |
| Conversation agents | `conversation.home_assistant`, `conversation.local_qwen`, `conversation.local_qwen_control` |

So the conversation half is built and wired (see `docs/local-ai.md`); the *audio*
half does not exist. That is the whole job.

## Four traps, found by looking rather than by guessing

**1. There are no add-ons, and every guide assumes there are.** Home Assistant
here is the plain Docker container (`ghcr.io/home-assistant/home-assistant`,
`--network host`), not HA OS and not Supervised. There is no Supervisor and no
add-on store, so "install the Whisper add-on" — the first step of essentially
every voice tutorial — is not available. The Wyoming services have to run as
their own containers beside `zigbee2mqtt` and `mosquitto`. Checked: all three
images publish `linux/arm64`.

| Image | arm64 |
| --- | --- |
| `rhasspy/wyoming-whisper` | ✅ |
| `rhasspy/wyoming-piper` | ✅ |
| `rhasspy/wyoming-openwakeword` | ✅ |

HA on host networking reaches them on `127.0.0.1`, which is also what keeps them
off the LAN.

**2. The panel's browser cannot open a microphone, and the failure is silent.**
The obvious design — a microphone button on the dashboard — does not work on the
panel as it stands. The dashboard is served over plain HTTP
(`http://192.168.0.234:8000/`), and `getUserMedia` is gated on a secure context:
HTTPS, or `localhost`, and the panel is neither. It does not error in a way
anyone would notice; the promise rejects and the button does nothing. Three ways
out, none free:

- serve the dashboard over HTTPS with a certificate the panel trusts;
- launch Chromium with `--unsafely-treat-insecure-origin-as-secure=http://192.168.0.234:8000`
  (which also needs `--user-data-dir`, and weakens every origin rule for that
  profile);
- **don't put the audio in the browser at all** — recommended, and what the
  architecture below does.

**3. The LLM must not be in the voice path.** This is already the project's rule
and voice is where breaking it would be most tempting. Measured: HA's local
intent matcher answers in ~0.02 s, `conversation.local_qwen` takes ~22 s, and
`conversation.local_qwen_control` can take over five minutes. A voice turn that
waits on Qwen is not a slow assistant, it is a broken one. Voice rides the
**default pipeline**, which already has `prefer_local_intents` on, and the model
stays the fallback for sentences the matcher cannot parse.

**4. Audio is the next thing the Wi-Fi will break.** A satellite streaming
16 kHz 16-bit mono is 256 kbit/s *continuously* if the wake word runs centrally.
The board's own link averages 333 ms to its router with ~5% loss; panel → board
measured 39 ms average, 82 ms peak, 0% loss over 8 packets that day. RTSP already
turned that latency into loss. Two consequences: **do the Ethernet/power-save fix
first**, and **choose a satellite that runs its wake word locally**, so audio
only flows after someone has said the wake word.

## The architecture

```
  where you stand                          Orange Pi 6 Plus
  ┌───────────────┐                    ┌──────────────────────────────┐
  │ mic + speaker │                    │ wyoming-whisper   (STT)      │
  │ wake word     │ ──audio, only ───► │ wyoming-piper     (TTS)      │
  │ runs here     │    after wake      │                              │
  │               │                    │ HA Assist pipeline           │
  │               │ ◄── spoken reply ──│  ├ local intents  ~0.02 s ──► house
  └───────────────┘                    │  └ fallback: local_qwen ~22 s│
                                       └──────────────────────────────┘
```

Nothing new runs on the Raspberry Pi 4. The panel keeps decoding video.

### Where the microphone goes — three options

| | Hardware cost | Wake word | Load added |
| --- | --- | --- | --- |
| **A. Home Assistant Voice Preview Edition** (ESP32-S3) | ~$60 | on-device, microWakeWord | **none on either board** |
| B. USB mic + speaker on the Pi 4, `wyoming-satellite` | ~$25 | openWakeWord, ~0.3 core (*estimate*) | on the busiest box |
| C. USB mic on the Orange Pi itself | ~$25 | on the board | small, but wrong place |

**A is the recommendation.** It is the device Home Assistant develops the voice
stack against, it has a microphone array, a speaker, and a physical mute switch,
it does its wake word on-device so nothing streams until you speak to it, and it
adds zero load to a board that is already running the house. It also goes where
the conversation is rather than where the screen is, which is the point — you
talk to a room, you look at a panel.

**C is still worth doing first**, for an afternoon, because the board already has
a capture device and free USB ports: it makes stages 1–3 testable before any
hardware is ordered.

**B only makes sense** if voice must be *at the panel specifically*. It puts
openWakeWord on four cores that are already at 70%, and the Pi 4 has no capture
device at all today, so it needs the same USB microphone that option C does.

## "Voice for dashboard control" is two different jobs

Worth separating, because one of them is already finished and the other is the
only real code in this proposal.

**Controlling the house** — lights, plugs, scenes, "is anyone in the office".
Home Assistant's intents already do this, against the real entities, in 0.02 s.
Voice needs a microphone and nothing else. **Nothing to build.**

**Controlling the dashboard** — "show me the front door", "go to cameras". This
does not exist, and it needs a path from HA back to a specific screen. The
transport is already built and proven: the panel holds `/api/events/stream` open,
and the camera-on-motion and follow-the-route work (`d817f6c`, `8e5df4d`) is
exactly a server-side decision driving what the panel displays. So the shape is

```
custom intent_script in HA  →  POST to the dashboard  →  SSE event  →  panel switches view
```

with the same per-screen opt-in the camera tickbox already uses, so a phone and
the wall panel can disagree about whether they take orders. Call it a day's work,
and it is the only genuinely new code here.

## Staged plan

Staged the way the AI restore was, so an unexpected problem points at one change.

**0. Fix the network.** Ethernet on `enp97s0`, or power save off on `wlp1s0`.
Already open item #1 from the wall-panel handoff. Do this first or spend the
project debugging audio dropouts that are actually Wi-Fi.

**1. Piper (TTS).** One container, `MemoryMax` set the way `install-ollama.sh`
does it. Replaces `tts.google_translate_en_com`, which is the last cloud
dependency in the house's speech path. *Verify:* a `tts.piper` entity appears,
and `tts.speak` produces audio. Useful on its own — spoken notifications — before
any microphone exists.

**2. Whisper (STT), and measure before committing.** Start at `base.en` int8 and
time a real 3-second utterance on the board's own cores. *Estimate:* 0.5–1.5 s,
but that number is exactly the kind this project has been burned by, so treat it
as unknown until measured. If it lands above ~1.5 s, drop to `tiny.en`; if it
lands well under, `small.en` buys accuracy. *Verify:* HA's Assist debug page,
typed first, then an uploaded audio file.

**3. Microphone.** Option C on the board for an afternoon to prove the pipeline
end to end, then option A where you actually talk. *Verify:* wake-to-spoken-reply
latency, and that the whole turn stays off `conversation.local_qwen`.

**4. Dashboard-control intents.** The `intent_script` → SSE path above, per-screen
opt-in, and only after 1–3 are boring.

## Budget

No swap, so this is a real constraint rather than bookkeeping. Current available
is 7.8 GiB, but Ollama takes ~3.3 GiB whenever a model is loaded and HA's
`keep_alive` holds it 300 s after the last request.

| | Resident (*estimate*) |
| --- | --- |
| wyoming-piper | ~100 MB |
| wyoming-whisper, `base.en` int8 | ~300–500 MB |
| wyoming-openwakeword (only if option B) | ~100 MB |

Comfortable, but give each unit a `MemoryMax` and `OOMPolicy=stop` so a runaway
speech container cannot be the process that makes the kernel pick a victim.

## What not to do

- Do not run any of this on the Raspberry Pi 4 while it is the wall panel.
- Do not reach for cloud STT or TTS. The rest of the house is local; `google_translate`
  TTS is the one exception and stage 1 removes it.
- Do not put Qwen in the voice path, on either pipeline.
- Do not stream continuous audio to a central wake word service over this Wi-Fi.
- Do not add a microphone button to the dashboard expecting it to work on the
  panel. See trap 2.

## Related

- `docs/local-ai.md` — the conversation agents, the pipelines, and why there are two
- `docs/kiosk-display.md` — the panel, its Chromium flags, and what breaks it
- `docs/handoff-2026-09-10-wall-panel.md` — the stream-cost measurements and the Wi-Fi item
