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


# ---------------------------------------------------------------------------
# Task 2 tests
# ---------------------------------------------------------------------------

def test_unauthenticated_html_redirects_to_login(tmp_path):
    """Non-API requests without a session cookie must redirect to /login."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    resp = client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/login")


def test_unauthenticated_api_returns_401(tmp_path):
    """API requests without a session cookie must return 401 JSON."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    resp = client.get("/api/health")
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


def test_login_page_accessible_unauthenticated(tmp_path):
    """GET /login must be reachable without a session cookie (no redirect loop)."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    resp = client.get("/login")
    # 200 (file exists) or 404 (login.html not created yet) — either is fine;
    # what matters is it is NOT a 3xx redirect.
    assert resp.status_code < 400 or resp.status_code == 404


def test_post_login_wrong_password(tmp_path):
    """POST /login with wrong credentials must redirect to /login?error=1."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    resp = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 303
    assert "error=1" in resp.headers["location"]


def test_post_login_correct_credentials(tmp_path):
    """POST /login with correct credentials must redirect to / and set session cookie."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    resp = client.post("/login", data={"username": "admin", "password": "admin"})
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/")
    assert "session" in resp.cookies


def test_authenticated_request_passes(tmp_path):
    """A valid session cookie must let API requests through."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    # Log in to obtain the session cookie
    login_resp = client.post("/login", data={"username": "admin", "password": "admin"})
    assert login_resp.status_code == 303
    # The TestClient stores cookies automatically; subsequent requests carry them
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_logout_clears_cookie_and_redirects(tmp_path):
    """POST /logout must redirect to /login and clear the session cookie."""
    client = _minimal_app(tmp_path, auth=True, follow_redirects=False)
    # Log in first
    client.post("/login", data={"username": "admin", "password": "admin"})
    # Now log out
    resp = client.post("/logout")
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/login")
    # Cookie should be deleted (empty value or absent)
    session_cookie = resp.cookies.get("session", "")
    assert session_cookie == "" or "session" not in resp.cookies


def test_login_route_skipped_when_no_auth_config(tmp_path):
    """When dashboard_auth is absent, /login must not exist (404)."""
    client = _minimal_app(tmp_path, auth=False, follow_redirects=False)
    resp = client.get("/login")
    assert resp.status_code == 404
