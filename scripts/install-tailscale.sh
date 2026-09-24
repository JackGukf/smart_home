#!/usr/bin/env bash
#
# Tailscale on the Orange Pi: reach the dashboard, Home Assistant and SSH from
# away from home without opening a single port on the router.  Run it ON the board.
#
#   ssh -t orangepi@<board>     # address: configs/hosts.env
#   cd smart_home_AI && ./scripts/install-tailscale.sh
#
# The first run prints a login URL; open it on any device signed in to your
# tailnet and the script carries on by itself.  Unattended instead:
#
#   TS_AUTHKEY=tskey-auth-... ./scripts/install-tailscale.sh
#
# What it deliberately does NOT do, and why:
#
#   --accept-dns=false   Tailscale would otherwise rewrite /etc/resolv.conf to
#                        100.100.100.100.  That file is hand-written on purpose:
#                        Docker copies it into containers, and a resolver the
#                        containers cannot reach presents as a Tuya
#                        "authentication failure" (docs/restore-runbook.md).
#                        MagicDNS names still work FROM your other devices.
#   no --accept-routes   The board is on the LAN it serves; a subnet route
#                        advertised by another node must not capture it.
#   no --ssh             Plain OpenSSH over the tailnet address is enough and
#                        keeps one set of keys.
#   no exit node / subnet router - opt in later, see docs/tailscale.md.
#
# Safe to re-run: an already-logged-in node only has its settings re-applied.
set -euo pipefail

TS_HOSTNAME="${TS_HOSTNAME:-orangepi6}"
RESOLV="/etc/resolv.conf"
KEYRING="/usr/share/keyrings/tailscale-archive-keyring.gpg"
APT_LIST="/etc/apt/sources.list.d/tailscale.list"

# Same sudo resolution as backup-smart-home.sh: passwordless if the host allows
# it, an askpass helper for unattended runs, otherwise prompt on the terminal.
if sudo -n true 2>/dev/null; then
  SUDO="sudo -n"
elif [[ -n "${SUDO_ASKPASS:-}" && -x "${SUDO_ASKPASS}" ]]; then
  SUDO="sudo -A"
else
  SUDO="sudo"
fi

info() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m    %s\n' "$*" >&2; }
die()  { printf '\n\033[31mERROR\033[0m: %s\n' "$*" >&2; exit 1; }

assert_watchdog_off() {
  local watchdog
  watchdog="$(systemctl show -p RuntimeWatchdogUSec --value)"
  if [[ "${watchdog}" != "0" && "${watchdog}" != "off" ]]; then
    die "RuntimeWatchdogUSec=${watchdog}, expected 0.

This board's SBSA watchdog has a FIXED 10-second timeout, so any non-zero
setting resets the board roughly every 80 seconds.  See
docs/handoff-2026-09-03-recovery.md before doing anything else."
  fi
  ok "RuntimeWatchdogUSec=0"
}

# --------------------------------------------------------------- preconditions

info "Checking preconditions"
assert_watchdog_off

[[ "$(uname -m)" == "aarch64" ]] || die "expected aarch64, got $(uname -m) - run this on the board"
# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID}" == "ubuntu" ]] || die "expected Ubuntu, got ${ID}"
ok "Ubuntu ${VERSION_CODENAME} aarch64"

resolv_before="$(sha256sum "${RESOLV}" | cut -d' ' -f1)"
ok "${RESOLV} recorded ($(grep -m1 '^nameserver' "${RESOLV}" || echo 'no nameserver'))"

# --------------------------------------------------------------------- install

info "Installing Tailscale"
if command -v tailscale >/dev/null 2>&1; then
  ok "already installed: $(tailscale version | head -1)"
else
  # Tailscale's own apt repository, so updates arrive with apt upgrade.
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.noarmor.gpg" \
    | ${SUDO} tee "${KEYRING}" >/dev/null
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.tailscale-keyring.list" \
    | ${SUDO} tee "${APT_LIST}" >/dev/null
  ${SUDO} apt-get update -qq
  ${SUDO} DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tailscale
  ok "installed: $(tailscale version | head -1)"
fi

${SUDO} systemctl enable --now tailscaled.service
systemctl is-active --quiet tailscaled.service || die "tailscaled did not start: journalctl -u tailscaled"
ok "tailscaled enabled and running"

# ------------------------------------------------------------------------ join

info "Joining the tailnet as '${TS_HOSTNAME}'"
flags=(--hostname="${TS_HOSTNAME}" --accept-dns=false --accept-routes=false)

state="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' 2>/dev/null || true)"
if [[ "${state}" == "Running" ]]; then
  ${SUDO} tailscale set "${flags[@]}"
  ok "already logged in - settings re-applied"
else
  keyfile=""
  if [[ -n "${TS_AUTHKEY:-}" ]]; then
    # file: keeps the key out of the process list.
    keyfile="$(mktemp)"
    chmod 600 "${keyfile}"
    printf '%s' "${TS_AUTHKEY}" >"${keyfile}"
    trap 'rm -f "${keyfile}"' EXIT
    flags+=(--auth-key="file:${keyfile}")
  else
    echo "  Open the URL below and approve the machine; this waits for you."
  fi
  ${SUDO} tailscale up "${flags[@]}"
fi

# ---------------------------------------------------------------------- verify

info "Verifying"
ts_ip="$(tailscale ip -4 2>/dev/null | head -1)"
[[ "${ts_ip}" == 100.* ]] || die "no tailnet IPv4 address - tailscale status says: $(tailscale status 2>&1 | head -3)"
ok "tailnet address ${ts_ip}"

ip link show tailscale0 >/dev/null 2>&1 || die "tailscale0 interface missing"
ok "tailscale0 up"

if [[ "$(sha256sum "${RESOLV}" | cut -d' ' -f1)" != "${resolv_before}" ]]; then
  die "${RESOLV} changed - Docker containers will copy it.  Check with
  cat ${RESOLV}
and rerun with --accept-dns=false (this script passes it; something else wrote it)."
fi
ok "${RESOLV} untouched"

getent hosts pkgs.tailscale.com >/dev/null || warn "host DNS lookup failed - check ${RESOLV}"
assert_watchdog_off

dns_name="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
host="${dns_name:-${ts_ip}}"

cat <<EOF

Done.  From any device on your tailnet:

  Dashboard        http://${host}:8000
  Home Assistant   http://${host}:8123
  SSH              ssh orangepi@${host}

Two things to do once, in https://login.tailscale.com/admin/machines:
  - '${TS_HOSTNAME}' -> ... -> Disable key expiry, or the board drops off the
    tailnet in 180 days and nobody is home to log it back in.
  - Check the ACLs: every service here listens on 0.0.0.0, so anything on the
    tailnet can reach go2rtc (:1984) and matter-server (:5580), which have no
    login of their own.
EOF
