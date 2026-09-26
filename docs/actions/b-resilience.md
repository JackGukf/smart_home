# B. Resilience

## B1 Automatic off-site backups
☑ 2026-09-26 · both · M

**Done 2026-09-26** - see `docs/offsite-backup.md`. Nightly at 02:40 to Backblaze B2 (Google
Drive was tried: rclone's shared Google app is being retired, and an own app stalled on
Google's Branding page), encrypted on the board with restic, 14 daily / 8 weekly / 12 monthly.
Unattended without sudo (Home Assistant's config through `docker cp`). The heartbeat fails
after 36 h without a success. Restore tested byte-identical. The passphrase is in the owner's
password manager and the board's `.env`. Previous backup before this: 2026-09-08.
Still to do: a quarterly restore drill against `docs/restore-runbook.md`.

**Why.** `scripts/backup-smart-home.sh` runs only when someone runs it. The
Zigbee network key and the Matter fabric cannot be recreated; losing the NVMe
means re-pairing every device.

**Do.** A nightly timer on the board runs the backup (already verified against a
manifest), encrypts it (restic or age) and sends it off the board (a cloud bucket
or another machine), keeping 30 days. A quarterly restore drill against
`docs/restore-runbook.md`.

**Done when.** A backup newer than a day exists off the board, its restore is
tested once, and a failed backup alerts (through A1 or the watchdog).

**Owner.** Where it goes, and the key.

## B2 Pinned image versions
☐ · Claude · S

**Why.** Home Assistant runs `ghcr.io/home-assistant/home-assistant:stable`, so any
pull is an unplanned major upgrade. The same for zigbee2mqtt and mosquitto.

**Do.** Record the running versions, pin them in the install scripts, and write
the upgrade procedure (pause the watchdog, back up, upgrade one, verify).

**Done when.** `docker ps` versions match the repo, and an upgrade is a
deliberate one-line change.

## B3 Memory safety
☐ · Claude · S

**Why.** No swap, the NPU driver holds 4 GB from boot, and the cast, Ollama,
Home Assistant and the detector share the rest. Only some units are capped.

**Do.** zram swap (2-4 GB, lz4); `MemoryMax=` on the dashboard, cast and house
memory units; `OOMScoreAdjust` so the kernel picks the cast or Ollama before Home
Assistant or mosquitto.

**Done when.** Every long-running user unit has a cap (a test asserts it) and
zram survives a reboot.

## B4 Watchdog for the new services
☐ · Claude · S

**Why.** `service_watchdog.py` does not know about the night watch, and does not
check that the alert automations are enabled — a disabled rule is silent.

**Do.** Checks for `night-watch` (process up, MQTT connected, a heartbeat file),
the leak / smoke / door / intruder automations being `on`, and each camera's NPU
stream being available.

**Done when.** Stopping night-watch or disabling a safety automation shows on the
dashboard's Status view within 4 minutes.

## B5 UPS, Zigbee routers, DHCP reservations
☐ · Owner · S each

- **UPS** (DC or small line-interactive) and a NUT client: a power cut must not
  corrupt Home Assistant's database on the NVMe.
- **Two or three mains-powered Zigbee routers** (e.g. IKEA plugs) near the far
  sensors: the network is a pure star with marginal links.
- **DHCP reservations** on the router for the board (`192.168.0.83`, hardcoded
  everywhere) and the wall panel (`192.168.0.176`, which is a credential).
