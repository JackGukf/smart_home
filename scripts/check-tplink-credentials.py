"""Verify TP-Link/Kasa account credentials for KLAP-firmware plugs.

Reads TPLINK_USERNAME / TPLINK_PASSWORD from the environment (or .env in the
current directory), validates them against TP-Link cloud, then attempts a
local KLAP handshake with every plug in tplink_switches.json that has no
readable alias. Prints pass/fail only — never the credentials.

Usage (on the Pi):
    cd ~/smart_home_AI && set -a && . ./.env && set +a && \
        .venv/bin/python scripts/check-tplink-credentials.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path

CLOUD_URL = "https://wap.tplinkcloud.com/"


def _load_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _cloud_call(payload: dict, token: str | None = None) -> dict:
    url = CLOUD_URL + (f"?token={token}" if token else "")
    request = urllib.request.Request(
        url, json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def check_cloud_login(username: str, password: str) -> bool:
    result = _cloud_call(
        {
            "method": "login",
            "params": {
                "appType": "Kasa_Android",
                "cloudUserName": username,
                "cloudPassword": password,
                "terminalUUID": str(uuid.uuid4()),
            },
        }
    )
    code = result.get("error_code")
    if code != 0:
        print(f"[FAIL] TP-Link cloud login: {result.get('msg', 'unknown error')} (code {code})")
        print("       Use the exact email and password you sign into the Kasa app with.")
        return False
    print("[ OK ] TP-Link cloud login accepted these credentials.")
    token = result.get("result", {}).get("token")
    if token:
        devices = _cloud_call({"method": "getDeviceList"}, token)
        for device in devices.get("result", {}).get("deviceList", []):
            print(f"       account device: {device.get('alias')} ({device.get('deviceModel')})")
    return True


async def check_local_plugs(username: str, password: str) -> bool:
    from kasa import Discover

    discovery_path = Path("tplink_switches.json")
    if not discovery_path.exists():
        print("[SKIP] tplink_switches.json not found; skipping local device checks.")
        return True

    payload = json.loads(discovery_path.read_text(encoding="utf-8"))
    hosts = [item["host"] for item in payload.get("switches", []) if not item.get("alias") or item.get("is_on") is None]
    ok = True
    for host in hosts:
        try:
            device = await Discover.discover_single(host, username=username, password=password)
            await device.update()
            print(f"[ OK ] {host}: authenticated locally, device name is '{device.alias}'")
            await device.disconnect()
        except Exception as exc:
            ok = False
            print(f"[FAIL] {host}: {type(exc).__name__}: {exc}")
    return ok


def main() -> int:
    _load_env_file()
    username = (os.getenv("TPLINK_USERNAME") or "").strip()
    password = (os.getenv("TPLINK_PASSWORD") or "").strip()
    if not username or not password:
        print("[FAIL] TPLINK_USERNAME / TPLINK_PASSWORD are not set (env or .env).")
        return 1

    cloud_ok = check_cloud_login(username, password)
    local_ok = asyncio.run(check_local_plugs(username, password)) if cloud_ok else False
    if cloud_ok and local_ok:
        print("All checks passed — restart the dashboard: systemctl --user restart smart-home-dashboard.service")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
