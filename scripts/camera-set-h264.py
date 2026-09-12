#!/usr/bin/env python3
"""Tell a camera to encode H.264 instead of HEVC, over ONVIF.

WebRTC cannot carry HEVC, so a camera that insists on it has to be transcoded by
go2rtc for the dashboard to show it at all - a permanent ffmpeg process and, on
this house's garage camera, about 19% of a board core, for ever. Asking the
camera to produce H.264 in the first place costs nothing and is always better.

The trap this script exists to get past: **do not believe what ONVIF reports.**
The Hipcam/Chortau camera here answers `GetVideoEncoderConfigurations` with
`<Encoding>H264</Encoding>` and offers H264 as the only option, while the RTSP
stream is plainly HEVC. Its reads are fiction. Its writes work. So `--show` may
tell you there is nothing to fix when there is; check the wire instead:

    ffprobe rtsp://user:pass@camera:554/12        # or scripts/npu-model tooling

Everything except the encoding is echoed back exactly as the camera reported it,
so a write cannot quietly change resolution, bitrate or frame rate.

Usage:
    scripts/camera-set-h264.py --host 192.168.0.191 --show
    scripts/camera-set-h264.py --host 192.168.0.191 --apply

Credentials come from --user/--password, or CAM_USER/CAM_PASS in the
environment. They are the camera's ONVIF account, which on these cameras is the
same as the RTSP one and is *not* the web UI login.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import secrets
import sys
import urllib.request
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree

NS = {
    "s": "http://www.w3.org/2003/05/soap-envelope",
    "tds": "http://www.onvif.org/ver10/device/wsdl",
    "trt": "http://www.onvif.org/ver10/media/wsdl",
    "tt": "http://www.onvif.org/ver10/schema",
}
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
DIGEST = ("http://docs.oasis-open.org/wss/2004/01/"
          "oasis-200401-wss-username-token-profile-1.0#PasswordDigest")
B64 = ("http://docs.oasis-open.org/wss/2004/01/"
       "oasis-200401-wss-soap-message-security-1.0#Base64Binary")


def password_digest(nonce: bytes, created: str, password: str) -> str:
    """ONVIF's UsernameToken digest: base64(sha1(nonce + created + password))."""
    return base64.b64encode(
        hashlib.sha1(nonce + created.encode() + password.encode()).digest()
    ).decode()


def security_header(user: str, password: str, nonce: bytes | None = None,
                    created: str | None = None) -> str:
    if not user:
        return ""
    nonce = secrets.token_bytes(16) if nonce is None else nonce
    created = created or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f'<s:Header><Security s:mustUnderstand="1" xmlns="{WSSE}"><UsernameToken>'
        f"<Username>{user}</Username>"
        f'<Password Type="{DIGEST}">{password_digest(nonce, created, password)}</Password>'
        f'<Nonce EncodingType="{B64}">{base64.b64encode(nonce).decode()}</Nonce>'
        f'<Created xmlns="{WSU}">{created}</Created>'
        f"</UsernameToken></Security></s:Header>"
    )


def envelope(body: str, user: str, password: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
        ' xmlns:tds="http://www.onvif.org/ver10/device/wsdl"'
        ' xmlns:trt="http://www.onvif.org/ver10/media/wsdl"'
        ' xmlns:tt="http://www.onvif.org/ver10/schema">'
        f"{security_header(user, password)}<s:Body>{body}</s:Body></s:Envelope>"
    )


class OnvifError(RuntimeError):
    pass


def call(url: str, body: str, user: str, password: str) -> ElementTree.Element:
    request = urllib.request.Request(
        url, data=envelope(body, user, password).encode(),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"},
    )
    try:
        raw = urllib.request.urlopen(request, timeout=15).read()
    except HTTPError as exc:
        raw = exc.read()          # SOAP faults arrive as 400/500 with a body
    except (URLError, OSError) as exc:
        raise OnvifError(f"cannot reach {url}: {exc}") from exc
    root = ElementTree.fromstring(raw)
    reason = root.find(".//{http://www.w3.org/2003/05/soap-envelope}Reason")
    if reason is not None:
        raise OnvifError(" ".join("".join(reason.itertext()).split()))
    return root


