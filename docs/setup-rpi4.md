# Raspberry Pi 4 Setup Notes

## Base System

```bash
sudo apt update
sudo apt upgrade
sudo apt install build-essential cmake git openssh-server python3 python3-venv python3-pip rsync
sudo systemctl enable --now ssh
```

## Optional Packages

```bash
sudo apt install mosquitto mosquitto-clients
```

## Recommended Services

- SSH for remote development
- MQTT broker if you want local event messaging
- A systemd service for always-on controller code

## Deployment Idea

Use `scripts/deploy-to-pi.sh` from WSL to cross-compile in Docker and deploy over SSH.

See `docs/rpi4-cross-compile-deploy.md`.
