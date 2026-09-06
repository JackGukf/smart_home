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


def test_resource_logger_service_survives_and_is_low_priority() -> None:
    """It exists to explain the next unexplained reboot.

    journald on this image is Storage=volatile, so the 2026-09-02 hang left no
    readable evidence behind. This writes somewhere the login user can read
    after a reboot.
    """
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "resource-logger.service").read_text(
        encoding="utf-8"
    )
    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/resource-logger.sh" in unit
    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit
    # A monitor must not compete with what it is monitoring.
    assert "Nice=10" in unit


def test_resource_logger_cannot_fill_the_disk() -> None:
    """A monitor that fills / would cause the outage it exists to explain."""
    script = (PROJECT_ROOT / "scripts" / "resource-logger.sh").read_text(encoding="utf-8")
    assert "RESOURCE_LOG_MAX_BYTES" in script
    assert "tail -c" in script
    # Boot markers are what make a reboot visible when reading the file back.
    assert "BOOT uptime=" in script
    # Records the biggest consumers, so a growing process is identifiable.
    assert "--sort=-rss" in script


def test_ai_services_are_memory_capped_because_the_board_has_no_swap() -> None:
    """The board has 15 GiB and no swap, so memory pressure does not degrade --
    it hits a wall, and the kernel kills whichever process asks for memory next.
    That is very likely Home Assistant rather than the model that caused it.

    llama-server holds ~5.0 GiB resident for the life of the process, so a cap is
    the difference between "the model died" and "the house stopped working".
    Enforceable here: the board runs cgroup v2 with the memory controller
    delegated to user.slice, checked before these were added.
    """
    for name in ("llama-server.service", "npu-detector.service"):
        unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / name).read_text(encoding="utf-8")

        assert "MemoryMax=" in unit, f"{name} has no memory cap"
        # Without this the unit restarts straight back into the wall it just hit.
        assert "OOMPolicy=stop" in unit, f"{name} would restart-loop on OOM"



def test_ollama_dropin_caps_memory_and_stays_on_loopback() -> None:
    """Ollama is a system unit installed by a vendor script that rewrites
    /etc/systemd/system/ollama.service on every update, so everything this board
    needs lives in a drop-in instead -- an upgrade cannot silently drop it.

    Same no-swap reasoning as the user units: the kernel kills whichever process
    asks for memory next, which is very likely Home Assistant rather than the
    model that caused the pressure.
    """
    dropin = (
        PROJECT_ROOT / "deploy" / "systemd" / "system" / "ollama.service.d" / "override.conf"
    ).read_text(encoding="utf-8")

    assert "MemoryMax=5G" in dropin, "no memory cap; a runaway model takes Home Assistant with it"
    assert "OOMPolicy=stop" in dropin, "would restart straight back into the wall it just hit"
    # Loopback only: there is no authentication in front of the model endpoint.
    assert 'Environment="OLLAMA_HOST=127.0.0.1:11434"' in dropin
    # The property that makes Ollama the right first LLM here -- an idle model is
    # unloaded and the memory comes back.
    assert 'Environment="OLLAMA_KEEP_ALIVE=5m"' in dropin
    assert 'Environment="OLLAMA_MAX_LOADED_MODELS=1"' in dropin
    # The A720 big cores, which are interleaved on this SoC. CIX's documented
    # 0,5,6,7,8,9,10,11 includes a little core and drops a fast one.
    assert "CPUAffinity=0 1 6 7 8 9 10 11" in dropin
    assert "RuntimeWatchdogSec" not in dropin


def test_ollama_installer_refuses_the_two_conditions_that_broke_this_board() -> None:
    """The installer is the place both failures get caught, because it is what
    someone runs months from now without re-reading the handoff.

    A non-zero RuntimeWatchdogSec against this SoC's fixed 10 s SBSA timer reset
    the board every ~80 s on 2026-09-02 and cost a full rebuild.  Two LLMs at
    once do not fit in 15 GiB beside the house services with no swap.
    """
    script = (PROJECT_ROOT / "scripts" / "install-ollama.sh").read_text(encoding="utf-8")

    assert "RuntimeWatchdogUSec" in script, "installer does not check the watchdog"
    # Checked again afterwards: the vendor installer writes system units.
    assert script.count("RuntimeWatchdogUSec") >= 2, "watchdog is not re-checked after install"
    assert "llama-server.service" in script, "installer does not refuse a second LLM"

    # A setting systemd ignores looks identical in the file to one it enforces,
    # so the installer asks systemd what it actually applied.
    assert "systemctl show ollama.service -p MemoryMax" in script
    assert "5368709120" in script


def test_ollama_thread_count_is_derived_from_the_pinned_cores() -> None:
    """The pinning has two halves and only one of them is a systemd setting.

    Ollama has no OLLAMA_NUM_THREADS; its llama-server picks a thread count from
    the machine's CPUs, not from the cgroup's cpuset.  Pinned to 8 cores it still
    oversubscribed them, and llama.cpp spin-waits at every graph barrier, so it
    burned 720% CPU and emitted zero tokens in 200s.  It never errors -- it just
    never finishes, which is the worst possible failure on a board whose day job
    is running the house.

    So num_thread is computed from CPUAffinity rather than written down beside
    it, because two numbers that must be equal will not stay equal.
    """
    script = (PROJECT_ROOT / "scripts" / "install-ollama.sh").read_text(encoding="utf-8")

    assert "cpuset_count" in script, "thread count is not derived from the cpuset"
    assert 'affinity="$(systemctl show ollama.service -p CPUAffinity --value)"' in script
    assert "PARAMETER num_thread ${THREADS}" in script

    # An un-parameterised tag left reachable is a caller-facing footgun.
    assert 'ollama rm "${BASE_MODEL}"' in script, "the unpinned base tag is not retired"

    # A stalled runner returns no error, so the smoke test must be time-bounded
    # or it hangs the installer instead of reporting the fault.
    assert "--max-time" in script, "the smoke test could hang instead of failing"


def test_ollama_guidance_does_not_repeat_the_llama_server_thinking_trick() -> None:
    """Qwen3 reasons before answering, and the two servers need opposite handling.

    llama-server's OpenAI endpoint takes chat_template_kwargs enable_thinking
    false.  Ollama does not: measured on 0.33.3, "think": false stops separating
    the reasoning and returns it AS the answer, and Qwen3 ignores a /no_think
    suffix.  What works is the default -- reasoning goes to message.thinking,
    the answer to message.content -- with a generous num_predict, because a
    small budget is spent reasoning and content comes back empty.
    """
    script = (PROJECT_ROOT / "scripts" / "install-ollama.sh").read_text(encoding="utf-8")

    assert '"think": false' not in script.split("Do NOT pass")[0], \
        "installer recommends think:false, which returns reasoning as the answer"
    assert "num_predict" in script, "no budget guidance for a thinking model"
    assert "message.content" in script
