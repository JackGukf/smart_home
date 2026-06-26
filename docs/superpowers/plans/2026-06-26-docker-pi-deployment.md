# Docker Pi Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Docker-based deployment option so a new Raspberry Pi 4 can run the full smart home stack (dashboard + Python Matter Server + go2rtc) with `git clone` + one setup script.

**Architecture:** Four new files only — `Dockerfile.pi` (lean production image), `docker-compose.pi.yml` (three-service stack), `.env.example` (secrets template), and `scripts/setup-pi-docker.sh` (new-Pi bootstrap). All three services use `network_mode: host` for mDNS and LAN access. The existing `Dockerfile` and `docker-compose.yml` are untouched.

**Tech Stack:** Docker, Docker Compose v2, `python:3.11-slim` base image, `ghcr.io/home-assistant-libs/python-matter-server:stable`, `ghcr.io/alexxit/go2rtc:latest`, PyYAML (for tests), bash.

## Global Constraints

- Base image: `python:3.11-slim` (supports `linux/arm64` natively for Pi 4)
- All three services must use `network_mode: host`
- All three services must use `restart: unless-stopped`
- Dashboard service must use `env_file: .env`
- Matter Server volume mount: `matter-data:/data` (CHIP SDK hardcoded path)
- go2rtc config mount: `./configs/go2rtc.yaml:/config/go2rtc.yaml:ro`
- Dashboard configs mount: `./configs:/app/configs:ro`
- Dashboard runs as non-root user `smarthome` inside the container
- `PYTHONPATH=/app` and `PYTHONUNBUFFERED=1` set in dashboard image
- `.env.example` must be committed; `.env` is already git-ignored
- Existing `Dockerfile`, `docker-compose.yml`, and all deploy scripts: do NOT modify
- Test baseline: 4 pre-existing failures, 99 passing — must stay unchanged after each task

## File Map

| File | Action |
|---|---|
| `Dockerfile.pi` | Create |
| `docker-compose.pi.yml` | Create |
| `.env.example` | Create |
| `scripts/setup-pi-docker.sh` | Create |
| `tests/python/test_docker_config.py` | Create (structural tests for all four files) |

---

### Task 1: Dockerfile.pi

**Files:**
- Create: `Dockerfile.pi`
- Create: `tests/python/test_docker_config.py` (Dockerfile tests only — later tasks append to this file)

**Interfaces:**
- Produces: `smart-home-dashboard:latest` image that runs `uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000` as user `smarthome`

- [ ] **Step 1: Write failing tests for Dockerfile.pi**

Create `tests/python/test_docker_config.py`:

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PI = PROJECT_ROOT / "Dockerfile.pi"


def test_dockerfile_pi_exists():
    assert DOCKERFILE_PI.exists()


def test_dockerfile_pi_uses_slim_python():
    content = DOCKERFILE_PI.read_text()
    assert "FROM python:3.11-slim" in content


def test_dockerfile_pi_runs_as_non_root():
    content = DOCKERFILE_PI.read_text()
    assert "USER smarthome" in content


def test_dockerfile_pi_sets_pythonpath():
    content = DOCKERFILE_PI.read_text()
    assert "PYTHONPATH=/app" in content


def test_dockerfile_pi_starts_uvicorn():
    content = DOCKERFILE_PI.read_text()
    assert "uvicorn" in content
    assert "src.python.web_app:app" in content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/python/test_docker_config.py -v
