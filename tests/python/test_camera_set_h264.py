"""Getting a camera off HEVC, over ONVIF.

WebRTC cannot carry HEVC, so a camera that insists on it costs a permanent
go2rtc transcode - ~19% of a board core on the garage camera. Asking the camera
for H.264 instead costs nothing, and these are the parts of that request that
are wrong silently rather than loudly:

  * the WS-Security digest. Get it wrong and the camera answers with a SOAP
    fault that reads like a permissions problem rather than a maths problem;
  * the echoed configuration. Only the encoding may change - a Set that drops or
    mangles a field is how a camera quietly ends up at 5fps or 256kbps, and
    nobody notices until they look at a recording.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
from pathlib import Path
from xml.etree import ElementTree

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "camera-set-h264.py"

# Hyphenated filename, so it cannot be imported by name.
_spec = importlib.util.spec_from_file_location("camera_set_h264", SCRIPT)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)

password_digest = _module.password_digest
security_header = _module.security_header
set_body = _module.set_body
describe = _module.describe
envelope = _module.envelope
NS = _module.NS


def sent(config) -> ElementTree.Element:
    """The request as it actually goes on the wire.

    set_body() returns a fragment whose tt:/trt: prefixes are declared by the
    envelope around it, so parsing it alone is not a thing the camera ever does
    and fails on an unbound prefix. Wrap it the way call() does.
    """
    return ElementTree.fromstring(envelope(set_body(config), "", ""))

# What the garage camera actually returned, trimmed to the fields that matter.
CONFIG_XML = """
<Configurations xmlns="http://www.onvif.org/ver10/media/wsdl"
                xmlns:tt="http://www.onvif.org/ver10/schema" token="VideoStream1Token">
  <tt:Name>VideoStream1</tt:Name>
  <tt:UseCount>1</tt:UseCount>
  <tt:Encoding>H264</tt:Encoding>
  <tt:Resolution><tt:Width>640</tt:Width><tt:Height>352</tt:Height></tt:Resolution>
  <tt:Quality>6.000000</tt:Quality>
  <tt:RateControl ConstantBitRate="false">
    <tt:FrameRateLimit>20</tt:FrameRateLimit>
    <tt:EncodingInterval>80</tt:EncodingInterval>
    <tt:BitrateLimit>400</tt:BitrateLimit>
  </tt:RateControl>
  <tt:H264><tt:GovLength>50</tt:GovLength><tt:H264Profile>Main</tt:H264Profile></tt:H264>
  <tt:SessionTimeout>PT60S</tt:SessionTimeout>
</Configurations>
"""


@pytest.fixture
def config() -> ElementTree.Element:
    return ElementTree.fromstring(CONFIG_XML)


# ── The digest ───────────────────────────────────────────────────────────────

def test_the_digest_is_sha1_of_nonce_created_and_password() -> None:
    """Straight from the ONVIF spec. Any other order authenticates against
    nothing, and the camera's refusal looks like a wrong password."""
    nonce, created, password = b"0123456789abcdef", "2026-09-12T07:30:00Z", "secret"
    expected = base64.b64encode(
        hashlib.sha1(nonce + created.encode() + password.encode()).digest()
    ).decode()
    assert password_digest(nonce, created, password) == expected


def test_the_header_carries_the_nonce_it_hashed() -> None:
    """The camera repeats the hash with the nonce we send it, so sending a
    different one than we hashed fails in a way that looks like bad credentials."""
    nonce, created = b"sixteen bytes!!!", "2026-09-12T07:30:00Z"
    header = security_header("H1250", "secret", nonce=nonce, created=created)
    assert base64.b64encode(nonce).decode() in header
    assert password_digest(nonce, created, "secret") in header
    assert created in header
    assert "<Username>H1250</Username>" in header


def test_no_credentials_means_no_security_header() -> None:
    """Some cameras answer Get* unauthenticated; an empty token is worse than
    none, because it is an authentication attempt that cannot succeed."""
    assert security_header("", "") == ""


# ── The write must change the encoding and nothing else ──────────────────────

def test_the_write_asks_for_h264(config) -> None:
    body = sent(config)
    assert body.find(".//tt:Encoding", NS).text == "H264"


def test_every_other_setting_is_echoed_back_untouched(config) -> None:
    """This is the one that matters. A Set that loses a field is how a camera
    silently ends up at a different resolution or bitrate."""
    body = sent(config)
    assert body.find(".//tt:Resolution/tt:Width", NS).text == "640"
    assert body.find(".//tt:Resolution/tt:Height", NS).text == "352"
    assert body.find(".//tt:RateControl/tt:FrameRateLimit", NS).text == "20"
    assert body.find(".//tt:RateControl/tt:BitrateLimit", NS).text == "400"
    assert body.find(".//tt:RateControl/tt:EncodingInterval", NS).text == "80"
    assert body.find(".//tt:Quality", NS).text == "6.000000"
    assert body.find(".//tt:H264/tt:GovLength", NS).text == "50"
    assert body.find(".//tt:H264/tt:H264Profile", NS).text == "Main"
    assert body.find(".//tt:SessionTimeout", NS).text == "PT60S"


def test_the_configuration_token_is_preserved(config) -> None:
    """Addressed to the wrong config, the write lands on the other stream."""
    body = sent(config)
    assert body.find(".//trt:Configuration", NS).get("token") == "VideoStream1Token"


def test_the_change_is_asked_to_persist(config) -> None:
    """Without ForcePersistence the camera forgets at the next power cut, and
    the transcode quietly comes back."""
    body = sent(config)
    assert body.find(".//trt:ForcePersistence", NS).text == "true"


def test_a_sparse_configuration_still_produces_valid_xml() -> None:
    """Cameras omit fields. Missing ones must fall back, not emit empty tags
    that the camera then reads as zero."""
    sparse = ElementTree.fromstring(
        '<Configurations xmlns="http://www.onvif.org/ver10/media/wsdl"'
        ' xmlns:tt="http://www.onvif.org/ver10/schema" token="T">'
        "<tt:Encoding>H265</tt:Encoding></Configurations>"
    )
    body = sent(sparse)
    assert body.find(".//tt:Quality", NS).text == "4"
    assert body.find(".//tt:H264/tt:H264Profile", NS).text == "Main"
    assert body.find(".//tt:SessionTimeout", NS).text == "PT60S"


def test_describe_reports_what_the_camera_claims(config) -> None:
    """Used to print the state - and labelled a claim, because on this camera
    the reported encoding was H264 while the wire carried HEVC."""
    assert describe(config) == "VideoStream1Token: H264 640x352 20fps 400kbps"
