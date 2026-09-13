# Deployment targets, from configs/hosts.env. Source this; do not execute it.
#
#   . "$(dirname "$0")/lib/hosts.sh"
#
# Anything already set in the environment wins, so a caller's `PI_HOST=x cmd`
# and a script's own `--host` flag both still override the file. That ordering
# is the point: the file is a default, not a lock.
#
# Deliberately not `set -a; . hosts.env` - that would clobber an env var the
# caller set on purpose, which is exactly backwards.

# shellcheck shell=bash

smart_home_load_hosts() {
    local file="${SMART_HOME_HOSTS:-}"
    if [[ -z "$file" ]]; then
        local here
        here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        file="${here}/../../configs/hosts.env"
    fi

    if [[ ! -r "$file" ]]; then
        echo "hosts.sh: cannot read ${file}" >&2
        return 1
    fi

    local line key value
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip blanks and comments; tolerate CRLF from a Windows checkout.
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        [[ "$line" != *=* ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        # Only a plain NAME=value line is honoured, so a stray shell fragment in
        # the file cannot become something this eval-free parser executes.
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        # Already set (and non-empty) means the caller meant it. Leave it.
        [[ -n "${!key:-}" ]] && continue
        printf -v "$key" '%s' "$value"
        export "${key?}"
    done < "$file"
}

smart_home_load_hosts
