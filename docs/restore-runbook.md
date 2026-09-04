# Runbook: restore the smart-home stack from backup

**Purpose: hand this file to a fresh session and say "restore the dashboard per
`docs/restore-runbook.md`". Everything needed is here.**

Written 2026-09-03 from an end-to-end rebuild onto a freshly flashed board. Every
trap listed cost real time on that rebuild; none of them announce themselves.

Related: `docs/handoff-2026-09-03-recovery.md` is the *incident* record (why the
board was rebuilt, the watchdog finding). This file is the *procedure*.

---

## 0. Before you start

| | |
| --- | --- |
| Board | `orangepi@192.168.0.234`, Orange Pi 6 Plus, Ubuntu Noble |
| Boots from | NVMe in the PCIe slot (`/dev/nvme0n1p2`) |
| Backup | newest `~/orangepi-recovery/smart-home-backup-*.tgz` on the workstation |
| Repo | `git@github.com:JackGukf/smart_home.git`, branch `main` |
| Password | `orangepi` (still the default — see Open risks) |

**Use the newest `smart-home-backup-*.tgz`, not `nvme-recovery-2026-09-03.tgz`.**
The older archive is missing `.storage/auth` and will cost you every Home
Assistant token and login session.

Confirm the archive before trusting it:

```bash
tar tzf <archive> | grep -c 'homeassistant-config/.storage/auth'   # must be 1
```

---

## 1. Restore, in order

Order matters only where noted. Run from the workstation unless stated.

### 1.1 Get the source onto the board

The board needs the repo at `/home/orangepi/smart_home_AI`. Either clone it, or
rsync the local checkout:

```bash
rsync -a --exclude='.git/' --exclude='build/' --exclude='third_party/' \
      --exclude='.codegraph/' --exclude='__pycache__/' --exclude='.venv/' \
      ./ orangepi@192.168.0.234:/home/orangepi/smart_home_AI/
```

> **Trap — `.codegraph/` is 1.1 GB.** It is not in the exclude list by accident;
> a `du -sh *` misses it because it is hidden, and syncing it wastes ten minutes
> over this Wi-Fi.

### 1.2 Restore config from the archive

Copy the archive to the board and unpack these into place:

| From archive | To |
| --- | --- |
| `smart_home_AI/.env` | `~/smart_home_AI/.env` (mode 600) |
| `smart_home_AI/configs/devices.local.yaml` | same path |
| `smart_home_AI/dashboard_areas.json` | same path |
| `smart_home_AI/deploy/zigbee/zigbee2mqtt/` | **entire directory** |
| `smart_home_AI/go2rtc/go2rtc.yaml` | same path |
| `homeassistant-config/` | `/home/orangepi/homeassistant-config` |
| `matter-server/` | `/var/lib/matter` (root-owned) |
| `homeassistant-container-spec.json` | `~/` (read for the image digest) |

> **Trap — the Zigbee directory must move as a unit.** The network key in
> `configuration.yaml`, `database.db` and `coordinator_backup.json` only restore
> devices without re-pairing if they stay consistent with each other.

> **Trap — `dashboard_areas.json` holds every device-to-area assignment**, all
> made by hand. Nothing regenerates it. Without it the dashboard comes up looking
> fine with every device in "Unassigned".

### 1.3 Python environment

```bash
cd /home/orangepi/smart_home_AI
python3 -m venv .venv && ./.venv/bin/pip install -r src/python/requirements.txt
```

> **Trap — Noble enforces PEP 668.** A system-wide `pip install` fails.
> `scripts/run-dashboard.sh` already prefers `.venv/bin/python` if it exists.

### 1.4 go2rtc binary

Not in git (`bin/go2rtc*` is ignored) and no script installs it:

```bash
curl -sSL -o bin/go2rtc \
  https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_arm64
chmod +x bin/go2rtc
```

### 1.5 Boot persistence

```bash
sudo loginctl enable-linger orangepi
sudo systemctl enable docker containerd
```

