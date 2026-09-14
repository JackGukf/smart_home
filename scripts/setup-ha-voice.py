#!/usr/bin/env python3
"""Give Home Assistant a voice: local speech-to-text and text-to-speech.

Before this, Assist here had no speech at all. The only TTS engine was
`tts.google_translate_en_com`, which is a cloud round trip in an otherwise local
house and dies with the WAN, and there was no STT engine of any kind - so a
voice satellite could wake, listen, and then have nothing to transcribe with.

`docker-compose.voice.yml` runs the two Wyoming services on loopback. This wires
them into Home Assistant and points the default Assist pipeline at them:

  * a `wyoming` config entry for Whisper  (127.0.0.1:10300) -> stt.*
  * a `wyoming` config entry for Piper    (127.0.0.1:10200) -> tts.*
  * the default pipeline's stt_engine and tts_engine set to those

## Why the add-ons are not an option here

Every Home Assistant voice guide starts "install the Whisper add-on". This
install is the plain Docker container, not Home Assistant OS and not Supervised,
so there is no Supervisor and no add-on store. The add-ons are wrappers around
exactly these Wyoming services, so running them directly is the same thing
without the wrapper.

## A pipeline of its own for the satellite, with no model in it

The default pipeline falls back to Qwen for anything the matcher cannot parse,
which is right for typed Assist and wrong for a voice. Measured on the panel on
2026-09-13: a mishearing waited 17 s and 57 s in silence on the model, which
then answered the noise ("I don't recognize Naboo as a device"). So the
satellite gets a "Voice Panel" pipeline - the same Whisper and Piper, Home
Assistant's own agent only - and its pipeline select is pointed at it. The
default pipeline, and the Qwen agents, stay scripts/setup-ha-ollama.py's
business and are not touched.

## The wake word said twice

The satellite gives no sign that it woke, so people say the wake word again,
and Whisper transcribes that as the command ("Okay, Naboo."). A sentence-trigger
automation answers exactly those transcripts with nothing, so a repeat is
silently ignored instead of becoming "Sorry, I couldn't understand that".

Idempotent. Re-running reports what is already there and changes nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SERVICES = [
    ("Whisper (speech to text)", "127.0.0.1", 10300),
    ("Piper (text to speech)", "127.0.0.1", 10200),
]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def port_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


# What each service calls itself, which is what wyoming titles the entry.
SERVICE_TITLES = {10300: "faster-whisper", 10200: "piper"}


async def existing_wyoming_entries(session, headers, base) -> dict[str, str]:
    """Map service title -> entry_id for wyoming entries already configured.

    Matching on the title rather than the address, because there is nothing
    better to match on: wyoming leaves unique_id as None, so Home Assistant will
    happily add the same host and port twice, and the config entries API does
    not expose an entry's data, so the host and port cannot be read back.

    The cost of getting this wrong is not a harmless no-op. Adding Whisper twice
    produces a second stt.faster_whisper_2 entity and a second container-facing
    connection, and the pipeline then points at whichever one the script picked
    last - which is how this script created a duplicate pair on its second run
    before this existed.
    """
    async with session.get(f"{base}/api/config/config_entries/entry",
                           headers=headers) as response:
        entries = await response.json()

    return {str(e.get("title")): e["entry_id"]
            for e in entries if e.get("domain") == "wyoming"}


async def ensure_entry(session, headers, base, host: str, port: int, apply: bool):
    async with session.post(f"{base}/api/config/config_entries/flow", headers=headers,
                            json={"handler": "wyoming", "show_advanced_options": True}) as response:
        flow = await response.json()
    if "flow_id" not in flow:
        raise RuntimeError(f"could not start the wyoming config flow: {flow}")

    async with session.post(f"{base}/api/config/config_entries/flow/{flow['flow_id']}",
                            headers=headers,
                            json={"host": host, "port": port}) as response:
        result = await response.json()

    if result.get("type") != "create_entry":
        raise RuntimeError(f"wyoming flow for {host}:{port} did not create an entry: {result}")
    return result["result"]["entry_id"]


async def engines(session, headers, base) -> tuple[list[str], list[str]]:
    async with session.get(f"{base}/api/states", headers=headers) as response:
        states = await response.json()
    stt = sorted(s["entity_id"] for s in states if s["entity_id"].startswith("stt."))
    tts = sorted(s["entity_id"] for s in states if s["entity_id"].startswith("tts."))
    return stt, tts


class HomeAssistantWS:
    """Minimal Home Assistant WebSocket client, matching the other scripts here."""

    def __init__(self, ws) -> None:
        self._ws = ws
        self._id = 0

    async def call(self, **payload):
        self._id += 1
        await self._ws.send_json({"id": self._id, **payload})
        while True:
            message = await self._ws.receive_json()
            if message.get("id") != self._id:
                continue
            if not message.get("success"):
                error = message.get("error", {})
                raise RuntimeError(f"{payload.get('type')}: {error.get('message', message)}")
            return message.get("result")


def best_language(supported: list[str], want: str = "en") -> str | None:
    """Pick a language the engine actually offers.

    Not cosmetic. Piper's voices are regional - it advertises en_US and en_GB
    and no bare "en" - so setting the pipeline to "en" makes Home Assistant
    refuse every announcement with "Language \'en\' not supported", which
    surfaces as a 500 from assist_satellite.announce and says nothing about the
    cause. Whisper, meanwhile, does take a bare "en". One hardcoded value cannot
    be right for both.
    """
    if not supported:
        return None
    if want in supported:
        return want
    prefix = want.lower().replace("-", "_") + "_"
    variants = [l for l in supported if l.lower().replace("-", "_").startswith(prefix)]
    if not variants:
        return None
    # en_US ahead of en_GB when both exist, otherwise whatever is offered.
    preferred = f"{want}_{want.upper()}" if want == "en" else None
    for candidate in ("en_US", preferred):
        if candidate and candidate in variants:
            return candidate
    return sorted(variants)[0]


async def engine_languages(ha: HomeAssistantWS, kind: str) -> dict[str, list[str]]:
    result = await ha.call(type=f"{kind}/engine/list")
    providers = (result or {}).get("providers", [])
    return {p.get("engine_id"): (p.get("supported_languages") or []) for p in providers}


async def point_pipeline_at(ha: HomeAssistantWS, stt_entity: str, tts_entity: str,
                            apply: bool) -> list[str]:
    listing = await ha.call(type="assist_pipeline/pipeline/list")
    pipelines = listing["pipelines"] if isinstance(listing, dict) else listing
    default = next((p for p in pipelines if p["name"] == "Home Assistant"), None)
    if default is None and pipelines:
        default = pipelines[0]
    if default is None:
        return ["no Assist pipeline to update"]

    stt_langs = await engine_languages(ha, "stt")
    tts_langs = await engine_languages(ha, "tts")
    stt_language = best_language(stt_langs.get(stt_entity, []))
    tts_language = best_language(tts_langs.get(tts_entity, []))
    if not stt_language or not tts_language:
        return [f"{stt_entity} or {tts_entity} offers no English; pipeline left alone"]

    changes = []
    if default.get("stt_engine") != stt_entity:
        changes.append(f"stt_engine={stt_entity}")
    if default.get("tts_engine") != tts_entity:
        changes.append(f"tts_engine={tts_entity}")
    if default.get("stt_language") != stt_language:
        changes.append(f"stt_language={stt_language}")
    if default.get("tts_language") != tts_language:
        changes.append(f"tts_language={tts_language}")
    if not changes:
        return []

    if apply:
        fields = {k: v for k, v in default.items() if k != "id"}
        fields["stt_engine"] = stt_entity
        fields["stt_language"] = stt_language
        fields["tts_engine"] = tts_entity
        fields["tts_language"] = tts_language
        fields["tts_voice"] = None
        await ha.call(type="assist_pipeline/pipeline/update",
                      pipeline_id=default["id"], **fields)
    return [f"pipeline {default['name']!r}: {', '.join(changes)}"]


VOICE_PIPELINE_NAME = "Voice Panel"
# Home Assistant's built-in agent: the local intent matcher and nothing behind it.
VOICE_AGENT = "conversation.home_assistant"
SATELLITE_PIPELINE_SELECT = "select.voice_panel_assistant"


def voice_pipeline_fields(stt_entity: str, stt_language: str,
                          tts_entity: str, tts_language: str) -> dict:
    return {
        "name": VOICE_PIPELINE_NAME,
        "language": "en",
        "conversation_engine": VOICE_AGENT,
        "conversation_language": "en",
        "prefer_local_intents": False,  # there is nothing non-local to prefer over
        "stt_engine": stt_entity,
        "stt_language": stt_language,
        "tts_engine": tts_entity,
        "tts_language": tts_language,
        "tts_voice": None,
        "wake_word_entity": None,
        "wake_word_id": None,
    }


async def ensure_voice_pipeline(ha: HomeAssistantWS, stt_entity: str, tts_entity: str,
                                apply: bool) -> list[str]:
    stt_language = best_language((await engine_languages(ha, "stt")).get(stt_entity, []))
    tts_language = best_language((await engine_languages(ha, "tts")).get(tts_entity, []))
    if not stt_language or not tts_language:
        return [f"{stt_entity} or {tts_entity} offers no English; voice pipeline left alone"]
    want = voice_pipeline_fields(stt_entity, stt_language, tts_entity, tts_language)

    listing = await ha.call(type="assist_pipeline/pipeline/list")
    pipelines = listing["pipelines"] if isinstance(listing, dict) else listing
    have = next((p for p in pipelines if p["name"] == VOICE_PIPELINE_NAME), None)
    if have is None:
        if apply:
            await ha.call(type="assist_pipeline/pipeline/create", **want)
        return [f"create pipeline {VOICE_PIPELINE_NAME!r} (agent {VOICE_AGENT})"]
    changes = [f"{k}={v}" for k, v in want.items() if have.get(k) != v]
    if not changes:
        return []
    if apply:
        await ha.call(type="assist_pipeline/pipeline/update", pipeline_id=have["id"], **want)
    return [f"pipeline {VOICE_PIPELINE_NAME!r}: {', '.join(changes)}"]


async def point_satellite_at_voice_pipeline(session, headers, base, apply: bool) -> list[str]:
    async with session.get(f"{base}/api/states/{SATELLITE_PIPELINE_SELECT}",
                           headers=headers) as response:
        if response.status == 404:
            return [f"{SATELLITE_PIPELINE_SELECT} does not exist; satellite left alone"]
        state = await response.json()
    if state["state"] == VOICE_PIPELINE_NAME:
        return []
    # The select lists pipelines as they exist, so on a dry run before the
    # pipeline is created the option is legitimately absent.
    if apply and VOICE_PIPELINE_NAME not in state["attributes"].get("options", []):
        return [f"{SATELLITE_PIPELINE_SELECT} does not offer {VOICE_PIPELINE_NAME!r} yet"]
    if apply:
        async with session.post(f"{base}/api/services/select/select_option", headers=headers,
                                json={"entity_id": SATELLITE_PIPELINE_SELECT,
                                      "option": VOICE_PIPELINE_NAME}) as response:
            response.raise_for_status()
    return [f"{SATELLITE_PIPELINE_SELECT}: {state['state']!r} -> {VOICE_PIPELINE_NAME!r}"]


WAKE_ECHO_AUTOMATION_ID = "voice_ignore_repeated_wake_word"
# What Whisper base.en makes of "Okay Nabu" - "Okay, Naboo." is verbatim from the
# pipeline debug record. The matcher ignores case and punctuation.
WAKE_ECHO_PHRASES = ["okay nabu", "ok nabu", "okay naboo", "ok naboo",
                     "okay nabu nabu", "okay naboo naboo"]


def wake_echo_automation() -> dict:
    return {
        "alias": "Voice: ignore the wake word said again as the command",
        "description": "Managed by scripts/setup-ha-voice.py. The satellite gives no "
                       "sign it woke, so people repeat the wake word; answer that with "
                       "nothing rather than an error.",
        "triggers": [{"trigger": "conversation", "command": WAKE_ECHO_PHRASES}],
        "conditions": [],
        "actions": [{"set_conversation_response": ""}],
        "mode": "parallel",
    }


async def ensure_wake_echo_automation(session, headers, base, apply: bool) -> list[str]:
    url = f"{base}/api/config/automation/config/{WAKE_ECHO_AUTOMATION_ID}"
    async with session.get(url, headers=headers) as response:
        current = await response.json() if response.status == 200 else None
    want = wake_echo_automation()
    if current is not None and all(current.get(k) == v for k, v in want.items()):
        return []
    if apply:
        # Home Assistant's config API validates and reloads, so a bad trigger is
        # refused here rather than written and left to fail.
        async with session.post(url, headers=headers, json=want) as response:
            if response.status != 200:
                raise RuntimeError(f"automation refused {response.status}: "
                                   f"{(await response.text())[:400]}")
    return [f"{'update' if current else 'create'} automation {WAKE_ECHO_AUTOMATION_ID!r}"]


# --- what Assist can reach -----------------------------------------------------

# Our own Matter bridge exports the dashboard's devices to Apple Home, and it is
# commissioned into Home Assistant as well - so each bridged Kasa switch appears
# twice, as the native tplink entity and as a Matter entity of the same name.
# Assist then refuses both: "Sorry, there are multiple devices called Kitchen
# light switch". The Matter copy is hidden from Assist where a native twin
# exists; a bridged device with no twin (Stick S3) is only reachable that way,
# so it stays.
BRIDGE_VIA_DEVICE = "Dashboard Bridge"
JUNK_MANUFACTURERS = frozenset({"TEST_VENDOR"})  # a leftover Matter test light
SWITCHABLE_DOMAINS = frozenset({"light", "switch", "fan"})
# Devices voice must never switch, matched by name because they may not be in
# Home Assistant yet (and new entities are exposed to Assist by default). The
# "Raspberry PI" plug powers the wall panel: a misheard "turn off" would cut it.
NEVER_EXPOSE_NAMES = frozenset({"raspberry pi"})
# One device added by three integrations, same name, so voice cannot choose.
# LLANO-S450 is kept through Apple TV (media_player.llano_s450_289cb541_2); the
# Google Cast and DLNA copies are hidden from Assist, not removed.
NEVER_EXPOSE_ENTITY_IDS = frozenset({"media_player.llano_s450_289cb541",
                                     "media_player.llano_s450_289cb541_3"})
# Readings people ask about by room. Batteries, tamper, signal and the like are
# left out on purpose - they are noise to a voice and are on the dashboard.
READING_CLASSES = {
    "binary_sensor": frozenset({"door", "window", "opening", "moisture", "smoke", "gas",
                                "carbon_monoxide", "occupancy", "motion"}),
    "sensor": frozenset({"temperature", "humidity", "illuminance"}),
}


def plan_exposure(entities: list[dict], devices: list[dict], states: dict[str, dict],
                  exposed: dict[str, dict], never_expose_names: frozenset[str] = NEVER_EXPOSE_NAMES
                  ) -> tuple[list[str], list[str]]:
    """Return (entity ids to expose to Assist, entity ids to hide from it)."""
    devices_by_id = {d["id"]: d for d in devices}

    def friendly(entity: dict) -> str:
        attributes = (states.get(entity["entity_id"]) or {}).get("attributes") or {}
        return str(attributes.get("friendly_name") or entity.get("name")
                   or entity.get("original_name") or "").strip().lower()

    def is_exposed(entity_id: str) -> bool:
        return bool((exposed.get(entity_id) or {}).get("conversation"))

    live = [e for e in entities if not e.get("disabled_by")]
    native_switchables = {friendly(e) for e in live
                          if e["platform"] != "matter"
                          and e["entity_id"].split(".")[0] in SWITCHABLE_DOMAINS}

    expose: list[str] = []
    hide: list[str] = []
    for entity in live:
        entity_id = entity["entity_id"]
        domain = entity_id.split(".")[0]
        device = devices_by_id.get(entity.get("device_id")) or {}
        via = devices_by_id.get(device.get("via_device_id")) or {}
        bridged_twin = (entity["platform"] == "matter"
                        and (via.get("name_by_user") or via.get("name")) == BRIDGE_VIA_DEVICE
                        and friendly(entity) in native_switchables)
        device_name = str(device.get("name_by_user") or device.get("name") or "").strip().lower()
        protected = (friendly(entity) in never_expose_names or device_name in never_expose_names
                     or entity_id in NEVER_EXPOSE_ENTITY_IDS)
        # An entity Home Assistant itself hides - notably the original switch
        # behind a "show as light" wrapper - shares its name with what replaced
        # it, so leaving it exposed recreates "multiple devices called ...".
        hidden = bool(entity.get("hidden_by"))
        if bridged_twin or device.get("manufacturer") in JUNK_MANUFACTURERS or protected or hidden:
            if is_exposed(entity_id):
                hide.append(entity_id)
            continue
        device_class = ((states.get(entity_id) or {}).get("attributes") or {}).get("device_class")
        if (device_class in READING_CLASSES.get(domain, ())
                and not entity.get("entity_category")
                and not entity.get("hidden_by")
                and not is_exposed(entity_id)):
            expose.append(entity_id)
    return sorted(expose), sorted(hide)


# Wall switches that switch lights but are filed as `switch` by the tplink
# integration (HS200), so "which lights are on" and "turn off the lights in the
# living room" skip them. Home Assistant's own "show as light" helper wraps each
# in a light entity and hides the original. Plugs stay switches on purpose.
WALL_SWITCHES_AS_LIGHTS = ("switch.master_bedroom_light", "switch.living_room_switch_2")


def switches_already_wrapped(entities: list[dict]) -> set[str]:
    """Switch entity ids that already have a switch_as_x wrapper.

    Matched through the device registry, not by name: the wrapper is created on
    the switch's own device, while an entry title or friendly name can differ
    from the switch's (the first version matched titles, missed, and a second
    --apply started a second wrapper for each switch).
    """
    wrapped_devices = {e.get("device_id") for e in entities
                       if e.get("platform") == "switch_as_x" and e.get("device_id")}
    return {e["entity_id"] for e in entities
            if e["entity_id"].startswith("switch.") and e.get("platform") != "switch_as_x"
            and e.get("device_id") in wrapped_devices}


async def ensure_wall_switches_as_lights(ha: HomeAssistantWS, session, headers, base,
                                         apply: bool) -> list[str]:
    entities = await ha.call(type="config/entity_registry/list")
    wrapped = switches_already_wrapped(entities)
    known = {e["entity_id"]: e for e in entities}

    lines = []
    for entity_id in WALL_SWITCHES_AS_LIGHTS:
        if entity_id not in known:
            lines.append(f"{entity_id} does not exist; not shown as a light")
            continue
        entity = known[entity_id]
        name = entity.get("name") or entity.get("original_name") or entity_id
        if entity_id in wrapped:
            continue
        if apply:
            async with session.post(f"{base}/api/config/config_entries/flow", headers=headers,
                                    json={"handler": "switch_as_x"}) as response:
                flow = await response.json()
            async with session.post(f"{base}/api/config/config_entries/flow/{flow['flow_id']}",
                                    headers=headers,
                                    json={"entity_id": entity_id, "target_domain": "light"}) as response:
                result = await response.json()
            if result.get("type") != "create_entry":
                raise RuntimeError(f"switch_as_x refused {entity_id}: {result}")
        lines.append(f"show {entity_id} ({name}) as a light")
    return lines


async def ensure_assist_exposure(ha: HomeAssistantWS, apply: bool) -> list[str]:
    entities = await ha.call(type="config/entity_registry/list")
    devices = await ha.call(type="config/device_registry/list")
    states = {s["entity_id"]: s for s in await ha.call(type="get_states")}
    exposed = (await ha.call(type="homeassistant/expose_entity/list") or {}).get("exposed_entities", {})
    expose, hide = plan_exposure(entities, devices, states, exposed)
    lines = []
    for ids, should_expose, why in ((hide, False, "hide from Assist (duplicate or test device)"),
                                    (expose, True, "expose to Assist (room reading)")):
        if not ids:
            continue
        if apply:
            await ha.call(type="homeassistant/expose_entity", assistants=["conversation"],
                          entity_ids=ids, should_expose=should_expose)
        lines.append(f"{why}: {', '.join(ids)}")
    return lines


CUSTOM_SENTENCES = PROJECT_ROOT / "configs" / "homeassistant" / "custom_sentences" / "en"


def ensure_custom_sentences(config_dir: Path, apply: bool) -> list[str]:
    """Copy the repo's custom sentences into Home Assistant's config directory.

    With no model behind the voice pipeline, the matcher's own sentences are all
    it understands, and they miss ordinary phrasings ("what day is today"). The
    files only add sentences for Home Assistant's built-in intents.
    """
    if not config_dir.is_dir():
        return [f"Home Assistant config directory {config_dir} not found; sentences left alone"]
    target = config_dir / "custom_sentences" / "en"
    changes = []
    for source in sorted(CUSTOM_SENTENCES.glob("*.yaml")):
        dest = target / source.name
        text = source.read_text(encoding="utf-8")
        existed = dest.is_file()
        if existed and dest.read_text(encoding="utf-8") == text:
            continue
        if apply:
            target.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        changes.append(f"{'update' if existed else 'install'} sentences {dest}")
    return changes


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

    # Fail here rather than half way through a config flow.
    missing = [f"{name} on {host}:{port}" for name, host, port in SERVICES
               if not port_open(host, port)]
    if missing:
        print("not answering: " + "; ".join(missing), file=sys.stderr)
        print("start them with:  docker compose -f docker-compose.voice.yml up -d",
              file=sys.stderr)
        return 1
    for name, host, port in SERVICES:
        print(f"{name} is answering on {host}:{port}")

    base = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    apply = args.apply

    async with aiohttp.ClientSession() as session:
        have = await existing_wyoming_entries(session, headers, base)
        for name, host, port in SERVICES:
            key = SERVICE_TITLES[port]
            if key in have:
                print(f"wyoming entry {key!r} ({host}:{port}) already exists ({have[key]})")
                continue
            if not apply:
                print(f"would create a wyoming entry for {key}")
                continue
            entry_id = await ensure_entry(session, headers, base, host, port, apply)
            print(f"created the wyoming entry for {key} ({entry_id})")

        if apply:
            await asyncio.sleep(4)  # let the entities register

        stt, tts = await engines(session, headers, base)
        print(f"speech to text engines: {', '.join(stt) or 'none'}")
        print(f"text to speech engines: {', '.join(tts) or 'none'}")

        local_stt = next((e for e in stt if "whisper" in e or "faster" in e), None) or (stt[0] if stt else None)
        local_tts = next((e for e in tts if "piper" in e), None)
        if not local_stt or not local_tts:
            print("could not identify the local engines; pipeline left alone",
                  file=sys.stderr)
            return 0 if not apply else 1

        async with session.ws_connect(ws_url) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("websocket auth failed", file=sys.stderr)
                return 1
            ha = HomeAssistantWS(ws)
            for line in await point_pipeline_at(ha, local_stt, local_tts, apply):
                print(("" if apply else "would ") + line)
            for line in await ensure_voice_pipeline(ha, local_stt, local_tts, apply):
                print(("" if apply else "would ") + line)

        async with session.ws_connect(ws_url) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("websocket auth failed", file=sys.stderr)
                return 1
            ha = HomeAssistantWS(ws)
            wall_changes = await ensure_wall_switches_as_lights(ha, session, headers, base, apply)
            for line in wall_changes:
                print(("" if apply else "would ") + line)
            if apply and any(line.startswith("show ") for line in wall_changes):
                await asyncio.sleep(4)  # let the wrapper entities register before planning exposure
            for line in await ensure_assist_exposure(ha, apply):
                print(("" if apply else "would ") + line)

        if apply:
            await asyncio.sleep(2)  # the select picks up the new pipeline as an option
        for line in await point_satellite_at_voice_pipeline(session, headers, base, apply):
            print(("" if apply else "would ") + line)
        for line in await ensure_wake_echo_automation(session, headers, base, apply):
            print(("" if apply else "would ") + line)

        sentence_changes = ensure_custom_sentences(Path(args.config_dir), apply)
        for line in sentence_changes:
            print(("" if apply else "would ") + line)
        if apply and sentence_changes and "not found" not in sentence_changes[0]:
            # Custom sentences are read when conversation loads; reload picks
            # them up without restarting Home Assistant.
            async with session.post(f"{base}/api/services/conversation/reload",
                                    headers=headers, json={}) as response:
                response.raise_for_status()
            print("reloaded conversation")

    if not apply:
        print("\ndry run - nothing changed. Re-run with --apply.")
    return 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123"))
    ap.add_argument("--config-dir",
                    default=os.getenv("HOME_ASSISTANT_CONFIG_DIR",
                                      "/home/orangepi/homeassistant-config"),
                    help="Home Assistant's config directory, for custom sentences")
    ap.add_argument("--apply", action="store_true",
                    help="make the changes (default is a dry run)")
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
