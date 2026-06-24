from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_systemd_service_restarts_and_uses_project_runner() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "smart-home-dashboard.service").read_text(encoding="utf-8")

    assert "WorkingDirectory=/home/smarthome/smart-home-rpi4" in unit
    assert "User=" not in unit
    assert "Group=" not in unit
    assert "ExecStart=/home/smarthome/smart-home-rpi4/scripts/run-dashboard.sh" in unit
    assert "Restart=always" in unit
    assert "Environment=HOST=0.0.0.0" in unit
    assert "Environment=PORT=8000" in unit


def test_go2rtc_systemd_service_restarts_and_uses_project_runner() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "go2rtc.service").read_text(encoding="utf-8")

    assert "After=network-online.target" in unit
    assert "Wants=network-online.target" in unit
    assert "WorkingDirectory=/home/smarthome/smart-home-rpi4" in unit
    assert "ExecStart=/home/smarthome/smart-home-rpi4/scripts/run-go2rtc.sh" in unit
    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit

def test_deploy_script_restarts_user_systemd_service_without_old_process_runner() -> None:
    script = (PROJECT_ROOT / "scripts" / "deploy-dashboard.sh").read_text(encoding="utf-8")

    assert "systemctl --user restart smart-home-dashboard.service" in script
    assert "systemctl --user restart go2rtc.service" in script
    assert '"${PROJECT_ROOT}/scripts/run-go2rtc.sh"' in script
    assert "pkill -f uvicorn" not in script
    assert "nohup bash -c" not in script


def test_install_script_uses_resolved_user_home_and_project_root_paths() -> None:
    script = (PROJECT_ROOT / "scripts" / "install-dashboard-service.sh").read_text(encoding="utf-8")

    assert 'RUN_USER="$(id -un)"' in script
    assert 'USER_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"' in script
    assert 'export HOME="${USER_HOME}"' in script
    assert 'UNIT_TARGET_DIR="${USER_HOME}/.config/systemd/user"' in script
    assert 'systemctl --user restart "${service_name}"' in script
    assert 'sudo ' not in script
    assert 'chmod +x "${PROJECT_ROOT}/scripts/run-dashboard.sh"' in script

def test_install_script_installs_and_enables_go2rtc_service() -> None:
    script = (PROJECT_ROOT / "scripts" / "install-dashboard-service.sh").read_text(encoding="utf-8")

    assert "SERVICE_NAMES=(" in script
    assert '"smart-home-dashboard.service"' in script
    assert '"go2rtc.service"' in script
    assert 'chmod +x "${PROJECT_ROOT}/scripts/run-go2rtc.sh"' in script
    assert 'systemctl --user enable "${service_name}"' in script
    assert 'systemctl --user restart "${service_name}"' in script
