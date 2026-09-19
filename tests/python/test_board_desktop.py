"""Settings -> Desktop: stop or start the board's GNOME desktop until the next
restart, which always brings it back. One polkit rule allows exactly that."""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import board_desktop, web_app

ROOT = Path(__file__).resolve().parents[2]


class FakeSystemctl:
    def __init__(self, allowed: bool = True):
        self.active = "active"
        self.allowed = allowed
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        assert args[:2] == ["systemctl", "--no-ask-password"]
        verb = args[2]
        if verb == "is-active":
            return subprocess.CompletedProcess(args, 0 if self.active == "active" else 3, f"{self.active}\n", "")
        if verb == "get-default":
            return subprocess.CompletedProcess(args, 0, "graphical.target\n", "")
        if verb in ("start", "stop"):
            assert args[3] == "gdm.service"
            if not self.allowed:
                return subprocess.CompletedProcess(args, 1, "", "Failed to stop gdm.service: Interactive authentication required.\n")
            self.active = "active" if verb == "start" else "inactive"
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)


def _meminfo(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text("MemTotal: 15984984 kB\nMemAvailable:    6662880 kB\n", encoding="utf-8")
    return path


def test_state_and_switching(tmp_path):
    run = FakeSystemctl()
    doc = board_desktop.state(run, _meminfo(tmp_path))
    assert doc == {"running": True, "state": "active", "on_at_boot": True,
                   "boot_target": "graphical.target", "mem_available_mb": 6506}
    assert board_desktop.set_running(False, run, _meminfo(tmp_path))["running"] is False
    assert board_desktop.set_running(True, run, _meminfo(tmp_path))["running"] is True
    # Only start and stop: never enable, disable or set-default - a restart always brings it back.
    verbs = {call[2] for call in run.calls}
    assert verbs <= {"is-active", "get-default", "start", "stop"}


def test_without_the_polkit_rule_it_says_how_to_fix_it(tmp_path):
    run = FakeSystemctl(allowed=False)
    try:
        board_desktop.set_running(False, run, _meminfo(tmp_path))
    except PermissionError as error:
        assert "install-desktop-control.sh" in str(error)
    else:
        raise AssertionError("expected PermissionError")


def test_the_endpoints(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    run = FakeSystemctl()
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False, desktop_runner=run))
    assert client.get("/api/desktop").json()["running"] is True
    assert client.put("/api/desktop", json={"running": False}).json()["running"] is False
    assert client.put("/api/desktop", json={"running": False, "extra": 1}).status_code == 422
    run.allowed = False
    response = client.put("/api/desktop", json={"running": True})
    assert response.status_code == 503 and "install-desktop-control.sh" in response.json()["detail"]


def test_the_polkit_rule_allows_only_start_and_stop_of_gdm_for_orangepi():
    rule = (ROOT / "deploy" / "polkit" / "50-smart-home-desktop.rules").read_text(encoding="utf-8")
    assert 'action.id == "org.freedesktop.systemd1.manage-units"' in rule
    assert 'subject.user == "orangepi"' in rule
    assert 'action.lookup("unit") == "gdm.service"' in rule
    assert 'action.lookup("verb") == "start" || action.lookup("verb") == "stop"' in rule
    for verb in ("enable", "disable", "restart", "isolate"):
        assert f'"{verb}"' not in rule


def test_the_settings_page():
    html = (ROOT / "src" / "python" / "web_static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")
    page = html[html.index('data-view-panel="desktop"'):]
    page = page[:page.index("<!-- ──")]
    assert 'id="desktopRunning"' in page and 'data-goto-view="settings"' in page
    assert 'desktop: "settings"' in js and 'requestJson("/api/desktop"' in js
    # Stopping asks first: someone may be at a monitor on the board.
    assert "Stop the board's desktop until the next restart?" in js
