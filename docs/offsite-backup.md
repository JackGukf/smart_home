# Nightly off-site backup (Backblaze B2, encrypted)

Since 2026-09-26 (action list B1). Before this, `scripts/backup-smart-home.sh` ran
only by hand from the workstation - the last archive was from 2026-09-08.

## What runs

`offsite-backup.timer` (02:40, `Persistent=true`) starts `scripts/offsite-backup.sh`:

1. `scripts/backup-smart-home.sh --local` builds the verified archive on the board
   (the required-members manifest still applies). Unattended there is nobody to
   type a sudo password, so Home Assistant's config - `.storage/auth` is root-only -
   comes out through `docker cp homeassistant:/config`; the Matter fabric in
   `/var/lib/matter` belongs to the login user. Three archives stay in `~/backups/`.
2. **restic** backs up the unpacked archive to **Backblaze B2**
   (`RESTIC_REPOSITORY=b2:<bucket>:smart-home`): encrypted on the board before it
   leaves (B2 sees only restic's packs) and deduplicated, so a night uploads what
   changed. First backup 2026-09-26: 161 MiB of files, 37 MiB stored, 21 s.
3. Keeps **14 daily, 8 weekly, 12 monthly** snapshots; prunes on Sundays.
4. Writes `~/backups/offsite-status.json`. **The heartbeat fails its ping when the
   last success is over 36 h old**, so two missed nights reach the owner through
   healthchecks.io's Telegram bot (one missed night shows as a warning in the ping).

Tools: restic 0.19.1 (and rclone 1.75.1, unused for B2) in `~/.local/bin`, pinned
and checksum-verified by `scripts/install-offsite-backup.sh` (no sudo).

**Why B2 and not Google Drive:** Drive needs a Google OAuth app; rclone's shared
one "is being retired and will stop working during 2026", and publishing an own
app stalled on Google's Branding page. B2 is free to 10 GB, needs no card, and a
key limited to one bucket cannot expire.

## One-time setup

1. `scripts/install-offsite-backup.sh` on the board: the tools and the timer.
2. **Backblaze B2:** a private bucket with lifecycle "Keep only the last version",
   and an application key limited to that bucket (read and write). In the board's
   `.env`: `B2_ACCOUNT_ID`, `B2_ACCOUNT_KEY`, `RESTIC_REPOSITORY=b2:<bucket>:smart-home`.
3. **Passphrase:** `RESTIC_PASSWORD` (40 random characters) in the board's `.env`,
   then `restic init`. **Keep the passphrase in a password
   manager too**: without it the backups cannot be restored, and the only other
   copy is on the board the backup exists to replace.

## Restore from Drive

On any machine with restic, with the B2 key (Backblaze -> Application Keys; make a
new one if the board is gone) and the passphrase from the password manager:

```bash
export B2_ACCOUNT_ID='<keyID>' B2_ACCOUNT_KEY='<applicationKey>'
export RESTIC_REPOSITORY='b2:<bucket>:smart-home' RESTIC_PASSWORD='<passphrase>'
restic snapshots
restic restore latest --target ./restored
```

Tested 2026-09-26: 1,363 files restored; `.storage/auth`, the Zigbee
`coordinator_backup.json` and `.env` byte-identical to the live copies.

`./restored/tmp/tmp.*/` then holds the same tree as a `smart-home-backup-*.tgz`;
continue with `docs/restore-runbook.md` step 1.2.

## Check it

```bash
cat ~/backups/offsite-status.json
systemctl --user list-timers offsite-backup.timer
journalctl --user -u offsite-backup -n 30 --no-pager
```
