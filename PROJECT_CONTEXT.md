# Smart Home AI — Project Context and Future-Work Handoff

> Start every future task by reading this file, then inspect the referenced files before changing code or deployment state.

## Canonical workspace

- **Current project path:** `/home/jackgu/workspace/smart_home_AI`
- **Former project path/name:** `smart-home-rpi4`; it was migrated here on 2026-07-29 with its Git history and working tree intact.
- **Purpose:** a locally hosted smart-home control and monitoring system, with a FastAPI dashboard, Python device adapters, optional C++ services, Home Assistant and Matter integrations, and Orange Pi 6 Plus-oriented deployment tooling.
- **Repository branch:** `main`, tracking `origin/main`.

As of 2026-07-29 the in-repo naming has been reconciled: documentation, Docker configuration, scripts, systemd units, and deploy defaults now use `smart_home_AI` and target the Orange Pi 6 Plus. The one place the legacy name is retained deliberately is the **secondary** Raspberry Pi 4 target, whose remote path stays `/home/smarthome/smart-home-rpi4` so the existing install is not broken. Nothing was renamed on the Pi remotely.

## Current local state — preserve before work

As of 2026-08-29 the working tree is clean except for one deliberate exception:

- Untracked: `third_party/connectedhomeip` (the Matter/CHIP SDK checkout — large, treat as a dependency, never commit)

The C++ Matter bridge changes previously listed here have since been committed. Do not reset, discard, commit, or deploy anything you did not change. Never commit credentials, access tokens, camera URLs, Wi-Fi details, or device IDs.

**`BUILD_COUNT`, `web_static/build_info.json`, and `web_static/index.html` will appear modified after almost any dashboard work.** A `post-commit` hook in `.git/hooks/` auto-deploys whenever a commit touches `src/python/web_static/` or `src/python/web_app.py`, and the deploy script rewrites those three files. Committing them re-triggers the hook, so commit them with hooks bypassed:

```bash
git -c core.hooksPath=/dev/null commit -a -m "chore: record dashboard build cache-busting metadata"
```

## What has been built

### Dashboard and device control

- FastAPI dashboard entry point: `src/python/web_app.py`.
- Static dashboard assets: `src/python/web_static/`.
- Device control and discovery modules cover TP-Link/Kasa, Tuya, cameras, Govee BLE/LAN/cloud devices, and Home Assistant entities.
- The dashboard includes login/logout support, weather/forecast and thermostat information, camera-first startup support, mobile layout refinements, ambient lights, humidifiers, environment sensors, and device views.
- The most recent dashboard work replaced the fixed device-group sidebar with an overview-led experience while retaining the underlying user-managed device-group engine and CRUD UI.

### Home Assistant integration

- A known-entity registry detects newly seen Home Assistant light/switch entities.
- New devices can be confirmed, ignored, categorized, and merged into dashboard views.
- Home area assignments and device placement are supported.
- The integration degrades gracefully when Home Assistant is unavailable; preserve that behavior in future changes.

### Matter integration and bridge

- A Python Matter Server integration exposes devices to the dashboard and supports commissioning.
- A native C++ Matter bridge maps dashboard devices into Matter endpoints.
- The bridge includes device mapping, bridge synchronization, endpoint registration, state updates, commissioning support, and regression tests.
- `third_party/connectedhomeip` is required for Matter bridge work. Its checkout is large and should be handled as a submodule/dependency, not edited casually.
- Docker deployment for the Matter bridge was retired in favor of the current native/service deployment approach; verify current deployment documentation before reintroducing containers.

### Device-specific findings retained in the history

- TP-Link credential errors are surfaced; Tapo devices are excluded from TP-Link discovery to avoid duplicate cards.
- Govee supports BLE, LAN where supported, and Cloud API v2 for humidifier/capability workflows.
- Lepro BLE was investigated and is display-only until a supported Alexa routine or bridge command path exists.
- Battery cameras use one-shot snapshots; doorbell cameras should not be background-polled.

## Browser support baseline

**The dashboard must run on Safari 12.1 (iOS 12.5).** An iPad mini on that version is a live client. This constrains the front end in three separate ways, and they fail differently:

