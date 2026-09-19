#!/usr/bin/env bash
# Let the dashboard stop and start the board's desktop (Settings -> Desktop).
#
# Installs one polkit rule: user orangepi may start and stop gdm.service, and
# nothing else. The desktop stays the boot default - this does not touch
# `systemctl get-default`. polkitd picks the rule up without a restart.
#
# Run on the board:  sudo scripts/install-desktop-control.sh
# Undo:              sudo rm /etc/polkit-1/rules.d/50-smart-home-desktop.rules
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "run with sudo: sudo $0" >&2
    exit 1
fi

SOURCE="$(cd "$(dirname "$0")/.." && pwd)/deploy/polkit/50-smart-home-desktop.rules"
TARGET=/etc/polkit-1/rules.d/50-smart-home-desktop.rules

install -m 0644 -o root -g root "$SOURCE" "$TARGET"
echo "installed $TARGET"

default="$(systemctl get-default)"
if [[ "$default" != "graphical.target" ]]; then
    echo "note: the boot default is $default, so the desktop does not start at boot." >&2
    echo "      sudo systemctl set-default graphical.target  brings it back." >&2
fi
