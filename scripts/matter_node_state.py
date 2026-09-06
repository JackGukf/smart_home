#!/usr/bin/env python3
"""Read a commissioned Matter node's OnOff state straight from matter-server.

This is the independent check when verifying the bridge: the bridge's own
/bridge/state/all is written by our code, so reading it back after a command
mostly proves our code agrees with itself. matter-server holds the device's
real attribute, fed by its subscription, so this answers "did the light
actually change?" rather than "did we record that it changed?".

Speaks the WebSocket handshake and framing directly. matter-server needs no
auth, and doing it this way means the script has no dependency beyond the
standard library -- it runs from the workstation, a container, or the board.

Usage:
  matter_node_state.py <node-id> [--host HOST] [--port PORT]

Prints one line per matching OnOff attribute, and exits non-zero if the node
is not in the fabric.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import sys

# Matter attribute path: <endpoint>/<cluster>/<attribute>. Cluster 6 is OnOff
# and attribute 0 is its OnOff value, so any "<ep>/6/0" key is a switch state.
ONOFF_SUFFIX = "/6/0"


class WSClient:
    def __init__(self, host: str, port: int, path: str = "/ws", timeout: float = 20.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall(
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n".encode()
        )
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("server closed during handshake")
            buf += chunk
        status = buf.split(b"\r\n", 1)[0]
        if b"101" not in status:
            raise ConnectionError(f"handshake failed: {status!r}")
        self._rest = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, obj: dict) -> None:
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            header = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < 65536:
            header = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(header + mask + masked)

    def _need(self, count: int) -> None:
        while len(self._rest) < count:
            chunk = self._sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("server closed")
            self._rest += chunk

    def recv(self) -> dict:
        self._need(2)
        length = self._rest[1] & 0x7F
        offset = 2
        if length == 126:
            self._need(4)
            length = struct.unpack("!H", self._rest[2:4])[0]
            offset = 4
        elif length == 127:
            self._need(10)
            length = struct.unpack("!Q", self._rest[2:10])[0]
            offset = 10
        self._need(offset + length)
        payload = self._rest[offset:offset + length]
        self._rest = self._rest[offset + length:]
        return json.loads(payload)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("node_id", type=int)
    parser.add_argument("--host", default=os.environ.get("PI_HOST", "192.168.0.234"))
    parser.add_argument("--port", type=int, default=5580)
    args = parser.parse_args(argv[1:])

    client = WSClient(args.host, args.port)
    try:
        client.recv()  # server info banner
        client.send({"message_id": "1", "command": "get_nodes"})
        while True:
            message = client.recv()
            if message.get("message_id") == "1":
                break
    finally:
        client.close()

    for node in message.get("result", []):
        if node.get("node_id") != args.node_id:
            continue
        attributes = node.get("attributes") or {}
        states = {k: v for k, v in attributes.items() if k.endswith(ONOFF_SUFFIX)}
        if not states:
            print(f"node {args.node_id}: no OnOff attribute (not a switch?)")
            return 1
        for path, value in sorted(states.items()):
            print(f"node {args.node_id} {path} = {value}")
        return 0

    print(f"node {args.node_id} is not in this fabric", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
