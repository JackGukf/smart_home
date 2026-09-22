import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

HARNESS = '''
const src = require("fs").readFileSync(process.argv[2], "utf8");
const pick = (name) => {
  const at = src.indexOf("function " + name);
  if (at < 0) throw new Error("missing " + name);
  let depth = 0, i = src.indexOf("{", at);
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error("unbalanced " + name);
};
const constOf = (name) => {
  const start = src.indexOf("const " + name);
  const end = src.indexOf("];", start);
  if (start < 0 || end < 0) throw new Error("missing " + name);
  return src.slice(start, end + 2);
};
globalThis.expandSensorReadings = (readings) => readings;
globalThis.filterReadingsForView = (readings) => readings;
eval(pick("sensorCapabilityKey") + constOf("SENSOR_PAGE_SECTIONS") + pick("sensorPageSectionId") + pick("groupSensorPageSections"));
const groups = [
  { name: "Boiler leak", readings: [{ device_class: "moisture", category: "tuya_moisture" }] },
  { name: "Kitchen multi", readings: [{ device_class: "occupancy", category: "tuya_occupancy" }, { device_class: "temperature", category: "tuya_temperature" }] },
  { name: "Hall light", readings: [{ device_class: "illuminance", category: "tuya_illuminance" }] },
  { name: "Button", readings: [{ device_class: "button", category: "tuya_button" }] },
];
console.log(JSON.stringify({
  ids: groups.map(sensorPageSectionId),
  sections: groupSensorPageSections(groups).map((section) => ({ id: section.id, names: section.groups.map((group) => group.name) })),
}));
'''

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_sensor_page_groups_physical_cards_by_primary_purpose(tmp_path: Path) -> None:
    harness = tmp_path / "sensor-sections.js"
    harness.write_text(HARNESS, encoding="utf-8")
    result = json.loads(subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True).stdout)
    assert result["ids"] == ["safety", "presence", "conditions", "other"]
    assert result["sections"] == [
        {"id": "safety", "names": ["Boiler leak"]},
        {"id": "presence", "names": ["Kitchen multi"]},
        {"id": "conditions", "names": ["Hall light"]},
        {"id": "other", "names": ["Button"]},
    ]

def test_sensor_section_headers_alternate_only_two_colours() -> None:
    styles = STYLES.read_text(encoding="utf-8")
    assert ".sensor-page-section-tone-b" in styles
    assert "--sensor-section-color: var(--t-accent)" in styles
    assert "--sensor-section-color: var(--amber)" in styles
    assert "Alert red remains reserved" in styles
