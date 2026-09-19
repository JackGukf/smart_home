"""Cast to TV: the switch, the renderer protocol, and what "off" costs.

The service itself drives Chromium, ffmpeg and a real TV dongle, so it was
proven on the board (2026-09-18: the LLANO-S450 played the stream for four
minutes). These pin the parts that decide what it does and whether it may.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import dashboard_cast as dc
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNIT = PROJECT_ROOT / "deploy" / "systemd" / "user" / "dashboard-cast.service"
INSTALLER = PROJECT_ROOT / "scripts" / "install-dashboard-service.sh"

# The LLANO-S450's own description, trimmed (http://192.168.0.59:60099/).
LLANO_DESCRIPTION = """<?xml version="1.0" encoding="utf-8"?>
<root xmlns="urn:schemas-upnp-org:device-1-0"><specVersion><major>1</major><minor>0</minor></specVersion>
<device><deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
<friendlyName>LLANO-S450 289CB541</friendlyName>
<UDN>uuid:ae12a83a-7445-4245-b1d6-79734dfea9d7</UDN>
<serviceList>
<service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType><serviceId>urn:upnp-org:serviceId:AVTransport</serviceId><SCPDURL>AVTransport/scpd.xml</SCPDURL><controlURL>AVTransport/control</controlURL><eventSubURL>AVTransport/event</eventSubURL></service>
<service><serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType><serviceId>urn:upnp-org:serviceId:RenderingControl</serviceId><SCPDURL>RenderingControl/scpd.xml</SCPDURL><controlURL>RenderingControl/control</controlURL><eventSubURL>RenderingControl/event</eventSubURL></service>
</serviceList></device></root>"""


class FakeSystemctl:
    """Answers like `systemctl --user` for one unit, and records what was asked."""

    def __init__(self, installed: bool = True, enabled: bool = False, fail: str = ""):
        self.installed, self.enabled, self.fail = installed, enabled, fail
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        verb = argv[2]
        if verb == "is-enabled":
            out = ("enabled" if self.enabled else "disabled") if self.installed else ""
            return subprocess.CompletedProcess(argv, 0 if self.enabled else 1, out + "\n", "")
        if verb == "is-active":
            return subprocess.CompletedProcess(argv, 0, ("active" if self.enabled else "inactive") + "\n", "")
        if verb in ("enable", "disable"):
            if self.fail:
                return subprocess.CompletedProcess(argv, 1, "", self.fail)
            self.enabled = verb == "enable"
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected systemctl {argv}")


def _client(tmp_path, runner, status=None, auth=None):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({"dashboard_auth": auth} if auth else {}), encoding="utf-8")
    status_path = tmp_path / "dashboard-cast.json"
    if status is not None:
        status_path.write_text(status, encoding="utf-8")
    app = create_app(config_path=cfg, check_camera_ports=False, cast_runner=runner, cast_status_path=status_path)
    return TestClient(app, raise_server_exceptions=False, follow_redirects=False), cfg


# ── The switch ──────────────────────────────────────────────────────────────

def test_casting_is_off_by_default_and_nothing_runs(tmp_path):
    runner = FakeSystemctl()
    client, _ = _client(tmp_path, runner)

    doc = client.get("/api/cast").json()

    assert doc == {"installed": True, "enabled": False, "running": False, "status": None}
    assert not any(call[2] in ("enable", "start") for call in runner.calls)


def test_switching_on_enables_and_starts_the_unit_and_off_stops_it(tmp_path):
    runner = FakeSystemctl()
    client, _ = _client(tmp_path, runner)

    on = client.put("/api/cast", json={"enabled": True})
    assert on.status_code == 200 and on.json()["enabled"] and on.json()["running"]
    assert ["systemctl", "--user", "enable", "--now", "dashboard-cast.service"] in runner.calls

    off = client.put("/api/cast", json={"enabled": False})
    assert off.status_code == 200 and not off.json()["enabled"] and not off.json()["running"]
    assert ["systemctl", "--user", "disable", "--now", "dashboard-cast.service"] in runner.calls


def test_a_failed_switch_says_why(tmp_path):
    client, _ = _client(tmp_path, FakeSystemctl(fail="Failed to enable unit: Access denied"))

    response = client.put("/api/cast", json={"enabled": True})

    assert response.status_code == 502
    assert "Access denied" in response.json()["detail"]


def test_a_board_without_the_unit_cannot_be_switched(tmp_path):
    runner = FakeSystemctl(installed=False)
    client, _ = _client(tmp_path, runner)

    assert client.get("/api/cast").json()["installed"] is False
    assert client.put("/api/cast", json={"enabled": True}).status_code == 503
    assert not any(call[2] == "enable" for call in runner.calls)


def test_the_status_is_shown_only_while_the_service_runs(tmp_path):
    report = '{"state": "casting", "renderer": "LLANO-S450 289CB541", "fps": 4, "detail": ""}'

    client, _ = _client(tmp_path, FakeSystemctl(enabled=True), status=report)
    assert client.get("/api/cast").json()["status"]["state"] == "casting"

    # A report left behind by a crash is not what it is doing now.
    stale, _ = _client(tmp_path, FakeSystemctl(enabled=False), status=report)
    assert stale.get("/api/cast").json()["status"] is None


def test_the_switch_is_behind_the_login(tmp_path):
    client, _ = _client(tmp_path, FakeSystemctl(), auth={"username": "admin", "password": "pw"})

    assert client.get("/api/cast").status_code in (401, 303, 307)
    assert client.put("/api/cast", json={"enabled": True}).status_code in (401, 303, 307)


def test_the_casts_own_session_gets_past_the_real_login(tmp_path):
    """The service mints its session the way the login does; if the two drift
    apart, the TV shows the login page instead of the house."""
    client, cfg = _client(tmp_path, FakeSystemctl(), auth={"username": "admin", "password": "pw"})

    client.cookies.set("session", dc.session_cookie(cfg))

    assert client.get("/api/cast").status_code == 200


# ── The renderer ────────────────────────────────────────────────────────────

def test_the_llano_description_yields_its_transport_control():
    renderer = dc.parse_description(LLANO_DESCRIPTION, "http://192.168.0.59:60099/")

    assert renderer == dc.Renderer("LLANO-S450 289CB541", "192.168.0.59",
                                   "http://192.168.0.59:60099/AVTransport/control",
                                   "http://192.168.0.59:60099/")


def test_a_device_without_av_transport_is_not_a_renderer():
    no_transport = LLANO_DESCRIPTION.replace("AVTransport:1", "Other:1")

    assert dc.parse_description(no_transport, "http://192.168.0.59:60099/") is None


def test_ssdp_replies_are_parsed_and_notifies_are_ignored():
    reply = (b"HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\n"
             b"LOCATION: http://192.168.0.59:60099/\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n")

    assert dc.parse_ssdp_response(reply)["location"] == "http://192.168.0.59:60099/"
    assert dc.parse_ssdp_response(b"NOTIFY * HTTP/1.1\r\nLOCATION: http://x/\r\n\r\n") == {}


def test_the_stream_url_is_escaped_in_the_soap_and_the_metadata():
    url = "http://192.168.0.83:8765/a&b.ts"
    envelope = dc.soap_envelope("SetAVTransportURI",
                                {"InstanceID": 0, "CurrentURI": url, "CurrentURIMetaData": dc.didl_for(url)})

    assert "<CurrentURI>http://192.168.0.83:8765/a&amp;b.ts</CurrentURI>" in envelope
    assert "&lt;DIDL-Lite" in envelope  # the metadata travels as text, not markup
    assert "video/mp2t" in dc.didl_for(url)


def test_it_takes_only_an_idle_tv_and_leaves_someone_elses_cast_alone():
    own = "http://192.168.0.83:8765/"

    assert dc.may_cast("NO_MEDIA_PRESENT", "", own)
    assert dc.may_cast("STOPPED", "http://phone/old-video.mp4", own)
    assert not dc.may_cast("PLAYING", "http://phone/video.mp4", own)


def test_its_own_leftover_stream_does_not_count_as_busy():
    """After a restart the dongle still reports PLAYING our old URL. Reading
    that as "someone else's cast" left the TV blank until it was power-cycled."""
    assert dc.may_cast("PLAYING", "http://192.168.0.83:8765/oldtoken.ts", "http://192.168.0.83:8765/")
    assert dc.may_cast("TRANSITIONING", "http://192.168.0.83:8765/oldtoken.ts", "http://192.168.0.83:8765/")


def test_only_another_cast_takes_the_tv_away():
    ours = "http://192.168.0.83:8765/tok123.ts"

    assert not dc.taken_over(ours, "tok123")
    assert not dc.taken_over("", "tok123")  # the EZCast forgets the URI while it opens one
    assert dc.taken_over("http://phone/video.mp4", "tok123")


def test_a_stuck_chromium_is_replaced_not_the_cast(monkeypatch):
    """A screenshot that timed out used to end the whole cast; now it is a stall
    to recover from, while the feeder keeps the last picture on the TV."""
    stream = dc.Stream(dc.Settings())
    assert stream.capture_stalled() is None

    monkeypatch.setattr(dc.time, "monotonic", lambda: stream.last_frame_at + dc.STALL_S + 1)
    assert "no new picture" in stream.capture_stalled()
    assert stream.failed() is None  # the stream itself is fine


def test_stalls_are_restarted_long_before_the_renderer_would_give_up():
    assert dc.STALL_S < dc.NO_CLIENT_S
    assert dc.MAX_CHROME_RESTARTS >= 3


def test_the_casts_clock_is_vancouver_not_the_boards_utc(monkeypatch):
    monkeypatch.delenv("DASHBOARD_CAST_TZ", raising=False)
    assert dc.Settings.from_env().timezone == "America/Vancouver"
    monkeypatch.setenv("DASHBOARD_CAST_TZ", "Europe/London")
    assert dc.Settings.from_env().timezone == "Europe/London"
    source = (PROJECT_ROOT / "src" / "python" / "dashboard_cast.py").read_text(encoding="utf-8")
    assert 'env["TZ"] = s.timezone' in source


# ── Off costs nothing ───────────────────────────────────────────────────────

def test_the_unit_is_bounded_and_yields_to_the_rest_of_the_house():
    unit = UNIT.read_text(encoding="utf-8")

    assert "ExecStart=/home/orangepi/smart_home_AI/scripts/run-dashboard-cast.sh" in unit
    assert "MemoryMax=" in unit and "OOMPolicy=stop" in unit
    assert "Nice=10" in unit
    # on-failure, not always: `disable --now` must stay stopped.
    assert "Restart=on-failure" in unit


def test_a_deploy_installs_the_unit_but_never_switches_it_on():
    installer = INSTALLER.read_text(encoding="utf-8")
    optional = installer[installer.index("OPTIONAL_UNITS=("):]
    optional = optional[:optional.index(")")]
    services = installer[installer.index("SERVICE_NAMES=("):]
    services = services[:services.index(")")]

    assert "dashboard-cast.service" in optional
    assert "dashboard-cast.service" not in services  # those are enabled and restarted
    assert "enable --now dashboard-cast" not in installer
    assert 'try-restart "${unit_name}"' in installer  # only if already on


def test_chromium_is_kept_away_from_the_desktop_session():
    """From the user unit, Chromium inherited the desktop's session bus, asked the
    keyring for a password store, and hung before opening DevTools."""
    source = (PROJECT_ROOT / "src" / "python" / "dashboard_cast.py").read_text(encoding="utf-8")

    assert "--password-store=basic" in source
    for variable in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
        assert f'"{variable}"' in source


def test_chromium_is_replaced_before_it_can_reach_the_units_memory_cap():
    unit = UNIT.read_text(encoding="utf-8")
    cap_mb = int(unit.split("MemoryMax=")[1].split("M")[0])

    assert dc.MEMORY_REFRESH_MB < cap_mb * 0.7, "leave room for the replacement to start"
    assert dc.CHROME_REFRESH_S <= 3600


def test_a_routine_refresh_is_not_counted_as_a_failure():
    import asyncio

    stream = dc.Stream(dc.Settings())

    async def no_chrome():
        return None

    stream._start_chrome = no_chrome
    asyncio.run(stream.restart_chrome(stalled=False))
    assert stream.chrome_restarts == 0
    asyncio.run(stream.restart_chrome())
    assert stream.chrome_restarts == 1


def test_the_memory_reading_counts_heap_and_shared_memory_not_cache(tmp_path, monkeypatch):
    cgroup = tmp_path / "user.slice" / "dashboard-cast.service"
    cgroup.mkdir(parents=True)
    (cgroup / "memory.stat").write_text(
        f"anon {300 << 20}\nfile {500 << 20}\nshmem {400 << 20}\nkernel {20 << 20}\n", encoding="utf-8")
    real_path = dc.Path

    def fake_path(p):
        if p == "/proc/self/cgroup":
            f = tmp_path / "cgroup"
            f.write_text("0::/user.slice/dashboard-cast.service\n", encoding="utf-8")
            return f
        if p == "/sys/fs/cgroup":
            return tmp_path
        return real_path(p)

    monkeypatch.setattr(dc, "Path", fake_path)
    assert dc.unit_memory_mb() == 700


# ── Home Assistant's switch.tv_cast (the Voice Panel's TV Cast) ─────────────

class FakeMQTT:
    def __init__(self):
        self.published: dict[str, tuple[str, bool]] = {}
        self.subscribed: list[str] = []

    def username_pw_set(self, *a): pass
    def will_set(self, *a, **k): pass
    def subscribe(self, topic): self.subscribed.append(topic)

    def publish(self, topic, payload, retain=False):
        self.published[topic] = (payload, retain)


class Message:
    def __init__(self, topic, payload):
        self.topic, self.payload = topic, payload


def _switch(tmp_path, runner, status=None):
    status_file = tmp_path / "dashboard-cast.json"
    if status:
        status_file.write_text(status, encoding="utf-8")
    client = FakeMQTT()
    switch = dc.MQTTSwitch("127.0.0.1", 1883, None, None, run=runner, status_file=status_file,
                           client_factory=lambda: client)
    return switch, client


def _settle(monkeypatch):
    """Run the switch's background work inline."""
    class Now:
        def __init__(self, target, daemon=None, **_):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(dc.threading, "Thread", Now)


