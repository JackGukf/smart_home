# Handoff: board recovery after NVMe-related resets

**Status: board is stable but bare. Nothing of the smart-home stack is running.**
Written 2026-09-03 at the end of a long debugging session, for a fresh session to
pick up recovery.

> **Update 2026-09-03, later that day: the NVMe has been erased and reflashed
> with the stock Ubuntu image, to test whether the resets follow a clean OS.**
> The old filesystem is **gone** — the backup archives are now the only copy.
> See "NVMe wipe and reflash" below before doing anything with either disk.

> **RESOLVED 2026-09-03: the board is running the full stack again, booted from
> the NVMe in the PCIe slot, and has not reset.** The reset loop did **not**
> follow the clean OS. See "Reflash test result" and "Rebuild on the NVMe" for
> what was rebuilt and the three traps found doing it. The single most important
> line in this document is now: **do not set `RuntimeWatchdogSec`** — see
> "Best current theory".

## Current state of the board

Current as of the 2026-09-03 rebuild. The description of the bare SD system that
was here before is preserved under "State during the incident" below.

| | |
| --- | --- |
| Reachable at | `192.168.0.234` over Wi-Fi (SSH host key changed again with the reflash; clear the old entry) |
| Booting from | **NVMe in the PCIe/M.2 slot** — `/dev/nvme0n1p2`, root auto-expanded to 460.9 GB, stock Orange Pi 1.0.2 Noble |
| SD card | **removed** — it had to come out, see the UUID collision note |
| Stack | dashboard, go2rtc, Home Assistant, resource-logger — all running, all survive a reboot |
| AI services | **not installed**, deliberately — `llama-server`, `npu-detector`, ollama all `not-found` |
| Watchdog | `RuntimeWatchdogUSec=0` — **keep it that way** |
| Zigbee dongle | still **physically removed** — Zigbee cannot come up until it is attached |
| Stability | no resets; one BOOT marker per real boot in `resource-history.log` |

Everything from the old system exists **only in the backup archive** — the NVMe
copy was destroyed by the reflash, and the SD copy left with the SD card. Verify
a restore target before overwriting either remaining copy.

### State during the incident (historical)

At the time this document was first written the board booted from a **SD card**
(`/dev/sda2`, 29.2 GB), a fresh flash of the stock image, with the NVMe attached
over a USB adapter as a data disk and the M.2 slot empty.

**That SD was not a clone of the working system.** It was a clean image that
happened to share filesystem UUIDs with the NVMe, because Orange Pi images ship
with a fixed root UUID. So on it: `~/smart_home_AI` did not exist, no systemd
user services existed (`not-found`, not merely disabled), no containers, no Home
Assistant, no Mosquitto, no Zigbee2MQTT, no Ollama and no swap.

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

> **Superseded 2026-09-03 — see "Best current theory (revised)" below.** The
> drive theory is kept here because the evidence for it is still worth reading,
> but the drive is probably not the cause and the SMART numbers were being read
> backwards. Do not act on this section alone.

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

### Best current theory (revised 2026-09-03)

**The systemd hardware watchdog, enabled during the AI work, is the mechanism.**

The reset intervals in `resource-history.log` are not random. Across 99 resets:

| mode | median | count |
| --- | --- | --- |
| A | **81 s** | 63 |
| B | **139 s** | 26 |
| other | >154 s | 6 |

Two tight modes separated by **58 s**. Hardware faults do not produce a bimodal
distribution with modes a minute apart — that is a **timer**.

The board's watchdog is an **SBSA Generic Watchdog whose `SETTIMEOUT` is
unsupported**, so its timeout is fixed at **10 seconds**:

```
$ wdctl
Device:        /dev/watchdog0
Identity:      SBSA Generic Watchdog [version 0]
Timeout:       10 seconds
SETTIMEOUT     Set timeout (in seconds)     0    ← cannot be changed
```

`RuntimeWatchdogSec=60s` makes systemd ping every 30 s against a hardware timer
that fires at 10 s. It resets the board shortly after systemd arms it late in
boot, which matches the ~81 s period.

This explains every part of the signature that looked mysterious:

