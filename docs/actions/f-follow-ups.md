# F. Follow-ups and questions for the owner

Dated checks that were set up on 2026-09-25 and need a look later, and open
questions only the owner can answer.

| | When | What | Then |
|---|---|---|---|
| F1 | 2026-09-26 | The office camera's night evidence snapshots (`~/night-clips/<date>/*office_camera*`): boxes and confidences of anything it called a person | If false ones are 75%+, the motion gate cannot stop them: a detection zone without the chair, or move the chair |
| F2 | 2026-09-28 | The garage camera's watch-only log (`input_text.house_camera_would_have`, logbook "House mode (watch-only)") against the phone's arrivals and departures; car detection at night | Turn on `input_boolean.house_camera_signals`, or tune |
| F3 | first walk out past the garage | The log says "someone walked out past the garage" | If not, the direction axis is reversed: `NPU_INWARD=garage_camera=y-` |
| F4 | tonight onwards | Telegram photos from the outdoor cameras at night: any false "person" | That camera's zone or threshold |
| F5 | watch | Camera Wi-Fi: streams broke up 17:30-17:34 on 2026-09-25 (timeouts, corrupt frames) | If it recurs: the cameras' Wi-Fi (channel, signal, access point) |

## Questions

- **Q0** The GitHub repository `JackGukf/smart_home` is **public**. No secrets are in it, but it
  documents the alarm schedule, the intruder rule's blind spot, camera placement and - in
  `docs/actions/` - the open security gaps. Make it private (Settings -> General -> Danger Zone)?
  CI keeps working; anonymous API access to runs stops.

- **Q1** Which of the six leak and smoke sensors physically exist? Two smoke
  detectors (family room Zigbee, kitchen Tuya), four leak sensors (washing
  machine and boiler Zigbee, two utility room Tuya). Old Tuya copies of sensors
  that moved to Zigbee should be removed from `src/python/safety_sensors.py`.
- **Q2** Does the backyard camera (`wyze_camera`) see the south fence sensor's
  spot? The night watch assumes so.
- **Q3** The utility-room Tuya leak sensor's battery is at 26%: the health check
  warns below 20%.
