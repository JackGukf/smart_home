# Handoff: board recovery after NVMe-related resets

**Status: board is stable but bare. Nothing of the smart-home stack is running.**
Written 2026-09-03 at the end of a long debugging session, for a fresh session to
pick up recovery.

> **Update 2026-09-03, later that day: the NVMe has been erased and reflashed
> with the stock Ubuntu image, to test whether the resets follow a clean OS.**
> The old filesystem is **gone** — the backup archives are now the only copy.
> See "NVMe wipe and reflash" below before doing anything with either disk.

## Current state of the board

| | |
| --- | --- |
| Reachable at | `192.168.0.234` over Wi-Fi (SSH host key **changed** — it was re-flashed) |
| Booting from | **SD card** (`/dev/sda2`, 29.2 GB) — a fresh flash of the stock Orange Pi image |
| Uptime | stable through every stress test; still up 58 min later having driven the whole reflash (~26 GB written to the NVMe) without a reset |
| NVMe | `WD_BLACK SN750 SE 500GB` attached over a **USB adapter**. ~~auto-mounted read-write with the old system~~ — **erased and reflashed 2026-09-03**, now a virgin Ubuntu install, unmounted |
| Zigbee dongle | **physically removed** |
| M.2 slot | empty — leave it that way, see below |

**The SD is not a clone of the working system.** It is a clean image that happens
to share filesystem UUIDs with the NVMe, because Orange Pi images ship with a
fixed root UUID. So:

- `~/smart_home_AI` does **not** exist on the SD
- no systemd user services exist (`not-found`, not merely disabled)
- no containers, no Home Assistant, no Mosquitto, no Zigbee2MQTT
- Ollama not installed/running, no swap

Everything from the old system now exists **only in the backup archive**. The
NVMe copy was destroyed by the 2026-09-03 reflash. There is no third copy — the
two archives below are it. Verify a restore target before overwriting either.

## Where the data is

**Verified backup**, pulled to the workstation and integrity-checked by parsing
each file (not just listing it):

```
~/orangepi-recovery/nvme-recovery-2026-09-03.tgz     12,948,968 bytes, 1123 files
/home/orangepi/nvme-recovery-2026-09-03.tgz          same archive, on the SD
```

Both re-verified byte-identical on 2026-09-03 immediately before the reflash:

```
sha256  ce7ad1083f8da61413de736de522c42071067bc9eea17a70e66b9fc128353cb9
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

The NVMe filesystem was undamaged and fully readable right up to the point it was
deliberately erased. Nothing was lost to the fault; the archive was pulled from a
healthy filesystem.

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

## NVMe wipe and reflash (2026-09-03)

Done deliberately, to answer one question the earlier tests could not: **do the
resets follow a clean OS?** The drive was erased and reflashed with the stock
image so that NVMe-as-root can be retried on a filesystem with no history.

This is a low-information test and was known to be so before it was run — the
fault signature is below Linux (no panic, empty pstore, firmware `0x143`), every
service was already stopped when the resets happened, and `apt` history was
empty, so there was no software state for a reinstall to fix. It was run anyway
to close off the possibility by test rather than by argument, which is the
standard the rest of this document holds to.

### What was done

| | |
| --- | --- |
| Image | `Orangepi6plus_1.0.2_ubuntu_noble_desktop_gnome_linux6.6.89.img.xz` |
| Provenance | Official Orange Pi image, SHA256 verified against its `.sha` on the workstation **and** again on the board after transfer |
| Target pinning | `/dev/disk/by-id/ata-WD_BLACK_SN750_SE_500GB_21315M803709` — serial, size and not-root asserted at write time, never a bare `/dev/sdb` |
| Erase | `wipefs -a` cleared primary GPT, **backup GPT at `0x7470c05e00`**, and PMBR; then 64 MiB zeroed at head and tail |
| Write | 12,853,444,608 bytes, `dd bs=4M oflag=direct conv=fsync`, exit 0 |
| Verify | Full readback `cmp` against the image with caches dropped and nothing mounted — byte-for-byte match |

The backup GPT at the end of the disk matters: it survives a 12 GiB image write
and would otherwise have kept the old colliding UUIDs alive on a 466 GB disk.

### A SMART data point worth keeping

Counters across the whole operation (~25.8 GB written, 12 GB read back):

| | before | after |
| --- | --- | --- |
| Error Information Log Entries | 1,205 | **1,205** |
| Media and Data Integrity Errors | 0 | 0 |
| Unsafe Shutdowns | 296 | 296 |
| Data Units Written | 4,130,759 | 4,181,230 |

**No new errors under sustained sequential I/O as a data disk.** This reinforces
the existing theory rather than changing it: the counter moves when the drive is
*root*, not under load as such. The board also stayed up throughout.

Full captures are committed alongside this doc:

```
docs/incident-2026-09-03/smart-baseline-pre-erase.txt
docs/incident-2026-09-03/smart-post-flash.txt
```

### The UUID collision is now live — read before booting

Both disks carry the stock image, so they now share identifiers:

```
sda1 / sdb1   ESP    UUID 27E0-5B2B      PARTUUID 0f0e4662-a0ae-4541-b76d-86c060411279   ← identical
sda2 / sdb2   ext4   UUID 228d2b4f-...   PARTUUID ab8cf4ab-... (SD) / 2977fae0-... (NVMe)
```

Each ESP's `GRUB.CFG` points at its **own** root by PARTUUID, so root resolution
is unambiguous once an ESP is chosen. What is ambiguous is *which ESP the
firmware picks* — the two are indistinguishable by PARTUUID and label.

**So: physically remove the SD card before testing an NVMe boot.** Leave it in
and the board may boot the SD and the test silently proves nothing.

### Before running the test

- **The fresh image has none of the Wi-Fi credentials** that make `192.168.0.234`
  reachable. Booted from NVMe the board will be off the network — have a monitor
  and keyboard attached, or Ethernet (and see the both-interfaces warning below).
  Login on the fresh image is `orangepi` / `orangepi`.
- Root is 11.8 GB of 465.8 GB until first boot auto-expands it.
- **Enable journald persistence first**, or a reset teaches nothing again:

```bash
sudo mkdir -p /var/log/journal
sudo sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