| Observation | Explained by |
| --- | --- |
| No kernel panic, `pstore` empty | A watchdog reset is not a crash; there is nothing to record |
| Firmware `WARM RESET 0x143` | Exactly what a watchdog-driven reset looks like |
| 81 s / 139 s bimodal, 58 s apart | A 60 s configured ping against a 10 s timer |
| Only when the NVMe was root | `/etc/systemd/system.conf` lives on the root fs; the SD was a stock image with no watchdog |
| Disabling every service changed nothing | systemd arms the watchdog itself, before any service |
| 12-core stress and sustained I/O passed | Load was never the trigger |
| 1,205 SMART errors, 296 unsafe shutdowns | **Consequences** of 87+ hard resets, not the cause |

That last row matters most: the drive evidence was being read backwards. A reset
aborts in-flight commands, and the drive logs them. The reflash test agrees —
25.8 GB written with the counter frozen at 1,205.

The timeline in `resource-history.log` fits: the board was healthy for 26 minutes
with `llama-server` running, then llama-server was **stopped** at 16:08:23 and the
first reset came 43 s later at 16:09:06. The loop began right after a
configuration change, not under load.

**Limits of this finding.** The NVMe root was erased, and the backup archive
holds only application configs — no `/etc` — so it cannot be proven that
`RuntimeWatchdogSec=60s` was written at 16:08. This is inference from the modal
separation, the timing, the hardware's fixed timeout, and this document's own
record that the watchdog was set on the NVMe install. Strong, but not confirmed.

**Consequence: never set `RuntimeWatchdogSec` on this board.** The Open Items
below used to tell you to re-apply it; that instruction has been corrected.

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

### Reflash test result

**Run 2026-09-03. The resets did not follow the clean OS.**

The NVMe was moved back into the **PCIe/M.2 slot** and booted as root
(`/dev/nvme0n1p2`, root auto-expanded to 460.9 GB, SD card removed). It has been
stable ever since, including a deliberate reboot and a full stack rebuild, with
`RuntimeWatchdogUSec=0` throughout. `resource-history.log` shows one BOOT marker
per real boot — no reset loop.

Read against the three branches above, this is the **"resets return AND the
counter does not move"** case inverted: no resets at all, and the SMART counter
never moved. Combined with the interval analysis, the drive is exonerated as the
*cause*; what changed between the failing and working systems is the root
filesystem's contents, not the hardware.

This also retires the confound the earlier investigation could not separate.
"NVMe as root" always meant two things at once — *this drive* and *the old,
modified system*. The reflash separated them: same drive, same slot, same root
role, clean filesystem, no resets.

## Rebuild on the NVMe (2026-09-03)

Restored per the plan below, **without any of the AI work** (`llama-server`,
`npu-detector`, ollama are all `not-found`; ollama is not installed).

Running and verified to survive a reboot:

| Service | Endpoint | Notes |
| --- | --- | --- |
| `smart-home-dashboard.service` (user) | `:8000` | venv at `.venv` — Noble enforces PEP 668 |
| `go2rtc.service` (user) | `:1984` | 6/6 cameras returning frames; binary is **not** in git (`bin/go2rtc*` is ignored) — fetch the `linux_arm64` release |
| `homeassistant` (docker) | `:8123` | recreated from the pinned digest in `homeassistant-container-spec-*.json`, **not** `:latest`, so it cannot migrate the 2026.6.3 `.storage` |
| `resource-logger.service` (user) | `~/resource-history.log` | reinstall this first, as before |

`loginctl enable-linger orangepi` is set, and **`docker` and `containerd` were
`disabled`** — they are now enabled, without which Home Assistant does not come
back after a power cycle.

### Three traps found during the rebuild

- **The backup archive has no `.storage/auth`.** It contains `.storage/onboarding`
  and `.storage/auth_provider.homeassistant`, but not the store holding users,
  credential links and refresh tokens. Every long-lived token and login session
  is therefore unrecoverable from this archive, and `HOME_ASSISTANT_TOKEN` in
  `.env` was dead on arrival — its issuing refresh token no longer exists. A new
  token has to be minted from the HA UI after logging in. **Fix the backup script
  to include `.storage/auth`.**
- **The HA container came up with an empty `/etc/resolv.conf`.** Docker strips
  loopback nameservers when copying the host resolver at container-creation time;
  the host was still on the `systemd-resolved` stub (`127.0.0.53`), so the
  container got no resolver at all and every cloud integration failed with
  `Failed to resolve … [Errno -3]`. This looked exactly like a Tuya
  authentication failure and is not one. The container is now created with
  `--dns 192.168.0.1` pinned so it cannot recur at boot.
