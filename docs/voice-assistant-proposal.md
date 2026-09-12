# Proposal: a voice assistant for the house

Investigated 2026-09-12 against the running hardware. Every figure below with a
unit was measured on the board or the panel that day unless it says *estimate*,
and the estimates are the ones stage 2 exists to replace.

**Updated the same day:** an ESP32-S3-Touch-LCD-4B is already on hand, which
settles the hardware question and makes stage 3 free. See "The
ESP32-S3-Touch-LCD-4B" below — it changes which device, not the architecture.

## The answer

**Neither board, and both.** "Orange Pi or Raspberry Pi" is the wrong split —
the question hiding inside it is *where the microphone goes*, and that is not the
same place as where the speech recognition runs.

- **The pipeline runs on the Orange Pi 6 Plus.** It has the cores, the memory and
  already runs Home Assistant, which is the thing the pipeline plugs into.
- **The microphone does not go on the Raspberry Pi 4.** It is the wall panel, and
  the panel's whole job is decoding video. Adding speech recognition to the same
  four cores contends with exactly the thing that makes it work.
- **The microphone goes where you stand and talk**, on its own small device —
  and one is already owned: an ESP32-S3-Touch-LCD-4B, an 86-box wall panel with
  a microphone in it, so the screen and the place you talk stop being a
  trade-off.

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
  ESP32-S3-Touch-LCD-4B              Orange Pi 6 Plus
  ┌─────────────────┐                ┌──────────────────────────────┐
  │ ES7210 mic      │                │ wyoming-whisper   (STT)      │
  │ ES8311 + speaker│ ─audio, only─► │ wyoming-piper     (TTS)      │
  │ micro_wake_word │   after wake   │                              │
  │ on-device       │                │ HA Assist pipeline           │
  │ (86 box, wall)  │ ◄spoken reply─ │  ├ local intents ~0.02 s ──► house
  └─────────────────┘                │  └ fallback: local_qwen ~22 s│
                                   └──────────────────────────────┘
