"""Bridge Sync API — internal FastAPI router for the C++ Matter bridge daemon.

Mounted at /bridge on the main web app (port 8000, localhost only).

Endpoints the C++ bridge calls:
  GET  /bridge/devices      — list all bridgeable devices with current state
  POST /bridge/command      — route a command from Apple Home to a real device
  GET  /bridge/state/all    — poll current state for all devices
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Awaitable
from typing import Any

from fastapi import APIRouter, HTTPException
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
# Updated by the dashboard's poll loop via update_state_cache().
# Key: device_id  Value: latest state dict (e.g. {"on": True})

_state_cache: dict[str, dict[str, Any]] = {}


def update_state_cache(device_id: str, state: dict[str, Any]) -> None:
    """Called by the dashboard's poll loop whenever device state changes."""
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
async def send_command(body: CommandBody) -> dict[str, str]:
    """Route an Apple Home command to the target device."""
    if _execute_command_fn is None:
        raise HTTPException(status_code=503, detail="Bridge not initialised")
    try:
        await _execute_command_fn(body.device_id, body.command)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown device: {body.device_id}")
    except Exception as exc:
        logger.error("Bridge command %s → %s failed: %s", body.command, body.device_id, exc)
        raise HTTPException(status_code=503, detail="Device unreachable")
