# Night watch: clips and Telegram photos of night-time motion

Since 2026-09-25: `night-watch.service` (systemd *user* unit),
`src/python/night_watch.py`, launched by `scripts/run-night-watch.sh` in the NPU
detector's Python 3.11 environment (`~/npu-venv`: OpenCV and paho-mqtt).

Why: on 2026-09-25 the front door's outdoor motion sensor fired five times
between 02:22 and 02:33 and nothing could say what it was. The cameras watched;
nothing was kept.

## What sets it off

| Trigger (MQTT) | Camera recorded | Telegram photo |
| --- | --- | --- |
| Motion sensor and TH front door (`presence`) | `front_door_camera` | only if the clip shows movement |
| Motion sensor and TH Backyard, ... fence south (`presence`) | `wyze_camera` (backyard) | only if the clip shows movement |
| Vibration sensor backdoor (`vibration`) | `wyze_camera` | only if the clip shows movement |
| A person rising on `front_door_camera`, `frontyard_camera`, `garage_camera` | that camera, with the detector's boxes drawn | yes |
| **Alarm speaker** starts (`alarm`) - **day or night** | `office_camera` and `family_room_camera` | yes |
| A person rising on `office_camera` / `family_room_camera` | snapshot only, boxes drawn - **evidence**, see below | no |

Night is `NIGHT_WATCH_HOURS` in `.env` (default `22:00-06:30`). The first message
on a topic after (re)connecting is a baseline, not an event: retained messages
arrive on connect.

## A sensor alone is not believed (2026-09-25)

The front door's outdoor motion sensor fired **437 times in the week to 2026-09-25**, 88 of them
at night - and at night a camera person or the door opening agreed with it **3 times**. That
evening it sent five Telegram photos of an empty porch; the five clips show nothing moving in
20 s (only the camera's clock). A PIR by the door sees heat down the walkway and beyond what
the camera shows clearly, and weather.

So a motion or vibration sensor's trigger records the snapshot and clip as before, then
`movement_in_clip` checks the clip: the photo goes to Telegram only if the camera saw
something move (a moving blob of at least 0.8% of the picture, not a change of most of it -
headlights, night mode), and it is the frame of most movement, boxed. Without a clip the
snapshot is sent. A person seen by the camera's own detection is sent at once, as before.

## What it does

- Snapshot (go2rtc `frame.jpeg`) and a **20 s clip** (ffmpeg stream copy from
  go2rtc's local RTSP, no re-encoding, video only) under
  `~/night-clips/<date>/<HHMMSS>_<camera>_<reason>.jpg|.mp4`.
- The snapshot goes to Telegram, **at most once per trigger per 5 minutes** (a
  sensor firing every two minutes is one message, every picture still kept);
  one clip per camera per minute; three ffmpeg at once at most. A failed upload
  is retried once.
- Kept **14 days, 20 GB at most**, oldest first (`NIGHT_WATCH_KEEP_DAYS`,
  `NIGHT_WATCH_MAX_GB`).
- Telegram: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_IDS` in the board's `.env`
  (the chat id was taken from Home Assistant's Telegram integration, allowed
  chat "Jack Gu"). The token is never logged.
- Wi-Fi: the detector already holds these streams open in go2rtc, which shares
  one camera connection, so a clip adds no camera traffic. The backyard camera
  is not in the detector and is pulled only for its 20 s.

## The office camera's false "person" (2026-09-25)

The office camera reported a person 01:10-02:33 on 2026-09-25 with nobody there,
and almost all night on 09-16 and 09-17. The room is full of person-like shapes:
framed photos of people, a plush toy, and a black mesh office chair, which on
the infrared night picture reads as a seated torso. It matters to security: the
office camera is one of the intruder rule's first-floor sensors, so a false
person keeps "someone expected downstairs" alive while armed - or, on Away,
would sound the siren.

Two changes:

- **Motion gate on** for the office (`NPU_MOTION_CONFIRM_CAMERAS=front_door_camera,office_camera`):
  a person box under 75% confidence counts only where the picture changed in the
  last ~2 s. A still chair or photo fails; a person moving - or seen at 75%+ - passes.
- **Evidence snapshots** at night show every office detection with its box and
  confidence. If a false one is 75%+ the gate cannot stop it, and the pictures
  will say which object it is (then: a detection zone that leaves it out, or move it).

## Install / restore

```bash
cp deploy/systemd/user/night-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now night-watch
scripts/run-night-watch.sh --test front_door_camera   # one snapshot, clip and photo now
```