```

Nothing new runs on the Raspberry Pi 4. The panel keeps decoding video.

### Where the microphone goes

**This is settled by hardware already on hand.** The ESP32-S3-Touch-LCD-4B in the
drawer is a better answer than anything that would have been bought, and the
next section is about it. The alternatives are recorded because they are the
fallbacks if it disappoints.

| | Hardware cost | Wake word | Load added |
| --- | --- | --- | --- |
| **A. ESP32-S3-Touch-LCD-4B** (owned) | **a speaker, a few dollars** | on-device, microWakeWord | **none on either board** |
| B. Home Assistant Voice Preview Edition | ~$60 | on-device, microWakeWord | none on either board |
| C. USB mic on the Orange Pi itself | ~$25 | on the board | small, but wrong place |
| D. USB mic + speaker on the Pi 4, `wyoming-satellite` | ~$25 | openWakeWord, ~0.3 core (*estimate*) | on the busiest box |

**B is the fallback, not a rival.** It is the device Home Assistant develops the
voice stack against, with a microphone array, a speaker and a physical mute
switch. If the ESP32-S3 board turns out to be a fight, this is what to buy, and
nothing else in this proposal changes.

**C is still worth an afternoon**, because the Orange Pi already has a capture
device (`ALC269VC`) and free USB ports. It makes stages 1–2 testable at a desk
before any wall is involved.

**D only makes sense** if voice must be *at the wall panel specifically*, which
the ESP32-S3 board makes unnecessary. It puts openWakeWord on four cores that are
already at 70%, and the Pi 4 has no capture device at all.

## The ESP32-S3-Touch-LCD-4B

An 86-box wall panel with a microphone in it, which dissolves the awkward part of
this proposal: the advice was to put the microphone where you talk rather than
where the screen is, and this is a screen you mount where you talk.

| | |
| --- | --- |
| Module | `ESP32-S3-WROOM-1-N16R8` — 16 MB flash, **8 MB octal PSRAM** |
| Microphone | onboard SMD mic, through an **ES7210** echo-cancellation ADC |
| Codec | **ES8311** for playback |
| Speaker | MX1.25 2P, 8 Ω 2 W — **connector only, nothing fitted** |
| Display | 4″ 480×480, ST7701 RGB, GT911 touch |
| Form factor | Smart 86 box — a wall switch box |
| Power | USB-C, or 3.7 V LiPo through an AXP2101 PMIC |

The octal PSRAM matters: it is the configuration `micro_wake_word` needs. Every
chip on the audio path has a stock ESPHome component — `es7210` as an
`audio_adc`, `es8311` as an `audio_dac`, plus `i2s_audio`, `micro_wake_word`,
`voice_assistant` and `gt911`. Nothing here needs a custom driver.

### The caveat: the display and the voice fight over PSRAM

An RGB parallel LCD has **no frame memory of its own**. The ESP32-S3 shifts
480×480×16bpp — 450 KB — out of PSRAM continuously, roughly 27 MB/s at 60 Hz,
and the wake-word inference and I2S buffers want the same PSRAM. This is not an
exotic risk: ESPHome's own reference voice devices (ESP32-S3-BOX-3, Voice PE) all
use small SPI or QSPI displays that hold their own frame memory, which avoids the
problem by construction. ESPHome's ST7701S page says PSRAM is required "due to
the size of the display buffer" and says nothing about sharing it.

It can be made to work. Plan on **the display being what gets compromised** — a
static, few-widget screen rather than animated LVGL — and treat voice as the job
the device is there to do. Write the display against `mipi_rgb`; the `st7701s`
component is deprecated and slated for removal.

### What it will not do

**Camera streams.** No video decode, not the bandwidth, not the resolution. The
Raspberry Pi 4 keeps that job, and this device is a second small panel beside it,
not a replacement for it — temperatures, security state, NPU presence, a few
light toggles.

### Two things to establish before writing any YAML

- **The GPIO pin map.** Waveshare's wiki documents the demos but not a pin table,
  and an ESPHome config needs exact I2S and I2C pins. The authority is the
  schematic, or their `07_ES8311` and `08_ES7210` demo sources.
- **Whether the ES7210's echo cancellation is actually engaged.** ESPHome's
  component is an ADC driver; the chip's AEC may not be exercised by it. The
  practical consequence is that the wake word may not trigger over the device's
  own TTS. Livable — but do not design around barge-in until it is demonstrated.

No published ESPHome configuration was found for this exact board, so expect to
write it from the datasheet rather than adapt someone else's.

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

**3. Microphone — now the cheapest stage, not the most expensive.** A USB mic on
the Orange Pi for an afternoon (option C) proves the pipeline end to end with no
firmware involved. Then the ESP32-S3 board, and do it in **two steps, voice
first**: bring it up as a headless `voice_assistant` + `micro_wake_word` satellite
with the display disabled entirely, confirm it works, and only then add the
screen. That ordering is what turns the PSRAM contention from a mystery into a
measurement — if the wake word degrades when the display comes up, you know
exactly what did it. *Verify:* wake-to-spoken-reply latency, and that the whole
turn stays off `conversation.local_qwen`.

**4. Dashboard-control intents.** The `intent_script` → SSE path above, per-screen
opt-in, and only after 1–3 are boring. The ESP32-S3 board makes this more
interesting than it was: touch and voice in the same device, so a spoken request
can act on the Raspberry Pi 4's big panel while the small one confirms it.

## Budget

No swap, so this is a real constraint rather than bookkeeping. Current available
is 7.8 GiB, but Ollama takes ~3.3 GiB whenever a model is loaded and HA's
`keep_alive` holds it 300 s after the last request.

| | Resident (*estimate*) |
| --- | --- |
| wyoming-piper | ~100 MB |
| wyoming-whisper, `base.en` int8 | ~300–500 MB |
| wyoming-openwakeword (only if option D) | ~100 MB |

Comfortable, but give each unit a `MemoryMax` and `OOMPolicy=stop` so a runaway
speech container cannot be the process that makes the kernel pick a victim.

The hardware bill is now **one 8 Ω 2 W speaker with an MX1.25 2P connector**, a
few dollars. Without it the board can hear and cannot answer, which is not a
voice assistant.

## What not to do

- Do not run any of this on the Raspberry Pi 4 while it is the wall panel.
- Do not reach for cloud STT or TTS. The rest of the house is local; `google_translate`
  TTS is the one exception and stage 1 removes it.
- Do not put Qwen in the voice path, on either pipeline.
- Do not stream continuous audio to a central wake word service over this Wi-Fi.
- Do not add a microphone button to the dashboard expecting it to work on the
  panel. See trap 2.
- Do not bring the ESP32-S3 board up with its display first. Voice is the job;
  the screen is the thing that might have to give, and doing it in that order
  means a wake word that degrades has exactly one suspect.
- Do not design around barge-in — talking over the device's own TTS — until the
  ES7210's echo cancellation has been shown to actually be engaged.

## Related

- `docs/local-ai.md` — the conversation agents, the pipelines, and why there are two
- `docs/kiosk-display.md` — the panel, its Chromium flags, and what breaks it
- `docs/handoff-2026-09-10-wall-panel.md` — the stream-cost measurements and the Wi-Fi item

### Vendor and component references

- Waveshare wiki: <https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-4B> — board
  specs and the `07_ES8311` / `08_ES7210` demos, which are the authority on pins
- ESPHome `es7210` audio ADC: <https://esphome.io/components/audio_adc/es7210/>
- ESPHome ST7701S display: <https://esphome.io/components/display/st7701s/> —
  deprecated; use `mipi_rgb`
