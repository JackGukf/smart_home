"""How a dashboard login session is signed - one place, used by every signer.

The dashboard (web_app) signs a cookie at login and checks it on every request;
the TV cast (dashboard_cast) signs its own so its headless Chromium gets past
the login. Both must derive the signer identically, so neither owns it.

Sessions used to be signed with sha256("smart-home-salt-" + password): anyone
who knew the password could mint a cookie offline, and nothing else could
revoke one. The key is now random - DASHBOARD_SECRET_KEY when set, otherwise a
key generated once and kept beside the config (git-ignored as *.key, mode 0600).
The username and password go into the *salt*, so changing either still signs
every browser out, but knowing them is no longer enough to forge a session.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from pathlib import Path

from itsdangerous import URLSafeTimedSerializer

SESSION_SECRET_FILE = "dashboard_secret.key"
# The placeholder an old deployment plan put in .env; never a real key.
_PLACEHOLDER_KEYS = frozenset({"", "changeme", "change_me"})
_MIN_KEY_LENGTH = 32

_log = logging.getLogger(__name__)


def session_secret(config_path: Path) -> str:
    """The key that signs session cookies. Never derived from the password."""
    configured = os.getenv("DASHBOARD_SECRET_KEY", "").strip()
    if configured not in _PLACEHOLDER_KEYS:
        return configured
    key_file = config_path.parent / SESSION_SECRET_FILE
    existing = _read_key(key_file)
    if existing:
        return existing
    generated = secrets.token_urlsafe(48)
    try:
        # O_EXCL: the dashboard and the cast may start together; the first to
        # create the file wins and the other reads what it wrote. 0600 from
        # the first byte - the key must never be readable by anyone else.
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = _read_key(key_file)
        if existing:
            return existing
        # Present but empty or truncated: replace it, or the two signers
        # would each invent a key and disagree.
        return _replace_key(key_file, generated)
    except OSError as exc:
        # Still secure, just not durable: every restart signs everyone out.
        _log.warning("Could not save the session key to %s (%s); sessions end at restart",
                     key_file, exc)
        return generated
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(generated + "\n")
    return generated


def session_salt(username: str, password: str) -> str:
    """Ties sessions to the current credentials without making them the key."""
    digest = hashlib.sha256(f"{username}\0{password}".encode("utf-8")).hexdigest()
    return f"dashboard-session:{digest}"


def session_signer(config_path: Path, username: str, password: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(session_secret(config_path), salt=session_salt(username, password))


def _replace_key(key_file: Path, generated: str) -> str:
    try:
        fd = os.open(key_file, os.O_WRONLY | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(generated + "\n")
    except OSError as exc:
        _log.warning("Could not rewrite the session key at %s (%s)", key_file, exc)
    return generated


def _read_key(key_file: Path) -> str:
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return key if len(key) >= _MIN_KEY_LENGTH else ""
