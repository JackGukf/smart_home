# Nightly off-site backup (Google Drive, encrypted)

Since 2026-09-26 (action list B1). Before this, `scripts/backup-smart-home.sh` ran
only by hand from the workstation - the last archive was from 2026-09-08.

## What runs

`offsite-backup.timer` (02:40, `Persistent=true`) starts `scripts/offsite-backup.sh`:

1. `scripts/backup-smart-home.sh --local` builds the verified archive on the board
   (the required-members manifest still applies). Unattended there is nobody to
   type a sudo password, so Home Assistant's config - `.storage/auth` is root-only -
   comes out through `docker cp homeassistant:/config`; the Matter fabric in
   `/var/lib/matter` belongs to the login user. Three archives stay in `~/backups/`.
2. **restic** backs up the unpacked archive to `rclone:gdrive:smart-home-backup`:
   encrypted on the board before it leaves (Google sees only restic's packs) and
   deduplicated, so a night uploads what changed.
3. Keeps **14 daily, 8 weekly, 12 monthly** snapshots; prunes on Sundays.
4. Writes `~/backups/offsite-status.json`. **The heartbeat fails its ping when the
   last success is over 36 h old**, so two missed nights reach the owner through
   healthchecks.io's Telegram bot (one missed night shows as a warning in the ping).

Tools: restic 0.19.1 and rclone 1.75.1 in `~/.local/bin`, pinned and
checksum-verified by `scripts/install-offsite-backup.sh` (no sudo).

## One-time setup

1. `scripts/install-offsite-backup.sh` on the board: the tools and the timer.
2. **Google Drive** (needs a browser, once): rclone's `drive.file` scope - it sees
   only the files it created, not the rest of the Drive. `rclone authorize "drive"`
   on a machine with a browser gives a token; on the board
   `rclone config create gdrive drive scope=drive.file token='<token>'`.
3. **Passphrase:** `RESTIC_PASSWORD` and `RESTIC_REPOSITORY=rclone:gdrive:smart-home-backup`
   in the board's `.env`, then `restic init`. **Keep the passphrase in a password
   manager too**: without it the backups cannot be restored, and the only other
   copy is on the board the backup exists to replace.

## Restore from Drive

On any machine with restic and rclone (the `gdrive` remote set up as above):

```bash
export RESTIC_REPOSITORY=rclone:gdrive:smart-home-backup RESTIC_PASSWORD='<from the password manager>'
restic snapshots
restic restore latest --target ./restored
```

`./restored/tmp/tmp.*/` then holds the same tree as a `smart-home-backup-*.tgz`;
continue with `docs/restore-runbook.md` step 1.2.

## Check it

```bash
cat ~/backups/offsite-status.json
systemctl --user list-timers offsite-backup.timer
journalctl --user -u offsite-backup -n 30 --no-pager
```
