"""A command is held until something confirms it.

/api/devices is a cache served instantly while a re-poll runs behind it, and a
Home Assistant entity needs a moment before HA has polled the device and moved
its state machine. So the read taken straight after a command usually still
reports the state from before it. The card painted the new state, snapped back
to the old one, then flipped a second time when the truth arrived - the switch
appeared to fail and then fix itself.

These run the real functions under node, because "does the card flicker" is a
question about what a sequence of reads produces, not about what the source
says.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

HARNESS_PRELUDE = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
"""

# The pending machinery, plus the lists it reaches into.
SETUP = """
globalThis.latestSwitchDevices = [];
globalThis.latestMatterDevices = [];
globalThis.latestTuyaDevices = [];
const PENDING_COMMAND_MS = 12000;
const pendingCommands = new Map();
eval(pick('deviceHostKey') + pick('notePendingCommand') + pick('applyPendingCommands')
   + pick('rememberBrightness') + pick('recalledBrightness'));
const lastKnownBrightness = new Map();
"""


def _run_node(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS_PRELUDE + script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_a_stale_read_after_a_command_does_not_flip_the_card_back(tmp_path: Path) -> None:
    """The reported bug, end to end: turn on, the cache still says off, and the
    card must keep saying on rather than blinking."""
    script = SETUP + """
latestSwitchDevices = [{ host: 'ha:switch.office', is_on: false }];
notePendingCommand('ha:switch.office', { is_on: true });

// The cache answers with the pre-command state, as it does in practice.
latestSwitchDevices = [{ host: 'ha:switch.office', is_on: false }];
applyPendingCommands();
const afterStaleRead = latestSwitchDevices[0].is_on;

// Home Assistant catches up a couple of seconds later.
latestSwitchDevices = [{ host: 'ha:switch.office', is_on: true }];
applyPendingCommands();
const afterTruth = latestSwitchDevices[0].is_on;

console.log(JSON.stringify({ afterStaleRead, afterTruth, held: pendingCommands.size }));
"""
    result = _run_node(script, tmp_path)

    assert result["afterStaleRead"] is True, "the stale read flipped the card back"
    assert result["afterTruth"] is True
    # Confirmed, so nothing is being overridden any more.
    assert result["held"] == 0


def test_the_hold_expires_so_a_failed_switch_settles_on_the_truth(tmp_path: Path) -> None:
    """A switch that never actually turned on must not be shown as on for ever."""
    script = SETUP + """
latestSwitchDevices = [{ host: '192.168.0.51', is_on: false }];
notePendingCommand('192.168.0.51', { is_on: true });
applyPendingCommands();
const whileHeld = latestSwitchDevices[0].is_on;

// Wind the deadline into the past rather than waiting twelve seconds.
pendingCommands.get('192.168.0.51').until = Date.now() - 1;
latestSwitchDevices = [{ host: '192.168.0.51', is_on: false }];
applyPendingCommands();

console.log(JSON.stringify({
  whileHeld, afterExpiry: latestSwitchDevices[0].is_on, held: pendingCommands.size,
}));
"""
    result = _run_node(script, tmp_path)

    assert result["whileHeld"] is True
    assert result["afterExpiry"] is False, "the hold never released"
    assert result["held"] == 0


def test_one_devices_command_does_not_hold_another(tmp_path: Path) -> None:
    script = SETUP + """
latestSwitchDevices = [
  { host: 'ha:switch.a', is_on: false },
  { host: 'ha:switch.b', is_on: false },
];
notePendingCommand('ha:switch.a', { is_on: true });
applyPendingCommands();
console.log(JSON.stringify(latestSwitchDevices.map((d) => d.is_on)));
"""
    assert _run_node(script, tmp_path) == [True, False]


def test_a_matter_device_is_matched_by_its_node_id(tmp_path: Path) -> None:
    """Matter devices carry no host field, so the key is built from node_id."""
    script = SETUP + """
latestMatterDevices = [{ node_id: 7, is_on: false }];
notePendingCommand('matter:7', { is_on: true });
applyPendingCommands();
console.log(JSON.stringify({ is_on: latestMatterDevices[0].is_on }));
"""
    assert _run_node(script, tmp_path)["is_on"] is True


def test_a_brightness_command_holds_the_level_as_well_as_the_power(tmp_path: Path) -> None:
    """Setting a level turns the light on as a side effect, so both have to
    survive the stale read that follows."""
    script = SETUP + """
latestSwitchDevices = [{ host: '192.168.0.51', is_on: false, brightness: 10 }];
notePendingCommand('192.168.0.51', { is_on: true, brightness: 65 });
latestSwitchDevices = [{ host: '192.168.0.51', is_on: false, brightness: 10 }];
applyPendingCommands();
console.log(JSON.stringify(latestSwitchDevices[0]));
"""
    device = _run_node(script, tmp_path)

    assert device["is_on"] is True
    assert device["brightness"] == 65


def test_a_light_comes_back_on_at_the_level_it_was_left_at(tmp_path: Path) -> None:
    """Home Assistant reports no brightness for a light that is off, so without
    the remembered level the dial opens at a placeholder and corrects itself a
    second later."""
    script = SETUP + """
rememberBrightness('ha:light.hall', 40);
const remembered = recalledBrightness('ha:light.hall');

// A level of zero or null is not a level, and must not be remembered as one.
rememberBrightness('ha:light.spare', 0);
rememberBrightness('ha:light.spare', null);

console.log(JSON.stringify({
  remembered, unknown: recalledBrightness('ha:light.spare') ?? null,
}));
"""
    result = _run_node(script, tmp_path)

    assert result["remembered"] == 40
    assert result["unknown"] is None
