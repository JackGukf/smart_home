"""Tuya IR hubs, driven locally, and their buttons in Home Assistant.

  * a hub is a Tuya device whose model is Smart IR and whose local key is set;
  * a learned code must be base64 before it is sent to a hub, a name must
    have a letter or digit - the button's entity id is made from it;
  * learning returns a code or nothing: tinytuya passes an error response
    through as if it were one, and study mode is always left;
  * each learned button is announced to Home Assistant (retained), a deleted
    one is withdrawn, and a press on its command topic sends the code;
  * the endpoints refuse unknown hubs and buttons, and bad codes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import tuya_ir
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
CODE = "Aa8jrxE1AjUCNQI1AjUC"  # base64

CONFIG = """
tuya:
  devices:
    - name: Smart IR Cabinet
      model: Smart IR
      device_id: ebcabinet
      host: 192.168.0.209
      local_key_env: TUYA_CABINET_KEY
      version: 3.3
    - name: Family room smart IR
      model: Smart IR
      device_id: ebfamily
      host: 192.168.0.139
      local_key_env: TUYA_MISSING_KEY
    - name: Old IR
      model: Smart IR
      enabled: false
      device_id: ebold
      host: 192.168.0.9
      local_key: k
    - name: Family room LED
      model: LED strip
      device_id: ebled
      host: 192.168.0.5
      local_key: k
