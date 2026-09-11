#!/usr/bin/env python3
"""
Let one address - the wall panel - in without a password.

This runs **on the Orange Pi**, where both logins live. Do not run it by hand;
run `scripts/enable-kiosk-autologin.py`, which pipes this file to the board so
there is never a stale copy of it sitting there.

There are two doors between a cold-booted panel and a working dashboard, and
they are guarded by different software:

  1. the dashboard's own session cookie  -> dashboard_auth.trusted_hosts
  2. the Home Assistant frame inside it  -> HA's trusted_networks auth provider

Both are address-based, which is the only mechanism the HA *frontend* offers:
a long-lived token cannot log the frontend in, because it keeps its refresh
token in the browser's localStorage rather than in a header we could set.

So the panel's IP address becomes a credential. Give it a static DHCP lease.
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

BEGIN = "# ── smart-home kiosk autologin (managed by scripts/enable-kiosk-autologin.py) ──"
END = "# ── end smart-home kiosk autologin ──"


class _HAYamlLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Home Assistant's `!include` / `!secret` tags.

    Plain safe_load refuses them outright, which would make every configuration
    .yaml look broken. The values behind the tags do not matter here - this
    loader exists only to prove the *structure* of the file still parses.
    """


_HAYamlLoader.add_multi_constructor("!", lambda loader, suffix, node: None)


def log(msg: str) -> None:
    print(msg, flush=True)


def backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.name}.bak-kiosk-{stamp}")
    shutil.copy2(path, dest)
    log(f"    backup: {dest.name}")
    return dest


# ── 1. The dashboard ─────────────────────────────────────────────────────────

def configure_dashboard(config_path: Path, kiosk_ip: str, dry_run: bool) -> bool:
    """Add the panel to dashboard_auth.trusted_hosts. True if the file changed."""
    if not config_path.exists():
        log(f"    SKIP: {config_path} does not exist")
        return False

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    auth = cfg.get("dashboard_auth")
    if not auth:
        log("    SKIP: dashboard_auth is not configured, so there is no login to bypass")
        return False

    hosts = auth.get("trusted_hosts") or []
    if isinstance(hosts, str):
        hosts = [hosts]
    if kiosk_ip in hosts:
        log(f"    already trusted: {kiosk_ip}")
        return False

    hosts.append(kiosk_ip)
    auth["trusted_hosts"] = hosts
    log(f"    trusted_hosts -> {hosts}")
    if dry_run:
        return False

    backup(config_path)
    # The dashboard rewrites this file itself when devices are added, with
    # plain yaml.dump - so match that shape rather than inventing another, and
    # do not bother with comments here: the next rewrite would eat them.
    config_path.write_text(yaml.dump(cfg, default_flow_style=False), encoding="utf-8")
    return True


# ── 2. Home Assistant ────────────────────────────────────────────────────────

async def _ha_current_user(base_url: str, token: str) -> dict:
    """Ask HA who this token belongs to. That user is who the panel logs in as."""
    import aiohttp

    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, heartbeat=30) as ws:
            await ws.receive_json()  # auth_required
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise RuntimeError("Home Assistant rejected HOME_ASSISTANT_TOKEN")
            await ws.send_json({"id": 1, "type": "auth/current_user"})
            while True:
                message = await ws.receive_json()
                if message.get("id") == 1:
                    if not message.get("success"):
                        raise RuntimeError(f"auth/current_user failed: {message.get('error')}")
                    return message["result"]


def _load_env_token(project_root: Path) -> str:
    """Read HOME_ASSISTANT_TOKEN out of the board's .env without sourcing it."""
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*(?:export\s+)?HOME_ASSISTANT_TOKEN\s*=\s*(.*)$", line)
            if match:
                return match.group(1).strip().strip("'\"")
    return os.environ.get("HOME_ASSISTANT_TOKEN", "")


def _auth_block(kiosk_cidr: str, user_id: str, user_name: str) -> str:
    return "\n".join([
        BEGIN,
        f"# The wall panel at {kiosk_cidr} has no keyboard, so it is logged in by",
        f"# address, as {user_name!r}. Every other client still gets the password form.",
        "#",
        "# Two things here are load-bearing and look like style:",
        "#",
        "#   trusted_networks is FIRST. The frontend renders providers[0] as the",
        "#   login form and the rest under 'Or log in with' - with homeassistant",
        "#   first the panel gets a password box and a link it cannot click.",
        "#   Listing it first costs nobody anything: /auth/providers is computed",
        "#   per client address, so an untrusted browser is never offered it.",
        "#",
        "#   homeassistant is still LISTED. Declaring auth_providers at all",
        "#   replaces Home Assistant's implicit default; drop that line and no",
        "#   password login works from anywhere, ever again.",
        "homeassistant:",
        "  auth_providers:",
        "    - type: trusted_networks",
        "      trusted_networks:",
        f"        - {kiosk_cidr}",
        "      trusted_users:",
        f"        {kiosk_cidr}: {user_id}",
        "      allow_bypass_login: true",
        "    - type: homeassistant",
        END,
    ]) + "\n"


