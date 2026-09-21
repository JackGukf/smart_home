import subprocess

from src.python import zigbee_service as zs


class FakeRunner:
    def __init__(self, enabled=True, running=True):
        self.enabled = enabled
        self.running = running
        self.restart = "unless-stopped" if enabled else "no"
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[:3] == ["systemctl", "--user", "is-enabled"]:
            return subprocess.CompletedProcess(argv, 0 if self.enabled else 1,
                                               ("enabled" if self.enabled else "disabled") + "\n", "")
        if argv[:3] == ["systemctl", "--user", "is-active"]:
            return subprocess.CompletedProcess(argv, 0 if self.running else 3,
                                               ("active" if self.running else "inactive") + "\n", "")
        if argv[:3] == ["systemctl", "--user", "enable"]:
            self.enabled = self.running = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["systemctl", "--user", "disable"]:
            self.enabled = self.running = False
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["docker", "inspect", "--format"]:
            return subprocess.CompletedProcess(argv, 0,
                                               f"{'running' if self.running else 'exited'} {self.restart}\n", "")
        if argv[:3] == ["docker", "update", "--restart=unless-stopped"]:
            self.restart = "unless-stopped"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["docker", "update", "--restart=no"]:
            self.restart = "no"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == ["docker", "start"]:
            self.running = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == ["docker", "stop"]:
            self.running = False
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)


def test_disabling_zigbee_stops_the_container_and_its_watchdog():
    runner = FakeRunner()

    state = zs.set_enabled(False, runner)

    assert state == {"installed": True, "enabled": False, "running": False}
    assert ["systemctl", "--user", "disable", "--now", zs.WATCH_UNIT] in runner.calls
    assert ["docker", "update", "--restart=no", zs.CONTAINER] in runner.calls
    assert ["docker", "stop", zs.CONTAINER] in runner.calls


def test_enabling_zigbee_restores_both_parts():
    runner = FakeRunner(enabled=False, running=False)

    state = zs.set_enabled(True, runner)

    assert state == {"installed": True, "enabled": True, "running": True}
    assert ["docker", "update", "--restart=unless-stopped", zs.CONTAINER] in runner.calls
    assert ["docker", "start", zs.CONTAINER] in runner.calls
    assert ["systemctl", "--user", "enable", "--now", zs.WATCH_UNIT] in runner.calls
