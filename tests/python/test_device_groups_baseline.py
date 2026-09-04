"""The seeded device groups must reproduce today's sidebar exactly.

This cycle's whole promise is "zero visible change". These assertions pin the
seeded document to the values currently hardcoded in index.html and styles.css,
so a drift is a test failure rather than something noticed on the dashboard.
"""

import re
from pathlib import Path

from src.python.web_app import DEFAULT_DEVICE_GROUPS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

EXPECTED_ORDER = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]

# Bridges is seeded but deliberately not builtin: it has no bespoke panel, so
# it renders through the dynamic-group path and gets a dynamic overview tile
# rather than one of the hardcoded builtinTiles entries.
SEEDED_DYNAMIC = ["bridges"]


def _overview_tiles() -> list[tuple[str, str, str]]:
    """(view, icon, label) for each built-in Devices overview tile, in order.

    The seven groups were removed from the sidebar, so the overview tiles are
    now what the dashboard actually shows for them. This keeps the baseline
    pinned to real rendered values rather than to markup that no longer exists.
    """
    javascript = APP_JS.read_text(encoding="utf-8")
    at = javascript.index("const builtinTiles = [")
    block = javascript[at:javascript.index("];", at)]
    found = []
    for match in re.finditer(
        r'\{\s*view:\s*"([^"]+)",\s*label:\s*"([^"]+)",\s*icon:\s*"ti-([a-z0-9-]+)"', block
    ):
        found.append((match.group(1), match.group(3), match.group(2)))
    return found


def _css_group_colors() -> dict[str, str]:
    """view -> bare palette name, from the --group-color declarations."""
    css = re.sub(r"/\*.*?\*/", "", STYLES_CSS.read_text(encoding="utf-8"), flags=re.S)
    colors = {}
    for block in re.finditer(
        r"([^{}]+)\{([^{}]*--group-color\s*:\s*var\(--([a-z]+)\)[^{}]*)\}", css
    ):
        for view in re.findall(r'data-goto-view="([^"]+)"', block.group(1)):
            colors[view] = block.group(3)
    return colors


def test_seeded_ids_and_order_match_the_overview_tiles() -> None:
    seeded = [g["id"] for g in DEFAULT_DEVICE_GROUPS if g["builtin"]]

    assert seeded == EXPECTED_ORDER
    assert [view for view, _icon, _label in _overview_tiles()] == EXPECTED_ORDER
    assert [g["id"] for g in DEFAULT_DEVICE_GROUPS] == EXPECTED_ORDER + SEEDED_DYNAMIC


def test_sensors_group_keeps_the_tuya_id() -> None:
    """data-view="tuya" may already be persisted as a user's default_view.
    Renaming the id to "sensors" would silently break that saved setting."""
    sensors = next(g for g in DEFAULT_DEVICE_GROUPS if g["name"] == "Sensors")

    assert sensors["id"] == "tuya"


def test_seeded_icons_and_labels_match_the_overview_tiles() -> None:
    by_id = {g["id"]: g for g in DEFAULT_DEVICE_GROUPS}

    for view, icon, label in _overview_tiles():
        assert by_id[view]["icon"] == icon, f"{view} icon drifted"
        assert by_id[view]["name"] == label, f"{view} label drifted"


def test_seeded_colors_match_the_stylesheet() -> None:
    by_id = {g["id"]: g for g in DEFAULT_DEVICE_GROUPS}
    css_colors = _css_group_colors()

    for group_id in EXPECTED_ORDER:
        assert by_id[group_id]["color"] == css_colors[group_id], f"{group_id} colour drifted"


def test_split_groups_carry_the_right_reading_filters() -> None:
    by_id = {g["id"]: g for g in DEFAULT_DEVICE_GROUPS}

    assert by_id["environment"]["readingFilter"] == "environment"
    assert by_id["tuya"]["readingFilter"] == "sensors"
    # Environment also collects the standalone Govee cloud sensors, which are a
    # separate inventory kind; readingFilter applies only to sensor-kind members.
    assert by_id["environment"]["kinds"] == ["sensor", "environment"]
    assert by_id["tuya"]["kinds"] == ["sensor"]


def test_only_lights_and_plugs_declare_chrome() -> None:
    with_chrome = {g["id"]: g["chrome"] for g in DEFAULT_DEVICE_GROUPS if g.get("chrome")}

    assert with_chrome == {
        "lights": ["lightScenes", "lightDragLock"],
        "plugs": ["plugActions"],
    }


def test_only_bridges_is_seeded_as_a_dynamic_group() -> None:
    """Builtin means "has a bespoke panel in index.html". Bridges does not: it
    renders through renderDynamicGroupPanel, which only repaints panels whose
    group is not builtin. Marking it builtin would leave it permanently stale."""
    dynamic = [g["id"] for g in DEFAULT_DEVICE_GROUPS if not g["builtin"]]

    assert dynamic == SEEDED_DYNAMIC


def test_bridges_collects_by_rule_because_the_api_cannot_set_kinds() -> None:
    """POST /api/device-groups hardcodes an empty "kinds", so a group that
    collects devices by type can only get that rule from this seed."""
    bridges = next(g for g in DEFAULT_DEVICE_GROUPS if g["id"] == "bridges")

    assert bridges["kinds"] == ["bridge"]
    assert bridges["name"] == "Bridges"
