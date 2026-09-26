# D. Design

## D1 Split web_app.py
☐ · Claude · L

**Why.** ~8,300 lines and 106 routes in one module: API gateway, vendor drivers,
MQTT, caches, auth and static files. A blocking call anywhere stalls everything,
and every change touches the same file.

**Do.** FastAPI `APIRouter` modules along the lines that already exist (auth,
devices, Home Assistant, alarm and house mode, energy, IR, Matter, AI, cast),
the way `bridge_sync.router` is done; state in a typed context object rather than
`app.state.*`. One router per commit; the tests stay green throughout (needs C2).

**Done when.** `web_app.py` only builds the app and includes routers.

## D2 Split app.js
☐ · Claude · L

**Why.** ~13,800 lines in one script. Native ES modules work on the iPad's
Safari, so no bundler is needed.

**Do.** One module per view plus shared utilities; the cache-busting in
`deploy-dashboard.sh` extended to modules.

**Done when.** `app.js` is an entry point importing views, and every view still
passes `scripts/check-card-overlap.py`.

## D3 MQTT contract
☐ · Claude · M

**Do.** Write down the topics (`smarthome/<domain>/<thing>/<event>`), JSON schemas
with a version field, retained-for-state / not-retained-for-events, and a
last-will availability topic for every service (the detector already has one; the
night watch, the dashboard and the house memory do not). The watchdog then checks
availability instead of probing each service its own way.

**Done when.** `docs/mqtt.md` lists every topic, and every service publishes
availability.

## D4 An honest architecture.md
☐ · Claude · S

`docs/architecture.md` still says "C/C++ for long-running services"; in practice
it is Home Assistant + MQTT + Python services + the C++ Matter bridge.
`src/cpp/controller.cpp`, `main.cpp` and `src/python/controller.py` are stubs.
Rewrite the doc (with a diagram) and remove or mark the stubs.

## D5 HTTPS and a wall-panel device token
☐ · both · M

**Why.** The dashboard is plain HTTP on the LAN; the session cookie cannot be
`secure`; the wall panel is trusted by its IP address, which anything on the LAN
can take.

**Do.** HTTPS (Tailscale certificates, or Caddy with a local CA installed on the
iPad and the panel); a long-lived signed device token for the panel, provisioned
once, replacing `trusted_hosts`; `secure` on the cookie.

**Owner.** Installing a CA or certificate on the devices, if that route.

## D6 House memory retention, narrower tokens
☐ · Claude · S

- `~/house-memory/events.db` keeps every Home Assistant event for ever. Keep raw
  events 180 days, daily summaries for ever, `VACUUM` monthly; the watchdog
  watches its size.
- Every service uses the same long-lived Home Assistant admin token. Give the
  read-only ones (house memory, learning, digest) a separate non-admin user.
