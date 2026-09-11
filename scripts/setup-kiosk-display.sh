#!/usr/bin/env bash
# Turn the Raspberry Pi 4 into a wall panel showing the dashboard full screen,
# by itself, from cold boot.
#
# This half only touches the panel: Chromium, the autostart entry, and screen
# blanking. The panel logging *itself in* - to the dashboard and to the Home
# Assistant frame inside it - is the other half, and lives on the Orange Pi:
#
#     scripts/enable-kiosk-autologin.py --kiosk-ip <this panel's IP>
#
# Usage: scripts/setup-kiosk-display.sh [--host HOST] [--user USER]
#                                       [--dashboard-url URL] [--reboot]
set -euo pipefail

PI_HOST="${KIOSK_HOST:-192.168.0.176}"
PI_USER="${KIOSK_USER:-smarthome}"
DASHBOARD_URL="${DASHBOARD_URL:-http://192.168.0.234:8000/}"
DO_REBOOT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host) PI_HOST="$2"; shift 2 ;;
        --user) PI_USER="$2"; shift 2 ;;
        --dashboard-url) DASHBOARD_URL="$2"; shift 2 ;;
        --reboot) DO_REBOOT=1; shift ;;
        -h|--help)
            sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

TARGET="${PI_USER}@${PI_HOST}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHER_SRC="${PROJECT_ROOT}/scripts/kiosk/kiosk-launch.sh"

echo "==> Panel:     ${TARGET}"
echo "==> Dashboard: ${DASHBOARD_URL}"
echo

# ── Check the panel before changing anything on it ───────────────────────────
echo "==> Checking the panel..."
ssh -o ConnectTimeout=10 "${TARGET}" 'bash -s' <<'REMOTE_CHECK'
set -u
fail=0
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
    echo "    MISSING: chromium (sudo apt install chromium)"; fail=1
else
    echo "    chromium:  $(command -v chromium || command -v chromium-browser)"
fi
if ! command -v curl >/dev/null 2>&1; then
    echo "    MISSING: curl (sudo apt install curl)"; fail=1
fi
autologin_user="$(grep -E '^\s*autologin-user=' /etc/lightdm/lightdm.conf 2>/dev/null | tail -1 | cut -d= -f2)"
autologin_session="$(grep -E '^\s*autologin-session=' /etc/lightdm/lightdm.conf 2>/dev/null | tail -1 | cut -d= -f2)"
if [[ -n "${autologin_user}" ]]; then
    echo "    autologin: ${autologin_user} (${autologin_session:-default session})"
else
    echo "    WARNING: desktop autologin is not configured."
    echo "             Run: sudo raspi-config -> System -> Boot -> Desktop Autologin"
    echo "             Without it the panel stops at the login screen after a power cut."
fi
connected=0
for s in /sys/class/drm/card*-*/status; do
    [[ "$(cat "$s" 2>/dev/null)" == "connected" ]] && { echo "    display:   ${s%/status} connected"; connected=1; }
done
(( connected == 0 )) && echo "    WARNING: no connected display detected"
exit "${fail}"
REMOTE_CHECK
echo

# ── Install ──────────────────────────────────────────────────────────────────
echo "==> Installing the launcher..."
ssh "${TARGET}" 'mkdir -p ~/.local/bin ~/.config/autostart ~/.local/state'
scp -q "${LAUNCHER_SRC}" "${TARGET}:.local/bin/smart-home-kiosk"
ssh "${TARGET}" 'chmod +x ~/.local/bin/smart-home-kiosk'

echo "==> Writing ~/.config/smart-home-kiosk.env..."
ssh "${TARGET}" "cat > ~/.config/smart-home-kiosk.env" <<ENVFILE
# Written by scripts/setup-kiosk-display.sh - re-run it to change these.
DASHBOARD_URL="${DASHBOARD_URL}"
WAIT_SECONDS=120
ENVFILE

echo "==> Writing the autostart entry..."
# The Pi's labwc session runs lxsession-xdg-autostart, which is what picks this
# up. A systemd --user unit would not: it starts outside the Wayland session and
# has no WAYLAND_DISPLAY to draw on.
ssh "${TARGET}" "cat > ~/.config/autostart/smart-home-kiosk.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Smart Home Kiosk
Comment=Full-screen dashboard on the wall panel
Exec=sh -c 'exec "$HOME/.local/bin/smart-home-kiosk"'
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

echo "==> Disabling screen blanking..."
# raspi-config's do_blanking is only two edits, and on labwc the one that
# matters is in the user's own autostart - a swayidle line that blanks the
# panel after 10 minutes. Doing it directly avoids needing a sudo password.
ssh "${TARGET}" 'bash -s' <<'REMOTE_BLANKING'
set -u
changed=0
labwc_autostart="${HOME}/.config/labwc/autostart"
if [[ -f "${labwc_autostart}" ]] && grep -q swayidle "${labwc_autostart}"; then
    sed -i '/swayidle/d' "${labwc_autostart}"
    echo "    removed the swayidle blanking timer from ~/.config/labwc/autostart"
    changed=1
fi
wayfire_ini="${HOME}/.config/wayfire.ini"
if [[ -f "${wayfire_ini}" ]] && grep -q dpms_timeout "${wayfire_ini}"; then
    sed -i 's/dpms_timeout.*/dpms_timeout=-1/' "${wayfire_ini}"
    echo "    set dpms_timeout=-1 in ~/.config/wayfire.ini"
    changed=1
fi
(( changed == 0 )) && echo "    already off (nothing blanking this session)"
# The lightdm greeter has its own copy and needs root, but autologin means the
# greeter is on screen for a second or two - not long enough to blank.
exit 0
REMOTE_BLANKING

# ── What the other half needs ────────────────────────────────────────────────
KIOSK_IP="$(ssh "${TARGET}" "hostname -I" | tr ' ' '\n' | grep -E '^192\.168\.|^10\.|^172\.(1[6-9]|2[0-9]|3[01])\.' | head -1)"

echo
echo "==> Panel is set up. It will open the dashboard on its own after a reboot."
echo
echo "    Next, so it does not stop at two login screens, run:"
echo
echo "        scripts/enable-kiosk-autologin.py --kiosk-ip ${KIOSK_IP}"
echo
echo "    And give ${KIOSK_IP} a static DHCP lease in your router. That address"
echo "    is what both logins trust - if DHCP moves it, the panel is locked out."
echo

if (( DO_REBOOT )); then
    echo "==> Rebooting the panel..."
    ssh "${TARGET}" 'sudo -n reboot' || echo "    reboot failed - reboot it by hand"
else
    echo "    Reboot the panel when ready:  ssh ${TARGET} sudo reboot"
fi
