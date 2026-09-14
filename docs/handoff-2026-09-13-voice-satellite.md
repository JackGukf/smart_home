# Handoff: the voice satellite, 2026-09-12 → 13

Written to be picked up cold. Voice is the open work and comes first; everything
else this session is finished and summarised at the end with pointers to where
it is recorded.

## Resolved 2026-09-13 (evening): the wake word stopped after the first playback

**Cause.** The engine ran from boot and was stopped for every announcement or
reply (the shared I2S bus, trap 4), then never restarted. The media player went
idle ~90 ms before `voice_assistant`, so `on_idle`'s instant
`not voice_assistant.is_running` check refused the restart, and nothing retried.
Two more restart paths were dead: `voice_assistant: on_idle` fires only in
continuous mode, and the I2S speaker holds the bus for its 500 ms timeout.

**Fix.** One `restart_wake_word` script, `mode: restart`, that *waits* for
assistant not running, media player idle and `i2s_out` stopped, then starts the
engine. Called from the media player's `on_idle` and `voice_assistant`'s
`on_end` / `on_error`.

**Verified** (firmware `config_hash 0xabc55d0c`): announce → `DETECTING_WAKE_WORD
→ STOPPED` → playback → `STOPPED → DETECTING_WAKE_WORD` 17 ms after idle; mic
capturing back `on`; repeated announcements restart every time, zero
`Parent bus is busy`. Before the fix, capturing went `off` after the first
announcement and stayed off.

**Verified by a person, 03:09–03:12:** three spoken "Okay Nabu"s, three
detections — `sliding average probability is 0.98 and max probability is 1.00`
against the 0.97 cutoff — and the wake word restarted after each run, including
after a spoken reply and after `stt-no-text-recognized`.

## What the first real use turned up, and what changed

The wake word worked; everything after it was the problem.

| Run | Transcript | What happened |
| --- | --- | --- |
| 03:09:53 | *(nothing)* | `stt-no-text-recognized`, back to listening |
| 03:10:28 | "I'm going to think about it a little bit." | 17 s on Qwen, answered the noise |
| 03:11:25 | "Okay, Naboo." — the wake word, said again | **57 s** on Qwen: "I don't recognize Naboo as a device" |

Two causes. The satellite gives no sign it woke, so people repeat the wake word
and it becomes the command. And the satellite used the `preferred` pipeline,
whose unmatched speech falls back to Qwen — against the proposal's own rule,
"Do not put Qwen in the voice path, on either pipeline".

Fixed by `scripts/setup-ha-voice.py --apply` (idempotent; a second run changes
nothing):

- **A "Voice Panel" pipeline** — same Whisper and Piper, agent
  `conversation.home_assistant` only — and `select.voice_panel_assistant` set to
  it. The default pipeline keeps its Qwen fallback for typed Assist.
- **Automation `voice_ignore_repeated_wake_word`** — a sentence trigger on
  "okay nabu" / "okay naboo" and variants that answers with an empty response.
  Home Assistant 2026.6.3 skips TTS on an empty reply (`pipeline.py`: no
  `tts_input.strip()` → `PipelineStage.END`), so a repeat is silence.

Measured through the new pipeline with text input: "Okay, Naboo." → empty, no
TTS, 0.01 s; "What time is it?" → "8:16 PM", 0.02 s; "Naboo is a device." →
"Sorry, I couldn't understand that", 0.07 s.

No wake chime, by choice: the mic and speaker share one bus, so a chime would
push the start of listening back and eat the start of the command.

**One thing seen, not fixed:** when Home Assistant continues a conversation
(a reply ending in a question), the microphone is reopened while the I2S speaker
still holds the bus — `i2s_audio.microphone: Driver failed to start; retrying in
1 second` — and recovers a second later. Rare now that no model writes the
replies; if it matters, lower the speaker's 500 ms `timeout`.

VERBOSE logging is reverted to DEBUG. The device now runs `config_hash
0xfdc46cc5`, which differs from the verified build only in log level; after that
flash the microphone came back capturing on its own.

## The original fault, as written before it was found

**The on-device wake word never runs.** Everything around it works.

