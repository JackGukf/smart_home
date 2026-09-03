"""Tests for the dashboard area (room grouping) API."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.python.web_app import DEFAULT_AREAS, create_app


def _write_discovery(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "count": 1,
                "switches": [
                    {
                        "alias": "Family room light switch",
                        "device_type": "DeviceType.Dimmer",
                        "host": "192.168.0.61",
                        "is_on": False,
                        "model": "HS220",
                        "name": "Family room light switch",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    discovery = tmp_path / "switches.json"
    _write_discovery(discovery)
    areas_path = tmp_path / "areas.json"
    app = create_app(
        discovery_path=discovery,
        config_path=tmp_path / "missing.yaml",
        check_camera_ports=False,
        areas_path=areas_path,
    )
    return TestClient(app), areas_path


def test_areas_seeded_with_home_assistant_defaults(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    response = client.get("/api/areas")
    assert response.status_code == 200
    assert response.json() == {"areas": DEFAULT_AREAS, "assignments": {}}
    names = [a["name"] for a in response.json()["areas"]]
    # This order is the dashboard's default order for cameras and devices too,
    # not just the Areas view, so it is asserted explicitly.
    assert names == [
        "Front Yard", "Front Door", "Living Room", "Kitchen",
        "Family Room", "Office", "Bedroom", "Back Yard", "Utility Room",
    ]


def test_create_area_persists(tmp_path: Path) -> None:
    client, areas_path = _make_client(tmp_path)
    response = client.post("/api/areas", json={"name": "Guest Room", "icon": "tree"})
    assert response.status_code == 200
    assert response.json()["area"] == {"id": "guest-room", "name": "Guest Room", "icon": "tree"}

    saved = json.loads(areas_path.read_text(encoding="utf-8"))
    assert saved["areas"][-1]["id"] == "guest-room"

    listing = client.get("/api/areas").json()
    assert listing["areas"] == DEFAULT_AREAS + [{"id": "guest-room", "name": "Guest Room", "icon": "tree"}]


def test_create_area_rejects_blank_and_duplicate(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    assert client.post("/api/areas", json={"name": "   "}).status_code == 400
    assert client.post("/api/areas", json={"name": "x" * 41}).status_code == 400
    assert client.post("/api/areas", json={"name": "!!!"}).status_code == 400

    # Seeded default areas already occupy their names, case-insensitively.
    assert client.post("/api/areas", json={"name": "living room"}).status_code == 409

    assert client.post("/api/areas", json={"name": "Sun Room"}).status_code == 200
    assert client.post("/api/areas", json={"name": "sun room"}).status_code == 409


def test_update_area(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    client.post("/api/areas", json={"name": "Den"})
    response = client.patch("/api/areas/den", json={"name": "Study", "icon": "books"})
    assert response.status_code == 200
    assert response.json()["area"] == {"id": "den", "name": "Study", "icon": "books"}
    assert client.patch("/api/areas/nope", json={"name": "X"}).status_code == 404


def test_assign_and_unassign_device(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    client.post("/api/areas", json={"name": "Garage"})

    response = client.put(
        "/api/areas/assignments",
        json={"device_key": "dev:192.168.0.61", "area_id": "garage"},
    )
    assert response.status_code == 200
    assert response.json()["assignments"] == {"dev:192.168.0.61": "garage"}

    response = client.put(
        "/api/areas/assignments",
        json={"device_key": "dev:192.168.0.61", "area_id": None},
    )
    assert response.status_code == 200
    assert response.json()["assignments"] == {}


def test_assign_to_missing_area_fails(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    response = client.put(
        "/api/areas/assignments",
        json={"device_key": "dev:192.168.0.61", "area_id": "ghost"},
    )
    assert response.status_code == 404


def test_delete_area_removes_assignments(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    client.post("/api/areas", json={"name": "Patio"})
    client.put("/api/areas/assignments", json={"device_key": "cam:front", "area_id": "patio"})

    assert client.delete("/api/areas/patio").status_code == 200
    listing = client.get("/api/areas").json()
    assert listing == {"areas": DEFAULT_AREAS, "assignments": {}}
    assert client.delete("/api/areas/patio").status_code == 404


def test_deleted_default_area_stays_deleted(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    assert client.delete("/api/areas/office").status_code == 200
    names = [a["name"] for a in client.get("/api/areas").json()["areas"]]
    assert "Office" not in names
    assert len(names) == len(DEFAULT_AREAS) - 1


def test_load_areas_falls_back_to_defaults_on_corrupt_file(tmp_path: Path) -> None:
    client, areas_path = _make_client(tmp_path)
    areas_path.write_text("{not json", encoding="utf-8")
    response = client.get("/api/areas")
    assert response.status_code == 200
    assert response.json() == {"areas": DEFAULT_AREAS, "assignments": {}}
