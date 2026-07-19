# Lepro + Govee BLE Dashboard Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dashboard control of the Lepro S1 AI LED over Bluetooth (new `lepro_ble` provider) and extend the existing Govee BLE support to the H6076 floor lamp, using the Pi's UB500 adapter.

**Architecture:** Generalize the existing `_GoveeBleManager` in `src/python/web_app.py` into a provider-agnostic BLE write manager with a per-provider packet builder and characteristic selector. `govee_ble` behavior is preserved byte-for-byte; `lepro_ble` adds its own encoder (defined by Phase 1 probing) and its vendor write characteristic `1e2aa502-7292-4263-a8f1-be907f039a1f`. The ambient-light card/endpoint dispatch switches on provider.

**Tech Stack:** Python 3.12, FastAPI, bleak (BLE), pytest, PyYAML. Frontend is vanilla JS (`web_static/app.js`). Deploy via `scripts/deploy-dashboard.sh` to the Pi (systemd user unit `smart-home-dashboard.service`).

## Global Constraints

- Never commit real BLE addresses, credentials, or `configs/devices.local.yaml` — that file is git-ignored and lives only on the Pi.
- BLE discovery and all live-device testing run **on the Pi**, never in WSL (WSL2 NAT blocks BLE/UDP). Use `./scripts/connect-pi.sh -- "<cmd>"`.
- The Pi dashboard venv is `/home/smarthome/smart-home-rpi4/.venv/bin/python3`; only that venv has `bleak`.
- The lamp accepts one BLE connection at a time — the iPhone Lepro app must be closed during any probing or live test.
- Govee `govee_ble` command bytes must remain unchanged (existing tests in `tests/python/test_web_app.py` lock them: `_govee_ble_command_bytes` XOR-checksum cases).
- Existing endpoint contract: unknown command → 400; `alexa` provider → 501; missing address → 400.
- Follow existing single-file `web_app.py` structure; do not extract a new module.

---

### Task 1: Lepro BLE protocol probe script (Phase 1 — interactive)

This task is a spike: its deliverable is a decoded protocol recorded in the spec's
"Open questions" section, not merged product code. It gates Tasks 2–6. If probing
finds no working packet family, STOP after this task — the Lepro stays on the
`alexa` provider and only the Govee tasks (5, 6 partially) proceed.

**Files:**
- Create: `scripts/probe-lepro-ble.py`

**Interfaces:**
- Produces: decoded Lepro command bytes for at minimum `on`/`off`, recorded in
  the design doc; consumed by Task 2's encoder.

- [ ] **Step 1: Write the probe script**

```python
#!/usr/bin/env python3
"""Interactive Lepro S1 BLE protocol probe. Run on the Pi with its venv.

Connects to the lamp, subscribes to notifications, and writes candidate
packets one family at a time, pausing for the operator to report reactions.
Close the iPhone Lepro app first (one connection only).
"""
import asyncio
import sys

from bleak import BleakClient, BleakScanner

WRITE_UUID = "1e2aa502-7292-4263-a8f1-be907f039a1f"
NOTIFY_UUID = "1e2aa503-7292-4263-a8f1-be907f039a1f"


def _govee_style(payload: list[int]) -> bytes:
    packet = payload + [0x00] * (19 - len(payload))
    checksum = 0
    for value in packet:
        checksum ^= value
    packet.append(checksum)
    return bytes(packet)


# Candidate on/off packets from common LED-controller families.
CANDIDATES = {
    "govee_style_on": _govee_style([0x33, 0x01, 0x01]),
    "govee_style_off": _govee_style([0x33, 0x01, 0x00]),
    "triones_on": bytes([0xCC, 0x23, 0x33]),
    "triones_off": bytes([0xCC, 0x24, 0x33]),
    "generic_7e_on": bytes([0x7E, 0x04, 0x04, 0x01, 0x00, 0x01, 0xFF, 0x00, 0xEF]),
    "generic_7e_off": bytes([0x7E, 0x04, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF]),
    "ascii_on": b"ON\r\n",
    "ascii_off": b"OFF\r\n",
}


def _on_notify(_char, data: bytearray) -> None:
    print(f"    <- notify: {data.hex()}")


async def main(address: str) -> None:
    print(f"Scanning for {address} (close the phone app!) ...")
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if device is None:
        print("Device not found in scan; is the phone app still connected?")
        sys.exit(1)
    async with BleakClient(device, timeout=15.0) as client:
        print("Connected. Subscribing to notifications.")
        try:
            await client.start_notify(NOTIFY_UUID, _on_notify)
        except Exception as exc:  # noqa: BLE001
            print(f"  (notify subscribe failed: {exc})")
        for name, packet in CANDIDATES.items():
            input(f"\nPress Enter to send {name} = {packet.hex()} ...")
            try:
                await client.write_gatt_char(WRITE_UUID, packet, response=False)
                print("    sent (write-without-response)")
            except Exception as exc:  # noqa: BLE001
                print(f"    write failed: {exc}")
            await asyncio.sleep(1.0)
            print("    -> Did the lamp react? Note it before continuing.")
        print("\nDone. Report which candidate(s) caused a visible change.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "B8:F8:62:DB:79:46"
    asyncio.run(main(target))
```