def configure_home_assistant(
    ha_config: Path, kiosk_ip: str, base_url: str, token: str, dry_run: bool
) -> bool:
    if not ha_config.exists():
        log(f"    SKIP: {ha_config} does not exist")
        return False

    text = ha_config.read_text(encoding="utf-8")
    kiosk_cidr = str(ipaddress.ip_network(f"{kiosk_ip}/32", strict=False))

    if not token:
        raise SystemExit(
            "    HOME_ASSISTANT_TOKEN is not set on the board (.env), so the panel's\n"
            "    Home Assistant user cannot be identified. Set it and re-run."
        )

    user = asyncio.run(_ha_current_user(base_url, token))
    user_id, user_name = user["id"], user.get("name") or "unknown"
    if not user.get("is_admin", False):
        log(f"    note: {user_name} is not an admin; the panel will see what that user sees")
    log(f"    panel logs in as: {user_name} ({user_id})")

    block = _auth_block(kiosk_cidr, user_id, user_name)

    if BEGIN in text:
        updated = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?",
            block,
            text,
            flags=re.DOTALL,
        )
        if updated == text:
            log("    already configured, unchanged")
            return False
        log("    updating the existing managed block")
    elif re.search(r"^homeassistant:", text, flags=re.MULTILINE):
        # Merging into a hand-written homeassistant: block textually is how you
        # end up with a duplicate key and an HA that will not start. Stop, and
        # hand the user the exact lines instead.
        lines = block.splitlines()
        keys = lines[lines.index("homeassistant:") + 1 : lines.index(END)]
        raise SystemExit(
            "    configuration.yaml already has a `homeassistant:` section.\n"
            "    Refusing to guess at a merge - add these keys under it yourself:\n\n"
            + "\n".join("      " + line for line in keys)
        )
    else:
        log("    appending the managed block")
        updated = text.rstrip("\n") + "\n\n" + block

    # A configuration.yaml that does not parse takes the whole house down until
    # somebody notices, so prove it parses before it ever reaches the disk.
    try:
        yaml.load(updated, Loader=_HAYamlLoader)
    except yaml.YAMLError as exc:
        raise SystemExit(f"    the edit does not parse, nothing written: {exc}")

    if dry_run:
        return False

    backup(ha_config)
    ha_config.write_text(updated, encoding="utf-8")
    return True


def check_ha_config(container: str) -> bool:
    log("==> Validating the Home Assistant config...")
    result = subprocess.run(
        ["docker", "exec", container, "python", "-m", "homeassistant",
         "--script", "check_config", "-c", "/config"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        log("    config OK")
        return True
    tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
    log("    check_config FAILED:")
    for line in tail:
        log(f"      {line}")
    return False


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kiosk-ip", required=True, help="the wall panel's IP address")
    parser.add_argument("--project-root", default="/home/orangepi/smart_home_AI")
    parser.add_argument("--ha-config", default="/home/orangepi/homeassistant-config/configuration.yaml")
    parser.add_argument("--ha-container", default="homeassistant")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    parser.add_argument("--no-restart", action="store_true", help="edit the files, restart nothing")
    args = parser.parse_args()

    ipaddress.ip_address(args.kiosk_ip)  # fail loudly on a typo, before editing
    project_root = Path(args.project_root)
    config_path = project_root / "configs" / "devices.local.yaml"

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {} if config_path.exists() else {}
    base_url = ((cfg.get("home_assistant") or {}).get("base_url")) or "http://127.0.0.1:8123"

    log(f"==> Panel: {args.kiosk_ip}{'  (dry run)' if args.dry_run else ''}")
    log("==> Dashboard login...")
    dashboard_changed = configure_dashboard(config_path, args.kiosk_ip, args.dry_run)

    log("==> Home Assistant login...")
    ha_changed = configure_home_assistant(
        Path(args.ha_config), args.kiosk_ip, base_url,
        _load_env_token(project_root), args.dry_run,
    )

    if args.dry_run:
        log("==> Dry run, nothing written.")
        return 0

    if ha_changed and not check_ha_config(args.ha_container):
        backups = sorted(Path(args.ha_config).parent.glob(f"{Path(args.ha_config).name}.bak-kiosk-*"))
        shutil.copy2(backups[-1], args.ha_config)
        log(f"    restored {backups[-1].name} - Home Assistant was NOT restarted")
        return 1

    if args.no_restart:
        log("==> --no-restart: changes are on disk but not live yet.")
        return 0

    if dashboard_changed:
        log("==> Restarting the dashboard...")
        subprocess.run(["systemctl", "--user", "restart", "smart-home-dashboard"], check=True)

    if ha_changed:
        log("==> Restarting Home Assistant (takes about a minute)...")
        subprocess.run(["docker", "restart", args.ha_container], check=True,
                       capture_output=True, text=True)

    log("==> Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
