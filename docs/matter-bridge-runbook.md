# Runbook: build the Matter bridge from scratch

**Purpose: hand this file to a fresh session and say "build and commission the
Matter bridge per `docs/matter-bridge-runbook.md`". Everything needed is here.**

Written 2026-09-06 from an end-to-end rebuild that ended with all five bridged
devices working in Apple Home. Every trap listed cost real time on that rebuild.
None of them announce themselves, and several present as a *different* problem
than they are.

Related:
- `docs/matter-bridge.md` — design record: what was built, device-type mapping,
  the original Bugs 1–4, future work. This file is the *procedure*.
- `docs/matter-controller.md` — the opposite direction (third-party Matter
  devices **into** the dashboard). Different fabric, different code, pure Python.

---

## What you are building

A **single Matter node** that presents the dashboard's devices to Apple Home.

```
Apple Home ──Matter/mDNS/IPv6──► chip-bridge-app  (C++, systemd user unit)
                                        │  HTTP localhost:8000
                                        ▼
                                 /bridge/*  (Python, bridge_sync.py)
                                        │
                                 python-kasa / tinytuya / matter-server
```

**The single most important fact about a Matter bridge**, because it explains
every failure mode below:

> A bridge is **one node**. One operational certificate per fabric, one node ID,
> one DAC, one CASE session per controller. Bridged devices are **endpoints**,
> not nodes — they have no keys, no certificates, no node IDs of their own.

Consequences:

- Failures are **all-or-nothing**. "All five devices show No Response" is the
  only shape a bridge fault can take. Never go looking for a per-device cause.
- **No per-device isolation.** Compromise the bridge and you have everything
  behind it. That is the trade versus commissioning devices directly.
- Multi-fabric applies to **the bridge as a whole** — each fabric gets its own
  NOC for the bridge, never per device.

Endpoint layout:

| Endpoint | Device type | Notes |
| --- | --- | --- |
| 0 | Root Node (22) | BasicInformation, NetworkCommissioning, OperationalCredentials… |
| 1 | Aggregator (14) | `Descriptor.PartsList` lists the bridged endpoints |
| 3…n | On/Off Light (256) **+ Bridged Node (19)** | one per bridged device, from `kDynamicEndpointStart = 3` |

Endpoint 2 is deliberately skipped — the bridge-app ZAP config reserves it for a
static example light with LevelControl, and inheriting that made Apple treat our
lights as dimmable.

---

## Prerequisites

- Docker dev environment (`docker compose build dev`)
- `third_party/connectedhomeip` checked out at **v1.3.0.0**
- `chip-tool` on PATH (or set `CHIP_TOOL`)
- SSH to the board, and `loginctl enable-linger orangepi` already set

---

## Procedure

### 0. One-time: bootstrap the CHIP SDK

```bash
docker compose run --rm dev bash scripts/setup-matter-sdk.sh
```

30–60 minutes, downloads ~500 MB of submodules plus the pigweed toolchain.
Includes the CIPD workaround (**Trap 1**) — do not run `scripts/bootstrap.sh`
directly, it will fail.

**Verify** `third_party/connectedhomeip/.environment/` contains
`python-venv/` and `activate.sh`, not just `cipd/` and `pigweed.json`. A
half-bootstrapped environment looks like a working one and silently
re-bootstraps on every build (**Trap 2**).

### 1. Choose which devices the bridge exposes

On the board, in `~/smart_home_AI/.env`:

```
BRIDGE_DEVICE_ALLOWLIST=kasa:192.168.0.73,kasa:192.168.0.61,kasa:192.168.0.110,kasa:192.168.0.143,matter:1
```

Unset means "expose everything". A **blank** value also means everything, not
nothing — deliberately, so a stray `BRIDGE_DEVICE_ALLOWLIST=` cannot unregister
every endpoint on the next restart.