- The verified image is kept at `/home/orangepi/Orangepi6plus_...img.xz` on the
  SD (1.9 GB), so a re-flash needs no new download.

### How to read the result

Whether it resets is only half the signal. Afterwards compare SMART against
`docs/incident-2026-09-03/smart-post-flash.txt`:

- **Resets return AND `Error Information Log Entries` climbs from 1,205** →
  hardware, as theorised. Proceed to the native-NVMe error-log read and the RMA.
- **Resets return AND the counter does not move** → the theory is wrong; the
  fault is in the board or firmware's NVMe-as-root path, not the drive.
- **No resets over several days** → genuinely unexplained, since nothing a
  reinstall changes was implicated. Do not read a clean run as an all-clear;
  re-check the counter before trusting the drive with the stack.

**Result: not yet run — record it here.**

## Recovery plan

Restore onto the **SD system**, keeping the NVMe as data only.

This plan stands regardless of how the reflash test turns out, and is the path
back to a working house. Do not begin restoring the stack onto the NVMe on the
strength of a clean test run alone — see "How to read the result" above.

1. **Do not** put the NVMe back in the M.2 slot, and do not make it root again —
   except deliberately and temporarily, for the reflash test described above.
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

- **Have the drive tested in a PC with a native NVMe slot.** Still open, and
  still the highest-value test. Re-confirmed 2026-09-03: over the USB bridge
  `smartctl` reports `NVMe Get Log truncated to 0x200 bytes` and then
  `No Errors Logged`, so the 1,205 entries are invisible — only the counter
  survives. `smartctl -l error /dev/nvme0` on a native slot will show what they
  actually are. Drive firmware is `711130WD`; check for a WD update while it is
  in there. If in warranty, this looks like an RMA.
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

- **Change the default password.** Still `orangepi/orangepi` as of 2026-09-03 —
  confirmed, not assumed; it was used to run the reflash. That is the most-scanned
  SBC credential pair there is, and this host runs Home Assistant on the LAN. The
  freshly flashed NVMe ships with the same default, so **both** installs need it
  changed. Do this before either system gets a route to the internet.
- Deploy scripts and docs still default to `192.168.0.234`. Fine for now, but
  they will need updating if the address changes.
- `scripts/resource-logger.sh` was what made this diagnosable. Reinstall it
  early — `deploy/systemd/user/resource-logger.service`.

## Related

- `docs/local-ai.md` — the LLM and NPU stack, and why those services are off
- `PROJECT_CONTEXT.md` — project background