```

Expected: 5 failures (`Dockerfile.pi` does not exist yet).

- [ ] **Step 3: Create Dockerfile.pi**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY src/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/python/ ./src/python/

RUN useradd -m smarthome && chown -R smarthome /app
USER smarthome

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["uvicorn", "src.python.web_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/python/test_docker_config.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Verify full test suite is unaffected**

```bash
python3 -m pytest tests/python/ 2>&1 | tail -3
```

Expected: `4 failed, 104 passed` (the 5 new tests + 99 pre-existing passing tests, same 4 pre-existing failures).

- [ ] **Step 6: Commit**

```bash
git add Dockerfile.pi tests/python/test_docker_config.py
git commit -m "feat: add production Dockerfile.pi for Pi deployment"
```

---

### Task 2: docker-compose.pi.yml and .env.example

**Files:**
- Create: `docker-compose.pi.yml`
- Create: `.env.example`
- Modify: `tests/python/test_docker_config.py` — append compose and env tests

**Interfaces:**
- Consumes: `Dockerfile.pi` from Task 1 (referenced as `dockerfile: Dockerfile.pi` in compose)
- Produces: validated compose stack definition; `.env.example` template for secrets

- [ ] **Step 1: Append failing tests to test_docker_config.py**

Add these imports at the top of `tests/python/test_docker_config.py` (after the existing `from pathlib import Path` line):

```python
import yaml
```

Add these constants after `DOCKERFILE_PI`:

```python
COMPOSE_PI = PROJECT_ROOT / "docker-compose.pi.yml"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
```

Append these test functions at the end of `tests/python/test_docker_config.py`:

```python
def test_compose_pi_has_required_services():
    compose = yaml.safe_load(COMPOSE_PI.read_text())
    services = compose["services"]
    assert "dashboard" in services
    assert "matter-server" in services
    assert "go2rtc" in services


def test_compose_pi_all_services_use_host_network():
    compose = yaml.safe_load(COMPOSE_PI.read_text())
    for name, svc in compose["services"].items():
        assert svc.get("network_mode") == "host", f"{name} must use network_mode: host"


def test_compose_pi_all_services_restart_unless_stopped():
    compose = yaml.safe_load(COMPOSE_PI.read_text())
    for name, svc in compose["services"].items():
        assert svc.get("restart") == "unless-stopped", f"{name} must restart unless-stopped"


def test_compose_pi_dashboard_uses_env_file():
    compose = yaml.safe_load(COMPOSE_PI.read_text())
    assert compose["services"]["dashboard"].get("env_file") == ".env"


def test_compose_pi_matter_server_mounts_named_volume():
    compose = yaml.safe_load(COMPOSE_PI.read_text())
    svc = compose["services"]["matter-server"]
    volumes = svc.get("volumes", [])
    assert any("matter-data" in str(v) for v in volumes)


def test_compose_pi_defines_matter_data_volume():
    compose = yaml.safe_load(COMPOSE_PI.read_text())
    assert "matter-data" in compose.get("volumes", {})


def test_env_example_has_required_keys():
    content = ENV_EXAMPLE.read_text()
    for key in [
        "TUYA_ACCESS_ID",
        "TUYA_ACCESS_SECRET",
        "HOME_ASSISTANT_URL",
        "HOME_ASSISTANT_TOKEN",
        "DASHBOARD_SECRET_KEY",
    ]:
        assert key in content, f".env.example missing {key}"
```

- [ ] **Step 2: Run tests to confirm new ones fail**

```bash
python3 -m pytest tests/python/test_docker_config.py -v
```

Expected: 5 pass (Dockerfile tests), 7 fail (compose and env tests — files don't exist yet).

- [ ] **Step 3: Create docker-compose.pi.yml**

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

- [ ] **Step 4: Create .env.example**

```
# Tuya cloud
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

- [ ] **Step 5: Run tests to confirm all pass**

```bash
python3 -m pytest tests/python/test_docker_config.py -v
```

Expected: 12 passed.

- [ ] **Step 6: Verify full test suite is unaffected**

```bash
python3 -m pytest tests/python/ 2>&1 | tail -3
```

Expected: `4 failed, 111 passed`.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.pi.yml .env.example tests/python/test_docker_config.py
git commit -m "feat: add docker-compose.pi.yml and .env.example for Pi deployment"
```

---

### Task 3: scripts/setup-pi-docker.sh

**Files:**
- Create: `scripts/setup-pi-docker.sh`
- Modify: `tests/python/test_docker_config.py` — append script tests

**Interfaces:**
- Consumes: `docker-compose.pi.yml` (Task 2), `.env.example` (Task 2), `scripts/generate-go2rtc-config.py` (pre-existing)
- Produces: executable setup script; new Pi can run `bash scripts/setup-pi-docker.sh` to start all services

- [ ] **Step 1: Append failing tests to test_docker_config.py**

Add this constant after `ENV_EXAMPLE`:

```python
SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "setup-pi-docker.sh"
```

Append these test functions at the end of `tests/python/test_docker_config.py`:

```python
def test_setup_script_exists():
    assert SETUP_SCRIPT.exists()


