# C. Deploy and code quality

## C1 Deploy everything a commit changes
☑ 2026-09-25 · Claude · M

**Done 2026-09-25.** `scripts/deploy.py` and the tracked hook `scripts/git-hooks/post-commit`.
Two things the first live run taught: the guard now accepts a board file that matches *any*
earlier version in git (stale, never deployed - `deploy-dashboard.sh` on the board was the
09-12 version), refusing only content the repo never had; and the board records the last
commit it received (`.deployed_commit`), so a refused or failed deploy is caught up by the
next commit rather than leaving a hole. Build-metadata commits are not counted as changes.
Verified live: the catch-up deploy of `00fdd79` + `85d09f0` (stale file noted and updated,
backup kept, nothing restarted), `--rollback --dry-run`, and dry-runs of the detector and
night-watch commits (restart exactly `npu-detector` / `night-watch`).

**Why.** The post-commit hook deploys only when dashboard files change. On
2026-09-25 the detector, the installers, the night watch and its unit were all
copied and restarted by hand — each time checking the board's copy first so as
not to overwrite anything. That does not scale and will one day be forgotten.

**Do.** `scripts/deploy.sh`: sync `src/python/`, `scripts/` and
`deploy/systemd/user/`; install changed unit files and `daemon-reload`; restart
only the services whose code changed (a table of file -> unit); refuse when the
board has local edits the repo does not (show them); keep the last N builds for a
rollback. The post-commit hook calls it for any change under those paths.

**Done when.** A commit touching `npu_detector.py` restarts the detector and
nothing else; a commit touching a unit file installs it; a board-side edit stops
the deploy with a diff.

## C2 A green test suite
☑ 2026-09-25 · Claude · M

**Done 2026-09-25: 2,999 passed, 4 skipped, 0 failed.** What each failure was:
- 3 camera-grid tests: stale fakes - `cameraCardHasRoomForGrid` reads `classList` since the
  approach-camera slots (14eb7c0, 09-23). Fakes updated; a test for hidden vs showing slots added.
- `inset` without longhands on `.environment-air-orb::after` (6dde319, 09-21): **a real
  regression** for Safari before 14.5 - longhands added.
- The refresh fallback: the Node sandbox lacked `AbortController` (added to
  `refreshDashboardSource` in 57136b5, 09-23), and the load-time refresh stayed in flight. The
  fallback itself works.
- The watchdog-guidance check: one Windows-1252 byte in `handoff-2026-09-20-dashboard-zigbee.md`.
- 3 motion-gate tests: OpenCV missing on the workstation. Now `importorskip`, and
  `requirements-dev.txt` (jinja2, Pillow, opencv-python-headless) for the workstation and the
  Docker dev image. The dev image was not rebuilt here; C3's CI run is the clean-machine check.

**Why.** 9 tests have failed since before 2026-09-25, so a new failure hides among
them and CI would always be red.

- 3 `test_npu_detector.py` motion-gate tests: OpenCV is missing on the workstation
  (install it in the dev environment, or skip them cleanly without it).
- 3 `test_home_camera_grid.py`, 1 `test_legacy_browser_fallbacks.py`
  (`inset` without longhands), 1 `test_command_refresh_scope.py`: real regressions
  or stale tests — each decided on its own.
- 1 `test_watchdog_guidance.py`: a handoff recommends enabling the watchdog.

**Done when.** `python3 -m pytest` passes on the workstation and in the Docker
dev container.

## C3 CI on GitHub
☐ · Claude · S

**Do.** A GitHub Actions workflow: Python tests and `node --check` on every push
and pull request; the C++ build later. The deploy (C1) refuses to run when the
commit's CI is red, unless forced.

**Done when.** A push shows a green check on GitHub.

## C4 Drift check and board-only config
☐ · Claude · M

**Why.** Much of the house lives only on the board: z2m device options (the IKEA
debounce), `.env` settings (the detector's classes, zones, gate; the Telegram
chat id), `devices.local.yaml` (the PIN), Home Assistant helpers and automations
installed by a dozen scripts — and any edit in the Home Assistant UI silently
diverges from them.

**Do.** `scripts/install-all.py --check`: every installer reports what differs
between its desired state and Home Assistant's; the non-secret board settings move
into versioned files (`configs/zigbee-device-options.yaml`, a documented
`.env.example`); the watchdog runs the check nightly.

**Done when.** Editing an automation in the Home Assistant UI shows up on the
Status view the next morning.
