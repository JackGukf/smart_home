"""Deployment targets, read from ``configs/hosts.env``.

The single place a board address is written down. See that file for why.

Mirrors ``scripts/lib/hosts.sh`` exactly, including the precedence rule: an
environment variable that is already set wins over the file, so
``PI_HOST=192.168.0.99 python3 scripts/whatever.py`` behaves the same way it
does for the shell scripts.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOSTS_FILE = Path(os.environ.get("SMART_HOME_HOSTS") or PROJECT_ROOT / "configs" / "hosts.env")


def load_hosts(path: Path | None = None) -> dict[str, str]:
    """Parse the file into a dict. Missing file yields an empty dict."""
    source = Path(path) if path is not None else HOSTS_FILE
    values: dict[str, str] = {}
    if not source.is_file():
        return values

    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.isidentifier():
            values[key] = value.strip()
    return values


class MissingHost(RuntimeError):
    """A setting was asked for that configs/hosts.env does not define."""


def host(name: str, default: str | None = None) -> str:
    """One setting, with the environment taking precedence over the file.

    Deliberately has no built-in address fallback. A stale literal hiding in
    this module would be a second place the board's address is written down,
    which is the exact problem the file exists to remove - and it would fail
    silently, by talking to the wrong machine, rather than loudly.
    """
    from_env = os.environ.get(name)
    if from_env:
        return from_env
    value = load_hosts().get(name)
    if value:
        return value
    if default is not None:
        return default
    raise MissingHost(f"{name} is not set in {HOSTS_FILE} or the environment")


# Convenience constants for the common case. Read at import time, which is what
# a script wants for an argparse default; call host() instead if the process is
# long-lived and the environment might change under it.
PI_HOST = host("PI_HOST")
PI_USER = host("PI_USER")
REMOTE_PATH = host("REMOTE_PATH")
RPI4_HOST = host("RPI4_HOST")
RPI4_USER = host("RPI4_USER")
RPI4_REMOTE_PATH = host("RPI4_REMOTE_PATH")
DASHBOARD_PORT = host("DASHBOARD_PORT")
