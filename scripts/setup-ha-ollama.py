#!/usr/bin/env python3
"""Point Home Assistant's Ollama integration at the board's local Qwen.

Home Assistant ships an `ollama` integration and this board already runs Ollama
on loopback. Nothing connected the two, so the model was an island: reachable
over SSH and from nowhere in the house. This wires it up.

It creates, if they are not already there:

  * the `ollama` config entry, pointing at 127.0.0.1:11434
  * `conversation.local_qwen` - a fallback agent with **no** access to the house
  * `conversation.local_qwen_control` - an agent that can see and control it
  * `ai_task.local_qwen_task` - a batch entity for the nightly digest jobs
  * a second Assist pipeline, "Local Qwen (control)", using the second agent

and it turns on `prefer_local_intents` for the default pipeline.

## Why two agents rather than one

Home Assistant runs local intent matching before the LLM only when
`prefer_local_intents` is set, and then narrows what it will match: if the
conversation agent advertises CONTROL - which it does as soon as it is given
`llm_hass_api` - `_async_local_fallback_intent_filter` restricts the local-first
path to GetState and MediaSearchAndPlay. Everything else, "turn on the office
light" included, goes to the model.

On this board that is backwards. Generation runs at ~15 tok/s and Qwen3 thinks
before it answers, so a command costs 10-15 s against the matcher's
milliseconds, and the model is wrong often enough that docs/local-ai.md tells
you not to put it in a control path.

So the default pipeline gets the agent *without* house access. The filter is
then never installed, every sentence the matcher understands is answered
locally and instantly, and only genuinely unrecognised ones reach the model.
The controlling agent still exists on its own pipeline for when you want it,
which is the deliberate, opt-in case rather than the default one.

## Two defaults that are wrong for this board

  keep_alive  Home Assistant defaults to -1, "keep the model loaded for ever".
              That pins ~3.3 GiB and destroys the one property Ollama was
              chosen for on a board with no swap: that it gives the memory back
              when idle. We send 300 seconds.

  think       Home Assistant defaults to False, and passing think=False to
              Qwen3 does not suppress its reasoning - it returns the reasoning
              *as* the answer (measured; docs/local-ai.md). With think=True the
              integration files it under thinking_content and the reply is
              clean.

Every subentry is given the same `num_ctx` on purpose. Ollama keys a loaded
runner on the context size, so mixing sizes makes each switch between agents
reload ~2.5 GiB of weights.

Idempotent: each step looks for what it is about to create and leaves it alone
if it is already there, so this is safe to re-run. Nothing is written without
--apply.

Run it from the dashboard virtualenv, which is the one with aiohttp:

    ~/smart_home_AI/.venv/bin/python scripts/setup-ha-ollama.py
    ~/smart_home_AI/.venv/bin/python scripts/setup-ha-ollama.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:4b-house"

# See the module docstring: neither of these is Home Assistant's default.
KEEP_ALIVE_SECONDS = 300

# Whether Qwen3 reasons before answering. It is not one answer for all three.
#
# The answering agent keeps thinking ON: its replies are free-form prose, and
# with think=False Ollama returns the reasoning *as* the answer (measured;
# docs/local-ai.md). With it on, the integration files the reasoning under
# thinking_content and the spoken reply is clean.
#
# The controlling agent turns it OFF, because it does not pay once per
# question - it pays once per tool iteration, and Home Assistant allows up to
# MAX_TOOL_ITERATIONS = 10 of them. Measured on this board with the default
# ~45 exposed entities, one question with thinking on ran for over eighteen
# minutes without finishing. Tool calls are structured, so the reasoning has
# nowhere to leak into; only the final spoken sentence is affected.
THINK_ANSWERING = True
THINK_CONTROL = False
THINK_TASK = True

# Shared by every subentry so they all use one loaded Ollama runner.
NUM_CTX = 8192
# Home Assistant defaults to 20. Prompt processing is ~66 tok/s, so every
# remembered turn is paid for again on the next one.
MAX_HISTORY = 6

ANSWER_PROMPT = (
    "You are a helpful assistant in a smart home. You cannot see or control "
    "the house - device commands and status questions are handled before they "
    "reach you. Answer general questions briefly, in one or two sentences. If "
    "you are asked about the state of a device, say plainly that you cannot "
    "check it and suggest asking again in simpler words."
)

CONTROL_PROMPT = (
    "You are the voice assistant for a smart home. Answer in one or two short "
    "sentences; no lists or preamble unless you are asked for them. Use the "
    "tools you are given to inspect and control devices. Only ever act on "
    "devices that appear in the exposed entity list - never guess an entity "
    "that is not there. If a request could mean more than one device, ask "
    "which rather than picking one."
)

# The ai_task_data subentry takes no prompt: ollama_config_option_schema adds
# `prompt` and `llm_hass_api` only for subentry_type == "conversation". An AI
# Task is instructed per call instead, by ai_task.generate_data.


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def subentry_plan(model: str) -> list[dict[str, Any]]:
    """The three subentries we want, in creation order.

    `llm_hass_api` is omitted rather than set empty for the answering agent:
    its presence is what makes Home Assistant advertise CONTROL, which is what
    narrows local intent matching.
    """
    common = {
        "model": model,
        "num_ctx": NUM_CTX,
        "max_history": MAX_HISTORY,
        "keep_alive": KEEP_ALIVE_SECONDS,
    }
    return [
        {
            "type": "conversation",
            "name": "Local Qwen",
            "data": {**common, "prompt": ANSWER_PROMPT, "think": THINK_ANSWERING},
            "why": "fallback for sentences the matcher does not recognise",
        },
        {
            "type": "conversation",
            "name": "Local Qwen Control",
            "data": {**common, "prompt": CONTROL_PROMPT, "llm_hass_api": ["assist"],
                     "think": THINK_CONTROL},
            "why": "opt-in agent that can actually see and drive the house",
        },
        {
            "type": "ai_task_data",
            "name": "Local Qwen Task",
            "data": {**common, "think": THINK_TASK},
            "why": "batch entity for ai_task.generate_data",
        },
    ]


class HomeAssistantWS:
    """Minimal Home Assistant WebSocket client, matching the other scripts here."""

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self._id = 0

    async def call(self, **payload: Any) -> Any:
        self._id += 1
        await self._ws.send_json({"id": self._id, **payload})
        while True:
            message = await self._ws.receive_json()
            if message.get("id") != self._id:
                continue  # An event, or a reply to something else.
            if not message.get("success"):
                error = message.get("error", {})
                raise RuntimeError(f"{payload.get('type')}: {error.get('message', message)}")
            return message.get("result")


async def preflight(session: Any, ollama_url: str, model: str) -> str | None:
    """Fail early and specifically rather than half-way through the config flow."""
    try:
        async with session.get(f"{ollama_url}/api/tags", timeout=10) as response:
            tags = await response.json()
    except Exception as err:  # noqa: BLE001 - any failure here is fatal and worth showing
        return f"Ollama is not answering on {ollama_url}: {err}"

    names = {entry["model"] for entry in tags.get("models", [])}
    if model not in names:
        listed = ", ".join(sorted(names)) or "none"
        return f"Ollama has no model {model!r} (it has: {listed})"
    return None


async def ensure_config_entry(session: Any, headers: dict, base: str,
                              ollama_url: str, apply: bool) -> tuple[str | None, bool]:
    """Return (entry_id, created). entry_id is None in a dry run that would create one."""
    async with session.get(f"{base}/api/config/config_entries/entry",
                           headers=headers) as response:
        entries = await response.json()

    for entry in entries:
        if entry.get("domain") == "ollama":
            return entry["entry_id"], False

    if not apply:
        return None, True

    async with session.post(f"{base}/api/config/config_entries/flow", headers=headers,
                            json={"handler": "ollama", "show_advanced_options": True}) as response:
        flow = await response.json()
    if "flow_id" not in flow:
        raise RuntimeError(f"could not start the ollama config flow: {flow}")

    async with session.post(f"{base}/api/config/config_entries/flow/{flow['flow_id']}",
                            headers=headers, json={"url": ollama_url}) as response:
        result = await response.json()

    if result.get("type") != "create_entry":
        raise RuntimeError(f"config flow did not create an entry: {result}")
    return result["result"]["entry_id"], True


async def wait_until_loaded(session: Any, headers: dict, base: str, entry_id: str) -> None:
    """The subentry flow aborts with entry_not_loaded if we get there too early."""
    for _ in range(30):
        async with session.get(f"{base}/api/config/config_entries/entry",
                               headers=headers) as response:
            entries = await response.json()
        for entry in entries:
            if entry["entry_id"] == entry_id and entry.get("state") == "loaded":
                return
        await asyncio.sleep(1)
    raise RuntimeError(f"config entry {entry_id} never reached state 'loaded'")


async def ensure_subentry(session: Any, headers: dict, base: str, entry_id: str,
                          existing: set[str], want: dict, apply: bool) -> bool:
    """Create one subentry if no subentry of that title exists. Returns True if created."""
    if want["name"] in existing:
        return False
    if not apply:
        return True

    # Adding a subentry reloads the config entry, and a flow opened while the
    # entry is reloading is discarded - the second POST then comes back
    # "Invalid flow specified". So settle first, then open the flow.
    await wait_until_loaded(session, headers, base, entry_id)

    async with session.post(f"{base}/api/config/config_entries/subentries/flow",
                            headers=headers,
                            json={"handler": [entry_id, want["type"]]}) as response:
        flow = await response.json()
    if "flow_id" not in flow:
        raise RuntimeError(f"could not start the {want['type']} subentry flow: {flow}")

    payload = {"name": want["name"], **want["data"]}
    async with session.post(
        f"{base}/api/config/config_entries/subentries/flow/{flow['flow_id']}",
        headers=headers, json=payload,
    ) as response:
        result = await response.json()

    if result.get("type") not in ("create_entry", "abort"):
        raise RuntimeError(f"{want['name']}: subentry flow returned {json.dumps(result)[:400]}")
    if result.get("type") == "abort":
        raise RuntimeError(f"{want['name']}: subentry flow aborted - {result.get('reason')}")
    return True


async def reconfigure_subentry(session: Any, headers: dict, base: str, entry_id: str,
                               subentry_id: str, want: dict, apply: bool) -> None:
    """Push the settings in `want` onto a subentry that already exists.

    Creation is not enough to make this script the source of truth: a setting
    changed here would never reach a board where the subentry was made by an
    earlier run. The reconfigure flow is the same form as the create flow, and
    takes no `name` - the title is fixed once the subentry exists.
    """
    if not apply:
        return

    await wait_until_loaded(session, headers, base, entry_id)

    async with session.post(f"{base}/api/config/config_entries/subentries/flow",
                            headers=headers,
                            json={"handler": [entry_id, want["type"]],
                                  "subentry_id": subentry_id}) as response:
        flow = await response.json()
    if "flow_id" not in flow:
        raise RuntimeError(f"could not start the {want['name']} reconfigure flow: {flow}")

    async with session.post(
        f"{base}/api/config/config_entries/subentries/flow/{flow['flow_id']}",
        headers=headers, json=dict(want["data"]),
    ) as response:
        result = await response.json()

    # A reconfigure ends in abort/reconfigure_successful, not create_entry.
    if result.get("type") == "form" and result.get("errors"):
        raise RuntimeError(f"{want['name']}: reconfigure rejected - {result['errors']}")
    if result.get("type") not in ("abort", "create_entry"):
        raise RuntimeError(f"{want['name']}: reconfigure returned {json.dumps(result)[:300]}")


async def subentry_titles(ha: HomeAssistantWS, entry_id: str) -> set[str]:
    """Titles of the subentries this config entry already has.

    Deliberately not the REST entry listing: that serializes `subentries` as
    null however many the entry has, so it silently reports every subentry as
    missing and this script would create a second copy on every run.
    """
    subentries = await ha.call(type="config_entries/subentries/list", entry_id=entry_id)
    return {sub["title"] for sub in subentries}


async def entity_for_subentry(ha: HomeAssistantWS, entry_id: str,
                              title: str, domain: str) -> str | None:
    """Find the entity a named subentry produced, via the entity registry."""
    registry = await ha.call(type="config/entity_registry/list")
    subentry_ids = await _subentry_ids(ha, entry_id)
    wanted = subentry_ids.get(title)
    if wanted is None:
        return None
    for entity in registry:
        if entity.get("config_subentry_id") == wanted and entity["entity_id"].startswith(f"{domain}."):
            return entity["entity_id"]
    return None


async def _subentry_ids(ha: HomeAssistantWS, entry_id: str) -> dict[str, str]:
    subentries = await ha.call(type="config_entries/subentries/list", entry_id=entry_id)
    return {sub["title"]: sub["subentry_id"] for sub in subentries}


async def ensure_pipelines(ha: HomeAssistantWS, answer_agent: str | None,
                           control_agent: str | None, apply: bool) -> list[str]:
    """Turn on local-intents-first for the default pipeline, add a control pipeline."""
    actions: list[str] = []
    listing = await ha.call(type="assist_pipeline/pipeline/list")
    pipelines = listing["pipelines"] if isinstance(listing, dict) else listing

    default = next((p for p in pipelines if p["name"] == "Home Assistant"), None)
    if default is None and pipelines:
        default = pipelines[0]

    if default is not None:
        needs_local = not default.get("prefer_local_intents")
        needs_agent = answer_agent is not None and default.get("conversation_engine") != answer_agent
        if needs_local or needs_agent:
            changes = []
            if needs_local:
                changes.append("prefer_local_intents=true")
            if needs_agent:
                changes.append(f"conversation_engine={answer_agent}")
            actions.append(f"update pipeline {default['name']!r}: {', '.join(changes)}")
            if apply:
                fields = {k: v for k, v in default.items() if k != "id"}
                fields["prefer_local_intents"] = True
                if answer_agent:
                    fields["conversation_engine"] = answer_agent
                    fields["conversation_language"] = default.get("conversation_language") or "en"
                await ha.call(type="assist_pipeline/pipeline/update",
                              pipeline_id=default["id"], **fields)

    if control_agent and not any(p["name"] == "Local Qwen (control)" for p in pipelines):
        actions.append("create pipeline 'Local Qwen (control)'")
        if apply and default is not None:
            fields = {k: v for k, v in default.items() if k not in ("id", "name")}
            fields.update({
                "name": "Local Qwen (control)",
                "conversation_engine": control_agent,
                "conversation_language": default.get("conversation_language") or "en",
                # The model is the point of this pipeline; letting the matcher
                # answer first would defeat it.
                "prefer_local_intents": False,
            })
            await ha.call(type="assist_pipeline/pipeline/create", **fields)

    return actions


async def run(args: argparse.Namespace) -> int:
    try:
        import aiohttp
    except ImportError:
        print("aiohttp is required (use ~/smart_home_AI/.venv/bin/python)", file=sys.stderr)
        return 1

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    base = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    apply = args.apply

    async with aiohttp.ClientSession() as session:
        problem = await preflight(session, args.ollama_url, args.model)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        print(f"Ollama on {args.ollama_url} is serving {args.model}")

        entry_id, created = await ensure_config_entry(session, headers, base,
                                                      args.ollama_url, apply)
        if created:
            print(f"{'created' if apply else 'would create'} the ollama config entry "
                  f"-> {args.ollama_url}")
        else:
            print(f"ollama config entry already exists ({entry_id})")

        if entry_id is None:
            print("\nDry run: the config entry does not exist yet, so the subentries and\n"
                  "pipelines below cannot be inspected. Re-run with --apply.")
            return 0

        if apply:
            await wait_until_loaded(session, headers, base, entry_id)

        async with session.ws_connect(ws_url, heartbeat=30) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("Home Assistant rejected the token", file=sys.stderr)
                return 1
            ha = HomeAssistantWS(ws)

            existing = await subentry_titles(ha, entry_id)
            for want in subentry_plan(args.model):
                made = await ensure_subentry(session, headers, base, entry_id,
                                             existing, want, apply)
                if made:
                    verb = "created" if apply else "would create"
                elif args.reconfigure:
                    ids = await _subentry_ids(ha, entry_id)
                    await reconfigure_subentry(session, headers, base, entry_id,
                                               ids[want["name"]], want, apply)
                    verb = "reconfigured" if apply else "would reconfigure"
                else:
                    verb = "already exists:"
                print(f"  {verb} {want['type']} {want['name']!r} - {want['why']}")

            answer_agent = await entity_for_subentry(ha, entry_id, "Local Qwen", "conversation")
            control_agent = await entity_for_subentry(ha, entry_id, "Local Qwen Control", "conversation")
            task_entity = await entity_for_subentry(ha, entry_id, "Local Qwen Task", "ai_task")
            for label, value in (("answering agent", answer_agent),
                                 ("controlling agent", control_agent),
                                 ("AI task entity", task_entity)):
                print(f"  {label}: {value or '(not created yet)'}")

            for action in await ensure_pipelines(ha, answer_agent, control_agent, apply):
                print(f"  {'did' if apply else 'would'}: {action}")

    if not apply:
        print("\nNothing was written. Re-run with --apply.")
    return 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="without this, nothing is changed")
    ap.add_argument("--reconfigure", action="store_true",
                    help="also push the settings above onto subentries that already "
                         "exist, so this script stays the source of truth for them")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL",
                                                    "http://127.0.0.1:8123"))
    ap.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL))
    ap.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
