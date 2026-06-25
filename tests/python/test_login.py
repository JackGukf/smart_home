from pathlib import Path
from fastapi.testclient import TestClient
from src.python.web_app import create_app


class FakeController:
    async def status(self, switch):
        from src.python.tplink_switch import SwitchState
        return SwitchState(name=switch.name, host=switch.host, is_on=False, alias=switch.name, model=switch.model)
    async def turn_on(self, switch):
        from src.python.tplink_switch import SwitchState
        return SwitchState(name=switch.name, host=switch.host, is_on=True, alias=switch.name, model=switch.model)
    async def turn_off(self, switch):
        from src.python.tplink_switch import SwitchState
        return SwitchState(name=switch.name, host=switch.host, is_on=False, alias=switch.name, model=switch.model)
    async def toggle(self, switch):
        from src.python.tplink_switch import SwitchState
        return SwitchState(name=switch.name, host=switch.host, is_on=True, alias=switch.name, model=switch.model)


def _minimal_app(tmp_path: Path, auth: bool = True, follow_redirects: bool = False):
    disc = tmp_path / "disc.json"
    disc.write_text('{"count": 0, "switches": []}', encoding="utf-8")
    cfg = tmp_path / "config.yaml"
    if auth:
        cfg.write_text("dashboard_auth:\n  username: admin\n  password: admin\n", encoding="utf-8")
    else:
        cfg.write_text("", encoding="utf-8")
    app = create_app(
        discovery_path=disc,
        config_path=cfg,
        controller=FakeController(),
        check_camera_ports=False,
    )
    return TestClient(app, follow_redirects=follow_redirects)


def test_no_auth_when_dashboard_auth_absent(tmp_path):
    client = _minimal_app(tmp_path, auth=False, follow_redirects=True)
    resp = client.get("/api/health")
    assert resp.status_code == 200