def test_home_assistant_is_offered_switch_tv_cast():
    payload = dc.discovery_payload()

    assert payload["default_entity_id"] == "switch.tv_cast"
    assert payload["name"] is None and payload["device"]["name"] == "TV cast"  # friendly name "TV cast"
    assert payload["command_topic"] == "smart_home_ai/cast/set"
    assert {payload["payload_on"], payload["payload_off"]} == {"ON", "OFF"}


def test_connecting_announces_the_switch_and_its_state(tmp_path, monkeypatch):
    _settle(monkeypatch)
    switch, client = _switch(tmp_path, FakeSystemctl(enabled=False))

    switch._on_connect(client, None, None, 0)

    assert "smart_home_ai/cast/set" in client.subscribed
    assert client.published[dc.DISCOVERY_TOPIC][1] is True  # retained
    assert client.published["smart_home_ai/cast/availability"] == ("online", True)
    assert client.published["smart_home_ai/cast/state"] == ("OFF", True)
    assert json.loads(client.published["smart_home_ai/cast/attributes"][0])["text"] == "Off"


def test_home_assistant_switches_casting_on_and_off(tmp_path, monkeypatch):
    _settle(monkeypatch)
    runner = FakeSystemctl()
    switch, client = _switch(tmp_path, runner)

    switch._on_message(client, None, Message("smart_home_ai/cast/set", b"ON"))
    assert ["systemctl", "--user", "enable", "--now", "dashboard-cast.service"] in runner.calls
    assert client.published["smart_home_ai/cast/state"][0] == "ON"

    switch._on_message(client, None, Message("smart_home_ai/cast/set", b"OFF"))
    assert ["systemctl", "--user", "disable", "--now", "dashboard-cast.service"] in runner.calls
    assert client.published["smart_home_ai/cast/state"][0] == "OFF"