| Layer | Failure mode | What to do |
| --- | --- | --- |
| **JS syntax** | Parse error — the *whole file* dies, nothing runs | Handled automatically: `scripts/build-dashboard-assets.sh` compiles `app.js` to ES2019 at deploy time. Write modern JS freely in the source. |
| **JS APIs** | `TypeError` at the call site — only that feature breaks, silently | **Not** handled by the build. Polyfill or guard by hand. |
| **CSS** | Silently ignored — the page still runs but looks wrong | Fallback first, modern property after; or a capability class. |

Rules that follow from this:

- **Inline `<script>` in `index.html` is never compiled** — only `app.js` goes through esbuild. Inline script must already be ES5. A test enforces it.
- **Compiling handles syntax, never APIs.** `Promise.allSettled` (Safari 13) shipped unguarded for weeks because the file parsed fine and only the calling feature broke. `tests/python/test_legacy_api_support.py` holds a list of APIs newer than the baseline; add to it rather than discovering the next one from a bug report.
- **Unsupported below the baseline, with fallbacks already in place:** `aspect-ratio` (Safari 15), `inset` shorthand (14.1), flex `gap` (14.1), Pointer Events (13), `ResizeObserver` (13.1), container queries and `cqh` units (16), `min()`/`max()`/`clamp()` (13.1), `dvh` units (15.4), element Fullscreen API (unreliable on iOS at any version).
- **A feature existing is not the same as it working.** `webkitRequestFullscreen` is defined on the iPad mini but `webkitFullscreenEnabled` is false; the call does nothing and throws nothing. Check the capability flag, not the method.
- Layout that depends on `aspect-ratio` must not be the *only* source of an element's height, or its `height: 100%` children collapse to nothing and the result is an invisible-but-present element.

The target lives in one place — `ES_TARGET` in `scripts/build-dashboard-assets.sh`, with the reason beside it. Raising it is a product decision about which devices stop working.

## Architecture and key locations

```text
Dashboard browser
  -> FastAPI app (src/python/web_app.py)
  -> Python integrations and config loaders (src/python/)
  -> Vendor APIs / Home Assistant / Matter Server / local devices

Dashboard-managed devices
  -> Python bridge sync API
  -> C++ Matter bridge (src/cpp/matter_bridge/)
  -> Matter controller ecosystems
```

| Area | Primary locations |
| --- | --- |
| Dashboard API and rendering | `src/python/web_app.py`, `src/python/web_static/` |
| Python dependencies | `src/python/requirements.txt`, `pyproject.toml` |
| Dashboard tests | `tests/python/` |
| C++ Matter bridge | `src/cpp/matter_bridge/`, `tests/cpp/matter_bridge/` |
| Device/deployment utilities | `scripts/` |
| Dashboard asset build (ES2019) | `scripts/build-dashboard-assets.sh` |
| systemd definitions | `deploy/systemd/` |
| Architecture/setup docs | `docs/architecture.md`, `docs/setup-orangepi6.md`, `docs/orangepi6-cross-compile-deploy.md`, `docs/docker-development.md`, `docs/WSL_DEVELOPMENT.md`, `docs/matter-bridge.md` |
| Local configuration examples | `.env.example`, configuration examples; keep actual values ignored |

## Development and verification

Read the current script or document before running it. Workspace paths now use the canonical `smart_home_AI` path throughout, including the Docker/devcontainer mount at `/workspace/smart_home_AI` and the MCP server path in `.mcp.json`.

Typical local dashboard run:

```bash
python3 -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000
```

Typical container-based checks documented by the project:

```bash
docker compose build dev
docker compose run --rm dev python3 -m pytest
docker compose run --rm dev sh -lc "cmake --preset docker-debug && cmake --build --preset docker-debug && ctest --test-dir build/docker-debug --output-on-failure"
```

Before changing dashboard behavior, run the focused Python tests first, then the full relevant suite (508 tests as of 2026-08-29).

Many front-end tests assert on the *text* of `app.js`, `index.html`, and `styles.css`, because there is no browser in the suite. That catches structural regressions but cannot tell you a page looks right or a gesture works, and such a test can silently assert nothing at all if its pattern stops matching. **When adding one, revert the fix and confirm the test fails**, then restore it. Two tests written during the 2026-08-29 work passed against the broken code until that check was run. Before changing the Matter bridge, verify both C++ tests and bridge deployment/commissioning behavior; the bridge has a history of subtle state-cache, attribute, subscription, and commissioning fixes.

