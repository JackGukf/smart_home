#!/bin/sh
# Entrypoint for the Matter bridge container.
# Ensures /data/bridge directory exists and is writable by the matter user,
# then drops privileges to run the bridge as the matter user.

set -e

mkdir -p /data/bridge
chown matter:matter /data/bridge

# Use gosu to drop to matter user and exec the bridge with all arguments
exec gosu matter /usr/local/bin/chip-bridge "$@"
