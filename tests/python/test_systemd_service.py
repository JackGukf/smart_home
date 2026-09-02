from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_systemd_service_restarts_and_uses_project_runner() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "smart-home-dashboard.service").read_text(encoding="utf-8")

    assert "WorkingDirectory=/home/orangepi/smart_home_AI" in unit
    assert "User=" not in unit
    assert "Group=" not in unit
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/run-dashboard.sh" in unit
    assert "Restart=always" in unit
    assert "Environment=HOST=0.0.0.0" in unit
    assert "Environment=PORT=8000" in unit


def test_go2rtc_systemd_service_restarts_and_uses_project_runner() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "go2rtc.service").read_text(encoding="utf-8")

    assert "After=network-online.target" in unit
    assert "Wants=network-online.target" in unit
    assert "WorkingDirectory=/home/orangepi/smart_home_AI" in unit
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/run-go2rtc.sh" in unit
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


def test_matter_server_service_targets_the_orange_pi() -> None:
    """The unit shipped with the Raspberry Pi user/paths, so it never started."""
    unit = (PROJECT_ROOT / "configs" / "matter-server.service").read_text(encoding="utf-8")

    assert "smarthome" not in unit
    assert "User=orangepi" in unit
    assert "/home/orangepi/.venvs/matter-server/bin/matter-server" in unit
    assert "--port 5580" in unit
    # Commissioning a factory-fresh device needs BLE.
    assert "--bluetooth-adapter" in unit
    assert "Restart=on-failure" in unit


def test_matter_server_installer_creates_data_dir_the_chip_stack_needs() -> None:
    """CHIP aborts at startup when it cannot write /data/chip_factory.ini."""
    script = (PROJECT_ROOT / "scripts" / "install-matter-server.sh").read_text(encoding="utf-8")

    assert "/data" in script
    assert "python-matter-server[server]" in script
    assert "systemctl enable matter-server" in script

def test_zigbee_adapter_watch_service_runs_project_script_and_restarts() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "zigbee-adapter-watch.service").read_text(encoding="utf-8")

    assert "WorkingDirectory=/home/orangepi/smart_home_AI" in unit
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/zigbee-adapter-watch.sh" in unit
    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit
    # User units cannot order against system units, so an "After=docker.service"
    # would look meaningful while doing nothing. Check the directives rather than
    # the raw text, so the comment explaining this may keep saying so.
    directives = [line.strip() for line in unit.splitlines() if not line.lstrip().startswith("#")]
    assert not any("docker.service" in line for line in directives)
    assert "User=" not in unit
    assert "Group=" not in unit


def test_zigbee_install_script_installs_and_enables_the_hotplug_watch() -> None:
    script = (PROJECT_ROOT / "scripts" / "install-zigbee2mqtt.sh").read_text(encoding="utf-8")

    assert 'WATCH_UNIT="zigbee-adapter-watch.service"' in script
    assert 'UNIT_TARGET_DIR="${HOME}/.config/systemd/user"' in script
    assert 'systemctl --user enable "${WATCH_UNIT}"' in script
    assert 'systemctl --user restart "${WATCH_UNIT}"' in script
    assert 'chmod +x "${PROJECT_ROOT}/scripts/zigbee-adapter-watch.sh"' in script
    # The unit only starts at boot when lingering is on, so the installer has
    # to say so rather than leaving a watch that silently misses reboots.
    assert "enable-linger" in script


def test_zigbee_adapter_watch_survives_failures_and_uses_the_stable_by_id_path() -> None:
    script = (PROJECT_ROOT / "scripts" / "zigbee-adapter-watch.sh").read_text(encoding="utf-8")

    # `set -e` here would kill the watcher the first time a docker call fails,
    # which is exactly when it is needed.
    assert "set -uo pipefail" in script
    assert "set -euo pipefail" not in script
    # The adapter must come from ZIGBEE_ADAPTER (a /dev/serial/by-id path), never
    # a raw ttyUSBn that moves when USB enumeration order changes.
    assert "ZIGBEE_ADAPTER" in script
    assert "/dev/ttyUSB" not in script
    # A manual stop needs a way to stay stopped.
    assert ".autostart-disabled" in script
    assert "udevadm monitor" in script
    # Polling is the safety net for a missed udev event.
    assert "ZIGBEE_POLL_SECONDS" in script
