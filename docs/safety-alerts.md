# Water leak and smoke alerts

Installed 2026-09-25 by `scripts/install-safety-alerts.py` (Home Assistant config
API, idempotent; `--apply` to write). The sensors are listed once, in
`src/python/safety_sensors.py` - add one there, then run the installer again. The
reasons behind each rule are in the installer's docstring.

## The sensors

| Kind | Where | Entity | On |
| --- | --- | --- | --- |
| Leak | washing machine | `binary_sensor.0xa4c138534cac048e_water_leak` | Zigbee |
| Leak | boiler | `binary_sensor.0xa4c138304954cd8d_water_leak` | Zigbee |
| Leak | utility room | `binary_sensor.water_sensor_moisture` ("WATER SENSOR") | Tuya gateway |
| Leak | utility room | `binary_sensor.shui_jin_chuan_gan_qi_moisture` | Tuya gateway |
| Smoke | family room | `binary_sensor.0xa4c138577961949d_smoke` | Zigbee |
| Smoke | kitchen | `binary_sensor.fire_alarm_detector_smoke` | Tuya gateway |

The Tuya ones are kept even if some turn out to be old copies of a sensor that
moved to Zigbee: a stale copy never changes, so it cannot raise a false alarm,
and leaving out a live one could miss a leak.

## What happens

| | Leak | Smoke |
| --- | --- | --- |
| Dashboard | red banner on every screen, naming where; **I know** clears it everywhere | same |
| iPhone | **critical** push (through mute and Focus), "I know" button | same |
| Telegram | every chat of the `telegram_bot` integration | same |
| Reminders while it stands | every 10 min, 3 at most | every 3 min, 5 at most |
| When all read clear again | one "Dry again at 14:32"; the banner stays until I know | one "Smoke cleared at 14:32"; same |

No siren and no lights: the detectors sound themselves. Say if either is wanted.

**Flapping.** The Tuya WATER SENSOR was wet for ~8 hours on 2026-09-20 while
dropping to `unavailable` and back about twenty times. An `unavailable -> on`
within 3 hours of the rule's last alert is treated as that, not news;
`off -> on` always alerts. **`unknown -> on` always alerts** - the Zigbee
detectors rest at `unknown` for days (they report only on a change), so that is
what their first report of smoke looks like.

## Sensor health

`safety_sensors_need_attention` sends an ordinary push and Telegram listing each
sensor whose battery is under 20% (or reports low), or that has been
`unavailable` for 6 hours - when it happens, and again at 10:00 every day until
it is fixed. `unknown` is not counted: that is how the Zigbee ones rest.

## Testing it

Press the test button on a smoke detector, or wet a leak sensor's contacts with
a damp cloth. The iPhone must allow critical alerts for the Home Assistant app
(Settings -> Notifications -> Home Assistant -> Critical Alerts); iOS asks the
first time one arrives.
