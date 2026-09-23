"""Home temperature trend requests follow the final sensor selection."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src/python/web_static/app.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_later_sensor_group_wins_when_an_early_request_finishes_last(tmp_path: Path) -> None:
    harness = tmp_path / "history.js"
    harness.write_text("""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const start = src.indexOf('async function loadTempHistory(groups) {');
const end = src.indexOf('/* Monotone cubic', start);
const requests = new Map();
globalThis.tempHistoryCache = { key: '', at: 0, data: null };
globalThis.tempHistory = tempHistoryCache;
globalThis.pendingTempHistoryKeys = new Set();
globalThis.localStorage = { setItem: () => {} };
globalThis.drawTempSparks = () => {};
globalThis.TEMP_HISTORY_MS = 300000;
globalThis.requestJson = (_url, options) => {
  const key = JSON.stringify(JSON.parse(options.body).groups);
  return new Promise((resolve) => requests.set(key, resolve));
};
eval(src.slice(start, end));
(async () => {
  const a = { outdoor_temperature: ['sensor.first'] };
  const b = { outdoor_temperature: ['sensor.final'] };
  const first = loadTempHistory(a);
  const second = loadTempHistory(b);
  requests.get(JSON.stringify(b))({ status: 'ok', series: { outdoor_temperature: [22] } });
  await second;
  requests.get(JSON.stringify(a))({ status: 'ok', series: { outdoor_temperature: [11] } });
  await first;
  console.log(JSON.stringify({
    key: tempHistory.key, value: tempHistory.data.series.outdoor_temperature[0],
    requests: requests.size,
  }));
})();
""", encoding="utf-8")
    result = subprocess.run(
        ["node", str(harness), str(APP_JS)], text=True, capture_output=True, check=True
    )
    actual = json.loads(result.stdout)
    assert actual == {
        "key": json.dumps({"outdoor_temperature": ["sensor.final"]}, separators=(",", ":")),
        "value": 22,
        "requests": 2,
    }

def test_saved_trend_survives_an_early_partial_sensor_group(tmp_path: Path) -> None:
    harness = tmp_path / "saved-history.js"
    harness.write_text("""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const finalGroup = { outdoor_temperature: ['sensor.final'] };
const saved = {
  key: JSON.stringify(finalGroup), at: Date.now(),
  data: { status: 'ok', series: { outdoor_temperature: [21] } },
};
globalThis.TEMP_HISTORY_CACHE_KEY = 'home_temp_history_v1';
globalThis.TEMP_HISTORY_MS = 300000;
globalThis.localStorage = { getItem: () => JSON.stringify(saved), setItem: () => {} };
globalThis.requestJson = () => new Promise(() => {});
globalThis.drawTempSparks = () => {};
const cacheStart = src.indexOf('function savedTempHistory() {');
const cacheEnd = src.indexOf('/* The monitor to show', cacheStart);
const cacheCode = src.slice(cacheStart, cacheEnd)
  .replace('let tempHistoryCache = savedTempHistory();', 'globalThis.tempHistoryCache = savedTempHistory();')
  .replace('let tempHistory = tempHistoryCache;', 'globalThis.tempHistory = tempHistoryCache;')
  .replace('const pendingTempHistoryKeys = new Set();', 'globalThis.pendingTempHistoryKeys = new Set();');
eval(cacheCode);
const start = src.indexOf('async function loadTempHistory(groups) {');
const end = src.indexOf('/* Monotone cubic', start);
eval(src.slice(start, end));
loadTempHistory({ outdoor_temperature: ['sensor.partial'] });
loadTempHistory(finalGroup);
console.log(JSON.stringify({
  key: tempHistory.key, value: tempHistory.data.series.outdoor_temperature[0],
}));
""", encoding="utf-8")
    result = subprocess.run(
        ["node", str(harness), str(APP_JS)], text=True, capture_output=True, check=True
    )
    assert json.loads(result.stdout) == {
        "key": json.dumps({"outdoor_temperature": ["sensor.final"]}, separators=(",", ":")),
        "value": 21,
    }