def test_setup_script_is_executable():
    import os
    assert os.access(SETUP_SCRIPT, os.X_OK), "setup-pi-docker.sh must be executable"


def test_setup_script_checks_for_devices_yaml():
    content = SETUP_SCRIPT.read_text()
    assert "devices.local.yaml" in content


def test_setup_script_checks_for_env_file():
    content = SETUP_SCRIPT.read_text()
    assert ".env" in content


def test_setup_script_calls_generate_go2rtc():
    content = SETUP_SCRIPT.read_text()
    assert "generate-go2rtc-config.py" in content


def test_setup_script_uses_pi_compose_file():
    content = SETUP_SCRIPT.read_text()
    assert "docker-compose.pi.yml" in content
```

- [ ] **Step 2: Run tests to confirm new ones fail**

```bash
python3 -m pytest tests/python/test_docker_config.py -v
```

Expected: 12 pass, 6 fail (script does not exist).

- [ ] **Step 3: Create scripts/setup-pi-docker.sh**

```bash
#!/usr/bin/env bash
# One-time setup for a new Pi using Docker deployment.
# Run from the repository root after cloning and copying configs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "==> Checking prerequisites..."
if [[ ! -f configs/devices.local.yaml ]]; then
  echo "ERROR: configs/devices.local.yaml not found."
  echo "Copy it from your existing Pi:"
  echo "  scp smarthome@<old-pi>:~/smart-home-rpi4/configs/devices.local.yaml configs/"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Edit it with your secrets, then re-run this script:"
  echo "  nano .env"
  exit 1
fi

echo "==> Generating go2rtc config..."
python3 scripts/generate-go2rtc-config.py

echo "==> Pulling images..."
docker compose -f docker-compose.pi.yml pull matter-server go2rtc

echo "==> Building dashboard image..."
docker compose -f docker-compose.pi.yml build dashboard

echo "==> Starting services..."
docker compose -f docker-compose.pi.yml up -d

echo ""
echo "==> Done. Services running:"
docker compose -f docker-compose.pi.yml ps

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo ""
echo "Dashboard: http://${PI_IP}:8000"
```

- [ ] **Step 4: Make it executable**

```bash
chmod +x scripts/setup-pi-docker.sh
```

- [ ] **Step 5: Run tests to confirm all pass**

```bash
python3 -m pytest tests/python/test_docker_config.py -v
```

Expected: 18 passed.

- [ ] **Step 6: Verify full test suite is unaffected**

```bash
python3 -m pytest tests/python/ 2>&1 | tail -3
```

Expected: `4 failed, 117 passed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/setup-pi-docker.sh tests/python/test_docker_config.py
git commit -m "feat: add setup-pi-docker.sh for new Pi bootstrap"
```

---

## New Pi Setup (post-implementation reference)

```bash
# 1. Install Docker on the new Pi (one-time)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker smarthome
# log out and back in

# 2. Clone the repo
git clone git@github.com:JackGukf/smart_home.git
cd smart-home-rpi4

# 3. Copy config from old Pi
scp smarthome@<old-pi>:~/smart-home-rpi4/configs/devices.local.yaml configs/

# 4. Fill in secrets
cp .env.example .env && nano .env

# 5. Launch everything
bash scripts/setup-pi-docker.sh
```

## Updating the Docker stack on a Pi

```bash
git pull
# Rebuild dashboard after code changes:
docker compose -f docker-compose.pi.yml build dashboard && docker compose -f docker-compose.pi.yml up -d
# Update Matter Server or go2rtc to latest image:
docker compose -f docker-compose.pi.yml pull matter-server go2rtc && docker compose -f docker-compose.pi.yml up -d
```
