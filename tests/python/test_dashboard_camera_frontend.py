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
    # Every screen opens the stream; the TV cast asks for its remote's too.
    assert 'new EventSource(tv ? "/api/events/stream?screen=tv" : "/api/events/stream")' in source


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


def test_live_refresh_debounces_and_refreshes_camera_triggers() -> None:
    """Sensor events refresh the camera path without waiting for the 60s poll."""
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function scheduleLiveRefresh(event)")
    body = source[start:start + 1600]

    assert "clearTimeout(liveRefreshTimer)" in body
    assert "LIVE_REFRESH_DEBOUNCE_MS" in body
    assert "refreshLiveCameraTriggers(entityIds)" in body
    assert 'requestJson("/api/cameras")' in source


def test_the_security_view_draws_the_house_and_the_card_draws_chips() -> None:
    """Two surfaces, two shapes, on purpose: the view is a picture of the house
    with a pin on each room, the Home card is columns of chips. The square tile
    grid both used to share is gone with them."""
    source = APP_JS.read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    assert "const HOUSE_ROOMS = [" in source
    assert "const HOUSE_PICTURE = " in source and "HOUSE_SVG" not in source
    assert 'data-house-room="' in source
    assert ".house-scene {" in css and ".house-pin {" in css and ".house-room {" not in css
    # The superseded tile markup and its rules are gone, not left orphaned.
    assert "zone-tile" not in source and "zone-tile" not in css
    assert "alarmZoneTilesHtml" not in source


def test_breached_zones_sort_first_and_are_not_marked_by_colour_alone() -> None:
    """An open door is the only thing on this card worth interrupting for."""
    source = APP_JS.read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    start = source.index("function sortedAlarmZones")
    assert "ab - bb" in source[start:start + 400]          # breached first
    rule = css[css.index(".house-pin.breached {"):]
    rule = rule[:rule.index("}")]
    assert "border-color" in rule and "background" in rule  # not colour alone
    # A zone that never reported must not look identical to a confirmed-closed one.
    assert ".house-pip.off" in css and ".alarm-chip.unknown" in css


def test_both_alarm_surfaces_take_a_zone_s_wording_from_one_place() -> None:
    """The Alarm view shows tiles and the Home card shows chips - two shapes on
    purpose - but what a zone *says* is decided once. Two copies of the wording
    is how one surface gains a state the other still calls "Closed"."""
    source = APP_JS.read_text(encoding="utf-8")

    assert "function zoneStateText(zone, breached)" in source
    for fn in ("houseDetailHtml", "renderHomeAlarmCard"):
        body = source.split(f"function {fn}(")[1].split("\nfunction ")[0]
        assert "zoneStateText(" in body, f"{fn} does not use the shared wording"
        assert '"Closed"' not in body, f"{fn} spells a zone state itself"


def test_the_home_alarm_card_is_builtin_so_it_reaches_every_device() -> None:
    """A custom card cannot: custom cards, their layout and their hidden state
    all live in localStorage, so one made on a PC has nothing to carry it to a
    phone. Being built-in is what makes it show up everywhere by default."""
    html = (PROJECT_ROOT / "src" / "python" / "web_static" / "index.html").read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    assert 'data-home-card="alarm"' in html
    assert 'id="homeAlarmBody"' in html
    # In the default layout, so a browser with a saved layout still places it:
    # cardLayoutOf() falls back to this table for an unknown card.
    layout = source.split("const DEFAULT_HOME_LAYOUT = {")[1].split("};")[0]
    assert "alarm:" in layout
    # Music has left Home for its own view; it must not still be laid out here.
    assert "bluetooth:" not in layout
    assert 'data-home-card="bluetooth"' not in html


