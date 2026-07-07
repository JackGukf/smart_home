from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_CPP = PROJECT_ROOT / "src" / "cpp" / "matter_single_light" / "main.cpp"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-matter-single-light.sh"


def test_fixed_light_accessory_contains_four_expected_switches() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")

    assert '"kasa:192.168.0.110", "Kitchen light switch"' in source
    assert '"kasa:192.168.0.143", "Master bedroom light switch"' in source
    assert '"kasa:192.168.0.61", "Family room light switch"' in source
    assert '"kasa:192.168.0.73", "Living room light switch 2"' in source
    assert "FetchAllStatesFor(deviceIds)" in source


def test_single_light_build_script_generates_four_onoff_endpoints() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "for endpoint_id in (2, 3, 4):" in script
    assert 'CHIP_DEVICE_CONFIG_DEVICE_NAME "Home light switches"' in script
    assert 'CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE 0' in script
    assert 'CHIP_SYSTEM_CONFIG_PACKETBUFFER_CAPACITY_MAX 9050' in script
    assert 'chip_project_config_include="<CHIPProjectAppConfig.h>"' in script
    assert 'CHIPProjectConfig.h' in script
    assert 'SystemProjectConfig.h' in script
    assert 'cluster.get("code") != 8' in script
