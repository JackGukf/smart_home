# Action list

From the architecture / design / implementation review of 2026-09-25 and what the
work that day turned up. Worked **one item at a time, in the order below**; tick
an item here and in its file when it is done, with the date and commit.

Legend: ☐ open · ◐ partly done · ☑ done — **Owner**: *Claude* (in the repo and on
the board), *Owner* (needs a person: hardware, accounts, a phone, a decision), or both.
**Size**: S under an hour, M a session, L several sessions.

## Order

| # | Item | Owner | Size | Status |
|---|---|---|---|---|
| 1 | [A1 External heartbeat](a-safety-security.md#a1-external-heartbeat) | both | S | ☑ 2026-09-25 |
| 2 | [C1 Deploy everything a commit changes](c-deploy-quality.md#c1-deploy-everything-a-commit-changes) | Claude | M | ☑ 2026-09-25 |
| 3 | [C2 A green test suite](c-deploy-quality.md#c2-a-green-test-suite) | Claude | M | ☑ 2026-09-25 (clean-machine run: C3) |
| 4 | [C3 CI on GitHub](c-deploy-quality.md#c3-ci-on-github) | Claude | S | ☑ 2026-09-25 |
| 5 | [A2 Intrusion: critical push and escalation](a-safety-security.md#a2-intrusion-critical-push-and-escalation) | Claude | S | ◐ installed; live test pending |
| 6 | [B1 Automatic off-site backups](b-resilience.md#b1-automatic-off-site-backups) | both | M | ☑ 2026-09-26 |
| 7 | [B4 Watchdog for the new services](b-resilience.md#b4-watchdog-for-the-new-services) | Claude | S | ☐ |
| 8 | [A4 The stairs sensor](a-safety-security.md#a4-the-stairs-sensor) | both | S | ☐ |
| 9 | [A5 Freeze and furnace-failure alert](a-safety-security.md#a5-freeze-and-furnace-failure-alert) | Claude | S | ☐ |
| 10 | [B2 Pinned image versions](b-resilience.md#b2-pinned-image-versions) | Claude | S | ☐ |
| 11 | [B3 Memory safety](b-resilience.md#b3-memory-safety) | Claude | S | ☐ |
| 12 | [C4 Drift check and board-only config](c-deploy-quality.md#c4-drift-check-and-board-only-config) | Claude | M | ☐ |
| 13 | [A3 An alarm the house owns](a-safety-security.md#a3-an-alarm-the-house-owns) | both | L | ☐ |
| 14 | [D6 House memory retention, narrower tokens](d-design.md#d6-house-memory-retention-narrower-tokens) | Claude | S | ☐ |
| 15 | [D3 MQTT contract](d-design.md#d3-mqtt-contract) | Claude | M | ☐ |
| 16 | [D1 Split web_app.py](d-design.md#d1-split-web_apppy) | Claude | L | ☐ |
| 17 | [D2 Split app.js](d-design.md#d2-split-appjs) | Claude | L | ☐ |
| 18 | [D5 HTTPS and a wall-panel device token](d-design.md#d5-https-and-a-wall-panel-device-token) | both | M | ☐ |
| 19 | [D4 An honest architecture.md](d-design.md#d4-an-honest-architecturemd) | Claude | S | ☐ |
| 20 | [E3 Clips on the dashboard](e-features.md#e3-clips-on-the-dashboard) | Claude | M | ☐ |
| 21 | [E2 Guest / cleaner mode](e-features.md#e2-guest--cleaner-mode) | Claude | S | ☐ |
| 22 | [E1 Per-person presence and users](e-features.md#e1-per-person-presence-and-users) | both | M | ☐ |
| 23 | [E4 Energy that acts](e-features.md#e4-energy-that-acts) | Claude | M | ☐ |
| 24 | [E5 Air quality actions](e-features.md#e5-air-quality-actions) | Claude | S | ☐ |

Owner-only items, done whenever convenient: ~~[A6 SSH hardening](a-safety-security.md#a6-ssh-hardening)~~ ☑ 2026-09-25,
[B5 UPS, Zigbee routers, DHCP reservations](b-resilience.md#b5-ups-zigbee-routers-dhcp-reservations),
[E6 Locks](e-features.md#e6-locks).

Dated follow-ups and questions for the owner: [f-follow-ups.md](f-follow-ups.md).

## Done 2026-09-25

| Review item | What | Commit |
|---|---|---|
| §2.1 | `/bridge/*` answers loopback only | `3e3b36a` |
| §2.2 | Random session key, constant-time check, login lockout, audit log | `3e3b36a` |
| §2.2 | Disarm PIN on the dashboard (and its misconfiguration message) | `3e0ffea`, `eecc621` |
| §2.3 | `orangepi` and root passwords changed (owner); documented | `52001b4` |
| §3.1 | Leak and smoke alerts, battery / not-reporting check | `3e7f8d4`, `d51454b` |
| §3.3 | Critical iPhone push for smoke and leaks | `3e7f8d4` |
| §3.4 (part) | Night clips and Telegram photos | `32412dd` |
| presence | Phone location *Always* (owner); garage camera leaving / arriving, watch-only | `e2b48ec`, `7903b8f` |
| cameras | Office camera motion gate; cars on the garage camera only | `32412dd`, `7903b8f` |
| A1 | External heartbeat: healthchecks.io every 5 min, `/fail` when the watchdog gives up; Telegram DOWN/UP tested | `f452e24` |
| A6 | SSH: `PermitRootLogin no`, `PasswordAuthentication no` (owner) | - |
| B1 | Nightly encrypted backup to Backblaze B2 (02:40; 14/8/12 kept); no sudo needed; heartbeat pages after 36 h; restore tested byte-identical | this commit |
| C3 | CI on every push (Python 3.12, Vancouver time, Node); failures as annotations; the deploy runs the related tests first. First run found a real bug: no switch rescan in the first 5 min after boot | `727c96a`, `f1a4819`, this commit |
| C2 | Green suite (2,999 passed): stale camera-grid and refresh harnesses fixed, `inset` fallback added (real regression, old iPad Safari), a Windows byte in a handoff, OpenCV tests guarded + `requirements-dev.txt` | this commit |
| C1 | Every commit deploys itself: changed files, unit files, only the services that use them; stale vs edited guard, catch-up, rollback; go2rtc no longer restarted by every dashboard deploy | `00fdd79`, `85d09f0` |
