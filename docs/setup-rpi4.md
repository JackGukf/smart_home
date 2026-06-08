# Raspberry Pi 4 Setup Notes

## Base System

```bash
sudo apt update
sudo apt upgrade
sudo apt install build-essential cmake git python3 python3-venv python3-pip
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

Use `scripts/deploy-to-pi.ps1` from Windows or a Git pull from the Raspberry Pi once the project is in a repository.
