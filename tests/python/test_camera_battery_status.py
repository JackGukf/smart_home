from src.python.web_app import CameraDefinition, _camera_card, _home_assistant_camera_battery


def test_configured_camera_card_exposes_battery_powered_flag() -> None:
    camera = CameraDefinition(
        name="Battery Doorbell",
        host="192.168.0.50",
        provider="tuya",
        model="Doorbell",
        room="Front Door",
        snapshot_url="/snapshot.jpg",
        stream_url=None,
        view_url="/stream",
        mjpeg_fps=10,
        mjpeg_width=640,
        mjpeg_quality=7,
        stream_name="battery_doorbell",
        go2rtc_url=None,
        battery_powered=True,
    )

    card = _camera_card(camera, check_ports=False)

    assert card["battery_powered"] is True

def test_home_assistant_tuya_doorbell_battery_level_is_scaled_to_percent() -> None:
    states = [
        {
            "entity_id": "sensor.zhi_neng_men_ling_battery",
            "state": "10",
            "attributes": {"friendly_name": "智能门铃 Battery"},
        }
    ]

    assert _home_assistant_camera_battery("智能门铃", states) == 100