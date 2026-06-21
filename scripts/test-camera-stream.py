from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a configured camera stream without printing credentials.")
    parser.add_argument("stream_name", help="Camera stream_name from configs/devices.local.yaml")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "devices.local.yaml"))
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    _load_env(PROJECT_ROOT / ".env")
    cameras = _load_cameras(Path(args.config))
    camera = next((item for item in cameras if item.get("stream_name") == args.stream_name), None)
    if not camera:
        raise SystemExit(f"ERROR no camera with stream_name={args.stream_name!r}")

    url = str(camera.get("stream_url") or _rtsp_url_from_config(camera) or "")
    if not url:
        raise SystemExit("ERROR camera is missing stream_url or credentials")

    variants = [("configured", url)]
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        variants.append(("without_auth", urlunparse(parsed._replace(netloc=f"{parsed.hostname}:{parsed.port}"))))
    if parsed.scheme == "rtsps":
        variants.append(("rtsp_same_port", urlunparse(parsed._replace(scheme="rtsp"))))

    for label, candidate in variants:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                candidate,
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=args.timeout,
        )
        stream_types = ",".join(line.strip() for line in result.stdout.splitlines() if line.strip())
        status = "OK" if result.returncode == 0 else f"FAIL returncode={result.returncode}"
        print(f"{label}: {status} streams={stream_types or '-'}")


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_cameras(path: Path) -> list[dict]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cameras: list[dict] = []
    cameras.extend(payload.get("tplink", {}).get("cameras", []))
    cameras.extend(payload.get("cameras", []))
    return cameras


def _rtsp_url_from_config(camera: dict) -> str | None:
    username = _secret_from_config(camera, "username")
    password = _secret_from_config(camera, "password")
    if not username or not password:
        return None

    scheme = str(camera.get("rtsp_scheme", "rtsp")).rstrip(":/").lower()
    if scheme not in {"rtsp", "rtsps"}:
        scheme = "rtsp"
    default_port = 322 if scheme == "rtsps" else 554
    port = int(camera.get("rtsp_port", default_port))
    stream_path = str(camera.get("stream_path", "/stream1"))
    if not stream_path.startswith("/"):
        stream_path = f"/{stream_path}"

    return (
        f"{scheme}://{quote(username, safe='')}:{quote(password, safe='')}"
        f"@{camera['host']}:{port}{stream_path}"
    )


def _secret_from_config(camera: dict, key: str) -> str | None:
    direct_value = camera.get(key)
    if direct_value:
        return _valid_secret(str(direct_value))

    env_name = camera.get(f"{key}_env")
    if env_name:
        return _valid_secret(os.getenv(str(env_name), ""))

    return None


def _valid_secret(value: str) -> str | None:
    stripped = value.strip()
    if not stripped or stripped == "replace_me":
        return None
    return stripped


if __name__ == "__main__":
    main()
