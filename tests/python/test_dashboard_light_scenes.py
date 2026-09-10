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


def test_the_scene_chips_are_small_and_uncoloured_backgrounds() -> None:
    """A tinted fill on a chip this size reads as a filled button and invites
    the very tap this change exists to avoid, so only the icon carries colour."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    block = css[css.index(".scene-button {"):css.index(".scene-button:hover")]
    assert "height: 30px" in block, "the chip is not chip-sized"
    assert "min-height: 82px" not in css and "min-height: 66px" not in css
    assert ".scene-button.all-on i" in css
    assert ".scene-button.all-off i" in css


def test_home_renders_the_same_scene_markup_as_lights() -> None:
    """One builder feeds both, so they cannot drift apart."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    assert 'id="homeLightScenes"' in html
    assert "function lightSceneChips(lightDevices)" in source
    assert '#homeLightScenes' in source
    # Still the same data attribute, so the existing click handler is untouched.
    assert 'data-light-scene="on"' in source


def test_the_four_view_controls_are_behind_one_button() -> None:
    """They kept their ids so every handler already bound to them still works -
    only where they live changed."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    menu = html[html.index('id="homeViewMenuList"'):]
    menu = menu[:menu.index("</div>", menu.index('id="homeResetLayout"'))]
    for control in ("addCustomCardButton", "addAreaButton", "homeCardsButton", "homeResetLayout"):
        assert f'id="{control}"' in menu, f"{control} is not inside the menu"
    assert 'aria-haspopup="menu"' in html
    assert 'aria-expanded="false"' in html


def test_the_menu_closes_on_escape_and_on_an_outside_click() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "function closeHomeViewMenu()" in source
    assert "function toggleHomeViewMenu()" in source
    assert 'event.key !== "Escape"' in source
    assert 'if (!event.target.closest("#homeViewMenu")) closeHomeViewMenu();' in source
    # Choosing an item dismisses it; a click on the padding between items does not.
    assert '#homeViewMenuList [role=\'menuitem\']' in source
