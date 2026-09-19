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
    # Restored through the same routing as a card's own dial, so a Home
    # Assistant or Matter light is restored where it lives.
    assert "lightBrightnessRequest(override.host, override.level)" in source
    assert "lightCommandRequest(override.host, override.command)" in source


def test_light_scenes_send_every_kind_of_light_to_its_own_api() -> None:
    """All lights off failed for every Home Assistant light (the IKEA drivers):
    the scene sent them to the TP-Link endpoint, which answered 404."""
    source = APP_JS.read_text(encoding="utf-8")
    scene = source[source.index("async function runLightScene"):]
    scene = scene[:scene.index("\n}\n")]
    helper = source[source.index("function lightCommandRequest"):]
    helper = helper[:helper.index("\n}\n")]

    assert "lightCommandRequest(host, command)" in scene
    assert "/api/devices/" not in scene and "/api/matter/" not in scene
    assert 'h.startsWith("ha:")' in helper and "/api/home-assistant/entities/" in helper
    assert 'h.startsWith("matter:")' in helper
    # All at once, each settled on its own: one failure does not stop the rest.
    assert "Promise.allSettled" in scene


def test_light_scene_buttons_have_fancy_styles() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".light-scene-row" in css
    assert ".scene-button" in css
    assert ".scene-button.all-on" in css
    assert ".scene-button.all-off" in css


def test_scenes_sit_in_the_header_not_above_the_grid() -> None:
    """Full width and directly above the light cards, "All Lights On" was in the
    path of every tap aimed at a switch and was hit by accident repeatedly. It
    belongs beside the section title, small and to the right."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    lights_panel = html[html.index('data-view-panel="lights"'):html.index('data-view-panel="plugs"')]

    header_end = lights_panel.index("</div>", lights_panel.index('id="lightScenes"'))
    assert lights_panel.index('id="lightScenes"') < lights_panel.index('id="lightGrid"')
    # Inside the section header, which closes before the grid begins.
    assert header_end < lights_panel.index('id="lightGrid"')
    assert 'id="lightDragLock"' in lights_panel


def test_the_header_wraps_rather_than_pushing_controls_off_a_phone() -> None:
    """On an iPhone 15 the Manage and Edit buttons, both chips and the lock come
    to about 400px against ~360px of usable width. Without wrapping the items on
    the right were pushed off the screen instead of onto a second line - which
    is why only the sun chip was visible."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    actions = css[css.index(".section-actions {"):]
    actions = actions[:actions.index("}")]
    assert "flex-wrap: wrap" in actions


def test_the_chip_labels_are_never_hidden() -> None:
    """Hiding them left a bare sun icon with nothing to distinguish the two
    chips. There is room for the labels now the meta line is gone."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".scene-label { display: none; }" not in css
    assert ".scene-label" in css


def test_the_lights_header_carries_no_vendor_line() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    lights_panel = html[html.index('data-view-panel="lights"'):html.index('data-view-panel="plugs"')]

    assert "TP-Link" not in lights_panel
    assert "local control" not in lights_panel


def test_the_scene_chips_are_small_and_uncoloured_backgrounds() -> None:
    """A tinted fill on a chip this size reads as a filled button and invites
    the very tap this change exists to avoid, so only the icon carries colour."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    block = css[css.index(".scene-button {"):css.index(".scene-button:hover")]
    assert "height: 30px" in block, "the chip is not chip-sized"
    assert "min-height: 82px" not in css and "min-height: 66px" not in css
    assert ".scene-button.all-on i" in css
    assert ".scene-button.all-off i" in css


def test_the_home_scene_buttons_live_on_the_quick_actions_card() -> None:
    """They left the Home header for a card of their own, keeping the same data
    attribute, so the existing click handler drives them unchanged."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    assert 'id="homeLightScenes"' not in html
    assert 'id="homeQuickBody"' in html
    assert "function lightSceneChips(lightDevices)" in source
    assert 'data-light-scene="${button.scene}"' in source
    assert 'scene: "on"' in source and 'scene: "off"' in source


def test_the_home_view_controls_moved_to_settings() -> None:
    """The "..." menu is gone: its four buttons are rows in Settings > Home
    view, with their ids intact so every handler bound to them still works."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    page = html[html.index('data-view-panel="homecards"'):]
    page = page[:page.index('<!-- ── STARTUP VIEW ── -->')]
    for control in ("addCustomCardButton", "addAreaButton", "homeCardsButton", "homeResetLayout"):
        assert f'id="{control}"' in page, f"{control} is not on the Home view settings page"
    assert 'id="homeMeta"' in page, "the device and area count moved here too"
    assert 'data-goto-view="homecards"' in html, "Settings needs a tile for it"
    assert "homeViewMenu" not in html and "homeViewMenu" not in source


