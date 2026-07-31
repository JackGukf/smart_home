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
