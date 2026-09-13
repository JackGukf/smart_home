"""`configs/hosts.env` is the only place a board address is written down.

On 2026-09-12 the Orange Pi moved from Wi-Fi to Ethernet. Thirty-four files held
the old address; the wall panel sat on a dead URL because the *installed* copy of
its launcher had one baked in; two Matter services reported `active` while bound
to an interface that no longer existed; and every camera broke because
`devices.local.yaml` repeated the address seven more times.

The fix is not "remember to grep next time" - it is that there is one place to
change. These tests fail if a second place appears.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOSTS_ENV = PROJECT_ROOT / "configs" / "hosts.env"

sys.path.insert(0, str(PROJECT_ROOT))
from src.python.hosts import MissingHost, host, load_hosts  # noqa: E402

REQUIRED = ["PI_HOST", "PI_USER", "REMOTE_PATH",
            "RPI4_HOST", "RPI4_USER", "RPI4_REMOTE_PATH", "DASHBOARD_PORT"]

# Files that may legitimately contain an address: the source of truth itself,
# dated records of what was true at the time, and test fixtures whose whole job
# is to be an arbitrary example.
ALLOWED = {
    "configs/hosts.env",
    "tests/python/test_hosts_config.py",
    "tests/python/test_camera_snapshot_source.py",
    "tests/python/test_go2rtc_auto_host.py",
}

# Executable code only. Prose in docs is allowed to show a concrete address -
# a runbook that says "ssh orangepi@<board>" helps nobody - but code that acts
# on one must ask for it.
CODE_GLOBS = ["scripts/**/*.sh", "scripts/**/*.py", "scripts/**/*.ps1",
              "src/python/**/*.py", "src/python/web_static/*.js", "configs/*.service"]

IP_PATTERN = re.compile(r"\b192\.168\.0\.(?:83|176)\b")


def test_hosts_env_defines_everything_that_is_needed() -> None:
    values = load_hosts(HOSTS_ENV)

    missing = [key for key in REQUIRED if not values.get(key)]
    assert not missing, f"configs/hosts.env is missing {missing}"


def test_no_board_address_is_hardcoded_in_code() -> None:
    """The invariant. If this fails, put the address in hosts.env instead."""
    offenders: list[str] = []
    for glob in CODE_GLOBS:
        for path in PROJECT_ROOT.glob(glob):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            if rel in ALLOWED or "__pycache__" in rel:
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if IP_PATTERN.search(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:90]}")

    assert not offenders, (
        "a board address is hardcoded outside configs/hosts.env:\n  "
        + "\n  ".join(offenders)
    )


def test_the_shell_and_python_loaders_agree() -> None:
    """Two parsers, one file - they must not drift apart."""
    script = (
        f'. "{PROJECT_ROOT}/scripts/lib/hosts.sh"; '
        'for k in ' + " ".join(REQUIRED) + '; do printf "%s=%s\\n" "$k" "${!k}"; done'
    )
    completed = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                               env={"PATH": "/usr/bin:/bin"})
    assert completed.returncode == 0, completed.stderr

    from_shell = dict(
        line.split("=", 1) for line in completed.stdout.strip().splitlines() if "=" in line
    )
    from_python = {key: host(key) for key in REQUIRED}

    assert from_shell == from_python


def test_the_environment_beats_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """`PI_HOST=x ./deploy` must still win, or the file becomes a lock."""
    monkeypatch.setenv("PI_HOST", "192.168.0.99")

    assert host("PI_HOST") == "192.168.0.99"


def test_a_missing_setting_fails_loudly_rather_than_guessing() -> None:
    """A stale literal fallback would fail by talking to the wrong machine."""
    with pytest.raises(MissingHost):
        host("PI_HOST_THAT_DOES_NOT_EXIST")


def test_comments_and_blank_lines_are_ignored() -> None:
    values = load_hosts(HOSTS_ENV)

    assert not any(key.startswith("#") for key in values)
    assert all(key.isidentifier() for key in values)
