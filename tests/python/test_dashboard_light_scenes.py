from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"


def test_lights_view_has_scene_controls_before_grid() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    lights_panel = html[html.index('data-view-panel="lights"'):html.index('data-view-panel="plugs"')]

    assert 'id="lightScenes"' in lights_panel
    assert lights_panel.index('id="lightScenes"') < lights_panel.index('id="lightGrid"')


def test_light_scenes_target_only_light_switch_cards() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'function renderLightScenes(lightDevices)' in source
    assert 'data-light-scene="on"' in source
    assert 'data-light-scene="off"' in source
    assert 'button[data-light-scene]' in source
    assert '.device-card[data-category="light_switch"]' in source
    assert 'Light scene: all on' in source
    assert 'Light scene: all off' in source


def test_light_scenes_update_fast_and_do_not_overwrite_manual_toggles() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "let manualLightCommandRevision = 0;" in source
    assert "let activeLightSceneCount = 0;" in source
    assert "const manualLightOverrides = new Map();" in source
    assert "function recordManualLightOverride(host, override)" in source
    assert "markManualLightCommand(card, command);" in source
    assert "function applyLightSceneOptimistic(lightCards, command)" in source
    assert "const sceneStartRevision = manualLightCommandRevision;" in source
    assert "applyLightSceneOptimistic(lightCards, command);" in source
    assert "reapplyManualLightOverrides(sceneHosts, sceneStartRevision)" in source
    assert "Light scene: manual override restored" in source
    assert "skipRefresh" in source


def test_light_scene_respects_manual_dim_overrides() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'recordManualLightOverride(host, { type: "brightness", level });' in source
    assert 'override.type === "brightness"' in source
    assert '"/api/devices/" + encodeURIComponent(override.host) + "/brightness"' in source
    assert 'JSON.stringify({ level: override.level })' in source


def test_light_scene_buttons_have_fancy_styles() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".light-scene-row" in css
    assert ".scene-button" in css
    assert ".scene-button.all-on" in css
    assert ".scene-button.all-off" in css
