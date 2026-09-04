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

### The Living Room Camera needs a patched Tuya integration

Tuya moved the Living Room Camera (`ebbec1c57e3b06cfb3hzev`) to an
**undocumented device category `cdsxj`**. Home Assistant's Tuya integration maps
only `sp` and `dghsxj` to the camera platform, so the device produces *zero*
entities and the device page shows `Smart Camera (unsupported)`. Upstream:
[home-assistant/core#177197](https://github.com/home-assistant/core/issues/177197),
still open as of HA 2026.6.3. Tuya has done this before — cameras moved `sp` →
`dghsxj`, fixed in PR #136960 the same one-line way.

This is *not* an authentication or network fault, and re-adding the integration
does not help: the category comes from the cloud. Confirm it from diagnostics
rather than guessing:

```bash
curl -s -H "Authorization: Bearer $HOME_ASSISTANT_TOKEN" \
  "http://localhost:8123/api/diagnostics/config_entry/<entry_id>/device/<device_id>" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; print(d["category"], d["online"], list(d["function"]))'
```

Re-apply the patch with:

```bash
./scripts/patch-ha-tuya-cdsxj-camera.sh
```

It edits `camera.py` in the **container's writable layer**, so it survives
restarts and reboots but is lost the moment the container is recreated or the
image is updated — re-run it after either. The original file is kept at
`/config/tuya-camera.py.orig`; `--revert` restores it.

Two things the patch does *not* bring back. The cloud now returns an empty DP
schema (`function: {}`, `status_range: {}`) for this device, so the eleven
control entities — privacy mode, motion detection, flip, watermark — stay gone;
only video returns, because `stream_source()` calls the cloud's
`get_device_stream_allocate` keyed on device id alone and never touches the DPs.
And there is no local fallback: ports 554/8554 are closed on the camera, and a
local tinytuya query against port 6668 returns `null`.

### Wyze RTSP cameras serve one client at a time

The Wyze cameras (`Backyard camera`, `Front door camera`) speak RTSP over TLS on
port **322**, not plain RTSP on 554, and each camera has its **own** RTSP
username and password generated when RTSP is enabled in the app — so every one
needs its own `username_env`/`password_env` pair rather than sharing
`WYZE_RTSP_USERNAME`/`PASSWORD`.

Their RTSP server tolerates roughly one client and **can crash outright**.
Observed 2026-08-24 on the front door camera: port 322 first served two
connections, then accepted TCP while dropping every TLS handshake
(`unexpected eof while reading`), then stopped listening altogether. Ping stayed
perfect throughout, so the network is not the signal to look at. A power-cycle
restores it; the TLS certificate is regenerated at that point, which makes
`notBefore` a reliable boot marker:

```bash
openssl s_client -connect 192.168.0.88:322 </dev/null 2>/dev/null | openssl x509 -noout -dates
```

Because of that single-client limit, the dashboard's idle thumbnail is fetched
from **go2rtc** (`/api/frame.jpeg?src=<stream>`), reusing the session go2rtc
already holds, and only falls back to its own ffmpeg for cameras that have no
gateway. Verify no competing session is being opened with:

```bash
ps -eo pid,ppid,comm | grep ffmpeg   # parent must be go2rtc, not the dashboard
```

### Adding camera credentials needs two restarts

`.env` is read **at process start**, so new credentials are invisible to
anything already running. After editing it:

```bash
cd /home/orangepi/smart_home_AI && python3 scripts/generate-go2rtc-config.py \
  && systemctl --user restart go2rtc smart-home-dashboard
```

Skipping the dashboard restart produces a confusing split: the live view works
(go2rtc has the credentials baked into its regenerated config) while snapshots
fail with `400 {"detail":"Camera does not have an RTSP stream URL"}`, because
the dashboard builds that URL from env vars it never loaded.

### Newer TP-Link switches (S505) need Matter, not the tplink integration

The S505 in the north bedroom cannot be driven locally by `python-kasa`. It
negotiates TP-Link's newer **TPAP** encryption, which the library does not
implement:

```
UnsupportedDeviceError: Unsupported device 192.168.0.163 of type SMART.TAPOSWITCH
with encrypt_scheme EncryptionScheme(is_support_https=False, encrypt_type='TPAP', ...)
```

Home Assistant bundles the same library, so its `tplink` integration fails too —
there it surfaces as `responded with 403 to handshake1`, which reads like bad
credentials but is not: the handshake never gets past the encryption scheme.
Tracked upstream as [python-kasa#1590](https://github.com/python-kasa/python-kasa/issues/1590)
(open, PR #1706 unmerged as of 2026-08-27), so upgrading HA will not fix it
until that lands. The old HS200/HS103/HS220 switches are unaffected — they use
the legacy unauthenticated protocol.

Left unattended, that entry logged a 403 roughly every five seconds and grew
`home-assistant.log` to 67 MB in three days. Its config entry is therefore
**disabled**, not deleted, so it can be re-enabled if TPAP support ships.

Control it through **Matter** instead. Matter devices hold several fabrics at
once, so commissioning Home Assistant does not disturb Apple Home: get a setup
code from the Home app (accessory settings, *Turn On Pairing Mode*) and add it
under HA's Matter integration. The dashboard then targets the Matter entity:

```yaml
home_assistant_devices:
- category: light_switch
  entity_id: light.bedroom_north_bedroom_light_switch   # Matter, not switch.north_bedroom
  name: North bedroom light switch
```

**Re-pairing reuses the existing HA device entry** when the serial matches
(`serial_ACA7F1B55729`), so a device id captured before pairing points at the
*live* device afterwards, not at the orphan. Re-read the registry after
commissioning before removing anything. If the device is deleted by mistake, the
node stays commissioned in the fabric and reloading the Matter config entry
rebuilds it:

```bash
curl -X POST -H "Authorization: Bearer $HOME_ASSISTANT_TOKEN" \
  http://localhost:8123/api/config/config_entries/entry/<matter_entry_id>/reload
```

#### When the north bedroom switch stops working

It has stopped twice. Both times **the switch was fine and on the network**, and
both times the dashboard showed nothing wrong — but the causes were different,
and so are the fixes, which is why step 3 below is the one that matters:

- **2026-08-26** — the Home Assistant *device entry* was deleted by mistake. The
  node was still commissioned, so reloading the Matter config entry rebuilt it.
- **2026-09-04** — the *node itself* was gone. Rebuilding the Matter fabric
  during the 2026-09-02 recovery does not re-commission the nodes in it: only
  our own Matter bridge came back, the S505 did not, and
  `light.bedroom_north_bedroom_light_switch` stopped existing. Reloading the
  config entry cannot fix this one — there is nothing in the fabric to rebuild
  from.

Diagnose in this order. The first three take seconds and rule out everything
that is *not* the fabric:

```bash
# 1. Is the switch on the LAN? (MAC aca7f1b55729 == serial ACA7F1B55729)
ping -c2 192.168.0.163 && ip neigh show 192.168.0.163

# 2. Does the entity exist in Home Assistant? "Entity not found" is the symptom.
curl -s -H "Authorization: Bearer $HOME_ASSISTANT_TOKEN" \
  http://127.0.0.1:8123/api/states/light.bedroom_north_bedroom_light_switch

# 3. Is the node in the fabric? matter-server is a SYSTEM unit, not a user one -
#    `systemctl --user status matter-server` says "could not be found" even when
#    it is running perfectly.
systemctl status matter-server
```

Step 3 is the answer. Ask matter-server what it actually holds — its node list
is authoritative, and HA's device registry is only a mirror of it:

| What you see | What it means | Fix |
| --- | --- | --- |
| Node with vendor `TP-Link`, serial `ACA7F1B55729` | Commissioned; HA lost the device entry | Reload the Matter config entry (above) |
| Only node 1, `TEST_VENDOR`/`TEST_PRODUCT` | That is *our own* `matter-bridge`, not the switch. **The S505 is not in the fabric** | Re-commission — see below |

`TEST_VENDOR`/`TEST_PRODUCT` is the CHIP example-app identity our bridge ships
with. It is easy to mistake for the switch because it is the only Matter light
in Home Assistant; it is not, and reloading the config entry will not conjure
the S505 back.

Re-commissioning **cannot be done over SSH** — it needs a setup code, which only
the Apple Home app can mint:

1. Home app → the switch → accessory settings → *Turn On Pairing Mode*.
2. Home Assistant → Settings → Devices → Matter → *Add device* → enter the code.
   Matter devices hold several fabrics at once, so this does not disturb Apple Home.
3. Read the new entity id back and reconcile `configs/devices.local.yaml`:

```bash
curl -s -H "Authorization: Bearer $HOME_ASSISTANT_TOKEN" \
  http://127.0.0.1:8123/api/states | \
  python3 -c 'import json,sys; [print(e["entity_id"]) for e in json.load(sys.stdin) if e["entity_id"].startswith("light.")]'
```

The entity may come back under a different id — a re-added node gets a `_2`
suffix when the old registry entry is still there — so **check it rather than
assuming**, and update `home_assistant_devices.entity_id` to match.

The dashboard no longer hides this. `_home_assistant_card_availability()` in
`web_app.py` separates three states that used to be one, because a configured
entity that has vanished used to render as a switch that was simply **off**:
`is_on` was `None` for both, and the front end drew a live-looking rocker over
"OFF". A card whose entity Home Assistant does not have now reads
**UNAVAILABLE** with the reason where the room name goes, and its rocker is
disabled. "We could not reach Home Assistant" stays a separate, quieter state —
collapsing the two would cry wolf on every HA restart.

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
