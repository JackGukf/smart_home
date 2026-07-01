from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_CPP = PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "main.cpp"


def test_rescan_does_not_restart_commissioned_bridge_on_device_count_change() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")

    assert "exit(0)" not in source
    assert "keeping existing Matter endpoints stable" in source