"""


@pytest.fixture
def config(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("TUYA_CABINET_KEY", "secret-key")
    monkeypatch.delenv("TUYA_MISSING_KEY", raising=False)
    path = tmp_path / "devices.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def test_only_reachable_ir_hubs(config: Path) -> None:
    hubs = tuya_ir.load_hubs(config)
    assert [(h.id, h.host, h.local_key, h.version) for h in hubs] == [
        ("smart_ir_cabinet", "192.168.0.209", "secret-key", 3.3)]


@pytest.mark.parametrize("code", ["", "not base64!", "A" * (tuya_ir.MAX_CODE_LENGTH + 4), None])
def test_bad_codes_are_refused(code) -> None:
    with pytest.raises(tuya_ir.IRError):
        tuya_ir.clean_code(code)


@pytest.mark.parametrize("name", ["", "   ", "!!!", "x" * 41])
def test_bad_names_are_refused(name) -> None:
    with pytest.raises(tuya_ir.IRError):
        tuya_ir.clean_name(name)


def test_the_store_keeps_learns_again_and_forgets(tmp_path: Path) -> None:
    store = tuya_ir.ButtonStore(tmp_path / "ir_buttons.json")
    assert store.save("hub", "  Cabinet light   off ", CODE) == {"id": "cabinet_light_off", "name": "Cabinet light off"}
    store.save("hub", "Cabinet light off", "QUJD")  # learned again: replaced, not doubled
    assert [b["id"] for b in store.buttons("hub")] == ["cabinet_light_off"]
    assert store.code("hub", "cabinet_light_off") == "QUJD"
    store.delete("hub", "cabinet_light_off")
    assert store.buttons("hub") == []
    with pytest.raises(tuya_ir.IRError):
        store.code("hub", "cabinet_light_off")


class FakeDevice:
    def __init__(self, result):
        self.result = result
        self.ended = 0
        self.sent: list[str] = []

    def receive_button(self, timeout):
        return self.result

    def study_end(self):
        self.ended += 1

    def send_button(self, code):
        self.sent.append(code)


HUB = tuya_ir.IRHub("smart_ir_cabinet", "Smart IR Cabinet", "eb", "192.168.0.209", "k", 3.3)


def test_learning_returns_a_code_or_nothing_and_leaves_study_mode() -> None:
    device = FakeDevice(CODE)
    assert tuya_ir.learn(HUB, device_factory=lambda hub: device) == CODE
    assert device.ended == 1

    for failure in (None, {"Error": "Network Error", "Err": "905"}, "not base64!"):
        device = FakeDevice(failure)
        assert tuya_ir.learn(HUB, device_factory=lambda hub: device) is None
        assert device.ended == 1


def test_one_thing_at_a_time_per_hub() -> None:
    lock = tuya_ir._hub_lock(HUB)
    lock.acquire()
    try:
        with pytest.raises(tuya_ir.IRError):
            tuya_ir.learn(HUB, device_factory=lambda hub: FakeDevice(CODE))
    finally:
        lock.release()


def test_sending_checks_the_code_first() -> None:
    device = FakeDevice(None)
    tuya_ir.send(HUB, CODE, device_factory=lambda hub: device)
    assert device.sent == [CODE]
    with pytest.raises(tuya_ir.IRError):
        tuya_ir.send(HUB, "<script>", device_factory=lambda hub: device)


class FakeClient:
    def __init__(self):
        self.published: list[tuple[str, str, bool]] = []
        self.subscribed: list[str] = []

    def username_pw_set(self, user, password): self.login = (user, password)
    def will_set(self, topic, payload, retain): self.will = (topic, payload, retain)
    def subscribe(self, topic): self.subscribed.append(topic)
    def publish(self, topic, payload, retain=False): self.published.append((topic, payload, retain))


class Message:
    def __init__(self, topic, payload=b""):
        self.topic, self.payload = topic, payload


def test_the_bridge_announces_withdraws_and_presses(tmp_path: Path) -> None:
    store = tuya_ir.ButtonStore(tmp_path / "ir_buttons.json")
    store.save(HUB.id, "Cabinet light off", CODE)
    sent: list[tuple[str, str]] = []
    pressed = threading.Event()

    def sender(hub, code):
        sent.append((hub.id, code))
        pressed.set()

    client = FakeClient()
    bridge = tuya_ir.MQTTBridge(lambda: [HUB], store, "127.0.0.1", 1883, "user", "pw",
                                client_factory=lambda: client, sender=sender)
    assert client.login == ("user", "pw") and client.will == (tuya_ir.AVAILABILITY_TOPIC, "offline", True)

    bridge._on_connect(client, None, None, 0)
    topic = "homeassistant/button/smart_home_ai_ir/smart_ir_cabinet_cabinet_light_off/config"
    announced = {t: p for t, p, retain in client.published if retain}
    assert announced[tuya_ir.AVAILABILITY_TOPIC] == "online"
    config = json.loads(announced[topic])
    assert config["object_id"] == "smart_ir_cabinet_cabinet_light_off"
    assert config["command_topic"] == "smart_home_ai/ir/smart_ir_cabinet/cabinet_light_off/press"
    assert config["device"]["name"] == "Smart IR Cabinet"
    assert "smart_home_ai/ir/+/+/press" in client.subscribed

    bridge._on_message(client, None, Message(config["command_topic"], b"PRESS"))
    assert pressed.wait(2) and sent == [("smart_ir_cabinet", CODE)]

    bridge._on_message(client, None, Message("smart_home_ai/ir/smart_ir_cabinet/nope/press"))
    bridge._on_message(client, None, Message("smart_home_ai/ir/other_hub/cabinet_light_off/press"))
    time.sleep(0.1)
    assert len(sent) == 1, "unknown buttons and hubs send nothing"

    store.delete(HUB.id, "cabinet_light_off")
    bridge.publish_all()
    assert client.published[-1] == (topic, "", True), "a forgotten button is withdrawn"

    client.published.clear()
    store.save(HUB.id, "Cabinet light on", CODE)
    bridge._on_message(client, None, Message("homeassistant/status", b"online"))
    assert any(t.endswith("smart_ir_cabinet_cabinet_light_on/config") for t, _, _ in client.published)


def test_mqtt_login_comes_from_the_zigbee_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MQTT_USER", raising=False)
    secret = tmp_path / "secret.yaml"
    secret.write_text("mqtt_user: z2m\nmqtt_password: pw\n", encoding="utf-8")
    assert tuya_ir.mqtt_credentials(secret) == ("z2m", "pw")
    monkeypatch.setenv("MQTT_USER", "env-user")
    monkeypatch.setenv("MQTT_PASSWORD", "env-pw")
    assert tuya_ir.mqtt_credentials(secret) == ("env-user", "env-pw")


def test_the_endpoints(config: Path, monkeypatch) -> None:
    client = TestClient(create_app(discovery_path=config.parent / "s.json", config_path=config,
                                   check_camera_ports=False))
    sent: list[str] = []
    monkeypatch.setattr(tuya_ir, "send", lambda hub, code: sent.append(code))
    monkeypatch.setattr(tuya_ir, "learn", lambda hub: CODE)

    hubs = client.get("/api/ir/hubs").json()["hubs"]
    assert [h["id"] for h in hubs] == ["smart_ir_cabinet"] and hubs[0]["buttons"] == []

    assert client.post("/api/ir/hubs/smart_ir_cabinet/learn").json() == {"status": "learned", "code": CODE}
    monkeypatch.setattr(tuya_ir, "learn", lambda hub: None)
    assert client.post("/api/ir/hubs/smart_ir_cabinet/learn").json() == {"status": "timeout"}

    saved = client.post("/api/ir/hubs/smart_ir_cabinet/buttons", json={"name": "Cabinet light off", "code": CODE}).json()
    assert saved["entity_id"] == "button.smart_ir_cabinet_cabinet_light_off"
    assert client.post("/api/ir/hubs/smart_ir_cabinet/buttons", json={"name": "x", "code": "nope!"}).status_code == 400

    assert client.post("/api/ir/hubs/smart_ir_cabinet/buttons/cabinet_light_off/send").json()["status"] == "sent"
    assert sent == [CODE]
    assert client.post("/api/ir/hubs/smart_ir_cabinet/buttons/nothing/send").status_code == 404
    assert client.post("/api/ir/hubs/family_room_led/learn").status_code == 404
    assert client.post("/api/ir/hubs/smart_ir_cabinet/test", json={"code": CODE}).json() == {"status": "sent"}

    assert client.delete("/api/ir/hubs/smart_ir_cabinet/buttons/cabinet_light_off").json() == {"deleted": "cabinet_light_off"}
    assert json.loads((config.parent / "ir_buttons.json").read_text()) == {"smart_ir_cabinet": {}}


HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
};
globalThis.escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
globalThis.irLearning = new Map();
globalThis.irMessages = new Map();
globalThis.IR_LEARN_SECONDS = 20;
eval(pick('irNameSuggestions') + pick('irHubCard'));
const hub = { id: 'smart_ir_cabinet', name: 'Smart IR <Cabinet>', host: '192.168.0.209',
  buttons: [{ id: 'cabinet_light_off', name: 'Cabinet light off', entity_id: 'button.smart_ir_cabinet_cabinet_light_off' }] };
const idle = irHubCard(hub);
irLearning.set('smart_ir_cabinet', { phase: 'waiting' });
const waiting = irHubCard(hub);
irLearning.set('smart_ir_cabinet', { phase: 'learned', code: 'QUJD' });
const learned = irHubCard(hub);
irLearning.set('smart_ir_cabinet', { phase: 'idle', error: 'Nothing was received.' });
const failed = irHubCard({ ...hub, buttons: [] });
console.log(JSON.stringify({
  press: idle.includes('data-ir-send="cabinet_light_off"') && idle.includes('button.smart_ir_cabinet_cabinet_light_off'),
  escaped: idle.includes('Smart IR &lt;Cabinet>'),
  learnButton: idle.includes('data-ir-learn="smart_ir_cabinet"'),
  waiting: waiting.includes('press the button now') && !waiting.includes('data-ir-learn='),
  suggestions: learned.includes('data-ir-suggest="Cabinet light off"') && learned.includes('data-ir-test='),
  failed: failed.includes('Nothing was received.') && failed.includes('No buttons learned yet.'),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_hub_card(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {k: True for k in (
        "press", "escaped", "learnButton", "waiting", "suggestions", "failed")}
