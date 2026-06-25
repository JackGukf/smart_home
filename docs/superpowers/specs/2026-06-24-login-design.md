# Dashboard Login — Design Spec
**Date:** 2026-06-24  
**Status:** Approved

## Overview

Add a single-user username/password login to the HomeOS dashboard. All dashboard routes are gated behind a session cookie. No HTTPS requirement — this runs on a trusted local network.

## Credentials Storage

Add a `dashboard_auth` section to `configs/devices.local.yaml` (already git-ignored):

```yaml
dashboard_auth:
  username: admin
  password: admin
```

Also add the section to `configs/devices.example.yaml` with placeholder values to document the schema.

If `dashboard_auth` is absent from the config, the app starts **without authentication** — preserving the current behavior for dev/testing environments.

## Backend Changes (`src/python/web_app.py`)

### Secret key
Derived at startup by hashing the configured password with a fixed salt using `hashlib.sha256`. No extra config field required.

### New routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/login` | Serve `login.html` |
| POST | `/login` | Verify credentials; set cookie and redirect to `/` on success; redirect to `/login?error=1` on failure |
| POST | `/logout` | Clear session cookie; redirect to `/login` |

### Middleware
A Starlette middleware runs before every request:

- **Skipped paths:** `/login`, `/logout`, `/static/*`
- **Valid cookie:** request passes through unchanged
- **Missing/invalid/expired cookie:**
  - `Accept: text/html` requests → redirect to `/login`
  - `/api/*` requests → return `{"error": "unauthorized"}` with HTTP 401

### Session cookie
- Signed with `itsdangerous.URLSafeTimedSerializer` (transitive FastAPI dependency — no new packages needed)
- Cookie name: `session`
- Max age: 30 days
- `HttpOnly: true`, `SameSite: Lax`
- Logout clears the cookie client-side (no server-side session store needed)

## Frontend: Login Page (`src/python/web_static/login.html`)

A standalone HTML file (not the main SPA) with:
- Same Inter font and CSS variables as `styles.css`
- Dark background, centered card layout
- HomeOS logo icon + "Sign in" heading
- Username input, password input, "Sign in" button
- Error message shown when `?error=1` appears in the URL: *"Invalid username or password"*
- No "remember me" toggle — 30-day sessions always on

## What Doesn't Change

- All existing device routes, WebSocket, weather endpoint, camera streams — only gated, not modified
- `/static/*` assets remain public (no sensitive data in JS/CSS)
- `devices.local.yaml` config loading logic is unchanged except for reading the new `dashboard_auth` key

## Non-Goals

- HTTPS (deferred)
- Multiple users / user database
- Password hashing at rest (plain text in a git-ignored local file is acceptable for this use case)
- Session revocation on server restart (in-memory sessions; logout clears cookie client-side)