- [ ] **Step 2: Ship the script to the Pi and run it interactively**

```bash
./scripts/deploy-dashboard.sh    # or scp the single file
./scripts/connect-pi.sh -- "cd ~/smart-home-rpi4 && ./.venv/bin/python3 scripts/probe-lepro-ble.py"
```

Expected: connects, subscribes, then walks candidate packets. Operator watches
the lamp and reports which family (if any) toggles it. Because `input()` needs a
TTY, run this over an interactive SSH session (`./scripts/connect-pi.sh` then run
the command in the shell), not the non-interactive `-- "<cmd>"` form, if prompts
don't appear.

- [ ] **Step 3: Record findings**

Edit the design doc "Open questions resolved during probing" section in
`docs/superpowers/specs/2026-07-18-lepro-govee-ble-design.md` with the working
packet family and any brightness/color frames discovered. If nothing worked,
record "protocol not decoded — Lepro remains display-only" and STOP the plan
here.

- [ ] **Step 4: Commit**

```bash
git add scripts/probe-lepro-ble.py docs/superpowers/specs/2026-07-18-lepro-govee-ble-design.md
git commit -m "Add Lepro BLE probe script and record decoded protocol"
```

---

### Task 2: Lepro packet builder

**Files:**
- Modify: `src/python/web_app.py` (add near `_govee_ble_command_bytes`, ~line 1276)
- Test: `tests/python/test_web_app.py`

**Interfaces:**
- Consumes: decoded packet format from Task 1.
- Produces: `_lepro_ble_command_bytes(command: str, body: dict[str, Any] | None = None) -> bytes`
  and constant `LEPRO_BLE_WRITE_UUID = "1e2aa502-7292-4263-a8f1-be907f039a1f"`.

> The byte literals below are ILLUSTRATIVE placeholders using the `govee_style`
> family. Replace every `bytes.fromhex(...)`/payload literal in Step 1 and Step 3
> with the actual frames recorded in Task 1 before running the test. Keep the
> function signature, command names, and 400-on-unknown-command behavior exactly
> as written.

- [ ] **Step 1: Write the failing test**

```python
def test_lepro_ble_command_bytes_encodes_power() -> None:
    from src.python.web_app import _lepro_ble_command_bytes
    # Replace expected values with the frames decoded in Task 1.
    assert _lepro_ble_command_bytes("on") == bytes.fromhex("REPLACE_WITH_ON_FRAME")
    assert _lepro_ble_command_bytes("off") == bytes.fromhex("REPLACE_WITH_OFF_FRAME")


def test_lepro_ble_command_bytes_rejects_unknown() -> None:
    from fastapi import HTTPException
    from src.python.web_app import _lepro_ble_command_bytes
    import pytest
    with pytest.raises(HTTPException) as exc:
        _lepro_ble_command_bytes("nope")
    assert exc.value.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_web_app.py::test_lepro_ble_command_bytes_encodes_power -v`
Expected: FAIL with `ImportError`/`cannot import name '_lepro_ble_command_bytes'`.

- [ ] **Step 3: Write minimal implementation**

