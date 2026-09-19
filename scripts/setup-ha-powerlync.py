#!/usr/bin/env python3
"""Connect the BC Hydro PowerLync to Home Assistant, and so to the dashboard.

The PowerLync (Powerley's Plug/Hub, the $75 one BC Hydro offers) reads the
smart meter over Zigbee Smart Energy and sends it to Powerley's cloud. It also
presents itself on the LAN as an Apple HomeKit accessory, with the meter's
demand and register in a custom HomeKit service that Home Assistant's own
HomeKit Controller ignores. The community integration
github.com/Bolshem/powerlync-hub-homeassistant reads that service every 10 s -
locally, no cloud - and turns it into sensors. This script, run on the board:

  1. installs that integration into Home Assistant's config directory, from a
     pinned commit (PINNED_COMMIT), and restarts Home Assistant if it changed;
  2. pairs the PowerLync with HomeKit Controller using the 8-digit setup code
     from its label (--code), unless it is already paired;
  3. adds the Powerlync Energy Monitor entry, and waits for a reading.

The dashboard's /api/energy then finds the sensors by itself (within a minute)
and the Energy card and view switch from sample data to live.

## Before running it

Set the PowerLync up with BC Hydro first - it has to be joined to *this* meter,
which BC Hydro does - and on the house Wi-Fi. Do **not** add it to Apple Home: a
HomeKit accessory accepts one controller, and Home Assistant must be that one.
If it is already paired elsewhere, pairing here fails with "already paired";
remove it there, or factory-reset it, and run this again.

The Energy Bridge ($179) is a different device with its own MQTT; this is not
for it.

Idempotent, and a dry run unless --apply.

    ~/smart_home_AI/.venv/bin/python scripts/setup-ha-powerlync.py --code 12345678 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import re
import sys
import tarfile
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOMAIN = "powerlync_energy"
REPO = "Bolshem/powerlync-hub-homeassistant"
# v1.0.2, 2026-05-05. Its manifest pins aiohomekit==3.2.20, which is what Home
# Assistant 2026.6.3 on the board ships - check before moving either.
PINNED_COMMIT = "bad8a380775beefb61b576871add9c4cb4720b7c"
COMPONENT_FILES = ("__init__.py", "config_flow.py", "manifest.json", "sensor.py", "strings.json")

HOMEKIT = "homekit_controller"
SETUP_CODE = re.compile(r"^\d{3}-?\d{2}-?\d{3}$")


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch_component(commit: str = PINNED_COMMIT) -> dict[str, str]:
    """The integration's files at the pinned commit, by name."""
    url = f"https://codeload.github.com/{REPO}/tar.gz/{commit}"
    with urlopen(url, timeout=30) as response:  # noqa: S310 - fixed GitHub URL
        data = response.read()
    files: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if member.isfile() and parts[1:3] == ["custom_components", DOMAIN] and len(parts) == 4:
                if parts[3] in COMPONENT_FILES:
                    files[parts[3]] = tar.extractfile(member).read().decode("utf-8")
    missing = set(COMPONENT_FILES) - set(files)
    if missing:
        raise RuntimeError(f"{REPO}@{commit[:7]} is missing {sorted(missing)}")
    return files


def ensure_component(config_dir: Path, files: dict[str, str], apply: bool) -> list[str]:
    if not config_dir.is_dir():
        raise RuntimeError(f"Home Assistant config directory {config_dir} not found")
    target = config_dir / "custom_components" / DOMAIN
    changes = []
    for name, text in sorted(files.items()):
        dest = target / name
        existed = dest.is_file()
        if existed and dest.read_text(encoding="utf-8") == text:
            continue
        if apply:
            target.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        changes.append(f"{'update' if existed else 'install'} {dest}")
    return changes


async def restart_home_assistant(session, headers, base) -> None:
    """A new or changed custom integration is only loaded at startup."""
    async with session.post(f"{base}/api/services/homeassistant/restart", headers=headers, json={}) as response:
        response.raise_for_status()
    await asyncio.sleep(10)
    for _ in range(90):
        try:
            async with session.get(f"{base}/api/config", headers=headers) as response:
                if response.status == 200 and (await response.json()).get("state") == "RUNNING":
                    return
        except Exception:  # noqa: BLE001 - connection refused while it restarts
            pass
        await asyncio.sleep(2)
    raise RuntimeError("Home Assistant did not come back within three minutes")


async def entries(session, headers, base, domain: str) -> list[dict]:
    async with session.get(f"{base}/api/config/config_entries/entry", headers=headers) as response:
        response.raise_for_status()
        return [e for e in await response.json() if e.get("domain") == domain]


async def flow_step(session, headers, base, flow_id: str | None, body: dict) -> dict:
    url = f"{base}/api/config/config_entries/flow" + (f"/{flow_id}" if flow_id else "")
    async with session.post(url, headers=headers, json=body) as response:
        result = await response.json(content_type=None)
        if response.status >= 400:
            raise RuntimeError(f"config flow: HTTP {response.status}: {result}")
        return result