## Deployment notes

- `scripts/deploy-dashboard.sh` syncs the dashboard, static files, selected scripts, and systemd user services, then restarts `go2rtc.service` and `smart-home-dashboard.service` on the target.
- Deploy scripts now default to `orangepi@192.168.0.234` and `/home/orangepi/smart_home_AI`. Still pass an explicit host/user when in doubt; do not assume a default points at the board you mean. The Raspberry Pi 4 requires explicit `--board rpi4 --host --user --remote-path`.
- `configs/matter-bridge.service` uses `--interface wlp1s0`. Ubuntu's predictable interface names differ from Raspberry Pi OS's `wlan0`; a wrong interface makes Matter commissioning fail quietly. Verify with `ip -o -4 addr show scope global` on the board.
- Deploying increments `BUILD_COUNT` and rewrites static cache-busting versions plus `web_static/build_info.json`. Treat deployment as a source-tree mutation and review the resulting diff. A `post-commit` hook also deploys automatically on any commit touching the dashboard.
- **The deploy ships a compiled `app.js`, not the source.** `scripts/deploy-dashboard.sh` stages `web_static/` through `scripts/build-dashboard-assets.sh`, which compiles to ES2019 and emits a source map, then rsyncs the staging directory. Copying `web_static/` to the board by hand would ship untranspiled source and silently break every older browser. The build needs `npx` on the deploying machine and fails loudly if it is missing.
- Running `uvicorn` locally still serves the untranspiled `app.js`, which keeps the dev loop build-free and is fine on any current browser.
- `tplink_switches.json` is rsynced from the workstation on every dashboard deploy. The board rewrites that file itself when it rediscovers a switch that changed IP, so a deploy can push a stale address back; rediscovery corrects it again within about a minute.
- The Orange Pi 6 Plus is now the primary deployment target as well as the local-AI host: Ubuntu 24.04.4 LTS ARM64, Cix P1/CD8180 with 12 Armv9.2-A cores (Cortex-A720 `0xd81` + Cortex-A520 `0xd80`), system GCC 13.3, NVMe storage, `wlp1s0` at 192.168.0.234 and `enp97s0` at 192.168.0.14. Ollama runs as a system service with `qwen3:4b` and listens only on loopback, which is intentional. Use an SSH tunnel for workstation access unless an authenticated reverse proxy is explicitly designed.
- Because the dev container's aarch64 cross-compiler is GCC 11, `-mcpu=cortex-a720` is unavailable. `cmake/toolchains/orangepi6-aarch64.cmake` probes for the best `-march` the compiler accepts and falls back to a safe baseline; override with `-DORANGEPI6_ARCH_FLAGS=...`.

## Recent history, condensed by workstream

1. **Foundation:** created the C/C++ and Python smart-home controller project with Docker/WSL and Raspberry Pi deployment support.
2. **Dashboard authentication:** designed and implemented configurable login/logout and middleware.
3. **Matter Server:** added Python Matter service installation, client mapping, dashboard APIs, discovery, and commissioning UI.
4. **Matter bridge:** added the CHIP submodule, native C++ bridge, device mapping, synchronization, dynamic endpoints, deployment/commissioning scripts, and a substantial reliability/regression-fix sequence.
5. **Dashboard product work:** added weather, themes, thermostat status, responsive layout, camera-first UX, camera snapshots, and a more scalable device-card experience.
6. **Home Assistant:** added registry persistence, unknown-device detection, confirmation/ignore flow, category and room placement, and resilient dashboard rendering.
7. **Ambient/environment devices:** added Govee and Lepro research/support, ambient controls, humidifiers, environment sensor inventory, and the Devices/Environment UX split.
8. **Device groups:** delivered a user-managed group data model, membership rules/overrides, CRUD and management modals, dynamic mixed-device panels, then moved the group experience out of the fixed sidebar in the latest merge.
9. **Workspace consolidation:** migrated the entire `smart-home-rpi4` project into this `smart_home_AI` path while preserving the prior working tree and standalone Tuya authorization image.
10. **Local AI:** validated a private, CPU-backed Ollama service on the Orange Pi 6 Plus using `qwen3:4b` at roughly 8 tokens/sec under load. This is available for future smart-home assistant features, but actions must remain allow-listed and independently validated.
11. **Board retarget (2026-07-29):** moved the primary deployment target from the Raspberry Pi 4 to the Orange Pi 6 Plus. Added the `orangepi6` toolchain and `docker-orangepi6-release` preset, renamed `scripts/build-rpi4.sh` to `scripts/build-orangepi6.sh` with a `--board rpi4` escape hatch, retargeted deploy/connect scripts and systemd units, and updated `CLAUDE.md`, `README.md`, and the board docs. The Raspberry Pi 4 remains a supported secondary target.

