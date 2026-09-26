# A. Safety and security

## A1 External heartbeat
◐ · both · S

**Progress 2026-09-25.** Service chosen: healthchecks.io, alerting on its own Telegram bot.
`heartbeat.timer` (every 5 min) runs `src/python/heartbeat.py` with the system python3:
a normal ping with the service watchdog's report, or `/fail` when the watchdog gave up
on something or stopped running. Installed and enabled on the board; sends nothing until
`HEALTHCHECKS_PING_URL` is in the board's `.env`.

**Why.** Everything that watches the house runs on the board: the service
watchdog, the alerts, Telegram. If the board dies, loses power or loses the
internet, nothing says so. The 20-hour Zigbee hang of 2026-09-23 is caught now;
a dead board is not.

**Do.** The board pings an outside service every 5 minutes (a systemd timer);
the service alerts the owner (Telegram / email / push) when the pings stop. The
ping carries a one-line health summary (the watchdog's status) so a failing
check can also fail the ping.

**Done when.** Unplugging the board's network produces an alert on the phone
within ~10 minutes, and plugging it back in a "back up" message; the setup is in
`docs/` and survives a restore.

**Owner.** Pick the service and create the account (it gives the ping URL).

## A2 Intrusion: critical push and escalation
☐ · Claude · S

**Why.** When the intruder rule sounds the alarm speaker, the only messages are
the night watch's Telegram photos. There is no critical iPhone push (smoke and
leak have one), and if nobody reacts nothing escalates.

**Do.** On the siren: a critical push naming the sensor, with "Stop" and "I know";
after 2 minutes unacknowledged, repeat and message a second person (Telegram chat
or phone number, owner's choice).

**Done when.** A simulated intrusion (as the smoke test was) reaches the phone
through silent mode, and an unanswered one escalates.

## A3 An alarm the house owns
☐ · both · L

**Why.** The Tuya panel is armed at 01:30 and disarmed at 07:00 by a Smart Life
schedule outside Home Assistant, and can be disarmed from the Smart Life app or
its own keypad without the dashboard PIN. The Tuya cloud subscription has also
expired.

**Do.** Move arming policy into Home Assistant (`manual` alarm panel or Alarmo):
Home / Away / Night modes, entry and exit delays, PIN on every disarm path Home
Assistant controls; the Tuya panel becomes a siren and sensors. The owner removes
the Smart Life schedule.

**Done when.** One alarm state, in Home Assistant, that the dashboard, the Voice
Panel and the house modes all use; no arming or disarming happens outside it.

## A4 The stairs sensor
☐ · both · S

**Why.** On 2026-09-25 someone went upstairs at ~02:33 and the stairs sensor
(`binary_sensor.0xa4c138ae6a275f0f_presence`) did not see it (last change 00:59).
The intruder rule treats "came down the stairs" as "family" — if it misses people
coming down too, a family member downstairs after the 30-minute window sets the
siren off.

**Do.** Measure its hit rate from the house memory (stairs vs bedroom radar vs
first-floor sensors); the owner checks its mounting / angle; if it is unreliable,
add a second sensor or use the bedroom radar as a second witness.

**Done when.** Ten walks down the stairs are ten detections.

## A5 Freeze and furnace-failure alert
☐ · Claude · S

**Why.** A furnace that fails in a Vancouver winter is found when the house is
cold. The ecobee already reports `equipment_running` and the temperatures.

**Do.** Alert when the indoor temperature falls below 12 °C, or heat has been
called for an hour without the temperature rising. Same channels as the leak alert.

**Done when.** Both rules installed from a script, tested by rendering, and
documented; `waiting_for_heating` in September is not a false alarm.

## A6 SSH hardening
☐ · Owner · S

`PermitRootLogin yes` is set and passwords are accepted. On the board:
`/etc/ssh/sshd_config.d/10-hardening.conf` with `PermitRootLogin no` and
`PasswordAuthentication no`, then `sudo sshd -t && sudo systemctl reload ssh` —
after every machine that logs in has a key (`ssh-copy-id`), keeping a session open.