Endpoints are **pinned per device** in `bridge_endpoints.json`, so the order here
does not decide them and adding a device cannot renumber the others — see
**Trap 5b**. A device keeps the first endpoint it is given; new ones take the
lowest free slot. Adding still needs a bridge restart, not a re-pair.

Restart the dashboard so it re-reads `.env`:

```bash
ssh orangepi@192.168.0.234 systemctl --user restart smart-home-dashboard
curl -s http://192.168.0.234:8000/bridge/devices | python3 -m json.tool
```

### 2. Build

```bash
docker compose run --rm dev bash scripts/build-matter-bridge.sh
```

**Verify** the artifact, not the exit code — the build is often run through a
pipe, and a pipeline's status is the *last* command's, not the build's:

```bash
ls -la build/matter-bridge/chip-bridge-app     # today ~1.5 MB, mtime = now
file build/matter-bridge/chip-bridge-app       # ELF 64-bit … ARM aarch64
strings build/matter-bridge/chip-bridge-app | grep -E '^(Smart Home AI|TEST_VENDOR)$'
```

Seeing `TEST_VENDOR` means `CHIPProjectConfig.h` did not reach the compile
(**Trap 6**).

### 3. Deploy

```bash
SKIP_BUILD=1 bash scripts/deploy-matter-bridge.sh
```

Syncs the binary and `configs/matter-bridge.service`, creates
`~/matter-bridge-kvs` (**Trap 4**), then enables and restarts the unit.

**Verify** every device registered:

```bash
ssh orangepi@192.168.0.234 \
  'PID=$(systemctl --user show matter-bridge -p MainPID --value); \
   grep -a "Registered .*(ep=" ~/matter-bridge.log | grep -a "\[$PID:"'
```

The count must equal `/bridge/devices`. A short list means **Trap 3**.

### 4. Commission

**Order matters: chip-tool first, Apple Home second.** chip-tool gives readable
errors and lets you verify conformance before spending an Apple re-pair.

```bash
scripts/verify-matter-bridge.sh --commission
```

Then for Apple Home, open a second window from the existing admin:

```bash
chip-tool pairing open-commissioning-window 1 1 900 1000 3840 \
  --storage-directory ~/.chip-tool-bridge
```

`1 1 900 1000 3840` = node 1, **enhanced** mode, 900 s, 1000 PBKDF iterations,
discriminator 3840. It prints a **fresh single-use code** — the original
passcode only works for the first pairing.

### 5. Verify before touching the Home app

```bash
scripts/verify-matter-bridge.sh
```

Then the walk Apple performs on every app open:

```bash
printf 'onoff read on-off 1 3\nany read-by-id 0xFFFFFFFF 0xFFFFFFFF 1 0xFFFF\nquit\n' \
  | chip-tool interactive start --storage-directory ~/.chip-tool-bridge 2>&1 \
  | grep -c UNSUPPORTED_READ
```

**This must print 0.** Anything else and Apple will commission successfully and
then drop the accessories (**Trap 5**).

---

## What good looks like

Reference values from the working 5-device bridge, 2026-09-06:

| Check | Expected |
| --- | --- |
| Wildcard read | **258 attributes, 0 `UNSUPPORTED_READ`, 0 failure statuses** |
| Per endpoint | ep0: 96, ep1: 16, ep3–7: 29–30 each |
| `descriptor read device-type-list 1 0` | Root Node (22) |
| `descriptor read device-type-list 1 1` | Aggregator (14) |
| `descriptor read device-type-list 1 3` | On/Off Light (256) **and** Bridged Node (19) |
| `descriptor read parts-list 1 1` | one entry per bridged device |
| `networkcommissioning read feature-map 1 0` | **4** (Ethernet) |
| `networkcommissioning read networks 1 0` | 1 entry, `Connected: TRUE` |
| `bridgeddevicebasicinformation read vendor-name 1 3` | `Smart Home AI` |
| `bridgeddevicebasicinformation read serial-number 1 3` | the device id |
| `basicinformation read vendor-name 1 0` | `Smart Home AI` |
| Bridge log | `NetworkCommissioning (Ethernet) initialised on ep0` |
| Bridge log | zero occurrences of `172.17.` |
| `systemctl --user show matter-bridge -p NRestarts` | `0` |

