"""`go2rtc_url: auto` exists so the board's address is never written down twice.

On 2026-09-12 the board moved from Wi-Fi to Ethernet and every camera on the
dashboard broke, because `configs/devices.local.yaml` held
`go2rtc_url: http://192.168.0.234:1984` seven times and nothing on the board had
any reason to notice it was wrong. `auto` removes the address from the config
entirely: the dashboard is on the same machine as go2rtc, so it already knows.

The subtlety worth a test is that `auto` has to resolve to *two different
answers* from one setting. A browser on the wall panel needs a routable LAN
address; the dashboard fetching a still frame is on the same box and should talk
to loopback rather than take a round trip across the LAN to reach itself.
"""

from __future__ import annotations

import pytest

from src.python import web_app as web_app_module
from src.python.web_app import (
    CameraDefinition,
    _go2rtc_auto_port,
    _go2rtc_base_url,
    _go2rtc_frame_url,
    _go2rtc_player_url,
)


def _camera(**overrides) -> CameraDefinition:
    fields = {
        "name": "Garage camera",
        "host": "192.168.0.90",
        "provider": "hipcam",
        "model": "Hipcam",
        "room": "Garage",
        "snapshot_url": None,
        "stream_url": "rtsp://user:pass@192.168.0.90:554/stream0",
        "view_url": None,
        "mjpeg_fps": 10,
        "mjpeg_width": 640,
        "mjpeg_quality": 7,
        "stream_name": "garage_camera",
        "go2rtc_url": "auto",
        "battery_powered": False,
    }
    fields.update(overrides)
    return CameraDefinition(**fields)


@pytest.fixture
def fixed_lan_ip(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(web_app_module, "_lan_address", lambda: "192.168.0.83")
    return "192.168.0.83"


@pytest.mark.parametrize(
    "value, port",
    [("auto", 1984), ("AUTO", 1984), ("  auto  ", 1984), ("auto:8555", 8555)],
)
def test_auto_is_recognised_however_it_is_written(value: str, port: int) -> None:
    assert _go2rtc_auto_port(value) == port


@pytest.mark.parametrize(
    "value",
    ["http://192.168.0.83:1984", "https://go2rtc.example:1984", "auto:", "autoscale"],
)
def test_a_real_url_is_left_alone(value: str) -> None:
    assert _go2rtc_auto_port(value) is None


def test_the_browser_gets_a_routable_address(fixed_lan_ip: str) -> None:
    """A wall panel cannot reach 127.0.0.1 on someone else's machine."""
    assert _go2rtc_player_url(_camera(), "webrtc") == (
        "http://192.168.0.83:1984/webrtc.html?src=garage_camera"
    )


def test_the_server_talks_to_itself_over_loopback(fixed_lan_ip: str) -> None:
    """Same setting, different answer - and it saves a LAN round trip."""
    assert _go2rtc_frame_url(_camera()) == (
        "http://127.0.0.1:1984/api/frame.jpeg?src=garage_camera"
    )


def test_a_custom_port_survives_both_paths(fixed_lan_ip: str) -> None:
    camera = _camera(go2rtc_url="auto:8555")

    assert _go2rtc_base_url(camera, for_browser=True) == "http://192.168.0.83:8555"
    assert _go2rtc_base_url(camera, for_browser=False) == "http://127.0.0.1:8555"


def test_an_explicit_url_still_works_unchanged(fixed_lan_ip: str) -> None:
    """go2rtc on a different machine is still a legitimate setup."""
    camera = _camera(go2rtc_url="http://192.168.0.99:1984/")

    assert _go2rtc_player_url(camera, "webrtc") == (
        "http://192.168.0.99:1984/webrtc.html?src=garage_camera"
    )
    assert _go2rtc_frame_url(camera) == (
        "http://192.168.0.99:1984/api/frame.jpeg?src=garage_camera"
    )


def test_no_go2rtc_configured_yields_nothing(fixed_lan_ip: str) -> None:
    assert _go2rtc_player_url(_camera(go2rtc_url=None), "webrtc") is None
    assert _go2rtc_frame_url(_camera(go2rtc_url=None)) is None


def test_lan_address_never_raises_and_never_returns_empty() -> None:
    """It runs on every camera card render, so it must not be able to throw."""
    address = web_app_module._lan_address()

    assert address
    assert address.count(".") == 3


def test_lan_address_falls_back_to_loopback_without_a_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRoute:
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def connect(self, *_): raise OSError("network unreachable")

    monkeypatch.setattr(web_app_module.socket, "socket", lambda *a, **k: NoRoute())

    assert web_app_module._lan_address() == "127.0.0.1"
