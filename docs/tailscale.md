# Tailscale on the Orange Pi

Remote access to the house (dashboard, Home Assistant, SSH) without port
forwarding. The board joins your tailnet as `orangepi6`; nothing on the router
changes and the LAN setup is untouched.

## Install

On the board, in a terminal (it asks for sudo and prints a login URL):

```bash
ssh -t orangepi@192.168.0.83 'cd smart_home_AI && ./scripts/install-tailscale.sh'
```

Unattended, with an auth key from the admin console: `TS_AUTHKEY=tskey-auth-… ./scripts/install-tailscale.sh`.
Re-running is safe; a logged-in node only has its settings re-applied.

Then, once, in the [admin console](https://login.tailscale.com/admin/machines):
**disable key expiry** for `orangepi6`, or it falls off the tailnet after 180 days.

## Settings, and why

| Setting | Why |
| --- | --- |
| `--accept-dns=false` | `/etc/resolv.conf` is hand-written because Docker copies it into containers. Tailscale would replace it with `100.100.100.100`, which bridge-network containers cannot reach — the failure looks like a Tuya auth error (see `restore-runbook.md`). The script fails if the file changes. |
| `--accept-routes=false` | The board sits on the LAN it serves; another node's subnet route must not capture that traffic. |
| no Tailscale SSH | OpenSSH over the tailnet address works and keeps one set of keys. |
| no subnet router / exit node | Opt in only if you need them: `sudo tailscale set --advertise-routes=192.168.0.0/24` (plus IP forwarding, and approve it in the console) would expose cameras and switches that have no login of their own. |

## What becomes reachable

Every service binds `0.0.0.0`, so on the tailnet you get the dashboard `:8000`,
Home Assistant `:8123`, go2rtc `:1984` and matter-server `:5580`. The last two
have **no authentication**; if the tailnet has other people or shared nodes,
restrict `orangepi6` with an ACL to your own devices.

Home Assistant's `trusted_networks` (the wall panel's login bypass) covers the
panel's LAN address only, so tailnet clients get the normal login. The Home
Assistant mobile app works with `http://orangepi6.<tailnet>.ts.net:8123` as its
internal or external URL.

## Checking it

```bash
tailscale status
tailscale ip -4
```