---

## Traps

Each of these cost time on the 2026-09-06 rebuild. Ordered by where you hit them.

### Trap 1 — SDK bootstrap dies on CIPD auth

**Symptom**
```
Not logged in to CIPD and no anonymous access to the following CIPD paths:
  fuchsia/third_party/zap
Login failed: interactive login flow requires the stdout to be attached to a terminal
CIPD login failed
```

**Cause** Not credentials. `pw_env_setup/cipd_setup/update.py:check_auth()`
strips any `${...}` segment before probing:

```python
parts = entry['path'].split('/')
while '${' in parts[-1]:
    parts.pop(-1)          # fuchsia/third_party/zap/${platform} → fuchsia/third_party/zap
```

It then probes a **prefix**, which anonymous users cannot list, and concludes
there is no access. The packages themselves are anonymously readable.

**Fix** Already in `setup-matter-sdk.sh`, via `scripts/fix_zap_cipd_paths.py`.

**Do not** "start from scratch" — the failure is deterministic and upstream, so
a fresh checkout reproduces it exactly.

### Trap 2 — a half-bootstrapped `.environment` looks like a working one

If it holds `cipd/` and `pigweed.json` but no `python-venv/`, bootstrap never
finished, and `scripts/activate.sh` silently re-runs it on every build.

### Trap 3 — devices silently missing from the bridge

**Symptom** `/bridge/devices` lists N devices; the bridge registers fewer, with
nothing logged. It looks like a Python-side bug.

**Cause** `kMaxDynamicDevices` in `main.cpp` bounds the registration loop. It was
hardcoded to **4** while the endpoint table held 16, so a fifth device was
dropped. It is now derived from `CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT` and
over-capacity is logged as `will NOT be bridged`.

**How to tell** `verify-matter-bridge.sh` prints the Python list and the
registered list side by side and marks the gap `NOT REGISTERED`. That comparison
is the fastest diagnostic in this file.

### Trap 4 — bridge restart-loops on a clean install

`--KVS` names a file inside `~/matter-bridge-kvs/`; CHIP does not create the
parent. `deploy-matter-bridge.sh` now does.

### Trap 5 — Apple Home commissions fine, then shows No Response on everything

**The headline bug of the 2026-09-06 rebuild.** Symptoms: commissioning succeeds,
all devices appear, then every one shows No Response and cycles "Updating…" on
each app open. chip-tool can read and control the same endpoints throughout.

**Cause** `main.cpp` calls `ChipLinuxAppInit()` and then runs **its own event
loop** instead of `ChipLinuxAppMainLoop()`. The SDK calls
`InitNetworkCommissioning()` from inside that main loop, so it never ran and no
driver backed the cluster on endpoint 0:

```
FeatureMap   2 (Thread)        ← ZAP static value, never overwritten by a driver
MaxNetworks  0
Networks     UNSUPPORTED_READ  ← no driver to answer
```

The root node advertised Thread networking on a board with no Thread radio.
Apple validates the root node's mandatory clusters and drops the accessories.

**Fix** Declare a `NetworkCommissioning::Instance` with `LinuxEthernetDriver`
and `Init()` it after `Server::Init()`.

**This is the same trap as Bug 3** (`docs/matter-bridge.md`), where the DAC
provider went unset for exactly the same reason. **If a third symptom of this
shape appears, audit everything `ChipLinuxAppMainLoop()` does that we skip.**

**What does not work:** setting `chip_enable_wifi=false` /
`chip_enable_openthread=false` in the gn args. Those choose which driver gets
*compiled*; nothing was initialising one. They were tried and reverted.

### Trap 5b — adding a device used to renumber the others

**Do you need to re-pair after adding a device to the bridge?** In principle no
— a bridge is designed to gain and lose endpoints at runtime, and controllers
re-read `PartsList`. Two things qualify that here.