> **Trap — `docker` ships *disabled* on a fresh image.** Everything looks correct
> until the first reboot, when Home Assistant simply does not come back.
> Lingering is what lets the user units start with nobody logged in.

### 1.6 Dashboard and go2rtc

```bash
cd /home/orangepi/smart_home_AI && bash scripts/install-dashboard-service.sh
```

### 1.7 Home Assistant

Recreate from the **digest recorded in the container spec**, never `:latest`:

```bash
docker run -d --name homeassistant --privileged --restart=unless-stopped \
  --network=host --dns 192.168.0.1 -e TZ=America/Vancouver \
  -v /home/orangepi/homeassistant-config:/config \
  -v /etc/localtime:/etc/localtime:ro -v /run/dbus:/run/dbus:ro \
  ghcr.io/home-assistant/home-assistant@sha256:<digest from the spec>
```

> **Trap — `--dns` is not optional.** Docker strips loopback nameservers when it
> copies the host resolver at container-creation time. If the host is still on
> the `systemd-resolved` stub (`127.0.0.53`), the container gets an **empty**
> `/etc/resolv.conf` and every cloud integration fails with
> `Failed to resolve ... [Errno -3]`. **This presents as a Tuya authentication
> failure and is not one.** Check `docker exec homeassistant cat /etc/resolv.conf`
> before believing any "auth" error.

> **Trap — never `:latest`.** A newer Home Assistant migrates `.storage`
> irreversibly. Config here is 2026.6.3.

### 1.8 Re-apply the Tuya camera patch

```bash
bash scripts/patch-ha-tuya-cdsxj-camera.sh
```

> **Trap — the patch lives in the container's writable layer.** `docker restart`
> keeps it; `docker rm` + `run`, or any image update, silently loses it.
> `camera.living_room_camera` disappearing is the symptom. Re-run after **any**
> container recreate.

### 1.9 Home Assistant token

The restored `.env` token will **not** work if the archive predates the
`.storage/auth` fix, and cannot be repaired — its issuing refresh token no longer
exists. Mint a new one:

HA → your initials (bottom-left) → **Security** → **Long-lived access tokens** →
**Create token**. Copy it immediately, it is shown once. Then:

```bash
cd ~/smart_home_AI && sed -i "s|^HOME_ASSISTANT_TOKEN=.*|HOME_ASSISTANT_TOKEN=<token>|" .env
systemctl --user restart smart-home-dashboard
```

Verify it landed — the JWT's `iss` must match a real refresh token id:

```bash
docker exec homeassistant python3 -c "
import json;d=json.load(open('/config/.storage/auth'))['data']
print(sum(1 for t in d['refresh_tokens'] if t['token_type']=='long_lived_access_token'))"
```

### 1.10 Zigbee

**Plug the dongle in first.** Then:

```bash
cd ~/smart_home_AI && bash scripts/install-zigbee2mqtt.sh
```

It keeps an existing `configuration.yaml`, reuses `secret.yaml`, regenerates the
mosquitto `passwd` (which is *not* in the backup — it is generated), records the
by-id adapter path in `.env`, installs `zigbee-adapter-watch.service`, and brings
the stack up.

> **Trap — never let anything overwrite `configuration.yaml`.** It holds the
> network key. A regenerated key orphans every paired device. Snapshot the
> directory first and diff the key afterwards.

Expect `zigbee-herdsman started (resumed)` and `Currently 5 devices are joined`.

### 1.11 Matter (only if you use it)

```bash
bash scripts/install-matter-server.sh
```

> **Trap — reinstalling gives a *new, empty fabric*.** If `/var/lib/matter` was
> not restored, every Matter device needs a factory reset and re-commissioning;
> node ids in `devices.local.yaml` are useless without the fabric keys.

### 1.12 Back up immediately

```bash
bash scripts/backup-smart-home.sh
```

Do this once Zigbee and Matter are up, so the live coordinator state and fabric
are captured. The script fails loudly if a required member is missing.

---

