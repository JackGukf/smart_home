# Smart Home AI Project

This project area is for controlling and monitoring smart home devices from an Orange Pi 6 Plus using C/C++ and Python.

Target device examples:

- TP-Link/Kasa light switches and plugs
- Cameras: TP-Link/Tapo, Wyze, Chortau, and Tuya
- Tuya smart sensors
- Govee and Lepro ambient lights
- Ecobee thermostats and environment sensors
- Matter devices, in both directions: our devices exposed to Apple Home via the
  Matter bridge, and third-party Matter devices controlled from the dashboard
- Other LAN, Wi-Fi, MQTT, HTTP, or vendor API based devices

Home Assistant sits alongside these as a source of devices the dashboard can
read and control; it is optional and the dashboard degrades gracefully without it.

## Goals

- Build reusable device-control modules.
- Keep vendor integrations isolated behind clear interfaces.
- Prefer local network control where possible.
- Keep credentials and API keys out of source control.
- Support both quick Python automation and lower-level C/C++ services.

## Suggested Architecture

```text
Device adapters
  -> TP-Link/Kasa adapter
  -> Tuya adapter
  -> Camera adapter

Automation layer
  -> Schedules
  -> Sensor triggers
  -> Manual commands

Runtime services
  -> Python scripts for rapid automation
  -> C/C++ daemon for reliable always-on control
```

## First Setup Steps

1. Install Ubuntu 24.04 ARM64 on the Orange Pi 6 Plus.
2. Enable SSH.
3. Update packages:

   ```bash
   sudo apt update
   sudo apt upgrade
   ```

4. Install development tools:

   ```bash
   sudo apt install build-essential cmake git python3 python3-venv python3-pip
   ```

5. Copy `configs/devices.example.yaml` to a local ignored config file when you are ready to add real devices.

## Development Environment

The recommended development setup is Docker running in WSL, opened with Visual Studio Code Dev Containers.

Quick check:

```bash
cd ~/workspace/smart_home_AI
docker compose build dev
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart_home_AI
```

See `docs/docker-development.md` for IDE, build, and debug setup.

Run tests:

```bash
docker compose run --rm dev python3 -m pytest
docker compose run --rm dev sh -lc "cmake --preset docker-debug && cmake --build --preset docker-debug && ctest --test-dir build/docker-debug --output-on-failure"
```

## Orange Pi 6 Plus Deployment

Build and deploy from WSL:

```bash
cd ~/workspace/smart_home_AI
./scripts/build-orangepi6.sh
./scripts/deploy-to-pi.sh
```

See `docs/orangepi6-cross-compile-deploy.md` for the full workflow, including
the secondary Raspberry Pi 4 target, and `docs/setup-orangepi6.md` for the
verified board facts.

Connect to the configured board:

```bash
./scripts/connect-pi.sh
./scripts/connect-pi.sh --check
```

## TP-Link/Kasa Switch Control

Use the Python CLI to control a configured TP-Link/Kasa light switch:

```bash
python3 -m src.python.tplink_switch --host 192.168.1.10 status
python3 -m src.python.tplink_switch --host 192.168.1.10 on
python3 -m src.python.tplink_switch --host 192.168.1.10 off
python3 -m src.python.tplink_switch --host 192.168.1.10 toggle
```

See `src/python/README.md`.

## Web Dashboard

Run the local smart home dashboard:

```bash
python3 -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000
```

On the board's touch screen, open:

```text
http://localhost:8000
```

## Cameras

Camera streams are served through **go2rtc**, which holds a single connection per
camera and fans it out to the dashboard as WebRTC. Idle thumbnails come from the
same go2rtc session (`/api/frame.jpeg`) rather than a second RTSP connection,
because some cameras serve only one client at a time.

```bash
./scripts/run-go2rtc.sh                       # regenerates go2rtc.yaml, then runs it
python3 scripts/generate-go2rtc-config.py     # regenerate the config only
python3 scripts/probe-camera-services.py IP   # find a camera's ports and RTSP paths
```

`go2rtc/go2rtc.yaml` is generated from the `cameras:` section of
`configs/devices.local.yaml` plus credentials in `.env` — edit those, never the
generated file. Give every camera its own `username_env`/`password_env` pair:
vendors such as Wyze issue credentials per camera, not per account.

## Home Assistant and Matter

The dashboard reads Home Assistant entities and can control them, so devices
with no local protocol still get a card. Configure the connection under
`home_assistant:` in `configs/devices.local.yaml` and set `HOME_ASSISTANT_TOKEN`.

Matter runs in two independent directions, documented separately:

- `docs/matter-bridge.md` — our devices exposed to Apple Home
- `docs/matter-controller.md` — third-party Matter devices controlled here

Both share one Matter server, so a device commissioned into that fabric can be
reached either directly (`matter:<node_id>`) or through Home Assistant.

## Known Device Quirks

Vendor firmware changes have broken working devices more than once, and the
symptoms rarely name the real cause. `docs/setup-orangepi6.md` records each one
with the check that identifies it:

- **Container DNS** must be pinned, or Home Assistant reports a Tuya
  *authentication* failure that is really a dead resolver.
- **Tuya cameras** moved to an undocumented `cdsxj` category that Home Assistant
  does not map, producing a device with zero entities. Re-apply the fix with
  `./scripts/patch-ha-tuya-cdsxj-camera.sh` after any HA container rebuild.
- **Wyze RTSP** serves roughly one client at a time and its RTSP service can
  crash outright; a power-cycle restores it.
- **Newer TP-Link switches (S505)** negotiate TPAP encryption, which
  `python-kasa` does not implement — control them over Matter instead.

## Security Notes

- Do not commit passwords, tokens, camera credentials, or home Wi-Fi details.
- Keep camera access restricted to trusted local network devices.
- Use a separate IoT VLAN or guest network if your router supports it.


### Ambient light configuration

Govee Bluetooth strips need a BLE address discovered from the Orange Pi:

    python scripts/discover-govee-ble.py

Then add entries like this to configs/devices.local.yaml:

    ambient_lights:
      devices:
        - name: Govee H613A Strip
          provider: govee_ble
          model: H613A
          room: Living Room
          address: AA:BB:CC:DD:EE:FF
        - name: Govee H6054 Light
          provider: govee_ble
          model: H6054
          room: Bedroom
          address: AA:BB:CC:DD:EE:00
        - name: Lepro S1 AI LED
          provider: alexa
          model: Lepro S1 AI LED
          room: Studio
          alexa_name: Lepro S1 AI LED

Lepro S1 AI LED is shown in the Ambient view as Alexa-bridge required until an Alexa routine or bridge command path is configured.
