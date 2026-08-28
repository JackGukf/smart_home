"""The Status view's Connected card and the listing behind it.

The card opens a modal listing every device the dashboard can address
directly, split by how: Wi-Fi/Ethernet devices by IP, Bluetooth devices by
MAC. Entities proxied through Home Assistant or Matter are deliberately
absent - they have no address of their own, so a row for them would show
nothing useful.
"""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.python.tplink_switch import SwitchState
from src.python.web_app import _is_ip_host, create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"


class FakeController:
    async def status(self, switch) -> SwitchState:
        if switch.host.endswith(".99"):
            raise OSError("unreachable")
        return SwitchState(
            name=switch.name, host=switch.host, is_on=True,
            alias=switch.name, model=switch.model,
        )


def _write_discovery(path: Path) -> None:
    path.write_text(json.dumps({"count": 2, "switches": [
        {"alias": "Kitchen light switch", "device_type": "DeviceType.WallSwitch",
         "host": "192.168.0.110", "is_on": False, "model": "HS220",
         "name": "Kitchen light switch", "mac": "10:27:F5:77:2D:04"},
        {"alias": "Dead plug", "device_type": "DeviceType.Plug",
         "host": "192.168.0.99", "is_on": False, "model": "HS103",
         "name": "Dead plug", "mac": "AA:BB:CC:DD:EE:FF"},
    ]}), encoding="utf-8")


def _write_config(path: Path) -> None:
    path.write_text(
        """
cameras:
  - name: Family room camera
    host: 192.168.0.24
    provider: tplink
    model: C200
    room: Family Room
    snapshot_url: http://192.168.0.24/snap.jpg
ambient_lights:
  devices:
    - name: TV backlight
      provider: govee_ble
      address: C5:31:30:30:4E:4B
      model: H6199
      room: Living Room
""",
        encoding="utf-8",
    )


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_config(config)
    return TestClient(create_app(
        discovery_path=discovery, config_path=config,
        controller=FakeController(), check_camera_ports=False,
    ))


def test_is_ip_host_rejects_proxied_ids() -> None:
    assert _is_ip_host("192.168.0.110")
    assert not _is_ip_host("ha:light.bedroom")
    assert not _is_ip_host("matter:1")
    assert not _is_ip_host("Home Assistant")
    assert not _is_ip_host(None)


def test_listing_groups_devices_by_how_they_are_addressed(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/network/devices").json()

    groups = {group["id"]: group for group in payload["groups"]}
    assert groups["network"]["label"] == "Wi-Fi / Ethernet"
    assert groups["bluetooth"]["label"] == "Bluetooth"

    network = {d["name"]: d for d in groups["network"]["devices"]}
    assert network["Kitchen light switch"]["address"] == "192.168.0.110"
    assert network["Family room camera"]["address"] == "192.168.0.24"
    # Every Wi-Fi row carries a real IP, never a placeholder.
    assert all(_is_ip_host(d["address"]) for d in groups["network"]["devices"])

    bluetooth = {d["name"]: d for d in groups["bluetooth"]["devices"]}
    assert bluetooth["TV backlight"]["address"] == "C5:31:30:30:4E:4B"
    assert "Govee BLE" in bluetooth["TV backlight"]["detail"]

    assert payload["total"] == len(groups["network"]["devices"]) + len(groups["bluetooth"]["devices"])


def test_unreachable_device_is_listed_but_marked_offline(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/network/devices").json()

    network = {d["name"]: d for d in payload["groups"][0]["devices"]}
    # A switch that did not answer still belongs in the inventory - knowing its
    # address is the point - but it must not claim to be reachable.
    assert network["Dead plug"]["online"] is False
    assert network["Kitchen light switch"]["online"] is True


def test_write_only_devices_report_unknown_rather_than_offline(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/network/devices").json()

    backlight = payload["groups"][1]["devices"][0]
    # BLE ambient lights cannot be read back, so claiming either state lies.
    assert backlight["online"] is None


def test_status_view_has_a_clickable_connected_card() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    status_panel = html[html.index('data-view-panel="status"'):html.index('data-view-panel="lights"')]
    assert 'id="openNetworkModal"' in status_panel
    assert 'id="networkCount"' in status_panel
    # A button, so it is keyboard reachable and announced as a control.
    assert re.search(r'<button class="stat-card stat-card-action" id="openNetworkModal"', status_panel)


def test_modal_markup_and_wiring_exist() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")

    assert 'id="networkModal"' in html
    assert 'id="networkModalList"' in html
    assert 'aria-modal="true"' in html[html.index('id="networkModal"'):]
    assert '/api/network/devices' in js
    assert "renderNetworkModalList" in js
    assert ".net-modal-list" in css
    assert ".stat-card-action" in css


def test_five_stat_cards_still_fit_on_a_phone() -> None:
    css = STYLES.read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(5, 1fr)" in css
    # The narrow-screen rules must come after the 5-column default, or the
    # stat row would stay five-across on a phone.
    five_col = css.index("grid-template-columns: repeat(5, 1fr)")
    two_col = css.index(".stat-row { grid-template-columns: repeat(2, 1fr); }")
    assert five_col < two_col


def test_rescan_repolls_devices_and_looks_for_moved_addresses(tmp_path: Path, monkeypatch) -> None:
    from src.python import web_app as web_app_module

    scans = []

    async def fake_scan(timeout: int = 8) -> dict[str, str]:
        scans.append(timeout)
        # The dead plug turns out to have moved to a new lease.
        return {"AA:BB:CC:DD:EE:FF": "192.168.0.98"}

    monkeypatch.setattr(web_app_module, "discover_hosts_by_mac", fake_scan)
    client = _client(tmp_path)

    client.get("/api/network/devices")            # prime the cache
    payload = client.post("/api/network/devices/rescan").json()

    assert scans, "rescan did not run a discovery scan"
    network = {d["name"]: d for d in payload["groups"][0]["devices"]}
    assert network["Dead plug"]["address"] == "192.168.0.98", "rescan did not pick up the new address"


def test_rescan_ignores_the_automatic_scan_rate_limit(tmp_path: Path, monkeypatch) -> None:
    from src.python import web_app as web_app_module

    scans = []

    async def fake_scan(timeout: int = 8) -> dict[str, str]:
        scans.append(timeout)
        return {}

    monkeypatch.setattr(web_app_module, "discover_hosts_by_mac", fake_scan)
    client = _client(tmp_path)

    # Pressing the button is a deliberate act; waiting out the interval that
    # exists to throttle *automatic* scans would defeat the point.
    client.post("/api/network/devices/rescan")
    client.post("/api/network/devices/rescan")

    assert len(scans) == 2


def test_rescan_button_is_wired_up() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    modal = html[html.index('id="networkModal"'):]
    assert 'id="networkModalRescan"' in modal
    assert "/api/network/devices/rescan" in js
    # A slow action needs to say it is working and refuse a second press.
    assert "rescanBtn.disabled = true" in js