def media_url(host: str, port: int, user: str, password: str) -> str:
    try:
        root = call(f"http://{host}:{port}/onvif/device_service",
                    "<tds:GetCapabilities><tds:Category>Media</tds:Category>"
                    "</tds:GetCapabilities>", user, password)
    except OnvifError:
        return f"http://{host}:{port}/onvif/media_service"
    for node in root.iter():
        if node.tag.endswith("}XAddr") and "media" in (node.text or "").lower():
            # Cameras advertise whatever address they think they have - this one
            # says 192.168.1.88 - so keep the one we actually reached it on.
            return re.sub(r"//[^/]+", f"//{host}:{port}", node.text.strip())
    return f"http://{host}:{port}/onvif/media_service"


def _text(node: ElementTree.Element, path: str, default: str = "") -> str:
    found = node.find(path, NS)
    return found.text if found is not None and found.text else default


def set_body(config: ElementTree.Element) -> str:
    """A SetVideoEncoderConfiguration that changes the encoding and nothing else."""
    token = config.get("token")
    return f"""<trt:SetVideoEncoderConfiguration>
      <trt:Configuration token="{token}">
        <tt:Name>{_text(config, 'tt:Name', token or 'video')}</tt:Name>
        <tt:UseCount>{_text(config, 'tt:UseCount', '1')}</tt:UseCount>
        <tt:Encoding>H264</tt:Encoding>
        <tt:Resolution>
          <tt:Width>{_text(config, 'tt:Resolution/tt:Width')}</tt:Width>
          <tt:Height>{_text(config, 'tt:Resolution/tt:Height')}</tt:Height>
        </tt:Resolution>
        <tt:Quality>{_text(config, 'tt:Quality', '4')}</tt:Quality>
        <tt:RateControl>
          <tt:FrameRateLimit>{_text(config, 'tt:RateControl/tt:FrameRateLimit')}</tt:FrameRateLimit>
          <tt:EncodingInterval>{_text(config, 'tt:RateControl/tt:EncodingInterval', '1')}</tt:EncodingInterval>
          <tt:BitrateLimit>{_text(config, 'tt:RateControl/tt:BitrateLimit')}</tt:BitrateLimit>
        </tt:RateControl>
        <tt:H264>
          <tt:GovLength>{_text(config, 'tt:H264/tt:GovLength', '50')}</tt:GovLength>
          <tt:H264Profile>{_text(config, 'tt:H264/tt:H264Profile', 'Main')}</tt:H264Profile>
        </tt:H264>
        <tt:SessionTimeout>{_text(config, 'tt:SessionTimeout', 'PT60S')}</tt:SessionTimeout>
      </trt:Configuration>
      <trt:ForcePersistence>true</trt:ForcePersistence>
    </trt:SetVideoEncoderConfiguration>"""


def describe(config: ElementTree.Element) -> str:
    return (f"{config.get('token')}: {_text(config, 'tt:Encoding')} "
            f"{_text(config, 'tt:Resolution/tt:Width')}x{_text(config, 'tt:Resolution/tt:Height')} "
            f"{_text(config, 'tt:RateControl/tt:FrameRateLimit')}fps "
            f"{_text(config, 'tt:RateControl/tt:BitrateLimit')}kbps")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8080, help="ONVIF port (default 8080)")
    parser.add_argument("--user", default=os.environ.get("CAM_USER", ""))
    parser.add_argument("--password", default=os.environ.get("CAM_PASS", ""))
    parser.add_argument("--show", action="store_true", help="print configs, change nothing")
    parser.add_argument("--apply", action="store_true", help="write H264 to every config")
    args = parser.parse_args()

    if not (args.show or args.apply):
        parser.error("pass --show or --apply")

    url = media_url(args.host, args.port, args.user, args.password)
    print(f"media service: {url}")
    try:
        root = call(url, "<trt:GetVideoEncoderConfigurations/>", args.user, args.password)
    except OnvifError as exc:
        print(f"failed: {exc}")
        return 1

    configs = [n for n in root.iter() if n.tag.endswith("}Configurations")]
    if not configs:
        print("no video encoder configurations returned")
        return 1

    for config in configs:
        print(f"  reported {describe(config)}")
    print("  (reported encoding is not evidence - check the RTSP stream itself)")

    if not args.apply:
        return 0

    failures = 0
    for config in configs:
        try:
            call(url, set_body(config), args.user, args.password)
            print(f"  wrote H264 to {config.get('token')}")
        except OnvifError as exc:
            print(f"  {config.get('token')} refused: {exc}")
            failures += 1
    print("\nRe-check the stream's real codec before trusting this worked.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
