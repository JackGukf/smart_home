#!/usr/bin/env python3
"""Inspect Home Assistant entities without printing credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def entity_matches(entity: dict[str, Any], terms: list[str]) -> bool:
    if not terms:
        return True
    attributes = entity.get("attributes") or {}
    haystack = " ".join(
        [
            str(entity.get("entity_id") or ""),
            str(entity.get("state") or ""),
            str(attributes.get("friendly_name") or ""),
            str(attributes.get("device_class") or ""),
            str(attributes.get("supported_features") or ""),
        ]
    ).lower()
    return all(term.lower() in haystack for term in terms)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="*", help="Case-insensitive terms that must appear in the entity.")
    parser.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--probe-camera", help="Probe Home Assistant camera proxy endpoints for this camera entity.")
    args = parser.parse_args()

    load_dotenv(args.env_file)
    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        raise SystemExit("HOME_ASSISTANT_TOKEN is not configured.")

    request = Request(
        f"{args.base_url.rstrip('/')}/api/states",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=12) as response:
        states = json.loads(response.read().decode("utf-8"))

    if args.probe_camera:
        camera = next((entity for entity in states if entity.get("entity_id") == args.probe_camera), None)
        if not camera:
            raise SystemExit(f"{args.probe_camera} was not found.")
        attributes = camera.get("attributes") or {}
        paths = [
            f"/api/camera_proxy/{args.probe_camera}",
            f"/api/camera_proxy_stream/{args.probe_camera}",
        ]
        if attributes.get("entity_picture"):
            paths.append(str(attributes["entity_picture"]))
        probes = []
        for path in paths:
            url = path if path.startswith("http") else f"{args.base_url.rstrip('/')}{path}"
            try:
                probe = Request(url, headers={"Authorization": f"Bearer {token}"})
                with urlopen(probe, timeout=12) as response:
                    probes.append(
                        {
                            "path": path.split("?", 1)[0],
                            "status": response.status,
                            "content_type": response.headers.get("Content-Type"),
                            "content_length": response.headers.get("Content-Length"),
                        }
                    )
            except Exception as exc:
                probes.append({"path": path.split("?", 1)[0], "error": str(exc)})
        print(json.dumps(probes, indent=2, ensure_ascii=False))
        return

    rows = []
    for entity in states:
        if not entity_matches(entity, args.terms):
            continue
        attributes = entity.get("attributes") or {}
        rows.append(
            {
                "entity_id": entity.get("entity_id"),
                "state": entity.get("state"),
                "friendly_name": attributes.get("friendly_name"),
                "device_class": attributes.get("device_class"),
                "supported_features": attributes.get("supported_features"),
                "entity_picture": attributes.get("entity_picture"),
                "access_token": bool(attributes.get("access_token")),
                "options": attributes.get("options"),
            }
        )
    print(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
