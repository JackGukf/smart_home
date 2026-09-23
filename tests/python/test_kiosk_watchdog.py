"""Kiosk recovery when Chromium stays alive with a frozen renderer."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time

WATCHDOG = Path(__file__).resolve().parents[2] / "scripts/kiosk/kiosk-watchdog.sh"


def _write_tool(directory: Path, name: str, body: str) -> None:
    script = directory / name
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)


def _run_case(tmp_path: Path, server_up: bool) -> tuple[bool, str]:
    tools = tmp_path / "bin"
    tools.mkdir()
    _write_tool(tools, "wlr-randr", 'printf "1920x1080 px, 60 Hz (current)\\n"\n')
    _write_tool(tools, "grim", 'printf frozen > "$3"\n')
    _write_tool(tools, "curl", "exit 0\n" if server_up else "exit 7\n")
    log = tmp_path / "kiosk.log"
    browser = subprocess.Popen(["sleep", "30"])
    env = os.environ.copy()
    env.update({
        "PATH": f"{tools}:{env['PATH']}",
        "XDG_RUNTIME_DIR": str(tmp_path),
        "WATCHDOG_INTERVAL_SECONDS": "1",
        "WATCHDOG_STALE_SECONDS": "2",
    })
    watcher = subprocess.Popen(
        ["bash", str(WATCHDOG), str(browser.pid), "http://dashboard/", str(log)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + (7 if server_up else 4)
        while time.monotonic() < deadline and browser.poll() is None:
            time.sleep(0.1)
        stopped = browser.poll() is not None
        return stopped, log.read_text() if log.exists() else ""
    finally:
        watcher.terminate()
        try:
            watcher.wait(timeout=2)
        except subprocess.TimeoutExpired:
            watcher.kill()
            watcher.wait(timeout=2)
        if browser.poll() is None:
            browser.terminate()
        browser.wait(timeout=2)


def test_frozen_clock_restarts_living_browser(tmp_path: Path) -> None:
    stopped, log = _run_case(tmp_path, server_up=True)
    assert stopped
    assert "visible dashboard clock unchanged" in log


def test_dashboard_outage_does_not_restart_browser(tmp_path: Path) -> None:
    stopped, log = _run_case(tmp_path, server_up=False)
    assert not stopped
    assert "visible dashboard clock unchanged" not in log