def test_anything_but_on_or_off_is_ignored(tmp_path, monkeypatch):
    _settle(monkeypatch)
    runner = FakeSystemctl()
    switch, client = _switch(tmp_path, runner)

    switch._on_message(client, None, Message("smart_home_ai/cast/set", b"TOGGLE; rm -rf"))

    assert not any(call[2] in ("enable", "disable") for call in runner.calls)


def test_a_failed_switch_puts_home_assistant_back_to_the_truth(tmp_path, monkeypatch):
    _settle(monkeypatch)
    switch, client = _switch(tmp_path, FakeSystemctl(fail="Access denied"))

    switch._on_message(client, None, Message("smart_home_ai/cast/set", b"ON"))

    assert client.published["smart_home_ai/cast/state"][0] == "OFF"


def test_the_panel_is_told_what_casting_is_doing(tmp_path):
    report = '{"state": "casting", "renderer": "LLANO-S450 289CB541", "fps": 4, "detail": ""}'
    switch, client = _switch(tmp_path, FakeSystemctl(enabled=True), status=report)

    switch.refresh()

    attributes = json.loads(client.published["smart_home_ai/cast/attributes"][0])
    assert attributes == {"status": "casting", "text": "Casting to LLANO-S450 289CB541"}


def test_an_unchanged_state_is_not_republished_every_poll(tmp_path):
    switch, client = _switch(tmp_path, FakeSystemctl())
    switch.refresh()
    client.published.clear()

    switch.refresh()

    assert client.published == {}