12. **Dashboard performance, device recovery, and older-browser support (2026-08-27 to 2026-08-29, `v0.5.0`–`v0.6.0`):**
    - *Performance.* First paint went from 6.2s to ~3.4s. `_device_cards` polled switches serially, so one switch that had dropped off Wi-Fi added its full 5s timeout to every load; polling is now concurrent with a per-device cap, and `/api/devices` is served from a stale-while-revalidate cache primed at startup. Static assets are gzipped with cache headers: 380KB to 85KB on the wire. `/api/tuya/devices` at ~3.0s is now the ceiling and gates first paint, since the front end still waits on a single `Promise.all`.
    - *Device recovery.* Switches are recorded with their MAC and found again by UDP broadcast after three consecutive failures, so a DHCP lease change no longer looks like a dead device. The MAC comes from the discovery broadcast itself, needing neither `update()` nor cloud credentials — which matters because KLAP devices report no alias without them.
    - *Dashboard.* A Connected card on the Status view lists every directly addressable device by IP or MAC, with a rescan. Home cards may overlap, be hidden and shown, and the layout can be reset. The Home camera plays in place with a full-screen overlay.
    - *Older browsers.* An iPad mini on iOS 12.5 could log in but never render: `app.js` used ES2020 syntax that Safari 12.1 cannot parse. The deploy now compiles to ES2019, and a series of fallbacks followed — see **Browser support baseline** above, which is the durable output of this work and should be read before touching the front end.

## Future-work protocol

1. Read this file and `git status --short --branch`.
2. Confirm whether the task is dashboard-only, device integration, Home Assistant, Matter bridge, deployment, or local AI.
3. Read the closest design/implementation docs and targeted source/tests. For code navigation, use the repository’s `.codegraph` index before broad text search.
4. Preserve existing uncommitted work and keep secrets out of source control and logs.
5. Prefer focused tests; use full tests and deployment checks when the affected boundary requires them.
6. For remote deployment, explicitly confirm host, user, target path, service names, and rollback plan.
7. For AI-assisted automations, treat model output as untrusted input: validate schema, enforce an allow-list, and keep device control deterministic.

## Recommended next milestones

- **Done (2026-08-29):** the dashboard and go2rtc are deployed and exercised against the Orange Pi 6 Plus under systemd user units, verified repeatedly through build 149. The **Matter bridge** has still not been exercised on the new host.
- Reduce `/api/tuya/devices` (~3.0s), now the sole thing gating dashboard first paint. Rendering each section as its data lands, instead of one `Promise.all`, would put real first paint near 0.25s.
- Re-commission the Matter bridge on the new host — new interface (`wlp1s0`) and a fresh KVS mean existing fabrics do not carry over from the Pi 4.
- Document the network/API boundary before exposing Ollama beyond loopback.
- Establish a small, authenticated AI-to-dashboard API with read-only status queries first; add any device action only after policy validation and audit logging exist.
- Consider whether the small tiles inside custom Home cards and the temp-sensor grid should be reorderable on touch. They still use HTML5 drag-and-drop, which iOS Safari does not implement, and a drag handle does not fit a 72px tile — they need a different gesture, such as an explicit arrange mode.
- Self-host the Google Fonts and Tabler icon stylesheets. They are render-blocking requests to external CDNs on an otherwise fully local dashboard.
