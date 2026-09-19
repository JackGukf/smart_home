"""The board's own desktop (GNOME, through GDM), switched from the dashboard.

The desktop is on after every restart - that is the point of it: when something
is wrong, a monitor and keyboard on the board get you a desktop to look from.
Nobody looks at it otherwise, and it holds about 0.8 GB of a swapless board,
so the dashboard can stop it until the next restart, and start it again.

The switch is `systemctl start|stop gdm.service`. The dashboard runs as
`orangepi`, and stopping a system service needs root, so one polkit rule
(deploy/polkit/50-smart-home-desktop.rules, installed by
scripts/install-desktop-control.sh) allows exactly that user those two verbs
on exactly that unit - nothing else, and never `disable`, so the boot default
cannot be changed from a web page. Without the rule, systemctl answers
"Interactive authentication required", and the page says how to fix it.

Nothing the house needs lives in the desktop session: the user services run
because the account lingers, not because GDM logged it in.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

UNIT = "gdm.service"
BOOT_TARGET = "graphical.target"
INSTALL_HINT = "run scripts/install-desktop-control.sh on the board once"
Runner = Callable[..., subprocess.CompletedProcess]


def _systemctl(args: list[str], run: Runner) -> subprocess.CompletedProcess:
    return run(["systemctl", "--no-ask-password", *args], capture_output=True, text=True, timeout=60)


def _mem_available_mb(meminfo: Path) -> int | None:
    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def state(run: Runner = subprocess.run, meminfo: Path = Path("/proc/meminfo")) -> dict[str, Any]:
    """Whether the desktop is running, and whether it comes back at a restart."""
    active = _systemctl(["is-active", UNIT], run).stdout.strip()
    default = _systemctl(["get-default"], run).stdout.strip()
    return {
        "running": active in ("active", "activating", "reloading"),
        "state": active or "unknown",
        "on_at_boot": default == BOOT_TARGET,
        "boot_target": default,
        "mem_available_mb": _mem_available_mb(meminfo),
    }


def set_running(running: bool, run: Runner = subprocess.run,
                meminfo: Path = Path("/proc/meminfo")) -> dict[str, Any]:
    """Start or stop the desktop now. The next restart brings it back either way."""
    result = _systemctl(["start" if running else "stop", UNIT], run)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "systemctl failed").strip().splitlines()[-1]
        if "authentication required" in message.lower() or "access denied" in message.lower():
            raise PermissionError(f"The board does not allow it yet - {INSTALL_HINT}")
        raise RuntimeError(message)
    return state(run, meminfo)
