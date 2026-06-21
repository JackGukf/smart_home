from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEVICE_CONFIG = PROJECT_ROOT / "configs" / "devices.local.yaml"
OUTPUT_CONFIG = PROJECT_ROOT / "go2rtc" / "go2rtc.yaml"


def main() -> None:
    _load_env(PROJECT_ROOT / ".env")
    payload = yaml.safe_load(DEVICE_CONFIG.read_text(encoding="utf-8")) or {}
    streams: dict[str, str] = {}

    cameras = []
    cameras.extend(payload.get("tplink", {}).get("cameras", []))
    cameras.extend(payload.get("cameras", []))
    for camera in cameras:
        if camera.get("go2rtc_enabled") is False:
            continue
        stream_name = camera.get("stream_name") or _stream_name(camera["name"])
        stream_url = camera.get("stream_url") or _rtsp_url_from_config(camera)
        if not stream_url:
            continue
        streams[str(stream_name)] = _go2rtc_stream_source(camera, str(stream_url))

    if not streams:
        raise SystemExit("No camera streams found. Check configs/devices.local.yaml and .env.")

    OUTPUT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_CONFIG.write_text(
        yaml.safe_dump(
            {
                "api": {
                    "listen": ":1984",
                    "allow_paths": [
                        "/",
                        "/api/webrtc",
                        "/api/ws",
                        "/api/frame.jpeg",
                        "/api/stream.m3u8",
                        "/api/hls",
                    ],
                },
                "webrtc": {"listen": ":8555"},
                "streams": streams,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_CONFIG} with {len(streams)} stream(s).")


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _rtsp_url_from_config(camera: dict) -> str | None:
    username = _secret_from_config(camera, "username")
    password = _secret_from_config(camera, "password")
    if not username or not password:
        return None

    host = str(camera["host"])
    scheme = str(camera.get("rtsp_scheme", "rtsp")).rstrip(":/").lower()
    if scheme not in {"rtsp", "rtsps"}:
        scheme = "rtsp"
    default_port = 322 if scheme == "rtsps" else 554
    port = int(camera.get("rtsp_port", default_port))
    stream_path = str(camera.get("stream_path", "/stream2"))
    if not stream_path.startswith("/"):
        stream_path = f"/{stream_path}"

    return f"{scheme}://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}{stream_path}"


def _go2rtc_stream_source(camera: dict, stream_url: str) -> str:
    source = str(camera.get("go2rtc_source", "")).lower()
    if source == "ffmpeg" or stream_url.startswith("rtsps://"):
        video = str(camera.get("go2rtc_video", "copy"))
        audio = str(camera.get("go2rtc_audio", "copy")).lower()
        ffmpeg_source = f"ffmpeg:{stream_url}#video={video}"
        if audio not in {"", "none", "off", "false", "0"}:
            ffmpeg_source = f"{ffmpeg_source}#audio={audio}"
        return ffmpeg_source
    return stream_url


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


def _stream_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in str(value)).strip("_")


if __name__ == "__main__":
    main()
