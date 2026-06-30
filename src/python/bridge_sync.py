"""Bridge Sync API — internal FastAPI router for the C++ Matter bridge daemon.

Mounted at /bridge on the main web app (port 8000, localhost only).

Endpoints the C++ bridge calls:
  GET  /bridge/devices      — list all bridgeable devices with current state
  POST /bridge/command      — route a command from Apple Home to a real device
  GET  /bridge/state/all    — poll current state for all devices
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Awaitable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bridge", tags=["bridge-sync"])

# ── Callbacks registered by web_app at startup ───────────────────────────────
# Using a registry avoids circular imports (bridge_sync ↔ web_app).

_get_devices_fn: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None
_execute_command_fn: Callable[[str, str], Awaitable[None]] | None = None


def register_handlers(
    get_devices_fn: Callable[[], Awaitable[list[dict[str, Any]]]] | None,
    execute_command_fn: Callable[[str, str], Awaitable[None]] | None,
) -> None:
    """Called by web_app.create_app() to wire device-list and command callbacks."""
    global _get_devices_fn, _execute_command_fn
    _get_devices_fn = get_devices_fn
    _execute_command_fn = execute_command_fn


# ── In-memory state cache ─────────────────────────────────────────────────────
# Updated by the dashboard's poll loop via update_state_cache(), and by
# /bridge/command after it executes a command from the C++ bridge.
# Key: device_id  Value: latest state dict (e.g. {"on": True})

_state_cache: dict[str, dict[str, Any]] = {}

# Race fix: a live status read (dashboard polling /api/devices, or the C++
# bridge's periodic device rescan via GET /bridge/devices) can land *while* a
# command issued moments earlier is still in flight to the physical device,
# and read the pre-command value. That stale read used to clobber the cache,
# so the next 10s C++ poll tick would report the device flipping back to its
# old state right after the user toggled it — which made Apple Home mark the
# accessory "No Response". mark_command_pending() opens a short window during
# which only the command's own (authoritative) result may write the cache;
# concurrent plain status reads are dropped instead of overwriting it.
# Key: device_id  Value: monotonic() deadline.
_pending_until: dict[str, float] = {}

_COMMAND_PENDING_TTL_SECONDS = 3.0


def mark_command_pending(device_id: str) -> None:
    """Call right before executing a command so concurrent status reads can't
    race it and clobber the cache with the pre-command value."""
    _pending_until[device_id] = time.monotonic() + _COMMAND_PENDING_TTL_SECONDS


def update_state_cache(device_id: str, state: dict[str, Any], *, authoritative: bool = False) -> None:
    """Update the cached state for a device.

    authoritative=True (the command's own result) always wins and clears the
    pending window. authoritative=False (a plain status read, e.g. dashboard
    polling or the C++ bridge's device rescan) is dropped if it lands inside
    another command's pending window, since it may be reading a value the
    in-flight command is about to change.
    """
    if authoritative:
        _pending_until.pop(device_id, None)
    elif _pending_until.get(device_id, 0.0) > time.monotonic():
        logger.debug("Dropping stale status read for %s — command in flight", device_id)
        return
    _state_cache[device_id] = state


# ── Pydantic models ───────────────────────────────────────────────────────────

class CommandBody(BaseModel):
    device_id: str
    command: str   # "on" | "off" | "toggle" | "brightness:N" (N = 0-100)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/devices")
async def list_devices() -> list[dict[str, Any]]:
    """Return all bridgeable devices with their current state."""
    if _get_devices_fn is None:
        return []
    return await _get_devices_fn()


@router.get("/state/all")
async def all_states() -> dict[str, dict[str, Any]]:
    """Return the latest cached state for every device."""
    return dict(_state_cache)


@router.post("/command", status_code=200)
async def send_command(body: CommandBody, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Route an Apple Home command to the target device.

    Returns 200 immediately and runs the actual device call in the background so
    the C++ bridge's synchronous HTTP call returns before the Kasa network round-trip
    completes — preventing the Matter event loop from blocking and causing Apple Home
    to show "No response".
    """
    if _execute_command_fn is None:
        raise HTTPException(status_code=503, detail="Bridge not initialised")

    device_id = body.device_id
    command = body.command

    # Close the race window now, before the background task even starts, so a
    # concurrent rescan/dashboard poll can't read stale state in the gap
    # between accepting this command and actually executing it.
    mark_command_pending(device_id)

    async def _run() -> None:
        try:
            await _execute_command_fn(device_id, command)
        except KeyError:
            logger.error("Bridge command %s → %s: unknown device", command, device_id)
        except Exception as exc:
            logger.error("Bridge command %s → %s failed: %s", command, device_id, exc)

    background_tasks.add_task(_run)
    return {"status": "ok"}
