#!/usr/bin/env python3
"""
Let the wall panel past both login screens, by address.

Run this from the workstation after scripts/setup-kiosk-display.sh. It pipes
scripts/kiosk/configure-autologin.py to the Orange Pi and runs it there with the
dashboard's virtualenv - nothing is left behind on the board, so the repo copy
is always the one that ran.

    scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176
    scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176 --dry-run

The panel's IP address becomes a credential for both the dashboard and Home
Assistant. Give it a static DHCP lease before you rely on this.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_HOST = "192.168.0.234"
DEFAULT_USER = "orangepi"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kiosk-ip", required=True, help="the wall panel's IP address")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"board (default {DEFAULT_HOST})")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"board user (default {DEFAULT_USER})")
    parser.add_argument("--remote-path", default=None, help="project path on the board")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    parser.add_argument("--no-restart", action="store_true", help="edit the files, restart nothing")
    args = parser.parse_args()

    remote_path = args.remote_path or f"/home/{args.user}/smart_home_AI"
    target = f"{args.user}@{args.host}"
    payload = Path(__file__).resolve().parent / "kiosk" / "configure-autologin.py"

    remote_args = ["--kiosk-ip", args.kiosk_ip, "--project-root", remote_path]
    if args.dry_run:
        remote_args.append("--dry-run")
    if args.no_restart:
        remote_args.append("--no-restart")

    # `python -` reads the program from stdin; argv after it is passed through.
    # The board's system python has no aiohttp - the dashboard's venv does.
    remote_cmd = (
        f"cd {remote_path} && "
        f"{{ [ -x .venv/bin/python ] && PY=.venv/bin/python || PY=python3; }} && "
        f"$PY - {' '.join(remote_args)}"
    )

    print(f"==> Board: {target}:{remote_path}")
    result = subprocess.run(
        ["ssh", target, remote_cmd],
        stdin=payload.open("rb"),
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
