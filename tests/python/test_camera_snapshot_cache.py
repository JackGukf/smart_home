"""The Home card and Cameras view share one recent preview capture."""
from pathlib import Path

from fastapi.testclient import TestClient

from src.python import web_app


def test_multiple_preview_consumers_share_recent_frame(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "devices.yaml"
    config.write_text(
        "cameras:\n"
        "  - name: Front door camera\n"
        "    host: 192.0.2.8\n"
        "    stream_url: rtsp://192.0.2.8/stream\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        web_app, "_capture_go2rtc_frame",
        lambda camera: calls.append(camera.name) or b"jpeg-frame",
    )
    client = TestClient(web_app.create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=config,
        check_camera_ports=False,
    ))

    first = client.get("/api/cameras/192.0.2.8/snapshot.jpg")
    second = client.get("/api/cameras/192.0.2.8/snapshot.jpg")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content == b"jpeg-frame"
    assert calls == ["Front door camera"]
    assert "max-age=30" in first.headers["cache-control"]