def test_music_is_an_app_under_media() -> None:
    """Media is a launcher; Music is one of its apps, on its own page.

    #btDeviceList is what refreshBluetooth() writes into, and it is queried at
    call time, so it has to survive the move."""
    html = (PROJECT_ROOT / "src" / "python" / "web_static" / "index.html").read_text(encoding="utf-8")

    media = html.split('data-view-panel="media"')[1].split('data-view-panel="youtube"')[0]
    for app in ("youtube", "music", "bluetooth"):
        assert f'class="app-tile" data-goto-view="{app}"' in media
    music = html.split('data-view-panel="music"')[1].split('data-view-panel="bluetooth"')[0]
    assert 'id="btDeviceList"' in music
    assert 'class="page-back" data-goto-view="media"' in music
    assert 'data-view="media"' in html
    # Bluetooth is a page now, not a modal - an app under Media and Discovery.
    assert 'data-goto-view="bluetooth"' in html
    assert 'id="btModal"' not in html
    assert 'id="btTiles"' in html


def test_custom_card_renders_sensors_as_tiles_not_rows() -> None:
    """A custom card is one uniform grid, not tiles stacked above rows."""
    source = APP_JS.read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    assert "function customCardSensorTileHtml(item)" in source
    assert "function customCardRowHtml(item)" not in source
    assert ".custom-sensor-tile {" in css
    # Same square geometry as the light tiles it sits beside.
    block = css[css.index(".custom-sensor-tile {"):css.index(".custom-sensor-tile {") + 400]
    assert "aspect-ratio: 1 / 1" in block

    # The rows are gone everywhere, Bluetooth included (it is tiles now).
    assert "custom-device-row" not in source
    assert ".custom-device-row" not in css


def test_custom_card_orders_controls_by_hand_and_readouts_alphabetically() -> None:
    """Two orderings, because the two kinds differ in what the user can control.

    Lights and plugs are drag-reorderable and that order is persisted, so it must
    be respected. Sensors cannot be dragged, so pick order gives neither control
    nor predictability - alphabetical does.
    """
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("const controls = items.filter")
    body = source[start:start + 700]

    assert "localeCompare" in body                       # readouts sorted
    assert "controls.map(customCardTileHtml)" in body     # controls keep their order
    assert "readouts.map(customCardSensorTileHtml)" in body


def test_alerting_custom_tile_is_not_marked_by_colour_alone() -> None:
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")
    rule = css[css.index(".custom-sensor-tile.alert {"):]
    rule = rule[:rule.index("}")]

    assert "border-color" in rule and "background" in rule


def test_jump_to_view_tiles_work_from_the_keyboard() -> None:
    """They declare role=button and tabindex, so they must answer Enter/Space."""
    source = APP_JS.read_text(encoding="utf-8")

    assert "'[data-goto-view][role=\"button\"]'" in source
    start = source.index("'[data-goto-view][role=\"button\"]'")
    assert "activateView(goto.dataset.gotoView)" in source[start:start + 300]



def test_custom_sensor_tile_icon_reflects_what_is_measured() -> None:
    """A door, a smoke alarm and a leak detector must not share one icon."""
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function customCardSensorIcon(item)")
    body = source[start:start + 700]

    assert "tuyaHaIcon(" in body
    # Battery rides along on nearly every device and identifies none of them.
    assert 'includes("battery")' in body


def test_custom_sensor_name_wraps_to_two_lines() -> None:
    """Sensor names are long; one ellipsised line did not identify the sensor."""
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")
    rule = css[css.index(".custom-sensor-name {"):]
    rule = rule[:rule.index("}")]

    assert "-webkit-line-clamp: 2" in rule
    assert "overflow-wrap: anywhere" in rule


def test_sensor_suffix_stripping_is_left_alone() -> None:
    """Group names feed `sensor:` inventory keys, which area assignments store.

    Changing the stripping rule renamed 7 groups on the live board and made 6 of
    them worse ("Smart button at office" -> "Smart button at office Battery"),
    while silently invalidating stored assignments. The colliding entity was
    renamed instead.
    """
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function groupSensorDevices(devices)")
    body = source[start:start + 400]

    assert ".map(([name, readings]) => ({ name, readings }))" in body
