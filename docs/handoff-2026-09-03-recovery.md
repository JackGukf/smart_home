# Handoff: board recovery after NVMe-related resets

**Status: board is stable but bare. Nothing of the smart-home stack is running.**
Written 2026-09-03 at the end of a long debugging session, for a fresh session to
pick up recovery.

## Current state of the board

| | |
| --- | --- |
| Reachable at | `192.168.0.234` over Wi-Fi (SSH host key **changed** — it was re-flashed) |
| Booting from | **SD card** (`/dev/sda2`, 29.2 GB) — a fresh flash of the stock Orange Pi image |
| Uptime | 24+ minutes and stable through every stress test |
| NVMe | `WD_BLACK SN750 SE 500GB` attached over a **USB adapter**, auto-mounted read-write at `/media/orangepi/228d2b4f-5e3f-431d-b5f8-b3bf5f16ffb1` |
| Zigbee dongle | **physically removed** |
| M.2 slot | empty — leave it that way, see below |

**The SD is not a clone of the working system.** It is a clean image that happens
to share filesystem UUIDs with the NVMe, because Orange Pi images ship with a
fixed root UUID. So:

- `~/smart_home_AI` does **not** exist on the SD
- no systemd user services exist (`not-found`, not merely disabled)
- no containers, no Home Assistant, no Mosquitto, no Zigbee2MQTT
- Ollama not installed/running, no swap

Everything from the old system exists **only** on the NVMe and in the backup.

## Where the data is

**Verified backup**, pulled to the workstation and integrity-checked by parsing
each file (not just listing it):

```
~/orangepi-recovery/nvme-recovery-2026-09-03.tgz     12.3 MB, 1123 files
/home/orangepi/nvme-recovery-2026-09-03.tgz          same archive, on the SD
```

Confirmed intact inside it:

- Zigbee `configuration.yaml` — **network key present, 16 bytes**, pan_id,
  ext_pan_id, channel 25, transmit_power 20
- `coordinator_backup.json`, `database.db`, `secret.yaml`, `state.json`
- Home Assistant `/config` (28 MB) — `.storage` with **190 entities, 54 devices**,
  `automations.yaml`, the recorder database
- `configs/devices.local.yaml`, `.env`, `go2rtc/go2rtc.yaml`
- `homeassistant-container-spec-*.json` — records the HA container's mounts
  (`/home/orangepi/homeassistant-config` → `/config`)
- `resource-history.log` from the investigation

The Zigbee network key plus `coordinator_backup.json` and `database.db` are what
make it possible to restore **without re-pairing any device**. Treat the archive
as secret: it contains that key, API tokens, and camera credentials.

The NVMe filesystem itself is undamaged and fully readable.

## The fault

The board reset repeatedly — 87+ times, at intervals from 21 s to 155 s —
whenever the NVMe was the **root filesystem**, whether in the M.2 slot or over
USB. It is stable when the same drive is merely attached as data.

Signature each time: **no kernel panic**, `/sys/fs/pstore` empty, the journal
ending mid-request with no error, and firmware recording
`sw reboot reason 0x143 / hw 0x4 (WARM RESET) / reboot_type 0x43`. Something
below Linux stopped the CPU.

### Ruled out, by test rather than argument

| Suspect | How it was eliminated |
| --- | --- |
| `llama-server` / memory pressure | Disabled; 8.8 GiB free throughout; never an OOM kill; still reset |
| `npu-detector` / NPU driver | Disabled; still reset |
| Zigbee dongle + USB extension | Physically removed; still reset |
| HA, MQTT, Zigbee2MQTT, go2rtc, dashboard | All stopped; still reset |
| Thermal | 37–50 °C throughout, including under load |
| Board power delivery in general | **12-core `stress` for 180 s: no reset**, peaked 50 °C |
| Storage corruption | No ext4/NVMe errors; every config file parsed cleanly |
| NVMe I/O load as such | **4 min sustained read: no reset. 4 min sustained write: no reset** |
| M.2 slot specifically | USB-attached-as-root reset too |
| Kernel/package update | `apt` history empty |

### Best current theory

The drive throws **intermittent command errors** — timeouts or aborts rather
than media failures. As a data disk a stall merely blocks one process, which is
why heavy read and write tests passed. As root, the same stall halts everything
that touches disk and firmware resets the board.

SMART supports this, and one field was initially misread as "healthy":

