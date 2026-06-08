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

## Security Notes

- Do not commit passwords, tokens, camera credentials, or home Wi-Fi details.
- Keep camera access restricted to trusted local network devices.
- Use a separate IoT VLAN or guest network if your router supports it.
