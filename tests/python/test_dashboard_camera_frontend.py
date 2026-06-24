from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_doorbell_camera_stream_renders_as_browser_image_not_video() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'liveType === "snapshot" || liveType === "mjpeg" || liveType === "doorbell"' in source

def test_camera_cards_render_battery_badge_overlay() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'function cameraBatteryBadge(camera)' in source
    assert '${cameraMedia(camera)}${cameraBatteryBadge(camera)}' in source
    assert 'camera.battery_powered' in source

def test_camera_cards_support_drag_saved_order() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'const CAMERA_ORDER_KEY = "camera_order_v1";' in source
    assert 'function applyCameraOrder(cameras)' in source
    assert 'function saveCameraOrderFromDom()' in source
    assert 'draggable="true"' in source
    assert 'data-camera-drag' in source
    assert 'dragstart' in source
    assert 'drop' in source
    assert 'saveCameraOrderFromDom(); // dragend persistence' in source

def test_camera_drag_handle_does_not_overlap_edit_button() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    styles = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    title_start = source.index('function cameraTitle(camera)')
    title_end = source.index('function cameraTitleEditor(camera)')
    title_source = source[title_start:title_end]

    assert '${cameraDragHandle(cameraId)}' in title_source
    assert '${cameraTitle(camera)}\n          ${cameraDragHandle(cameraId)}' not in source
    drag_rule = styles[styles.index('.camera-drag-handle {'):styles.index('.camera-drag-handle:hover')]
    assert 'position: absolute' not in drag_rule