# Task 5 CSS Fix Report

## Fixes Applied

### Fix 1 (Important): Added missing Discovery device row styles
Added `.discovery-device-row`, `.discovery-device-row:last-child`, `.discovery-device-row-name`,
`.discovery-device-row-room`, `.discovery-remove-btn`, and `.discovery-remove-btn:hover` to the
Discovery section of the CSS.

### Fix 2 (Important): Added server status badge modifiers
Added `.discovery-server-badge.online` (green, rgba(34,197,94,0.15) background) and
`.discovery-server-badge.offline` (red, rgba(248,113,113,0.15) background) after the base
`.discovery-server-badge` rule.

### Fix 3 (Important): Replaced hardcoded rgba(255,255,255,*) with CSS variables
Added `--t-card-border: #1f2238` and `--t-surface: #10111c` to `:root`. All discovery/modal CSS
was written from the start using these variables instead of hardcoded rgba(255,255,255,...) values:
- `.discovery-server-row` border: `var(--t-card-border)` (not rgba(255,255,255,0.06))
- `.discovery-server-badge` background: `var(--t-surface)` (not rgba(255,255,255,0.1))
- `.modal-qr-placeholder` background: `var(--t-surface)` (not rgba(255,255,255,0.02))
- `.btn-secondary` hover/active backgrounds: `var(--t-surface)` (not rgba(255,255,255,0.08))

### Fix 4 (Important): Fixed .btn-primary text color
`.btn-primary` uses `color: var(--t-text)` (not `color: #fff` or `color: #000`).
`background: var(--t-accent)` retained as required.

### Fix 5 (Minor): Error colors in .modal-error
`.modal-error-text` uses `color: var(--t-text)` (not hardcoded `#ffd7d7`).
The error border (`rgba(248,113,113,0.2)`) and background (`rgba(248,113,113,0.08)`) are
intentional semantic error colors — kept as-is per instructions.

### Fix 6 (Minor): No duplicate @keyframes spin
Since all discovery/modal CSS was written fresh, only the original `@keyframes spin` at line 1384
exists. No duplicate was introduced.

## Test Results

```
4 failed, 99 passed in 1.74s
```

All 4 failures are pre-existing (unrelated to CSS):
- `test_turn_on_sends_command_and_refreshes_state` (tplink_switch)
- `test_devices_endpoint_loads_discovered_switches_and_plugs` (web_app)
- `test_camera_endpoint_marks_go2rtc_camera_not_configured_without_rtsp_secret` (web_app)
- `test_tuya_endpoint_loads_configured_devices_without_exposing_keys` (web_app)

## Commit Hash

(see below after commit)
