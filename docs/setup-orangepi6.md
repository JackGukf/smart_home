# Orange Pi 6 Plus Setup Notes

The Orange Pi 6 Plus is the primary deployment target, set up 2026-07-29.

## Verified Board Facts

| Property | Value |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS ARM64 |
| Architecture | `aarch64` |
| SoC | Cix P1 / CD8180 |
| CPU | 12 cores, Armv9.2-A big.LITTLE — Cortex-A720 (part `0xd81`) + Cortex-A520 (part `0xd80`) |
| System GCC | 13.3.0 |
| Storage | NVMe |
| Wi-Fi interface | `wlp1s0` — 192.168.0.234 |
| Ethernet interface | `enp97s0` — 192.168.0.14 |
| SSH user | `orangepi` |
| Project path | `/home/orangepi/smart_home_AI` |

Ubuntu uses predictable interface names here, **not** the `wlan0`/`eth0` of
Raspberry Pi OS. Anything that names an interface — most importantly the Matter
bridge's `--interface` flag in `configs/matter-bridge.service` — must use
`wlp1s0` or `enp97s0`. Confirm before installing units:

```bash
ip -o -4 addr show scope global
```

## Base System

```bash
sudo apt update
sudo apt upgrade
sudo apt install build-essential cmake git openssh-server python3 python3-venv python3-pip rsync
sudo systemctl enable --now ssh
```

## Optional Packages

```bash
sudo apt install mosquitto mosquitto-clients
```

## Recommended Services

- SSH for remote development
- MQTT broker if you want local event messaging
- systemd **user** units for always-on services (dashboard, go2rtc, Matter bridge)

Systemd user units only survive logout with linger enabled:

```bash
sudo loginctl enable-linger orangepi
```

## Docker and Home Assistant Autostart

Home Assistant runs as a Docker container on the board, not as a systemd user
unit — so the `enable-linger` above does **not** cover it:

| Property | Value |
| --- | --- |
| Container | `homeassistant` |
| Image | `ghcr.io/home-assistant/home-assistant` |
| Network | `host` (UI on `:8123`) |
| Restart policy | `unless-stopped` |

**`docker.service` must be enabled, not just `docker.socket`.** Docker ships
both units, and the socket alone is enough for interactive use: the first
command that touches `/var/run/docker.sock` socket-activates the daemon. But a
container's restart policy is only applied when the daemon itself starts, so
with `docker.service` disabled the board boots with no daemon, nothing restores
the container, and Home Assistant never comes back after a power cut.

This one is easy to miss because **inspecting it hides it** — running `docker ps`
to check starts the daemon as a side effect, which restarts the container, so
everything looks healthy about ten seconds after you go looking. The symptom
reads as "Home Assistant is down until I check on it".

```bash
sudo systemctl enable --now docker.service
systemctl is-enabled docker.service containerd.service   # both: enabled
```

Verify after a reboot *without* issuing a Docker command first, since that would
mask the fault:

```bash
uptime -s                                                        # boot time
systemctl show docker.service -p ActiveEnterTimestamp            # within ~15s of boot
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8123/  # 200
```

Three related notes:

- **Never `docker stop` the container to test this.** With `unless-stopped`, a
  container stopped explicitly is *not* restarted when the daemon returns — that
  would both invalidate the test and leave HA down. Reboot instead.
- **The board has no battery-backed RTC.** It boots with a stale clock restored
  from `fake-hwclock` until NTP corrects it, so some unit timestamps can appear
  to predate `uptime -s`. Compare against `uptime -s` from the *same* boot
  rather than wall-clock dates.
- Power cuts hard-kill the container, and HA then logs `could not validate that
  the sqlite3 database ... was shutdown cleanly`. Harmless once, but repeated
  hard cuts can corrupt `home-assistant_v2.db` — a UPS is the real fix.
  Autostart only guarantees HA returns afterwards.

### Container DNS must be pinned, or Tuya "authentication" breaks

Docker writes each container's `/etc/resolv.conf` from the host's **at container
start**. If the container starts before the host's DNS has settled — the host
still showing only the `127.0.0.53` systemd-resolved stub, which Docker strips
for containers — Docker can produce a `resolv.conf` with *no nameserver line at
all*. The container then resolves nothing, for as long as it stays up. Restarting
the container regenerates the file and fixes it, which is why the fault survives
reboots but vanishes the moment you restart HA to investigate.

