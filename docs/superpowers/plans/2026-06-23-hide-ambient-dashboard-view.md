# Hide Ambient Dashboard View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide Ambient Light from the dashboard without deleting its backend, configuration, styles, or control implementation.

**Architecture:** Remove the Ambient sidebar entry and content panel from static HTML. Remove the Ambient API request and render call from the normal dashboard refresh path, while retaining the API routes and dormant frontend helper functions for later restoration.

**Tech Stack:** Static HTML, vanilla JavaScript, pytest, FastAPI.

---

### Task 1: Retire Ambient from the visible dashboard

**Files:**
- Modify: `tests/python/test_dashboard_layout.py`
- Modify: `src/python/web_static/index.html`
- Modify: `src/python/web_static/app.js`

- [ ] Change the layout test to assert that Ambient navigation and panel markup are absent while `/api/ambient-lights` remains implemented in `src/python/web_app.py`.
- [ ] Run `python3 -m pytest tests/python/test_dashboard_layout.py -q` and confirm the new test fails because Ambient is still visible.
- [ ] Remove the `data-view="ambient"` sidebar item and `data-view-panel="ambient"` panel from `index.html`.
- [ ] Remove Ambient from the `Promise.all` refresh request, destructuring, and `renderAmbientLights` call in `loadDevices()`.
- [ ] Bump the frontend asset version in `index.html` so browsers receive the updated UI.
- [ ] Run layout/frontend tests, JavaScript syntax validation, and verify `/api/ambient-lights` still responds after deployment.