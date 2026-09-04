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
    assert 'data-camera-drag' in source
    # Reordering moved from HTML5 drag-and-drop to pointer events, which iOS
    # Safari actually implements; the order is persisted from the drop.
    assert 'enablePointerReorder({' in source
    assert 'saveCameraOrderFromDom();' in source

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

def test_default_order_falls_back_to_area_position() -> None:
    """Cameras and devices with no hand-dragged order sort by their area.

    Both used to return early on an empty saved order, leaving whatever order the
    backend happened to produce.
    """
    source = APP_JS.read_text(encoding="utf-8")

    assert "function homeAreaRanker()" in source
    # The early return is what defeated a default order; it must stay gone.
    assert "const order = savedCameraOrder();\n  if (order.length === 0) return cameras;" not in source
    assert "const order = savedDeviceOrder(category);\n  if (order.length === 0) return devices;" not in source

    for fn, key_prefix in (("applyCameraOrder", "cam:"), ("applyDeviceOrder", "dev:")):
        start = source.index(f"function {fn}(")
        body = source[start:start + 1200]
        assert "homeAreaRanker()" in body, fn
        assert f"`{key_prefix}" in body, fn
        # Saved drag order still wins; area order is only the tie-break.
        assert "(a.saved - b.saved) || (a.area - b.area) || (a.index - b.index)" in body, fn


def test_area_ranker_matches_resolve_home_areas_resolution() -> None:
    """The ranker must resolve areas the same way the Areas view does.

    If they diverge, an item sorts into one room and renders under another.
    """
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function homeAreaRanker()")
    body = source[start:source.index("function applyDeviceOrder(")]

    assert "assignments[key]" in body          # explicit assignment wins
    assert "idByName.get(String(room" in body  # then exact room-name match
    assert "Number.MAX_SAFE_INTEGER" in body   # no area -> last, with Unassigned


def test_live_updates_are_additive_to_the_poll() -> None:
    """The 60 s poll must survive alongside the stream.

    It is the reconciliation pass for anything the stream missed, and the only
    refresh for state Home Assistant does not report (TP-Link, cameras).
    """
    source = APP_JS.read_text(encoding="utf-8")

    assert "/* Auto-refresh every 60 s */" in source
    assert "}, 60_000);" in source
    assert 'new EventSource("/api/events/stream")' in source


def test_live_updates_never_break_page_load() -> None:
    """A missing or fake EventSource must not throw during load.

    The node test harness stubs EventSource as a bare function, which is exactly
    the shape that broke this: the constructor succeeded and addEventListener did
    not exist.
    """
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function connectLiveUpdates()")
    body = source[start:start + 1800]

    assert 'typeof EventSource !== "function"' in body      # absent entirely
    assert 'typeof source.addEventListener !== "function"' in body  # present but fake
    # The wiring, not just the constructor, sits inside the guard.
    assert body.index("try {") < body.index('addEventListener("changed"')


def test_live_refresh_is_debounced_and_reuses_the_normal_refresh() -> None:
    """A reconnecting bridge republishes everything; that must be one refresh.

    And the stream is a trigger, not a second state feed - it calls the same
    loadDevices() the poll does, so there is one code path building cards.
    """
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function scheduleLiveRefresh()")
    body = source[start:start + 500]

    assert "clearTimeout(liveRefreshTimer)" in body
    assert "loadDevices()" in body
    assert "LIVE_REFRESH_DEBOUNCE_MS" in body


def test_alarm_zones_render_as_tiles_like_the_temperature_card() -> None:
    """Zones moved from full-width rows to a square tile grid.

    The two cards sit side by side on Home, so they share a shape deliberately.
    """
    source = APP_JS.read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    assert 'class="zone-tile-grid"' in source
    assert "zone-tile-icon" in source and "zone-tile-state" in source and "zone-tile-name" in source
    # The superseded row markup and its rules are gone, not left orphaned.
    assert "zone-row" not in source and "zone-row" not in css
    assert ".zone-tile-grid {" in css and ".zone-tile {" in css
    # Same grid geometry as the temperature tiles is what makes them match.
    assert "aspect-ratio: 1 / 1" in css[css.index(".zone-tile {"):css.index(".zone-tile {") + 400]


def test_breached_zones_sort_first_and_are_not_marked_by_colour_alone() -> None:
    """An open door is the only thing on this card worth interrupting for."""
    source = APP_JS.read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    start = source.index("const zonesSorted")
    assert "ab - bb" in source[start:start + 400]          # breached first
    rule = css[css.index(".zone-tile.breached {"):]
    rule = rule[:rule.index("}")]
    assert "border-color" in rule and "background" in rule  # not colour alone
    # A zone that never reported must not look identical to a confirmed-closed one.
    assert ".zone-tile.unknown" in css
