#!/usr/bin/env bash
# Re-apply the Tuya "cdsxj" camera patch to the Home Assistant container.
#
# Tuya moved some cameras (here: the Living Room Camera) to an undocumented
# device category "cdsxj". Home Assistant's Tuya integration maps only "sp" and
# "dghsxj" to the camera platform, so the device produces zero entities and is
# labelled "(unsupported)". Upstream: home-assistant/core#177197.
#
# The patch adds "cdsxj" to that map. It lives in the container's writable
# layer, so it survives restarts and reboots but is LOST whenever the container
# is recreated or the image is updated -- re-run this script after either.
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.234}"
PI_USER="${PI_USER:-orangepi}"
CONTAINER="${HA_CONTAINER:-homeassistant}"
RESTART=1

usage() {
    cat <<'USAGE'
Usage:
  scripts/patch-ha-tuya-cdsxj-camera.sh [--host HOST] [--user USER]
                                        [--container NAME] [--no-restart]
                                        [--revert] [--local]

Options:
  --host HOST       Board IP/hostname. Default: 192.168.0.234
  --user USER       SSH username. Default: orangepi
  --container NAME  Home Assistant container name. Default: homeassistant
  --no-restart      Apply the patch without restarting Home Assistant
  --revert          Restore the unpatched camera.py from /config/tuya-camera.py.orig
  --local           Run against the local Docker daemon (i.e. on the board)

Verify afterwards (needs HOME_ASSISTANT_TOKEN):
  curl -s -o /tmp/lrc.jpg -w '%{http_code} %{content_type} %{size_download}\n' \
    -H "Authorization: Bearer $HOME_ASSISTANT_TOKEN" \
    http://localhost:8123/api/camera_proxy/camera.living_room_camera
USAGE
}

MODE=patch
LOCAL=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host) PI_HOST="$2"; shift 2 ;;
        --user) PI_USER="$2"; shift 2 ;;
        --container) CONTAINER="$2"; shift 2 ;;
        --no-restart) RESTART=0; shift ;;
        --revert) MODE=revert; shift ;;
        --local) LOCAL=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

PY_PATCH=$(cat <<'PYEOF'
import pathlib
import shutil
import sys

target = pathlib.Path("/usr/src/homeassistant/homeassistant/components/tuya/camera.py")
backup = pathlib.Path("/config/tuya-camera.py.orig")
mode = sys.argv[1]

if mode == "revert":
    if not backup.exists():
        sys.exit("no backup at /config/tuya-camera.py.orig - nothing to revert")
    shutil.copy2(backup, target)
    print("reverted")
    sys.exit(0)

if not backup.exists():
    shutil.copy2(target, backup)

src = target.read_text()
anchor = '    DeviceCategory.DGHSXJ: CameraEntityDescription(key=""),\n'
patch = (
    '    # Local patch: Tuya moved some cameras to the undocumented "cdsxj"\n'
    "    # category; upstream home-assistant/core#177197. Remove once fixed.\n"
    '    "cdsxj": CameraEntityDescription(key=""),  # type: ignore[dict-item]\n'
)

if "cdsxj" in src:
    print("already patched")
elif anchor not in src:
    sys.exit(
        "anchor not found in camera.py - the Tuya integration changed shape; "
        "patch by hand and update this script"
    )
else:
    target.write_text(src.replace(anchor, anchor + patch, 1))
    print("patched")
PYEOF
)

run() {
    if [[ "$LOCAL" -eq 1 ]]; then
        bash -c "$1"
    else
        ssh "${PI_USER}@${PI_HOST}" "$1"
    fi
}

printf 'Applying "%s" to container %s\n' "$MODE" "$CONTAINER"
run "docker exec -i ${CONTAINER} python3 - ${MODE}" <<<"$PY_PATCH"

if [[ "$RESTART" -eq 1 ]]; then
    echo "Restarting ${CONTAINER}..."
    run "docker restart ${CONTAINER}" >/dev/null
    echo "Restarted. camera.living_room_camera should return within a minute."
else
    echo "Skipped restart; Home Assistant must restart for this to take effect."
fi
