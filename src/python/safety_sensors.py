"""The house's leak and smoke sensors, and what to call them in an alert.

One list for both sides: scripts/install-safety-alerts.py builds the Home
Assistant rules from it, and the dashboard names the wet or smoky sensors in
its banner from it. Add a sensor here, then re-run the installer.

The Tuya copies (fire_alarm_detector, water_sensor, shui_jin_chuan_gan_qi) are
on the Tuya gateway and are kept on purpose: docs/restore-runbook.md says they
are real, and a copy that has gone stale cannot raise a false alarm - it just
never changes - while leaving out a live one could miss a leak.
"""
from __future__ import annotations

# binary_sensor -> where it is, as it reads in "Water at the boiler."
LEAK = {
    "binary_sensor.0xa4c138534cac048e_water_leak": "the washing machine",
    "binary_sensor.0xa4c138304954cd8d_water_leak": "the boiler",
    "binary_sensor.water_sensor_moisture": "the utility room (WATER SENSOR)",
    "binary_sensor.shui_jin_chuan_gan_qi_moisture": "the utility room",
}

SMOKE = {
    "binary_sensor.0xa4c138577961949d_smoke": "the family room",
    "binary_sensor.fire_alarm_detector_smoke": "the kitchen",
}

# Batteries worth a warning: a leak or smoke sensor that dies says nothing.
BATTERIES = {
    "sensor.0xa4c138534cac048e_battery": "Leak sensor, washing machine",
    "sensor.0xa4c138304954cd8d_battery": "Leak sensor, boiler",
    "sensor.water_sensor_battery": "WATER SENSOR, utility room",
    "sensor.shui_jin_chuan_gan_qi_battery": "Leak sensor, utility room",
    "sensor.0xa4c138577961949d_battery": "Smoke detector, family room",
    "sensor.fire_alarm_detector_battery": "Smoke detector, kitchen",
}
# Zigbee sensors that also say "low" themselves, below any percentage.
BATTERY_LOW = {
    "binary_sensor.0xa4c138534cac048e_battery_low": "Leak sensor, washing machine",
    "binary_sensor.0xa4c138304954cd8d_battery_low": "Leak sensor, boiler",
}
