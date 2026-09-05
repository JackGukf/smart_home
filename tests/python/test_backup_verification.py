"""The backup's own verification is the thing that has to be right.

The 2026-09-03 recovery lost `.storage/auth` because the backup "integrity
checked by parsing each file", which cannot detect a file that was never
captured. `backup-smart-home.sh` answers that with a manifest of REQUIRED
members checked against the finished archive.

The Matter fabric could not simply join that list: the controller is not
installed on every host, so a literal REQUIRED entry would fail backups that
are legitimately complete. These pin the distinction the script draws instead —
"no controller here" passes, "controller here and its credentials are missing"
fails — and the second case is the one that would otherwise cost a factory
reset of every Matter device.

Driven through --verify-only, so nothing touches the board.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup-smart-home.sh"

# Everything the script's REQUIRED list names. Kept as a fixture of a *complete*
# archive so each test can remove exactly one thing and prove that one thing is
# what fails.
REQUIRED_MEMBERS = [
    "smart_home_AI/.env",
    "smart_home_AI/configs/devices.local.yaml",
    "smart_home_AI/dashboard_areas.json",
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/configuration.yaml",
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/secret.yaml",
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/database.db",
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/coordinator_backup.json",
    "homeassistant-config/.storage/auth",
    "homeassistant-config/.storage/auth_provider.homeassistant",
    "homeassistant-config/.storage/core.config_entries",
    "homeassistant-config/.storage/core.device_registry",
    "homeassistant-config/.storage/core.entity_registry",
    "homeassistant-config/.HA_VERSION",
    "homeassistant-config/configuration.yaml",
    "homeassistant-config/automations.yaml",
    "homeassistant-container-spec.json",
]

# The fabric file is named for the compressed fabric id, in decimal. This is the
# board's real one, so the pattern is exercised against a value it has to match.
FABRIC_FILE = "matter-server/4050640241409191186.json"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _archive(tmp_path: Path, members: dict[str, str], name: str = "backup.tgz") -> Path:
    stage = tmp_path / name.replace(".tgz", "")
    for rel, content in members.items():
        path = stage / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    out = tmp_path / name
    with tarfile.open(out, "w:gz") as tar:
        for rel in members:
            tar.add(stage / rel, arcname="./" + rel)
    return out


def _complete(**overrides: str) -> dict[str, str]:
    members = {rel: "x" for rel in REQUIRED_MEMBERS}
    # The zigbee check reads this file for a real key rather than trusting that
    # the file exists, so a complete archive has to carry one.
    members["smart_home_AI/deploy/zigbee/zigbee2mqtt/configuration.yaml"] = (
        "mqtt:\n  base_topic: zigbee2mqtt\nadvanced:\n  network_key: [1, 2, 3]\n"
    )
    members.update(overrides)
    return members


def _verify(archive: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), "--verify-only", str(archive)],
        capture_output=True, text=True, timeout=60,
    )


def test_a_complete_archive_with_a_fabric_passes(tmp_path: Path) -> None:
    members = _complete()
    members[FABRIC_FILE] = "{}"
    members["matter-server/chip.json"] = "{}"

    result = _verify(_archive(tmp_path, members))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "matter-server/ fabric credentials" in result.stdout


def test_a_host_with_no_matter_controller_passes(tmp_path: Path) -> None:
    """A board that has never run matter-server still has a valid backup, which
    is why the fabric could not be a literal REQUIRED entry."""
    members = _complete()
    members["matter-server-absent"] = ""

    result = _verify(_archive(tmp_path, members))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no Matter controller on this host" in result.stdout


def test_an_installed_controller_whose_fabric_is_missing_fails(tmp_path: Path) -> None:
    """The case that bites: the controller exists on the board, so no sentinel is
    written, but nothing reached the archive. Previously a warning, which is what
    let it pass unnoticed."""
    result = _verify(_archive(tmp_path, _complete()))

    assert result.returncode != 0
    assert "MISSING matter-server/" in result.stderr


def test_a_fabric_directory_without_the_fabric_file_fails(tmp_path: Path) -> None:
    """chip.json alone restores a controller that has never been commissioned.
    The directory existing proves nothing -- the same reason the zigbee check
    greps for network_key instead of trusting configuration.yaml to exist."""
    members = _complete()
    members["matter-server/chip.json"] = "{}"

    result = _verify(_archive(tmp_path, members))

    assert result.returncode != 0
    assert "fabric-id" in result.stderr


def test_a_missing_required_member_still_fails(tmp_path: Path) -> None:
    """The original guarantee, unchanged by the Matter work."""
    members = _complete()
    del members["homeassistant-config/.storage/auth"]
    members[FABRIC_FILE] = "{}"

    result = _verify(_archive(tmp_path, members))

    assert result.returncode != 0
    assert "MISSING homeassistant-config/.storage/auth" in result.stderr


def test_a_configuration_without_a_network_key_still_fails(tmp_path: Path) -> None:
    members = _complete()
    members["smart_home_AI/deploy/zigbee/zigbee2mqtt/configuration.yaml"] = "mqtt:\n  base_topic: z\n"
    members[FABRIC_FILE] = "{}"

    result = _verify(_archive(tmp_path, members))

    assert result.returncode != 0
    assert "network_key" in result.stderr
