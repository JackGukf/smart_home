# House modes: Away, Home again, Vacation, night arming

Installed 2026-09-24 by `scripts/install-house-modes.py` (Home Assistant config
API, idempotent; `--apply` to write). The rules themselves and every reason
behind them are in that script's docstring; this page is what to know around it.

## The mode

`input_select.house_mode` - **Home**, **Away** or **Vacation**. Presence sets
it, and so can a person, in Home Assistant: the actions follow the *change of
mode*, so picking Vacation by hand before a trip does what 24 hours away would,
and picking Home by hand ends a vacation exactly as arriving does.

| Mode | Entered when | What happens |
| --- | --- | --- |
| Away | Every tracked phone out of `zone.home` (5 min) **and** no indoor sensor has seen anyone for 15 min | All lights off (`script.panel_all_lights_off`, follows Manage); living room light on sunset–23:30 |
| Home again | A phone enters the home zone, or (Away only, and Away for 10 min at least) an indoor PIR sees someone - or Home picked by hand | Ambient lights on if the sun is down, only those that are off (`house_mode_coming_home`, on the mode change) |
| Vacation | Away for 24 h (`input_datetime.house_away_since`), or picked by hand | As Away, plus alarm **armed away** and an ecobee vacation (15 °C heat, 28 °C cool, 60 days) |
| Back from Vacation | Phone arrives, or Home picked by hand | Alarm disarmed if armed away; ecobee vacation deleted |

Alarm, independent of the mode (not on Vacation):

- **01:30 - 06:30:** armed **home** once no first-floor sensor has seen anyone
  for 15 min. The Tuya panel has Arm home and Arm away only, no night mode. The
  family room radar holds "occupied" ~30 min after the last movement, so a late
  evening arms at ~02:00.
- **07:00:** disarmed if armed home.

The owner's choices (2026-09-24): phones **and** no motion decide "empty";
disarm on arrival from a vacation; living room sunset–23:30 while away; ambient
lights on arrival only in the dark.

## On the dashboard (Security view)

