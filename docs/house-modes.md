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
| Home again | A phone enters the home zone, or (Away only) an indoor PIR sees someone | Ambient lights on if the sun is down, only those that are off |
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