| Stage | State | Evidence |
| --- | --- | --- |
| Speaker | ✅ working | a real speaker *is* fitted to the MX1.25 connector (see below); playback audible, drains at the right rate |
| Microphone | ✅ capturing | `binary_sensor.voice_panel_microphone_capturing` = `on` |
| Whisper STT | ✅ working | transcribed live speech from the board's mic as `" Okay, Naboo."` |
| Intent / reply | ✅ working | "what time is it" → "7:42 PM" in **0.57 s**, local matcher |
| **Wake word** | ❌ **not running** | zero inference lines at VERBOSE; no pipeline run has ever had a `wake_word-end` event |

> **Correction, 2026-09-13 (later session): the evidence below is not evidence.**
> The compiled `micro_wake_word` (ESPHome 2026.8.2) contains **no `ESP_LOGV` at
> all** — it never prints per-inference probabilities at any level, so silence
> at VERBOSE is what a healthy engine prints. And an on-device detection starts
> Home Assistant's pipeline at **STT** (`USE_WAKE_WORD` is only sent for
> server-side wake words), so `wake_word-end` never appears for this device
> either. What the engine does log is `[D] State changed from … to …`.
>
> A live capture then showed the real fault: the engine **was** in
> `DETECTING_WAKE_WORD` until the first announcement, stopped for playback, and
> never restarted — the speaker went idle ~90 ms *before* `voice_assistant`, so
> `on_idle`'s guard refused the restart and nothing retried. Microphone
> capturing went `off` and stayed off. The fix restarts from whichever side goes
> idle second; see `configs/esphome/voice-panel.yaml`.

### Why the evidence is conclusive rather than suggestive (superseded — see above)

- **VERBOSE logging demonstrably works.** Other components print `[V]` lines in
  the same capture — the Wi-Fi roam scans are there — while `micro_wake_word`
  prints only its config dump. No probabilities, no inferences, no detections.
  An engine that was running and hearing silence would still print
  probabilities near zero.
- **The microphone is capturing**, so the absence is not "nothing is on the bus".
  Audio is flowing and not reaching the model.
- **HA's pipeline debug record** (`assist_pipeline/pipeline_debug/list`) shows
  only two runs, and neither has `wake_word-end`. Both began at `stt-start`.

### A misreading to not repeat

It felt, at the end of the session, as though "Okay Nabu" had woken the device.
It had not. `assist_satellite.start_conversation` — run as a test — puts the
satellite straight into listening, and Whisper then transcribed the *wake word
itself* as the command. "Okay, Naboo." is not an intent, so it fell through to
`conversation.local_qwen` (~22 s) and the run ended at `intent-start → run-end`
with no reply. That "no response" was correct behaviour for that input. **A run
with no `wake_word-end` event was not started by the wake word.**

### The next test — a hypothesis, stated as one

Two confident explanations for this symptom have already been wrong this session.

**Leading suspect:** the `on_announcement → micro_wake_word.stop` /
`on_idle → micro_wake_word.start` pair on the media player
(`configs/esphome/voice-panel.yaml`). It was added for the shared I2S bus. The
media player passes through announcement state around boot and after every TTS;
if `stop` fires and `on_idle`'s `not voice_assistant.is_running` guard stops the
restart, the mic keeps capturing for the satellite while the model sits
stopped — which is exactly the observed state.

**Test:** remove that pair, keep the `on_boot` start, OTA, read the VERBOSE log.

- **Probabilities appear** → those triggers were the cause. Playback will then
  hang again on `Parent bus is busy` (below), so the triggers need a smarter
  guard rather than removal.
- **Still silent** → the cause is upstream. Next suspect: `voice_assistant`
  holding the microphone rather than sharing it with `micro_wake_word`.

No input from a person is needed to run either branch.

## What is built

### On the board — `docker-compose.voice.yml`

| Service | Bind | Detail |
| --- | --- | --- |
| `wyoming-whisper` | `127.0.0.1:10300` | `base.en`, **`--compute-type int8`**, beam 1, `cpuset 0,1,6,7`, `mem_limit 2g` |
| `wyoming-piper` | `127.0.0.1:10200` | `en_US-lessac-medium`, `cpuset 8,9`, `mem_limit 512m` |

Loopback only; Home Assistant runs `network_mode: host`, so it reaches them.

`scripts/setup-ha-voice.py` wires both into Home Assistant and points the
default pipeline at them. Idempotent; dry run unless `--apply`.

Default pipeline "Home Assistant" is now: STT `stt.faster_whisper` (`en`), TTS
`tts.piper` (**`en_US`**), conversation `conversation.local_qwen`,
`prefer_local_intents` on.