**You need a bridge restart.** `RegisterDevices()` runs only at startup. The
poll loop deliberately refuses to re-register, because `/bridge/devices` goes
partial during dashboard restarts and re-registering under a paired bridge is
what caused No Response historically. The fabric survives a restart, so the
commissioning does not need redoing:

```bash
ssh orangepi@192.168.0.234 systemctl --user restart smart-home-dashboard
ssh orangepi@192.168.0.234 systemctl --user restart matter-bridge
scripts/verify-matter-bridge.sh
```

**The endpoint number is the accessory's identity**, and it used to come from
position in the device list. That list is built in a fixed order — Kasa (in
`tplink_switches.json` order) → Tuya → Matter (by node id) — and the allowlist
only *filters*, it does not reorder. So adding a Kasa switch that sits *earlier*
in `tplink_switches.json` inserted it mid-list and shifted every endpoint after
it. A controller tracking accessories by endpoint then sees them swap
identities, and you would have to re-pair after an ordinary config change.

**Fixed** by `bridge_endpoints.json` and `_assign_bridge_endpoints()`: a device
keeps the first endpoint it is ever given, new devices take the lowest free one,
and removing a device frees its endpoint without moving anybody. `/bridge/devices`
carries an `endpoint` field and `RegisterDevices()` honours it, falling back to
positional only when the field is absent.

Demonstrated against the live assignments — inserting `kasa:192.168.0.165`,
which sorts fourth in `tplink_switches.json`, gives it **ep8** and leaves ep3–7
untouched:

```
before: .110→3  .143→4  .61→5  .73→6  matter:1→7
after:  .110→3  .143→4  .61→5  .73→6  matter:1→7  .165→8
```

**Do not hand-edit `bridge_endpoints.json` on a paired bridge.** Changing a
number there renames an accessory as far as every controller is concerned. If
you must reset it, delete the file and re-pair everything.

### Trap 6 — TEST_VENDOR / TEST_PRODUCT identity collision

The SDK defaults the bridge's vendor and product names to `TEST_VENDOR` /
`TEST_PRODUCT` — which is **also what a cheap Matter device may advertise**. On
2026-09-04 that made matter-server's node 1 (the office Stick S3) look like this
bridge, and a wrong identification reached the runbook.

`CHIPProjectConfig.h` now sets `Smart Home AI` / `Dashboard Bridge`. **Names
only** — `CHIP_DEVICE_CONFIG_DEVICE_VENDOR_ID` / `_PRODUCT_ID` must stay at the
example DAC's `0xFFF1` / `0x8001`, or attestation fails and commissioning stops
at "Pairing failed".

To tell the bridge from a real device: the bridge is `matter-bridge.service` and
is normally *not* running. A node reported `available: true` while that unit is
inactive cannot be the bridge.

### Trap 7 — the commissioning window closes after ~15 minutes

**Symptom** PASE times out waiting for message type 33. The bridge keeps
advertising, so it looks available.

**Fix** On an **uncommissioned** bridge, restart it to reopen the basic window.
On a **commissioned** one a restart will *not* help — it logs `Fabric already
commissioned. Disabling BLE advertisement`. Use
`pairing open-commissioning-window` from an existing admin instead.

### Trap 8 — bridged devices show "Unknown" manufacturer and serial

`BridgedDeviceBasicInformation` must actually serve `VendorName` and
`SerialNumber`; only `Reachable` and `UniqueID` are mandatory, so omitting them
is legal but renders as Unknown in Home. Declaring an attribute in
`AttributeList` and not backing it is the habit that produced Trap 5.

### Trap 9 — chip-tool is a permissive oracle

**chip-tool has no concept of a bridge.** It addresses `<node> <endpoint>`
directly. It never walks `PartsList`, never builds per-accessory objects, never
re-enumerates on reconnect, and **never rejects you for non-conformance** — on a
wildcard read it prints "Response Failure" for a bad path and carries on.

