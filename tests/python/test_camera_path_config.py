"""The configured front-door priority is carried to the browser route."""
from pathlib import Path

from src.python.web_app import _camera_paths


def test_front_door_priority_resolves_to_camera_id(tmp_path: Path) -> None:
    config = tmp_path / "devices.yaml"
    config.write_text(
        "camera_paths:\n"
        "  - name: Front approach\n"
        "    priority_camera: Front door camera\n"
        "    prewarm_next: true\n"
        "    cameras: [Garage camera, Frontyard camera, Front door camera]\n",
        encoding="utf-8",
    )
    cards = [
        {"id": name.lower().replace(" ", "_"), "name": name,
         "motion_entity": "binary_sensor." + name.lower().replace(" ", "_")}
        for name in ("Garage camera", "Frontyard camera", "Front door camera")
    ]
    route = _camera_paths(config, cards)[0]
    assert route["priority_camera_id"] == "front_door_camera"
    assert route["prewarm_next"] is True
