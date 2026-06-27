#!/bin/sh
# Entrypoint for the Matter bridge container.
# Ensures /data/bridge directory exists and is writable by the matter user,
# then drops privileges to run the bridge as the matter user.

set -e

mkdir -p /data/bridge
chown matter:matter /data/bridge

# Drop privileges to the matter user and exec the bridge with all arguments.
# Uses plain su (no gosu dependency) — su -s sets the shell, -c with exec
# preserves the PID so SIGTERM from Docker reaches chip-bridge directly.
exec su -s /bin/sh matter -c 'exec /usr/local/bin/chip-bridge "$@"' -- "$@"