**Home Assistant `internal_url` is set to `http://192.168.0.83:8123`.** It was
unset. See trap 9.

### The device — `configs/esphome/voice-panel.yaml`

| | |
| --- | --- |
| Board | Waveshare ESP32-S3-Touch-LCD-4B, `ESP32-S3-WROOM-1-N16R8`, 8 MB octal PSRAM |
| Firmware | ESPHome 2026.8.2 — **the device runs exactly what is committed** |
| Address | `192.168.0.58` (a DHCP lease), MAC `94:A9:90:DE:C0:18` |
| In HA as | "Voice Panel" |
| Display | **not configured, on purpose** — voice first (see the proposal) |

Entities: `assist_satellite.voice_panel_assist_satellite`,
`media_player.voice_panel_media`, `select.voice_panel_wake_word` ("Okay Nabu"),
`switch.voice_panel_audio_enable`, `binary_sensor.voice_panel_microphone_capturing`,
`binary_sensor.voice_panel_status`.

**Pin map**, read out of Waveshare's own demos
(`ESP32-S3-Touch-LCD-4B-Demos.zip` → `Mylibrary/pin_config.h` and the example
`.ino` files) rather than guessed:

```
I2S      MCLK 5   BCLK 16   LRCK 7   DIN 15 (mic, ES7210)   DOUT 6 (speaker, ES8311)
I2C      SDA 47   SCL 48
TCA9554  0x20, pin 3 = audio enable
```

The I2C scan confirms it: `0x14` GT911, `0x18` ES8311, `0x20` TCA9554, `0x34`,
`0x40` ES7210, `0x51` PCF85063, `0x6B` AXP2101.

**A speaker is fitted.** Waveshare's wiki says "MX1.25 2P Connector, supports
8Ω 2W Speaker" and a mirror says "connector only, no onboard speaker". Wrong for
this unit — the cover was opened and one is connected. A replacement was being
considered; the harshness found was clipping, not the transducer, so it may not
buy much.

**First flash** was from Windows via `web.esphome.io`: WSL cannot see the USB
port without `usbipd-win` attaching it. Everything since has been OTA.
`configs/esphome/secrets.yaml` (API key, OTA password) is git-ignored twice.
Wi-Fi was provisioned over `improv_serial`, so no network credentials exist in
the repo or the image.

### Measured, not estimated

| | |
| --- | --- |
| Whisper | 3.29 s of speech transcribed in **0.98 s** (0.30× real time), exactly, three runs |
| Whisper memory | **423 MB → 166 MB** with `int8` |
| Local intent | "what time is it" answered in **0.57 s** |
| Playback | 3.01 s clip → back to idle in **4.76 s** |
| Announce | `HTTP 200` in **7.1 s**, satellite returns to idle (was hanging 45 s+) |
| Volume | clean at DAC 0.8 and 0.9, harsh at 1.0 → dial set to **0.5 – 0.9** |

## Temporary diagnostics in the current firmware

**Reverted 2026-09-13:** `logger` is back to `DEBUG`. The VERBOSE setting never
showed anything about the wake word — `micro_wake_word` has no VERBOSE lines.

**Keep or drop, cheap either way:**

- `binary_sensor.voice_panel_microphone_capturing` — the first piece of hard
  evidence about the input side. Arguably worth keeping as a diagnostic.

## Thirteen traps from getting audio working

Each cost time. Several present as a different problem than they are.

1. **`esphome run` exits 0 on a failed config** after printing the config dump.
   A broken build reads as a successful one and the device quietly keeps the old
   firmware — several rounds were tested against stale firmware this way. Use
   `esphome config` or `compile` to see the error, and check the binary's mtime.
2. **Killing a log capture does not stop its container.** Seven accumulated, up
   to eight hours old, holding the build cache; nothing compiled until they were
   removed. Always `docker run --rm --name <n>` and `docker rm -f <n>` after.
3. **Home Assistant holds the API**, so an `esphome logs` client reconnects
   repeatedly. That is contention, not a crash — count `ESPHome version` boot
   banners before concluding the device is rebooting.
4. **The mic and speaker share one I2S bus on this board** (one MCLK/BCLK/LRCK for
   both codecs). They cannot run at once: `Parent bus is busy`, retrying once a
   second. It is wiring, not software. ESPHome's reference config stops the wake
   word around playback with the comment "Stops wake word if mic is capturing".
