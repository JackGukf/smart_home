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





def test_all_lights_on_skips_lights_that_are_already_on() -> None:
    """Sent to a light already on, the IKEA drivers flash; the owner's rule is
    that nothing that turns lights on does that. Off still goes to every light."""
    source = APP_JS.read_text(encoding="utf-8")
    scene = source[source.index("async function runLightScene"):]
    scene = scene[:scene.index("\n}\n")]

    assert 'command === "on" ? allCards.filter((card) => card.classList.contains("on")) : []' in scene
    assert "lightCards = allCards.filter((card) => !alreadyOn.includes(card))" in scene
    assert '"already on"' in scene and ".concat(skippedRows)" in scene


# ── Which devices All lights on / off switch ────────────────────────────────

import json as _json
import shutil as _shutil
import subprocess as _subprocess

import pytest as _pytest
import yaml as _yaml
from fastapi.testclient import TestClient as _TestClient

from src.python import web_app as _web_app


def _pick(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth, i = 0, source.index("{", start)
    for i in range(i, len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
    raise AssertionError(name)


def test_the_scene_is_the_lights_group_plus_and_minus_the_saved_list(tmp_path) -> None:
    """Plugs powering LED strips are added, Stick S3 taken out, and nothing
    outside the list - the Theme page's demo cards were switched before."""
    if not _shutil.which("node"):
        _pytest.skip("node is not installed")
    source = APP_JS.read_text(encoding="utf-8")
    script = f"""
const findDeviceGroup = () => ({{ devices: [{{ key: 'dev:192.168.0.61' }}, {{ key: 'dev:matter:1' }},
                                           {{ key: 'dev:ha:light.0x64028ffffe64de32' }}] }});
let lightScenesDoc = {{ include: ['dev:192.168.0.142', 'dev:192.168.0.165'], exclude: ['dev:matter:1'] }};
{_pick(source, "sceneLightHosts")}
console.log(JSON.stringify(sceneLightHosts().sort()));
"""
    path = tmp_path / "t.js"
    path.write_text(script, encoding="utf-8")
    hosts = _json.loads(_subprocess.run(["node", str(path)], capture_output=True, text=True, check=True).stdout)

    assert hosts == ["192.168.0.142", "192.168.0.165", "192.168.0.61", "ha:light.0x64028ffffe64de32"]


def test_scene_cards_are_one_per_device_and_never_the_theme_demo() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    cards = _pick(source, "sceneLightCards")
    assert 'querySelectorAll(\'.device-card[data-category="light_switch"]\')' not in cards
    assert ':not([data-view-panel="theme"])' in cards and "document.querySelector(" in cards


def _client(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(_yaml.dump({}), encoding="utf-8")
    app = _web_app.create_app(config_path=cfg, check_camera_ports=False,
                              light_scenes_path=tmp_path / "light_scenes.json")
    return _TestClient(app)


def test_the_saved_list_round_trips_and_is_validated(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.get("/api/light-scenes").json() == {"include": [], "exclude": [], "entities": []}

    saved = client.put("/api/light-scenes", json={"include": ["dev:192.168.0.165", "dev:192.168.0.142"],
                                                  "exclude": ["dev:matter:1"]}).json()
    assert saved == {"include": ["dev:192.168.0.142", "dev:192.168.0.165"], "exclude": ["dev:matter:1"], "entities": []}
    assert client.get("/api/light-scenes").json() == saved

    assert client.put("/api/light-scenes", json={"include": ["192.168.0.142"]}).status_code == 400
    assert client.put("/api/light-scenes", json={"include": ["dev:a b"]}).status_code == 400
    assert client.put("/api/light-scenes", json={"include": ["dev:x"], "exclude": ["dev:x"]}).status_code == 400


def test_manage_keeps_only_what_differs_from_the_lights_group(tmp_path) -> None:
    if not _shutil.which("node"):
        _pytest.skip("node is not installed")
    source = APP_JS.read_text(encoding="utf-8")
    script = f"""
{_pick(source, "nextLightScenes")}
const doc = {{ include: ['dev:192.168.0.142'], exclude: ['dev:matter:1'] }};
console.log(JSON.stringify({{
  untickGroupMember: nextLightScenes(doc, 'dev:192.168.0.61', true, false),
  retickGroupMember: nextLightScenes(doc, 'dev:matter:1', true, true),
  tickPlug: nextLightScenes(doc, 'dev:192.168.0.165', false, true),
  untickPlug: nextLightScenes(doc, 'dev:192.168.0.142', false, false),
}}));
"""
    path = tmp_path / "t.js"
    path.write_text(script, encoding="utf-8")
    r = _json.loads(_subprocess.run(["node", str(path)], capture_output=True, text=True, check=True).stdout)

    assert r["untickGroupMember"] == {"include": ["dev:192.168.0.142"], "exclude": ["dev:192.168.0.61", "dev:matter:1"]}
    assert r["retickGroupMember"] == {"include": ["dev:192.168.0.142"], "exclude": []}
    assert r["tickPlug"] == {"include": ["dev:192.168.0.142", "dev:192.168.0.165"], "exclude": ["dev:matter:1"]}
    assert r["untickPlug"] == {"include": [], "exclude": ["dev:matter:1"]}


def test_the_all_lights_sheets_have_manage() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    info = source[source.index("async function quickInfo"):]
    info = info[:info.index("if (button.quick")]
    assert "manage: key" in info
    assert 'data-light-scene-manage="${escapeHtml(manage)}"' in source
