import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PI = PROJECT_ROOT / "Dockerfile.pi"
COMPOSE_PI = PROJECT_ROOT / "docker-compose.pi.yml"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


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
