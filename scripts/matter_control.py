#!/usr/bin/env python3
"""
Matter light switch control — uses chip-tool to talk to the bridge over the
Matter protocol.  Tests the full path: Python → chip-tool → Matter → bridge → Kasa.

Prerequisites:
  - build/chip-tool-x86/chip-tool must exist (build with scripts/build-chip-tool.sh)
  - Matter bridge running on Pi at 192.168.0.176
  - Bridge pairing code: 34970112332

Usage:
  python3 scripts/matter_control.py                       # list switches
  python3 scripts/matter_control.py on   3                # turn on by list index
  python3 scripts/matter_control.py off  3                # turn off by list index
  python3 scripts/matter_control.py toggle 3              # toggle by list index
  python3 scripts/matter_control.py on  "Kitchen"         # match by name substring
  python3 scripts/matter_control.py on  ep:5              # by Matter endpoint ID
  python3 scripts/matter_control.py commission            # (re-)commission chip-tool
"""
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent.resolve()
PROJECT_DIR  = SCRIPT_DIR.parent
CHIP_TOOL    = PROJECT_DIR / "build" / "chip-tool-x86" / "chip-tool"
NODE_ID      = 1
AGG_EP       = 1
PAIRING_CODE  = "34970112332"
CHIP_CONFIG   = Path("/tmp/chip_tool_config.ini")
CHIP_COUNTERS = Path("/tmp/chip_counters.ini")
# Persistent backup so the config survives /tmp clears between sessions.
CHIP_CONFIG_BACKUP = PROJECT_DIR / ".chip-tool" / "chip_tool_config.ini"

# Endpoints known to be OnOff light switches in this bridge build.
# ep=3..9 are Kasa switches; update if your bridge layout changes.
LIGHT_EP_RANGE = range(3, 10)


# ── chip-tool runner ──────────────────────────────────────────────────────────

def run_chip(args: list[str], timeout: int = 30) -> tuple[str, bool]:
    """Run chip-tool, return (output, success)."""
    cmd = [str(CHIP_TOOL)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout + r.stderr
        ok = "Run command failure" not in out and r.returncode == 0
        return out, ok
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT after {timeout}s]", False


def parse_value(output: str, key: str) -> str | None:
    m = re.search(rf"{re.escape(key)}:\s*(.+)", output)
    return m.group(1).strip() if m else None


# ── commissioning ─────────────────────────────────────────────────────────────

def _save_config_backup() -> None:
    """Copy /tmp chip-tool config to a persistent location in the project."""
    CHIP_CONFIG_BACKUP.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(CHIP_CONFIG, CHIP_CONFIG_BACKUP)


def _restore_config_backup() -> bool:
    """Restore config from backup if /tmp config is missing. Returns True if restored."""
    if not CHIP_CONFIG_BACKUP.exists():
        return False
    import shutil
    shutil.copy2(CHIP_CONFIG_BACKUP, CHIP_CONFIG)
    print("  Restored chip-tool config from project backup.")
    return True


def _session_alive() -> bool:
    """Quick smoke-test: read reachable attribute on ep=1 to check CASE session."""
    out, ok = run_chip(
        ["bridgeddevicebasicinformation", "read", "reachable", str(NODE_ID), "1"],
        timeout=15,
    )
    return ok and "Run command failure" not in out


def commission() -> bool:
    print(f"Commissioning chip-tool → bridge (pairing code {PAIRING_CODE})...")
    CHIP_CONFIG.unlink(missing_ok=True)
    CHIP_COUNTERS.unlink(missing_ok=True)
    out, _ = run_chip([
        "pairing", "code", str(NODE_ID), PAIRING_CODE,
        "--bypass-attestation-verifier", "true",
    ], timeout=40)
    if "completed with success" in out:
        print("  Commissioned OK.\n")
        _save_config_backup()
        return True
    if "Incorrect state" in out or "already" in out.lower():
        print(
            "\n  Commission FAILED: bridge is already paired to another fabric\n"
            "  (Apple Home or a previous chip-tool session).\n"
            "\n"
            "  To fix, factory-reset the bridge on the Pi:\n"
            "    ssh pi@192.168.0.176 'sudo systemctl stop matter-bridge && "
            "rm -f /home/pi/matter-bridge-data/*.ini && "
            "sudo systemctl start matter-bridge'\n"
            "  Then run:  python3 scripts/matter_control.py commission\n"
        )
    else:
        print("  Commission FAILED.")
        print(out[-600:])
    return False