```
Media and Data Integrity Errors:  0        ← no bad data
Available Spare:                  100%
Percentage Used:                  0%
Error Information Log Entries:    1,205    ← command-level errors
Power On Hours:                   196
Power Cycles:                     1,277
Unsafe Shutdowns:                 296      ← the resets, from the drive's side
```

1,205 error entries at 196 hours on a drive with zero wear is not normal.

**What is still unexplained:** the board ran fine for weeks with this drive, and
the resets began 2026-09-02. Nothing found accounts for the onset. The AI
deployment that day pushed several GB of writes through the drive, which could
plausibly have tipped a marginal device — but that is a hypothesis, not a
finding. Do not present it as the cause.

## Recovery plan

Restore onto the **SD system**, keeping the NVMe as data only.

1. **Do not** put the NVMe back in the M.2 slot, and do not make it root again.
2. Install the base stack on the SD: Docker is already present (1 image); the
   repo is not. Clone `git@github.com:JackGukf/smart_home.git` to
   `/home/orangepi/smart_home_AI`.
3. Restore from the archive, in this order:
   - `configs/devices.local.yaml` and `.env` (git-ignored, not in the repo)
   - `deploy/zigbee/zigbee2mqtt/` **entire directory** — the network key,
     `database.db` and `coordinator_backup.json` must go back together or
     devices will need re-pairing
   - `homeassistant-config/` to `/home/orangepi/homeassistant-config`
   - `go2rtc/go2rtc.yaml` (or regenerate with `scripts/generate-go2rtc-config.py`)
4. Recreate the Home Assistant container with the mounts recorded in
   `homeassistant-container-spec-*.json` (`/home/orangepi/homeassistant-config`
   → `/config`).
5. Bring up the Zigbee stack: `docker compose -f docker-compose.zigbee.yml up -d`.
   **Plug the Zigbee dongle back in first** — `scripts/install-zigbee2mqtt.sh`
   records its by-id path in `.env`.
6. Dashboard and go2rtc: `scripts/install-dashboard-service.sh`.
7. Leave `llama-server` and `npu-detector` **off** until the board has been
   stable for several days. See `docs/local-ai.md` for what they are and
   `scripts/install-ai-services.sh` to bring them back.

### Verify after restoring

- Zigbee: all 5 devices rejoin without pairing (`docker logs zigbee2mqtt`)
- Home Assistant: 190 entities, 54 devices present
- The four button automations still fire

## Open items

- **Have the drive tested in a PC with a native NVMe slot.** The USB bridge
  truncates the error log, so only the counter is visible. `smartctl -l error
  /dev/nvme0` there will show what the 1,205 entries actually are. Check for a
  WD firmware update; if in warranty, this looks like an RMA.
- **SD is a stopgap.** Home Assistant's recorder writes constantly and will wear
  the card. Plan for better storage once the drive question is settled.
- **Wi-Fi is weak** — ping RTT was 70–112 ms on the LAN, and SSH dropped
  constantly during this session. Prefer Ethernet, but see the warning below.
- **Never run Wi-Fi and Ethernet on the same subnet at once.** Both up gives two
  addresses but a single connected route, so replies to the Wi-Fi address leave
  via Ethernet. That alone caused constant SSH drops earlier. Turn Wi-Fi off
  (`nmcli radio wifi off`) once Ethernet is in.
- **Journald persistence and the watchdog** were set on the *NVMe* install and
  are gone with the SD reflash. Re-apply — without them the next incident is
  undiagnosable again:

```bash
sudo mkdir -p /var/log/journal
sudo sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
sudo sed -i 's/^#\?RuntimeWatchdogSec=.*/RuntimeWatchdogSec=60s/' /etc/systemd/system.conf
sudo systemctl daemon-reexec
```

- **Change the default password.** The SD is a stock image; `orangepi/orangepi`
  is the most-scanned SBC credential pair there is, and this host runs Home
  Assistant on the LAN.
- Deploy scripts and docs still default to `192.168.0.234`. Fine for now, but
  they will need updating if the address changes.
- `scripts/resource-logger.sh` was what made this diagnosable. Reinstall it
  early — `deploy/systemd/user/resource-logger.service`.

## Related

- `docs/local-ai.md` — the LLM and NPU stack, and why those services are off
- `PROJECT_CONTEXT.md` — project background