## 2. Verification

Expected once healthy (counts drift a little as batteries report):

```
user/smart-home-dashboard   active enabled      :8000  → 303 → /login
user/go2rtc                 active enabled      :1984  → 200, 6/6 cameras
user/resource-logger        active enabled
user/zigbee-adapter-watch   active enabled
sys/docker, containerd      active enabled
sys/matter-server           active enabled      :5580
docker: homeassistant, zigbee2mqtt, mosquitto   :8123 → 200
```

| Integration | working | notes |
| --- | --- | --- |
| mqtt | ~58 | Zigbee. **6 unavailable is correct** — see below |
| tuya | ~24–30 | battery sensors drift in and out |
| tplink | 18 | |
| homekit_controller | 17 | ecobee + 2 remote sensors |
| matter | 6 | |
| automation | 5 | four button rules `on` |

Registry: ~222 entities, ~56 devices.

**Expected `unavailable` — do not chase these:**

- **6 mqtt** — `*_npu_person`, `*_npu_person_count` for three cameras. They belong
  to `npu-detector`, which is deliberately not installed.
- **13 mobile_app** — phones that are not connected.
- Two battery Tuya sensors (water, temp/humidity) report only periodically.

Also verify:

```bash
systemctl show -p RuntimeWatchdogUSec        # MUST be 0
```

---

## 3. Traps that do not announce themselves

Ordered by how much time they cost.

1. **`RuntimeWatchdogSec` must stay unset.** The board's SBSA watchdog has a
   **fixed 10 s timeout** (`SETTIMEOUT` unsupported). Setting 60 s makes systemd
   ping every 30 s against a 10 s timer, resetting the board ~80 s after boot,
   forever, with no kernel panic and an empty `pstore`. This is the prime suspect
   for the 2026-09-02 reset loop. Journald persistence is safe and worth setting;
   the watchdog line is not.
2. **Empty container `/etc/resolv.conf`** masquerading as a Tuya auth failure
   (§1.7).
3. **The Tuya camera patch is lost on container recreate** (§1.8).
4. **`docker` disabled at boot** — passes every test until a power cycle (§1.5).
5. **`.storage/auth` absent from old archives** — silently loses every token,
   because the file is root-owned and a non-root backup skips it without error.
6. **Wi-Fi is weak.** SSH drops mid-command; RTT 35–175 ms on the LAN. Run long
   operations detached (`setsid nohup`) so a dropped connection cannot truncate
   them. Prefer Ethernet, but **never run Wi-Fi and Ethernet on the same subnet
   at once** — two addresses with one connected route causes constant drops.
7. **`localStorage` drag orders beat the default room order.** If cameras or
   devices appear in the wrong order after a restore, clear `camera_order_v1`,
   `light_order_v1`, `plug_order_v1`, `home_area_order` in the browser. This is
   per-browser and invisible from the server.
8. **The post-commit hook deploys.** Committing `src/python/web_static/**` or
   `web_app.py` runs `deploy-dashboard.sh`, which rewrites `BUILD_COUNT` and
   cache-busting metadata. Commit that follow-up with hooks disabled
   (`git -c core.hooksPath=/dev/null commit`) or it retriggers itself.

---

## 4. Open risks

- **Default password.** Still `orangepi/orangepi` on a host running Home
  Assistant on the LAN. Change it.
- **`North bedroom light switch`** is not commissioned on the current Matter
  fabric. Factory reset it, re-pair, then re-run the backup.
- **Front door sensor (Zbeacon TS0203) does not hold state.** Every movement, in
  either direction, emits an identical `contact:true` → `contact:false` pair
  ~140 ms apart, so it settles to "open" and stays there. The level cannot be
  polled (`No converter available for 'contact'`). Suspected marginal magnet gap;
  a firmware quirk is not ruled out. **Do not "fix" this with a debounce** — it
  would pin the sensor to "closed" after every movement and be wrong half the
  time.
- **SD card is out.** The board boots NVMe-only; there is no fallback root.