Pin a nameserver so a boot race cannot produce an empty resolver:

```bash
echo '{"dns": ["192.168.0.1"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

Note `systemctl restart docker` restarts the containers with it.

**This presents as a Tuya authentication failure, not a network fault.** Home
Assistant surfaces "authentication failed" while the log shows the real cause:

```
Failed to resolve 'apigw.tuyaus.com' ([Errno -3] Try again)
```

`EAI_AGAIN` is a resolver failure, not a rejected credential. The misdiagnosis
sticks because **re-authenticating fails too** — the Tuya config flow fetches a
login QR code (`config_flow.py` → `__async_get_qr_code`) over the same dead
resolver, so every attempt to fix it through the UI fails the same way and looks
like the credentials really are bad. Observed 2026-08-23: 34 Tuya entities
offline for days with valid tokens the whole time.

Check the resolver before touching credentials:

```bash
docker exec homeassistant grep ^nameserver /etc/resolv.conf   # must be non-empty
docker exec homeassistant python3 -c "import socket;print(socket.gethostbyname('github.com'))"
```

A failure on a *neutral* host like `github.com` proves it is DNS and not the
vendor — that one check separates the two causes immediately.

## Bluetooth

The board has **two** Bluetooth controllers:

| Adapter | MAC | Notes |
| --- | --- | --- |
| Onboard Intel AX210 | `E0:D5:5D:9D:38:97` | USB `8087:0032`; the AX210's Wi-Fi is separate (PCIe, `wlp1s0`) |
| TP-Link UB500 | `20:E1:5D:68:2B:DB` | USB `2357:0604`, Realtek RTL8761B; **the one BLE should use** |

BLE devices (the Govee strips) are pinned to the UB500 with `BLE_ADAPTER` in
`.env`:

```bash
BLE_ADAPTER=20:E1:5D:68:2B:DB
```

`BLE_ADAPTER` accepts an `hciN` name or a MAC. **Prefer the MAC** — `hciN`
numbering is assigned in probe order and can swap across reboots when two
adapters are present. List adapters with `hciconfig -a`.

Three things that are easy to get wrong here:

- **bleak needs an explicit adapter on this host.** With no adapter argument,
  `BleakScanner.discover()` returns *zero* devices — it does not fall back to
  the default controller. `src/python/ble_adapter.py` therefore always passes
  one, defaulting to the first adapter found when `BLE_ADAPTER` is unset.
- **`/sys/class/bluetooth/hciN/address` does not exist on this kernel.** The
  `hciN` entries are there but carry no `address` attribute, so MAC-to-interface
  lookup falls back to parsing `hciconfig`.
- **Govee BLE devices are never paired or bonded.** They stay `Paired: no`,
  `Connected: no` in `bluetoothctl`; the dashboard opens a GATT link per command
  and keeps it warm. Do not try to pair them.

Verify the wiring end to end:

```bash
cd ~/smart_home_AI && set -a && . ./.env && set +a
.venv/bin/python -c "from src.python.ble_adapter import resolve_ble_adapter, ble_kwargs; print(resolve_ble_adapter(), ble_kwargs())"
python3 scripts/discover-govee-ble.py
```

## Local AI (Ollama)

The board also runs Ollama as a system service with `qwen3:4b` installed
(roughly 8 tokens/sec under load). Ollama listens on loopback only, which is
intentional — use an SSH tunnel from the workstation rather than exposing it:

```bash
ssh -N -L 11434:127.0.0.1:11434 orangepi@192.168.0.234
```

Do not widen that binding without an authenticated reverse proxy. Treat model
output as untrusted input: validate schema and keep device actions allow-listed.

## Deployment

Use `scripts/deploy-to-pi.sh` from WSL to cross-compile in Docker and deploy over
SSH. See [orangepi6-cross-compile-deploy.md](orangepi6-cross-compile-deploy.md).

## Secondary Target: Raspberry Pi 4

The previous Raspberry Pi 4 (`smarthome@192.168.0.176`,
`/home/smarthome/smart-home-rpi4`) is still supported so the existing install
keeps working. Build for it with the explicit board flag:

```bash
./scripts/build-orangepi6.sh --board rpi4
```

Its base-system setup is the same as above, except it runs Raspberry Pi OS
64-bit with `wlan0`/`eth0` interface names and the `smarthome` user.
