"""Conversation agent: Home Assistant's own matcher first, the resolver on a miss."""

from __future__ import annotations

import logging
import time

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.ulid import ulid_now

from . import resolver

_LOGGER = logging.getLogger(__name__)

DEFAULT_AGENT = "conversation.home_assistant"
SWITCHABLE_DOMAINS = ("light", "switch", "fan")
# A question left unanswered this long is stale; the next utterance starts over.
PENDING_TTL_SECONDS = 30
# Only these mean "the matcher did not know the device or the sentence";
# anything else (a device that failed, a timer error) is Home Assistant's answer.
MISS_CODES = {
    intent.IntentResponseErrorCode.NO_VALID_TARGETS,
    intent.IntentResponseErrorCode.NO_INTENT_MATCH,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([VoiceResolverAgent(entry)])


class VoiceResolverAgent(conversation.ConversationEntity):
    # A fixed name without a device, so the entity id is predictable
    # (conversation.voice_resolver) rather than derived from nothing.
    _attr_has_entity_name = False
    _attr_name = "Voice resolver"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = entry.entry_id
        self._pending: dict[str, tuple[float, resolver.Decision]] = {}

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        conversation_id = user_input.conversation_id or ulid_now()

        pending = self._take_pending(conversation_id)
        if pending is not None:
            decision = resolver.resolve_reply(user_input.text, pending)
            if decision.kind != "not_a_reply":
                return await self._finish(decision, user_input, conversation_id)

        result = await conversation.async_converse(
            self.hass, user_input.text, conversation_id, user_input.context,
            language=user_input.language, agent_id=DEFAULT_AGENT,
            device_id=user_input.device_id, satellite_id=user_input.satellite_id,
        )
        response = result.response
        if response.response_type != intent.IntentResponseType.ERROR or response.error_code not in MISS_CODES:
            return result

        decision = resolver.resolve(user_input.text, self._candidates())
        _LOGGER.debug("matcher missed %r; resolver decided %s", user_input.text, decision)
        if decision.kind == "not_a_command":
            return result
        return await self._finish(decision, user_input, result.conversation_id or conversation_id)

    def _take_pending(self, conversation_id: str) -> resolver.Decision | None:
        entry = self._pending.pop(conversation_id, None)
        if entry is None or time.monotonic() - entry[0] > PENDING_TTL_SECONDS:
            return None
        return entry[1]

    def _candidates(self) -> list[resolver.Candidate]:
        entities = er.async_get(self.hass)
        devices = dr.async_get(self.hass)
        areas = ar.async_get(self.hass)
        found = []
        for state in self.hass.states.async_all(SWITCHABLE_DOMAINS):
            if not async_should_expose(self.hass, conversation.DOMAIN, state.entity_id):
                continue
            entry = entities.async_get(state.entity_id)
            area_id = entry.area_id if entry else None
            if entry and not area_id and entry.device_id and (device := devices.async_get(entry.device_id)):
                area_id = device.area_id
            area = areas.async_get_area(area_id) if area_id else None
            # The alias set can hold a ComputedNameType placeholder ("use the
            # entity's own name") rather than text; only real strings are names.
            aliases = tuple(sorted(a for a in entry.aliases if isinstance(a, str))) if entry else ()
            found.append(resolver.Candidate(
                entity_id=state.entity_id,
                name=str(state.name),
                aliases=aliases,
                area=area.name if area else None,
            ))
        return found

    async def _finish(self, decision: resolver.Decision, user_input: conversation.ConversationInput,
                      conversation_id: str) -> conversation.ConversationResult:
        response = intent.IntentResponse(language=user_input.language)
        text = resolver.speech(decision)
        if decision.kind == "act":
            target = decision.target
            try:
                await self.hass.services.async_call(
                    target.domain, decision.action, {"entity_id": target.entity_id},
                    blocking=True, context=user_input.context,
                )
            except Exception:  # noqa: BLE001 - the device, not the sentence, failed
                _LOGGER.exception("resolver could not %s %s", decision.action, target.entity_id)
                text = f"I found {target.name}, but it did not respond."
        elif decision.kind in ("ask", "unknown") and decision.options:
            self._pending[conversation_id] = (time.monotonic(), decision)
        response.async_set_speech(text)
        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
            continue_conversation=text.endswith("?"),
        )
