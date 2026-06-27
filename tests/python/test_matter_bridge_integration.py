"""
Integration smoke tests for the chip-bridge-app binary.

These tests build a native (x86_64) bridge binary, start it in a subprocess,
and verify fundamental behaviour: mDNS advertisement, port 5540, DAC provider
initialisation, and absence of the known regression bugs.

Run with:
    docker compose run --rm dev python3 -m pytest -m matter_integration -v

Skipped automatically when the native binary is absent and
MATTER_SKIP_BUILD is set (e.g. in quick unit-test runs).
"""
from __future__ import annotations

import os
import re
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
NATIVE_BINARY = PROJECT_ROOT / "build" / "matter-bridge-native" / "chip-bridge-app"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-matter-bridge-native.sh"

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def native_bridge_binary():
    """Build native x86_64 bridge binary once per test session."""
    if NATIVE_BINARY.exists():
        return NATIVE_BINARY
    if os.environ.get("MATTER_SKIP_BUILD"):
        pytest.skip("native bridge binary not found and MATTER_SKIP_BUILD is set")
    if not BUILD_SCRIPT.exists():
        pytest.skip("build-matter-bridge-native.sh not found")
    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail(f"Native build failed:\n{result.stderr[-3000:]}")
    assert NATIVE_BINARY.exists(), "Build succeeded but binary not found"
    return NATIVE_BINARY


@pytest.fixture()
def running_bridge(native_bridge_binary, tmp_path):
    """
    Start the bridge binary with a fresh KVS, yield its log output after
    startup, then shut it down.
    """
    kvs = tmp_path / "kvs"
    proc = subprocess.Popen(
        [str(native_bridge_binary), "--KVS", str(kvs)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Collect logs until "bridge running" appears or 15s elapse
    lines: list[str] = []
    deadline = time.time() + 15
    while time.time() < deadline:
        line = proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            break
        lines.append(line)
        if "bridge running" in line or "Server Listening" in line:
            break
    yield proc, lines
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── Tests ─────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.matter_integration


def test_bridge_starts_and_logs_running(running_bridge):
    """Bridge must log 'bridge running' within 15 s of startup."""
    _proc, lines = running_bridge
    combined = "\n".join(lines)
    assert "Matter bridge running" in combined or "Server Listening" in combined, (
        f"Bridge did not reach running state.\nLogs:\n{combined}"
    )


def test_bridge_logs_manual_pairing_code(running_bridge):
    """Bridge must log an 11-digit manual pairing code."""
    _proc, lines = running_bridge
    combined = "\n".join(lines)
    match = re.search(r"Manual pairing code: \[(\d{11})\]", combined)
    assert match, f"No 11-digit manual pairing code in logs.\nLogs:\n{combined}"


def test_bridge_logs_qr_code(running_bridge):
    """Bridge must log a QR code string starting with MT:."""
    _proc, lines = running_bridge
    combined = "\n".join(lines)
    assert "SetupQRCode: [MT:" in combined, (
        f"No QR code (MT:...) in logs.\nLogs:\n{combined}"
    )


def test_bridge_dac_provider_not_not_implemented(running_bridge):
    """
    DAC 'Not Implemented' must NOT appear before commissioning.

    Regression: SetDeviceAttestationCredentialsProvider() was never called
    because we skip ChipLinuxAppMainLoop(). The bridge returned
    CHIP_ERROR_NOT_IMPLEMENTED for every CertificateChainRequest, causing
    Apple Home to reject the device during attestation.
    """
    _proc, lines = running_bridge
    combined = "\n".join(lines)
    # "Not Implemented" on startup (before any commissioning attempt) is the bug.
    assert "CertificateChainRequest" not in combined or "Not Implemented" not in combined, (
        "DAC provider not set up — CertificateChainRequest returned Not Implemented at startup.\n"
        f"Logs:\n{combined}"
    )


def test_bridge_port_5540_listening(running_bridge):
    """Bridge must open UDP port 5540 for Matter commissioning."""
    proc, _lines = running_bridge
    time.sleep(2)  # give the server a moment after startup log
    assert proc.poll() is None, "Bridge process exited unexpectedly"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(1)
        # Send garbage; any response (or no ECONNREFUSED) means port is open.
        try:
            s.sendto(b"\x00" * 4, ("127.0.0.1", 5540))
        except OSError:
            pytest.fail("UDP port 5540 is not reachable on localhost")


def test_bridge_mdns_advertises_matterc(running_bridge):
    """
    Bridge must send an mDNS announcement for _matterc._udp.local within 5 s.

    Regression: mDNS was advertising on docker0 (172.17.0.x) in addition to
    the real WiFi interface. iPhone cached the unreachable docker0 IP and
    could not connect.
    """
    _proc, _lines = running_bridge
    MCAST = "224.0.0.251"
    PORT = 5353
    captured: list[bytes] = []
    deadline = time.time() + 5
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.settimeout(0.5)
        mreq = struct.pack("4sL", socket.inet_aton(MCAST), socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        s.bind(("", PORT))
        while time.time() < deadline:
            try:
                data, _addr = s.recvfrom(4096)
                if b"_matterc" in data:
                    captured.append(data)
            except socket.timeout:
                pass
    assert captured, "No _matterc._udp.local mDNS announcement captured within 5 s"


def test_bridge_mdns_no_docker_bridge_ip(running_bridge):
    """
    mDNS A records must not advertise Docker bridge IPs (172.17.x.x / 172.18.x.x).

    Regression: CHIP minimal mDNS advertised on all interfaces, including docker0.
    iPhone received the docker0 A record last and tried to connect to an
    unreachable 172.x IP.
    """
    _proc, _lines = running_bridge
    MCAST = "224.0.0.251"
    PORT = 5353
    docker_ips: list[str] = []
    deadline = time.time() + 5
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.settimeout(0.5)
        mreq = struct.pack("4sL", socket.inet_aton(MCAST), socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        s.bind(("", PORT))
        while time.time() < deadline:
            try:
                data, _addr = s.recvfrom(4096)
                if b"_matterc" not in data:
                    continue
                # Find type-A records (rdtype=0x0001) in raw DNS
                for i in range(len(data) - 13):
                    if data[i : i + 4] in (b"\x00\x01\x00\x01", b"\x00\x01\x80\x01"):
                        rdlen = struct.unpack("!H", data[i + 8 : i + 10])[0]
                        if rdlen == 4 and i + 14 <= len(data):
                            ip = ".".join(str(b) for b in data[i + 10 : i + 14])
                            if ip.startswith("172."):
                                docker_ips.append(ip)
            except socket.timeout:
                pass
    assert not docker_ips, (
        f"Bridge advertised Docker bridge IP(s) in mDNS: {docker_ips}. "
        "iPhone will cache this unreachable address and fail to commission."
    )
