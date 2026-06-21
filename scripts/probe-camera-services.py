from __future__ import annotations

import argparse
import http.client
import socket
from urllib.parse import urlsplit


PORTS = [80, 81, 88, 443, 554, 8554, 8080, 8000, 8899, 5000, 5001, 8999]
RTSP_PATHS = [
    "/",
    "/live",
    "/live0",
    "/stream0",
    "/stream1",
    "/11",
    "/12",
    "/user=admin_password=_channel=1_stream=0.sdp",
    "/h264Preview_01_main",
    "/h264Preview_01_sub",
    "/cam/realmonitor?channel=1&subtype=0",
]
HTTP_PATHS = ["/", "/onvif/device_service", "/web/cgi-bin/hi3510/param.cgi?cmd=getserverinfo"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe camera ports, RTSP OPTIONS, and HTTP headers.")
    parser.add_argument("hosts", nargs="+")
    args = parser.parse_args()

    for host in args.hosts:
        print(f"HOST {host}")
        _probe_ports(host)
        _probe_http(host)
        _probe_rtsp(host)


def _probe_ports(host: str) -> None:
    open_ports = []
    for port in PORTS:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                open_ports.append(port)
        except OSError:
            pass
    print(f"ports open={','.join(str(port) for port in open_ports) or '-'}")


def _probe_http(host: str) -> None:
    for port in (80, 8080):
        for path in HTTP_PATHS:
            try:
                conn = http.client.HTTPConnection(host, port, timeout=2)
                conn.request("HEAD", path)
                response = conn.getresponse()
                server = response.getheader("Server") or "-"
                auth = response.getheader("WWW-Authenticate") or "-"
                print(f"http {port}{path} {response.status} server={server} auth={auth}")
                conn.close()
            except OSError as exc:
                print(f"http {port}{path} error={type(exc).__name__}")


def _probe_rtsp(host: str) -> None:
    for path in RTSP_PATHS:
        target = f"rtsp://{host}:554{path}"
        request = f"OPTIONS {target} RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode()
        try:
            with socket.create_connection((host, 554), timeout=2) as sock:
                sock.settimeout(2)
                sock.sendall(request)
                data = sock.recv(512).decode(errors="replace").replace("\r", "")
        except OSError as exc:
            print(f"rtsp {path} error={type(exc).__name__}")
            continue
        first_line = data.splitlines()[0] if data.splitlines() else "-"
        server = next((line for line in data.splitlines() if line.lower().startswith("server:")), "Server: -")
        print(f"rtsp {path} {first_line} {server}")


if __name__ == "__main__":
    main()
