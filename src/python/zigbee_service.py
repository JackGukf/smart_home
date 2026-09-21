"""The Zigbee coordinator's on/off switch, as exposed by the dashboard."""
from __future__ import annotations

import os
import subprocess
from typing import Any, Callable


WATCH_UNIT = "zigbee-adapter-watch.service"
CONTAINER = "zigbee2mqtt"
Runner = Callable[..., subprocess.CompletedProcess]


def _run(command: list[str], run: Runner) -> subprocess.CompletedProcess:
    return run(command, capture_output=True, text=True, timeout=20, check=False)


def _systemctl(args: list[str], run: Runner) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return run(["systemctl", "--user", *args], capture_output=True, text=True,
               timeout=20, env=env, check=False)


def _failure(result: subprocess.CompletedProcess) -> str:
    return (result.stderr or result.stdout or "command failed").strip().splitlines()[-1]


def state(run: Runner = subprocess.run) -> dict[str, Any]:
    """Report whether both halves of the coordinator are installed and on."""
    watch_enabled = _systemctl(["is-enabled", WATCH_UNIT], run).stdout.strip()
    watch_active = _systemctl(["is-active", WATCH_UNIT], run).stdout.strip()
    container = _run(["docker", "inspect", "--format", "{{.State.Status}} {{.HostConfig.RestartPolicy.Name}}", CONTAINER], run)
    fields = container.stdout.strip().split()
    container_state, restart = (fields + ["", ""])[:2]
    installed = watch_enabled not in ("", "not-found") and container.returncode == 0
    return {
        "installed": installed,
        "enabled": installed and watch_enabled == "enabled" and restart != "no",
        "running": installed and watch_active in {"active", "activating", "reloading"} and container_state == "running",
    }


def set_enabled(enabled: bool, run: Runner = subprocess.run) -> dict[str, Any]:
    """Enable or disable Zigbee2MQTT and its USB-replug watchdog together."""
    current = state(run)
    if not current["installed"]:
        raise RuntimeError("Zigbee is not installed on this board")

    if enabled:
        result = _run(["docker", "update", "--restart=unless-stopped", CONTAINER], run)
        if result.returncode != 0:
            raise RuntimeError(_failure(result))
        if not current["running"]:
            result = _run(["docker", "start", CONTAINER], run)
            if result.returncode != 0:
                raise RuntimeError(_failure(result))
        result = _systemctl(["enable", "--now", WATCH_UNIT], run)
    else:
        result = _systemctl(["disable", "--now", WATCH_UNIT], run)
        if result.returncode != 0:
            raise RuntimeError(_failure(result))
        result = _run(["docker", "update", "--restart=no", CONTAINER], run)
        if result.returncode != 0:
            raise RuntimeError(_failure(result))
        if current["running"]:
            result = _run(["docker", "stop", CONTAINER], run)
        else:
            result = subprocess.CompletedProcess([], 0)

    if result.returncode != 0:
        raise RuntimeError(_failure(result))
    return state(run)
