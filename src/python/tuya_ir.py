"""Tuya IR hubs, driven locally: learn a remote's buttons, send them, and offer
them to Home Assistant.

A Tuya "Smart IR" hub is a blaster with no state of its own - it sends the
codes it is given. The codes the Smart Life app learned live in Tuya's cloud,
and the cloud is not something to depend on: the project's Tuya IoT Core
subscription expired on 2026-09-18 and took every cloud call with it. So the
codes are learned again, locally: the hub goes into study mode, you press the
button on the original remote with it pointed at the hub, and the code it
reports is kept here, on the board.

Sending is local too (tinytuya, the hub's local key), so a learned button
works with the internet down.

Each learned button is offered to Home Assistant as a `button` entity through
MQTT discovery - `button.<hub>_<button>` - so a script (Movie mode) can press
it. Pressing it in Home Assistant publishes to a command topic this module
listens on, and the IR goes out from here.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

log = logging.getLogger("smart_home.tuya_ir")

LEARN_TIMEOUT_S = 20
MAX_CODE_LENGTH = 8192
MAX_NAME_LENGTH = 40
MAX_BUTTONS_PER_HUB = 40

DISCOVERY_PREFIX = "homeassistant"
COMMAND_ROOT = "smart_home_ai/ir"
AVAILABILITY_TOPIC = f"{COMMAND_ROOT}/status"


class IRError(ValueError):
    """A request this module refuses: an unknown hub or button, a bad name or code."""


@dataclass(frozen=True)
class IRHub:
    id: str
    name: str
    device_id: str
    host: str
    local_key: str
    version: float


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def load_hubs(config_path: Path, env: dict[str, str] | None = None) -> list[IRHub]:
    """The Tuya devices configured as IR hubs that can be reached locally."""
    env = os.environ if env is None else env
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    hubs = []
    for item in (payload.get("tuya") or {}).get("devices") or []:
        if item.get("enabled") is False or "ir" not in str(item.get("model") or "").lower().split():
            continue
        key = str(item.get("local_key") or env.get(str(item.get("local_key_env") or ""), "") or "").strip()
        if not (item.get("device_id") and item.get("host") and key):
            continue
        hubs.append(IRHub(id=slug(item["name"]), name=str(item["name"]), device_id=str(item["device_id"]),
                          host=str(item["host"]), local_key=key, version=float(item.get("version") or 3.3)))
    return hubs


def clean_name(name: Any) -> str:
    text = " ".join(str(name or "").split())
    if not text or len(text) > MAX_NAME_LENGTH or not slug(text):
        raise IRError(f"a button name is 1 to {MAX_NAME_LENGTH} characters, with a letter or digit")
    return text


def clean_code(code: Any) -> str:
    """A learned code is base64 from the hub. Anything else is refused before it
    reaches the hub - the code is sent as the hub's own payload."""
    text = str(code or "").strip()
    if not text or len(text) > MAX_CODE_LENGTH:
        raise IRError("not an IR code")
    try:
        base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as error:
        raise IRError("not an IR code") from error
    return text


