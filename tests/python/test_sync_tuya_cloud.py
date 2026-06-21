import importlib.util
from pathlib import Path


def _load_sync_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "sync-tuya-cloud.py"
    spec = importlib.util.spec_from_file_location("sync_tuya_cloud", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_security_camera_and_doorbell_devices_are_camera_category() -> None:
    sync = _load_sync_module()

    assert sync._category({"product_name": "Security Camera", "name": "智能门铃"}) == "tuya_camera"
    assert sync._category({"product_name": "Doorbell Camera"}) == "tuya_camera"
