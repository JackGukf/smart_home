#!/usr/bin/env python3
"""Print the Govee cloud device list with each device's capability instances.

Usage:
    GOVEE_API_KEY=... python3 scripts/probe-govee-cloud-device.py [SKU]

Run this on the Pi (or anywhere with the API key) before wiring a new Govee
device into the dashboard — never assume a model's capabilities from its SKU.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = "https://openapi.api.govee.com"


def main() -> int:
    key = os.environ.get("GOVEE_API_KEY")
    if not key:
        print("GOVEE_API_KEY is not set", file=sys.stderr)
        return 2

    wanted = sys.argv[1].upper() if len(sys.argv) > 1 else None

    request = urllib.request.Request(
        f"{BASE}/router/api/v1/user/devices",
        headers={"Govee-API-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    for entry in payload.get("data") or []:
        sku = str(entry.get("sku") or "")
        if wanted and sku.upper() != wanted:
            continue
        print(f"{sku}  {entry.get('deviceName')}")
        print(f"  device: {entry.get('device')}")
        for cap in entry.get("capabilities") or []:
            print(f"  - {cap.get('type')}  instance={cap.get('instance')}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