def test_status_lines_for_a_person():
    assert dc.status_text({"installed": True, "enabled": False}) == "Off"
    assert dc.status_text({"enabled": True, "running": True, "status": None}) == "Starting"
    assert dc.status_text({"enabled": True, "running": True,
                           "status": {"state": "waiting", "detail": "LLANO-S450 is not on the network - is the TV on?"}}
                          ) == "Looking for the TV: LLANO-S450 is not on the network - is the TV on?"


def test_switching_in_the_dashboard_tells_home_assistant_at_once(tmp_path):
    runner = FakeSystemctl()
    client, _ = _client(tmp_path, runner)
    refreshed = []

    class Recorder:
        def refresh(self, force=False):
            refreshed.append(force)

    client.app.state.cast_switch = Recorder()
    client.put("/api/cast", json={"enabled": True})

    assert refreshed == [True]


def test_the_voice_panel_switches_the_entity_the_dashboard_publishes():
    panel = (PROJECT_ROOT / "configs" / "esphome" / "voice-panel.yaml").read_text(encoding="utf-8")
    entity = dc.discovery_payload()["default_entity_id"]

    # A launcher app beside Wall panel - it is a remote too - opening page 13,
    # whose back goes to the launcher, not Settings.
    launcher = panel[panel.index("- id: apps_page_2"):panel.index("- id: lights_page")]
    assert 'key: tvcast, title: "TV cast", icon: app_cast, page: 13' in launcher
    assert "set_cast" not in panel
    assert "- lvgl.page.show: cast_page" in panel
    assert "id(current_app) >= 8 && id(current_app) != 13 ? 7 : 0" in panel
    assert '"about", "tv cast"};' in panel and "page <= 13" in panel
    assert (PROJECT_ROOT / "configs" / "esphome" / "panel" / "images" / "app_cast.png").exists()

    page = panel[panel.index("- id: cast_page"):panel.index("- id: about_page")]
    assert f"entity_id: {entity}" in page
    assert "action: switch.turn_on" in page and "action: switch.turn_off" in page
    # The switch and the status line follow Home Assistant, not the tap.
    assert f"id: tv_cast_on\n    entity_id: {entity}" in panel
    assert f"id: tv_cast_text\n    entity_id: {entity}\n    attribute: text" in panel