The **House mode** card, top of the right column, shows the mode, whether it
was set automatically or by hand (a person's change carries a `user_id` in its
context; an automation's does not) and since when. Every mode can be picked
by hand, on top of the automatic rules:

- **Home / Away / Vacation** set `input_select.house_mode`
  (`POST /api/house-mode/{home,away,vacation}`). The actions follow the change,
  so this does exactly what presence would. Away and Vacation ask first.
- **Night arm / Morning disarm** run the two timed rules now
  (`POST /api/house-mode/{night_arm,morning_disarm}` → `automation.trigger`
  with `skip_condition`), found by their config id, not their entity id, which
  Home Assistant derives from the alias.

The mode rides in `/api/alarm` as `house_mode`, so the card needs no polling of
its own; it is absent until `install-house-modes.py --apply` has run.

Motion ends an Away only after it has lasted 10 minutes: Away picked by hand
on the way out would otherwise be undone by the entry sensor at the door.

## The garage camera as a second witness (2026-09-25, watch-only)

The phone was the only way the house knew it had been left, and on 2026-09-25 it
had not reported since 12:30 (location *When in use*), so an afternoon out never
became Away. The garage camera now counts too, **OR** with the phones:

| Signal | From | Means |
| --- | --- | --- |
| The car left the driveway | `binary_sensor.garage_camera_npu_car` on -> off, after 10 min parked | someone just left |
| Someone walked out | `sensor.garage_camera_npu_person_direction` -> `outward` (towards the street) | someone just left |
| A car parked in the empty driveway | car off (5 min at least) -> on, Away for 10 min | someone is home |

- "Someone just left" lasts 30 minutes, and **Away still needs the house still for 15**:
  the camera cannot tell who left (one of several driving off, a guest walking out).
- A car arriving ends **Away, never Vacation** - ending a Vacation disarms the alarm,
  and any car can pull into the driveway.
- Only the garage camera watches `car` (`NPU_CLASS_OVERRIDES=garage_camera=person+car`
  in the board's `.env`; every other camera keeps `NPU_CLASSES=person`, so the front
  yard's view of the street logs no passing cars). A camera that stops watching a class
  has that class's entities removed from Home Assistant when the detector starts.
  The detector knows the street is up the frame (`NPU_INWARD=garage_camera=y+`).
  Only `person` is an occupancy sensor, so a parked car never reads as someone home on
  the Security or Status views or in the house learning.
- **Watch-only** until `input_boolean.house_camera_signals` is turned on (the owner's
  choice, for three days from 2026-09-25): until then each would-be change is written to
  `input_text.house_camera_would_have` and the logbook, and the mode is left alone.
  To review: the logbook ("House mode (watch-only)"), or the house memory's history of
  that helper against `zone.home`. To go live: turn the helper on in Home Assistant.
- Unmeasured before this: car detection at night on the camera's infrared picture, and
  a parked car hidden by a person or heavy rain for over a minute (the detector holds
  a sighting 60 s). Both would show as a false "car left" in the watch-only log.

## The disarm PIN (2026-09-25)

Signing in - or being the wall panel, whose address is its login - was enough
to disarm the house. With `security.disarm_pin` in `devices.local.yaml`
(4-8 digits, **quoted**: YAML reads `0123` unquoted as the octal number 83), the
dashboard asks for it on a keypad before anything that lowers the alarm:

| Asks | Never asks |
| --- | --- |
| Disarm | Arm home, Arm away, Night arm |
| Morning disarm | Away, Vacation |
| Home, while the mode is Vacation (it disarms), or when HA cannot say the mode | Home from Away; Stop on the alarm speaker (the bedroom button stops it without one) |

- **The board checks it** (`_check_disarm_pin` in `web_app.py`); the page is told only
  *whether* one is needed (`disarm_pin` in `/api/alarm`). Read at every request, so
  setting or changing it needs no restart.
- **Five wrong PINs** from one address lock that address out for 15 minutes. That
  includes the wall panel: an intruder at the panel cannot guess, and the owner
  still has the phone.
- A PIN set wrongly (unquoted, too short, not digits) **refuses to disarm** with a
  message saying so, rather than quietly switching the check off.
- Every attempt is in the audit log, never the digits:
  `journalctl --user -u smart-home-dashboard | grep audit`.
- **Not covered:** Home Assistant itself, the Smart Life app and the Tuya panel's own
  keypad can still disarm without it. The PIN guards the dashboard, which is where
  the wall panel and the trusted address are.

## What it needs to work

- **The iPhone must report in the background.** The HA app's location
  permission was *When in use* on 2026-09-24 - with that, leaving and arriving
  are only seen when the app is open. iOS Settings → Home Assistant → Location
  → **Always**, and Precise on.
- **The iPhone must reach Home Assistant away from home**, or the zone exit is
  never delivered: Tailscale on the phone, set to stay connected (on-demand),
  and the app's external URL `http://orangepi6.tail9804d9.ts.net:8123`
  (`docs/tailscale.md`).
- **Every resident's phone**, for Away to mean empty rather than "Jack is out".
  Only `person.jack_gu` is tracked; the motion condition is what protects
  anyone at home without a tracked phone. Adding a phone is the HA app plus a
  person - `zone.home` counts people, so nothing here changes.
- **The alarm is Tuya cloud** (`alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji`).
  If Tuya's cloud is down the arm and disarm calls fail; the vacation actions
  carry on past that (`continue_on_error`), the night rule does not retry.

## Interactions

- `living_room_off_late_and_quiet` (`install-living-room-lighting.py`) now skips
  Away and Vacation, or it would put the away light out at 23:00 instead of
  23:30. Its other rules need no change - nobody is moving when away.
- Indoor sensors counted: living room, kitchen/family room, entry, downstairs
  (illumination), upstairs, bedroom (PIR), family room and master bedroom
  (radar). Front door TH, backyard and fence south are outdoors and ignored. A
  sensor that is `unavailable` counts as quiet, so a dead one cannot pin the
  house at Home for ever.
- Arrival by motion uses the PIR sensors only - the radar ones can report
  someone for half an hour after nobody. Motion never ends a Vacation: an
  armed house seeing someone is the alarm's business.

## While the alarm is armed (`scripts/install-security-response.py`)

Installed 2026-09-24, beside the modes.

- **The alarm speaker** (`switch.0xa4c1382b1f1bd155_alarm`, Zigbee, living
  room) sounds for 300 s when, while armed, a first-floor PIR or the family
  room / office camera sees someone **unexpected**. Away or Vacation: anyone.
  Home: not someone who came down the stairs (upstairs sensor in the last 3
  min) or was downstairs when the alarm armed - they stay expected for 30 min
  after their last movement downstairs (`input_datetime.security_expected_until`).
  Not in the first 2 min after arming. Never the radar sensors.
  What set it off goes to `input_text.security_alarm_reason`.
- **Stopping it:** the dashboard shows a red banner on every view and on the
  Security view (`POST /api/alarm/speaker/stop`); one press of the bedroom smart
  button; or the speaker's own timeout.
- **Bedroom button:** once = stop the speaker, twice = Night arm. The two
  automations that used it for the master bedroom light
  (`npu_bedroom_button_single_on` / `_double_off`) were deleted.
- **While armed · outdoors**, a log on the Security view
  (`house_memory.armed_log`): the outdoor cameras' person detection and the
  outdoor motion sensors, only while the alarm was armed, plus every time the
  speaker sounded; the last 7 days. The garage camera counts its **driveway
  only** (`NPU_ZONES` in the board's `.env`, `docs/local-ai.md`) - it also sees
  the street.

**The alarm has its own schedule.** The house memory shows it armed *away* at
01:30 and disarmed at 07:00 on 2026-09-22, 23 and 24, from outside Home
Assistant (most likely the Smart Life app). So at night the panel says
"armed away" with the family asleep upstairs - the reason "unexpected" follows
the house mode, not the arm type. Our Night arm (arm *home*) then finds the
alarm already armed and does nothing. Keep one of the two schedules.
