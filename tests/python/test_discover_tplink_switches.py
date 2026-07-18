import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "discover_tplink_switches",
    Path(__file__).resolve().parents[2] / "scripts" / "discover_tplink_switches.py",
)
discover_tplink_switches = importlib.util.module_from_spec(_SPEC)
sys.modules["discover_tplink_switches"] = discover_tplink_switches
_SPEC.loader.exec_module(discover_tplink_switches)

merge_previous_aliases = discover_tplink_switches.merge_previous_aliases


def test_keeps_previous_alias_when_rediscovery_returns_none() -> None:
    fresh = [{"host": "192.168.0.208", "alias": None, "name": "192.168.0.208"}]
    previous = [
        {"host": "192.168.0.208", "alias": "North bedroom night light", "name": "North bedroom night light"}
    ]

    merged = merge_previous_aliases(fresh, previous)

    assert merged[0]["alias"] == "North bedroom night light"
    assert merged[0]["name"] == "North bedroom night light"


def test_fresh_alias_wins_over_previous() -> None:
    fresh = [{"host": "192.168.0.51", "alias": "Office switch renamed", "name": "Office switch renamed"}]
    previous = [{"host": "192.168.0.51", "alias": "Office switch", "name": "Office switch"}]

    merged = merge_previous_aliases(fresh, previous)

    assert merged[0]["alias"] == "Office switch renamed"


def test_tapo_devices_are_excluded_from_discovery() -> None:
    class FakeConnection:
        device_family = "SMART.TAPOSWITCH"

    class FakeConfig:
        connection_type = FakeConnection()

    class FakeTapoSwitch:
        config = FakeConfig()
        model = "S505"

    class FakeKasaPlug:
        config = None
        model = "HS103"

    assert discover_tplink_switches._is_tapo_device(FakeTapoSwitch()) is True
    assert discover_tplink_switches._is_tapo_device(FakeKasaPlug()) is False


def test_unknown_host_passes_through() -> None:
    fresh = [{"host": "192.168.0.99", "alias": None, "name": "192.168.0.99"}]

    merged = merge_previous_aliases(fresh, [])

    assert merged[0]["name"] == "192.168.0.99"
    assert merged[0]["alias"] is None
