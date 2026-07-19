from pathlib import Path

from src.python.web_app import _load_humidifiers


def _write_humidifier_config(path: Path) -> None:
    path.write_text(
        """
humidifiers:
  devices:
    - name: Bedroom Humidifier
      provider: govee_cloud
      model: H7140
      room: Bedroom
      device_id: replace_me
    - name: Disabled Humidifier
      provider: govee_cloud
      model: H7141
      enabled: false
""",
        encoding="utf-8",
    )


def test_load_humidifiers_parses_entries_and_skips_disabled(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    _write_humidifier_config(config)

    humidifiers = _load_humidifiers(config)

    assert len(humidifiers) == 1
    assert humidifiers[0].name == "Bedroom Humidifier"
    assert humidifiers[0].provider == "govee_cloud"
    assert humidifiers[0].model == "H7140"
    assert humidifiers[0].room == "Bedroom"
    assert humidifiers[0].device_id == "replace_me"


def test_load_humidifiers_tolerates_missing_file_and_section(tmp_path: Path) -> None:
    missing = tmp_path / "devices.local.yaml"
    assert _load_humidifiers(missing) == []

    empty = tmp_path / "empty.yaml"
    empty.write_text("tplink: {}\n", encoding="utf-8")
    assert _load_humidifiers(empty) == []
