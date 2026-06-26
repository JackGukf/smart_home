# Docker Pi Deployment Design
**Date:** 2026-06-26
**Status:** Approved

## Overview

Add a Docker-based deployment option for the smart home dashboard alongside the existing systemd deployment. The goal is reproducibility: cloning the repo and running one setup script on a new Raspberry Pi 4 should bring up an identical environment. The existing rsync + systemd workflow is unchanged.

## Architecture

Three containers run on the Pi, all using `network_mode: host`:

```
Pi host network (no NAT)

  dashboard          matter-server         go2rtc
  :8000              :5580                 :1984 / :8554
  FastAPI/uvicorn    official image        official image

Bind mounts:
  ./configs/devices.local.yaml  → /app/configs/devices.local.yaml (dashboard, read-only)
  ./configs/go2rtc.yaml         → /config/go2rtc.yaml (go2rtc, read-only)

Named volumes:
  matter-data → /data  (CHIP SDK storage, persists across restarts)
```

**Why host networking for all three:**
- Matter Server requires mDNS multicast for WiFi device discovery — broken by bridge NAT
- Dashboard connects to `ws://localhost:5580` (Matter Server) and reaches TP-Link/Tuya devices by LAN IP — both require host network
- go2rtc reaches camera RTSP streams and exposes WebRTC ports — host is simplest

## Files

### New files (nothing existing is modified)

| File | Purpose |
|---|---|
| `Dockerfile.pi` | Lean production image for the dashboard — no dev/C++ tools |
| `docker-compose.pi.yml` | Production compose: dashboard + matter-server + go2rtc |
| `.env.example` | Secret variable template committed to the repo |
| `scripts/setup-pi-docker.sh` | One-time new-Pi setup script |

### Existing files (unchanged)

- `Dockerfile` — dev image for cross-compile and testing, untouched
- `docker-compose.yml` — dev compose, untouched
- `scripts/deploy-dashboard.sh` — systemd deploy, untouched

## Dockerfile.pi

Base image: `python:3.11-slim` (supports `linux/arm64` natively). No cross-compiler, no cmake, no test tooling.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY src/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/python/ ./src/python/
RUN useradd -m smarthome && chown -R smarthome /app
USER smarthome
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["uvicorn", "src.python.web_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`configs/` is NOT baked into the image — it is bind-mounted at runtime so secrets never enter the image layer.

## docker-compose.pi.yml

```yaml
services:
  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.pi
    image: smart-home-dashboard:latest
    container_name: smart-home-dashboard
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./configs:/app/configs:ro
    env_file: .env

  matter-server:
    image: ghcr.io/home-assistant-libs/python-matter-server:stable
    container_name: matter-server
    network_mode: host
    restart: unless-stopped
    volumes:
      - matter-data:/data

  go2rtc:
    image: ghcr.io/alexxit/go2rtc:latest
    container_name: go2rtc
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./configs/go2rtc.yaml:/config/go2rtc.yaml:ro

volumes:
  matter-data:
```

## .env.example

Committed to the repo. User copies to `.env` (git-ignored) and fills in values before first run.

```
# Tuya
TUYA_ACCESS_ID=
TUYA_ACCESS_SECRET=
TUYA_ENDPOINT=

# Home Assistant
HOME_ASSISTANT_URL=
HOME_ASSISTANT_TOKEN=

# Ecobee
ECOBEE_ACCESS_TOKEN=
ECOBEE_REFRESH_TOKEN=

# Dashboard auth
DASHBOARD_SECRET_KEY=changeme
```

## scripts/setup-pi-docker.sh

One-time setup for a new Pi. Run from the repo root.

Steps:
1. Verify `configs/devices.local.yaml` exists — exit with instructions if not
2. Verify `.env` exists — copy from `.env.example` and exit with instructions if not
3. Run `python3 scripts/generate-go2rtc-config.py` to produce `configs/go2rtc.yaml`
4. `docker compose -f docker-compose.pi.yml pull matter-server go2rtc`
5. `docker compose -f docker-compose.pi.yml build dashboard`
6. `docker compose -f docker-compose.pi.yml up -d`
7. Print dashboard URL

## New Pi Setup Workflow

```bash
# 1. Install Docker on the new Pi (one-time system dependency)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker smarthome
# log out and back in

# 2. Clone the repo
git clone git@github.com:JackGukf/smart_home.git
cd smart-home-rpi4

# 3. Copy config from old Pi (or create from example)
scp smarthome@<old-pi>:~/smart-home-rpi4/configs/devices.local.yaml configs/

# 4. Fill in secrets
cp .env.example .env
nano .env

# 5. Launch everything
bash scripts/setup-pi-docker.sh
```

After this, `docker compose -f docker-compose.pi.yml` manages the stack. `restart: unless-stopped` means all three services start automatically on Pi reboot.

## Updating an Existing Docker Pi

When new code is pushed:

```bash
git pull
docker compose -f docker-compose.pi.yml build dashboard
docker compose -f docker-compose.pi.yml up -d
```

Matter Server and go2rtc update by pulling the latest image:

```bash
docker compose -f docker-compose.pi.yml pull matter-server go2rtc
docker compose -f docker-compose.pi.yml up -d
```

## Data Persistence

| Data | Storage | Survives container restart? | Survives Pi reboot? |
|---|---|---|---|
| Matter device pairings | `matter-data` named volume | ✅ | ✅ |
| Device config | `configs/devices.local.yaml` (bind mount) | ✅ | ✅ |
| go2rtc config | `configs/go2rtc.yaml` (bind mount) | ✅ | ✅ |
| Dashboard session secrets | `.env` (bind via env_file) | ✅ | ✅ |

## Out of Scope

- Building a multi-arch image for CI (amd64 + arm64) — run `docker compose build` directly on the Pi for now
- Docker Swarm or Kubernetes — single-Pi deployment only
- Automated secret rotation
- Centralised log collection