def test_the_tv_page_is_a_remote_like_the_wall_panels():
    panel = (PROJECT_ROOT / "configs" / "esphome" / "voice-panel.yaml").read_text(encoding="utf-8")
    page = panel[panel.index("- id: cast_page"):panel.index("- id: about_page")]
    wall = panel[panel.index("- id: wall_page"):panel.index("- id: settings_page")]

    for view in ("home", "cameras", "alarm", "devices", "climate", "status"):
        assert f"remote: tv, event: esphome.tv_cast_show_view, screen: \"TV\", key: {view}," in page
        assert f"remote: wall, event: esphome.wall_panel_show_view, screen: \"Hallway wall panel\", key: {view}," in wall
    for event, value in (("esphome.tv_cast_scroll", "up"), ("esphome.tv_cast_scroll", "down"),
                         ("esphome.tv_cast_camera", "prev"), ("esphome.tv_cast_camera", "next")):
        assert f"event: {event}, field: " in page and f"value: {value}," in page
    # Nothing on the TV page reaches the wall panel, and the other way round.
    assert "wall_panel" not in page and "tv_cast_" not in wall
    assert "id: tv_camera\n    entity_id: sensor.tv_cast_camera" in panel
    assert "- id: tv_refresh" in panel and "- id: tv_view" in panel


def test_the_cast_opens_the_dashboard_as_the_tv():
    assert dc.Settings().url.endswith("/?screen=tv")


def test_the_page_asks_for_the_tv_stream_and_reports_the_tvs_camera():
    js = (PROJECT_ROOT / "src" / "python" / "web_static" / "app.js").read_text(encoding="utf-8")

    assert 'new URLSearchParams(location.search).get("screen") === "tv"' in js
    assert '"/api/events/stream?screen=tv"' in js
    tv = js[js.index('source.addEventListener("tv_cast"'):]
    tv = tv[:tv.index("});")]
    assert 'remoteCameraPath = "/api/tv-cast/camera"' in tv
    assert "requestJson(remoteCameraPath" in js
