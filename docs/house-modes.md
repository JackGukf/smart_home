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
