#!/usr/bin/env python3
"""
Manual device control tool — bypasses Matter entirely.
Talks directly to the Python bridge sync API over HTTP.

Usage:
  python3 scripts/control_devices.py              # list all devices
  python3 scripts/control_devices.py on  3        # turn on device #3
  python3 scripts/control_devices.py off 3        # turn off device #3
  python3 scripts/control_devices.py toggle 3     # toggle device #3
  python3 scripts/control_devices.py on  "Kitchen light switch"  # by name
"""
import sys
import json
import urllib.request
import urllib.error

BASE = "http://192.168.0.176:8000"


def fetch(path, method="GET", body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def list_devices():
    resp = fetch("/bridge/devices")
    devices = resp if isinstance(resp, list) else resp.get("devices", [])
    if not devices:
        print("No devices returned from bridge API.")
        return []
    print(f"{'#':<4} {'Name':<35} {'State':<8} {'ID'}")
    print("-" * 75)
    for i, d in enumerate(devices):
        state = d.get("state", {})
        on_val = state.get("on", "?")
        on_str = "ON" if on_val is True else ("OFF" if on_val is False else str(on_val))
        print(f"{i:<4} {d.get('name','?'):<35} {on_str:<8} {d.get('device_id','?')}")
    return devices


def send_command(device_id, command):
    try:
        resp = fetch("/bridge/command", method="POST",
                     body={"device_id": device_id, "command": command})
        print(f"  OK: {resp}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()}")
    except Exception as ex:
        print(f"  Error: {ex}")


def resolve_device(devices, selector):
    # Try as integer index
    try:
        idx = int(selector)
        if 0 <= idx < len(devices):
            return devices[idx]
        print(f"Index {idx} out of range (0-{len(devices)-1})")
        return None
    except ValueError:
        pass
    # Try as name substring (case-insensitive)
    sel_lower = selector.lower()
    matches = [d for d in devices if sel_lower in d.get("name", "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous name '{selector}', matches:")
        for m in matches:
            print(f"  {m['name']}")
        return None
    print(f"No device found matching '{selector}'")
    return None


def main():
    args = sys.argv[1:]

    if not args:
        list_devices()
        return

    command = args[0].lower()
    if command not in ("on", "off", "toggle"):
        print(f"Unknown command '{command}'. Use: on / off / toggle")
        sys.exit(1)

    if len(args) < 2:
        print("Specify a device number or name, e.g.:  toggle 3")
        sys.exit(1)

    devices = list_devices()
    if not devices:
        sys.exit(1)

    print()
    selector = " ".join(args[1:])
    dev = resolve_device(devices, selector)
    if not dev:
        sys.exit(1)

    if command == "toggle":
        state = dev.get("state", {})
        on_val = state.get("on")
        command = "off" if on_val is True else "on"

    print(f"Sending '{command}' → {dev['name']} ({dev['device_id']})")
    send_command(dev["device_id"], command)


if __name__ == "__main__":
    main()
