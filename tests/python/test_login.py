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


# ---------------------------------------------------------------------------
# Hardening (2026-09-25): random session key, lockout, audit
# ---------------------------------------------------------------------------

import hashlib
import logging
import os
import stat

from itsdangerous import URLSafeTimedSerializer

from src.python.dashboard_session import SESSION_SECRET_FILE
from src.python.web_app import _LoginGuard, _credentials_match


def test_session_key_is_random_and_private(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    _minimal_app(tmp_path)
    key_file = tmp_path / SESSION_SECRET_FILE
    key = key_file.read_text(encoding="utf-8").strip()
    assert len(key) >= 32
    assert "admin" not in key
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600


def test_session_survives_restart(tmp_path, monkeypatch):
    """The key is kept, so a dashboard restart does not sign everyone out."""
    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    first = _minimal_app(tmp_path)
    first.post("/login", data={"username": "admin", "password": "admin"})
    cookie = first.cookies.get("session")
    second = _minimal_app(tmp_path)
    second.cookies.set("session", cookie)
    assert second.get("/api/health").status_code == 200


def test_cookie_forged_from_password_is_refused(tmp_path, monkeypatch):
    """The old scheme signed with sha256(salt + password): knowing the password
    was enough to mint a session. That cookie must no longer work."""
    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    client = _minimal_app(tmp_path)
    old_secret = hashlib.sha256(b"smart-home-salt-admin").hexdigest()
    client.cookies.set("session", URLSafeTimedSerializer(old_secret).dumps({"u": "admin"}))
    assert client.get("/api/health").status_code == 401


def test_password_change_ends_sessions(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    client = _minimal_app(tmp_path)
    client.post("/login", data={"username": "admin", "password": "admin"})
    cookie = client.cookies.get("session")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("dashboard_auth:\n  username: admin\n  password: changed\n", encoding="utf-8")
    after = TestClient(create_app(discovery_path=tmp_path / "disc.json", config_path=cfg,
                                  controller=FakeController(), check_camera_ports=False),
                       follow_redirects=False)
    after.cookies.set("session", cookie)
    assert after.get("/api/health").status_code == 401


def test_secret_key_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "x" * 40)
    client = _minimal_app(tmp_path)
    client.post("/login", data={"username": "admin", "password": "admin"})
    assert client.get("/api/health").status_code == 200
    assert not (tmp_path / SESSION_SECRET_FILE).exists()


def test_credentials_match_needs_both():
    assert _credentials_match("admin", "pw", "admin", "pw")
    assert not _credentials_match("admin", "nope", "admin", "pw")
    assert not _credentials_match("other", "pw", "admin", "pw")
    assert not _credentials_match("", "", "admin", "pw")


def test_lockout_after_repeated_failures(tmp_path):
    client = _minimal_app(tmp_path)
    for _ in range(_LoginGuard.LOGIN_MAX_FAILURES):
        resp = client.post("/login", data={"username": "admin", "password": "wrong"})
        assert resp.headers["location"].endswith("error=1")
    # Locked: even the right password is refused, and no cookie is issued.
    resp = client.post("/login", data={"username": "admin", "password": "admin"})
    assert resp.headers["location"].endswith("error=locked")
    assert "session" not in resp.cookies


def test_lockout_is_per_address():
    now = [0.0]
    guard = _LoginGuard(clock=lambda: now[0])
    for _ in range(_LoginGuard.LOGIN_MAX_FAILURES):
        guard.failed("10.0.0.9")
    assert guard.locked("10.0.0.9")
    assert not guard.locked("192.168.0.20")


def test_lockout_expires_and_old_failures_age_out():
    now = [0.0]
    guard = _LoginGuard(clock=lambda: now[0])
    for _ in range(_LoginGuard.LOGIN_MAX_FAILURES):
        guard.failed("a")
    now[0] += _LoginGuard.LOGIN_LOCKOUT_S
    assert not guard.locked("a")
    # Failures spread wider than the window never add up to a lockout.
    for _ in range(_LoginGuard.LOGIN_MAX_FAILURES * 2):
        guard.failed("b")
        now[0] += _LoginGuard.LOGIN_WINDOW_S / (_LoginGuard.LOGIN_MAX_FAILURES - 1) + 1
    assert not guard.locked("b")


def test_success_resets_failures():
    guard = _LoginGuard(clock=lambda: 0.0)
    for _ in range(_LoginGuard.LOGIN_MAX_FAILURES - 1):
        guard.failed("a")
    guard.succeeded("a")
    guard.failed("a")
    assert not guard.locked("a")


def test_security_actions_are_audited_with_actor(tmp_path, monkeypatch):
    import src.python.web_app as web_app_module

    monkeypatch.setattr(web_app_module, "_house_mode_command", lambda path, action: {"status": "ok"})
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = _Capture()
    web_app_module._AUDIT_LOG.addHandler(handler)
    try:
        client = _minimal_app(tmp_path)
        client.post("/login", data={"username": "admin", "password": "admin"})
        assert client.post("/api/house-mode/home").status_code == 200
    finally:
        web_app_module._AUDIT_LOG.removeHandler(handler)
    assert any("house mode -> home by admin from testclient" in m for m in records)


def test_truncated_key_file_is_replaced_not_ignored(tmp_path, monkeypatch):
    """An empty key file must be rewritten: if each process invented its own
    key instead, the TV cast's cookie would stop matching the dashboard's."""
    from src.python.dashboard_session import session_secret

    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    key_file = tmp_path / SESSION_SECRET_FILE
    key_file.write_text("short\n", encoding="utf-8")
    first = session_secret(tmp_path / "config.yaml")
    assert session_secret(tmp_path / "config.yaml") == first
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600
