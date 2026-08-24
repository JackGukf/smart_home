"""Snapshots should come from go2rtc so cameras only ever see one session.

The Wyze RTSP firmware serves a single client at a time: the dashboard's idle
thumbnail must not open its own ffmpeg session alongside the one go2rtc already
holds, or the camera's RTSP service can stop answering entirely.
"""

from __future__ import annotations

import pytest

from src.python import web_app as web_app_module
from src.python.web_app import CameraDefinition, _go2rtc_frame_url


def _camera(**overrides) -> CameraDefinition:
    fields = {
        "name": "Front door camera",
        "host": "192.168.0.88",
        "provider": "wyze",
        "model": "Wyze RTSP",
        "room": "Home",
        "snapshot_url": None,
        "stream_url": "rtsps://user:pass@192.168.0.88:322/stream0",
        "view_url": None,
        "mjpeg_fps": 10,
        "mjpeg_width": 640,
        "mjpeg_quality": 7,
        "stream_name": "front_door_camera",
        "go2rtc_url": "http://192.168.0.234:1984",
        "battery_powered": False,
    }
    fields.update(overrides)
    return CameraDefinition(**fields)


def test_frame_url_points_at_the_go2rtc_stream() -> None:
    assert _go2rtc_frame_url(_camera()) == "http://192.168.0.234:1984/api/frame.jpeg?src=front_door_camera"


def test_frame_url_strips_a_trailing_slash_and_encodes_the_stream_name() -> None:
    camera = _camera(go2rtc_url="http://192.168.0.234:1984/", stream_name="front door")

    assert _go2rtc_frame_url(camera) == "http://192.168.0.234:1984/api/frame.jpeg?src=front+door"


def test_no_frame_url_without_a_gateway() -> None:
    assert _go2rtc_frame_url(_camera(go2rtc_url=None)) is None


class _FakeResponse:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc) -> None:
        return None


def test_capture_returns_the_frame_go2rtc_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def fake_urlopen(request, timeout=None):  # noqa: ANN001, ARG001
        requested.append(request.full_url)
        return _FakeResponse(200, b"\xff\xd8jpeg-bytes")

    monkeypatch.setattr(web_app_module, "urlopen", fake_urlopen)

    assert web_app_module._capture_go2rtc_frame(_camera()) == b"\xff\xd8jpeg-bytes"
    assert requested == ["http://192.168.0.234:1984/api/frame.jpeg?src=front_door_camera"]


def test_capture_treats_an_empty_body_as_no_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """go2rtc answers 200 with no bytes while a stream has no producer yet."""
    monkeypatch.setattr(web_app_module, "urlopen", lambda *a, **k: _FakeResponse(200, b""))

    assert web_app_module._capture_go2rtc_frame(_camera()) is None


def test_capture_treats_a_non_200_as_no_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app_module, "urlopen", lambda *a, **k: _FakeResponse(404, b"missing"))

    assert web_app_module._capture_go2rtc_frame(_camera()) is None


def test_capture_swallows_gateway_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*_args, **_kwargs):
        raise OSError("go2rtc is down")

    monkeypatch.setattr(web_app_module, "urlopen", fake_urlopen)

    assert web_app_module._capture_go2rtc_frame(_camera()) is None


def test_capture_skips_the_request_without_a_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("should not reach out without a go2rtc URL")

    monkeypatch.setattr(web_app_module, "urlopen", fail)

    assert web_app_module._capture_go2rtc_frame(_camera(go2rtc_url=None)) is None


def _write_camera_config(path) -> None:
    path.write_text(
        """
cameras:
  - name: Front door camera
    provider: wyze
    host: 192.168.0.88
    model: Wyze RTSP
    room: Home
    stream_name: front_door_camera
    username_env: WYZE_FRONT_DOOR_RTSP_USERNAME
    password_env: WYZE_FRONT_DOOR_RTSP_PASSWORD
    rtsp_scheme: rtsps
    rtsp_port: 322
    stream_path: /stream0
media_gateway:
  go2rtc_url: http://192.168.0.234:1984
""",
        encoding="utf-8",
    )


def _snapshot_client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    config = tmp_path / "devices.yaml"
    _write_camera_config(config)
    monkeypatch.setenv("WYZE_FRONT_DOOR_RTSP_USERNAME", "wyzecamfront")
    monkeypatch.setenv("WYZE_FRONT_DOOR_RTSP_PASSWORD", "secret")
    return TestClient(web_app_module.create_app(config_path=config, check_camera_ports=False))


def test_endpoint_serves_the_go2rtc_frame_without_touching_ffmpeg(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app_module, "_capture_go2rtc_frame", lambda camera: b"\xff\xd8from-go2rtc")

    def fail(*_args, **_kwargs):
        raise AssertionError("must not open a second RTSP session when go2rtc has a frame")

    monkeypatch.setattr(web_app_module, "_capture_rtsp_frame", fail)

    response = _snapshot_client(tmp_path, monkeypatch).get("/api/cameras/192.168.0.88/snapshot.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == b"\xff\xd8from-go2rtc"


def test_endpoint_falls_back_to_the_camera_when_go2rtc_has_no_frame(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app_module, "_capture_go2rtc_frame", lambda camera: None)
    captured: list[str] = []

    def fake_capture(rtsp_url: str) -> bytes:
        captured.append(rtsp_url)
        return b"\xff\xd8from-ffmpeg"

    monkeypatch.setattr(web_app_module, "_capture_rtsp_frame", fake_capture)
    monkeypatch.setattr(web_app_module.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

    response = _snapshot_client(tmp_path, monkeypatch).get("/api/cameras/192.168.0.88/snapshot.jpg")

    assert response.status_code == 200
    assert response.content == b"\xff\xd8from-ffmpeg"
    assert captured == ["rtsps://wyzecamfront:secret@192.168.0.88:322/stream0"]