```python
LEPRO_BLE_WRITE_UUID = "1e2aa502-7292-4263-a8f1-be907f039a1f"


def _lepro_ble_command_bytes(command: str, body: dict[str, Any] | None = None) -> bytes:
    body = body or {}
    # Replace payloads below with the frames decoded in Task 1.
    if command == "on":
        return bytes.fromhex("REPLACE_WITH_ON_FRAME")
    if command == "off":
        return bytes.fromhex("REPLACE_WITH_OFF_FRAME")
    if command == "brightness":
        # Only if Task 1 decoded a brightness frame; otherwise delete this branch.
        value = _bounded_byte(body.get("brightness", body.get("value", 100)), minimum=1, maximum=100)
        return bytes([0x00, value])  # REPLACE
    if command == "color":
        # Only if Task 1 decoded a color frame; otherwise delete this branch.
        red = _bounded_byte(body.get("red", body.get("r", 255)))
        green = _bounded_byte(body.get("green", body.get("g", 255)))
        blue = _bounded_byte(body.get("blue", body.get("b", 255)))
        return bytes([0x00, red, green, blue])  # REPLACE
    raise HTTPException(status_code=400, detail=f"Unsupported Lepro BLE command: {command}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/python/test_web_app.py -k lepro_ble_command_bytes -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/python/web_app.py tests/python/test_web_app.py
git commit -m "Add Lepro BLE command byte encoder"
```

---

### Task 3: Provider-agnostic BLE manager

Generalize `_GoveeBleManager` so the write characteristic and any provider
quirks are selected by provider, without changing Govee output.

**Files:**
- Modify: `src/python/web_app.py` (`_GoveeBleManager`, `_govee_ble_write_target`, ~lines 1327-1490)
- Test: `tests/python/test_web_app.py`

**Interfaces:**
- Consumes: `AmbientLightDefinition.provider`, `LEPRO_BLE_WRITE_UUID` (Task 2),
  `GOVEE_BLE_WRITE_UUIDS`.
- Produces: `_ble_write_target(client, provider) -> tuple[str, bool]` that returns
  the Lepro write char for `lepro_ble` and preserves existing Govee selection for
  `govee_ble`. The manager's `write(light, packet)` signature is unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_ble_write_target_prefers_lepro_char_for_lepro_provider() -> None:
    import src.python.web_app as web_app_module

    class _Char:
        def __init__(self, uuid, props):
            self.uuid = uuid
            self.properties = props

    class _Svc:
        characteristics = [
            _Char("1e2aa502-7292-4263-a8f1-be907f039a1f", ["write", "write-without-response"]),
            _Char("00002a00-0000-1000-8000-00805f9b34fb", ["read"]),
        ]

    class _Client:
        services = [_Svc()]

    char, needs_response = web_app_module._ble_write_target(_Client(), "lepro_ble")
    assert char == "1e2aa502-7292-4263-a8f1-be907f039a1f"
    assert needs_response is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_web_app.py::test_ble_write_target_prefers_lepro_char_for_lepro_provider -v`
Expected: FAIL with `AttributeError: module ... has no attribute '_ble_write_target'`.

- [ ] **Step 3: Implement the generalized target selector and route the manager through it**

Rename `_govee_ble_write_target(client)` to `_ble_write_target(client, provider)`.
Keep the existing Govee body for the `govee_ble` branch. Add a `lepro_ble` branch:

```python
def _ble_write_target(client: Any, provider: str) -> tuple[str, bool]:
    services = getattr(client, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="BLE services were not available after connect")

    writable = []
    for service in services:
        for characteristic in service.characteristics:
            props = set(characteristic.properties)
            if "write" in props or "write-without-response" in props:
                writable.append((str(characteristic.uuid).lower(), props))

    preferred = (LEPRO_BLE_WRITE_UUID,) if provider == "lepro_ble" else GOVEE_BLE_WRITE_UUIDS
    for uuid in preferred:
        for candidate, props in writable:
            if candidate == uuid.lower():
                return candidate, "write-without-response" not in props

    for candidate, props in writable:
        if not candidate.startswith("00002a"):
            return candidate, "write-without-response" not in props
    raise HTTPException(status_code=503, detail="No writable BLE characteristic found")