async def abort_flow(session, headers, base, flow_id: str) -> None:
    async with session.delete(f"{base}/api/config/config_entries/flow/{flow_id}", headers=headers):
        pass


def powerlync_choice(result: dict) -> str | None:
    """The PowerLync among the HomeKit accessories Home Assistant can see."""
    for field in result.get("data_schema") or []:
        if field.get("name") != "device":
            continue
        options = field.get("options") or []
        keys = [o[0] if isinstance(o, (list, tuple)) else o for o in options]
        if isinstance(options, dict):
            keys = list(options)
        return next((k for k in keys if "powerlync" in str(k).lower()), None)
    return None


async def pair(session, headers, base, code: str) -> str:
    result = await flow_step(session, headers, base, None, {"handler": HOMEKIT, "show_advanced_options": False})
    if result.get("type") == "abort":
        raise RuntimeError(
            f"HomeKit Controller found no unpaired accessory ({result.get('reason')}). Is the PowerLync "
            "powered and on the Wi-Fi? Is it already paired with Apple Home or another controller?")
    flow_id = result["flow_id"]
    try:
        device = powerlync_choice(result)
        if not device:
            raise RuntimeError(f"no PowerLync among the HomeKit accessories on the LAN: {result.get('data_schema')}")
        print(f"found {device}")
        result = await flow_step(session, headers, base, flow_id, {"device": device})
        if result.get("step_id") != "pair":
            raise RuntimeError(f"expected the pairing step, got {result}")
        result = await flow_step(session, headers, base, flow_id, {"pairing_code": code})
        if result.get("type") != "create_entry":
            raise RuntimeError(f"pairing failed: {result.get('errors') or result.get('reason') or result}")
        flow_id = ""
        return result.get("title") or device
    finally:
        if flow_id:
            await abort_flow(session, headers, base, flow_id)


async def wait_for_reading(session, headers, base, seconds: int = 120) -> tuple[str, str] | None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.python.energy import find_powerlync_entities

    for _ in range(seconds // 5):
        async with session.get(f"{base}/api/states", headers=headers) as response:
            states = await response.json()
        found = find_powerlync_entities(states)
        if found:
            value = next(s["state"] for s in states if s["entity_id"] == found[0])
            try:
                float(value)
                return found[0], value
            except ValueError:
                pass
        await asyncio.sleep(5)
    return None


async def run(args: argparse.Namespace) -> int:
    import aiohttp

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1
    if args.code and not SETUP_CODE.match(args.code.strip()):
        print("--code is the 8-digit HomeKit setup code on the PowerLync's label, e.g. 123-45-678",
              file=sys.stderr)
        return 1
    base = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    apply = args.apply
    say = (lambda line: print(line)) if apply else (lambda line: print("would " + line))

    files = fetch_component()
    print(f"fetched {REPO}@{PINNED_COMMIT[:7]}")
    async with aiohttp.ClientSession() as session:
        changes = ensure_component(Path(args.config_dir), files, apply)
        for line in changes:
            say(line)
        if changes and apply:
            print("restarting Home Assistant to load the integration ...")
            await restart_home_assistant(session, headers, base)
            print("Home Assistant is back")

        paired = [e for e in await entries(session, headers, base, HOMEKIT)
                  if "powerlync" in str(e.get("title", "")).lower()]
        if paired:
            print(f"PowerLync already paired with Home Assistant ({paired[0]['title']})")
        elif not args.code:
            print("PowerLync not paired yet: run again with --code <8-digit setup code from its label>")
            return 0 if not apply else 1
        elif not apply:
            say("pair the PowerLync with HomeKit Controller")
        else:
            print(f"paired: {await pair(session, headers, base, args.code.strip())}")

        if await entries(session, headers, base, DOMAIN):
            print("Powerlync Energy Monitor entry already exists")
        elif not apply:
            say("add the Powerlync Energy Monitor entry")
        else:
            result = await flow_step(session, headers, base, None, {"handler": DOMAIN})
            if result.get("type") != "create_entry":
                print(f"could not add Powerlync Energy Monitor: {result}", file=sys.stderr)
                return 1
            print(f"added {result.get('title')}")

        if not apply:
            return 0
        print("waiting for a reading from the meter (it reports about every 30 s) ...")
        reading = await wait_for_reading(session, headers, base)
        if not reading:
            print("no reading within two minutes: check Settings -> Devices -> Powerlync in Home "
                  "Assistant, and that BC Hydro has joined the PowerLync to the meter", file=sys.stderr)
            return 1
        print(f"{reading[0]} = {reading[1]} W - the dashboard switches to live within a minute")
    return 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--code", help="the PowerLync's 8-digit HomeKit setup code, from its label")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123"))
    ap.add_argument("--config-dir", default=os.getenv("HOME_ASSISTANT_CONFIG_DIR", "/home/orangepi/homeassistant-config"),
                    help="Home Assistant's config directory, for the integration")
    ap.add_argument("--apply", action="store_true", help="make the changes (default is a dry run)")
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
