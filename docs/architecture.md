# Architecture Notes

## Device Integration Strategy

Keep each vendor integration separate:

- `tplink` for TP-Link/Kasa devices
- `tuya` for Tuya sensors and devices
- `camera` for camera-related capture and status checks
- `automation` for rules, schedules, and event handling

## Runtime Options

Python is best for:

- Fast device discovery
- Experiments
- Scheduled scripts
- API integration

C/C++ is best for:

- Long-running local services
- Lower memory overhead
- GPIO or native hardware integration
- Performance-sensitive event handling

## Event Flow

```text
Sensor or schedule event
  -> automation rule
  -> device adapter command
  -> status logging
```