class ButtonStore:
    """Learned buttons, per hub, in one JSON file beside the device config."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict[str, dict[str, Any]]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def buttons(self, hub_id: str) -> list[dict[str, Any]]:
        with self._lock:
            hub = self._read().get(hub_id, {})
        return [{"id": key, "name": value["name"], "learned_at": value.get("learned_at")}
                for key, value in sorted(hub.items(), key=lambda kv: kv[1].get("learned_at") or 0)]

    def code(self, hub_id: str, button_id: str) -> str:
        with self._lock:
            entry = self._read().get(hub_id, {}).get(button_id)
        if not entry:
            raise IRError("no such button")
        return entry["code"]

    def save(self, hub_id: str, name: str, code: str) -> dict[str, Any]:
        name, code = clean_name(name), clean_code(code)
        button_id = slug(name)
        with self._lock:
            data = self._read()
            hub = data.setdefault(hub_id, {})
            if button_id not in hub and len(hub) >= MAX_BUTTONS_PER_HUB:
                raise IRError(f"a hub keeps at most {MAX_BUTTONS_PER_HUB} buttons")
            hub[button_id] = {"name": name, "code": code, "learned_at": time.time()}
            self._write(data)
        return {"id": button_id, "name": name}

    def delete(self, hub_id: str, button_id: str) -> None:
        with self._lock:
            data = self._read()
            if button_id not in data.get(hub_id, {}):
                raise IRError("no such button")
            del data[hub_id][button_id]
            self._write(data)

    def all(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            data = self._read()
        return {hub: [{"id": k, "name": v["name"]} for k, v in buttons.items()] for hub, buttons in data.items()}


# ── the hub ──────────────────────────────────────────────────────────────────

def _device(hub: IRHub):
    from tinytuya.Contrib import IRRemoteControlDevice
    device = IRRemoteControlDevice(hub.device_id, hub.host, hub.local_key, version=hub.version, persist=False)
    device.set_socketTimeout(5)
    return device


_hub_locks: dict[str, threading.Lock] = {}


def _hub_lock(hub: IRHub) -> threading.Lock:
    return _hub_locks.setdefault(hub.id, threading.Lock())


def learn(hub: IRHub, timeout: float = LEARN_TIMEOUT_S, device_factory: Callable[[IRHub], Any] = _device) -> str | None:
    """Put the hub in study mode and wait for a button. None if none came."""
    lock = _hub_lock(hub)
    if not lock.acquire(blocking=False):
        raise IRError("this hub is busy - learning or sending already")
    try:
        device = device_factory(hub)
        try:
            code = device.receive_button(timeout=timeout)
        finally:
            try:
                device.study_end()
            except Exception:  # noqa: BLE001 - leaving study mode is best effort
                pass
        # tinytuya passes an error response through unchanged; only a code is a code.
        if isinstance(code, str):
            try:
                return clean_code(code)
            except IRError:
                return None
        return None
    finally:
        lock.release()


def send(hub: IRHub, code: str, device_factory: Callable[[IRHub], Any] = _device) -> None:
    code = clean_code(code)
    with _hub_lock(hub):
        device_factory(hub).send_button(code)


# ── Home Assistant, through MQTT discovery ───────────────────────────────────

def discovery_topic(hub: IRHub, button_id: str) -> str:
    return f"{DISCOVERY_PREFIX}/button/smart_home_ai_ir/{hub.id}_{button_id}/config"


def command_topic(hub: IRHub, button_id: str) -> str:
    return f"{COMMAND_ROOT}/{hub.id}/{button_id}/press"


def discovery_payload(hub: IRHub, button: dict[str, Any]) -> dict[str, Any]:
    """Home Assistant names it `button.<hub>_<button>`: the device name, then the
    entity name, as with any device that has several entities."""
    return {
        "name": button["name"],
        "unique_id": f"smart_home_ai_ir_{hub.id}_{button['id']}",
        "object_id": f"{hub.id}_{button['id']}",
        "command_topic": command_topic(hub, button["id"]),
        "payload_press": "PRESS",
        "availability_topic": AVAILABILITY_TOPIC,
        "icon": "mdi:remote",
        "device": {
            "identifiers": [f"smart_home_ai_ir_{hub.id}"],
            "name": hub.name,
            "manufacturer": "Tuya",
            "model": "Smart IR (local, via the dashboard)",
        },
    }


def entity_id(hub: IRHub, button_id: str) -> str:
    return f"button.{hub.id}_{button_id}"


class MQTTBridge:
    """Publishes the learned buttons to Home Assistant and presses them on command.

    One paho client on its own network thread. Discovery is retained, so Home
    Assistant finds the buttons after its own restart; it also re-publishes
    when Home Assistant announces itself online, in case the broker lost them.
    """

    def __init__(self, hubs: Callable[[], list[IRHub]], store: ButtonStore,
                 host: str, port: int, username: str | None, password: str | None,
                 client_factory: Callable[[], Any] | None = None,
                 sender: Callable[[IRHub, str], None] = send):
        self.hubs = hubs
        self.store = store
        self.sender = sender
        self.published: set[str] = set()
        self._client = (client_factory or self._paho)()
        if username:
            self._client.username_pw_set(username, password)
        self._client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._host, self._port = host, port

    @staticmethod
    def _paho():
        import paho.mqtt.client as mqtt
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smart-home-ai-ir")

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        client.subscribe(f"{COMMAND_ROOT}/+/+/press")
        client.subscribe(f"{DISCOVERY_PREFIX}/status")
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        self.publish_all()

    def publish_all(self) -> None:
        """Announce every learned button, and withdraw ones that were deleted."""
        wanted: dict[str, str] = {}
        buttons = self.store.all()
        for hub in self.hubs():
            for button in buttons.get(hub.id, []):
                wanted[discovery_topic(hub, button["id"])] = json.dumps(discovery_payload(hub, button))
        for topic in self.published - set(wanted):
            self._client.publish(topic, "", retain=True)
        for topic, payload in wanted.items():
            self._client.publish(topic, payload, retain=True)
        self.published = set(wanted)

    def _on_message(self, client, userdata, message) -> None:
        topic = message.topic
        if topic == f"{DISCOVERY_PREFIX}/status":
            if message.payload == b"online":
                self.publish_all()
            return
        parts = topic.split("/")
        if len(parts) != 5 or parts[-1] != "press":
            return
        hub_id, button_id = parts[2], parts[3]
        hub = next((h for h in self.hubs() if h.id == hub_id), None)
        if hub is None:
            return
        try:
            code = self.store.code(hub_id, button_id)
        except IRError:
            log.info("IR press for an unknown button %s/%s", hub_id, button_id)
            return
        # Off paho's network thread: a hub that does not answer must not stall
        # every other message.
        threading.Thread(target=self._press, args=(hub, code, button_id), daemon=True).start()

    def _press(self, hub: IRHub, code: str, button_id: str) -> None:
        try:
            self.sender(hub, code)
            log.info("IR %s/%s sent", hub.id, button_id)
        except Exception as error:  # noqa: BLE001
            log.warning("IR %s/%s failed: %s", hub.id, button_id, error)


def mqtt_credentials(secret_path: Path) -> tuple[str | None, str | None]:
    """The broker login the Zigbee stack uses; the environment wins if set."""
    user, password = os.getenv("MQTT_USER"), os.getenv("MQTT_PASSWORD")
    if user:
        return user, password
    try:
        secret = yaml.safe_load(secret_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None, None
    return secret.get("mqtt_user"), secret.get("mqtt_password")


def hub_by_id(hubs: Iterable[IRHub], hub_id: str) -> IRHub:
    for hub in hubs:
        if hub.id == hub_id:
            return hub
    raise IRError("no such IR hub")