```

In `_GoveeBleManager._write_once`, change the call site from
`_govee_ble_write_target(client)` to `_ble_write_target(client, light.provider)`.
Only apply the Govee-specific cache-forget (`_govee_ble_forget_cached_device`) and
H613A initial delay when `light.provider == "govee_ble"` (guard those lines with
that check; for `lepro_ble` use `initial_delay = 1` and skip the bluetoothctl
remove unless Task 1 showed it is needed).

- [ ] **Step 4: Run tests to verify pass (new + Govee regression)**

Run: `python3 -m pytest tests/python/test_web_app.py -k "ble or govee" -v`
Expected: PASS, including existing `test_govee_*` tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/python/web_app.py tests/python/test_web_app.py
git commit -m "Generalize BLE write manager to support multiple providers"
```

---

### Task 4: Wire lepro_ble into card + command endpoint

**Files:**
- Modify: `src/python/web_app.py` (`_ambient_light_card` ~1196, `ambient_light_command` ~406, `_govee_ble_command_payload` ~1410 → generalize)
- Test: `tests/python/test_web_app.py`

**Interfaces:**
- Consumes: `_lepro_ble_command_bytes` (Task 2), generalized manager (Task 3).
- Produces: `lepro_ble` cards report `controllable`/`capabilities` like Govee; the
  POST command endpoint dispatches `lepro_ble` to a shared
  `_ble_command_payload(light, command, body)`.

- [ ] **Step 1: Write the failing test**

Update `_write_ambient_config` in the test file to give the Lepro entry
`provider: lepro_ble` with a fake address, then:

```python
def test_lepro_ble_card_is_controllable_with_address(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ambient_config(config)  # Lepro entry now provider: lepro_ble + address
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))
    lights = client.get("/api/ambient-lights").json()["lights"]
    lepro = next(l for l in lights if l["provider"] == "lepro_ble")
    assert lepro["controllable"] is True
    assert lepro["capabilities"]["power"] is True
```

Note: the existing `test_ambient_light_command_rejects_unconfigured_or_unsupported_paths`
asserts the Lepro returns 501 on the `alexa` provider. Since the fixture Lepro
becomes `lepro_ble`, change that assertion to expect a different failure — with a
monkeypatched manager it should reach 502/ok, so instead assert an `alexa`-only
entry still 501s (add a separate always-alexa fixture entry) OR update the
existing assertion to target a still-`alexa` device. Keep one 501 case alive.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_web_app.py::test_lepro_ble_card_is_controllable_with_address -v`
Expected: FAIL — `lepro_ble` currently falls into the `unsupported` branch, `controllable` is False.

- [ ] **Step 3: Implement**

In `_ambient_light_card`, treat `lepro_ble` like `govee_ble` for status/note/
controllable/capabilities. Extract the shared BLE branch:

```python
    if light.provider in ("govee_ble", "lepro_ble"):
        has_address = _is_real_ble_address(light.address)
        status = "configured" if has_address else "needs_ble_address"
        vendor = "Govee" if light.provider == "govee_ble" else "Lepro"
        note = "BLE address configured" if has_address else f"Run BLE discovery on the Raspberry Pi and add the {vendor} address."
        controllable = has_address
```

Set the `capabilities` dict for both BLE providers. For `lepro_ble`, only mark
`brightness`/`color` true if Task 1 decoded those frames (else power-only).

Rename `_govee_ble_command_payload` to `_ble_command_payload` and select the
encoder by provider:

```python
    packet = (_govee_ble_command_bytes if light.provider == "govee_ble" else _lepro_ble_command_bytes)(command, body)
```

In `ambient_light_command`, replace the `provider != "govee_ble"` rejection:

```python
        if light.provider == "alexa":
            raise HTTPException(status_code=501, detail="Lepro via Alexa needs an Alexa routine or bridge before dashboard commands can be sent.")
        if light.provider not in ("govee_ble", "lepro_ble"):
            raise HTTPException(status_code=400, detail=f"Unsupported ambient provider: {light.provider}")
        if not light.address:
            raise HTTPException(status_code=400, detail="BLE light needs a Bluetooth address from Pi discovery before it can be controlled.")
        return await asyncio.to_thread(_ble_command_payload, light, command, body or {})
```

Keep the `toggle`-unsupported guard inside `_ble_command_payload`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/python/test_web_app.py -k "ambient or lepro or govee" -v`
Expected: PASS (including the preserved 501 alexa case).

- [ ] **Step 5: Commit**