So a green chip-tool run proves the **data plane** and says nothing about the
**enumeration/subscription plane**, which is the only thing Apple exercises.

**Use Home Assistant as a second opinion.** It is already on the board and shares
`matter-server`, it *does* implement the bridge conventions, and its logs are
readable. Commission the bridge into that fabric:

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts")
from matter_node_state import WSClient
c = WSClient("192.168.0.234", 5580, timeout=180); c.recv()
c.send({"message_id":"c1","command":"commission_with_code",
        "args":{"code":"<manual-code>","network_only":True}})
while True:
    m = c.recv()
    if m.get("message_id") == "c1": print(m.get("result") or m); break
PY
```

- **HA also broken** → the fault is ours, and HA's logs will name it.
- **HA fine, Apple broken** → an Apple-enforced conformance detail. This is
  exactly how Trap 5 was localised.

### Trap 10 — every chip-tool command takes 45 seconds from WSL

**Symptom**
```
node lookup status for ADEF574ABBDFA616-0000000000000001 after 45002 ms
```

**Cause** Each separate chip-tool process re-resolves the node over DNS-SD, and
WSL2's NAT makes that multicast lookup wait out its full timeout. It is **not**
the bridge and **not** re-commissioning.

**Fix** One `chip-tool interactive start` session. Discovery is paid once; the
four operations after the first measured **32 ms total**. `verify-matter-bridge.sh`
does this over a FIFO — a full two-cycle run went from minutes to 15.7 s.

Two bash hazards when scripting around it, both of which produced silent wrong
answers during this work:

- `cmd | grep -q` under `set -o pipefail` — grep exits on first match, chip-tool
  takes SIGPIPE, and the pipeline reports failure on a **successful** read.
- `x="$(helper …)"` runs the helper in a **subshell**, so a read-offset global
  does not persist and every call re-matches the *previous* command's reply.

### Trap 11 — mDNS advertising the docker0 IP

Historical, but docker0 still exists on the board. CHIP's minimal mDNS
multicasts on every interface; an iPhone caching a `172.17.x` A record fails
with "Unable to connect to accessory" *after* accepting the code.

**Check** `grep -c '172\.17\.' ~/matter-bridge.log` must be `0`.

### Trap 12 — wrong interface name

`--interface wlp1s0`, never `wlan0`. Ubuntu's predictable names; the Pi 4's unit
does not transfer. A wrong interface makes commissioning fail **silently**.

---

## Tooling reference

| Command | Purpose |
| --- | --- |
| `scripts/setup-matter-sdk.sh` | one-time SDK bootstrap (includes the CIPD fix) |
| `scripts/build-matter-bridge.sh` | cross-compile arm64 binary |
| `scripts/deploy-matter-bridge.sh` | sync binary + unit, create KVS dir, restart |
| `scripts/verify-matter-bridge.sh` | inventory / commission / exercise, one chip-tool session |
| `scripts/matter_node_state.py` | read a node's real OnOff from matter-server |
| `scripts/test-matter-commissioning.sh` | native-binary integration test in the dev container |

`verify-matter-bridge.sh --cycle <ep>` restores the endpoint to the state it
found, so it is safe against real lights.

---

## Things that are *not* the problem

Recorded because each was investigated at length on 2026-09-06 and cleared:

- **The router or IPv6.** The board has only a link-local IPv6 address and Matter
  works fine on it. Other Matter devices on the same LAN were never affected.
- **The number of bridged endpoints.** A wildcard subscribe across 5 endpoints
  succeeded with 61 report chunks and no resource exhaustion.
- **Session eviction.** Evictions in the log clustered around chip-tool testing,
  not Apple traffic.
- **Packet buffers.** `CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE 0` and
  `CAPACITY_MAX 9050` in `CHIPProjectConfig.h` already handle Apple's wildcard
  subscriptions; zero `NO_MEMORY` throughout.
- **ACL.** Apple's fabrics receive admin entries with `Targets: null`.
