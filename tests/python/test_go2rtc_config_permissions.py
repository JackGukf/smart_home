"""go2rtc.yaml holds every camera password in plain text; only its owner may read it.

It was 0664 on the board. It is regenerated on every go2rtc start, so the
permission has to come from the generator rather than a one-off chmod.
"""

from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "generate-go2rtc-config.py"

_spec = importlib.util.spec_from_file_location("generate_go2rtc_config", SCRIPT)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_a_new_config_is_owner_only(tmp_path) -> None:
    target = tmp_path / "go2rtc.yaml"
    gen._write_private(target, "streams: {}\n")
    assert _mode(target) == 0o600
    assert target.read_text(encoding="utf-8") == "streams: {}\n"


def test_an_existing_world_readable_config_is_tightened(tmp_path) -> None:
    """The file on the board already exists at 0664; rewriting must not keep that."""
    target = tmp_path / "go2rtc.yaml"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o664)
    gen._write_private(target, "new\n")
    assert _mode(target) == 0o600
    assert target.read_text(encoding="utf-8") == "new\n"


def test_a_leftover_temporary_file_does_not_carry_its_mode_over(tmp_path) -> None:
    target = tmp_path / "go2rtc.yaml"
    leftover = tmp_path / ".go2rtc.yaml.tmp"
    leftover.write_text("stale\n", encoding="utf-8")
    leftover.chmod(0o666)
    gen._write_private(target, "fresh\n")
    assert _mode(target) == 0o600
    assert not leftover.exists()


def test_main_writes_through_the_private_writer() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "OUTPUT_CONFIG.write_text(" not in source
    assert "_write_private(\n        OUTPUT_CONFIG" in source