```bash
git add src/python/web_app.py tests/python/test_web_app.py
git commit -m "Route lepro_ble through ambient card and command endpoint"
```

---

### Task 5: Frontend provider label + config schema

**Files:**
- Modify: `src/python/web_static/app.js:837` (provider label), `:851` (discover button)
- Modify: `configs/devices.example.yaml` (ambient section, ~line 127)
- Test: manual (frontend is exercised by dashboard tests that assert on card HTML if present)

**Interfaces:**
- Consumes: card JSON `provider: "lepro_ble"` from Task 4.
- Produces: user-visible "Lepro Bluetooth" label; example schema documents the provider.

- [ ] **Step 1: Update the provider label**

In `ambientLightCard`, line 837:

```javascript
  const providerLabel = light.provider === "govee_ble" ? "Govee Bluetooth"
    : light.provider === "lepro_ble" ? "Lepro Bluetooth"
    : light.provider === "alexa" ? "Alexa bridge" : light.provider;
```

- [ ] **Step 2: Update the discover-button condition**

Line 851 — show discover for either BLE provider missing an address:

```javascript
  const discover = (light.provider === "govee_ble" || light.provider === "lepro_ble") && !light.address
    ? '<button class="command" data-ambient-discover="' + escapeHtml(light.provider) + '"><i class="ti ti-bluetooth"></i> Discover</button>'
    : '';
```

- [ ] **Step 3: Update the example config schema**

In `configs/devices.example.yaml`, change the Lepro entry to document the new
provider (keep it as an example, not a real address):

```yaml
    - name: Lepro S1 AI LED
      provider: lepro_ble
      model: Lepro S1 AI LED
      room: Studio
      # Run scripts/probe-lepro-ble.py / BLE discovery on the Pi and paste the address here.
      address: replace_me
```

- [ ] **Step 4: Run the Python suite (guards against template/asset test breakage)**

Run: `python3 -m pytest tests/python/test_dashboard_device_frontend.py tests/python/test_web_app.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/python/web_static/app.js configs/devices.example.yaml
git commit -m "Surface Lepro Bluetooth provider in dashboard UI and example config"
```

---

### Task 6: Pi config update, deploy, and live verification

**Files:**
- Modify (on the Pi only, git-ignored): `configs/devices.local.yaml`
- No repo files.

**Interfaces:**
- Consumes: all prior tasks deployed.

- [ ] **Step 1: Update the Pi's local config**

On the Pi, edit `configs/devices.local.yaml` ambient section: switch the Lepro
S1 entry to `provider: lepro_ble` with `address: B8:F8:62:DB:79:46`; add the
Govee H6076:

```yaml
    - name: Govee H6076 Floor Lamp
      provider: govee_ble
      model: H6076
      room: Ambient
      address: E8:6E:80:C6:2F:18
```

(Do this via an interactive SSH edit; do not commit this file.)

- [ ] **Step 2: Deploy the dashboard**

```bash
./scripts/deploy-dashboard.sh
```

Expected: rsync/scp of updated `web_app.py`, `app.js`, and scripts; service
picks up changes (config re-read per request; a `web_app.py` change needs the
service restart that the deploy script performs).

- [ ] **Step 3: Verify Govee lights (H613A, H6054, H6076) from the dashboard**

Log into the dashboard, open the Ambient view, and toggle each Govee light On/Off
and one brightness/color. Confirm the lamp physically reacts. Close the iPhone
apps for any lamp that won't connect (one BLE connection each).

- [ ] **Step 4: Verify the Lepro S1 from the dashboard**

With the iPhone Lepro app CLOSED, toggle the Lepro card On/Off (and
brightness/color if decoded). Confirm the lamp reacts.

- [ ] **Step 5: Record the outcome**

Update the memory note `tplink-ub500-bluetooth-adapter.md` (and the Obsidian
project note) with the Lepro `lepro_ble` result and the added H6076. Do not
record the BLE addresses as secrets — they are already non-sensitive MACs, but
keep them out of the git repo per Global Constraints.

---

## Notes on the second `LP` device

`10:20:BA:30:2A:7A` also advertises as `LP` but refused connection during the
initial probe. It is out of scope; if it turns out to be a second Lepro unit,
adding it is a one-line config addition mirroring Step 1 once it connects.
