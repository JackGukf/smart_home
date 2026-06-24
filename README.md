# Smart Home Raspberry Pi 4 Project

This project area is for controlling and monitoring smart home devices from a Raspberry Pi 4 using C/C++ and Python.

Target device examples:

- TP-Link/Kasa light switches and plugs
- TP-Link cameras
- Tuya smart sensors
- Other LAN, Wi-Fi, MQTT, HTTP, or vendor API based devices

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

1. Install Raspberry Pi OS on the Pi 4.
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
cd ~/workspace/smart-home-rpi4
docker compose build dev
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart-home-rpi4
```

See `docs/docker-development.md` for IDE, build, and debug setup.

Run tests:

```bash
docker compose run --rm dev python3 -m pytest
docker compose run --rm dev sh -lc "cmake --preset docker-debug && cmake --build --preset docker-debug && ctest --test-dir build/docker-debug --output-on-failure"
```

## Raspberry Pi Deployment

For Raspberry Pi OS 64-bit, build and deploy from WSL:

```bash
cd ~/workspace/smart-home-rpi4
./scripts/build-rpi4.sh
./scripts/deploy-to-pi.sh
```

See `docs/rpi4-cross-compile-deploy.md`.

Connect to the configured Raspberry Pi:

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

On the Raspberry Pi touch screen, open:

```text
http://localhost:8000
```

## Security Notes

- Do not commit passwords, tokens, camera credentials, or home Wi-Fi details.
- Keep camera access restricted to trusted local network devices.
- Use a separate IoT VLAN or guest network if your router supports it.


### Ambient light configuration

Govee Bluetooth strips need a BLE address discovered from the Raspberry Pi:

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