5. **Announcement and media pipelines cannot share a speaker** — a hard config
   error. A `mixer` owns the real output and hands each pipeline a source speaker.
6. **`media_player.play_media` needs a `media_pipeline`.** With only
   `announcement_pipeline` it sat in `playing` for ever and made no sound.
7. **`micro_wake_word` does not start itself.** A start inside `voice_assistant`'s
   `on_end` can never run, because no session can end that never began.
8. **Distortion only when loud is amplitude, not sample rate.** A rate too low
   sounds thin at every volume. The cause was `volume_multiplier: 2.0`, copied
   from ESPHome's reference device, which drives a different amplifier.
9. **HA's `internal_url` was unset**, so TTS URLs pointed at `172.17.0.1` — the
   Docker bridge, unreachable from the LAN. The device could not fetch its own
   speech. This breaks media delivery to *any* device, not just this one.
10. **Piper advertises `en_US`, not `en`.** A pipeline set to `en` refuses every
    announcement with a 500 that names nothing. Whisper does take `en`.
    `setup-ha-voice.py` now negotiates per engine.
11. **Wyoming leaves `unique_id` as `None`**, so Home Assistant adds the same host
    and port twice. The config entries API does not expose `data`, so the script
    matches on title.
12. **`start_conversation` transcribes the wake word as the command.** A run with
    no `wake_word-end` event was not started by the wake word.
13. **The add-ons do not exist here.** This is the Home Assistant container, not
    HA OS — no Supervisor, no add-on store. Wyoming services run directly.

## Open items

- **The wake word** — above.
- **Revert VERBOSE logging** once it works.
- ~~Stale duplicate entities~~ — **not stale.** `select.voice_panel_assistant_2`
  and `select.voice_panel_wake_word_2` have unique ids `…-pipeline_2` and
  `…-wake_word_2`: ESPHome's *second* wake word slot, set to `no_wake_word`. Leave
  them.
- **The device address is a DHCP lease.** Reserve `192.168.0.58` for
  `94:A9:90:DE:C0:18`, alongside the two already recorded in `configs/hosts.env`.
- **Push to GitHub.** Commits after `711785e` are local only.
- **Stage 4 of the proposal** (dashboard-control intents) and **the display** —
  not started, deliberately, until voice is boring.

## Everything else this session — finished

| | Where it is recorded |
| --- | --- |
| NPU docs corrected: the 09-08 blocker was solved on 09-08; four known-bad models moved to `~/npu-test/known-bad/` with a README | `docs/npu-model-pipeline.md`, `docs/local-ai.md` |
| Voice proposal written, then rebuilt around the ESP32-S3 board | `docs/voice-assistant-proposal.md` |
| Pi 4 fan unplugged; `resource-logger` now on the panel too, logging `throttled=`. Settled at 55–58 °C, peak 59 °C, **zero** throttling over 7 h | `deploy/systemd/user/resource-logger-rpi4.service` |
| Orange Pi fan: no OS control, no tachometer, `pwmchip0` unclaimed | `docs/handoff-2026-09-10-wall-panel.md` |
| **Board moved to Ethernet**, `192.168.0.83`: 0.78 ms to the router against 333 ms on Wi-Fi. **Both** Matter services were bound to the vanished `wlp1s0` — one a user unit, one a system unit | `CLAUDE.md`, `docs/matter-controller.md` |
| `configs/hosts.env` is the single source for addresses; a guard test forbids literals in code. Cameras use `go2rtc_url: auto` and need no address | `configs/hosts.env`, `tests/python/test_hosts_config.py` |
| DHCP reservation details — MACs, router, the **two-hour** lease | `configs/hosts.env` |
| **Home view fits the screen**: panel/PC three columns × 20 rows, tablets two × 14, phone stacked. Weather + Climate end level with Camera; Temperatures level with Security; the camera player fills its card | `tests/python/test_home_layout_fit.py` |
| Clicking an area wrecked the view — an id `display` rule outranked `[hidden]` | same test file |
| Layout defaults versioned, so a stored cell cannot outlive its table | `HOME_CARD_LAYOUT_VERSION` in `app.js` |

## Related

- `docs/voice-assistant-proposal.md` — why the design is shaped this way
- `docs/local-ai.md` — the conversation agents and why the LLM stays out of the voice path
- `configs/esphome/voice-panel.yaml` — every fix above is commented where it lives