- **`scripts/patch-ha-tuya-cdsxj-camera.sh` must be re-run after any container
  recreate.** The patch lives in the container's writable layer. `docker restart`
  keeps it; `docker rm` + `run`, or an image update, does not.
  `camera.living_room_camera` is the symptom.

### Still outstanding after the rebuild

- **Zigbee** needs the dongle physically attached. Everything else is staged, and
  the network key, `database.db` and `coordinator_backup.json` went back together,
  so the 5 devices should rejoin without re-pairing. 35 MQTT entities stay
  `unavailable` until then, and Home Assistant logs an MQTT connection refusal.
- **Matter** (9 entities) needs `matter-server`, not yet reinstalled.
- Two battery-powered Tuya sensors report only periodically and will read
  `unavailable` until their next check-in.

## Recovery plan

> **Executed 2026-09-03 — but onto the *NVMe*, not the SD.** The steps below were
> followed as written apart from the target: after the reflash test showed the
> resets did not follow a clean OS, the stack was rebuilt on the NVMe in the PCIe
> slot. See "Rebuild on the NVMe" for what that turned up. Kept here as the
> procedure, and as the fallback if the board has to be rebuilt again.

~~Restore onto the **SD system**, keeping the NVMe as data only.~~

Step 1 below was written before the watchdog finding, when the drive was still
the prime suspect. It no longer reflects what is known — the NVMe has been root
since the rebuild, without resets.

1. ~~**Do not** put the NVMe back in the M.2 slot, and do not make it root again.~~
   **Superseded:** the NVMe is now root in the M.2 slot and stable.
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
- **Journald persistence** — applied on the rebuilt NVMe install 2026-09-03.
  Without it the next incident is undiagnosable again:

```bash
sudo mkdir -p /var/log/journal
sudo sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

- **⚠️ Do NOT re-apply the watchdog.** An earlier revision of this document told
  you to set `RuntimeWatchdogSec=60s` here. That instruction has been removed
  because it is the prime suspect for the reset loop — the SoC watchdog's timeout
  is fixed at 10 s and cannot be raised, so a 60 s configuration guarantees it
  fires. See "Best current theory (revised)". `RuntimeWatchdogUSec=0` is the
  correct state; verify with `systemctl show -p RuntimeWatchdogUSec`.

- **~~Back up `.storage/auth`.~~ Fixed 2026-09-03 — `scripts/backup-smart-home.sh`.**
  There was no backup script; the lost archive was assembled by hand. The new
  script exists mainly to not repeat the two mistakes that made this incident
  expensive:

  - It reads the Home Assistant config **through sudo**. `.storage/auth` is mode
    600 and owned by root because the container writes it, so a backup running as
    `orangepi` silently skips it — the most likely explanation for the omission,
    since no error is raised.
  - It **verifies the finished archive against a manifest of required members**
    and exits non-zero if any is absent, then separately confirms the Zigbee
    `network_key` is really present. Parsing the files you did capture cannot
    detect a file you never captured, which is exactly how the gap passed review.

  Run it from the workstation: `scripts/backup-smart-home.sh`. sudo prompts on
  your terminal; use `--askpass PATH` for an unattended/cron run. The archive is
  written mode 600 and holds the network key, tokens and camera credentials.

  Verified by running the new manifest check against the old archive, where it
  correctly reports `MISSING homeassistant-config/.storage/auth`.

  **The old `nvme-recovery-2026-09-03.tgz` is still missing auth** — it cannot be
  repaired retroactively. `smart-home-backup-20260903-070721.tgz` supersedes it
  and does contain a working long-lived token.

- **Ecobee remote sensors were fixed in code, not just in HA.** The two remote
  sensors stopped appearing on the dashboard because an entity-registry *name
  override* replaced their HomeKit names ("Family room Temperature") with the
  generic device name, and the dashboard matched remote sensors by room keyword
  in the friendly name — so both were silently dropped while the built-in, which
  is matched by entity-id prefix, kept working. The override is present in the
  backup archive too, so it predates the rebuild.

  `_ecobee_sensors_from_ha_states()` now matches structurally: HA's template API
  returns every sensor whose device is linked to the thermostat by `via_device`,
  and naming plays no part in whether a sensor is included. It falls back to the
  old keyword matching when the registry lookup is unavailable. Verified by
  re-applying the bad override and confirming the sensors still resolve.

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
