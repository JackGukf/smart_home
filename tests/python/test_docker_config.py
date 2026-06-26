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
