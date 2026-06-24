from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_light_and_plug_cards_support_saved_drag_order() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'light_switch: "light_order_v1"' in source
    assert 'smart_plug: "plug_order_v1"' in source
    assert 'function applyDeviceOrder(devices, category)' in source
    assert 'function saveDeviceOrderFromDom(grid, category)' in source
    assert 'function deviceDragHandle(host)' in source
    assert 'applyDeviceOrder(lightDevices, "light_switch")' in source
    assert 'applyDeviceOrder(devices, "smart_plug")' in source
    assert 'data-device-drag' in source
    assert 'draggable="true"' in source
    assert '.device-card[data-host]' in source
    assert 'saveDeviceOrderFromDom(grid, category); // dragend persistence' in source

def test_light_switch_dragging_is_locked_by_default() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    html = (PROJECT_ROOT / "src" / "python" / "web_static" / "index.html").read_text(encoding="utf-8")

    assert 'id="lightDragLock"' in html
    assert 'const LIGHT_DRAG_UNLOCK_KEY = "light_drag_unlocked_v1";' in source
    assert 'function isLightDragUnlocked()' in source
    assert 'function applyLightDragLockState()' in source
    assert 'card.dataset.category === "light_switch" && !isLightDragUnlocked()' in source
    assert 'data-drag-locked="true"' in source


def test_dimmable_light_cards_have_plus_minus_step_controls() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'class="dim-step dim-plus"' in source
    assert 'data-dim-step="10"' in source
    assert 'class="dim-step dim-minus"' in source
    assert 'data-dim-step="-10"' in source
    assert 'button[data-dim-step]' in source
    assert 'function stepLightBrightness(card, delta)' in source


def test_dimmable_step_controls_survive_dial_refresh() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'function buildDimControlDial(brightness, isOn, dimmable)' in source
    assert 'buildDimControlDial(brightness, isOn, dimmable)' in source
    assert 'buildDimControlDial(brightness, isNowOn, !locked)' in source


def test_fixed_light_optimistic_on_always_uses_full_brightness() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'const brightness = locked ? 100 : (parseInt(card.dataset.brightness, 10) || (isNowOn ? 100 : 10));' in source
    assert 'buildDimControlDial(brightness, isNowOn, !locked)' in source


def test_ambient_light_frontend_fetches_and_renders_view() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'const ambientGrid' in source
    assert 'const ambientCount' in source
    assert 'requestJson("/api/ambient-lights")' in source
    assert 'function renderAmbientLights(payload)' in source
    assert 'function ambientLightCard(light)' in source
    assert 'button[data-ambient-command]' in source
    assert 'button[data-ambient-discover]' in source
    assert 'data-ambient-brightness' in source
    assert 'data-ambient-color' in source
    assert 'async function loadAmbientLights()' in source
    assert 'await loadAmbientLights()' in source
    assert 'Turning on...' in source

