#!/usr/bin/env python3
"""Name zap's CIPD packages explicitly, so the CHIP SDK bootstrap can run.

pigweed's `pw_env_setup/cipd_setup/update.py:check_auth()` probes every CIPD
package for access before installing it, but strips any "${...}" segment first::

    parts = entry['path'].split('/')
    while '${' in parts[-1]:
        parts.pop(-1)

The CHIP SDK's `scripts/setup/zap.json` asks for
``fuchsia/third_party/zap/${platform}``, so the probe ends up asking about
``fuchsia/third_party/zap`` -- a *prefix*, not a package. ``cipd ls`` on it
returns "No matching packages", because anonymous users cannot list that
prefix, and ``cipd instances`` errors, because a prefix is not a package. From
those two answers pigweed concludes there is no anonymous access, tries an
interactive login, and the bootstrap dies with "CIPD login failed" on any
machine without a TTY -- CI, a container, an ssh session.

The packages are anonymously readable; only the prefix is not::

    $ cipd resolve fuchsia/third_party/zap/linux-amd64 -version latest
    Packages:
      fuchsia/third_party/zap/linux-amd64:ob3YnV-Qj99dKOcB2mI9YbbmVONxQR1Ts3I8UPw3YZIC

So this rewrites the one placeholder entry into one concrete entry per platform.
CIPD installs exactly the same package for each platform as before; there is
simply no placeholder left for check_auth to mangle into a prefix.

Idempotent: running it on an already-explicit file changes nothing.

Usage: fix_zap_cipd_paths.py <path to zap.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PLACEHOLDER = "${platform}"

# The SDK's own file maps mac-arm64 to the amd64 build, with the comment
# "Always get the amd64 version on mac until usable arm64 zap build is
# available". Rewriting the entries must not quietly drop that.
MAC_FALLBACK = ("mac-amd64", "mac-arm64")


def expand(packages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for pkg in packages:
        path = pkg.get("path", "")
        if PLACEHOLDER not in path:
            out.append(pkg)
            continue
        for platform in pkg.get("platforms", []):
            out.append(
                {
                    "path": path.replace(PLACEHOLDER, platform),
                    "platforms": [platform],
                    "tags": pkg["tags"],
                }
            )

    # Fold the SDK's separate mac-arm64 entry into the mac-amd64 one rather than
    # leaving two entries naming the same package.
    amd, arm = MAC_FALLBACK
    mac = [p for p in out if p["path"].endswith(amd)]
    if mac:
        platforms = set()
        for pkg in mac:
            platforms.update(pkg["platforms"])
        if any(arm in p["platforms"] for p in out):
            platforms.add(arm)
        merged = dict(mac[0])
        merged["platforms"] = sorted(platforms)
        out = [p for p in out if not p["path"].endswith(amd)]
        out.append(merged)

    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2

    path = Path(argv[1])
    doc = json.loads(path.read_text(encoding="utf-8"))
    packages = doc.get("packages", [])

    if not any(PLACEHOLDER in p.get("path", "") for p in packages):
        print("    already explicit; nothing to do")
        return 0

    doc["packages"] = expand(packages)
    path.write_text(json.dumps(doc, indent=4) + "\n", encoding="utf-8")
    print(f"    {len(doc['packages'])} explicit package entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