def ensure_commissioned() -> bool:
    if CHIP_CONFIG.exists():
        return True
    # /tmp was cleared — try to restore from the persistent backup first.
    if _restore_config_backup() and CHIP_CONFIG.exists():
        if _session_alive():
            return True
        print("  Restored backup but CASE session is dead (bridge reset?). Re-commissioning...")
        CHIP_CONFIG.unlink(missing_ok=True)
    else:
        print("chip-tool config missing — attempting to commission...")
    return commission()


# ── device operations ─────────────────────────────────────────────────────────

def get_name(ep: int) -> str:
    out, ok = run_chip(["bridgeddevicebasicinformation", "read", "product-name",
                        str(NODE_ID), str(ep)])
    return parse_value(out, "ProductName") or f"ep={ep}"


def get_onoff(ep: int) -> bool | None:
    out, ok = run_chip(["onoff", "read", "on-off", str(NODE_ID), str(ep)])
    val = parse_value(out, "OnOff")
    if val is None:
        return None
    return val.strip().upper() in ("TRUE", "1")


def discover_switches() -> list[dict]:
    """Read name for all known light-switch endpoints (skips on/off to stay fast)."""
    devices = []
    for ep in LIGHT_EP_RANGE:
        print(f"  Reading ep={ep}...", end=" ", flush=True)
        name = get_name(ep)
        print(name)
        devices.append({"ep": ep, "name": name, "on": None})
    return devices


# ── display ───────────────────────────────────────────────────────────────────

def print_devices(devices: list[dict]) -> None:
    if not devices:
        print("No devices found.")
        return
    print(f"\n{'#':<4} {'EP':<5} {'State':<8} Name")
    print("-" * 55)
    for i, d in enumerate(devices):
        state = "ON" if d["on"] else ("OFF" if d["on"] is not None else "?")
        print(f"{i:<4} {d['ep']:<5} {state:<8} {d['name']}")


# ── selector ─────────────────────────────────────────────────────────────────

def resolve(devices: list[dict], selector: str) -> dict | None:
    # Numeric list index
    try:
        idx = int(selector)
        if 0 <= idx < len(devices):
            return devices[idx]
        print(f"Index {idx} out of range (0–{len(devices)-1})")
        return None
    except ValueError:
        pass
    # ep:N
    if selector.lower().startswith("ep:"):
        ep = int(selector[3:])
        for d in devices:
            if d["ep"] == ep:
                return d
        print(f"No device at ep={ep}")
        return None
    # Name substring
    low = selector.lower()
    matches = [d for d in devices if low in d["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous '{selector}':")
        for m in matches:
            print(f"  ep={m['ep']} {m['name']}")
        return None
    print(f"No device matches '{selector}'")
    return None


# ── control ───────────────────────────────────────────────────────────────────

def send_command(ep: int, cmd: str) -> bool:
    out, ok = run_chip(["onoff", cmd, str(NODE_ID), str(ep)], timeout=30)
    if "Sending cluster" in out:
        return True
    if "[TIMEOUT" in out or "failure" in out.lower():
        print(f"  chip-tool output:\n{out[-400:]}")
        return False
    return ok


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not CHIP_TOOL.exists():
        print(f"chip-tool not found: {CHIP_TOOL}")
        print("Build: docker compose run --rm dev bash scripts/build-chip-tool.sh")
        sys.exit(1)

    args = sys.argv[1:]

    if args and args[0] == "commission":
        commission()
        return

    if not ensure_commissioned():
        sys.exit(1)

    cmd = args[0].lower() if args else "list"

    if cmd in ("list", "ls"):
        print("Discovering light switches via Matter...")
        devices = discover_switches()
        print_devices(devices)
        return

    if cmd not in ("on", "off", "toggle"):
        print(f"Unknown command '{cmd}'. Use: on / off / toggle / list / commission")
        sys.exit(1)

    if len(args) < 2:
        print(f"Usage: matter_control.py {cmd} <index|name|ep:N>")
        sys.exit(1)

    print("Discovering light switches via Matter...")
    devices = discover_switches()
    if not devices:
        sys.exit(1)
    print_devices(devices)

    selector = " ".join(args[1:])
    dev = resolve(devices, selector)
    if not dev:
        sys.exit(1)

    actual_cmd = cmd
    if actual_cmd == "toggle":
        actual_cmd = "off" if dev["on"] else "on"

    print(f"\n→ Sending '{actual_cmd}' to ep={dev['ep']} ({dev['name']}) via Matter...")
    if send_command(dev["ep"], actual_cmd):
        print(f"  OK — light should now be {'ON' if actual_cmd == 'on' else 'OFF'}")
    else:
        print("  FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
