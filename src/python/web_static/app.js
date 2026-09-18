/* ── THEMES ── */
const THEMES = {
  walnut: {
    label: "Warm walnut & brass", swatch: "#C9A227",
    bg: "#1C1A17", cardOff: "#221F1B", cardOnTop: "#2C2620", cardOnBot: "#221E19",
    accent: "#C9A227", glow: "#FFB454", offMuted: "#4A453E",
    text: "#EDE6DA", textDim: "#8A8276", textDim2: "#6B655B", segOff: "#3A352E",
    rockerTop: "#2E2A24", rockerBot: "#1C1916", rockerOnT: "#D9B445", rockerOnB: "#A8801E",
    rockerOffT: "#5A554C", rockerOffB: "#403C35", knobStart: "#34302A", knobEnd: "#211E19",
    accentRgb: "201,162,39", alert: "#FF6B5C",
  },
  slate: {
    label: "Cool slate & ice blue", swatch: "#5FC0EA",
    bg: "#12161B", cardOff: "#181E24", cardOnTop: "#1E3140", cardOnBot: "#161D24",
    accent: "#5FC0EA", glow: "#8FE0FF", offMuted: "#3C4750",
    text: "#E7EEF4", textDim: "#7C8893", textDim2: "#6B7682", segOff: "#313A42",
    rockerTop: "#232B33", rockerBot: "#12161B", rockerOnT: "#8FD8F5", rockerOnB: "#4FA3D6",
    rockerOffT: "#4A5560", rockerOffB: "#323C45", knobStart: "#28323B", knobEnd: "#161B20",
    accentRgb: "95,192,234", alert: "#FF8A7A",
  },
  forest: {
    label: "Deep forest & copper", swatch: "#C97A4A",
    bg: "#11160F", cardOff: "#161D14", cardOnTop: "#23311D", cardOnBot: "#171F14",
    accent: "#C97A4A", glow: "#FF9D5C", offMuted: "#3D4538",
    text: "#E8EDE2", textDim: "#828F78", textDim2: "#6B7660", segOff: "#303A2C",
    rockerTop: "#232C1F", rockerBot: "#11160F", rockerOnT: "#E0A36F", rockerOnB: "#B5723D",
    rockerOffT: "#4F5A47", rockerOffB: "#38412F", knobStart: "#2A3424", knobEnd: "#171F14",
    accentRgb: "201,122,74", alert: "#FF6B5C",
  },
  clay: {
    label: "Soft clay & terracotta", swatch: "#E07A5F",
    bg: "#211A17", cardOff: "#281F1B", cardOnTop: "#36241D", cardOnBot: "#281E1A",
    accent: "#E07A5F", glow: "#FFA787", offMuted: "#51423C",
    text: "#F2E8E1", textDim: "#9C887D", textDim2: "#7E6B61", segOff: "#46342C",
    rockerTop: "#32241E", rockerBot: "#211A17", rockerOnT: "#F0A488", rockerOnB: "#C56848",
    rockerOffT: "#5C4A41", rockerOffB: "#423129", knobStart: "#3C2A22", knobEnd: "#241B17",
    accentRgb: "224,122,95", alert: "#FF6B5C",
  },
};

let currentThemeId = "slate";

const BRAND_TITLE_KEY = "dashboard_brand_title";
const DEFAULT_BRAND_TITLE = "HomeOS";

function applyTheme(id) {
  const t = THEMES[id] || THEMES.slate;
  currentThemeId = id;
  const r = document.documentElement;
  r.style.setProperty("--t-bg",           t.bg);
  r.style.setProperty("--t-card-off",     t.cardOff);
  r.style.setProperty("--t-card-on-top",  t.cardOnTop);
  r.style.setProperty("--t-card-on-bot",  t.cardOnBot);
  r.style.setProperty("--t-accent",       t.accent);
  r.style.setProperty("--t-glow",         t.glow);
  r.style.setProperty("--t-off-muted",    t.offMuted);
  r.style.setProperty("--t-text",         t.text);
  r.style.setProperty("--t-text-dim",     t.textDim);
  r.style.setProperty("--t-text-dim2",    t.textDim2);
  r.style.setProperty("--t-seg-off",      t.segOff);
  r.style.setProperty("--t-rocker-top",   t.rockerTop);
  r.style.setProperty("--t-rocker-bot",   t.rockerBot);
  r.style.setProperty("--t-rocker-on-t",  t.rockerOnT);
  r.style.setProperty("--t-rocker-on-b",  t.rockerOnB);
  r.style.setProperty("--t-rocker-off-t", t.rockerOffT);
  r.style.setProperty("--t-rocker-off-b", t.rockerOffB);
  r.style.setProperty("--t-knob-start",   t.knobStart);
  r.style.setProperty("--t-knob-end",     t.knobEnd);
  r.style.setProperty("--t-accent-rgb",   t.accentRgb);
  r.style.setProperty("--t-alert",        t.alert);
}

function renderPalettePicker() {
  const container = document.querySelector("#palettePicker");
  if (!container) return;
  container.innerHTML = Object.entries(THEMES).map(([id, theme]) => {
    const isActive = id === currentThemeId;
    const shadow = isActive
      ? `0 0 0 2px var(--bg), 0 0 0 4px ${theme.swatch}`
      : "0 0 0 1px rgba(255,255,255,0.15)";
    return `<button class="palette-swatch"
      data-theme-id="${id}"
      title="${theme.label}"
      aria-label="${theme.label}"
      aria-pressed="${isActive}"
      style="background:${theme.swatch};box-shadow:${shadow}"></button>`;
  }).join("");
}

/* ── DOM refs ── */
const apiStatus         = document.querySelector("#apiStatus");
const statusDot         = document.querySelector("#statusDot");
const logoText          = document.querySelector("#logoText");
const headerWeather     = document.querySelector("#headerWeather");
const weatherDropdown   = document.querySelector("#weatherDropdown");
const weatherBackdrop   = document.querySelector("#weatherBackdrop");
const weatherIcon       = document.querySelector("#weatherIcon");
const weatherTemp       = document.querySelector("#weatherTemp");
const weatherCondition  = document.querySelector("#weatherCondition");
const weatherFeels      = document.querySelector("#weatherFeels");
const weatherHumidity   = document.querySelector("#weatherHumidity");
const weatherWind       = document.querySelector("#weatherWind");
const weatherPressure   = document.querySelector("#weatherPressure");
const weatherUv         = document.querySelector("#weatherUv");
const weatherHighLow    = document.querySelector("#weatherHighLow");
const weatherPrecip     = document.querySelector("#weatherPrecip");
const weatherForecast   = document.querySelector("#weatherForecast");
const deviceCount       = document.querySelector("#deviceCount");
const onCount           = document.querySelector("#onCount");
const cameraCount       = document.querySelector("#cameraCount");
const buildBadge        = document.querySelector("#buildBadge");
const indoorTemp        = document.querySelector("#indoorTemp");
const outdoorTemp       = document.querySelector("#outdoorTemp");
const refreshButton     = document.querySelector("#refreshButton");
const lightGrid         = document.querySelector("#lightGrid");
const lightScenes       = document.querySelector("#lightScenes");
const lightDragLock     = document.querySelector("#lightDragLock");
const plugGrid          = document.querySelector("#plugGrid");
const ambientGrid       = document.querySelector("#ambientGrid");
const tuyaGrid          = document.querySelector("#tuyaGrid");
const motionGrid        = document.querySelector("#motionGrid");
const motionLog         = document.querySelector("#motionLog");
const thermostatGrid    = document.querySelector("#thermostatGrid");
const homeAssistantFrame = document.querySelector("#homeAssistantFrame");
const homeAssistantOpen = document.querySelector("#homeAssistantOpen");
const homeAssistantBack = document.querySelector("#homeAssistantBack");
const cameraGrid        = document.querySelector("#cameraGrid");
const lightCount        = document.querySelector("#lightCount");
const plugCount         = document.querySelector("#plugCount");
const ambientCount      = document.querySelector("#ambientCount");
const tuyaCount         = document.querySelector("#tuyaCount");
const motionCount       = document.querySelector("#motionCount");
const thermostatCount   = document.querySelector("#thermostatCount");
const haCount           = document.querySelector("#haCount");
const cameraTabCount    = document.querySelector("#cameraTabCount");
const weatherGrid       = document.querySelector("#weatherGrid");
const activityLog       = document.querySelector("#activityLog");

/* Queried fresh rather than snapshotted: groups can be created at runtime, and a
   module-load snapshot would silently miss their nav items — losing the active
   class, startup-view validation, and the startup dropdown entry. */
function railButtonEls() {
  return Array.from(document.querySelectorAll(".room-item[data-view]"));
}
/* Queried fresh for the same reason as railButtonEls: panels are created at
   runtime for user-made groups, and a module-load snapshot would never see
   them — so the new panel would render its content but never get .active. */
function viewPanelEls() {
  return Array.from(document.querySelectorAll(".view-panel[data-view-panel]"));
}

function restoreBrandTitle() {
  if (!logoText) return;
  try {
    const savedTitle = localStorage.getItem(BRAND_TITLE_KEY);
    logoText.textContent = savedTitle && savedTitle.trim() ? savedTitle.trim() : DEFAULT_BRAND_TITLE;
  } catch {
    logoText.textContent = DEFAULT_BRAND_TITLE;
  }
}

function saveBrandTitle() {
  if (!logoText) return;
  const nextTitle = logoText.textContent.trim() || DEFAULT_BRAND_TITLE;
  logoText.textContent = nextTitle;
  try { localStorage.setItem(BRAND_TITLE_KEY, nextTitle); } catch {}
}

if (logoText) {
  restoreBrandTitle();
  logoText.addEventListener("blur", saveBrandTitle);
  logoText.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      logoText.blur();
    }
    if (event.key === "Escape") {
      event.preventDefault();
      restoreBrandTitle();
      logoText.blur();
    }
  });
}

const CAMERA_ORDER_KEY = "camera_order_v1";
const DEVICE_ORDER_KEYS = { light_switch: "light_order_v1", smart_plug: "plug_order_v1" };
const LIGHT_DRAG_UNLOCK_KEY = "light_drag_unlocked_v1";
/* Promise.allSettled is Safari 13. The deploy compiles modern *syntax* down
   to ES2019, but an API is just a missing function at run time - the call
   throws where it stands. Unlike syntax, an API can simply be supplied. */
if (typeof Promise.allSettled !== "function") {
  Promise.allSettled = function (promises) {
    return Promise.all(
      Array.from(promises, (item) =>
        Promise.resolve(item).then(
          (value) => ({ status: "fulfilled", value }),
          (reason) => ({ status: "rejected", reason })
        )
      )
    );
  };
}

/* ── Drag input, with and without Pointer Events ──

   Pointer Events did not reach Safari until 13, so on an iOS 12 iPad none of
   the pointerdown handlers here ever fired: dragging and resizing a card were
   not awkward there, they were inert. Touch events cover those browsers, and
   mouse events cover any desktop browser in the same position.

   Touch also needs preventDefault on every move, or the page scrolls out from
   under the gesture - and that needs a listener registered as non-passive. */
const HAS_POINTER_EVENTS = typeof window.PointerEvent === "function";

function dragPoint(event) {
  const touch = event.touches && event.touches[0];
  return touch || event;
}

let lastTouchAt = 0;

function onDragStart(target, handler) {
  if (!target) return;
  if (HAS_POINTER_EVENTS) {
    target.addEventListener("pointerdown", handler);
    return;
  }
  target.addEventListener("touchstart", (event) => {
    lastTouchAt = Date.now();
    handler(event);
  }, { passive: false });
  // iOS replays a touch as mousedown/mouseup a moment later. Letting that
  // through starts a second drag on top of the one just finished, which then
  // moves the card on the next unrelated gesture.
  target.addEventListener("mousedown", (event) => {
    if (Date.now() - lastTouchAt < 700) return;
    handler(event);
  });
}

function trackDrag(startEvent, { onMove, onEnd }) {
  const isTouch = startEvent.type === "touchstart";
  const moveName = HAS_POINTER_EVENTS ? "pointermove" : isTouch ? "touchmove" : "mousemove";
  const endNames = HAS_POINTER_EVENTS
    ? ["pointerup", "pointercancel"]
    : isTouch
    ? ["touchend", "touchcancel"]
    : ["mouseup"];

  const move = (event) => {
    if (isTouch) event.preventDefault();
    onMove(dragPoint(event));
  };
  const end = () => {
    window.removeEventListener(moveName, move);
    endNames.forEach((name) => window.removeEventListener(name, end));
    onEnd();
  };

  window.addEventListener(moveName, move, { passive: false });
  endNames.forEach((name) => window.addEventListener(name, end));
}

const activeCameraIds   = new Set();
/* Set by the probe in index.html: this browser cannot parse the syntax that
   embedded players are written in, so anything relying on one must be given a
   plainer alternative. */
const LEGACY_JS = document.documentElement.classList.contains("legacy-js");
let latestCameras       = [];
let latestCameraPaths   = [];
let latestTuyaDevices   = [];
let latestAlarmData     = null;
let latestSwitchDevices = [];
let latestMatterDevices = [];
let latestThermostats   = [];
let latestAmbientLights = [];
let latestHumidifiers   = [];
let latestEnvironmentSensors = [];
let latestZigbeeBridge  = null;
let areasDoc            = { areas: [], assignments: {} };
let currentAreaId       = null;
let doorbellEventsReady = false;
const latestCameraById  = new Map();
const lastDoorbellEventById = new Map();
let manualLightCommandRevision = 0;
let activeLightSceneCount = 0;
const manualLightOverrides = new Map();

/* Declared here, above the clock, because tick() runs at load and reads them -
   see applyWeatherSky(). */
let latestWeather = null;
const SKY_TWILIGHT_MIN = 75;

/* ── Live clock ──
   Hour and minute in the header; the Weather card carries the same time large,
   with the date. Checked every second so the minute turns over on time, but the
   DOM is only touched when the minute actually changes. */
let lastClockMinute = "";
function tick() {
  const now = new Date();
  const hm = now.toTimeString().slice(0, 5);
  if (hm === lastClockMinute) return;
  lastClockMinute = hm;
  const clockEl = document.querySelector("#clock");
  if (clockEl) clockEl.textContent = hm;
  const cardClock = document.querySelector("#weatherClock");
  if (cardClock) cardClock.textContent = hm;
  const cardDate = document.querySelector("#weatherDate");
  if (cardDate) cardDate.textContent = now.toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long"
  });
  applyWeatherSky(now);
}
tick();
setInterval(tick, 1000);

/* ── Activity log ── */
function logActivity(text, type = "normal") {
  if (!activityLog) return;
  const entry = document.createElement("div");
  entry.className = "activity-item";
  entry.innerHTML = `
    <div class="activity-dot${type === "warn" ? " warn" : type === "error" ? " error" : ""}"></div>
    <div class="activity-text">${escapeHtml(text)}</div>
    <div class="activity-time">just now</div>
  `;
  activityLog.prepend(entry);
  while (activityLog.children.length > 8) activityLog.removeChild(activityLog.lastElementChild);
}

/* ── Sidebar collapsible: Recent Activity ── */
(function initSidebarCollapsibles() {
  const activityToggle = document.querySelector("#activityToggle");
  activityToggle?.addEventListener("click", () => {
    if (!activityLog) return;
    activityLog.hidden = !activityLog.hidden;
    activityToggle.classList.toggle("open", !activityLog.hidden);
    activityToggle.title = activityLog.hidden ? "Show recent activity" : "Hide recent activity";
  });
  activityToggle?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activityToggle.click();
    }
  });
})();

/* ── Devices sidebar group ── */
/* Seeded to the built-in groups so the sidebar works before the group document
   loads; replaced by the loaded ids once it arrives. */
let DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "motion", "environment", "tuya", "climate"];
let latestDeviceGroups = [];
let latestDeviceGroupOverrides = {};

/* Tracks whether the current view was reached from the Devices overview, so the
   back button only appears when there is somewhere to go back to. Deliberately
   not persisted: it describes one navigation step, not a preference. */
let arrivedFromDevices = false;

function setDevicesBackVisible(show) {
  document.querySelectorAll("[data-back-to-devices]").forEach((btn) => {
    btn.hidden = !show;
  });
}

/* The seven built-in views already covered by the hardcoded tiles below. Any
   other id resolveDeviceGroups() returns — a user-created group, or the
   synthetic auto:unassigned bucket — gets a dynamic tile appended instead. */
const BUILTIN_TILE_VIEWS = new Set(["lights", "plugs", "ambient", "humidifier", "motion", "environment", "tuya", "climate"]);

/* Tile for a user-created group or auto:unassigned. name/icon/color are
   user-supplied via the API, so the name is escaped at render time (like every
   other tile label) and the colour is routed through the same GROUP_COLOR_VARS
   allowlist deviceGroupNavPlan uses for the sidebar — never a raw stored value. */
function dynamicGroupTileData(group) {
  const icon = GROUP_ICON_PATTERN.test(String(group.icon || "")) ? group.icon : "device-desktop";
  const count = group.devices.length;
  return {
    view: group.id,
    label: group.name,
    icon: `ti-${icon}`,
    color: GROUP_COLOR_VARS[group.color] || GROUP_COLOR_VARS.slate,
    count,
    summary: `${count} device${count === 1 ? "" : "s"}`,
  };
}

/* Devices overview tiles. Renders from arrays already in memory — no fetches. */
/* Has the user moved this device out of that group in Manage Devices?

   Builtin tiles count from the typed device lists (latestSwitchDevices and
   friends) rather than from resolved group membership, so without this a device
   the user reassigned keeps being counted by the tile it left - the panel below
   shows one fewer than the tile above it. Keys match collectHomeInventory(). */
function isExcludedFromGroup(key, groupId) {
  const rules = (latestDeviceGroupOverrides || {})[key];
  return Boolean(rules && (rules.exclude || []).includes(groupId));
}

function deviceGroupTileData() {
  const allSwitchLike = [...latestSwitchDevices, ...latestMatterDevices];
  const lights = allSwitchLike.filter(
    (d) => d.category === "light_switch" && !isExcludedFromGroup(`dev:${d.host}`, "lights")
  );
  const plugs = allSwitchLike.filter(
    (d) => d.category === "smart_plug" && !isExcludedFromGroup(`dev:${d.host}`, "plugs")
  );
  const ambient = latestAmbientLights.filter((d) => !isExcludedFromGroup(`ambient:${d.id}`, "ambient"));
  const humidifiers = latestHumidifiers.filter((d) => !isExcludedFromGroup(`humidifier:${d.id}`, "humidifier"));
  const thermostats = latestThermostats.filter((d) => !isExcludedFromGroup(`thermo:${d.id}`, "climate"));
  const envSensors = latestEnvironmentSensors.filter(
    (d) => !isExcludedFromGroup(`env:${areaSlug(d.name || "environment sensor")}`, "environment")
  );
  const onOf = (list) => `${list.filter((d) => d.is_on).length} of ${list.length} on`;
  const onlineOf = (list) => `${list.filter((d) => d.online !== false).length} online`;

  const builtinTiles = [
    { view: "lights",     label: "Lights",      icon: "ti-bulb",       count: lights.length,                 summary: onOf(lights) },
    { view: "plugs",      label: "Plugs",       icon: "ti-plug",       count: plugs.length,                  summary: onOf(plugs) },
    { view: "ambient",    label: "Ambient",     icon: "ti-lamp-2",     count: ambient.length,                summary: onlineOf(ambient) },
    { view: "humidifier", label: "Humidifiers", icon: "ti-droplet",    count: humidifiers.length,            summary: onlineOf(humidifiers) },
    { view: "motion",     label: "Motion",      icon: "ti-walk",       count: sensorGroupCount("motion"),    summary: motionSummary() },
    { view: "environment", label: "Environment", icon: "ti-temperature-celsius", count: sensorGroupCount("environment") + envSensors.length, summary: environmentSummary() },
    { view: "tuya",       label: "Sensors",     icon: "ti-radar-2",    count: sensorGroupCount("sensors"),   summary: onlineOf(sensorsTileGroups()) },
    { view: "climate",    label: "Climate",     icon: "ti-temperature",count: thermostats.length,            summary: onlineOf(thermostats) },
  ];

  const dynamicTiles = resolveDeviceGroups()
    .filter((group) => !BUILTIN_TILE_VIEWS.has(group.id))
    .map(dynamicGroupTileData);

  return [...builtinTiles, ...dynamicTiles];
}

/* Average temperature across environment groups, for the overview tile. */
function environmentSummary() {
  const tuyaTemps = latestTuyaDevices
    .filter((d) => sensorCapabilityKey(d) === "temperature")
    .map(readingMetricNumber)
    .filter(Number.isFinite);
  // Already in Celsius -- the backend converts from Fahrenheit before this
  // reaches the client. Use != null so a legitimate 0°C reading is kept.
  const goveeTemps = latestEnvironmentSensors
    .map((s) => s.temperature)
    .filter((t) => t != null)
    .map(Number)
    .filter(Number.isFinite);
  const temps = [...tuyaTemps, ...goveeTemps];
  if (temps.length === 0) return "No readings";
  const avg = temps.reduce((a, b) => a + b, 0) / temps.length;
  return `avg ${avg.toFixed(1)} °C`;
}

function renderDevicesOverview() {
  const grid = document.querySelector("#devicesOverviewGrid");
  if (!grid) return;
  /* App tiles, as in Settings: the group's colour fills the icon square
     (device-group-tile-accent), then the name, how many, and a summary. */
  /* IR remotes is not a device group - its hubs are senders, not devices with
     a state - so its tile follows the groups' rather than being one of them. */
  const irTile = latestIRHubs.length
    ? [{ view: "ir", label: "IR remotes", icon: "ti-device-remote", count: latestIRHubs.length, summary: irSummary() }]
    : [];
  grid.innerHTML = [...deviceGroupTileData(), ...irTile].map((tile) => `
    <button type="button" class="app-tile device-group-tile" data-goto-view="${escapeHtml(tile.view)}"${tile.color ? ` style="--group-color:${tile.color}"` : ""}>
      <span class="app-tile-count mono">${tile.count}</span>
      <span class="app-tile-icon device-group-tile-accent"><i class="ti ${escapeHtml(tile.icon)}" aria-hidden="true"></i></span>
      <span class="app-tile-name">${escapeHtml(tile.label)}</span>
      <span class="app-tile-sub">${escapeHtml(tile.summary)}</span>
    </button>
  `).join("");
}

/* Distinct physical devices. A multi-capability sensor appears in more than
   one child view, so summing the child badges would over-count. */
function distinctDeviceCount() {
  const ids = new Set();
  const add = (list, prefix) => list.forEach((d, i) => ids.add(`${prefix}:${d.id ?? d.name ?? i}`));
  add(latestSwitchDevices, "switch");
  add(latestMatterDevices, "matter");
  add(latestAmbientLights, "ambient");
  add(latestHumidifiers, "humidifier");
  add(latestThermostats, "climate");
  add(latestEnvironmentSensors, "environment");
  latestTuyaDevices
    .filter((d) => !isTuyaCamera(d))
    .forEach((d) => ids.add(`tuya:${sensorBaseName(String(d.name || d.id || ""))}`));
  // The coordinator is a device we own, and the only one not on any of the
  // lists above -- it reaches the dashboard as bridge health, not as a device.
  ids.add("bridge:zigbee");
  return ids.size;
}

/* ── API helper ── */
async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

/* Extract the human-readable detail from an API error (FastAPI returns {"detail": "..."}) */
function apiErrorDetail(error) {
  try {
    const parsed = JSON.parse(error.message);
    if (parsed && parsed.detail) return String(parsed.detail);
  } catch {}
  return error.message || "request failed";
}

/* ── Utilities ── */
function stateLabel(value) {
  if (value === true)  return "on";
  if (value === false) return "off";
  return "offline";
}

function iconFor(device) {
  if (device.type === "Dimmer")     return '<i class="ti ti-bulb" aria-hidden="true"></i>';
  if (device.type === "Plug")       return '<i class="ti ti-plug" aria-hidden="true"></i>';
  return '<i class="ti ti-toggle-right" aria-hidden="true"></i>';
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g,  "&amp;")
    .replace(/</g,  "&lt;")
    .replace(/>/g,  "&gt;")
    .replace(/"/g,  "&quot;")
    .replace(/'/g,  "&#039;");
}

function formatStatus(value) {
  return String(value || "unknown").replace(/_/g, " ");
}

function roundMetric(value) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return String(Math.round(number));
}

function unitSymbol(unit) {
  if (!unit) return "";
  if (unit.includes("F")) return "°F";
  if (unit.includes("C")) return "°C";
  return unit;
}

/* ── Power Gauge (plug cards) ── */
function buildPowerGauge(isOn, watts, maxWatts) {
  const segs     = 24;
  const safeW    = Number(watts)    || 0;
  const safeMax  = Number(maxWatts) || 1500;
  const pct      = isOn ? Math.min(100, Math.round((safeW / safeMax) * 100)) : 0;
  const litSegs  = Math.round((pct / 100) * segs);
  const lines = Array.from({ length: segs }, (_, i) => {
    const a0 = -135 + (270 / segs) * i;
    const a  = (a0 * Math.PI) / 180;
    const r1 = 44, r2 = 38;
    const x1 = (50 + r1 * Math.cos(a)).toFixed(2);
    const y1 = (50 + r1 * Math.sin(a)).toFixed(2);
    const x2 = (50 + r2 * Math.cos(a)).toFixed(2);
    const y2 = (50 + r2 * Math.sin(a)).toFixed(2);
    const stroke = (isOn && i < litSegs) ? "var(--t-glow)" : "var(--t-seg-off)";
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="2.4" stroke-linecap="round" stroke="${stroke}"/>`;
  }).join("");
  const valColor = isOn ? "var(--t-text)" : "var(--t-text-dim2)";
  return `
    <div class="dial-wrap">
      <svg viewBox="0 0 100 100" class="dial-svg">${lines}</svg>
      <div class="dial-knob power-dial-knob">
        <span class="power-val" style="color:${valColor}">${isOn ? safeW : "—"}</span>
        <span class="power-unit">${isOn ? "WATTS" : "IDLE"}</span>
      </div>
    </div>`;
}

/* ── Dial (rocker card centre piece) ── */
function buildDial(level, on, locked = false) {
  const segs = 24;
  const litSegs = on ? Math.round((level / 100) * segs) : 0;
  const lines = Array.from({ length: segs }, (_, i) => {
    const a0 = -135 + (270 / segs) * i;
    const a  = (a0 * Math.PI) / 180;
    const r1 = 44, r2 = 38;
    const x1 = (50 + r1 * Math.cos(a)).toFixed(2);
    const y1 = (50 + r1 * Math.sin(a)).toFixed(2);
    const x2 = (50 + r2 * Math.cos(a)).toFixed(2);
    const y2 = (50 + r2 * Math.sin(a)).toFixed(2);
    const stroke = (i < litSegs) ? "var(--t-glow)" : "var(--t-seg-off)";
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="2.4" stroke-linecap="round" stroke="${stroke}"/>`;
  }).join("");

  const valColor = on ? "var(--t-text)" : "var(--t-text-dim2)";
  return `
    <div class="dial-wrap${locked ? " dial-locked" : ""}">
      <svg viewBox="0 0 100 100" class="dial-svg">${lines}</svg>
      <div class="dial-knob">
        <span class="dial-value" style="color:${valColor}">${on ? `${level}%` : "—"}</span>
        ${locked ? '<span class="dial-fixed-tag">FIXED</span>' : ""}
      </div>
    </div>`;
}

function buildDimControlDial(brightness, isOn, dimmable) {
  return [
    dimmable ? '<button class="dim-step dim-plus" data-dim-step="10" type="button" aria-label="Increase brightness">+</button>' : "",
    buildDial(brightness, isOn, !dimmable),
    dimmable ? '<button class="dim-step dim-minus" data-dim-step="-10" type="button" aria-label="Decrease brightness">-</button>' : "",
  ].join("");
}

/* ── Live dial update (brightness drag) ── */
function updateDialLines(wrap, brightness, isOn) {
  const lines = wrap.querySelectorAll("line");
  const N = lines.length;
  const litSegs = isOn ? Math.round((brightness / 100) * N) : 0;
  lines.forEach((ln, i) => {
    const lit = i < litSegs;
    ln.setAttribute("stroke", lit ? "var(--t-glow)" : "var(--t-seg-off)");
  });
  const val = wrap.querySelector(".dial-value");
  if (val) {
    val.textContent = isOn ? `${brightness}%` : "—";
    val.style.color = isOn ? "var(--t-text)" : "var(--t-text-dim2)";
  }
}

/* ── Brightness drag on dimmer dials ── */
function attachDimDrag(card) {
  const wrap = card.querySelector(".dial-wrap");
  if (!wrap) return;
  wrap._dimDragAttached = true;

  let dragging = false;
  let pendingLevel = null;

  function levelFromPointer(px, py) {
    const rect = wrap.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top  + rect.height / 2;
    // Use screen-space atan2: y increases downward, matches SVG sin direction
    const theta = Math.atan2(py - cy, px - cx) * (180 / Math.PI);
    if (theta > 135 || theta < -135) return null; // dead zone (left gap)
    const t = (theta + 135) / 270;
    return Math.max(1, Math.min(100, Math.round(t * 100)));
  }

  onDragStart(wrap, (e) => {
    if (card.dataset.dimLocked === "true") return;
    const start = dragPoint(e);
    const lv = levelFromPointer(start.clientX, start.clientY);
    // Null means the dead zone at the dial's gap: leave that touch to the page
    // so the view can still be scrolled from there.
    if (lv === null) return;
    e.preventDefault();
    dragging = true;
    pendingLevel = lv;
    updateDialLines(wrap, lv, card.classList.contains("on"));
    card.dataset.brightness = lv;

    trackDrag(e, {
      onMove: (point) => {
        const moved = levelFromPointer(point.clientX, point.clientY);
        if (moved === null) return;
        pendingLevel = moved;
        updateDialLines(wrap, moved, card.classList.contains("on"));
        card.dataset.brightness = moved;
      },
      onEnd: () => {
        if (!dragging) return;
        dragging = false;
        const level = pendingLevel;
        pendingLevel = null;
        if (level === null) return;
        sendBrightness(card.dataset.host, level).catch((err) => {
          console.error("Brightness set failed:", err);
        });
      },
    });
  });
}

async function stepLightBrightness(card, delta) {
  if (!card || card.dataset.dimmable !== "true" || card.dataset.dimLocked === "true") return;
  const current = parseInt(card.dataset.brightness || "50", 10);
  const next = Math.max(1, Math.min(100, current + delta));
  const wrap = card.querySelector(".dial-wrap");
  card.dataset.brightness = String(next);
  updateDeviceCardSwitchState(card, true);
  if (wrap) updateDialLines(wrap, next, true);
  try {
    await sendBrightness(card.dataset.host, next);
  } catch (err) {
    console.error("Brightness step failed:", err);
  }
}

/* ── Lock state (persisted in localStorage) ── */
function isDimLocked(host) {
  return localStorage.getItem(`dim-lock-${host}`) === "true";
}
function persistDimLock(host, locked) {
  localStorage.setItem(`dim-lock-${host}`, String(locked));
}

async function sendBrightness(host, level) {
  recordManualLightOverride(host, { type: "brightness", level });
  /* Brightness turns the light on as a side effect, and nothing used to tell
     the rest of the page: the card that said OFF kept saying OFF until the next
     60 s poll, even though the lamp was visibly lit. */
  patchLocalDeviceState(host, { brightness: level, is_on: true });
  /* A level the user just chose is the best possible answer to "what will this
     light come back on at", so it is remembered and held like any command. */
  rememberBrightness(host, level);
  notePendingCommand(host, { is_on: true, brightness: level });
  if (host.startsWith("matter:")) {
    const nodeId = host.slice(7);
    const resp = await fetch(`/api/matter/devices/${nodeId}/commands/brightness?brightness=${level}`, {
      method: "POST",
    });
    if (!resp.ok) throw new Error("Brightness set failed: " + resp.status);
    const body = await resp.json();
    await refreshDeviceSource(host);
    return body;
  }
  if (host.startsWith("ha:")) {
    const entityId = host.slice(3);
    const resp = await fetch(
      `/api/home-assistant/entities/${encodeURIComponent(entityId)}/brightness`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level }),
      },
    );
    if (!resp.ok) throw new Error("Brightness set failed: " + resp.status);
    return resp.json();
  }
  const resp = await fetch("/api/devices/" + encodeURIComponent(host) + "/brightness", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level }),
  });
  if (!resp.ok) throw new Error("Brightness set failed: " + resp.status);
  return resp.json();
}

/* ── Sensor colour helpers ── */
function tempColor(c) {
  if (c < 16) return "#4FA3D6";
  if (c < 21) return "#5FC0EA";
  if (c < 25) return "#7ED9A0";
  if (c < 29) return "#F2B84B";
  return "#FF6B5C";
}

function humidityColor(h) {
  if (h < 30) return "#E0B074";
  if (h <= 55) return "#7ED9A0";
  return "#5FA8E0";
}

function humidityLabel(h) { return h < 30 ? "Dry" : h > 55 ? "Humid" : "Comfortable"; }
function lightLabel(lux)  { return lux < 50 ? "Dark" : lux < 300 ? "Dim" : "Bright"; }

/* ── Sensor SVG gauges ── */
function thermoGaugeSVG(value, pct) {
  const color = tempColor(value);
  const tubeTop = 8, tubeBottom = 56, tubeHeight = tubeBottom - tubeTop;
  const fillTop = tubeBottom - (tubeHeight * pct) / 100;
  return `
    <div class="gauge-wrap">
      <div class="gauge-slot">
        <svg width="26" height="64" viewBox="0 0 26 64">
          <rect x="9" y="${tubeTop}" width="8" height="${tubeHeight}" rx="4"
            fill="var(--t-knob-end)" stroke="var(--t-text-dim2)" stroke-width="1.1"/>
          <circle cx="13" cy="56" r="9"
            fill="var(--t-knob-end)" stroke="var(--t-text-dim2)" stroke-width="1.1"/>
          <rect x="10.6" y="${fillTop.toFixed(1)}" width="4.8"
            height="${(tubeBottom - fillTop + 2).toFixed(1)}" rx="2.4" fill="${color}"/>
          <circle cx="13" cy="56" r="6.8" fill="${color}"/>
        </svg>
      </div>
      <span class="gauge-value">${value}<small>°C</small></span>
    </div>`;
}

function dropletGaugeSVG(value, pct, uid) {
  const color  = humidityColor(value);
  const clipId = `drop-${escapeHtml(uid)}`;
  const path   = "M20 2 C20 2 6 23 6 33 C6 41.28 12.27 47 20 47 C27.73 47 34 41.28 34 33 C34 23 20 2 20 2 Z";
  const fillY  = (47 - (45 * pct) / 100).toFixed(1);
  return `
    <div class="gauge-wrap">
      <div class="gauge-slot">
        <svg width="38" height="48" viewBox="0 0 40 50">
          <defs><clipPath id="${clipId}"><path d="${path}"/></clipPath></defs>
          <path d="${path}" fill="var(--t-knob-end)" stroke="var(--t-text-dim2)" stroke-width="1.2"/>
          <g clip-path="url(#${clipId})">
            <rect x="0" y="${fillY}" width="40" height="50" fill="${color}"/>
          </g>
        </svg>
      </div>
      <span class="gauge-value">${value}<small>%</small></span>
      <span class="gauge-label">${humidityLabel(value)}</span>
    </div>`;
}

function sunGaugeSVG(value, pct) {
  const rayCount = 8;
  const litRays  = Math.round((pct / 100) * rayCount);
  const cx = 30, cy = 30;
  const rays = Array.from({ length: rayCount }, (_, i) => {
    const angle = (360 / rayCount) * i;
    const rad   = (angle * Math.PI) / 180;
    const r1 = 18, r2 = 26;
    const x1 = (cx + r1 * Math.cos(rad)).toFixed(2);
    const y1 = (cy + r1 * Math.sin(rad)).toFixed(2);
    const x2 = (cx + r2 * Math.cos(rad)).toFixed(2);
    const y2 = (cy + r2 * Math.sin(rad)).toFixed(2);
    const stroke = (i < litRays) ? "var(--t-glow)" : "var(--t-seg-off)";
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="3" stroke-linecap="round" stroke="${stroke}"/>`;
  }).join("");
  const sunOpacity = (0.15 + 0.7 * (pct / 100)).toFixed(2);
  return `
    <div class="gauge-wrap">
      <div class="gauge-slot">
        <svg width="58" height="58" viewBox="0 0 60 60">
          ${rays}
          <circle cx="${cx}" cy="${cy}" r="13" fill="var(--t-knob-end)" stroke="var(--t-text-dim2)" stroke-width="1"/>
          <circle cx="${cx}" cy="${cy}" r="13" fill="var(--t-glow)" opacity="${sunOpacity}"/>
        </svg>
      </div>
      <span class="gauge-value">${value}<small>lx</small></span>
      <span class="gauge-label">${lightLabel(value)}</span>
    </div>`;
}

/* ── Alert SVG icons ── */
function radarIconSVG(detected) {
  const color = detected ? "var(--t-alert)" : "var(--t-glow)";
  const r1cls = detected ? ' class="svg-radar-ring anim-1"' : "";
  const r2cls = detected ? ' class="svg-radar-ring anim-2"' : "";
  return `<svg width="22" height="22" viewBox="0 0 22 22" flex-shrink="0">
    <circle cx="11" cy="11" r="2.2" fill="${color}"/>
    <circle cx="11" cy="11" r="6" fill="none" stroke="${color}" stroke-width="1.4"
      opacity="${detected ? 0.7 : 0.35}"${r1cls}/>
    <circle cx="11" cy="11" r="9.5" fill="none" stroke="${color}" stroke-width="1.2"
      opacity="${detected ? 0.4 : 0.2}"${r2cls}/>
  </svg>`;
}

function alarmTriangleSVG() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" flex-shrink="0">
    <path d="M11 1.5L21 19.5H1L11 1.5Z" fill="var(--t-alert)"
      style="filter:drop-shadow(0 0 4px var(--t-alert))" class="svg-pulse"/>
    <rect x="10" y="8" width="2" height="5.5" rx="1" fill="var(--t-bg,#12161B)"/>
    <circle cx="11" cy="16" r="1.1" fill="var(--t-bg,#12161B)"/>
  </svg>`;
}

function leakIconSVG() {
  return `<svg width="22" height="22" viewBox="0 0 22 22" flex-shrink="0">
    <path d="M11 2C11 2 4 11.2 4 15.2A7 7 0 0018 15.2C18 11.2 11 2 11 2Z"
      fill="var(--t-glow)" opacity="0.5"/>
  </svg>`;
}

function flameIconSVG(detected) {
  const color  = detected ? "var(--t-alert)" : "var(--t-glow)";
  const fStyle = detected ? `style="filter:drop-shadow(0 0 4px ${color})"` : "";
  const pulse  = detected ? ' class="svg-pulse"' : "";
  return `<svg width="22" height="22" viewBox="0 0 22 22" flex-shrink="0">
    <path d="M11 1.5c2.6 3.6-1.8 4.8-1 8.3.3 1.3-.6 2.4-1.9 2.4a2.6 2.6 0 01-2.6-2.6c0-2.4 1.6-3.4 2.4-5.6-.1 2.4 1.6 2.6 1.6.7-.1-1.4-.8-2.1 1.5-3.2zM9.6 12.4c.3 1.7 1.9 2.9 3.6 2.6 1.9-.3 3.1-2.1 2.7-4-.3-1.5-1.5-2.2-1.2-.5.2 1.4-1.1 2.5-2.5 2.3a2.1 2.1 0 01-1.7-1.9c-.1-.6.7-.6 1-.4-.6-1.4-2.2-1.1-1.9 1.9z"
      fill="${color}" opacity="${detected ? 1 : 0.5}" ${fStyle}${pulse}/>
  </svg>`;
}

/* ── Sensor gauge builder ── */
function buildSensorGauge(device) {
  const dc  = String(device.device_class || "").toLowerCase();
  const cat = String(device.category    || "").toLowerCase();

  if (dc === "temperature" || cat.includes("temperature")) {
    const raw = device.state ?? Object.values(device.values || {})[0];
    const val = Number(raw);
    if (Number.isFinite(val)) {
      const pct = Math.min(100, Math.max(0, ((val - 16) / (30 - 16)) * 100));
      return `<div class="sensor-gauges">${thermoGaugeSVG(val, pct)}</div>`;
    }
  }

  if (dc === "humidity" || cat.includes("humidity")) {
    const raw = device.state ?? Object.values(device.values || {})[0];
    const val = Number(raw);
    if (Number.isFinite(val)) {
      return `<div class="sensor-gauges">${dropletGaugeSVG(val, val, device.id)}</div>`;
    }
  }

  if (dc === "illuminance" || cat.includes("illuminance")) {
    const raw = device.state ?? Object.values(device.values || {})[0];
    const val = Number(raw);
    if (Number.isFinite(val)) {
      const pct = Math.min(100, (val / 1000) * 100);
      return `<div class="sensor-gauges">${sunGaugeSVG(val, pct)}</div>`;
    }
  }

  return "";
}

/* ── Alert row builder ── */
function isAlertDetected(device) {
  return device.is_on === true ||
    ["on", "open", "wet", "detected", "smoke"].includes(String(device.state || "").toLowerCase());
}

/* A tripped reading that actually warrants attention.

   Motion is ordinary household traffic, not an incident. The old card marked
   it with one small red dot, which was easy to ignore; the tile marks an
   incident by lighting the whole card, and a grid that flashes red every time
   somebody walks down the hall teaches you to ignore red. Battery level is
   context and has never been an incident either. */
function isSensorIncident(device) {
  if (!isAlertDetected(device)) return false;
  const dc  = String(device.device_class || "").toLowerCase();
  const cat = String(device.category || "").toLowerCase();
  if (dc === "battery" || cat.includes("battery")) return false;
  return !(["occupancy", "motion", "moving"].includes(dc) ||
           cat.includes("occupancy") || cat.includes("motion"));
}

function buildAlertRow(device) {
  const dc  = String(device.device_class || "").toLowerCase();
  const cat = String(device.category    || "").toLowerCase();
  const detected = isAlertDetected(device);
  const rows = [];

  if (["occupancy", "motion", "moving"].includes(dc) ||
      cat.includes("occupancy") || cat.includes("motion")) {
    rows.push(`
      <div class="alert-row">
        <div class="alert-icon-text">
          ${radarIconSVG(detected)}
          <span class="alert-status-text${detected ? " is-alert" : ""}">
            ${detected ? "MOTION DETECTED" : "ALL CLEAR"}
          </span>
        </div>
      </div>`);
  }

  if (dc === "moisture" || dc === "problem" ||
      cat.includes("moisture") || cat.includes("leak")) {
    rows.push(`
      <div class="alert-row">
        <div class="alert-icon-text">
          ${detected ? alarmTriangleSVG() : leakIconSVG()}
          <span class="alert-status-text${detected ? " is-alert" : ""}">
            ${detected ? "LEAK DETECTED" : "DRY"}
          </span>
        </div>
      </div>`);
  }

  if (dc === "smoke" || cat.includes("smoke")) {
    rows.push(`
      <div class="alert-row">
        <div class="alert-icon-text">
          ${flameIconSVG(detected)}
          ${detected ? alarmTriangleSVG() : ""}
          <span class="alert-status-text${detected ? " is-alert" : ""}">
            ${detected ? "SMOKE DETECTED" : "NORMAL"}
          </span>
        </div>
      </div>`);
  }

  if (["door", "window", "garage_door", "opening"].includes(dc)) {
    const openColor = detected ? "var(--t-alert)" : "var(--t-glow)";
    rows.push(`
      <div class="alert-row">
        <div class="alert-icon-text">
          <svg width="22" height="22" viewBox="0 0 22 22">
            <rect x="3" y="1" width="16" height="20" rx="2" fill="none"
              stroke="${openColor}" stroke-width="1.5"/>
            ${detected ? `<line x1="11" y1="5" x2="11" y2="17" stroke="${openColor}" stroke-width="1.5" stroke-linecap="round"/>` : ""}
          </svg>
          <span class="alert-status-text${detected ? " is-alert" : ""}">
            ${detected ? "OPEN" : "CLOSED"}
          </span>
        </div>
      </div>`);
  }

  if (!rows.length) return "";
  const hasSensorGauge = buildSensorGauge(device) !== "";
  return `<div class="alert-rows${hasSensorGauge ? " gauge-divider" : ""}">${rows.join("")}</div>`;
}

/* ── TP-Link device cards ── */
function renderDevices(devices, cameras, matterDevices = []) {
  const lightDevices = groupMemberData("lights", ["light"]);
  const plugDevices  = groupMemberData("plugs", ["plug"]);

  if (deviceCount) deviceCount.textContent = String(devices.length + matterDevices.length);
  if (onCount) onCount.textContent = String([...devices, ...matterDevices].filter((d) => d.is_on === true).length);
  if (lightCount) lightCount.textContent = String(lightDevices.length);
  if (plugCount) plugCount.textContent = String(plugDevices.length);
  cameraTabCount.textContent = String(cameras.length);

  renderLightScenes(lightDevices);
  renderLightDragLock();
  renderDeviceGroup(lightGrid, applyDeviceOrder(lightDevices, "light_switch"), "No light switches found.");
  renderPlugSection(plugDevices);

  renderForeignKinds("lights", ["light"], "#lightGrid");
  renderForeignKinds("plugs", ["plug"], "#plugGrid");
}

function isLightDragUnlocked() {
  try { return localStorage.getItem(LIGHT_DRAG_UNLOCK_KEY) === "true"; } catch { return false; }
}

function setLightDragUnlocked(unlocked) {
  try { localStorage.setItem(LIGHT_DRAG_UNLOCK_KEY, String(unlocked)); } catch {}
}

function renderLightDragLock() {
  if (!lightDragLock) return;
  const unlocked = isLightDragUnlocked();
  lightDragLock.classList.toggle("locked", !unlocked);
  lightDragLock.classList.toggle("unlocked", unlocked);
  lightDragLock.setAttribute("aria-pressed", String(unlocked));
  lightDragLock.title = unlocked ? "Lock light switch arrangement" : "Unlock light switch arrangement";
  lightDragLock.innerHTML = unlocked
    ? '<i class="ti ti-lock-open" aria-hidden="true"></i>'
    : '<i class="ti ti-lock" aria-hidden="true"></i>';
}

function applyLightDragLockState() {
  const unlocked = isLightDragUnlocked();
  document.querySelectorAll('#lightGrid .device-card[data-category="light_switch"]').forEach((card) => {
    card.draggable = unlocked;
    card.dataset.dragLocked = unlocked ? "false" : "true";
  });
  renderLightDragLock();
}

function savedDeviceOrder(category) {
  const key = DEVICE_ORDER_KEYS[category];
  if (!key) return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

/* The dashboard's default order, shared by the camera, device and area views:
   the position of the item's area in areasDoc.areas. Resolution mirrors
   resolveHomeAreas() exactly — an explicit assignment wins, then a room name
   that matches an area name — so a device cannot sort into one area here and
   render under another there.

   Returns a closure because the callers sort: building the lookup once per sort
   rather than once per comparison. Anything with no area ranks last, next to the
   Unassigned bucket it lands in. Before /api/areas has loaded, areasDoc is empty
   and every item ranks equal, leaving the incoming order untouched. */
function homeAreaRanker() {
  const areas = (areasDoc && areasDoc.areas) || [];
  const assignments = (areasDoc && areasDoc.assignments) || {};
  const rankById = new Map(areas.map((area, index) => [area.id, index]));
  const idByName = new Map(areas.map((area) => [String(area.name).toLowerCase(), area.id]));
  return (key, room) => {
    let areaId = assignments[key];
    if (!areaId || !rankById.has(areaId)) {
      areaId = idByName.get(String(room || "").trim().toLowerCase());
    }
    return rankById.has(areaId) ? rankById.get(areaId) : Number.MAX_SAFE_INTEGER;
  };
}

/* Hand-dragged order wins where it exists; everything else falls back to area
   order. Both are consulted on every sort rather than returning early on an
   empty saved order, so a newly added device slots into its room instead of
   landing at whatever position the backend happened to return it in. */
function applyDeviceOrder(devices, category) {
  const order = savedDeviceOrder(category);
  const indexByHost = new Map(order.map((host, index) => [host, index]));
  const rankOf = homeAreaRanker();
  return [...devices]
    .map((device, index) => ({
      device,
      index,
      saved: indexByHost.has(String(device.host)) ? indexByHost.get(String(device.host)) : Number.MAX_SAFE_INTEGER,
      area: rankOf(`dev:${device.host}`, device.room),
    }))
    .sort((a, b) => (a.saved - b.saved) || (a.area - b.area) || (a.index - b.index))
    .map((entry) => entry.device);
}

function saveDeviceOrderFromDom(grid, category) {
  const key = DEVICE_ORDER_KEYS[category];
  if (!grid || !key) return;
  const order = Array.from(grid.querySelectorAll(".device-card[data-host]"))
    .map((card) => card.dataset.host)
    .filter(Boolean);
  try { localStorage.setItem(key, JSON.stringify(order)); } catch {}
}

function deviceDragHandle(host) {
  return `<button class="device-drag-handle" data-device-drag="${escapeHtml(host)}" type="button" title="Drag to reorder" aria-label="Drag to reorder device"><i class="ti ti-grip-vertical" aria-hidden="true"></i></button>`;
}
/* Compact chips, not the 82px blocks these used to be.
   Full width and directly above the light grid, they sat in the path to the
   switches and "All Lights On" was hit by accident repeatedly. Small and to the
   right of the section header keeps them reachable without being in the way.
   The same markup is rendered into the Home header, so the two stay identical
   by construction rather than by being kept in step. */
function lightSceneChips(lightDevices) {
  const disabled = lightDevices.length === 0 ? " disabled" : "";
  return [
    '<button class="scene-button all-on" data-light-scene="on" type="button"',
    ' title="Turn every light switch on"' + disabled + '>',
    '<i class="ti ti-sun-filled" aria-hidden="true"></i>',
    '<span class="scene-label">All On</span>',
    '</button>',
    '<button class="scene-button all-off" data-light-scene="off" type="button"',
    ' title="Turn every light switch off"' + disabled + '>',
    '<i class="ti ti-moon-filled" aria-hidden="true"></i>',
    '<span class="scene-label">All Off</span>',
    '</button>'
  ].join("");
}

function renderLightScenes(lightDevices) {
  const markup = lightSceneChips(lightDevices);
  for (const host of [lightScenes, document.querySelector("#homeLightScenes")]) {
    if (host) host.innerHTML = markup;
  }
}
async function loadAmbientLights() {
  const payload = await requestJson("/api/ambient-lights");
  renderAmbientLights(payload);
  return payload;
}

function renderAmbientLights(payload) {
  latestAmbientLights = payload?.lights || [];
  const lights = groupMemberData("ambient", ["ambient"]);
  if (ambientCount) ambientCount.textContent = String(lights.length);
  if (!ambientGrid) return;
  if (lights.length === 0) {
    const message = latestAmbientLights.length === 0
      ? "No ambient lights configured yet. Add Govee/Lepro entries to configs/devices.local.yaml."
      : "No devices in this group. Use Manage to add some.";
    ambientGrid.innerHTML = `<div class="empty">${message}</div>`;
    renderForeignKinds("ambient", ["ambient"], "#ambientGrid");
    return;
  }
  ambientGrid.innerHTML = lights.map(ambientLightCard).join("");
  renderDevicesOverview();
  renderForeignKinds("ambient", ["ambient"], "#ambientGrid");
}

function ambientLightCard(light) {
  const providerLabel = light.provider === "govee_ble" ? "Govee Bluetooth" : light.provider === "govee_lan" ? "Govee Wi-Fi" : light.provider === "alexa" ? "Alexa bridge" : light.provider;
  const statusClass = light.controllable ? "online" : "setup";
  /* A Bluetooth-only strip cannot be asked, so what the dashboard last sent is
     all there is - said so, rather than passed off as a reading. */
  const basePower = light.is_on === true ? "On" : light.is_on === false ? "Off" : "Not known yet";
  const powerLabel = light.is_on != null && light.state_source === "last_set" ? `${basePower} · as last set` : basePower;
  const level = Number.isFinite(Number(light.brightness)) && light.brightness != null
    ? Math.max(1, Math.min(100, Math.round(Number(light.brightness)))) : 80;
  const onActive = light.is_on === true ? " active" : "";
  const offActive = light.is_on === false ? " active" : "";
  const powerButtons = light.controllable
    ? '<div class="ambient-actions"><button class="command primary' + onActive + '" data-ambient-command="on" data-ambient-id="' + escapeHtml(light.id) + '">On</button><button class="command' + offActive + '" data-ambient-command="off" data-ambient-id="' + escapeHtml(light.id) + '">Off</button></div>'
    : '<div class="ambient-actions"><button class="command" disabled>Setup needed</button></div>';
  const brightnessControl = light.controllable && light.capabilities?.brightness
    ? '<div class="ambient-control-row"><i class="ti ti-sun"></i><input type="range" min="1" max="100" value="' + level + '" data-ambient-brightness data-ambient-id="' + escapeHtml(light.id) + '"><span>' + level + '%</span></div>'
    : '';
  const colorControl = light.controllable && light.capabilities?.color
    ? '<div class="ambient-swatches"><button style="--swatch:#ff8040" data-ambient-color data-red="255" data-green="128" data-blue="64" data-ambient-id="' + escapeHtml(light.id) + '" title="Warm"></button><button style="--swatch:#ffffff" data-ambient-color data-red="255" data-green="255" data-blue="255" data-ambient-id="' + escapeHtml(light.id) + '" title="White"></button><button style="--swatch:#4da3ff" data-ambient-color data-red="77" data-green="163" data-blue="255" data-ambient-id="' + escapeHtml(light.id) + '" title="Cool"></button><button style="--swatch:#b15cff" data-ambient-color data-red="177" data-green="92" data-blue="255" data-ambient-id="' + escapeHtml(light.id) + '" title="Purple"></button></div>'
    : '';
  const discover = light.provider === "govee_ble" && !light.address
    ? '<button class="command" data-ambient-discover="govee_ble"><i class="ti ti-bluetooth"></i> Discover</button>'
    : "";
  return [
    '<article class="ambient-card ' + statusClass + '">',
    '<div class="ambient-glow"></div>',
    '<div class="ambient-top">',
    '<div class="ambient-icon"><i class="ti ti-lamp-2"></i></div>',
    '<div class="ambient-title"><div class="ambient-name-row"><h3>' + escapeHtml(light.name) + '</h3><button class="ambient-edit-btn" data-ambient-edit="' + escapeHtml(light.id) + '" type="button" title="Rename light" aria-label="Rename light"><i class="ti ti-pencil"></i></button></div><p>' + escapeHtml(light.room || light.model || "Ambient") + '</p></div>',
    '</div>',
    '<div class="ambient-meta"><span>' + escapeHtml(providerLabel) + '</span><span>' + escapeHtml(light.model || "") + '</span></div>',
    '<div class="ambient-status ' + statusClass + '">' + escapeHtml(light.controllable ? powerLabel : (light.status || "unknown")) + '</div>',
    '<p class="ambient-note">' + escapeHtml(light.note || "") + '</p>',
    powerButtons,
    brightnessControl,
    colorControl,
    discover,
    '</article>'
  ].join("");
}

/* ── Humidifiers (Govee cloud) ── */
async function loadHumidifiers() {
  const payload = await requestJson("/api/humidifiers");
  renderHumidifiers(payload);
}

/* ── IR remotes (Tuya IR hubs, local) ──
   A hub sends the codes it is given; the codes are learned here, locally,
   from the original remote - the Tuya cloud that held the Smart Life ones is
   not something to depend on. Each learned button is also a button entity in
   Home Assistant, so a script can press it. */
let latestIRHubs = [];
const irLearning = new Map();   // hub id -> { phase, code, error }
const irMessages = new Map();   // hub id -> the last thing that went wrong

/* An error belongs on the card it happened on, not in a log nobody sees. */
function irMessage(hubId, text) {
  irMessages.set(hubId, text);
  logActivity(text, "warn");
  renderIRHubs();
}
const IR_LEARN_SECONDS = 20;

function irSummary() {
  const buttons = latestIRHubs.reduce((sum, hub) => sum + hub.buttons.length, 0);
  return `${buttons} button${buttons === 1 ? "" : "s"} learned`;
}

/* Names worth offering: the thing the hub is for, then the usual ones. */
function irNameSuggestions(hub) {
  const base = /cabinet/i.test(hub.name) ? ["Cabinet light off", "Cabinet light on", "Cabinet light"] : [];
  return [...base, "Power", "On", "Off"].slice(0, 5);
}

function irHubCard(hub) {
  const learning = irLearning.get(hub.id) || { phase: "idle" };
  const buttons = hub.buttons.map((b) => `
    <div class="ir-button">
      <button type="button" class="ir-press" data-ir-send="${escapeHtml(b.id)}" data-ir-hub="${escapeHtml(hub.id)}" title="Send">
        <i class="ti ti-player-play" aria-hidden="true"></i><span>${escapeHtml(b.name)}</span>
      </button>
      <button type="button" class="ir-delete" data-ir-delete="${escapeHtml(b.id)}" data-ir-hub="${escapeHtml(hub.id)}" title="Forget ${escapeHtml(b.name)}" aria-label="Forget ${escapeHtml(b.name)}"><i class="ti ti-x" aria-hidden="true"></i></button>
      <code class="ir-entity" title="In Home Assistant">${escapeHtml(b.entity_id)}</code>
    </div>`).join("");

  let learn;
  if (learning.phase === "waiting") {
    learn = `<div class="ir-learn waiting"><i class="ti ti-antenna-bars-5" aria-hidden="true"></i>
      <span>Point the remote at the hub and press the button now…<small>Listening for ${IR_LEARN_SECONDS} seconds</small></span></div>`;
  } else if (learning.phase === "learned") {
    learn = `<form class="ir-learn learned" data-ir-save="${escapeHtml(hub.id)}">
      <span class="ir-learn-ok"><i class="ti ti-circle-check" aria-hidden="true"></i> Got it. Name the button:</span>
      <input type="text" name="name" maxlength="40" required placeholder="e.g. Cabinet light off" value="${escapeHtml(learning.name || "")}">
      <div class="ir-suggest">${irNameSuggestions(hub).map((n) => `<button type="button" data-ir-suggest="${escapeHtml(n)}">${escapeHtml(n)}</button>`).join("")}</div>
      <div class="ir-learn-actions">
        <button type="button" class="command" data-ir-test="${escapeHtml(hub.id)}"><i class="ti ti-player-play" aria-hidden="true"></i> Test</button>
        <button type="submit" class="command primary"><i class="ti ti-device-floppy" aria-hidden="true"></i> Save</button>
        <button type="button" class="command" data-ir-cancel="${escapeHtml(hub.id)}">Cancel</button>
      </div>
    </form>`;
  } else {
    const problem = learning.error || irMessages.get(hub.id);
    const note = problem ? `<p class="ir-note warn">${escapeHtml(problem)}</p>` : "";
    learn = `${note}<button type="button" class="command ir-learn-start" data-ir-learn="${escapeHtml(hub.id)}"><i class="ti ti-plus" aria-hidden="true"></i> Learn a button</button>`;
  }

  return `<article class="ir-card" data-ir-card="${escapeHtml(hub.id)}">
    <div class="ir-card-head">
      <span class="ir-card-icon"><i class="ti ti-device-remote" aria-hidden="true"></i></span>
      <span><h3>${escapeHtml(hub.name)}</h3><small>Tuya Smart IR · ${escapeHtml(hub.host)}</small></span>
    </div>
    ${hub.buttons.length ? `<div class="ir-buttons">${buttons}</div>` : `<p class="ir-note">No buttons learned yet.</p>`}
    ${learn}
  </article>`;
}

function renderIRHubs() {
  const grid = document.querySelector("#irGrid");
  if (!grid) return;
  grid.innerHTML = latestIRHubs.length
    ? latestIRHubs.map(irHubCard).join("")
    : `<div class="empty">No Tuya IR hubs with a local key are configured.</div>`;
}

async function loadIRHubs() {
  const payload = await requestJson("/api/ir/hubs");
  latestIRHubs = payload.hubs || [];
  renderIRHubs();
  renderDevicesOverview();
}

async function irLearn(hubId) {
  irLearning.set(hubId, { phase: "waiting" });
  renderIRHubs();
  try {
    const result = await requestJson(`/api/ir/hubs/${encodeURIComponent(hubId)}/learn`, { method: "POST" });
    irLearning.set(hubId, result.status === "learned"
      ? { phase: "learned", code: result.code }
      : { phase: "idle", error: "Nothing was received. Hold the remote close to the hub and try again." });
  } catch (error) {
    irLearning.set(hubId, { phase: "idle", error: apiErrorDetail(error) });
  }
  renderIRHubs();
}

document.addEventListener("click", async (event) => {
  const learn = event.target.closest("[data-ir-learn]");
  if (learn) { irMessages.delete(learn.dataset.irLearn); irLearn(learn.dataset.irLearn); return; }

  const suggest = event.target.closest("[data-ir-suggest]");
  if (suggest) {
    const input = suggest.closest("form")?.querySelector('input[name="name"]');
    if (input) input.value = suggest.dataset.irSuggest;
    return;
  }

  const cancel = event.target.closest("[data-ir-cancel]");
  if (cancel) { irLearning.delete(cancel.dataset.irCancel); renderIRHubs(); return; }

  const test = event.target.closest("[data-ir-test]");
  if (test) {
    const state = irLearning.get(test.dataset.irTest);
    if (!state?.code) return;
    test.disabled = true;
    try {
      await requestJson(`/api/ir/hubs/${encodeURIComponent(test.dataset.irTest)}/test`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: state.code }),
      });
    } catch (error) {
      logActivity(apiErrorDetail(error), "warn");
      const form = test.closest("form");
      form?.querySelector(".ir-learn-ok")?.replaceChildren(document.createTextNode(`Test failed: ${apiErrorDetail(error)}`));
    }
    test.disabled = false;
    return;
  }

  const send = event.target.closest("[data-ir-send]");
  if (send) {
    send.classList.add("sending");
    try {
      await requestJson(`/api/ir/hubs/${encodeURIComponent(send.dataset.irHub)}/buttons/${encodeURIComponent(send.dataset.irSend)}/send`, { method: "POST" });
      irMessages.delete(send.dataset.irHub);
      send.classList.remove("sending");
      send.classList.add("sent");
      setTimeout(() => send.classList.remove("sent"), 900);
    } catch (error) {
      send.classList.remove("sending");
      irMessage(send.dataset.irHub, apiErrorDetail(error));
    }
    return;
  }

  const forget = event.target.closest("[data-ir-delete]");
  if (forget) {
    const name = forget.closest(".ir-button")?.querySelector(".ir-press span")?.textContent || "this button";
    if (!window.confirm(`Forget "${name}"? Anything in Home Assistant that presses it will stop working.`)) return;
    try {
      await requestJson(`/api/ir/hubs/${encodeURIComponent(forget.dataset.irHub)}/buttons/${encodeURIComponent(forget.dataset.irDelete)}`, { method: "DELETE" });
    } catch (error) {
      irMessages.set(forget.dataset.irHub, apiErrorDetail(error));
    }
    loadIRHubs().catch((err) => console.error(err));
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-ir-save]");
  if (!form) return;
  event.preventDefault();
  const hubId = form.dataset.irSave;
  const state = irLearning.get(hubId);
  const name = form.querySelector('input[name="name"]').value.trim();
  if (!state?.code || !name) return;
  try {
    await requestJson(`/api/ir/hubs/${encodeURIComponent(hubId)}/buttons`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, code: state.code }),
    });
    irLearning.delete(hubId);
    await loadIRHubs();
  } catch (error) {
    irLearning.set(hubId, { ...state, name });
    renderIRHubs();
    const ok = document.querySelector(`[data-ir-save="${CSS.escape(hubId)}"] .ir-learn-ok`);
    if (ok) ok.textContent = `Not saved: ${apiErrorDetail(error)}`;
  }
});

/* ── Environment sensors (Govee cloud thermo-hygrometers) ── */
async function loadEnvironmentSensors() {
  const payload = await requestJson("/api/environment-sensors");
  latestEnvironmentSensors = payload.sensors || [];
  renderEnvironmentSensors();
  renderDevicesOverview();
  renderHomeTempSensors();
}

/* CO2 is on Home, and it moves within minutes of people coming into a room.
   The board polls the monitor every minute and serves this from that poll, so
   refreshing while Home is showing costs no Govee calls. */
const ENVIRONMENT_HOME_POLL_MS = 2 * 60_000;
setInterval(() => {
  if (document.hidden || !document.querySelector('.view-panel.active[data-view-panel="home"]')) return;
  loadEnvironmentSensors().catch((error) => console.error(error));
}, ENVIRONMENT_HOME_POLL_MS);

/* Govee cloud thermo-hygrometers use the same tile as the grouped sensors, so
   the Environment grid reads as one set rather than two card designs. A CO2
   monitor leads with CO2 - the reading that says "open a window" - and keeps
   temperature and humidity underneath. */
const CO2_TINT = { fresh: "var(--green)", ok: "var(--teal)", stuffy: "var(--amber)", poor: "var(--red)" };
const CO2_HISTORY_MS = 5 * 60_000;
let co2History = { key: "", at: 0, data: null, pending: false };

function environmentSensorCard(sensor) {
  const hasCo2 = sensor.co2 != null;
  const hasTemp = sensor.temperature != null;
  const level = sensor.co2_level;
  const hero = hasCo2
    ? `<div class="sdc-tile-big">${escapeHtml(String(sensor.co2))}<span class="sdc-tile-unit">ppm CO₂</span></div>`
    : hasTemp
      ? `<div class="sdc-tile-big">${escapeHtml(String(sensor.temperature))}<span class="sdc-tile-unit">°C</span></div>`
      : `<div class="sdc-tile-state">No reading</div>`;

  const facets = [];
  if (hasCo2 && level) {
    facets.push(`<span class="co2-level co2-${escapeHtml(level.key)}">${escapeHtml(level.text)}</span>`);
  }
  if (hasCo2 && hasTemp) {
    facets.push(sensorTileFacet({ key: "temperature", text: `${sensor.temperature}°C` }));
  }
  if (sensor.humidity != null) {
    facets.push(sensorTileFacet({ key: "humidity", text: `${sensor.humidity}%` }));
  }
  const place = [sensor.room, sensor.model].filter(Boolean).join(" · ") || "Govee";
  facets.push(`<span class="sdc-tile-note">${escapeHtml(place)}</span>`);

  const note = sensor.note
    ? `<p class="sdc-tile-note sdc-tile-note-line">${escapeHtml(sensor.note)}</p>`
    : "";
  const spark = hasCo2 && sensor.co2_entity_id
    ? `<div class="co2-spark" data-co2-spark="${escapeHtml(sensor.co2_entity_id)}" aria-label="CO₂, last 24 hours"></div>`
    : "";
  const tint = hasCo2 && level ? CO2_TINT[level.key] || "var(--teal)" : "var(--teal)";

  return `<article class="sdc-tile${sensor.online ? "" : " sdc-tile-offline"}"
    data-device-id="${escapeHtml(sensor.name)}" style="--tint:${tint}">
    ${sensorTileIcon("environment", "sdc-tile-mark")}
    <div class="sdc-tile-top">
      <span class="sdc-tile-badge">${sensorTileIcon("environment")}${hasCo2 ? "Air quality" : "Environment"}</span>
      <span class="sdc-tile-live">${sensor.online ? "ONLINE" : "OFFLINE"}</span>
    </div>
    <div class="sdc-tile-read">
      ${hero}
      <h3 class="sdc-tile-name" title="${escapeHtml(sensor.name)}">${escapeHtml(sensor.name)}</h3>
      <div class="sdc-tile-sub">${facets.join("")}</div>
      ${spark}
      ${note}
    </div>
  </article>`;
}

/* The last 24 hours of CO2, hourly means from Home Assistant's history of the
   mirrored entity. Bands behind the line say where "stuffy" starts. */
function co2SparkSvg(values) {
  const points = values.map((v, i) => [i, v]).filter(([, v]) => typeof v === "number" && Number.isFinite(v));
  if (points.length < 2) return `<span class="co2-spark-empty">History fills in over the next hours.</span>`;
  const w = 240, h = 48, last = values.length - 1 || 1;
  const hi = Math.max(1200, ...points.map(([, v]) => v)), lo = 400;
  const X = (i) => (i / last) * w;
  const Y = (v) => h - ((Math.max(lo, v) - lo) / (hi - lo)) * (h - 4) - 2;
  const line = points.map(([i, v], n) => `${n ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const [lastI, lastV] = points[points.length - 1];
  const peak = Math.round(Math.max(...points.map(([, v]) => v)));
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="CO₂ over 24 hours, peak ${peak} ppm">
      <rect class="co2-band-stuffy" x="0" y="0" width="${w}" height="${Y(1000).toFixed(1)}"/>
      <path class="co2-spark-line" d="${line}"/>
      <circle class="co2-spark-dot" cx="${X(lastI).toFixed(1)}" cy="${Y(lastV).toFixed(1)}" r="2.5"/>
    </svg><span class="co2-spark-caption">24 h · peak ${peak} ppm</span>`;
}

function drawCo2Sparks() {
  const series = co2History.data?.series?.co2;
  document.querySelectorAll("[data-co2-spark]").forEach((el) => {
    el.innerHTML = Array.isArray(series) ? co2SparkSvg(series) : "";
  });
}

async function loadCo2History() {
  const ids = [...new Set([...document.querySelectorAll("[data-co2-spark]")].map((el) => el.dataset.co2Spark))];
  if (!ids.length) return;
  const key = ids.join(",");
  if ((co2History.key === key && Date.now() - co2History.at < CO2_HISTORY_MS) || co2History.pending) {
    drawCo2Sparks();
    return;
  }
  co2History.pending = true;
  try {
    const data = await requestJson("/api/sensors/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ groups: { co2: ids }, hours: 24 }),
    });
    co2History = { key, at: Date.now(), data: data.status === "ok" ? data : null, pending: false };
  } catch (error) {
    console.error(error);
    co2History = { key, at: Date.now(), data: co2History.data, pending: false };
  }
  drawCo2Sparks();
}

function renderHumidifiers(payload) {
  latestHumidifiers = payload.humidifiers || [];
  const humidifiers = groupMemberData("humidifier", ["humidifier"]);
  const grid = document.querySelector("#humidifierGrid");
  const badge = document.querySelector("#humidifierCount");
  if (badge) badge.textContent = String(humidifiers.length);
  if (!grid) return;
  if (humidifiers.length === 0) {
    const message = latestHumidifiers.length === 0
      ? "No humidifiers configured yet. Add a humidifiers: section to configs/devices.local.yaml."
      : "No devices in this group. Use Manage to add some.";
    grid.innerHTML = `<div class="empty">${message}</div>`;
    renderForeignKinds("humidifier", ["humidifier"], "#humidifierGrid");
    return;
  }
  grid.innerHTML = humidifiers.map(humidifierCard).join("");
  renderDevicesOverview();
  renderForeignKinds("humidifier", ["humidifier"], "#humidifierGrid");
}

/* Night-light colour presets (RGB) offered on the humidifier card palette. */
const HUMIDIFIER_NIGHTLIGHT_COLORS = [
  { name: "Warm", r: 255, g: 176, b: 96 },
  { name: "White", r: 255, g: 255, b: 255 },
  { name: "Red", r: 255, g: 64, b: 64 },
  { name: "Orange", r: 255, g: 138, b: 0 },
  { name: "Yellow", r: 255, g: 214, b: 64 },
  { name: "Green", r: 64, g: 220, b: 120 },
  { name: "Cyan", r: 0, g: 229, b: 255 },
  { name: "Blue", r: 77, g: 163, b: 255 },
  { name: "Purple", r: 177, g: 92, b: 255 },
  { name: "Pink", r: 255, g: 105, b: 180 },
];

/* Radial Dial design: a conic-gradient dial encodes the mist level, the dial
   centre powers the unit on/off, +/- step the mist, and a night-light panel
   exposes on/off, a colour palette, and brightness when the device supports it. */
function humidifierCard(humidifier) {
  const isOn = humidifier.is_on === true;
  const configured = humidifier.status === "configured";
  const statusClass = configured ? (isOn ? "on" : "off") : "setup";
  const id = escapeHtml(humidifier.id);
  const mist = humidifier.capabilities && humidifier.capabilities.mist_level;
  const mistMax = mist ? mist.max : 8;
  const mistMin = mist ? mist.min : 1;
  const level = humidifier.mist_level ?? mistMin;

  const stateLabel = configured
    ? (isOn ? "On" : humidifier.is_on === false ? "Off" : "Ready")
    : "Setup";
  const pillText = configured ? stateLabel : (humidifier.note || "Setup needed");

  const head = [
    '<div class="humid-head">',
    '<span class="humid-ico"><i class="ti ti-droplet"></i></span>',
    '<div class="humid-title"><h3>' + escapeHtml(humidifier.name) + '</h3>',
    '<p>' + escapeHtml([humidifier.model, humidifier.room].filter(Boolean).join(" · ")) + '</p></div>',
    '<span class="humid-pill ' + statusClass + '">' + escapeHtml(pillText) + '</span>',
    '</div>',
  ].join("");

  if (!humidifier.controllable) {
    return [
      '<article class="humid-card ' + statusClass + '">',
      head,
      '<div class="humid-setup"><i class="ti ti-cloud-off"></i><span>' + escapeHtml(humidifier.note || "Setup needed") + '</span></div>',
      '</article>',
    ].join("");
  }

  const powerCmd = isOn ? "off" : "on";

  // Orb centre: the linked thermometer's humidity is the hero, with temperature
  // beneath it; if no reading is available, fall back to the mist level.
  const hasHumidity = humidifier.humidity != null;
  const tempUnit = humidifier.temperature_unit || "C";
  const heroValue = hasHumidity
    ? escapeHtml(String(humidifier.humidity)) + '<small>%</small>'
    : level + '<small>/' + mistMax + '</small>';
  const tempLine = humidifier.temperature != null
    ? '<div class="humid-orb-temp"><i class="ti ti-temperature"></i>' + escapeHtml(String(humidifier.temperature)) + '°' + escapeHtml(tempUnit) + '</div>'
    : "";
  const sourceLine = hasHumidity && humidifier.thermometer
    ? '<div class="humid-orb-src"><i class="ti ti-link"></i>' + escapeHtml(humidifier.thermometer) + '</div>'
    : "";
  const orbLabel = hasHumidity ? "Mist · Level " + level : "Mist level";

  const particles =
    '<span class="humid-dot d1"></span><span class="humid-dot d2"></span><span class="humid-dot d3"></span>'
    + '<span class="humid-dot d4"></span><span class="humid-dot d5"></span><span class="humid-dot d6"></span>'
    + '<span class="humid-plume p1"></span><span class="humid-plume p2"></span><span class="humid-plume p3"></span>'
    + '<span class="humid-bubble b1"></span><span class="humid-bubble b2"></span><span class="humid-bubble b3"></span>'
    + '<span class="humid-bubble b4"></span><span class="humid-bubble b5"></span><span class="humid-bubble b6"></span>'
    + '<span class="humid-bubble b7"></span><span class="humid-bubble b8"></span><span class="humid-bubble b9"></span>'
    + '<span class="humid-bubble b10"></span><span class="humid-bubble b11"></span><span class="humid-bubble b12"></span>';

  const orb = [
    '<div class="humid-orb-stage">',
    '<div class="humid-orb">',
    '<div class="humid-orb-surface"></div>',
    particles,
    '<div class="humid-orb-read">',
    '<div class="humid-orb-pct">' + heroValue + '</div>',
    tempLine,
    '<span class="humid-orb-lvl">' + escapeHtml(orbLabel) + '</span>',
    sourceLine,
    '</div>',
    '</div>',
    '<div class="humid-controls">',
    '<button class="humid-step" data-humidifier-mist-step="-1" data-humidifier-id="' + id + '" data-current="' + level + '" data-min="' + mistMin + '" data-max="' + mistMax + '"' + (level <= mistMin ? " disabled" : "") + ' title="Lower mist"><i class="ti ti-minus"></i></button>',
    '<button class="humid-power ' + (isOn ? "on" : "") + '" data-humidifier-command="' + powerCmd + '" data-humidifier-id="' + id + '" title="Turn ' + powerCmd + '"><i class="ti ti-power"></i></button>',
    '<button class="humid-step" data-humidifier-mist-step="1" data-humidifier-id="' + id + '" data-current="' + level + '" data-min="' + mistMin + '" data-max="' + mistMax + '"' + (level >= mistMax ? " disabled" : "") + ' title="Raise mist"><i class="ti ti-plus"></i></button>',
    '</div>',
    '<div class="humid-mist-caption mono">Mist Level ' + level + ' / ' + mistMax + '</div>',
    '</div>',
  ].join("");

  const nl = humidifier.capabilities && humidifier.capabilities.nightlight;
  let nightlight = "";
  if (nl) {
    const nlOn = humidifier.nightlight_on === true;
    const nlCmd = nlOn ? "off" : "on";
    const curColor = humidifier.nightlight_color;
    const toHex = (n) => "#" + (n & 0xffffff).toString(16).padStart(6, "0");
    const currentHex = curColor != null ? toHex(curColor) : "#8ab4ff";

    // Colour: show only the current swatch; the full palette expands on click.
    const colorRow = nl.color
      ? [
          '<div class="humid-night-row">',
          '<span class="humid-night-lbl">Colour</span>',
          '<div class="humid-color-picker">',
          '<button class="humid-color-current" style="--sw:' + currentHex + '" data-humidifier-color-toggle title="Current colour — click to change"></button>',
          '<div class="humid-swatches" hidden>',
          HUMIDIFIER_NIGHTLIGHT_COLORS.map((c) => {
            const intVal = (c.r << 16) | (c.g << 8) | c.b;
            const active = curColor === intVal ? " active" : "";
            const hex = "#" + [c.r, c.g, c.b].map((v) => v.toString(16).padStart(2, "0")).join("");
            return '<button class="humid-swatch' + active + '" style="--sw:' + hex + '" title="' + escapeHtml(c.name) + '"'
              + ' data-humidifier-color data-humidifier-id="' + id + '" data-red="' + c.r + '" data-green="' + c.g + '" data-blue="' + c.b + '"></button>';
          }).join(""),
          '</div></div></div>',
        ].join("")
      : "";

    // Scene: named presets from the device (Forest/Ocean/…).
    const curScene = humidifier.nightlight_scene;
    const sceneRow = nl.scene && nl.scene.length
      ? [
          '<div class="humid-night-row">',
          '<span class="humid-night-lbl">Scene</span>',
          '<div class="humid-scenes">',
          nl.scene.map((s) =>
            '<button class="humid-scene' + (curScene === s.value ? " active" : "") + '" data-humidifier-scene="' + s.value + '" data-humidifier-id="' + id + '">' + escapeHtml(s.name) + '</button>'
          ).join(""),
          '</div></div>',
        ].join("")
      : "";

    const bright = nl.brightness
      ? (() => {
          const bval = humidifier.nightlight_brightness ?? nl.brightness.max;
          return '<div class="humid-night-row"><span class="humid-night-lbl">Brightness</span>'
            + '<div class="humid-bright"><i class="ti ti-sun"></i>'
            + '<input type="range" min="' + nl.brightness.min + '" max="' + nl.brightness.max + '" value="' + bval + '" data-humidifier-brightness data-humidifier-id="' + id + '">'
            + '<span class="humid-bright-val mono">' + bval + '%</span></div></div>';
        })()
      : "";

    nightlight = [
      '<div class="humid-night ' + (nlOn ? "on" : "") + '">',
      '<div class="humid-night-head">',
      '<span class="humid-night-title"><i class="ti ti-bulb"></i> Night Light</span>',
      '<button class="humid-switch ' + (nlOn ? "on" : "") + '" role="switch" aria-checked="' + (nlOn ? "true" : "false") + '" data-humidifier-nightlight="' + nlCmd + '" data-humidifier-id="' + id + '" title="Toggle night light"><span class="humid-switch-knob"></span></button>',
      '</div>',
      '<div class="humid-night-body">',
      colorRow,
      sceneRow,
      bright,
      '</div>',
      '</div>',
    ].join("");
  }

  return [
    '<article class="humid-card ' + statusClass + '">',
    head,
    orb,
    nightlight,
    '</article>',
  ].join("");
}

/* A device that cannot be controlled must not render as one that is simply off.

   `available` is three-valued and comes from the backend: false means we asked
   and the device is not controllable, null means we could not ask, absent means
   the source does not report availability (TP-Link switches poll their own
   state). Only false is worth shouting about, and it has to be shouted -- the
   north bedroom S505 lost its Matter node, its Home Assistant entity stopped
   existing, and the card went on drawing a live-looking rocker over "OFF" for
   days. See _home_assistant_card_availability() in web_app.py. */
function deviceUnavailability(device) {
  const dead = device.available === false;
  return { dead, reason: device.unavailable_reason || "Unavailable" };
}

function deviceStatusLine(device, dead, reason) {
  return dead
    ? `<i class="ti ti-alert-triangle" aria-hidden="true"></i> ${escapeHtml(reason)}`
    : escapeHtml(device.room || "");
}

function rockerAttrs(device, dead, reason, isOn) {
  return dead
    ? `disabled title="${escapeHtml(reason)}" aria-label="${escapeHtml(device.name)} is unavailable"`
    : `aria-label="${isOn ? "Turn off" : "Turn on"} ${escapeHtml(device.name)}"`;
}

function renderPlugSection(devices) {
  devices = applyDeviceOrder(devices, "smart_plug");
  const plugActionsEl = document.querySelector("#plugActions");
  if (plugActionsEl) {
    plugActionsEl.innerHTML = `
      <button class="quick-action-btn" data-plug-all="on">
        <span class="qa-label">All On</span>
        <span class="qa-caption">Power every outlet</span>
      </button>
      <button class="quick-action-btn" data-plug-all="off">
        <span class="qa-label">All Off</span>
        <span class="qa-caption">Cut power, save standby</span>
      </button>`;
  }

  if (devices.length === 0) {
    plugGrid.innerHTML = '<div class="empty">No TP-Link smart plugs found. Run discovery on the Orange Pi first.</div>';
    return;
  }

  plugGrid.innerHTML = devices.map((device) => {
    const isOn     = device.is_on === true;
    const watts    = Number(device.current_power ?? device.watts ?? 0);
    const maxWatts = Number(device.max_watts ?? 1500);
    const kwhToday = Number(device.kwh_today  ?? device.total_energy_today ?? 0);
    const nextCmd  = isOn ? "off" : "on";
    const { dead, reason } = deviceUnavailability(device);

    return `
      <div class="device-card new-style ${isOn ? "on" : ""}${dead ? " device-unavailable" : ""}"
           draggable="true"
           data-host="${device.host}"
           data-category="${escapeHtml(device.category || "")}">
        <div class="device-top">
          <div>
            <h3 class="device-name">${escapeHtml(device.name)}${device.provider === "matter" ? '<span class="matter-badge">MATTER</span>' : ""}</h3>
            <p class="device-status">${deviceStatusLine(device, dead, reason)}</p>
          </div>
          <div class="device-top-right">
            ${deviceDragHandle(device.host)}
            <button class="rocker ${isOn ? "on" : ""}"
              data-command="${nextCmd}"
              data-host="${device.host}"
              type="button"
              aria-pressed="${isOn}"
              ${rockerAttrs(device, dead, reason, isOn)}>
              <div class="rocker-pad"></div>
            </button>
          </div>
        </div>
        <div class="dial-center">
          ${buildPowerGauge(isOn, watts, maxWatts)}
        </div>
        <div class="device-footer">
          <span>TODAY</span>
          <span style="color:var(--t-text-dim)">${kwhToday.toFixed(1)} kWh</span>
          <span style="color:${dead ? "var(--red)" : isOn ? "var(--t-accent)" : "var(--t-text-dim2)"}">
            ${dead ? "UNAVAILABLE" : isOn ? "ON" : "OFF"}
          </span>
        </div>
      </div>`;
  }).join("");
}
function renderDeviceGroup(targetGrid, devices, emptyText) {
  if (devices.length === 0) {
    targetGrid.innerHTML = `<div class="empty">${emptyText}</div>`;
    return;
  }

  const isPlug = (d) => d.category === "smart_plug";

  targetGrid.innerHTML = devices.map((device) => {
    const isOn        = device.is_on === true;
    const nextCommand = isOn ? "off" : "on";
    const plug        = isPlug(device);
    const dimmable    = plug ? false : (device.is_dimmable !== false);
    /* Home Assistant reports no brightness for a light that is off, so without
       the recalled level the dial would open at a placeholder and then jump to
       the real one a second later. */
    rememberBrightness(device.host, device.brightness);
    const brightness  = device.brightness ?? recalledBrightness(device.host) ?? (isOn ? 100 : 10);
    const dimLocked   = dimmable && isDimLocked(device.host);
    const { dead, reason } = deviceUnavailability(device);

    return `
      <div class="device-card new-style ${isOn ? "on" : ""}${dead ? " device-unavailable" : ""}"
           draggable="false"
           data-drag-locked="true"
           data-host="${device.host}"
           data-category="${escapeHtml(device.category || "")}"
           data-dimmable="${dimmable}"
           data-brightness="${brightness}"
           data-dim-locked="${dimLocked}">
        <div class="device-top">
          <div>
            <h3 class="device-name">${escapeHtml(device.name)}${device.provider === "matter" ? '<span class="matter-badge">MATTER</span>' : ""}</h3>
            <p class="device-status">${deviceStatusLine(device, dead, reason)}</p>
          </div>
          <div class="device-top-right">
            ${deviceDragHandle(device.host)}
            ${dimmable ? `
              <button class="dim-lock-btn ${dimLocked ? "locked" : ""}"
                data-dim-lock="${escapeHtml(device.host)}"
                title="${dimLocked ? "Unlock brightness" : "Lock brightness"}"
                type="button">
                <i class="ti ti-lock${dimLocked ? "" : "-open"}"></i>
              </button>` : ""}
            <button class="rocker ${isOn ? "on" : ""}"
              data-command="${nextCommand}"
              data-host="${device.host}"
              type="button"
              aria-pressed="${isOn}"
              ${rockerAttrs(device, dead, reason, isOn)}>
              <div class="rocker-pad"></div>
            </button>
          </div>
        </div>
        <div class="dial-center dim-control-row">
          ${buildDimControlDial(brightness, isOn, dimmable)}
        </div>
        <div class="device-footer">
          <span>${plug ? "TODAY" : (dimmable ? "DIM" : "FIXED")}</span>
          <span style="color:${dead ? "var(--red)" : isOn ? "var(--t-accent)" : "var(--t-text-dim2)"}">
            ${dead ? "UNAVAILABLE" : isOn ? "ON" : "OFF"}
          </span>
          <span>${plug ? escapeHtml(device.model || device.type || "") : (dimmable ? "BRIGHT" : "100%")}</span>
        </div>
      </div>`;
  }).join("");

  // Attach brightness drag to all dimmable cards
  targetGrid.querySelectorAll(".device-card[data-dimmable='true']").forEach(attachDimDrag);
  applyLightDragLockState();
}

/* ── Capability count for N-IN-1 badge ── */
function countCapabilities(device) {
  const dc  = String(device.device_class || "").toLowerCase();
  const cat = String(device.category    || "").toLowerCase();
  let n = 0;
  if (dc === "temperature"  || cat.includes("temperature"))                             n++;
  if (dc === "humidity"     || cat.includes("humidity"))                                n++;
  if (dc === "illuminance"  || cat.includes("illuminance"))                             n++;
  if (["occupancy","motion","moving"].includes(dc) || cat.includes("occupancy") || cat.includes("motion")) n++;
  if (dc === "moisture" || dc === "problem" || cat.includes("moisture") || cat.includes("leak")) n++;
  if (dc === "smoke"    || cat.includes("smoke"))                                       n++;
  if (["door","window","garage_door","opening"].includes(dc))                           n++;
  return Math.max(n, 1);
}

function sensorCapabilityKey(device) {
  const dc  = String(device.device_class || "").toLowerCase();
  const cat = String(device.category || "").toLowerCase();
  if (dc === "temperature" || cat.includes("temperature")) return "temperature";
  if (dc === "humidity" || cat.includes("humidity")) return "humidity";
  if (dc === "illuminance" || cat.includes("illuminance")) return "illuminance";
  if (["occupancy", "motion", "moving"].includes(dc) || cat.includes("occupancy") || cat.includes("motion")) return "motion";
  if (dc === "battery" || cat.includes("battery")) return "battery";
  if (dc === "moisture" || dc === "problem" || cat.includes("moisture") || cat.includes("leak")) return "water";
  if (dc === "smoke" || cat.includes("smoke")) return "smoke";
  if (["door", "window", "garage_door", "opening"].includes(dc)) return "door";
  return device.id || device.name;
}

function countUniqueSensorCapabilities(readings) {
  return Math.max(new Set(readings.map(sensorCapabilityKey)).size, 1);
}

/* ── Environment / Sensors split ──
   One physical device can report temperature, humidity, leak and smoke at
   once. It appears in both views, filtered to the readings each view owns,
   so nothing is hidden. Battery rides along in both as context. */
const ENVIRONMENT_CAPABILITIES = new Set(["temperature", "humidity"]);

/* The eight capability keys sensorCapabilityKey() can actually classify a
   reading into. Anything else means it fell through to the id/name
   fallback -- i.e. an unrecognised capability, not a "sensors" capability. */
const KNOWN_SENSOR_CAPABILITIES = new Set([
  "temperature", "humidity", "illuminance", "motion",
  "battery", "water", "smoke", "door",
]);

function filterReadingsForView(readings, mode) {
  if (mode !== "environment" && mode !== "sensors" && mode !== "motion") return readings;
  return readings.filter((reading) => {
    const key = sensorCapabilityKey(reading);
    if (key === "battery") return true;
    /* Motion is a narrowing of Sensors, not a slice alongside it: the same
       reading still appears there. A combined "Motion sensor and TH" therefore
       shows occupancy here and temperature in Environment, rather than being
       moved out of one to appear in the other. */
    if (mode === "motion") return key === "motion";
    return mode === "environment"
      ? ENVIRONMENT_CAPABILITIES.has(key)
      : !ENVIRONMENT_CAPABILITIES.has(key);
  });
}

/* A battery reading alone must not conjure a card into either view, and
   neither may a reading whose capability key isn't one of the eight known
   kinds (e.g. a direct/local Tuya device with no device_class, whose raw
   reading falls back to its id/name). The one exception: if a device has
   NO recognised capability at all -- not even battery -- it still needs a
   home so it doesn't vanish from the dashboard entirely, and Sensors is
   that home (Environment stays reserved for genuine temperature/humidity). */
function groupHasViewContent(group, mode) {
  const expanded = expandSensorReadings(group.readings);

  const viewReadings = filterReadingsForView(expanded, mode);
  const hasOwnedCapability = viewReadings.some((reading) => {
    const key = sensorCapabilityKey(reading);
    return key !== "battery" && KNOWN_SENSOR_CAPABILITIES.has(key);
  });
  if (hasOwnedCapability) return true;

  /* Sensors is the catch-all, so it also takes anything unclassifiable. Motion
     is the opposite: no motion reading, no tile, or every temperature sensor in
     the house would appear here holding only a battery percentage. */
  if (mode === "motion") return false;

  const hasAnyKnownCapability = expanded.some((reading) =>
    KNOWN_SENSOR_CAPABILITIES.has(sensorCapabilityKey(reading))
  );
  return mode === "sensors" && !hasAnyKnownCapability;
}

/* The Sensors and Environment tiles are two views of the same sensor groups, so
   both filter the same universe - and both have to respect a group the user
   moved a sensor out of. "sensors" is the tuya group's id for historical
   reasons; the tile is labelled Sensors. */
function sensorTileGroupId(mode) {
  if (mode === "environment") return "environment";
  if (mode === "motion") return "motion";
  return "tuya";
}

function visibleSensorGroups(mode) {
  const visible = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  const groupId = sensorTileGroupId(mode);
  return groupSensorDevices(visible)
    .filter((g) => !isBridgeSensorGroup(g))
    .filter((g) => groupHasViewContent(g, mode))
    .filter((g) => !isExcludedFromGroup(`sensor:${areaSlug(g.name)}`, groupId));
}

function sensorGroupCount(mode) {
  return visibleSensorGroups(mode).length;
}

/* Device groups backing the Sensors tile, collapsed to one online flag per
   group so onlineOf() can summarize groups instead of raw readings -- the
   same universe sensorGroupCount("sensors") counts. */
function sensorsTileGroups() {
  return visibleSensorGroups("sensors")
    .map((g) => ({ online: g.readings.some((d) => d.online !== false) }));
}

/* ── Sensor device grouping ── */
const SENSOR_SUFFIXES = [
  ' Temperature', ' Humidity', ' Illuminance',
  ' Battery', ' Door', ' Window', ' Moisture',
  ' Occupancy', ' Motion', ' Smoke', ' Tamper', ' Problem',
];

function sensorBaseName(name) {
  const n = name.trim();
  for (const s of SENSOR_SUFFIXES) {
    if (n.endsWith(s)) return n.slice(0, -s.length).trim();
  }
  return n;
}

function groupSensorDevices(devices) {
  const map = new Map();
  for (const d of devices) {
    const key = sensorBaseName(d.name);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(d);
  }
  return [...map.entries()]
    .map(([name, readings]) => ({ name, readings }))
    .sort((a, b) => {
      const aAlert = a.readings.some(isSensorIncident);
      const bAlert = b.readings.some(isSensorIncident);
      if (aAlert !== bAlert) return aAlert ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
}

function sensorDeviceSubtitle(readings) {
  const labels = readings.map((r) => {
    return String(r.category || "").replace("tuya_", "").replace(/_/g, " ") || "sensor";
  });
  const unique = [...new Set(labels)];
  if (unique.length === 0) return "sensor";
  if (unique.length === 1) return `${unique[0]} sensor`;
  const last = unique[unique.length - 1];
  return unique.slice(0, -1).join(", ") + " & " + last + " sensor";
}

function tempComfortLabel(c) {
  if (c < 16) return "Cold";
  if (c < 20) return "Cool";
  if (c < 24) return "Comfortable";
  if (c < 28) return "Warm";
  return "Hot";
}

function humidComfortLabel(pct) {
  if (pct < 30) return "Dry";
  if (pct < 55) return "Comfortable";
  if (pct < 70) return "Humid";
  return "Very Humid";
}

function lxComfortLabel(lx) {
  if (lx < 50) return "Dark";
  if (lx < 200) return "Dim";
  if (lx < 500) return "Moderate";
  return "Bright";
}

function readingMetricNumber(device) {
  const raw = device.state ?? Object.values(device.values || {})[0];
  const match = String(raw ?? "").match(/-?\d+(?:\.\d+)?/);
  if (!match) return NaN;
  return Number(match[0]);
}

function directSensorValue(device, aliases) {
  const values = device.values || {};
  for (const [key, value] of Object.entries(values)) {
    const normalized = String(key).toLowerCase().replace(/[^a-z0-9]+/g, "_");
    if (aliases.some((alias) => normalized.includes(alias))) {
      return value;
    }
  }
  return undefined;
}

function syntheticSensorReading(device, suffix, deviceClass, category, value) {
  const baseId = device.id || device.name || "tuya-sensor";
  const baseName = sensorBaseName(device.name || "Tuya sensor");
  return {
    ...device,
    id: String(baseId) + "-" + deviceClass,
    entity_id: String(device.entity_id || baseId) + "-" + deviceClass,
    name: baseName + " " + suffix,
    device_class: deviceClass,
    category,
    state: value,
    values: { State: value },
    source: device.source || "direct",
    controllable: false,
  };
}

function expandSensorReadings(readings) {
  const expanded = [...readings];
  for (const device of readings) {
    const values = device.values || {};
    if (!values || Object.keys(values).length === 0) continue;
    const base = sensorBaseName(device.name);
    const hasKind = (kind) => expanded.some((reading) =>
      sensorBaseName(reading.name) === base &&
      (String(reading.device_class || "").toLowerCase() === kind || String(reading.category || "").toLowerCase().includes(kind))
    );

    const temp = directSensorValue(device, ["temperature", "temp_current", "temp", "va_temperature"]);
    if (temp !== undefined && !hasKind("temperature")) {
      expanded.push(syntheticSensorReading(device, "Temperature", "temperature", "tuya_temperature", temp));
    }

    const humidity = directSensorValue(device, ["humidity", "va_humidity"]);
    if (humidity !== undefined && !hasKind("humidity")) {
      expanded.push(syntheticSensorReading(device, "Humidity", "humidity", "tuya_humidity", humidity));
    }

    const illuminance = directSensorValue(device, ["illuminance", "illuminance_value", "lux"]);
    if (illuminance !== undefined && !hasKind("illuminance")) {
      expanded.push(syntheticSensorReading(device, "Illuminance", "illuminance", "tuya_illuminance", illuminance));
    }

    const motion = directSensorValue(device, ["motion", "occupancy", "presence", "presence_state", "pir"]);
    if (motion !== undefined && !hasKind("occupancy")) {
      expanded.push(syntheticSensorReading(device, "Occupancy", "occupancy", "tuya_occupancy", motion));
    }
  }
  return expanded;
}

/* ── Device-type presentation registry ──
   One icon and one hue per capability key, so the same device_class always
   reads the same whether the reading arrived from Zigbee, Tuya direct or
   Home Assistant. Keys are the ones sensorCapabilityKey() returns, plus
   "window" (a door-class refinement) and the "sensor" fallback. */
/* Icon and wording per sensor type. Deliberately no colour: the type is
   carried by the icon and the label, which say it precisely, where a hue only
   hints at it. Nine hues across fourteen types turned a grid of these tiles
   into a colour chart nobody could read. */
const SENSOR_TYPE_META = {
  temperature: { icon: "ti-temperature",    label: "Temperature" },
  humidity:    { icon: "ti-droplet",        label: "Humidity"    },
  illuminance: { icon: "ti-sun",            label: "Light level" },
  motion:      { icon: "ti-radar-2",        label: "Motion"      },
  door:        { icon: "ti-door",           label: "Door"        },
  window:      { icon: "ti-window",         label: "Window"      },
  water:       { icon: "ti-droplet-filled", label: "Leak"        },
  smoke:       { icon: "ti-flame",          label: "Smoke"       },
  tamper:      { icon: "ti-shield-lock",    label: "Tamper"      },
  problem:     { icon: "ti-alert-hexagon",  label: "Status"      },
  battery:     { icon: "ti-battery-3",      label: "Battery"     },
  light:       { icon: "ti-bulb",           label: "Light"       },
  environment: { icon: "ti-temperature",    label: "Environment" },
  sensor:      { icon: "ti-radar-2",        label: "Sensor"      },
};

/* The whole palette these tiles may use, and there are only two entries:
   red means something wants attention, the theme accent means everything else.
   A reading's *type* is never coloured - only its urgency is - so a wall of
   sensors reads as calm until one of them is not. */
function sensorTileHue(needsAttention) {
  return needsAttention ? "var(--red)" : "var(--t-accent)";
}

function sensorTypeMeta(key) {
  return SENSOR_TYPE_META[key] || SENSOR_TYPE_META.sensor;
}

/* Battery is context on these tiles, never the headline -- it gets an icon
   that reflects the real level and a hue that only shouts when it should. */
function batteryMeta(pct) {
  return {
    icon: pct > 75 ? "ti-battery-4" : pct > 50 ? "ti-battery-3" : pct > 25 ? "ti-battery-2" : "ti-battery-1",
    /* The level is already in the icon and the number beside it, so colour is
       spent only on the one case worth interrupting for. */
    hue: pct > 20 ? "" : "var(--red)",
  };
}

function sensorTileIcon(key, cls, hue) {
  const meta = sensorTypeMeta(key);
  const style = hue ? ` style="color:${hue}"` : "";
  return `<i class="ti ${meta.icon}${cls ? " " + cls : ""}"${style} aria-hidden="true"></i>`;
}

/* One small icon-and-value pair in the tile's footer line. */
function sensorTileFacet(facet) {
  /* Only a tripped facet is coloured; the rest inherit the tile's text colour. */
  return `<span class="sdc-tile-m">${sensorTileIcon(facet.key, "", facet.detected ? sensorTileHue(true) : "")}${escapeHtml(facet.text)}</span>`;
}

/* ── Sensor device tile ──
   A device-type-tinted tile: one headline reading, the type icon as an
   oversized watermark, and everything else as small pairs under the name.
   Which reading gets to be the headline depends on the view -- Environment
   opens on a number, Sensors opens on the state that made you look. */
function renderSensorDeviceCard(group, mode) {
  const { name } = group;
  const readings = filterReadingsForView(expandSensorReadings(group.readings), mode);
  const capN = countUniqueSensorCapabilities(readings);

  const findCat = (kw) => readings.find((d) => String(d.category || "").includes(kw));
  const tempDev  = findCat("temperature");
  const humDev   = findCat("humidity");
  const illumDev = findCat("illuminance");
  const battDev  = findCat("battery");
  const doorDev  = readings.find((d) => {
    const dc = String(d.device_class || "").toLowerCase();
    return ["door", "window", "garage_door", "opening"].includes(dc);
  });
  const moistDev  = findCat("moisture");
  const occDev    = readings.find((d) => {
    const dc = String(d.device_class || "").toLowerCase();
    return ["occupancy", "motion", "moving"].includes(dc) || String(d.category || "").includes("occupancy");
  });
  const smokeDev  = findCat("smoke");
  const tamperDev = findCat("tamper");
  const problemDev = findCat("problem");
  const lightDev  = findCat("light");

  const alertDevices = [doorDev, moistDev, occDev, smokeDev, tamperDev, problemDev].filter(Boolean);
  const hasAlert = alertDevices.some(isSensorIncident);

  /* Numeric readings, most headline-worthy first. */
  const numeric = [];
  const pushNumeric = (device, key, unit, round) => {
    if (!device) return;
    const val = readingMetricNumber(device);
    if (!Number.isFinite(val)) return;
    const shown = round ? String(Math.round(val)) : val.toFixed(1);
    numeric.push({ key, value: shown, unit, text: shown + unit });
  };
  pushNumeric(tempDev, "temperature", "°C", false);
  pushNumeric(humDev, "humidity", "%", true);
  pushNumeric(illumDev, "illuminance", " lx", true);

  /* Binary readings, in the order they deserve attention. */
  const binary = [];
  const pushBinary = (device, key, onWord, offWord) => {
    if (!device) return;
    const detected = isAlertDetected(device);
    binary.push({ key, detected, text: detected ? onWord : offWord });
  };
  pushBinary(smokeDev, "smoke", "Smoke", "Clear");
  pushBinary(moistDev, "water", "Leak", "Dry");
  pushBinary(doorDev,
    String(doorDev?.device_class || "").toLowerCase() === "window" ? "window" : "door",
    "Open", "Closed");
  pushBinary(occDev, "motion", "Motion", "Clear");
  pushBinary(tamperDev, "tamper", "Tamper", "Secure");
  pushBinary(problemDev, "problem", "Problem", "OK");

  /* The headline. A tripped sensor always wins; otherwise Environment leads
     with its number and Sensors leads with its state. A device we cannot
     classify at all still gets a headline: whatever it is actually reporting. */
  const tripped = binary.find((b) => b.detected);
  const preferred = mode === "environment"
    ? [...numeric, ...binary]
    : [...binary, ...numeric];
  const hero = tripped || preferred[0] ||
    (lightDev ? { key: "light", text: lightDev.is_on ? "On" : "Off" } : null) || {
      key: "sensor",
      text: readings[0] ? primaryTuyaState(readings[0]) : "No reading",
    };

  const heroMeta = sensorTypeMeta(hero.key);
  const tint = sensorTileHue(hasAlert && Boolean(hero.detected));

  const heroHtml = hero.value !== undefined
    ? `<div class="sdc-tile-big">${escapeHtml(hero.value)}<span class="sdc-tile-unit">${escapeHtml(hero.unit)}</span></div>`
    : `<div class="sdc-tile-state">${escapeHtml(hero.text)}</div>`;

  /* Everything the headline did not take, capped so a 4-in-1 sensor stays
     legible at tile size -- the full breakdown is a tap away. */
  const rest = [...numeric, ...binary].filter((f) => f !== hero).slice(0, 3);
  const facets = rest.map(sensorTileFacet).join("");

  let battHtml = "";
  let battFacet = "";
  if (battDev) {
    const bPct = Number(battDev.state);
    if (Number.isFinite(bPct)) {
      const { icon, hue } = batteryMeta(bPct);
      const pct = Math.round(bPct);
      battHtml = `<span class="sdc-tile-batt"><i class="ti ${icon}" style="color:${hue}" aria-hidden="true"></i>${pct}</span>`;
      battFacet = `<span class="sdc-tile-m"><i class="ti ${icon}" style="color:${hue}" aria-hidden="true"></i>${pct}%</span>`;
    }
  }

  /* A Tuya LED strip surfaced as a light keeps its switch. The full-size
     rocker is far too big for a tile, so it becomes a compact power button
     carrying the same data-tuya-command the click handler already listens for. */
  let lightHtml = "";
  if (lightDev) {
    lightHtml = `<button class="sdc-tile-power${lightDev.is_on ? " on" : ""}"
      data-tuya-command="${lightDev.is_on ? "off" : "on"}"
      data-device-id="${escapeHtml(lightDev.id)}"
      data-device-source="${lightDev.source || "direct"}"
      title="${lightDev.is_on ? "Turn off" : "Turn on"}"
      aria-label="${lightDev.is_on ? "Turn off" : "Turn on"} ${escapeHtml(name)}"
      type="button"><i class="ti ti-power" aria-hidden="true"></i></button>`;
  }

  const subHtml = facets || (lightHtml ? battFacet : "") ||
    `<span class="sdc-tile-note">${escapeHtml(sensorDeviceSubtitle(readings))}</span>`;
  const offline = readings.length > 0 && readings.every((d) => d.online === false);
  const badge = capN > 1 ? `${capN}-in-1` : heroMeta.label;

  return `<article class="sdc-tile${hasAlert ? " sdc-tile-alert" : ""}${offline ? " sdc-tile-offline" : ""}"
    data-device-id="${escapeHtml(name)}" style="--tint:${tint}">
    ${sensorTileIcon(hero.key, "sdc-tile-mark")}
    <div class="sdc-tile-top">
      <span class="sdc-tile-badge">${sensorTileIcon(hero.key)}${escapeHtml(badge)}</span>
      ${lightHtml || battHtml}
    </div>
    <div class="sdc-tile-read">
      ${heroHtml}
      <h3 class="sdc-tile-name" title="${escapeHtml(name)}">${escapeHtml(name)}</h3>
      <div class="sdc-tile-sub">${subHtml}</div>
    </div>
  </article>`;
}

/* ── Tuya sensors ── */
function renderTuyaDevices(devices) {
  latestTuyaDevices = devices;
  const visibleDevices = groupMemberData("tuya", ["sensor"]).flatMap((g) => g.readings).filter((d) => !isTuyaCamera(d));
  if (tuyaCount) tuyaCount.textContent = String(sensorGroupCount("sensors"));

  if (visibleDevices.length === 0) {
    const anyTuyaDevices = latestTuyaDevices.filter((d) => !isTuyaCamera(d)).length > 0;
    const message = anyTuyaDevices
      ? "No devices in this group. Use Manage to add some."
      : "No Tuya devices found from Home Assistant yet.";
    tuyaGrid.innerHTML = `<div class="empty">${message}</div>`;
    renderForeignKinds("tuya", ["sensor"], "#tuyaGrid");
    renderMotionSensors();
    return;
  }

  // Auto-surface fire/smoke notifications
  visibleDevices.forEach((device) => {
    const dc  = String(device.device_class || "").toLowerCase();
    const cat = String(device.category    || "").toLowerCase();
    if ((dc === "smoke" || cat.includes("smoke")) && isAlertDetected(device)) {
      pushNotification("fire", `Fire alarm — ${escapeHtml(device.name)}`, "Smoke detected", { deviceId: device.id });
    }
  });

  const groups = groupSensorDevices(visibleDevices).filter((g) => groupHasViewContent(g, "sensors"));

  const alertGroupCount = groups.filter((g) => g.readings.some(isSensorIncident)).length;

  const banner = alertGroupCount
    ? `<div class="sdc-alert-banner"><i class="ti ti-alert-triangle"></i> ${alertGroupCount} device${alertGroupCount > 1 ? "s" : ""} need${alertGroupCount > 1 ? "" : "s"} attention</div>`
    : "";

  tuyaGrid.innerHTML = banner + groups.map((g) => renderSensorDeviceCard(g, "sensors")).join("");
  renderDevicesOverview();
  renderEnvironmentSensors();
  renderMotionSensors();
  renderForeignKinds("tuya", ["sensor"], "#tuyaGrid");
}

/* ── Motion ──

   A narrowing of the same sensor groups the Sensors view draws, filtered to the
   motion capability. sensorCapabilityKey() already folds occupancy, motion and
   moving into one key, so a sensor added later is picked up with no
   configuration -- which is the point, since more of them are coming. */
function motionDetectedIn(group) {
  return filterReadingsForView(expandSensorReadings(group.readings), "motion")
    .some((reading) => sensorCapabilityKey(reading) === "motion" && isAlertDetected(reading));
}

function motionSummary() {
  const groups = visibleSensorGroups("motion");
  if (groups.length === 0) return "No sensors";
  const active = groups.filter(motionDetectedIn).length;
  return active ? `${active} detecting` : "All clear";
}

function renderMotionSensors() {
  if (!motionGrid) return;
  const groups = visibleSensorGroups("motion");
  if (motionCount) motionCount.textContent = String(groups.length);

  if (groups.length === 0) {
    motionGrid.innerHTML =
      '<div class="empty">No motion sensors found. Sensors reporting occupancy or motion appear here automatically.</div>';
    renderForeignKinds("motion", ["sensor"], "#motionGrid");
    return;
  }

  /* Detecting first, then alphabetical: the one that just tripped is the reason
     anyone opened this view, and a stable order underneath keeps the rest from
     jumping around as states change. */
  const ordered = [...groups].sort((a, b) => {
    const diff = Number(motionDetectedIn(b)) - Number(motionDetectedIn(a));
    return diff || String(a.name).localeCompare(String(b.name));
  });

  const active = ordered.filter(motionDetectedIn).length;
  const banner = active
    ? `<div class="sdc-alert-banner motion-banner"><i class="ti ti-walk"></i> ${active} sensor${active > 1 ? "s" : ""} detecting motion</div>`
    : "";

  motionGrid.innerHTML = banner + ordered.map((g) => renderSensorDeviceCard(g, "motion")).join("");
  renderForeignKinds("motion", ["sensor"], "#motionGrid");
}

function motionLogRowHtml(event) {
  const detected = String(event.state) === "on";
  const when = new Date((Number(event.ts) || 0) * 1000);
  const time = Number.isFinite(when.getTime())
    ? when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "--:--:--";
  const held = Number(event.duration_s);
  const detail = detected
    ? "Detected"
    : Number.isFinite(held) ? `Cleared · ${formatMotionDuration(held)}` : "Cleared";
  return `<div class="motion-row${detected ? "" : " cleared"}">
      <span class="motion-time">${escapeHtml(time)}</span>
      <span class="motion-dot" aria-hidden="true"></span>
      <span class="motion-name">${escapeHtml(String(event.name || event.entity_id || ""))}</span>
      <span class="motion-event">${escapeHtml(detail)}</span>
    </div>`;
}

function formatMotionDuration(seconds) {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  const mins = Math.floor(total / 60);
  if (mins < 60) return `${mins}m ${String(total % 60).padStart(2, "0")}s`;
  return `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m`;
}

/* How many rows the log shows before you ask for more. The fortnight of history
   is still fetched and still there - but rendering all of it pushed everything
   below the log off the bottom of the page, and grew as the house did. */
const MOTION_LOG_COLLAPSED = 8;
let motionLogEvents = [];
let motionLogExpanded = false;

function renderMotionLog(events) {
  if (!motionLog) return;
  motionLogEvents = events;
  if (!events.length) {
    motionLog.innerHTML =
      '<div class="empty">No motion recorded yet. Events appear here as sensors trip.</div>';
    return;
  }

  const shown = motionLogExpanded ? events : events.slice(0, MOTION_LOG_COLLAPSED);
  /* Grouped by day, because "19:58" means nothing without knowing which day,
     and the log keeps a fortnight. */
  let lastDay = "";
  const rows = shown.map((event) => {
    const day = new Date((Number(event.ts) || 0) * 1000).toDateString();
    const header = day === lastDay ? "" : `<div class="motion-day">${escapeHtml(day)}</div>`;
    lastDay = day;
    return header + motionLogRowHtml(event);
  });

  const hidden = events.length - shown.length;
  const toggle = motionLogExpanded
    ? `<button class="motion-log-more" type="button" data-motion-log-toggle>Show fewer</button>`
    : hidden > 0
      ? `<button class="motion-log-more" type="button" data-motion-log-toggle>Show ${hidden} older</button>`
      : "";

  motionLog.classList.toggle("expanded", motionLogExpanded);
  motionLog.innerHTML = rows.join("") + toggle;
}

document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-motion-log-toggle]")) return;
  motionLogExpanded = !motionLogExpanded;
  /* Re-rendered from what was already fetched, so expanding costs no request. */
  renderMotionLog(motionLogEvents);
});

async function loadMotionLog() {
  if (!motionLog) return;
  try {
    const payload = await requestJson("/api/motion/log?limit=100");
    renderMotionLog(payload.events || []);
  } catch (err) {
    /* The tiles above are still useful without the history, so a failed log
       reports itself in place instead of blanking the view. */
    motionLog.innerHTML = '<div class="empty">Motion log unavailable.</div>';
    console.error(err);
  }
}

/* ── Environment (temperature & humidity) ── */
function renderEnvironmentSensors() {
  const grid = document.querySelector("#environmentGrid");
  const badge = document.querySelector("#environmentCount");
  const visible = groupMemberData("environment", ["sensor"]).flatMap((g) => g.readings).filter((d) => !isTuyaCamera(d));
  const groups = groupSensorDevices(visible).filter((g) => groupHasViewContent(g, "environment"));

  const total = groups.length + latestEnvironmentSensors.length;
  if (badge) badge.textContent = String(total);
  if (!grid) return;
  if (total === 0) {
    const fullTotal = sensorGroupCount("environment") + latestEnvironmentSensors.length;
    const message = fullTotal === 0
      ? "No temperature or humidity sensors reporting yet."
      : "No devices in this group. Use Manage to add some.";
    grid.innerHTML = `<div class="empty">${message}</div>`;
    renderForeignKinds("environment", ["sensor", "environment"], "#environmentGrid");
    return;
  }
  grid.innerHTML =
    latestEnvironmentSensors.map(environmentSensorCard).join("") +
    groups.map((g) => renderSensorDeviceCard(g, "environment")).join("");
  renderForeignKinds("environment", ["sensor", "environment"], "#environmentGrid");
  loadCo2History();
}

function primaryTuyaState(device) {
  const values = Object.values(device.values || {});
  if (values.length > 0) return String(values[0]);
  if (device.status) return formatStatus(device.status);
  return device.online ? "Online" : "Unavailable";
}

function activeTuyaSensorState(device) {
  const state = primaryTuyaState(device).toLowerCase();
  if (["on", "open", "wet", "detected", "problem", "smoke"].includes(state)) return true;
  if (device.category?.includes("battery")) {
    const number = Number.parseFloat(state);
    return Number.isFinite(number) && number <= 30;
  }
  return false;
}

function tuyaHaIcon(device) {
  const category = `${device.category || ""} ${device.domain || ""} ${device.device_class || ""}`.toLowerCase();
  if (category.includes("light"))     return '<i class="ti ti-bulb" aria-hidden="true"></i>';
  if (category.includes("switch"))    return '<i class="ti ti-plug" aria-hidden="true"></i>';
  if (category.includes("temperature")) return '<i class="ti ti-temperature" aria-hidden="true"></i>';
  if (category.includes("humidity"))  return '<i class="ti ti-droplet" aria-hidden="true"></i>';
  if (category.includes("battery"))   return '<i class="ti ti-battery-2" aria-hidden="true"></i>';
  if (category.includes("door"))      return '<i class="ti ti-door" aria-hidden="true"></i>';
  if (category.includes("moisture") || category.includes("water")) return '<i class="ti ti-droplet" aria-hidden="true"></i>';
  if (category.includes("occupancy") || category.includes("motion")) return '<i class="ti ti-radar-2" aria-hidden="true"></i>';
  if (category.includes("smoke"))     return '<i class="ti ti-flame" aria-hidden="true"></i>';
  if (category.includes("tamper") || category.includes("problem")) return '<i class="ti ti-alert-triangle" aria-hidden="true"></i>';
  return '<i class="ti ti-device-unknown" aria-hidden="true"></i>';
}

/* ── Thermostat / Climate ── */
const THERMO_MODE_COLORS = { heat: "#FF8A5C", cool: "#5FC0EA", auto: "#7ED9A0" };
const THERMO_PRESETS = [
  { id: "home",  name: "Home",  caption: "Comfort setpoint", target: 22, mode: "auto" },
  { id: "away",  name: "Away",  caption: "Energy saving",    target: 18, mode: "auto" },
  { id: "sleep", name: "Sleep", caption: "Cooler overnight", target: 19, mode: "cool" },
];

function tempRangeColor(c) {
  if (c < 16) return "#5FC0EA";
  if (c < 21) return "#22d3ee";
  if (c < 25) return "#7ED9A0";
  if (c < 29) return "#fbbf24";
  return "#ef4444";
}

function thermoModeIcon(mode) {
  if (mode === "heat") return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2c0 0-4 5-4 9a4 4 0 008 0c0-4-4-9-4-9z"/><line x1="9" y1="17" x2="9" y2="21"/><line x1="12" y1="17" x2="12" y2="22"/><line x1="15" y1="17" x2="15" y2="21"/></svg>`;
  if (mode === "cool") return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="12" y1="2" x2="12" y2="22"/><polyline points="17 7 12 12 7 7"/><polyline points="17 17 12 12 7 17"/><line x1="2" y1="12" x2="22" y2="12"/><polyline points="7 7 2 12 7 17"/><polyline points="17 7 22 12 17 17"/></svg>`;
  if (mode === "auto") return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a9 9 0 100 18A9 9 0 0012 3z"/><path d="M12 8v4l3 3"/></svg>`;
  return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M18.36 6.64A9 9 0 1112 3"/><line x1="12" y1="2" x2="12" y2="12"/></svg>`;
}

const thermoUIState = new Map();

function getThermoUI(thermostat) {
  const id = thermostat.id;
  if (!thermoUIState.has(id)) {
    const raw = thermostat.desired_heat ?? thermostat.desired_cool ?? thermostat.temperature ?? 22;
    thermoUIState.set(id, {
      target: Math.max(10, Math.min(32, Math.round(Number(raw) || 22))),
      mode:   thermostat.hvac_mode || "auto",
      fan:    "auto",
      preset: thermostat.preset_mode || null,
    });
  }
  return thermoUIState.get(id);
}

function buildThermoDial(thermostatId, ui, currentTemp) {
  const MIN = 10, MAX = 32, SEGS = 40;
  const pct = (ui.target - MIN) / (MAX - MIN);
  const litSegs = Math.round(pct * SEGS);
  const arcColor = THERMO_MODE_COLORS[ui.mode] || "var(--t-text-dim2)";

  let lines = "";
  for (let i = 0; i < SEGS; i++) {
    const a0 = -135 + (270 / SEGS) * i;
    const a  = (a0 * Math.PI) / 180;
    const r1 = 92, r2 = 80;
    const x1 = (100 + r1 * Math.cos(a)).toFixed(2);
    const y1 = (100 + r1 * Math.sin(a)).toFixed(2);
    const x2 = (100 + r2 * Math.cos(a)).toFixed(2);
    const y2 = (100 + r2 * Math.sin(a)).toFixed(2);
    const lit = ui.mode !== "off" && i < litSegs;
    const stroke = lit ? arcColor : "var(--t-seg-off)";
    const filt   = lit ? `drop-shadow(0 0 3px ${arcColor}99)` : "none";
    lines += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="4.5" stroke-linecap="round" stroke="${stroke}" style="filter:${filt}"/>`;
  }

  const statusText = ui.mode === "off" ? "Off"
    : ui.mode === "heat" ? `Heating to ${ui.target}°`
    : ui.mode === "cool" ? `Cooling to ${ui.target}°`
    : `Auto · ${ui.target}°`;
  const statusColor = ui.mode === "off" ? "var(--t-text-dim2)" : arcColor;

  return `
    <div class="thermo-dial-wrap" data-thermo-dial="${escapeHtml(thermostatId)}">
      <svg viewBox="0 0 200 200" class="thermo-dial-svg" aria-hidden="true">${lines}</svg>
      <div class="thermo-knob">
        <span class="thermo-target-num">${ui.target}°</span>
        <span class="thermo-current-lbl">Current ${currentTemp}°</span>
        <span class="thermo-status-lbl" style="color:${statusColor}">${statusText}</span>
      </div>
    </div>`;
}

function refreshThermoDial(thermostatId) {
  const ui = thermoUIState.get(thermostatId);
  if (!ui) return;

  const MIN = 10, MAX = 32, SEGS = 40;
  const litSegs  = Math.round(((ui.target - MIN) / (MAX - MIN)) * SEGS);
  const arcColor = THERMO_MODE_COLORS[ui.mode] || "var(--t-text-dim2)";

  /* The same thermostat can be shown in both the Climate view and the Home
     panel — keep every dial instance in sync. */
  document.querySelectorAll(`.thermo-dial-wrap[data-thermo-dial="${CSS.escape(thermostatId)}"]`).forEach((wrap) => {
    wrap.querySelectorAll(".thermo-dial-svg line").forEach((ln, i) => {
      const lit = ui.mode !== "off" && i < litSegs;
      ln.setAttribute("stroke", lit ? arcColor : "var(--t-seg-off)");
      ln.style.filter = lit ? `drop-shadow(0 0 3px ${arcColor}99)` : "none";
    });

    const numEl    = wrap.querySelector(".thermo-target-num");
    const statusEl = wrap.querySelector(".thermo-status-lbl");
    if (numEl) numEl.textContent = `${ui.target}°`;
    if (statusEl) {
      statusEl.textContent = ui.mode === "off" ? "Off"
        : ui.mode === "heat" ? `Heating to ${ui.target}°`
        : ui.mode === "cool" ? `Cooling to ${ui.target}°`
        : `Auto · ${ui.target}°`;
      statusEl.style.color = ui.mode === "off" ? "var(--t-text-dim2)" : arcColor;
    }
  });
}

function thermoArticlesFor(thermostatId) {
  return document.querySelectorAll(`article.thermo-card[data-thermostat-id="${CSS.escape(thermostatId)}"]`);
}

function applyThermoModeUI(article, thermoId, newMode) {
  const ui = thermoUIState.get(thermoId);
  if (!ui) return;
  ui.mode   = newMode;
  ui.preset = null;
  article.querySelectorAll(".thermo-mode-btn").forEach((b) => {
    const m      = b.dataset.thermoMode;
    const mColor = THERMO_MODE_COLORS[m];
    const active = m === newMode;
    b.classList.toggle("active", active);
    b.style.boxShadow = active && mColor
      ? `0 0 0 1px ${mColor}66, 0 6px 16px -6px ${mColor}55`
      : "0 0 0 1px rgba(255,255,255,0.04)";
    const icon  = b.querySelector(".thermo-mode-icon");
    const label = b.querySelector(".thermo-mode-label");
    if (icon)  icon.style.color  = active && mColor ? mColor : "var(--t-text-dim2)";
    if (label) label.style.color = active ? "var(--t-text)" : "var(--t-text-dim2)";
  });
  refreshThermoDial(thermoId);
}

function attachThermoDrag(wrap) {
  const id = wrap.dataset.thermoDial;
  const MIN = 10, MAX = 32;
  let dragging = false;

  function setFromPointer(clientX, clientY) {
    const rect = wrap.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top  + rect.height / 2;
    let angle = (Math.atan2(clientY - cy, clientX - cx) * 180) / Math.PI + 90;
    if (angle < 0) angle += 360;
    const pct = angle >= 270 ? 0 : Math.min(100, Math.max(0, (angle / 270) * 100));
    const newTarget = Math.round(MIN + (pct / 100) * (MAX - MIN));
    const ui = thermoUIState.get(id);
    if (!ui || ui.target === newTarget) return;
    ui.target = newTarget;
    ui.preset = null;
    refreshThermoDial(id);
  }

  onDragStart(wrap, (e) => {
    const start = dragPoint(e);
    e.preventDefault();
    dragging = true;
    setFromPointer(start.clientX, start.clientY);
    trackDrag(e, {
      onMove: (point) => { if (dragging) setFromPointer(point.clientX, point.clientY); },
      onEnd: () => { dragging = false; },
    });
  });
}

function renderThermostats(payload) {
  const thermostats = payload?.thermostats || [];
  latestThermostats = thermostats;
  const groupThermostats = groupMemberData("climate", ["thermostat"]);
  if (thermostatCount) thermostatCount.textContent = String(thermostats.length);

  if (thermostats.length > 0) {
    const first = thermostats[0];
    if (first.temperature != null) {
      const u = first.temperature_unit?.includes("F") ? "°F" : "°C";
      if (indoorTemp) indoorTemp.textContent = `${Math.round(first.temperature)}${u}`;
    }
  }

  if (groupThermostats.length === 0) {
    const message = thermostats.length === 0
      ? (payload?.message || "No Ecobee thermostats configured yet. Add them to configs/devices.local.yaml.")
      : "No devices in this group. Use Manage to add some.";
    thermostatGrid.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
    renderForeignKinds("climate", ["thermostat"], "#thermostatGrid");
    return;
  }

  thermostatGrid.innerHTML = groupThermostats
    .map((th) => thermoCardHtml(th, th.status || payload.status || "unknown"))
    .join("");

  thermostatGrid.querySelectorAll(".thermo-dial-wrap").forEach(attachThermoDrag);
  renderForeignKinds("climate", ["thermostat"], "#thermostatGrid");
}

const THERMO_MODES_DEF = [
  { id: "heat", label: "HEAT", color: THERMO_MODE_COLORS.heat },
  { id: "cool", label: "COOL", color: THERMO_MODE_COLORS.cool },
  { id: "auto", label: "AUTO", color: THERMO_MODE_COLORS.auto },
  { id: "off",  label: "OFF",  color: null },
];

/* Full interactive thermostat card — shared by the Climate view and the
   Home view Climate panel. All controls are wired via delegated
   data-thermo-* handlers, so copies stay functional anywhere. */
function thermoCardHtml(th, status = "unknown") {
    const ui      = getThermoUI(th);
    const current = th.temperature != null ? Math.round(Number(th.temperature)) : "--";
    const humidity = th.humidity != null ? `${th.humidity}%` : "--";

    const modeButtons = THERMO_MODES_DEF.map((m) => {
      const active = ui.mode === m.id;
      const shadow = active && m.color
        ? `0 0 0 1px ${m.color}66, 0 6px 16px -6px ${m.color}55`
        : "0 0 0 1px rgba(255,255,255,0.04)";
      return `<button class="thermo-mode-btn${active ? " active" : ""}"
        data-thermo-mode="${m.id}" data-thermo-id="${escapeHtml(th.id)}"
        type="button" style="box-shadow:${shadow}">
        <span class="thermo-mode-icon" style="color:${active && m.color ? m.color : "var(--t-text-dim2)"}">${thermoModeIcon(m.id)}</span>
        <span class="thermo-mode-label" style="color:${active ? "var(--t-text)" : "var(--t-text-dim2)"}">${m.label}</span>
      </button>`;
    }).join("");

    const fanPills = ["auto", "on"].map((f) => {
      const active = ui.fan === f;
      return `<button class="thermo-fan-btn${active ? " active" : ""}" data-thermo-fan="${f}" data-thermo-id="${escapeHtml(th.id)}" type="button">${f.toUpperCase()}</button>`;
    }).join("");

    const presetBtns = THERMO_PRESETS.map((p) => {
      const active = ui.preset === p.id;
      return `<button class="thermo-preset-btn${active ? " active" : ""}" data-thermo-preset="${p.id}" data-thermo-id="${escapeHtml(th.id)}" type="button">
        <span class="thermo-preset-name">${p.name}</span>
        <span class="thermo-preset-caption">${p.caption}</span>
      </button>`;
    }).join("");

    const roomRows = (th.sensors || []).map((r) => {
      const temp = r.temperature != null ? Math.round(Number(r.temperature)) : null;
      const tColor = temp != null ? tempRangeColor(temp) : "var(--t-text-dim2)";
      const tempDisplay = temp != null ? `${temp}°` : "--";
      const isOccupied = r.occupied === true;
      const occupancyKnown = r.occupied != null;
      return `<div class="thermo-room-row">
        <div class="thermo-room-left">
          <span class="thermo-occ-dot${isOccupied ? " occupied" : ""}"></span>
          <div>
            <p class="thermo-room-name">${escapeHtml(r.name)}</p>
            <p class="thermo-room-status">${occupancyKnown ? (isOccupied ? "Occupied" : "Empty") : ""}</p>
          </div>
        </div>
        <span class="thermo-room-temp" style="color:${tColor}">${tempDisplay}</span>
      </div>`;
    }).join("");

    return `
      <article class="thermo-card" data-thermostat-id="${escapeHtml(th.id)}">
        <div class="thermo-header">
          <h3>${escapeHtml(th.name)}</h3>
          <span class="power-state ${th.online ? "on" : "offline"}">${formatStatus(status)}</span>
        </div>

        <div class="thermo-dial-center">
          ${buildThermoDial(th.id, ui, current)}
          <div class="thermo-step-row">
            <button class="thermo-step" data-thermo-step="-1" data-thermo-id="${escapeHtml(th.id)}" type="button">−</button>
            <button class="thermo-step" data-thermo-step="1"  data-thermo-id="${escapeHtml(th.id)}" type="button">+</button>
          </div>
        </div>

        <div class="thermo-mode-grid">${modeButtons}</div>

        <div class="thermo-fan-row">
          <span class="thermo-fan-label">FAN</span>
          <div class="thermo-fan-pills">${fanPills}</div>
        </div>

        <div class="thermo-presets">${presetBtns}</div>

        <div class="thermo-rooms">${roomRows}</div>

        <div class="thermo-sensors-row">
          <span class="thermo-sensor-pill"><i class="ti ti-droplet"></i> ${humidity} humidity</span>
          <span class="thermo-sensor-pill"><i class="ti ti-flame"></i> Heat ${th.desired_heat ?? "--"}°</span>
          <span class="thermo-sensor-pill"><i class="ti ti-snowflake"></i> Cool ${th.desired_cool ?? "--"}°</span>
        </div>
      </article>
    `;
}

async function updateClimate(thermostatId, payload) {
  apiStatus.textContent = "Sending";
  await requestJson(`/api/home-assistant/climate/${encodeURIComponent(thermostatId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadDevices();
}

/* ── Home Assistant panel ── */
function renderHomeAssistant(payload) {
  const entities = payload?.entities || [];
  haCount.textContent = String(entities.length);
  const url = homeAssistantUrl();
  if (homeAssistantFrame && homeAssistantFrame.src !== url) homeAssistantFrame.src = url;
  if (homeAssistantOpen) homeAssistantOpen.href = url;
}

function homeAssistantUrl() {
  /* No fallback address: see _zigbeeUiUrl. The browser knows where it is. */
  const host = window.location.hostname;
  return `http://${host}:8123/lovelace/default_view`;
}

/* ── Weather ── */
function weatherHeaderIcon(code, night = false) {
  const num = Number(code);
  if ([0, 1].includes(num)) return night ? "ti-moon" : "ti-sun";
  if (num === 2) return night ? "ti-moon" : "ti-cloud";
  if ([3, 45, 48].includes(num)) return num === 3 ? "ti-cloud" : "ti-mist";
  if (num >= 71 && num < 80) return "ti-snowflake";
  if (num >= 95) return "ti-cloud-storm";
  if (num >= 51) return "ti-cloud-rain";
  return "ti-cloud";
}

/* Day or night for the Weather card's icon: a moon after sunset.

   The card itself wears the same colour as every other card - it had a sky
   that followed the time of day, and it did not sit well beside the rest.
   Sunrise and sunset come from the forecast, so the moon appears when the sun
   actually sets in Coquitlam, not at a fixed hour. Open-Meteo gives them as
   local wall-clock times with no offset ("2026-09-16T06:50"), which Date parses
   as local time - right, because the browser and the board share a time zone.
   Until the first forecast arrives, a fixed 07:00-19:00 day stands in. */

function minutesOfDay(date) {
  return date.getHours() * 60 + date.getMinutes();
}

function skyPhase(now, weather) {
  const parse = (value) => {
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? minutesOfDay(date) : null;
  };
  const sunrise = parse(weather?.sunrise) ?? 7 * 60;
  const sunset = parse(weather?.sunset) ?? 19 * 60;
  const t = minutesOfDay(now);
  if (t >= sunrise - SKY_TWILIGHT_MIN / 2 && t < sunrise + SKY_TWILIGHT_MIN) return "dawn";
  if (t >= sunrise + SKY_TWILIGHT_MIN && t < sunset - SKY_TWILIGHT_MIN) return "day";
  if (t >= sunset - SKY_TWILIGHT_MIN && t < sunset + SKY_TWILIGHT_MIN / 2) return "dusk";
  return "night";
}

function applyWeatherSky(now = new Date()) {
  const phase = skyPhase(now, latestWeather);
  if (latestWeather?.status === "ok" && weatherIcon) {
    weatherIcon.className = "ti home-weather-icon " + weatherHeaderIcon(latestWeather.weather_code, phase === "night");
  }
}

function renderWeatherWeek(forecast, tempUnit) {
  const week = document.querySelector("#weatherWeek");
  if (!week) return;
  const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  week.innerHTML = forecast.slice(0, 7).map((day, i) => {
    const date = new Date(day.date + "T12:00:00");
    const label = i === 0 ? "Today" : DAY_NAMES[date.getDay()];
    return `
      <span class="wk-day${i === 0 ? " today" : ""}" title="${escapeHtml(day.condition || "")}">
        <span class="wk-name">${escapeHtml(label)}</span>
        <i class="ti ${escapeHtml(weatherHeaderIcon(day.weather_code))}" aria-hidden="true"></i>
        <span class="wk-temps"><strong>${escapeHtml(String(roundMetric(day.high)))}°</strong><span>${escapeHtml(String(roundMetric(day.low)))}°</span></span>
      </span>`;
  }).join("");
}

function setHeaderWeatherUnavailable(message) {
  if (headerWeather) headerWeather.title = message || "Weather is not configured yet.";
  latestWeather = null;
  if (weatherIcon) weatherIcon.className = "ti home-weather-icon ti-cloud";
  if (weatherTemp) weatherTemp.textContent = "--°";
  if (weatherCondition) weatherCondition.textContent = "Weather unavailable";
  const cardHiLo = document.querySelector("#weatherCardHiLo");
  if (cardHiLo) cardHiLo.textContent = "";
  const week = document.querySelector("#weatherWeek");
  if (week) week.innerHTML = "";
  const weatherLocation = document.querySelector("#weatherLocation");
  if (weatherLocation) weatherLocation.textContent = "—";
  if (weatherFeels) weatherFeels.textContent = "--°C";
  if (weatherHumidity) weatherHumidity.textContent = "--%";
  if (weatherWind) weatherWind.textContent = "--";
  if (weatherPressure) weatherPressure.textContent = "--";
  if (weatherUv) weatherUv.textContent = "--";
  if (weatherHighLow) weatherHighLow.textContent = "-- / --";
  if (weatherPrecip) weatherPrecip.textContent = "--%";
  if (outdoorTemp) outdoorTemp.textContent = "--";
}

function renderWeather(weather) {
  if (!weather || weather.status !== "ok") {
    setHeaderWeatherUnavailable(weather?.message);
    return;
  }

  const tempUnit = unitSymbol(weather.temperature_unit);
  const tempDisplay = String(roundMetric(weather.temperature)) + tempUnit;
  const feelsDisplay = String(roundMetric(weather.feels_like)) + tempUnit;
  const humidityDisplay = String(roundMetric(weather.humidity)) + "%";
  const windDisplay = (String(roundMetric(weather.wind_speed)) + " " + (weather.wind_unit || "")).trim();
  const pressureDisplay = String(roundMetric(weather.pressure)) + (weather.pressure_unit || "");
  const uvDisplay = String(roundMetric(weather.uv_index));
  const icon = weatherHeaderIcon(weather.weather_code);
  const highDisplay = weather.high != null ? String(roundMetric(weather.high)) + tempUnit : "--";
  const lowDisplay  = weather.low  != null ? String(roundMetric(weather.low))  + tempUnit : "--";
  const precipDisplay = weather.precipitation_probability != null
    ? String(roundMetric(weather.precipitation_probability)) + "%"
    : "--%";

  latestWeather = weather;
  if (weatherIcon) weatherIcon.className = "ti home-weather-icon " + icon;
  /* The card shows the degree sign alone: C or F is a setting, not news. */
  if (weatherTemp) weatherTemp.textContent = String(roundMetric(weather.temperature)) + "°";
  const cardHiLo = document.querySelector("#weatherCardHiLo");
  if (cardHiLo) {
    cardHiLo.textContent = weather.high != null && weather.low != null
      ? ` · H ${roundMetric(weather.high)}° L ${roundMetric(weather.low)}°`
      : "";
  }
  if (weatherCondition) weatherCondition.textContent = weather.condition || "Outdoor";
  const weatherLocation = document.querySelector("#weatherLocation");
  if (weatherLocation) weatherLocation.textContent = weather.location || "Local";
  if (weatherFeels) weatherFeels.textContent = feelsDisplay;
  if (weatherHumidity) weatherHumidity.textContent = humidityDisplay;
  if (weatherWind) weatherWind.textContent = windDisplay;
  if (weatherPressure) weatherPressure.textContent = pressureDisplay;
  if (weatherUv) weatherUv.textContent = uvDisplay;
  if (weatherHighLow) weatherHighLow.textContent = highDisplay + " / " + lowDisplay;
  if (weatherPrecip) weatherPrecip.textContent = precipDisplay;
  if (outdoorTemp) outdoorTemp.textContent = tempDisplay;

  const conditionEl = document.querySelector("#statCondition");
  if (conditionEl) conditionEl.textContent = weather.condition || "Outdoor";

  renderWeatherForecast(weather.forecast || []);
  renderWeatherWeek(weather.forecast || [], tempUnit);
  applyWeatherSky();
}

function renderWeatherForecast(forecast) {
  if (!weatherForecast) return;
  if (!forecast.length) {
    weatherForecast.innerHTML = "";
    return;
  }
  const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  weatherForecast.innerHTML = forecast.map((day, i) => {
    const date = new Date(day.date + "T12:00:00");
    const dayLabel = i === 0 ? "Today" : DAY_NAMES[date.getDay()];
    const icon = weatherHeaderIcon(day.weather_code);
    const precip = day.precipitation_probability != null ? Math.round(day.precipitation_probability) + "%" : "";
    return `
      <div class="wdf-row">
        <span class="wdf-day">${escapeHtml(dayLabel)}</span>
        <i class="ti ${escapeHtml(icon)} wdf-icon"></i>
        <span class="wdf-cond">${escapeHtml(day.condition || "")}</span>
        <span class="wdf-precip">${precip ? '<i class="ti ti-droplet"></i>' + escapeHtml(precip) : ""}</span>
        <span class="wdf-temps"><strong>${escapeHtml(String(roundMetric(day.high)))}</strong><span class="wdf-low">${escapeHtml(String(roundMetric(day.low)))}</span></span>
      </div>`;
  }).join("");
}

/* ── Weather dropdown toggle ── */
function openWeatherDropdown() {
  if (!weatherDropdown) return;
  // Position desktop dropdown below the button (mobile uses CSS fixed bottom:0)
  if (headerWeather && window.innerWidth > 480) {
    const rect = headerWeather.getBoundingClientRect();
    weatherDropdown.style.top  = (rect.bottom + 8) + "px";
    weatherDropdown.style.right = (window.innerWidth - rect.right) + "px";
    weatherDropdown.style.left  = "auto";
    weatherDropdown.style.bottom = "auto";
  }
  weatherDropdown.classList.add("open");
  weatherDropdown.setAttribute("aria-hidden", "false");
  if (headerWeather) headerWeather.setAttribute("aria-expanded", "true");
  if (weatherBackdrop) weatherBackdrop.classList.add("open");
}

function closeWeatherDropdown() {
  if (!weatherDropdown) return;
  weatherDropdown.classList.remove("open");
  weatherDropdown.setAttribute("aria-hidden", "true");
  if (headerWeather) headerWeather.setAttribute("aria-expanded", "false");
  if (weatherBackdrop) weatherBackdrop.classList.remove("open");
  weatherDropdown.style.top = weatherDropdown.style.right = weatherDropdown.style.left = weatherDropdown.style.bottom = "";
}

if (headerWeather) {
  headerWeather.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = weatherDropdown && weatherDropdown.classList.contains("open");
    if (isOpen) {
      closeWeatherDropdown();
    } else {
      openWeatherDropdown();
    }
  });
}

document.addEventListener("click", (e) => {
  if (weatherDropdown && weatherDropdown.classList.contains("open")) {
    if (!weatherDropdown.contains(e.target) && e.target !== headerWeather && !headerWeather?.contains(e.target)) {
      closeWeatherDropdown();
    }
  }
});

if (weatherBackdrop) {
  weatherBackdrop.addEventListener("click", closeWeatherDropdown);
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeWeatherDropdown();
});

function formatWeatherTime(value) {
  if (!value) return "--:--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

function weatherIconClass(code) {
  const numericCode = Number(code);
  if ([0, 1].includes(numericCode)) return "weather-icon sunny";
  if ([2, 3, 45, 48].includes(numericCode)) return "weather-icon cloudy";
  if (numericCode >= 51 && numericCode < 80) return "weather-icon rainy";
  return "weather-icon sunny";
}

/* ── Tuya helpers ── */
function isTuyaCamera(device) {
  const text = `${device.category || ""} ${device.model || ""} ${device.name || ""}`.toLowerCase();
  return text.includes("tuya_camera") || text.includes("camera") || text.includes("doorbell") || text.includes("门铃");
}

function formatTuyaValue(name, value) {
  const normalized = String(name).toLowerCase();
  const label = friendlyTuyaLabel(normalized);
  if (value === null || value === undefined || value === "") return { label, value: "unknown" };
  if (typeof value === "boolean") return { label, value: value ? "On" : "Off" };
  if (normalized.includes("temperature")) return { label, value: `${value}°C` };
  if (normalized.includes("humidity"))    return { label, value: `${value}%` };
  if (normalized.includes("battery") || normalized.includes("wireless_electricity")) return { label, value: `${value}%` };
  if (normalized.includes("wireless_awake"))    return { label, value: value ? "Awake" : "Sleeping" };
  if (normalized.includes("doorbell_active"))   return { label, value: value ? "Ringing" : "Idle" };
  if (normalized.includes("illuminance"))       return { label, value: `${value} lx` };
  if (normalized.includes("presence_time"))     return { label, value: `${value}s` };
  if (normalized.includes("watersensor_state")) return { label, value: waterSensorState(value) };
  return { label, value: String(value) };
}

function friendlyTuyaLabel(name) {
  const known = {
    va_temperature: "Temperature", temp_current: "Temperature", temperature: "Temperature",
    va_humidity: "Humidity", humidity: "Humidity",
    va_battery: "Battery", battery: "Battery", battery_percentage: "Battery",
    switch: "Switch", switch_led: "Light",
    doorcontact_state: "Door", presence_state: "Presence", presence_time: "Presence time",
    illuminance_value: "Illuminance", watersensor_state: "Water",
    wireless_electricity: "Battery", wireless_awake: "Awake",
    wireless_lowpower: "Low battery threshold", wireless_powermode: "Power mode",
    doorbell_active: "Doorbell", doorbell_pic: "Doorbell image",
    movement_detect_pic: "Motion image", pir_switch: "PIR",
  };
  if (known[name]) return known[name];
  return name.replace(/^va_/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function waterSensorState(value) {
  const normalized = String(value);
  if (normalized === "1") return "Dry";
  if (normalized === "2") return "Wet";
  return normalized;
}

/* ── Cameras ── */
function tuyaCameraCard(device) {
  const battery   = device.values?.wireless_electricity ?? device.values?.battery ?? device.values?.va_battery;
  const isDoorbell = String(device.name || "").includes("门铃") || String(device.model || "").toLowerCase().includes("doorbell");
  const awake     = device.values?.wireless_awake === true ? "Awake" : "Sleeping";
  const active    = isDoorbell ? (device.values?.doorbell_active ? "Ringing" : awake) : "Video stopped";
  const detail    = isDoorbell
    ? battery === undefined ? "Battery doorbell" : `Battery ${battery}%`
    : "Tuya camera stream is not configured";
  return {
    id: device.id, name: device.name, host: device.host || "Tuya Cloud",
    provider: "tuya", model: device.model || (isDoorbell ? "Doorbell camera" : "Smart camera"),
    room: device.room, status: active,
    status_detail: isDoorbell ? "Battery camera. Video is not loaded automatically." : "No local RTSP/WebRTC stream found yet.",
    view_type: isDoorbell ? "doorbell" : "tuya_camera",
    customMedia: `<div class="camera-placeholder doorbell-placeholder">${active}<br /><span>${detail}</span></div>`,
  };
}

/* ── Snapshot cache ── */
const SNAP_PREFIX = "cam_snap_";

function loadCachedSnapshot(cameraId) {
  try { return localStorage.getItem(SNAP_PREFIX + cameraId); } catch { return null; }
}

function saveCachedSnapshot(cameraId, dataUri) {
  try { localStorage.setItem(SNAP_PREFIX + cameraId, dataUri); } catch {}
}

async function captureSnapshotOnce(camera) {
  const cameraId = cameraIdFor(camera);
  try {
    const response = await fetch(camera.snapshot_url || snapshotUrlFor(camera));
    if (!response.ok) return null;
    const blob = await response.blob();
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUri = reader.result;
        saveCachedSnapshot(cameraId, dataUri);
        const img = cameraGrid.querySelector(`img[data-camera-snap="${CSS.escape(cameraId)}"]`);
        if (img) img.src = dataUri;
        resolve(dataUri);
      };
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

async function cacheSnapshotsInBackground(cameras) {
  for (const camera of cameras) {
    if (!camera.view_url || activeCameraIds.has(cameraIdFor(camera))) continue;
    if (camera.battery_powered) continue;
    await captureSnapshotOnce(camera);
    await new Promise((r) => setTimeout(r, 300));
  }
}

/* ── Doorbell camera card (prototype-style idle/live) ── */
const doorbellLiveIds = new Set();

function doorbellBatteryIcon(pct) {
  const color = pct < 20 ? "var(--t-alert)" : pct < 50 ? "#F2B84B" : "#7ED9A0";
  const fillW = Math.max(1, (pct / 100) * 14).toFixed(1);
  return `<svg width="22" height="12" viewBox="0 0 22 12">
    <rect x="0.5" y="0.5" width="18" height="11" rx="2" fill="none" stroke="var(--t-text-dim2)" stroke-width="1"/>
    <rect x="19.5" y="3.5" width="2" height="5" rx="1" fill="var(--t-text-dim2)"/>
    <rect x="2.2" y="2.2" width="${fillW}" height="7.6" rx="1" fill="${color}"/>
  </svg>`;
}

function doorbellSignalIcon(bars) {
  const b = Math.min(3, Math.max(0, Number(bars) || 0));
  return `<svg width="18" height="14" viewBox="0 0 18 14">
    ${[0,1,2].map((i) => {
      const h   = 4 + i * 4;
      const lit = i < b;
      return `<rect x="${i*6}" y="${14-h}" width="4" height="${h}" rx="1" fill="${lit ? "var(--t-glow)" : "var(--t-off-muted)"}"/>`;
    }).join("")}
  </svg>`;
}

function doorbellCardHtml(camera) {
  const cameraId  = cameraIdFor(camera);
  const isLive    = doorbellLiveIds.has(cameraId);
  const battery   = Number(camera.battery ?? 100);
  const signal    = Number(camera.signal  ?? 2);
  const events    = camera.events || [];

  const standby = `
    <div class="doorbell-standby">
      <svg width="30" height="30" viewBox="0 0 30 30">
        <rect x="4" y="9" width="16" height="13" rx="2.5" fill="none" stroke="var(--t-text-dim2)" stroke-width="1.6"/>
        <path d="M20 13l6-3.5v11L20 17" fill="none" stroke="var(--t-text-dim2)" stroke-width="1.6" stroke-linejoin="round"/>
        <line x1="2" y1="2" x2="27" y2="27" stroke="var(--t-text-dim2)" stroke-width="1.6" stroke-linecap="round"/>
      </svg>
      <p>Camera idle</p>
      <small>Tap below to wake — streaming uses battery</small>
    </div>
    <button class="view-live-btn" data-doorbell-live="${escapeHtml(cameraId)}">VIEW LIVE</button>`;

  const doorbellMedia = camera.view_url
    ? `<img class="doorbell-live-media" src="${escapeHtml(camera.view_url)}" alt="${escapeHtml(camera.name)} live view" />`
    : `<div class="doorbell-live-placeholder">Live video unavailable</div>`;

  const liveView = `
    <div class="doorbell-live-view">
      <div class="doorbell-live-glow" style="background:radial-gradient(circle at 50% 40%,rgba(var(--t-accent-rgb),0.13),transparent 65%)"></div>
      ${doorbellMedia}
      <div class="live-badge-row">
        <span class="live-dot"></span>
        <span class="live-label-text">LIVE</span>
      </div>
      <div class="live-timer" data-live-timer="${escapeHtml(cameraId)}">00:00</div>
      <div class="live-controls-bar">
        <button class="live-ctrl-btn" data-doorbell-talk="${escapeHtml(cameraId)}" aria-label="Hold to talk">
          <span class="live-ctrl-icon">
            <svg width="16" height="16" viewBox="0 0 16 16"><rect x="5" y="1" width="6" height="9" rx="3" fill="white"/><path d="M2.5 7.5a5.5 5.5 0 0011 0M8 13v2" stroke="white" stroke-width="1.3" fill="none" stroke-linecap="round"/></svg>
          </span>
          <span class="live-ctrl-label">HOLD TO TALK</span>
        </button>
        <button class="live-ctrl-btn" data-doorbell-snap="${escapeHtml(cameraId)}" aria-label="Snapshot">
          <span class="live-ctrl-icon">
            <svg width="16" height="16" viewBox="0 0 16 16"><rect x="1.5" y="4" width="13" height="9.5" rx="2" fill="none" stroke="white" stroke-width="1.3"/><circle cx="8" cy="8.7" r="2.6" fill="none" stroke="white" stroke-width="1.3"/><rect x="5.3" y="1.5" width="5.4" height="2.2" rx="0.8" fill="white"/></svg>
          </span>
          <span class="live-ctrl-label">SNAPSHOT</span>
        </button>
        <button class="live-ctrl-btn" data-doorbell-end="${escapeHtml(cameraId)}" aria-label="End live view">
          <span class="live-ctrl-icon">
            <svg width="14" height="14" viewBox="0 0 14 14"><line x1="1" y1="1" x2="13" y2="13" stroke="white" stroke-width="1.6" stroke-linecap="round"/><line x1="13" y1="1" x2="1" y2="13" stroke="white" stroke-width="1.6" stroke-linecap="round"/></svg>
          </span>
          <span class="live-ctrl-label">END</span>
        </button>
      </div>
    </div>`;

  const eventsHtml = events.length ? `
    <div class="doorbell-events">
      ${events.slice(0, isLive ? 1 : 3).map((e) => {
        const isRing = e.type === "ring";
        const icon   = isRing
          ? `<svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 1.2c-.6 0-1 .45-1 1v.4C4.9 3 3.4 4.8 3.4 7v2.6L2 11.4v.6h12v-.6l-1.4-1.8V7c0-2.2-1.5-4-3.6-4.4v-.4c0-.55-.45-1-1-1z" fill="var(--t-text-dim2)"/><path d="M6.3 12.6a1.7 1.7 0 003.4 0z" fill="var(--t-text-dim2)"/></svg>`
          : `<svg width="14" height="14" viewBox="0 0 22 22"><circle cx="11" cy="11" r="2.2" fill="var(--t-text-dim2)"/><circle cx="11" cy="11" r="6" fill="none" stroke="var(--t-text-dim2)" stroke-width="1.4" opacity="0.5"/></svg>`;
        return `<div class="doorbell-event-row">
          <div class="doorbell-event-info">${icon}<span class="doorbell-event-label">${escapeHtml(e.label)}</span></div>
          <span class="doorbell-event-time">${escapeHtml(e.time)}</span>
        </div>`;
      }).join("")}
    </div>` : "";

  const simBtn = `<button class="doorbell-simulate-btn" data-doorbell-ring="${escapeHtml(cameraId)}" data-camera-name="${escapeHtml(camera.name)}">🔔 Simulate doorbell press (demo)</button>`;

  return `
    <article class="doorbell-cam-card ${isLive ? "live" : ""}" data-camera-id="${escapeHtml(cameraId)}">
      <div class="doorbell-cam-top">
        <div>
          <h3 class="device-name" style="font-family:'Fraunces',serif;font-size:17px;color:var(--t-text)">${escapeHtml(camera.name)}</h3>
          <p class="device-status" style="font-size:12px;color:var(--t-text-dim);margin-top:4px">${escapeHtml(camera.room || camera.model || "Doorbell camera")}</p>
        </div>
        <div class="doorbell-cam-info">
          <div class="doorbell-sig-row">${doorbellSignalIcon(signal)}</div>
          <div class="doorbell-bat-row">${doorbellBatteryIcon(battery)}<span class="doorbell-bat-pct">${battery}%</span></div>
        </div>
      </div>
      ${isLive ? liveView : standby}
      ${eventsHtml}
      ${!isLive ? simBtn : ""}
    </article>`;
}

/* ── Live timer management ── */
const liveTimers = {};

function startLiveTimer(cameraId) {
  if (liveTimers[cameraId]) return;
  let secs = 0;
  liveTimers[cameraId] = setInterval(() => {
    secs++;
    const el = document.querySelector(`[data-live-timer="${CSS.escape(cameraId)}"]`);
    if (el) {
      const mm = String(Math.floor(secs / 60)).padStart(2, "0");
      const ss = String(secs % 60).padStart(2, "0");
      el.textContent = `${mm}:${ss}`;
    }
  }, 1000);
}

function stopLiveTimer(cameraId) {
  clearInterval(liveTimers[cameraId]);
  delete liveTimers[cameraId];
}

/* ── Camera rendering ── */
function renderCameras(cameras, tuyaDevices = []) {
  const tuyaCameras = tuyaDevices.filter(isTuyaCamera).map(tuyaCameraCard);
  const allCameras  = applyCameraOrder([...cameras, ...tuyaCameras]);
  latestCameraById.clear();
  allCameras.forEach((camera) => latestCameraById.set(cameraIdFor(camera), camera));
  if (cameraCount) cameraCount.textContent = String(allCameras.length);
  cameraTabCount.textContent = String(allCameras.length);

  if (allCameras.length === 0) {
    cameraGrid.innerHTML = '<div class="empty">No cameras configured yet. Add them to configs/devices.local.yaml.</div>';
    return;
  }

  const existingCards = Array.from(cameraGrid.querySelectorAll(".camera-card[data-camera-id]"));
  const existingIds   = existingCards.map((c) => c.dataset.cameraId);
  const newIds        = allCameras.map(cameraIdFor);
  const sameLayout    = existingIds.length === newIds.length && newIds.every((id, i) => id === existingIds[i]);

  if (sameLayout) {
    allCameras.forEach((camera) => {
      const cameraId = cameraIdFor(camera);
      const card = cameraGrid.querySelector(`.camera-card[data-camera-id="${CSS.escape(cameraId)}"]`);
      if (!card) return;
      if (!activeCameraIds.has(cameraId)) {
        const frame = card.querySelector(".camera-frame");
        if (frame) frame.innerHTML = cameraMedia(camera) + cameraBatteryBadge(camera);
      }
      const action = card.querySelector(".camera-action");
      if (action) action.innerHTML = cameraAction(camera);
    });
  } else {
    cameraGrid.innerHTML = allCameras.map((camera) => cameraCardHtml(camera)).join("");
  }
}

function savedCameraOrder() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CAMERA_ORDER_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

/* Same two-tier ordering as applyDeviceOrder: a hand-dragged order wins, and
   anything it does not cover falls back to the area order, so the camera wall
   reads front yard, front door, living room ... by default. */
function applyCameraOrder(cameras) {
  const order = savedCameraOrder();
  const indexById = new Map(order.map((id, index) => [id, index]));
  const rankOf = homeAreaRanker();
  return [...cameras]
    .map((camera, index) => {
      const id = cameraIdFor(camera);
      return {
        camera,
        index,
        saved: indexById.has(id) ? indexById.get(id) : Number.MAX_SAFE_INTEGER,
        area: rankOf(`cam:${id}`, camera.room),
      };
    })
    .sort((a, b) => (a.saved - b.saved) || (a.area - b.area) || (a.index - b.index))
    .map((entry) => entry.camera);
}

function saveCameraOrderFromDom() {
  if (!cameraGrid) return;
  const order = Array.from(cameraGrid.querySelectorAll(".camera-card[data-camera-id]"))
    .map((card) => card.dataset.cameraId)
    .filter(Boolean);
  try { localStorage.setItem(CAMERA_ORDER_KEY, JSON.stringify(order)); } catch {}
}

function cameraDragHandle(cameraId) {
  return `<button class="camera-drag-handle" data-camera-drag="${escapeHtml(cameraId)}" type="button" title="Drag to reorder" aria-label="Drag to reorder camera"><i class="ti ti-grip-vertical" aria-hidden="true"></i></button>`;
}

function cameraCardHtml(camera) {
  const cameraId = cameraIdFor(camera);
  return `
    <article class="camera-card" data-camera-id="${escapeHtml(cameraId)}">
      <div class="camera-frame">${cameraMedia(camera)}${cameraBatteryBadge(camera)}</div>
      <div class="camera-info">
        <div class="camera-copy">
          ${cameraTitle(camera)}
          <p class="meta">${escapeHtml(camera.room || "")}${camera.room ? " · " : ""}${escapeHtml(camera.model || "Camera")} · ${escapeHtml(camera.provider || "camera")}</p>
          <p class="meta">${escapeHtml(camera.host || camera.status_detail || "")}</p>
          ${camera.valuesHtml ? `<div class="tuya-values camera-values">${camera.valuesHtml}</div>` : ""}
        </div>
        <div class="camera-action">${cameraAction(camera)}</div>
      </div>
    </article>
  `;
}

function cameraTitle(camera) {
  const cameraId = cameraIdFor(camera);
  return `
    <div class="camera-title-row">
      <h3>${escapeHtml(camera.name)}</h3>
      ${cameraDragHandle(cameraId)}
      <button class="camera-edit-button" data-camera-edit="${escapeHtml(cameraId)}" type="button" title="Edit camera name">Edit</button>
    </div>
  `;
}

function cameraTitleEditor(camera) {
  const cameraId = cameraIdFor(camera);
  return `
    <form class="camera-title-editor" data-camera-edit-form="${escapeHtml(cameraId)}">
      <input class="camera-name-input" data-camera-name-input value="${escapeHtml(camera.name)}" maxlength="80" aria-label="Camera name" />
      <div class="camera-edit-actions">
        <button class="command primary" type="submit">Save</button>
        <button class="command" data-camera-edit-cancel="${escapeHtml(cameraId)}" type="button">Cancel</button>
      </div>
    </form>
  `;
}

function cameraBatteryBadge(camera) {
  const hasBatteryValue = camera.battery !== null && camera.battery !== undefined && camera.battery !== "";
  if (!hasBatteryValue && !camera.battery_powered) return "";
  const battery = hasBatteryValue ? Math.max(0, Math.min(100, Number(camera.battery))) : null;
  const low = battery !== null && battery < 20;
  const label = battery === null || Number.isNaN(battery) ? "Battery" : `${Math.round(battery)}%`;
  const icon = low ? "ti-battery-1" : battery === null ? "ti-battery" : battery < 50 ? "ti-battery-2" : "ti-battery-4";
  return `<div class="camera-battery-badge ${low ? "low" : ""}" title="Battery powered camera"><i class="ti ${icon}" aria-hidden="true"></i><span>${label}</span></div>`;
}
function cameraIdFor(camera) {
  return camera.id || camera.host || camera.name;
}

function cameraMedia(camera) {
  const isActive = activeCameraIds.has(cameraIdFor(camera));
  if (camera.customMedia) return camera.customMedia;
  const liveUrl  = camera.view_url || camera.webrtc_url;
  const liveType = camera.view_url ? camera.view_type
                 : (camera.webrtc_url ? "webrtc" : null);
  if (liveUrl && isActive) {
    if (liveType === "webrtc") {
      /* go2rtc's player is modern JavaScript, so on an older browser the
         iframe renders as a dead shell - go2rtc's own "Live broadcast"
         heading with no picture beneath it. Our MJPEG proxy is just an <img>,
         which every browser can show. */
      if (LEGACY_JS) {
        const proxyId = encodeURIComponent(cameraIdFor(camera));
        return `<img class="camera-media" src="/api/cameras/${proxyId}/mjpeg" alt="${escapeHtml(camera.name)} live view" />`;
      }
      /* scrolling="no": go2rtc's player sets its <video> to 100% height but
         leaves it inline, so the baseline gap under it overflows the page by a
         few pixels and a scrollbar appeared beside every live picture. */
      return `<iframe class="camera-media camera-player" src="${liveUrl}" title="${camera.name} live WebRTC view" allow="autoplay; fullscreen; microphone" scrolling="no"></iframe>`;
    }
    if (liveType === "snapshot" || liveType === "mjpeg" || liveType === "doorbell") {
      const separator = liveUrl.includes("?") ? "&" : "?";
      return `<img class="camera-media" src="${liveUrl}${separator}ts=${Date.now()}" alt="${escapeHtml(camera.name)} live view" />`;
    }
    return `<video class="camera-media" src="${liveUrl}" controls muted playsinline></video>`;
  }
  if (camera.battery_powered) {
    const cameraId = cameraIdFor(camera);
    const cached = loadCachedSnapshot(cameraId);
    if (cached) {
      return `<img class="camera-media camera-preview" src="${cached}" alt="${escapeHtml(camera.name)} last view" data-camera-snap="${escapeHtml(cameraId)}" />`;
    }
    return `<div class="camera-placeholder doorbell-placeholder">Battery camera<br /><span>Tap View to load a picture</span></div>`;
  }
  if (camera.view_url || camera.snapshot_url) {
    const cameraId = cameraIdFor(camera);
    const cached = loadCachedSnapshot(cameraId);
    const src = cached || camera.snapshot_url || snapshotUrlFor(camera);
    return `<img class="camera-media camera-preview" src="${src}" alt="${escapeHtml(camera.name)} last view" data-camera-snap="${escapeHtml(cameraId)}" />`;
  }
  return `<div class="camera-placeholder">${camera.status || "Camera unavailable"}<br /><span>${camera.status_detail || "Check config"}</span></div>`;
}

function cameraAction(camera) {
  const cameraId = cameraIdFor(camera);
  if (camera.view_type === "tuya_camera") {
    return `<div class="camera-actions"><button class="command primary" type="button" disabled title="No browser-playable Tuya camera stream is configured yet.">View</button></div>`;
  }
  const viewUrl = camera.view_url || camera.webrtc_url || camera.hls_url;
  if (viewUrl) {
    return `
      <div class="camera-actions">
        <button class="command primary" data-camera-toggle="${cameraId}" type="button">${activeCameraIds.has(cameraId) ? "Stop" : "View"}</button>
        <a class="command" href="${viewUrl}" target="_blank" rel="noreferrer">Open</a>
      </div>
    `;
  }
  return `<span class="camera-note">${camera.view_type || "offline"}</span>`;
}

function snapshotUrlFor(camera) {
  const cameraId = encodeURIComponent(cameraIdFor(camera));
  return `/api/cameras/${cameraId}/snapshot.jpg?ts=${Date.now()}`;
}

/* ────────────────────────────────────────────────────────────
   NOTIFICATION SYSTEM
   ──────────────────────────────────────────────────────────── */
const notifMap = new Map();
const notifSeen = new Set(); // prevent duplicate auto-surfaced alerts

function pushNotification(type, title, message, meta = {}) {
  const key = type + "-" + (meta.deviceId || meta.cameraId || "") + "-" + (meta.eventKey || "");
  if (notifSeen.has(key)) return;
  notifSeen.add(key);
  const id = `notif-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  notifMap.set(id, { id, type, title, message, ...meta });
  renderNotifications();
  return id;
}

function dismissNotification(id) {
  notifMap.delete(id);
  renderNotifications();
}

// "New device" banners are per browser, but whether a device is still new is the
// server's answer, shared by every screen. Closing a banner on the PC tells the
// server, yet the wall panel - which never reloads - kept its own copy for ever,
// until a stack of stale banners covered the whole panel. Every refresh now drops
// the banners the server no longer flags. notifSeen keeps their keys, so a
// dropped banner is not pushed again.
const NOTIF_MAX_NEW_DEVICES = 2;

function syncNewDeviceNotifications(entities) {
  // An empty list means Home Assistant did not answer, not "nothing is new":
  // clearing on it would silently lose banners nobody has acted on yet.
  if (!Array.isArray(entities) || entities.length === 0) return false;
  const stillNew = new Set(entities.filter((entity) => entity.is_new).map((entity) => entity.entity_id));
  let changed = false;
  for (const [id, notif] of [...notifMap]) {
    if (notif.type === "new_device" && notif.entityId && !stillNew.has(notif.entityId)) {
      notifMap.delete(id);
      changed = true;
    }
  }
  return changed;
}

// Urgent banners (fire, alarm, doorbell) always show. New-device banners are
// capped so they can never crowd those out or fill the screen; the rest collapse
// into one "+N more" line.
function notificationsToShow(notifs, maxNewDevices = NOTIF_MAX_NEW_DEVICES) {
  const others = notifs.filter((notif) => notif.type !== "new_device");
  const newDevices = notifs.filter((notif) => notif.type === "new_device");
  const shownNewDevices = newDevices.slice(0, maxNewDevices);
  return { shown: [...others, ...shownNewDevices], hiddenNewDevices: newDevices.length - shownNewDevices.length };
}

function notificationsMarkup(notifs) {
  const { shown, hiddenNewDevices } = notificationsToShow(notifs);
  const banners = shown.map((n) => {
    const urgent = n.type !== "doorbell";
    return `
      <div class="notif-banner ${urgent ? "urgent" : "mild"}">
        <div class="notif-icon">${notifIconSVG(n.type)}</div>
        <div class="notif-content">
          <p class="notif-title">${escapeHtml(n.title)}</p>
          <p class="notif-message">${escapeHtml(n.message)}</p>
          <div class="notif-actions">
            <button class="notif-btn ${urgent ? "respond-urgent" : "respond-mild"}"
              data-notif-respond="${escapeHtml(n.id)}">Respond</button>
            <button class="notif-btn notif-close"
              data-notif-close="${escapeHtml(n.id)}">Close</button>
          </div>
        </div>
      </div>`;
  });
  if (hiddenNewDevices > 0) {
    banners.push(`
      <div class="notif-banner mild notif-more">
        <div class="notif-content">
          <p class="notif-title">+${hiddenNewDevices} more new device${hiddenNewDevices === 1 ? "" : "s"}</p>
          <div class="notif-actions">
            <button class="notif-btn notif-close" data-notif-dismiss-new="all">Dismiss all new devices</button>
          </div>
        </div>
      </div>`);
  }
  return banners.join("");
}

function notifIconSVG(type) {
  if (type === "doorbell") {
    return `<svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 1.2c-.6 0-1 .45-1 1v.4C4.9 3 3.4 4.8 3.4 7v2.6L2 11.4v.6h12v-.6l-1.4-1.8V7c0-2.2-1.5-4-3.6-4.4v-.4c0-.55-.45-1-1-1z" fill="var(--t-glow)" style="filter:drop-shadow(0 0 3px var(--t-glow))"/><path d="M6.3 12.6a1.7 1.7 0 003.4 0z" fill="var(--t-glow)"/></svg>`;
  }
  if (type === "fire") {
    return `<svg width="22" height="22" viewBox="0 0 22 22"><path d="M11 1.5c2.6 3.6-1.8 4.8-1 8.3.3 1.3-.6 2.4-1.9 2.4a2.6 2.6 0 01-2.6-2.6c0-2.4 1.6-3.4 2.4-5.6-.1 2.4 1.6 2.6 1.6.7-.1-1.4-.8-2.1 1.5-3.2zM9.6 12.4c.3 1.7 1.9 2.9 3.6 2.6 1.9-.3 3.1-2.1 2.7-4-.3-1.5-1.5-2.2-1.2-.5.2 1.4-1.1 2.5-2.5 2.3a2.1 2.1 0 01-1.7-1.9c-.1-.6.7-.6 1-.4-.6-1.4-2.2-1.1-1.9 1.9z" fill="var(--t-alert)" class="svg-pulse"/></svg>`;
  }
  // alarm
  return `<svg width="22" height="22" viewBox="0 0 22 22" style="transform:scale(0.7);transform-origin:top left"><path d="M11 1.5L21 19.5H1L11 1.5Z" fill="var(--t-alert)" class="svg-pulse"/><rect x="10" y="8" width="2" height="5.5" rx="1" fill="var(--t-bg,#12161B)"/><circle cx="11" cy="16" r="1.1" fill="var(--t-bg,#12161B)"/></svg>`;
}

function doorbellEventSignature(camera) {
  const events = Array.isArray(camera.events) ? camera.events : [];
  if (!events.length) return "";
  return events
    .map((event) => String(event.type || "event") + ":" + String(event.label || "") + ":" + String(event.time || ""))
    .join("|");
}

function notifyDoorbellEvents(cameras) {
  const doorbells = (cameras || []).filter((camera) => camera.view_type === "doorbell");
  for (const camera of doorbells) {
    const cameraId = cameraIdFor(camera);
    const signature = doorbellEventSignature(camera);
    if (!signature) continue;
    const previous = lastDoorbellEventById.get(cameraId);
    lastDoorbellEventById.set(cameraId, signature);
    if (!doorbellEventsReady || previous === undefined || previous === signature) continue;
    pushNotification("doorbell", camera.name + " - someone is there", "Doorbell event detected by Home Assistant", { cameraId, eventKey: signature });
    logActivity(camera.name + " doorbell event", "warn");
  }
  doorbellEventsReady = true;
}

function notifySeenNewHomeAssistantDevices(entities) {
  if (syncNewDeviceNotifications(entities)) renderNotifications();
  for (const entity of entities || []) {
    if (!entity.is_new) continue;
    pushNotification(
      "new_device",
      "New device found: " + entity.name,
      "Add it to your dashboard?",
      {
        entityId: entity.entity_id,
        eventKey: entity.entity_id,
        suggestedName: entity.name,
        suggestedRoom: _guessRoomFromName(entity.name),
        suggestedCategory: entity.domain === "switch" && entity.device_class === "outlet" ? "smart_plug" : "light_switch",
      }
    );
  }
}

function _guessRoomFromName(name) {
  const firstWord = String(name || "").split(" switch")[0].split(" light")[0].trim();
  return firstWord;
}

function renderNotifications() {
  const area = document.querySelector("#notifArea");
  if (!area) return;
  if (notifMap.size === 0) { area.innerHTML = ""; return; }
  area.innerHTML = notificationsMarkup([...notifMap.values()]);
}

function respondToNotification(notif) {
  if (notif.type === "doorbell" && notif.cameraId) {
    activateView("cameras");
    doorbellLiveIds.add(notif.cameraId);
    renderCameras(latestCameras, latestTuyaDevices);
    startLiveTimer(notif.cameraId);
    const card = cameraGrid.querySelector(`[data-camera-id="${CSS.escape(notif.cameraId)}"]`);
    card?.scrollIntoView({ behavior: "smooth", block: "center" });
  } else if (notif.type === "fire" && notif.deviceId) {
    activateView("tuya");
    const card = tuyaGrid.querySelector(`[data-device-id="${CSS.escape(notif.deviceId)}"]`);
    card?.scrollIntoView({ behavior: "smooth", block: "center" });
  } else if (notif.type === "alarm") {
    activateView("alarm");
  }
}

/* ────────────────────────────────────────────────────────────
   ALARM SECTION
   ──────────────────────────────────────────────────────────── */
const ALARM_ZONES = [
  { id: "front",          name: "Front Door",         type: "door",   state: "closed", time: "2 hr ago" },
  { id: "back",           name: "Back Door",           type: "door",   state: "closed", time: "5 hr ago" },
  { id: "garage-door",    name: "Garage Side Door",    type: "door",   state: "closed", time: "1 day ago" },
  { id: "living-window",  name: "Living Room Window",  type: "window", state: "closed", time: "3 hr ago" },
  { id: "garage-motion",  name: "Garage",              type: "motion", state: "clear",  time: "20 min ago" },
];

let alarmState   = localStorage.getItem("alarm_state")   || "disarmed";
let alarmPending = null;
let alarmCountdown = 0;
let alarmTimer   = null;
let sirenTesting = false;

function saveAlarmState() { localStorage.setItem("alarm_state", alarmState); }

function alarmShieldSVG(color, pulsing) {
  const filterStyle = color ? `filter:drop-shadow(0 0 10px ${color}66)` : "";
  const anim = pulsing ? "animation:shield-pulse 1.1s ease-in-out infinite" : "";
  const fill = color || "none";
  const stroke = color ? color : "#666";
  return `<svg width="76" height="86" viewBox="0 0 76 86" style="${filterStyle};${anim}">
    <path d="M38 4 L70 16 V40 C70 62 56 76 38 84 C20 76 6 62 6 40 V16 Z"
      fill="${fill}" stroke="${stroke}" stroke-width="3" stroke-linejoin="round" opacity="${color ? 0.92 : 1}"/>
  </svg>`;
}

function zoneIconSVG(type, breached) {
  const color = breached ? "var(--t-alert)" : "var(--t-text-dim2)";
  if (type === "door")   return `<svg width="16" height="16" viewBox="0 0 22 22"><rect x="5" y="2" width="12" height="18" rx="1" fill="none" stroke="${color}" stroke-width="1.5"/><circle cx="13.5" cy="11" r="1" fill="${color}"/></svg>`;
  if (type === "smoke")  return `<svg width="16" height="16" viewBox="0 0 22 22"><path d="M11 2.5c2.2 3 1 4.6.2 5.8-.9 1.3-1.6 2.4-.6 4 .5.8 1.5 1.2 1.5 1.2s-.4-1.6.5-2.6c1-1.1 3-1.8 3.4 1.1.2 1.3-.1 2.6-.8 3.6a5.6 5.6 0 01-9.6-1.2C4.4 11 7 8.4 8.6 6.6 10 5 11 3.9 11 2.5z" fill="none" stroke="${color}" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
  if (type === "moisture") return `<svg width="16" height="16" viewBox="0 0 22 22"><path d="M11 3s5.2 5.6 5.2 9.1A5.2 5.2 0 0111 17.3a5.2 5.2 0 01-5.2-5.2C5.8 8.6 11 3 11 3z" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  if (type === "vibration") return `<svg width="16" height="16" viewBox="0 0 22 22"><rect x="7" y="4" width="8" height="14" rx="1.5" fill="none" stroke="${color}" stroke-width="1.5"/><path d="M4 8c-1 2-1 4 0 6M18 8c1 2 1 4 0 6" fill="none" stroke="${color}" stroke-width="1.4" stroke-linecap="round"/></svg>`;
  if (type === "window") return `<svg width="16" height="16" viewBox="0 0 22 22"><rect x="3" y="3" width="16" height="16" rx="1" fill="none" stroke="${color}" stroke-width="1.5"/><line x1="11" y1="3" x2="11" y2="19" stroke="${color}" stroke-width="1.5"/><line x1="3" y1="11" x2="19" y2="11" stroke="${color}" stroke-width="1.5"/></svg>`;
  return `<svg width="16" height="16" viewBox="0 0 22 22"><circle cx="11" cy="11" r="2.2" fill="${color}"/><circle cx="11" cy="11" r="6" fill="none" stroke="${color}" stroke-width="1.3" opacity="0.45"/></svg>`;
}

/* Zone rendering, shared by the Alarm view and the Home alarm card.

   Two surfaces showing the same zones from two copies of this markup is how
   they drift: one gains a state the other renders as "Closed". */
function zoneIsBreached(zone) {
  return zone.state === "open" || zone.state === "motion" || zone.state === "alert";
}

function sortedAlarmZones(zones) {
  /* Breached first -- when something is open, that is the only part anyone is
     reading -- then alphabetical so the rest do not reshuffle on every poll. */
  return [...zones].sort((a, b) => {
    const ab = zoneIsBreached(a) ? 0 : 1;
    const bb = zoneIsBreached(b) ? 0 : 1;
    return ab - bb || String(a.name).localeCompare(String(b.name));
  });
}

function alarmBreachedCount(zones) {
  return zones.filter(zoneIsBreached).length;
}

/* The Security card on Home.

   A built-in card rather than a custom one, because everything about custom
   cards -- the cards themselves, their layout, and which are hidden -- lives in
   localStorage, so a card made on a PC cannot appear on a phone. There is
   nothing to sync it. Being built-in is what makes it show everywhere by
   default.

   Laid out by kind since 2026-09-17: the state and the arm buttons first, then
   a column each for doors and windows, safety and cameras. A row of identical
   tiles with the names cut off ("Door sensor …") answered neither "is the house
   shut" nor "which sensor is that". */
const ALARM_KIND_COLUMNS = [
  { id: "entry", label: "Doors & windows", types: ["door", "window", "vibration"] },
  { id: "safety", label: "Safety", types: ["smoke", "moisture", "gas", "co"] },
  { id: "camera", label: "Cameras", types: ["motion"], camera: true },
  { id: "motion", label: "Motion", types: ["motion"], camera: false },
];

/* A camera's person detector and a room's motion sensor both arrive as motion
   zones, and they answer different questions: one is "someone is at the front
   door", the other "someone is in the kitchen". The detector entities are the
   NPU ones the vision service publishes. */
function isCameraZone(zone) {
  return /_npu_person$/i.test(String(zone.id || "")) || /\bcamera\b/i.test(String(zone.name || ""));
}

/* Names a device was given in another language. Applied wherever a sensor's
   name is shown - the Status view had its own copy, and the Security card
   went on saying 水浸传感器. */
const ZONE_NAME_TRANSLATIONS = [[/水浸传感器/g, "Water sensor"]];

/* "Door sensor front door" is the device's name, not the place. */
function shortZoneName(name) {
  /* Each column already says what kind these are, so "Camera" and "Motion
     sensor and TH" are repetition the chip has no room for: what is left is
     the place, which is the part that differs. */
  const translated = ZONE_NAME_TRANSLATIONS.reduce((text, [pattern, to]) => text.replace(pattern, to), String(name || ""));
  const short = translated
    .replace(/^door sensor\s+/i, "")
    .replace(/\s*\(NPU\)\s*Person$/i, "")
    .replace(/^fire alarm detector\s+smoke$/i, "Smoke detector")
    .replace(/\s+(Smoke|Moisture|Contact|Occupancy|Motion)$/i, "")
    .replace(/\s+camera$/i, "")
    .replace(/^motion sensor and th\s+/i, "")
    .replace(/^motion and th\s+/i, "")
    .replace(/^vibration sensor\s+/i, "")
    .trim();
  return (short.charAt(0).toUpperCase() + short.slice(1)) || translated;
}

function zoneStateText(zone, breached) {
  if (zone.state === "unknown" || zone.state === "unavailable") return "No data";
  if (zone.type === "motion") return breached ? "Someone" : "No one";
  if (zone.type === "vibration") return breached ? "Movement" : "Still";
  if (["smoke", "moisture", "gas", "co"].includes(zone.type)) return breached ? "Detected" : "Clear";
  return breached ? "Open" : "Closed";
}

function renderHomeAlarmCard(payload = latestAlarmData) {
  const body = document.querySelector("#homeAlarmBody");
  if (!body) return;

  const haState = payload?.panel?.entity_id ? normalizeAlarmPanelState(payload.panel.state) : null;
  const displayState = haState || alarmState;
  const statusText =
    displayState === "disarmed" ? "Disarmed" :
    displayState === "arming"   ? "Arming" :
    displayState === "home"     ? "Armed · Home" :
    displayState === "away"     ? "Armed · Away" :
    "SOS ALARM ACTIVE";

  /* The card shows a chosen subset; the Alarm view still shows everything.
     Nine motion sensors made the card a list to read rather than a glance, so
     the default is doors, smoke and leaks -- the things worth interrupting for. */
  const allZones = payload?.zones?.length ? payload.zones : ALARM_ZONES;
  const chosen = homeAlarmSelection;
  const zones = chosen === null
    ? allZones.filter((z) => z.type !== "motion")
    : allZones.filter((z) => chosen.includes(String(z.id)));
  const breached = alarmBreachedCount(zones);
  const unknown = zones.filter((z) => z.state === "unknown" || z.state === "unavailable").length;
  const summary = !zones.length ? "No sensors chosen"
    : breached ? `${breached} open`
    : unknown ? `${zones.length - unknown} normal · ${unknown} no data`
    : `all ${zones.length} normal`;

  const columns = ALARM_KIND_COLUMNS
    .map((column) => ({
      ...column,
      zones: sortedAlarmZones(zones.filter((z) =>
        column.types.includes(z.type) && (column.camera === undefined || isCameraZone(z) === column.camera))),
    }))
    .filter((column) => column.zones.length);

  /* data-arm-mode, so the Security view's own handler drives these too. */
  const armButtons = displayState === "disarmed"
    ? `<button class="alarm-arm" type="button" data-arm-mode="home" title="Arm home"><i class="ti ti-home" aria-hidden="true"></i><span>Arm home</span></button>
       <button class="alarm-arm" type="button" data-arm-mode="away" title="Arm away"><i class="ti ti-lock" aria-hidden="true"></i><span>Arm away</span></button>`
    : `<button class="alarm-arm" type="button" data-arm-mode="disarmed" title="Disarm"><i class="ti ti-lock-open" aria-hidden="true"></i><span>Disarm</span></button>`;

  body.innerHTML = `
    <div class="alarm-head${displayState === "alarm" ? " alarm-active" : ""}">
      <span class="alarm-shield${breached ? " breached" : ""}"><i class="ti ti-shield-check" aria-hidden="true"></i></span>
      <span class="alarm-headline">
        <b>${escapeHtml(statusText)}</b>
        <small class="${breached ? "breached" : ""}">${escapeHtml(summary)}</small>
      </span>
      <span class="alarm-arms">${armButtons}</span>
    </div>
    <div class="alarm-kinds">${columns.map((column) => `
      <div class="alarm-kind">
        <div class="alarm-kind-head"><b>${escapeHtml(column.label)}</b><span class="${column.zones.some(zoneIsBreached) ? "breached" : "ok"}">${column.zones.filter((z) => !zoneIsBreached(z)).length}/${column.zones.length}</span></div>
        ${column.zones.map((zone) => {
          const isBreached = zoneIsBreached(zone);
          const noData = zone.state === "unknown" || zone.state === "unavailable";
          return `<div class="alarm-chip${isBreached ? " breached" : noData ? " unknown" : ""}" title="${escapeHtml(zone.name)}">
            <span class="alarm-ring">${zoneIconSVG(zone.type, isBreached)}</span>
            <span class="alarm-chip-text">
              <b>${escapeHtml(shortZoneName(zone.name))}</b>
              <small>${escapeHtml(zoneStateText(zone, isBreached))}</small>
            </span>
          </div>`;
        }).join("")}
      </div>`).join("") || `<div class="home-empty">No sensors chosen. Use the list button to pick some.</div>`}
    </div>`;
}

/* ── Which sensors the Home alarm card shows ──

   Server-side, unlike the rest of the Home card state, and deliberately: the
   card is builtin so that it reaches every device, and a per-browser choice of
   contents would put the inconsistency straight back. null means the user has
   never chosen, and the default rule applies. */
let homeAlarmSelection = null;
let homeAlarmAvailable = [];

async function loadHomeAlarmSelection() {
  try {
    const payload = await requestJson("/api/home-alarm-card");
    homeAlarmAvailable = payload.available || [];
    homeAlarmSelection = payload.using_default ? null : (payload.sensors || []);
  } catch (err) {
    // The card still renders on the default rule; only the choice is missing.
    console.error(err);
  }
  renderHomeAlarmCard();
}

function renderHomeAlarmPicker() {
  const list = document.querySelector("#homeAlarmSensorList");
  if (!list) return;
  const selected = homeAlarmSelection === null
    ? homeAlarmAvailable.filter((z) => z.type !== "motion").map((z) => String(z.id))
    : homeAlarmSelection;

  /* Zigbee gives some devices entities they never report - the backdoor
     vibration sensor also has a contact entity that has never said anything -
     and picking one puts a permanent "No data" on the card. They are hidden
     here, except one already chosen, which stays so it can be removed. */
  const hidden = homeAlarmAvailable.filter((z) => z.reported === false && !selected.includes(String(z.id)));
  const available = homeAlarmAvailable.filter((z) => !hidden.includes(z));

  if (!available.length) {
    list.innerHTML = '<div class="home-empty">No sensors reported yet.</div>';
    return;
  }
  /* Grouped by kind, because picking is a different task from reading: you come
     here knowing you want "the leak sensors", not a particular entity id. */
  const groups = [
    ["Doors & windows", ["door", "window"]],
    ["Smoke & gas", ["smoke"]],
    ["Water", ["moisture"]],
    ["Motion & presence", ["motion"]],
    ["Vibration", ["vibration"]],
  ];
  const seen = new Set();
  let html = "";
  for (const [label, types] of groups) {
    const rows = available.filter((z) => types.includes(String(z.type)));
    if (!rows.length) continue;
    html += `<div class="net-modal-group">${escapeHtml(label)}</div>`;
    for (const zone of rows) {
      seen.add(String(zone.id));
      const on = selected.includes(String(zone.id));
      html += `<label class="net-modal-row">
        <input type="checkbox" data-home-alarm-sensor="${escapeHtml(String(zone.id))}" ${on ? "checked" : ""}>
        <span>${escapeHtml(zone.name)}</span>
      </label>`;
    }
  }
  const rest = available.filter((z) => !seen.has(String(z.id)));
  if (rest.length) {
    html += `<div class="net-modal-group">Other</div>`;
    for (const zone of rest) {
      const on = selected.includes(String(zone.id));
      html += `<label class="net-modal-row">
        <input type="checkbox" data-home-alarm-sensor="${escapeHtml(String(zone.id))}" ${on ? "checked" : ""}>
        <span>${escapeHtml(zone.name)}</span>
      </label>`;
    }
  }
  if (hidden.length) {
    html += `<div class="net-modal-note">${hidden.length} sensor${hidden.length === 1 ? "" : "s"} hidden: ${
      hidden.length === 1 ? "it has" : "they have"} never reported anything.</div>`;
  }
  list.innerHTML = html;
}

async function saveHomeAlarmSelection(sensors) {
  homeAlarmSelection = sensors;
  renderHomeAlarmCard();
  try {
    await requestJson("/api/home-alarm-card", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sensors }),
    });
    logActivity(`Security card → ${sensors.length} sensor${sensors.length === 1 ? "" : "s"}`);
  } catch (err) {
    console.error(err);
    logActivity("Could not save the alarm card sensors", "error");
    await loadHomeAlarmSelection();
  }
}

(function initHomeAlarmPicker() {
  const modal = document.querySelector("#homeAlarmModal");
  if (!modal) return;
  const open = () => {
    renderHomeAlarmPicker();          // paint from what we have, then refresh
    modal.hidden = false;
    // A sensor added since page load should be pickable without a reload.
    loadHomeAlarmSelection().then(renderHomeAlarmPicker).catch(console.error);
  };
  const close = () => { modal.hidden = true; };

  document.querySelector("#homeAlarmPickButton")?.addEventListener("click", (event) => {
    event.stopPropagation();   // the card header is draggable
    open();
  });
  document.querySelector("#closeHomeAlarmModal")?.addEventListener("click", close);
  modal.addEventListener("click", (event) => { if (event.target === modal) close(); });

  document.querySelector("#homeAlarmSave")?.addEventListener("click", () => {
    const picked = [...modal.querySelectorAll("[data-home-alarm-sensor]")]
      .filter((box) => box.checked)
      .map((box) => box.dataset.homeAlarmSensor);
    saveHomeAlarmSelection(picked).catch(console.error);
    close();
  });

  /* Back to the rule rather than to a snapshot of it, so a sensor added later
     still appears without coming back here. */
  document.querySelector("#homeAlarmUseDefault")?.addEventListener("click", () => {
    saveHomeAlarmSelection(
      homeAlarmAvailable.filter((z) => z.type !== "motion").map((z) => String(z.id))
    ).catch(console.error);
    close();
  });
})();

/* ── The Security view: the house ──────────────────────────────────────────
   A wall of identical tiles answered neither "is the house shut" nor "which
   sensor is that". The view is now a cutaway of the house: rooms in their
   places, each carrying its own sensors, amber when something is happening.
   Clicking a room lists its sensors beside the drawing.

   The house is a picture (a rendered cutaway, security-house.jpg) with live
   pins laid over it at percentages (HOUSE_ROOMS). The picture cannot change,
   so what it paints that the house does not have - its sensor icons, its
   legend, "Bedroom 1" - is covered by what the house does. A new picture
   means re-measuring the pins, and only that. Sensors find
   their room through Areas; the two exceptions are written down in
   ROOM_OVERRIDES, where Areas cannot say what the house knows. */
const HOUSE_ROOMS = [
  /* Pins on the picture, in % of it (1312 x 1199 px). Where the picture has
     painted sensor icons, a pin covers them - w is that row's width, so a
     one-sensor pin still hides all of it. Where it paints a name that is not
     ours ("Bedroom 1"), cover puts ours over it. named: the picture has no
     label there, so the pin carries the room's name. */
  { name: "Master Bedroom", x: 30.72, y: 15.60, w: 6.9, cover: [29.88, 27.36] , floor: "up" },
  { name: "North Bedroom",  x: 47.10, y: 15.60, w: 6.9, cover: [46.95, 25.69] , floor: "up" },
  { name: "Hallway",        x: 50.30, y: 32.94, named: true , floor: "up" },
  { name: "South Bedroom",  x: 70.43, y: 15.60, w: 6.9, cover: [71.04, 25.69] , floor: "up" },
  { name: "Bathroom",       x: 58.69, y: 20.85, named: true , floor: "up" },
  { name: "Garage",         x: 19.05, y: 49.79, w: 9.4 },
  { name: "Office",         x: 41.01, y: 63.72, w: 7.1 },
  { name: "Living Room",    x: 73.32, y: 63.39, w: 9.1 },
  { name: "Kitchen",        x: 49.85, y: 43.20, w: 9.2 },
  { name: "Family Room",    x: 70.73, y: 43.95, w: 9.5 },
  { name: "Utility Room",   x: 35.98, y: 54.21, w: 7.2, label: "Utility" },
  { name: "Front Door",     x: 55.26, y: 75.48, named: true, outdoor: true },
  { name: "Front Yard",     x: 42.68, y: 85.90, outdoor: true },
  { name: "Back Yard",      x: 86.89, y: 21.35, w: 9.5, outdoor: true },
];

/* Areas has one "Bedroom" for the whole upstairs. The ecobee sensors name the
   master bedroom; the other two sit in the hallway between the bedrooms. Split
   the areas and these rules stop being consulted. */
const ROOM_OVERRIDES = [
  { area: "Bedroom", match: /^master bedroom/i, room: "Master Bedroom" },
  { area: "Bedroom", match: /^(upstairs|bedroom)$/i, room: "Hallway" },
  { area: "Bedroom", match: /./, room: "Hallway" },
];

/* A camera's person detector belongs where the camera looks, which its name
   says and no assignment does. */
function cameraZoneRoom(zone) {
  const name = String(zone.name || "").replace(/\s*\(NPU\)\s*Person$/i, "").replace(/\s*camera$/i, "").trim();
  const canonical = { frontyard: "Front Yard", backyard: "Back Yard", "front door": "Front Door" };
  const key = name.toLowerCase();
  return canonical[key] || name;
}

function zoneRoom(zone) {
  if (/_npu_person$/i.test(String(zone.id || ""))) return cameraZoneRoom(zone);
  const areaId = areasDoc.assignments?.[`sensor:${areaSlug(sensorBaseName(String(zone.name || "")))}`];
  const area = (areasDoc.areas || []).find((a) => a.id === areaId);
  const areaName = area?.name || null;
  if (!areaName) return null;
  const short = shortZoneName(zone.name);
  for (const rule of ROOM_OVERRIDES) {
    if (rule.area === areaName && rule.match.test(short)) return rule.room;
  }
  return areaName;
}

/* The picture of the house. Static; the live state is laid over it. The
   version is part of the URL so the picture can be cached for good and a new
   one still reaches every screen. */
const HOUSE_PICTURE = "/static/security-house.jpg?v=1";
const HOUSE_PICTURE_HTML = `<img class="house-picture" src="${HOUSE_PICTURE}" width="1312" height="1199"
  alt="The house, cut open: both floors, the garage, the front yard and the back garden" draggable="false">`;

/* Which room the view is showing on the right. Kept across refreshes so a poll
   does not move it. */
let selectedHouseRoom = null;

function zonesByRoom(zones) {
  const rooms = new Map();
  const loose = [];
  for (const zone of zones) {
    const room = zoneRoom(zone);
    if (!room) { loose.push(zone); continue; }
    if (!rooms.has(room)) rooms.set(room, []);
    rooms.get(room).push(zone);
  }
  for (const list of rooms.values()) list.splice(0, list.length, ...sortedAlarmZones(list));
  return { rooms, loose: sortedAlarmZones(loose) };
}

function houseRoomHtml(room, zones) {
  const list = zones || [];
  const place = `left:${room.x}%;top:${room.y}%${room.w ? `;min-width:${room.w}%` : ""}`;
  const cover = room.cover
    ? `<span class="house-label" style="left:${room.cover[0]}%;top:${room.cover[1]}%">${escapeHtml(room.label || room.name)}</span>`
    : "";
  if (!list.length) {
    // Only where the picture paints icons is there anything to cover.
    return cover + (room.w
      ? `<span class="house-pin house-pin-empty" style="${place}">No sensors</span>` : "");
  }
  const hot = list.some(zoneIsBreached);
  const title = `${room.name}: ${hot ? `${list.filter(zoneIsBreached).length} active` : `${list.length} sensor${list.length === 1 ? "" : "s"}, all quiet`}`;
  return cover + `
    <button class="house-pin${hot ? " breached" : ""}${selectedHouseRoom === room.name ? " selected" : ""}"
            type="button" data-house-room="${escapeHtml(room.name)}" style="${place}"
            title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">
      ${list.slice(0, 5).map((z) => {
        const breached = zoneIsBreached(z);
        const unknown = z.state === "unknown" || z.state === "unavailable";
        return `<span class="house-pip${breached ? " on" : ""}${unknown ? " off" : ""}">${zoneIconSVG(z.type, breached)}</span>`;
      }).join("")}
      ${room.named ? `<span class="house-pin-name">${escapeHtml(room.label || room.name)}</span>` : ""}
    </button>`;
}

/* The corner the picture fills with a legend: how each floor is, in a line. */
function houseFloorLines(rooms) {
  const floors = [["Upstairs", (r) => r.floor === "up"], ["Ground floor", (r) => !r.floor && !r.outdoor], ["Outside", (r) => r.outdoor]];
  return floors.map(([label, test]) => {
    const zones = HOUSE_ROOMS.filter(test).flatMap((r) => rooms.get(r.name) || []);
    const hot = zones.filter(zoneIsBreached).length;
    return `<span class="house-cover-row${hot ? " breached" : ""}"><span>${label}</span><span>${
      !zones.length ? "–" : hot ? `${hot} active` : "quiet"}</span></span>`;
  }).join("");
}

/* What happened last, anywhere: the newest reading, for the picture's corner. */
function houseLatestZone(zones) {
  return zones
    .filter((z) => Number.isFinite(z.age_seconds))
    .reduce((newest, z) => (!newest || z.age_seconds < newest.age_seconds ? z : newest), null);
}

function zoneAgeLabel(seconds) {
  const minutes = seconds / 60;
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = minutes / 60;
  return hours < 48 ? `${hours.toFixed(1)} h` : `${Math.round(hours / 24)} d`;
}

function houseDetailHtml(room, list, controls) {
  const zones = list || [];
  const hot = zones.filter(zoneIsBreached).length;
  const rows = zones.map((z) => {
    const breached = zoneIsBreached(z);
    const unknown = z.state === "unknown" || z.state === "unavailable";
    return `
      <div class="house-detail-row${breached ? " breached" : ""}${unknown ? " unknown" : ""}">
        <span class="house-detail-icon">${zoneIconSVG(z.type, breached)}</span>
        <span class="house-detail-name">${escapeHtml(shortZoneName(z.name))}</span>
        <span class="house-detail-state">${escapeHtml(zoneStateText(z, breached))}${
          Number.isFinite(z.age_seconds) ? `<span class="house-detail-age">${zoneAgeLabel(z.age_seconds)}</span>` : ""}</span>
      </div>`;
  }).join("");

  return `
    <h3>${escapeHtml(room || "Nothing selected")}</h3>
    <div class="house-detail-sub">${zones.length
      ? `${zones.length} sensor${zones.length === 1 ? "" : "s"} · ${hot ? `${hot} active now` : "all quiet"}`
      : "Pick a room on the plan"}</div>
    ${rows}
    ${controls}`;
}

function renderAlarmSection(payload = latestAlarmData) {
  const panel = document.querySelector("#alarmPanel");
  if (!panel) return;

  const haState = payload?.panel?.entity_id ? normalizeAlarmPanelState(payload.panel.state) : null;
  const displayState = haState || alarmState;
  const statusText =
    displayState === "disarmed" ? "Disarmed" :
    displayState === "arming"   ? (haState ? "Arming" : `Arming ${alarmPending === "home" ? "Home" : "Away"} in ${alarmCountdown}s`) :
    displayState === "home"     ? "Armed · Home" :
    displayState === "away"     ? "Armed · Away" :
    "SOS ALARM ACTIVE";

  const zones = payload?.zones?.length ? payload.zones : ALARM_ZONES;
  const { rooms, loose } = zonesByRoom(zones);
  const breached = alarmBreachedCount(zones);

  if (!selectedHouseRoom || (!rooms.has(selectedHouseRoom) && selectedHouseRoom !== "Not placed")) {
    const busiest = HOUSE_ROOMS.find((room) => (rooms.get(room.name) || []).some(zoneIsBreached));
    selectedHouseRoom = busiest?.name || HOUSE_ROOMS.find((room) => rooms.has(room.name))?.name || null;
  }

  const modes = displayState === "disarmed"
    ? [["home", "Arm home", "ti-home"], ["away", "Arm away", "ti-shield-lock"]]
    : [["disarmed", "Disarm", "ti-lock-open"]];
  const armButtons = modes.map(([mode, label, icon]) =>
    `<button class="house-arm${mode === "disarmed" ? "" : " primary"}" type="button" data-arm-mode="${mode}">
       <i class="ti ${icon}" aria-hidden="true"></i>${label}</button>`).join("");

  /* One row of small buttons: the room's sensors are what the card is for. */
  const haControls = (payload?.controls || []).map((control) => {
    const isOn = control.state === "on";
    const label = `${shortControlName(control.name)} · ${formatStatus(control.state || "unknown").toLowerCase()}`;
    return control.controllable
      ? `<button class="house-chip${isOn ? " on" : ""}" type="button" data-ha-command="${isOn ? "off" : "on"}"
                 data-ha-entity-id="${escapeHtml(control.entity_id)}" title="${escapeHtml(`${control.name}: turn ${isOn ? "off" : "on"}`)}">${escapeHtml(label)}</button>`
      : `<span class="house-chip muted" title="${escapeHtml(control.name)}">${escapeHtml(label)}</span>`;
  }).join("");

  const controlsHtml = `
    <div class="house-controls">
      ${haControls}
      <button class="house-chip ${sirenTesting ? "testing" : ""}" type="button" id="sirenTestBtn" title="Sounds for two seconds">${sirenTesting ? "Testing…" : "Test siren"}</button>
      <button class="house-chip sos" type="button" id="sosTriggerBtn" title="Sound the alarm now">SOS</button>
    </div>`;

  renderHomeAlarmCard(payload);
  const alarmBadgeEl = document.querySelector("#alarmBadge");
  if (alarmBadgeEl) alarmBadgeEl.textContent = displayState === "alarm" ? "!" : displayState === "disarmed" ? "–" : "ON";

  const detailZones = selectedHouseRoom === "Not placed" ? loose : (rooms.get(selectedHouseRoom) || []);
  const latest = houseLatestZone(zones);

  panel.innerHTML = `
    <div class="house-head${displayState === "alarm" ? " alarm-active" : ""}">
      <h2 class="house-title">Security</h2>
      <span class="house-shield${breached ? " breached" : ""}"><i class="ti ti-shield-check" aria-hidden="true"></i></span>
      <span class="house-state">
        <b>${escapeHtml(statusText)}</b>
        <small>${escapeHtml(payload?.panel?.name || "Local alarm panel")} · ${
          breached ? `${breached} sensor${breached === 1 ? "" : "s"} active` : `all ${zones.length} normal`}</small>
      </span>
      <span class="house-arms">${armButtons}</span>
    </div>
    <div class="house-stage">
      <div>
        <div class="house-scene">
          ${HOUSE_PICTURE_HTML}
          <div class="house-cover house-cover-status${breached ? " breached" : ""}">
            <b>${escapeHtml(statusText)}</b>
            <span>${breached ? `${breached} active now` : `all ${zones.length} normal`}</span>
            ${houseFloorLines(rooms)}
            <span class="house-cover-hint">Tap a pin for its sensors</span>
          </div>
          <div class="house-cover house-cover-latest">${latest
            ? `<b>${escapeHtml(shortZoneName(latest.name))}</b><span>${escapeHtml(zoneStateText(latest, zoneIsBreached(latest)))} · ${zoneAgeLabel(latest.age_seconds)}</span>`
            : "<b>Latest</b><span>Nothing yet</span>"}</div>
          ${HOUSE_ROOMS.map((room) => houseRoomHtml(room, rooms.get(room.name))).join("")}
        </div>
      </div>
      <div class="house-side">
        ${loose.length ? `<button class="house-loose" type="button" data-house-room="Not placed">${loose.length} sensor${loose.length === 1 ? "" : "s"} not in a room</button>` : ""}
        <section class="house-detail" aria-label="The selected room">${houseDetailHtml(selectedHouseRoom, detailZones, controlsHtml)}</section>
        <section class="house-activity" id="houseActivity" aria-label="Recent activity">${houseActivityHtml()}</section>
      </div>
    </div>`;
}

/* ── Security activity: the house memory's recent events and today's counts ──
   One request feeds two cards: Recent activity on the Security view and Today
   at a glance on Status. A sensor firing again within ten minutes is folded
   into one line by the board. */
const SECURITY_ACTIVITY_MS = 60_000;
const ACTIVITY_WORDS = { camera: "person", door: "opened", motion: "motion", vibration: "vibration", safety: "alert" };
let latestSecurityActivity = null;

function shortControlName(name) {
  return String(name || "").replace(/^alarm system\s+/i, "").replace(/^\w/, (c) => c.toUpperCase());
}

function activityTime(ts) {
  const at = new Date(ts * 1000);
  return Number.isNaN(at.getTime()) ? "" : at.toTimeString().slice(0, 5);
}

function houseActivityHtml(data = latestSecurityActivity) {
  const head = `<div class="house-activity-head"><h3>Recent activity</h3>${
    data?.today ? `<small>${data.today.doors + data.today.people + data.today.motion + data.today.other} today</small>` : ""}</div>`;
  if (!data) return `${head}<p class="house-activity-empty">Loading…</p>`;
  if (!data.available) return `${head}<p class="house-activity-empty">The house memory is not running yet.</p>`;
  const lines = data.recent || [];
  if (!lines.length) return `${head}<p class="house-activity-empty">Nothing in the last day.</p>`;
  return head + `<ol class="house-activity-list">${lines.map((line) => {
    const what = ACTIVITY_WORDS[line.kind] || line.kind;
    const more = line.count > 1 ? `, ${line.count} times since ${activityTime(line.first_ts)}` : "";
    const room = zoneRoom({ id: line.entity_id, name: line.name });
    return `<li><button type="button" class="house-activity-line kind-${escapeHtml(line.kind)}"${room ? ` data-house-room="${escapeHtml(room)}"` : ""}>
      <time>${activityTime(line.ts)}</time><i aria-hidden="true"></i>
      <span>${escapeHtml(shortZoneName(line.name))}<small> · ${escapeHtml(what + more)}</small></span></button></li>`;
  }).join("")}</ol>`;
}

/* Today at a glance, on Status: three counts and the day so far, by hour. */
function statusTodayHtml(data = latestSecurityActivity) {
  const today = data?.today;
  if (!data?.available || !today) {
    return `<div class="home-panel-head"><span class="panel-title"><i class="ti ti-calendar-stats"></i> Today at a glance</span></div>
      <p class="st-empty">${data && !data.available ? "The house memory is not running yet." : "Loading…"}</p>`;
  }
  const hours = today.hours || [];
  const max = Math.max(1, ...hours);
  const stat = (value, label) => `<div class="today-stat"><b class="mono">${value}</b><span>${label}</span></div>`;
  return `<div class="home-panel-head"><span class="panel-title"><i class="ti ti-calendar-stats"></i> Today at a glance</span><span class="section-meta">since midnight</span></div>
    <div class="today-body">
      <div class="today-stats">${stat(today.doors, `door${today.doors === 1 ? "" : "s"} opened`)}${stat(today.people, "people seen")}${stat(today.motion, "motion")}</div>
      <div class="today-hours" role="img" aria-label="Security events per hour today">
        ${hours.map((value, hour) => `<i class="${hour === today.hour_now ? "now" : hour > today.hour_now ? "later" : ""}"
          style="height:${hour > today.hour_now ? 0 : Math.max(value ? 6 : 2, (value / max) * 100).toFixed(1)}%"
          title="${String(hour).padStart(2, "0")}:00 · ${value} event${value === 1 ? "" : "s"}"></i>`).join("")}
        <span class="today-axis"><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></span>
      </div>
    </div>`;
}

function renderSecurityActivity() {
  const activity = document.querySelector("#houseActivity");
  if (activity) activity.innerHTML = houseActivityHtml();
  const today = document.querySelector("#statusToday");
  if (today) today.innerHTML = statusTodayHtml();
}

async function loadSecurityActivity() {
  try {
    latestSecurityActivity = await requestJson(`/api/memory/security?tz=${encodeURIComponent(browserTimeZone())}`);
  } catch (error) {
    console.error(error);
  }
  renderSecurityActivity();
}

setInterval(() => {
  if (document.hidden || !document.querySelector('.view-panel.active[data-view-panel="alarm"], .view-panel.active[data-view-panel="status"]')) return;
  loadSecurityActivity();
}, SECURITY_ACTIVITY_MS);

/* Choosing a room only changes what the panel beside the house lists. */
document.addEventListener("click", (event) => {
  const room = event.target.closest("[data-house-room]");
  if (!room) return;
  selectedHouseRoom = room.dataset.houseRoom;
  renderAlarmSection();
});

function normalizeAlarmPanelState(state) {
  const normalized = String(state || "").toLowerCase();
  if (normalized === "armed_home") return "home";
  if (normalized === "armed_away") return "away";
  if (normalized === "triggered") return "alarm";
  if (normalized === "pending" || normalized === "arming") return "arming";
  if (normalized === "disarmed") return "disarmed";
  return null;
}

async function sendAlarmCommand(mode) {
  apiStatus.textContent = "Sending";
  await requestJson(`/api/alarm/commands/${encodeURIComponent(mode)}`, { method: "POST" });
  logActivity(`Alarm → ${mode}`);
  await loadDevices();
}
async function requestArmMode(mode) {
  clearInterval(alarmTimer);
  if (latestAlarmData?.panel?.entity_id) {
    try {
      await sendAlarmCommand(mode);
    } catch (error) {
      apiStatus.textContent = "Error";
      console.error(error);
    }
    return;
  }
  if (mode === "disarmed") {
    alarmState = "disarmed";
    alarmPending = null;
    alarmCountdown = 0;
    saveAlarmState();
    renderAlarmSection();
    return;
  }
  alarmPending = mode;
  alarmState = "arming";
  alarmCountdown = 5;
  renderAlarmSection();
  alarmTimer = setInterval(() => {
    alarmCountdown--;
    if (alarmCountdown <= 0) {
      clearInterval(alarmTimer);
      alarmState = alarmPending;
      alarmPending = null;
      saveAlarmState();
    }
    renderAlarmSection();
  }, 1000);
}

function triggerSOS() {
  clearInterval(alarmTimer);
  alarmState = "alarm";
  alarmPending = null;
  saveAlarmState();
  renderAlarmSection();
  pushNotification("alarm", "SOS alarm triggered", "Panic button pressed on the alarm panel");
}

/* ── Main load ── */
async function loadDevices() {
  if (statusDot) statusDot.classList.remove("online");
  apiStatus.textContent = "Refreshing";

  const [deviceData, cameraData, tuyaData, weatherData, ecobeeData, homeAssistantData, alarmData, matterData, areasData] = await Promise.all([
    requestJson("/api/devices"),
    requestJson("/api/cameras"),
    requestJson("/api/tuya/devices"),
    requestJson("/api/weather").catch(() => null), // weather being down must not kill the refresh
    requestJson("/api/ecobee/thermostats"),
    requestJson("/api/home-assistant/entities"),
    requestJson("/api/alarm"),
    requestJson("/api/matter/devices").catch(() => ({ devices: [], matter_online: false })),
    requestJson("/api/areas").catch(() => areasDoc),
  ]);

  notifyDoorbellEvents(cameraData.cameras);
  notifySeenNewHomeAssistantDevices(homeAssistantData.entities);

  latestCameras       = cameraData.cameras;
  latestCameraPaths   = cameraData.paths || [];
  latestTuyaDevices   = tuyaData.devices;
  latestAlarmData     = alarmData;
  latestSwitchDevices = deviceData.devices;
  latestMatterDevices = matterData.devices || [];
  applyPendingCommands();
  latestThermostats   = ecobeeData?.thermostats || [];
  areasDoc            = areasData;

  renderDevices(deviceData.devices, cameraData.cameras, matterData.devices || []);
  renderTuyaDevices(tuyaData.devices);
  renderThermostats(ecobeeData);
  renderHomeAssistant(homeAssistantData);
  renderCameras(cameraData.cameras, tuyaData.devices);
  renderWeather(weatherData);
  renderAlarmSection(alarmData);
  _updateMatterServerStatus(matterData.matter_online ?? false);
  _renderMatterDeviceList(matterData.devices || []);
  renderHomeView();
  refreshActiveDynamicGroupPanel();
  /* After the render, so an episode that opens here draws over fresh cards.
     Paths first: they own their cameras, and the single-camera watch skips
     them, so letting the path decide first keeps the two from racing. */
  updatePathWatch();
  updateMotionWatch();

  if (statusDot) statusDot.classList.add("online");
  apiStatus.textContent = "Online";

  logActivity("Devices refreshed");

  cacheSnapshotsInBackground(cameraData.cameras).catch(console.error);
}

/* ═════════════════ HOME (AREAS) VIEW ═════════════════ */

const HOME_AREA_ORDER_KEY = "home_area_order";

const AREA_ICON_CHOICES = [
  "home", "sofa", "bed", "chef-hat", "bath", "desk",
  "car", "tree", "flower", "door", "stairs", "device-tv",
  "barbell", "sun-high", "plant", "toys",
];

const AREA_KIND_ICONS = {
  light: "ti-bulb",
  plug: "ti-plug",
  sensor: "ti-radar-2",
  camera: "ti-video",
  thermostat: "ti-temperature",
  ambient: "ti-lamp-2",
  humidifier: "ti-droplet",
  environment: "ti-temperature-celsius",
  bridge: "ti-router",
};

/* ── Bridges ──

   A bridge is a radio other devices talk through, not a device in its own
   right: the Zigbee coordinator, and the Tuya multi-mode gateway. Grouping
   them matters because a dead bridge is silent -- everything behind it simply
   stops updating, and nothing on screen says why. One replug went unnoticed
   for 66 minutes.

   Nothing in a Tuya gateway's payload distinguishes it from a sensor: it
   reports link state through the same shape a door sensor reports its state.
   The product name is the only signal available, and it is stable per product,
   so that is what this matches on. A device caught wrongly can be moved back
   with Manage, which is exactly what the per-device overrides are for. */
const BRIDGE_NAME_PATTERN = /\b(gateway|bridge|coordinator|hub)\b/i;

function isBridgeSensorGroup(group) {
  return BRIDGE_NAME_PATTERN.test(String(group?.name || ""));
}

/* One shape for both kinds of bridge, so the tile renderer does not have to
   know whether it is drawing Zigbee2MQTT or a Tuya gateway.
   state is "online" | "offline" | "unknown" -- "unknown" is a real third case
   here and must not collapse into "offline": it means we could not reach Home
   Assistant to ask, which is a different problem with a different fix. */
function zigbeeBridgeDevice() {
  const base = { id: "zigbee", name: "Zigbee coordinator", icon: "ti-access-point" };
  const info = latestZigbeeBridge;

  if (!info) {
    return { ...base, state: "unknown", label: "Unknown", meta: "Dashboard could not reach the bridge API" };
  }
  if (!info.available) {
    return { ...base, state: "unknown", label: "Unknown", meta: "Home Assistant unreachable, or MQTT not set up" };
  }

  const since = _zigbeeSince(info.connection_changed);
  const version = info.version ? `Zigbee2MQTT ${info.version}` : "Zigbee2MQTT";
  if (info.connected === true) {
    return { ...base, state: "online", label: "Online", meta: since ? `${version} · up ${since}` : version };
  }
  if (info.connected === false) {
    return { ...base, state: "offline", label: "Offline", meta: since ? `Down for ${since} · ${version}` : version };
  }
  return { ...base, state: "unknown", label: "Unknown", meta: `${version} · no connection state published` };
}

function isMatterBridgeDevice(device) {
  return device?.is_bridge === true || device?.category === "bridge";
}

/* Same tile shape as the Zigbee coordinator and the Tuya gateway, so the three
   radios read as one set. A Matter bridge has no "connected" flag of its own --
   matter-server either reaches the node or does not -- so availability is the
   whole of its health. */
function matterBridgeDevice(device) {
  const online = device.available !== false && device.online !== false;
  return {
    id: String(device.host || "matter-bridge"),
    name: device.name || "Matter bridge",
    icon: "ti-topology-star-3",
    state: online ? "online" : "offline",
    label: online ? "Online" : "Offline",
    meta: "Matter bridge · publishes this dashboard's devices",
  };
}

function tuyaGatewayBridgeDevice(group) {
  const first = group.readings[0] || {};
  const online = group.readings.some((d) => d.online !== false);
  /* Tuya reports a gateway's model as its name, so using the model unguarded
     printed the name twice on the tile. */
  const model = String(first.model || "");
  const meta = model && model !== group.name ? model : "Tuya gateway";
  return {
    id: areaSlug(group.name),
    name: group.name,
    icon: "ti-router",
    state: online ? "online" : "offline",
    label: online ? "Online" : "Offline",
    meta,
  };
}

/* The tile, in the same language as the sensor tiles: type-tinted ground, an
   oversized watermark, one headline word. An offline bridge is the loudest
   thing on the page on purpose. */
function bridgeTileHtml(bridge) {
  const tint = bridge.state === "online" ? "var(--green)"
    : bridge.state === "offline" ? "var(--red)" : "var(--slate)";
  const cls = bridge.state === "offline" ? " sdc-tile-alert"
    : bridge.state === "unknown" ? " sdc-tile-offline" : "";
  return `<article class="sdc-tile bridge-tile${cls}"
    data-device-id="${escapeHtml(bridge.name)}" style="--tint:${tint}">
    <i class="ti ${escapeHtml(bridge.icon)} sdc-tile-mark" aria-hidden="true"></i>
    <div class="sdc-tile-top">
      <span class="sdc-tile-badge"><i class="ti ${escapeHtml(bridge.icon)}" aria-hidden="true"></i>Bridge</span>
    </div>
    <div class="sdc-tile-read">
      <div class="sdc-tile-state">${escapeHtml(bridge.label)}</div>
      <h3 class="sdc-tile-name" title="${escapeHtml(bridge.name)}">${escapeHtml(bridge.name)}</h3>
      <div class="sdc-tile-sub"><span class="sdc-tile-note">${escapeHtml(bridge.meta)}</span></div>
    </div>
  </article>`;
}

function areaSlug(name) {
  return String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/* Flatten every dashboard device into {key, kind, name, room, data} entries.
   Keys must stay stable across refreshes — they anchor area assignments. */
function collectHomeInventory() {
  const inventory = [];

  for (const device of [...latestSwitchDevices, ...latestMatterDevices]) {
    /* Our own chip-bridge-app is a node in the fabric like any other, so it
       arrived here as a light to switch on. It is the thing publishing the
       lights; it belongs with the other radios, and the key keeps its "dev:"
       prefix so an area assignment already made against it survives. */
    if (isMatterBridgeDevice(device)) {
      inventory.push({
        key: `dev:${device.host}`,
        kind: "bridge",
        name: device.name,
        room: device.room || "",
        data: matterBridgeDevice(device),
      });
      continue;
    }
    inventory.push({
      key: `dev:${device.host}`,
      kind: device.category === "smart_plug" ? "plug" : "light",
      name: device.name,
      room: device.room || "",
      data: device,
    });
  }

  /* A gateway arrives on the same Tuya feed as the sensors and is grouped with
     them, so it is separated here rather than at the source -- one place makes
     the decision, and the key keeps its "sensor:" prefix so an override the
     user already set does not become orphaned. */
  const visibleSensors = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  for (const group of groupSensorDevices(visibleSensors)) {
    const bridge = isBridgeSensorGroup(group);
    inventory.push({
      key: `sensor:${areaSlug(group.name)}`,
      kind: bridge ? "bridge" : "sensor",
      name: group.name,
      room: group.readings[0]?.room || "",
      data: bridge ? tuyaGatewayBridgeDevice(group) : group,
    });
  }

  const tuyaCams = latestTuyaDevices.filter(isTuyaCamera).map(tuyaCameraCard);
  for (const camera of [...latestCameras, ...tuyaCams]) {
    inventory.push({
      key: `cam:${cameraIdFor(camera)}`,
      kind: "camera",
      name: camera.name || cameraIdFor(camera),
      room: camera.room || "",
      data: camera,
    });
  }

  for (const thermostat of latestThermostats) {
    inventory.push({
      key: `thermo:${thermostat.id}`,
      kind: "thermostat",
      name: thermostat.name,
      room: thermostat.room || "",
      data: thermostat,
    });
  }

  for (const light of latestAmbientLights) {
    inventory.push({
      key: `ambient:${light.id}`,
      kind: "ambient",
      name: light.name,
      room: light.room || "",
      data: light,
    });
  }

  for (const humidifier of latestHumidifiers) {
    inventory.push({
      key: `humidifier:${humidifier.id}`,
      kind: "humidifier",
      name: humidifier.name,
      room: humidifier.room || "",
      data: humidifier,
    });
  }

  for (const sensor of latestEnvironmentSensors) {
    inventory.push({
      key: `env:${areaSlug(sensor.name || "environment sensor")}`,
      kind: "environment",
      name: sensor.name,
      room: sensor.room || "",
      data: sensor,
    });
  }

  /* The coordinator is the one device with no list to come from: it reaches
     the dashboard as bridge health, not as a device. */
  inventory.push({
    key: "bridge:zigbee",
    kind: "bridge",
    name: "Zigbee coordinator",
    room: "",
    data: zigbeeBridgeDevice(),
  });

  return inventory;
}

/* ── Device group membership ──
   Membership is multi-valued on purpose: a 4-in-1 sensor belongs in both
   Environment and Sensors, because those are two views of its readings rather
   than two competing homes. A per-device override adds or removes one group
   without disturbing the others. */
function resolveDeviceGroupMembers(group, inventory, overrides) {
  const kinds = new Set(group.kinds || []);
  const rules = overrides || {};
  return inventory.filter((item) => {
    const rule = rules[item.key] || {};
    if ((rule.exclude || []).includes(group.id)) return false;
    if ((rule.include || []).includes(group.id)) return true;
    return kinds.has(item.kind);
  });
}

/* Devices belonging to no group at all land here, so deleting a group can never
   make a device invisible. Mirrors the Areas feature's auto:unassigned bucket:
   synthetic, never persisted, shown only when non-empty, always sorted last. */
const UNASSIGNED_GROUP_ID = "auto:unassigned";

/* Memoised for the current synchronous turn only. A full dashboard render calls
   this once per panel and once per foreign-kind pass — roughly a dozen times —
   and each call otherwise rebuilds the whole inventory and re-resolves every
   group. The microtask clear means the cache can never outlive the turn that
   built it, so membership cannot go stale across an await.

   The cache hangs off the function rather than a module-level binding so the
   function stays self-contained: the JS test harness extracts functions by name
   and would not carry a separate declaration along with it. */
function resolveDeviceGroups() {
  if (resolveDeviceGroups.cache) return resolveDeviceGroups.cache;

  const inventory = collectHomeInventory();
  const overrides = latestDeviceGroupOverrides || {};
  const groups = (latestDeviceGroups || []).map((group) => ({
    ...group,
    devices: resolveDeviceGroupMembers(group, inventory, overrides),
  }));

  const claimed = new Set();
  groups.forEach((group) => group.devices.forEach((device) => claimed.add(device.key)));
  const orphans = inventory.filter((item) => !claimed.has(item.key));
  if (orphans.length) {
    groups.push({
      id: UNASSIGNED_GROUP_ID,
      name: "Unassigned",
      icon: "help-hexagon",
      color: "slate",
      kinds: [],
      chrome: [],
      readingFilter: null,
      builtin: false,
      synthetic: true,
      devices: orphans,
    });
  }

  resolveDeviceGroups.cache = groups;
  queueMicrotask(() => { resolveDeviceGroups.cache = null; });
  return groups;
}

function findDeviceGroup(groupId) {
  return resolveDeviceGroups().find((group) => group.id === groupId);
}

/* The underlying device objects for a group's members, restricted to kinds the
   caller's renderer understands. Returns [] for an unknown group, so a deleted
   group degrades to an empty panel rather than throwing. */
function groupMemberData(groupId, kinds) {
  const wanted = new Set(kinds);
  const group = findDeviceGroup(groupId);
  if (!group) return [];
  return group.devices.filter((d) => wanted.has(d.kind)).map((d) => d.data);
}

/* Any device the user moved into a group whose bespoke renderer cannot display
   it. Rendered generically below the native content so nothing silently
   vanishes and no bespoke renderer is handed a shape it was not written for. */
function renderForeignKinds(groupId, nativeKinds, containerId) {
  const container = document.querySelector(containerId);
  if (!container) return;
  const existing = container.parentElement?.querySelector(".device-group-foreign");
  if (existing) existing.remove();

  const group = findDeviceGroup(groupId);
  if (!group) return;
  const native = new Set(nativeKinds);
  const foreign = group.devices.filter((d) => !native.has(d.kind));
  if (!foreign.length) return;

  const wrap = document.createElement("div");
  wrap.className = "device-group-foreign";
  wrap.innerHTML = genericGroupSectionsHtml(foreign);
  container.parentElement.appendChild(wrap);
  hydrateGenericGroupBody(wrap, foreign);
}

/* A group with no static panel (any user-created group, and Unassigned) gets one
   built on demand. The name is user-supplied via the API, so it is set with
   textContent rather than interpolated into markup. */
function ensureDeviceGroupPanel(group) {
  const existing = document.querySelector(`[data-view-panel="${CSS.escape(group.id)}"]`);
  if (existing) return existing;

  const host = document.querySelector('[data-view-panel="devices"]')?.parentElement;
  if (!host) return null;

  const panel = document.createElement("div");
  panel.className = "view-panel";
  panel.dataset.viewPanel = group.id;

  const header = document.createElement("div");
  header.className = "section-header";
  const title = document.createElement("span");
  title.className = "section-title";
  title.textContent = group.name;
  header.appendChild(title);

  const actions = document.createElement("div");
  actions.className = "section-actions";

  const back = document.createElement("button");
  back.className = "command device-back-btn";
  back.type = "button";
  back.setAttribute("data-back-to-devices", "");
  back.hidden = true;
  back.innerHTML = '<i class="ti ti-arrow-left" aria-hidden="true"></i> Devices';
  actions.appendChild(back);

  if (group.id !== UNASSIGNED_GROUP_ID) {
    const manage = document.createElement("button");
    manage.className = "command";
    manage.type = "button";
    manage.dataset.manageGroup = group.id;
    manage.innerHTML = '<i class="ti ti-list-check" aria-hidden="true"></i> Manage';
    actions.appendChild(manage);

    const edit = document.createElement("button");
    edit.className = "command";
    edit.type = "button";
    edit.dataset.editGroup = group.id;
    edit.innerHTML = '<i class="ti ti-pencil" aria-hidden="true"></i> Edit';
    actions.appendChild(edit);
  }

  header.appendChild(actions);
  panel.appendChild(header);

  const body = document.createElement("div");
  body.className = "device-group-body";
  panel.appendChild(body);

  host.appendChild(panel);
  return panel;
}

function renderDynamicGroupPanel(groupId) {
  const group = findDeviceGroup(groupId);
  if (!group) return;
  const panel = ensureDeviceGroupPanel(group);
  const body = panel?.querySelector(".device-group-body");
  if (!body) return;
  if (!group.devices.length) {
    body.innerHTML = '<div class="empty">No devices in this group yet. Use Manage to add some.</div>';
    return;
  }
  body.innerHTML = genericGroupSectionsHtml(group.devices);
  hydrateGenericGroupBody(body, group.devices);
}

/* The seven built-in panels refresh on every loadDevices() poll because their
   bespoke renderers (renderAmbientLights, renderThermostats, ...) are called
   from it directly. A dynamic group panel has no bespoke renderer -- it only
   ever repaints when activateView navigates to it -- so a user sitting on one
   would see it go stale until they left and came back. Re-render only the
   active dynamic panel, keyed off the group's own builtin flag rather than
   DEVICE_GROUP_VIEWS, so this also covers the synthetic auto:unassigned view. */
function refreshActiveDynamicGroupPanel() {
  const activePanel = viewPanelEls().find((panel) => panel.classList.contains("active"));
  const viewName = activePanel?.dataset.viewPanel;
  if (!viewName) return;
  const group = findDeviceGroup(viewName);
  if (!group || group.builtin) return;
  renderDynamicGroupPanel(viewName);
}

/* PUT /api/device-groups/overrides replaces a device's whole entry, so a toggle
   must resend that device's entries for every other group. Only deviations from
   the group's kind rule are stored, so changing a rule later still flows through
   to devices the user never touched. */
function mergedOverrideFor(deviceKey, groupId, shouldBeMember, ruleSaysMember) {
  const current = (latestDeviceGroupOverrides || {})[deviceKey] || {};
  const include = (current.include || []).filter((id) => id !== groupId);
  const exclude = (current.exclude || []).filter((id) => id !== groupId);

  if (shouldBeMember && !ruleSaysMember) include.push(groupId);
  if (!shouldBeMember && ruleSaysMember) exclude.push(groupId);

  return { include, exclude };
}

let manageDevicesGroupId = null;

function openManageDevicesModal(groupId) {
  const group = findDeviceGroup(groupId);
  if (!group) return;
  manageDevicesGroupId = groupId;
  const title = document.querySelector("#manageDevicesTitle");
  if (title) title.textContent = `Manage Devices — ${group.name}`;
  renderManageDevicesList();
  const modal = document.querySelector("#manageDevicesModal");
  if (modal) modal.hidden = false;
}

function renderManageDevicesList() {
  const list = document.querySelector("#manageDevicesList");
  const group = findDeviceGroup(manageDevicesGroupId);
  if (!list || !group) return;

  const inventory = collectHomeInventory().sort((a, b) =>
    a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind.localeCompare(b.kind)
  );
  const memberKeys = new Set(group.devices.map((d) => d.key));
  const ruleKeys = new Set(
    resolveDeviceGroupMembers({ ...group, kinds: group.kinds }, inventory, {}).map((d) => d.key)
  );

  list.innerHTML = inventory.map((item) => {
    const isMember = memberKeys.has(item.key);
    const byRule = ruleKeys.has(item.key);
    const why = isMember ? (byRule ? "by rule" : "added") : (byRule ? "removed" : "");
    return `
      <div class="assign-device-row">
        <span class="assign-device-icon"><i class="ti ${AREA_KIND_ICONS[item.kind] || "ti-cpu"}"></i></span>
        <span class="assign-device-name">${escapeHtml(item.name)}</span>
        <span class="manage-device-why">${escapeHtml(why)}</span>
        <input class="manage-device-check" type="checkbox"
               data-manage-key="${escapeHtml(item.key)}"
               data-rule-member="${byRule ? "1" : "0"}"
               ${isMember ? "checked" : ""}
               aria-label="Include ${escapeHtml(item.name)} in this group">
      </div>`;
  }).join("");
}

async function toggleManageDevice(checkbox) {
  const deviceKey = checkbox.dataset.manageKey;
  const ruleSaysMember = checkbox.dataset.ruleMember === "1";
  const wantsMember = checkbox.checked;
  const body = mergedOverrideFor(deviceKey, manageDevicesGroupId, wantsMember, ruleSaysMember);
  try {
    await requestJson("/api/device-groups/overrides", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_key: deviceKey, include: body.include, exclude: body.exclude }),
    });
  } catch (error) {
    // The browser has already flipped checkbox.checked natively before this
    // handler runs, so a failed save must put it back or the UI shows a
    // membership change that was never persisted.
    checkbox.checked = !wantsMember;
    console.error(error);
    logActivity("Device group update failed", "warn");
    return;
  }
  await loadDeviceGroups();
  renderManageDevicesList();
  /* The tiles are counted from the overrides just reloaded, so redraw them now
     rather than waiting on loadDevices() - that refetches every device and the
     count would otherwise sit stale for the length of a full poll. */
  renderDevicesOverview();
  loadDevices().catch((error) => console.error(error));
}

const DEVICE_GROUP_ICON_CHOICES = [
  "bulb", "plug", "lamp-2", "droplet", "temperature-celsius", "radar-2",
  "temperature", "device-desktop", "movie", "coffee", "moon", "sun-high",
  "shield-lock", "music", "wifi", "home",
];

let groupModalEditingId = null;
let groupModalIcon = "device-desktop";
let groupModalColor = "slate";

function renderGroupIconPicker() {
  const picker = document.querySelector("#groupIconPicker");
  if (!picker) return;
  picker.innerHTML = DEVICE_GROUP_ICON_CHOICES.map((icon) => `
    <button class="area-icon-option${icon === groupModalIcon ? " selected" : ""}"
            type="button" data-group-icon="${escapeHtml(icon)}">
      <i class="ti ti-${escapeHtml(icon)}"></i>
    </button>`).join("");
}

function renderGroupColorPicker() {
  const picker = document.querySelector("#groupColorPicker");
  if (!picker) return;
  // Rendered from GROUP_COLOR_VARS so the picker cannot offer a colour the API
  // would reject, and cannot drift from the allowlist.
  picker.innerHTML = Object.keys(GROUP_COLOR_VARS).map((name) => `
    <button class="group-color-option${name === groupModalColor ? " selected" : ""}"
            type="button" data-group-color="${escapeHtml(name)}" aria-label="${escapeHtml(name)}"></button>`
  ).join("");
  picker.querySelectorAll("[data-group-color]").forEach((el) => {
    el.style.setProperty("background", GROUP_COLOR_VARS[el.dataset.groupColor]);
  });
}

function openGroupModal(groupId) {
  const group = groupId ? findDeviceGroup(groupId) : null;
  groupModalEditingId = group ? group.id : null;
  groupModalIcon = group ? group.icon : "device-desktop";
  groupModalColor = group ? group.color : "slate";

  const title = document.querySelector("#groupModalTitle");
  if (title) title.textContent = group ? `Edit ${group.name}` : "New Group";
  const input = document.querySelector("#groupNameInput");
  if (input) input.value = group ? group.name : "";
  const save = document.querySelector("#groupSave");
  if (save) save.textContent = group ? "Save" : "Create Group";
  const del = document.querySelector("#groupDelete");
  if (del) del.hidden = !group;
  const error = document.querySelector("#groupModalError");
  if (error) error.hidden = true;

  renderGroupIconPicker();
  renderGroupColorPicker();
  const modal = document.querySelector("#groupModal");
  if (modal) modal.hidden = false;
}

function closeGroupModal() {
  const modal = document.querySelector("#groupModal");
  if (modal) modal.hidden = true;
}

function showGroupModalError(message) {
  const box = document.querySelector("#groupModalError");
  const text = document.querySelector("#groupModalErrorText");
  if (text) text.textContent = message;
  if (box) box.hidden = false;
}

async function submitGroupModal() {
  const name = (document.querySelector("#groupNameInput")?.value || "").trim();
  const payload = { name, icon: groupModalIcon, color: groupModalColor };
  try {
    if (groupModalEditingId) {
      await requestJson(`/api/device-groups/${encodeURIComponent(groupModalEditingId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await requestJson("/api/device-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
  } catch (error) {
    showGroupModalError(apiErrorDetail(error));
    return;
  }
  closeGroupModal();
  await loadDeviceGroups();
  loadDevices().catch((err) => console.error(err));
}

async function deleteGroupFromModal() {
  if (!groupModalEditingId) return;
  const group = findDeviceGroup(groupModalEditingId);
  if (!window.confirm(`Delete the "${group ? group.name : groupModalEditingId}" group? Its devices move to Unassigned.`)) return;
  try {
    await requestJson(`/api/device-groups/${encodeURIComponent(groupModalEditingId)}`, { method: "DELETE" });
  } catch (error) {
    showGroupModalError(apiErrorDetail(error));
    return;
  }
  closeGroupModal();
  await loadDeviceGroups();
  activateView("devices");
  loadDevices().catch((err) => console.error(err));
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#deviceGroupAdd")) { openGroupModal(null); return; }
  const edit = event.target.closest("[data-edit-group]");
  if (edit) { openGroupModal(edit.dataset.editGroup); return; }
  if (event.target.closest("#closeGroupModal") || event.target.closest("#groupCancel")) { closeGroupModal(); return; }
  if (event.target.closest("#groupSave")) { submitGroupModal().catch(console.error); return; }
  if (event.target.closest("#groupDelete")) { deleteGroupFromModal().catch(console.error); return; }

  const icon = event.target.closest("[data-group-icon]");
  if (icon) { groupModalIcon = icon.dataset.groupIcon; renderGroupIconPicker(); return; }
  const color = event.target.closest("[data-group-color]");
  if (color) { groupModalColor = color.dataset.groupColor; renderGroupColorPicker(); }
});

/* Palette names the sidebar and tiles may use. The value that reaches the DOM
   is always chosen from this table, never built from the stored string. */
const GROUP_COLOR_VARS = {
  accent: "var(--accent)", amber: "var(--amber)", cyan: "var(--cyan)",
  green: "var(--green)", indigo: "var(--indigo)", orange: "var(--orange)",
  pink: "var(--pink)", purple: "var(--purple)", red: "var(--red)",
  slate: "var(--slate)", teal: "var(--teal)",
};

const GROUP_ICON_PATTERN = /^[a-z0-9-]{1,32}$/;

function deviceGroupNavPlan(groups) {
  return (groups || []).map((group) => ({
    id: group.id,
    name: group.name,
    icon: GROUP_ICON_PATTERN.test(String(group.icon || "")) ? group.icon : "device-desktop",
    color: GROUP_COLOR_VARS[group.color] || GROUP_COLOR_VARS.slate,
  }));
}

/* ── Device group navigation ── */
async function loadDeviceGroups() {
  const payload = await requestJson("/api/device-groups");
  latestDeviceGroups = payload.groups || [];
  latestDeviceGroupOverrides = payload.overrides || {};
  if (latestDeviceGroups.length) {
    DEVICE_GROUP_VIEWS = latestDeviceGroups.map((group) => group.id);
  }
  syncDeviceGroupNav();
}

/* The seven <li> elements ship in index.html as the seeded baseline, so the
   sidebar is correct before any JavaScript runs. This reconciles them with the
   loaded document rather than rebuilding the list, which keeps that fallback
   intact. Values reach the DOM through the API, never through markup strings. */
function syncDeviceGroupNav() {
  // Device groups are reached from the Devices overview tiles, not the sidebar,
  // so no per-group nav items are rendered. Any left over from an older build
  // are cleared. Panels are still ensured so a tile has somewhere to navigate.
  document.querySelectorAll(".device-group-item").forEach((el) => el.remove());

  resolveDeviceGroups().forEach((group) => {
    if (!document.querySelector(`[data-view-panel="${CSS.escape(group.id)}"]`)) {
      ensureDeviceGroupPanel(group);
    }
  });
}

/* Resolve every device into an area: explicit assignment wins, then a room
   name that exactly matches a defined area. Everything else lands in the
   catch-all "Unassigned" bucket — room names never spawn areas on their own,
   because many devices report their own name as a "room". */
function resolveHomeAreas() {
  const areaById = new Map();
  for (const area of areasDoc.areas) {
    areaById.set(area.id, { ...area, custom: true, devices: [] });
  }
  const idByName = new Map([...areaById.values()].map((a) => [a.name.toLowerCase(), a.id]));
  areaById.set("auto:unassigned", {
    id: "auto:unassigned", name: "Unassigned", icon: "help-hexagon", custom: false, devices: [],
  });

  for (const item of collectHomeInventory()) {
    let areaId = areasDoc.assignments[item.key];
    if (!areaId || !areaById.has(areaId)) {
      const room = String(item.room || "").trim().toLowerCase();
      areaId = idByName.get(room) || "auto:unassigned";
    }
    areaById.get(areaId).devices.push(item);
  }

  const areas = [...areaById.values()];
  const customOrder = new Map(areasDoc.areas.map((a, i) => [a.id, i]));
  let savedOrder = [];
  try { savedOrder = JSON.parse(localStorage.getItem(HOME_AREA_ORDER_KEY) || "[]") || []; } catch {}
  const savedIndex = new Map(savedOrder.map((id, i) => [id, i]));
  areas.sort((a, b) => {
    const sa = savedIndex.has(a.id) ? savedIndex.get(a.id) : Infinity;
    const sb = savedIndex.has(b.id) ? savedIndex.get(b.id) : Infinity;
    if (sa !== sb) return sa - sb;
    if (a.id === "auto:unassigned") return 1;
    if (b.id === "auto:unassigned") return -1;
    return customOrder.get(a.id) - customOrder.get(b.id);
  });
  return areas;
}

function areaTemperature(area) {
  const thermo = area.devices.find((d) => d.kind === "thermostat" && d.data.temperature != null);
  if (thermo) {
    const unit = thermo.data.temperature_unit?.includes("F") ? "°F" : "°C";
    return `${Math.round(Number(thermo.data.temperature))}${unit}`;
  }
  for (const item of area.devices) {
    if (item.kind !== "sensor") continue;
    const reading = item.data.readings.find((r) => String(r.category || "").includes("temperature"));
    if (!reading) continue;
    const value = readingMetricNumber(reading);
    if (Number.isFinite(value)) return `${Math.round(value)}°`;
  }
  return null;
}

function areaCardHtml(area) {
  const switches = area.devices.filter((d) => d.kind === "light" || d.kind === "plug");
  const lightsOn = switches.filter((d) => d.data.is_on === true).length;
  const cameras  = area.devices.filter((d) => d.kind === "camera").length;
  const sensors  = area.devices.filter((d) => d.kind === "sensor").length;
  const ambient  = area.devices.filter((d) => d.kind === "ambient").length;
  const humidifiers = area.devices.filter((d) => d.kind === "humidifier").length;
  const environment = area.devices.filter((d) => d.kind === "environment").length;
  const temp     = areaTemperature(area);
  const lit      = lightsOn > 0;

  const chips = [];
  if (switches.length) {
    chips.push(`<span class="area-chip ${lit ? "lit" : ""}"><i class="ti ti-bulb"></i>${lightsOn}/${switches.length}</span>`);
  }
  if (temp)    chips.push(`<span class="area-chip warm"><i class="ti ti-temperature"></i>${temp}</span>`);
  if (cameras) chips.push(`<span class="area-chip"><i class="ti ti-video"></i>${cameras}</span>`);
  if (sensors) chips.push(`<span class="area-chip"><i class="ti ti-radar-2"></i>${sensors}</span>`);
  if (ambient) chips.push(`<span class="area-chip"><i class="ti ti-lamp-2"></i>${ambient}</span>`);
  if (humidifiers) chips.push(`<span class="area-chip"><i class="ti ti-droplet"></i>${humidifiers}</span>`);
  if (environment) chips.push(`<span class="area-chip"><i class="ti ti-temperature-celsius"></i>${environment}</span>`);

  const count = area.devices.length;
  return `
    <div class="area-card ${lit ? "lit" : ""}" data-area-id="${escapeHtml(area.id)}" role="button" tabindex="0"
         aria-label="Open ${escapeHtml(area.name)}">
      <div class="area-card-glow"></div>
      <div class="area-card-top">
        <span class="area-card-icon"><i class="ti ti-${escapeHtml(area.icon)}"></i></span>
        <button class="area-card-grip" data-area-drag="${escapeHtml(area.id)}" type="button"
          title="Drag to rearrange" aria-label="Drag to rearrange ${escapeHtml(area.name)}"><i class="ti ti-grip-vertical" aria-hidden="true"></i></button>
        ${switches.length ? `
          <button class="area-lights-toggle ${lit ? "on" : ""}" data-area-lights="${escapeHtml(area.id)}"
            type="button" title="${lit ? "Turn off" : "Turn on"} all lights in ${escapeHtml(area.name)}">
            <i class="ti ti-power"></i>
          </button>` : ""}
      </div>
      <div class="area-card-copy">
        <h3 class="area-card-name">${escapeHtml(area.name)}</h3>
        <div class="area-card-sub">${count} device${count === 1 ? "" : "s"}</div>
      </div>
      <div class="area-card-chips">${chips.join("")}</div>
    </div>`;
}

/* ── Pointer-driven reordering ──

   Reordering was built on HTML5 drag-and-drop, which iOS Safari does not
   implement at all: on an iPad the cards and camera tiles simply would not
   move, no matter how carefully you dragged. Pointer events cover mouse,
   touch and pencil through one code path, so this replaces drag-and-drop
   rather than sitting alongside it.

   The drag starts from a handle rather than the whole card, because
   suppressing touch scrolling (touch-action: none) is only acceptable on a
   small part of a card - otherwise a card big enough to fill the screen
   becomes a place the page cannot be scrolled. */
function enablePointerReorder({ container, itemSelector, handleSelector, onReorder }) {
  if (!container) return;

  onDragStart(container, (event) => {
    if (event.button) return;
    const handle = event.target.closest(handleSelector);
    const item = handle && handle.closest(itemSelector);
    if (!item || !container.contains(item)) return;

    event.preventDefault();
    item.classList.add("dragging");

    const onMove = (move) => {
      // elementFromPoint rather than the event target: the pointer is captured
      // by the handle, so every move reports the handle as its target.
      const under = document.elementFromPoint(move.clientX, move.clientY);
      const over = under && under.closest(itemSelector);
      if (!over || over === item || !container.contains(over)) return;

      const rect = over.getBoundingClientRect();
      const itemRect = item.getBoundingClientRect();
      // Compare along whichever axis actually separates the two cards, so the
      // same code works for a multi-column grid and a single-column stack.
      const sameRow =
        Math.abs(rect.top - itemRect.top) < Math.min(rect.height, itemRect.height) / 2;
      const before = sameRow
        ? move.clientX < rect.left + rect.width / 2
        : move.clientY < rect.top + rect.height / 2;
      container.insertBefore(item, before ? over : over.nextSibling);
    };

    trackDrag(event, {
      onMove,
      onEnd: () => {
        item.classList.remove("dragging");
        onReorder(container, item);
      },
    });
  });
}

/* ── Re-rendering without losing the reader's place ──

   The Home panels rebuild themselves by assigning innerHTML. That empties the
   container for an instant, and the browser clamps the scroll offset to the
   briefly shorter page. Below 900px `main` drops to height:auto, so on a
   tablet the document itself is the scroller - and every 60s refresh threw the
   reader back to the top of the Home view.

   Skipping identical markup avoids the churn altogether, which also keeps
   focus and half-typed input alive across a refresh. When the markup really
   did change, the scroll offset is restored by hand. */
const lastRenderedHtml = new WeakMap();

function renderHtml(element, html) {
  if (!element) return false;
  if (lastRenderedHtml.get(element) === html) return false;

  const scroller = document.scrollingElement || document.documentElement;
  const documentTop = scroller.scrollTop;
  // Above 900px the panel scrolls instead of the document, so save both.
  const panel = element.closest(".content");
  const panelTop = panel ? panel.scrollTop : 0;

  element.innerHTML = html;
  lastRenderedHtml.set(element, html);

  if (scroller.scrollTop !== documentTop) scroller.scrollTop = documentTop;
  if (panel && panel.scrollTop !== panelTop) panel.scrollTop = panelTop;
  return true;
}

function renderHomeView() {
  const areaGrid = document.querySelector("#areaGrid");
  if (!areaGrid) return;

  const areas = resolveHomeAreas();
  const shown = areas.filter((a) => a.custom || a.devices.length > 0);
  const totalDevices = areas.reduce((sum, a) => sum + a.devices.length, 0);

  const homeMeta = document.querySelector("#homeMeta");
  if (homeMeta) homeMeta.textContent = `${totalDevices} devices · ${shown.length} area${shown.length === 1 ? "" : "s"}`;

  renderHtml(
    areaGrid,
    shown.map(areaCardHtml).join("") +
      `<button class="area-card area-card-add" id="areaAddCard" type="button">
       <span class="area-add-plus"><i class="ti ti-plus"></i></span>
       <span class="area-add-label">New Area</span>
     </button>`
  );
  layoutAreaGrid();

  renderHomeClimate();
  renderHomeQuickActions();
  loadQuickScripts();
  renderHomeTempSensors();
  renderHomeCamera();
  renderCustomHomeCards();
  const picker = document.querySelector("#homeSensorPicker");
  if (picker && !picker.hidden) renderHomeSensorPicker();

  if (currentAreaId) {
    const area = areas.find((a) => a.id === currentAreaId);
    if (area) {
      renderAreaDetail(area);
      return;
    }
    currentAreaId = null;
  }
  showHomeOverview();
}

/* Fit every area tile inside the Areas card with the whole tile visible.
   Densities carry the real minimum tile size their typography needs; we try
   normal → compact → tiny, and if even tiny cannot fit, zoom the grid down —
   tiles are never clipped, whatever the card size. */
const AREA_DENSITIES = [
  { cls: "",        minW: 106, minH: 104 },
  { cls: "compact", minW: 82,  minH: 84 },
  { cls: "tiny",    minW: 58,  minH: 52 },
];

function layoutAreaGrid() {
  const grid = document.querySelector("#areaGrid");
  if (!grid) return;
  const count = grid.children.length;
  if (!count) return;
  const gap = 8;

  grid.style.zoom = "";
  const width = grid.clientWidth;
  if (width < 30) return;

  if (!homeGridMode()) {
    // Flex fallback (narrow screens): natural rows, normal density.
    const cols = Math.max(1, Math.floor((width + gap) / (118 + gap)));
    grid.style.gridTemplateColumns = `repeat(${Math.min(cols, count)}, minmax(0, 1fr))`;
    grid.style.gridAutoRows = "";
    grid.classList.remove("compact", "tiny", "fitted");
    return;
  }

  const height = grid.clientHeight;
  let chosen = null;
  for (const density of AREA_DENSITIES) {
    let best = null;
    for (let c = 1; c <= count; c++) {
      const rows = Math.ceil(count / c);
      const tileW = (width - gap * (c - 1)) / c;
      const tileH = (height - gap * (rows - 1)) / rows;
      if (tileW < density.minW || tileH < density.minH) continue;
      const score = Math.min(tileW / density.minW, tileH / density.minH);
      if (!best || score > best.score) best = { cols: c, score };
    }
    if (best) { chosen = { cols: best.cols, cls: density.cls, zoom: 1 }; break; }
  }
  if (!chosen) {
    // Nothing fits even at tiny density: zoom the whole grid down to fit.
    const tiny = AREA_DENSITIES[AREA_DENSITIES.length - 1];
    let best = { zoom: 0, cols: 1 };
    for (let c = 1; c <= count; c++) {
      const rows = Math.ceil(count / c);
      const tileW = (width - gap * (c - 1)) / c;
      const tileH = (height - gap * (rows - 1)) / rows;
      const zoom = Math.min(tileW / tiny.minW, tileH / tiny.minH);
      if (zoom > best.zoom) best = { zoom, cols: c };
    }
    chosen = { cols: best.cols, cls: "tiny", zoom: Math.max(0.25, Math.min(1, best.zoom)) };
  }

  if (chosen.zoom !== 1) grid.style.zoom = String(Math.round(chosen.zoom * 100) / 100);
  grid.style.gridTemplateColumns = `repeat(${Math.min(chosen.cols, count)}, minmax(0, 1fr))`;
  grid.style.gridAutoRows = "minmax(0, 1fr)";
  // "tiny" builds on the compact typography and additionally hides rows.
  grid.classList.toggle("compact", chosen.cls === "compact" || chosen.cls === "tiny");
  grid.classList.toggle("tiny", chosen.cls === "tiny");
  grid.classList.add("fitted");
}

/* ── Home dashboard panels (climate + camera) ── */
const HOME_TEMP_SENSORS_KEY = "home_temp_sensors";
const HOME_CAMERA_KEY = "home_camera_id";
/* Set while a motion episode is showing a camera the user did not choose.
   Deliberately not persisted - see the motion watch further down. */
let homeCameraOverride = null;

/* Areas that count as outdoors for the Temperatures card. An area can also
   say so itself with `outdoor: true` in the areas document. */
const OUTDOOR_AREA_IDS = new Set(["front-door", "front-yard", "back-yard"]);

function isOutdoorArea(areaId) {
  if (!areaId) return false;
  const area = (areasDoc.areas || []).find((a) => a.id === areaId);
  return typeof area?.outdoor === "boolean" ? area.outdoor : OUTDOOR_AREA_IDS.has(areaId);
}

/* "Motion sensor and TH front door" -> "Front door motion". The raw names are
   device models, not places; the card has room only for the place. */
function shortSensorName(name) {
  const raw = String(name || "").trim();
  const rules = [
    [/^motion sensor and th\s+(.+)$/i, "$1 motion"],
    [/^motion and th\s+(.+)$/i, "$1 motion"],
    [/^temperature and humidity\s+(.+)$/i, "$1 T&H"],
    [/^motion sensor and illumination$/i, "Motion & light"],
  ];
  for (const [pattern, replacement] of rules) {
    if (pattern.test(raw)) {
      const short = raw.replace(pattern, replacement);
      return short.charAt(0).toUpperCase() + short.slice(1);
    }
  }
  return raw;
}

/* Every temperature source on the dashboard: ecobee remote sensors plus any
   Tuya/HA sensor group that reports a temperature, each once.

   The ecobee's remote sensors are also Home Assistant sensor entities in their
   own right (sensor.8jt7_temperature), so the same sensor used to appear twice
   - once through the thermostat, once as a group. A group whose temperature
   entity is an ecobee sensor's is skipped. */
function homeTempSources() {
  const sources = [];
  const ecobeeEntities = new Set();
  for (const th of latestThermostats) {
    const unit = th.temperature_unit?.includes("F") ? "°F" : "°C";
    for (const sensor of th.sensors || []) {
      if (sensor.temperature == null) continue;
      const entity = /^[a-z0-9_]+$/.test(String(sensor.id || "")) ? `sensor.${sensor.id}` : null;
      if (entity) ecobeeEntities.add(entity);
      sources.push({
        id: `ecobee:${th.id}:${sensor.name}`,
        name: sensor.name,
        temp: Number(sensor.temperature),
        unit,
        humidity: null,
        tempEntity: entity,
        humEntity: null,
        outdoor: false,   /* a thermostat's remote sensors are indoors */
        occupied: sensor.occupied,
      });
    }
  }
  const visibleSensors = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  for (const group of groupSensorDevices(visibleSensors)) {
    const reading = group.readings.find((r) => String(r.category || "").includes("temperature"));
    if (!reading) continue;
    if (reading.entity_id && ecobeeEntities.has(reading.entity_id)) continue;
    const value = readingMetricNumber(reading);
    if (!Number.isFinite(value)) continue;
    const humReading = group.readings.find((r) => String(r.category || "").includes("humidity"));
    const humidity = humReading ? readingMetricNumber(humReading) : NaN;
    const slug = areaSlug(group.name);
    sources.push({
      id: `tuya:${slug}`,
      name: shortSensorName(group.name),
      temp: value,
      unit: "°",
      humidity: Number.isFinite(humidity) ? humidity : null,
      tempEntity: reading.entity_id || null,
      humEntity: Number.isFinite(humidity) ? humReading.entity_id || null : null,
      outdoor: isOutdoorArea(areasDoc.assignments?.[`sensor:${slug}`]),
    });
  }
  return sources;
}

function selectedTempSensorIds(sources) {
  try {
    const raw = localStorage.getItem(HOME_TEMP_SENSORS_KEY);
    if (raw != null) {
      const saved = new Set(JSON.parse(raw));
      return new Set(sources.filter((s) => saved.has(s.id)).map((s) => s.id));
    }
  } catch {}
  return new Set(sources.map((s) => s.id));
}

function renderHomeClimate() {
  const body = document.querySelector("#homeClimateBody");
  if (!body) return;

  /* Dial-only summary: the wheel mirrors the thermostat state; clicking it
     jumps to the Climate view for the full controls. */
  const thermoCards = latestThermostats.map((th) => {
    const ui = getThermoUI(th);
    const current = th.temperature != null ? Math.round(Number(th.temperature)) : "--";
    return `
      <div class="home-dial" data-goto-view="climate" role="button" tabindex="0"
           title="Open Climate for full thermostat controls">
        <div class="home-dial-name">${escapeHtml(th.name)}</div>
        ${buildThermoDial(th.id, ui, current)}
        <div class="home-dial-sub">${escapeHtml(String(th.hvac_mode || "off").toUpperCase())}${th.humidity != null ? ` · ${escapeHtml(String(th.humidity))}% humidity` : ""}</div>
      </div>`;
  }).join("");

  const content = thermoCards || `<div class="home-empty">No thermostat found</div>`;
  renderHtml(body, `<div class="home-fit-clip"><div class="home-fit">${content}</div></div>`);
  fitClimateBody();
}

/* ── Quick actions ──
   Four buttons beside Climate: the two light scenes the Home header used to
   carry, plus Home Assistant scripts. Which scripts exist is asked once per
   page load; a script that is not there is not offered.

   "Good night" is ours rather than Home Assistant's: lights off, and the
   thermostat to its sleep preset if it has one. */
const QUICK_SCRIPT_CANDIDATES = [
  { match: /^script\.movie_mode$/, label: "Movie mode", icon: "ti-movie", a: "#a78bfa", b: "#6d28d9" },
];
let quickScripts = null;

async function loadQuickScripts() {
  if (quickScripts) return;
  try {
    const payload = await requestJson("/api/home-assistant/scripts");
    quickScripts = payload.items || [];
  } catch (error) {
    console.error(error);
    quickScripts = [];
  }
  renderHomeQuickActions();
}

function quickActionButtons() {
  const buttons = [
    { key: "lights-on", label: "All lights on", icon: "ti-bulb", a: "#fbbf24", b: "#d97706", scene: "on" },
    { key: "lights-off", label: "All lights off", icon: "ti-bulb-off", a: "#64748b", b: "#334155", scene: "off" },
  ];
  for (const candidate of QUICK_SCRIPT_CANDIDATES) {
    const script = (quickScripts || []).find((item) => candidate.match.test(item.entity_id));
    if (script) buttons.push({ key: script.entity_id, label: candidate.label, icon: candidate.icon, a: candidate.a, b: candidate.b, script: script.entity_id });
  }
  buttons.push({ key: "good-night", label: "Good night", icon: "ti-moon", a: "#4f8ef7", b: "#1e40af", quick: "good-night" });
  return buttons;
}

function renderHomeQuickActions() {
  const body = document.querySelector("#homeQuickBody");
  if (!body) return;
  renderHtml(body, `<div class="quick-grid">${quickActionButtons().map((button) => `
    <button class="quick-btn" type="button"
      ${button.scene ? `data-light-scene="${button.scene}"` : ""}
      ${button.script ? `data-run-script="${escapeHtml(button.script)}"` : ""}
      ${button.quick ? `data-quick-action="${button.quick}"` : ""}
      title="${escapeHtml(button.label)}">
      <span class="quick-ic" style="--a:${button.a};--b:${button.b}"><i class="ti ${button.icon}" aria-hidden="true"></i></span>
      <span class="quick-label">${escapeHtml(button.label)}</span>
    </button>`).join("")}</div>`);
}

async function runQuickScript(entityId, button) {
  button.disabled = true;
  try {
    await requestJson(`/api/home-assistant/scripts/${encodeURIComponent(entityId)}/run`, { method: "POST" });
    logActivity(`Ran ${entityId.split(".")[1].replace(/_/g, " ")}`);
  } catch (error) {
    console.error(error);
    logActivity("Could not run that script", "error");
  }
  button.disabled = false;
}

/* Lights off, then the thermostat to sleep - each independent, so a thermostat
   that cannot take a preset does not stop the lights going off. */
async function runGoodNight(button) {
  button.disabled = true;
  try {
    document.querySelector('.quick-btn[data-light-scene="off"]')?.click();
    const thermostat = latestThermostats.find((t) => (t.preset_modes || []).some((m) => /sleep/i.test(m)));
    if (thermostat) {
      const preset = thermostat.preset_modes.find((m) => /sleep/i.test(m));
      await updateClimate(thermostat.id, { preset_mode: preset, preset_entity_id: thermostat.preset_entity_id || null });
    }
    logActivity(thermostat ? "Good night: lights off, thermostat to sleep" : "Good night: lights off");
  } catch (error) {
    console.error(error);
    logActivity("Good night did not finish", "error");
  }
  button.disabled = false;
}

document.addEventListener("click", (event) => {
  const scriptBtn = event.target.closest("button[data-run-script]");
  if (scriptBtn) { runQuickScript(scriptBtn.dataset.runScript, scriptBtn); return; }
  const quickBtn = event.target.closest('button[data-quick-action="good-night"]');
  if (quickBtn) runGoodNight(quickBtn);
});

/* ── Temperatures card ──
   The house as one number, the last day as four sparklines, then only the
   sensors worth a look. Sixteen tiles of near-identical numbers said less.

   Indoor is the average of every chosen indoor sensor; outdoor is any sensor in
   an outdoor area (isOutdoorArea). "Worth a look" is an indoor sensor more than
   TEMP_OUTLIER_DEGREES from the indoor average right now. The history is hourly
   averages from Home Assistant's recorder (POST /api/sensors/history), fetched
   at most every five minutes and whenever the chosen sensors change. */
const TEMP_OUTLIER_DEGREES = 1.5;
const TEMP_HISTORY_MS = 5 * 60_000;
let tempHistory = { key: "", at: 0, data: null, pending: false };

const TEMP_SPARKS = [
  { key: "indoor_temperature", name: "Indoor temperature", unit: "°", decimals: 1, color: "#4a9ae0" },
  { key: "outdoor_temperature", name: "Outdoor temperature", unit: "°", decimals: 1, color: "#d9713a" },
  { key: "indoor_humidity", name: "Indoor humidity", unit: "%", decimals: 0, color: "#4a9ae0" },
  { key: "outdoor_humidity", name: "Outdoor humidity", unit: "%", decimals: 0, color: "#d9713a" },
];

const mean = (values) => values.reduce((sum, v) => sum + v, 0) / values.length;

function tempCardModel() {
  const sources = homeTempSources();
  const chosen = selectedTempSensorIds(sources);
  const picked = sources.filter((s) => chosen.has(s.id));
  const indoor = picked.filter((s) => !s.outdoor);
  const outdoor = picked.filter((s) => s.outdoor);
  const humid = (list) => list.map((s) => s.humidity).filter((h) => h != null);
  const indoorAvg = indoor.length ? mean(indoor.map((s) => s.temp)) : null;
  const groups = {
    indoor_temperature: indoor.map((s) => s.tempEntity).filter(Boolean),
    outdoor_temperature: outdoor.map((s) => s.tempEntity).filter(Boolean),
    indoor_humidity: indoor.map((s) => s.humEntity).filter(Boolean),
    outdoor_humidity: outdoor.map((s) => s.humEntity).filter(Boolean),
  };
  return {
    sources, picked, indoor, outdoor, groups,
    now: {
      indoor_temperature: indoorAvg,
      outdoor_temperature: outdoor.length ? mean(outdoor.map((s) => s.temp)) : null,
      indoor_humidity: humid(indoor).length ? mean(humid(indoor)) : null,
      outdoor_humidity: humid(outdoor).length ? mean(humid(outdoor)) : null,
    },
    min: indoor.length ? Math.min(...indoor.map((s) => s.temp)) : null,
    max: indoor.length ? Math.max(...indoor.map((s) => s.temp)) : null,
    outliers: indoorAvg == null ? [] : indoor
      .filter((s) => Math.abs(s.temp - indoorAvg) > TEMP_OUTLIER_DEGREES)
      .sort((a, b) => Math.abs(b.temp - indoorAvg) - Math.abs(a.temp - indoorAvg)),
  };
}

/* The monitor to show on Home: the highest CO2 of those reading now - with
   more than one, the stuffiest room is the one worth seeing. */
const CO2_SHORT = { fresh: "Fresh", ok: "OK", stuffy: "Stuffy", poor: "Poor" };

function homeCo2Reading(sensors = latestEnvironmentSensors) {
  const live = (sensors || []).filter((s) => s.online && s.co2 != null && s.co2_level);
  return live.length ? live.reduce((worst, s) => (s.co2 > worst.co2 ? s : worst)) : null;
}

function formatReading(value, decimals, unit) {
  return value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(decimals)}${unit}`;
}

function renderHomeTempSensors() {
  const body = document.querySelector("#homeTempSensorsBody");
  if (!body) return;
  const model = tempCardModel();
  if (!model.sources.length) {
    renderHtml(body, `<div class="home-empty">No temperature sensors found</div>`);
    return;
  }
  if (!model.picked.length) {
    renderHtml(body, `<div class="home-empty">No sensors selected — use the filter above</div>`);
    return;
  }
  const { now, indoor, outdoor, outliers } = model;
  const indoorAvg = now.indoor_temperature;
  const outdoorWhere = outdoor.length === 1 ? outdoor[0].name : outdoor.length ? `${outdoor.length} sensors` : "no sensor";
  const shown = outliers.slice(0, 3);
  const within = indoor.length - outliers.length;
  const co2 = homeCo2Reading();

  renderHtml(body, `
    <div class="tc">
      <div class="tc-hero${co2 ? " has-co2" : ""}">
        <div class="tc-indoor">
          <div class="tc-big mono">${formatReading(indoorAvg, 1, "°")}</div>
          <div class="tc-cap">Indoor · ${indoor.length} sensor${indoor.length === 1 ? "" : "s"}${indoor.length > 1 ? ` · <b>${formatReading(model.min, 1, "")}–${formatReading(model.max, 1, "°")}</b>` : ""}</div>
        </div>
        <div class="tc-hum">
          <div class="tc-mid mono">${formatReading(now.indoor_humidity, 0, "%")}</div>
          <div class="tc-cap">Humidity</div>
        </div>
        ${co2 ? `<div class="tc-co2" title="${escapeHtml(`${co2.name}: ${co2.co2_level.text}`)}">
          <div class="tc-mid mono">${co2.co2}<span class="tc-unit">ppm</span></div>
          <div class="tc-cap">CO₂ · <span class="co2-level co2-${escapeHtml(co2.co2_level.key)}">${escapeHtml(CO2_SHORT[co2.co2_level.key] || co2.co2_level.text)}</span></div>
        </div>` : ""}
        <div class="tc-out">
          <div class="tc-mid mono">${formatReading(now.outdoor_temperature, 1, "°")}${now.outdoor_humidity != null ? `<span class="tc-out-hum"> · ${formatReading(now.outdoor_humidity, 0, "%")}</span>` : ""}</div>
          <div class="tc-cap">Outdoor · ${escapeHtml(outdoorWhere)}</div>
        </div>
      </div>
      <div class="tc-sparks">${TEMP_SPARKS.map((spark) => `
        <div class="tc-spark" data-spark="${spark.key}">
          <div class="tc-spark-top"><span>${spark.name}</span><b class="mono">${formatReading(now[spark.key], spark.decimals, spark.unit)}</b></div>
          <div class="tc-spark-plot"><svg role="img" aria-label="${spark.name}, last 24 hours"></svg><span class="tc-tip" hidden></span></div>
        </div>`).join("")}</div>
      <div class="tc-look">${indoorAvg == null ? "" : `
        ${shown.length ? `<span class="tc-look-label">Worth a look</span>` : ""}
        ${shown.map((s) => {
          const delta = s.temp - indoorAvg;
          return `<span class="tc-chip">${escapeHtml(s.name)} <b class="mono">${s.temp.toFixed(1)}°</b><span class="mono ${delta > 0 ? "up" : "down"}">${delta > 0 ? "+" : "−"}${Math.abs(delta).toFixed(1)}</span></span>`;
        }).join("")}
        <span class="tc-rest"><i aria-hidden="true">●</i> ${shown.length ? `${within} within ${TEMP_OUTLIER_DEGREES}°` : `All ${indoor.length} within ${TEMP_OUTLIER_DEGREES}° of the average`}</span>`}
      </div>
    </div>`);

  drawTempSparks();
  loadTempHistory(model.groups);
}

async function loadTempHistory(groups) {
  const key = JSON.stringify(groups);
  const fresh = tempHistory.key === key && Date.now() - tempHistory.at < TEMP_HISTORY_MS;
  if (fresh || tempHistory.pending) return;
  tempHistory.pending = true;
  try {
    const data = await requestJson("/api/sensors/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ groups, hours: 24 }),
    });
    tempHistory = { key, at: Date.now(), data: data.status === "ok" ? data : null, pending: false };
  } catch (error) {
    console.error(error);
    // Try again on the next refresh rather than hammering a board that said no.
    tempHistory = { key, at: Date.now(), data: tempHistory.data, pending: false };
  }
  drawTempSparks();
}

/* Monotone cubic (Fritsch–Carlson): smooth, and never overshoots a low or a
   high, so the curve does not invent a colder hour than the data had. */
function smoothSparkPath(points) {
  const n = points.length;
  if (n < 2) return "";
  const dx = [], m = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(points[i + 1][0] - points[i][0]);
    m.push((points[i + 1][1] - points[i][1]) / dx[i]);
  }
  const t = [m[0]];
  for (let i = 1; i < n - 1; i++) t.push(m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2);
  t.push(m[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], h = a * a + b * b;
    if (h > 9) { const k = 3 / Math.sqrt(h); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  let d = `M${points[0][0].toFixed(1)},${points[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const third = dx[i] / 3;
    d += `C${(points[i][0] + third).toFixed(1)},${(points[i][1] + third * t[i]).toFixed(1)} `
      + `${(points[i + 1][0] - third).toFixed(1)},${(points[i + 1][1] - third * t[i + 1]).toFixed(1)} `
      + `${points[i + 1][0].toFixed(1)},${points[i + 1][1].toFixed(1)}`;
  }
  return d;
}

function sparkHourLabel(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : `${String(date.getHours()).padStart(2, "0")}:00`;
}

function drawTempSparks() {
  const data = tempHistory.data;
  for (const spark of TEMP_SPARKS) {
    const el = document.querySelector(`#homeTempSensorsBody [data-spark="${spark.key}"]`);
    const svg = el?.querySelector("svg");
    if (!svg) continue;
    const values = data?.series?.[spark.key] || [];
    const pts = values.map((v, i) => [i, v]).filter(([, v]) => v != null);
    const w = svg.clientWidth, h = svg.clientHeight;
    if (pts.length < 2 || w < 40 || h < 16) {
      svg.innerHTML = data ? `<text x="4" y="${Math.max(12, h / 2)}" font-size="10" fill="currentColor" opacity=".5">No history</text>` : "";
      continue;
    }
    const n = values.length;
    let lo = pts[0], hi = pts[0];
    for (const p of pts) { if (p[1] < lo[1]) lo = p; if (p[1] > hi[1]) hi = p; }
    const pad = (hi[1] - lo[1]) * 0.15 || 1;
    const X = (i) => 4 + (i / (n - 1)) * (w - 8);
    const Y = (v) => 12 + (1 - (v - (lo[1] - pad)) / (hi[1] - lo[1] + 2 * pad)) * (h - 24);
    const xy = pts.map(([i, v]) => [X(i), Y(v)]);
    const line = smoothSparkPath(xy);
    const area = `${line}L${xy[xy.length - 1][0].toFixed(1)},${h}L${xy[0][0].toFixed(1)},${h}Z`;
    const mark = ([i, v], above) => {
      const x = X(i), anchor = x < 36 ? "start" : x > w - 36 ? "end" : "middle";
      return `<circle cx="${x.toFixed(1)}" cy="${Y(v).toFixed(1)}" r="3" fill="${spark.color}" stroke="var(--card)" stroke-width="1.5"/>`
        + `<text x="${x.toFixed(1)}" y="${(Y(v) + (above ? -6 : 13)).toFixed(1)}" text-anchor="${anchor}" class="tc-mark">`
        + `${v.toFixed(spark.decimals)}${spark.unit} ${sparkHourLabel(data.hours[i]).slice(0, 2)}h</text>`;
    };
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.innerHTML = `
      <defs><linearGradient id="tcg-${spark.key}" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="${spark.color}" stop-opacity=".22"/><stop offset="1" stop-color="${spark.color}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${area}" fill="url(#tcg-${spark.key})"/>
      <path d="${line}" fill="none" stroke="${spark.color}" stroke-width="2" stroke-linecap="round"/>
      <line class="tc-cross" y1="0" y2="${h}" style="display:none"/>
      ${lo === hi ? "" : mark(lo, false) + mark(hi, true)}`;

    const tip = el.querySelector(".tc-tip");
    const cross = svg.querySelector(".tc-cross");
    const show = (event) => {
      const rect = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(n - 1, Math.round(((event.clientX - rect.left - 4) / (rect.width - 8)) * (n - 1))));
      if (values[i] == null) return;
      cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.style.display = "";
      tip.textContent = `${sparkHourLabel(data.hours[i])} · ${values[i].toFixed(spark.decimals)}${spark.unit}`;
      tip.style.left = `${Math.max(30, Math.min(rect.width - 30, X(i)))}px`;
      tip.hidden = false;
    };
    svg.onpointermove = show;
    svg.onpointerdown = show;
    svg.onpointerleave = () => { tip.hidden = true; cross.style.display = "none"; };
  }
}

/* Scale a card's fit-wrapped contents to fill it: grow with the width, and
   fit entirely inside the card height. */
const CLIMATE_DESIGN_W = 260;

function fitHomeFitBody(body) {
  const clip = body?.querySelector(".home-fit-clip");
  const inner = clip?.querySelector(".home-fit");
  if (!body || !clip || !inner) return;

  const fixed = homeGridMode();
  inner.style.transform = "none";
  inner.style.marginLeft = "0";
  clip.style.height = "";
  inner.style.width = `${CLIMATE_DESIGN_W}px`;

  const availW = clip.clientWidth;
  const availH = fixed ? clip.clientHeight : 0;
  const naturalH = inner.scrollHeight;
  if (availW < 40 || !naturalH) return;

  let scale = availW / CLIMATE_DESIGN_W;
  if (fixed) scale = Math.min(scale, availH / naturalH);
  if (!inner.querySelector(".thermo-dial-wrap")) scale = Math.min(scale, 1.4); // don't blow up empty states
  scale = Math.max(0.3, Math.min(scale, 2.2));

  inner.style.transform = `scale(${scale})`;
  inner.style.marginLeft = `${Math.max(0, (availW - CLIMATE_DESIGN_W * scale) / 2)}px`;
  if (!fixed) clip.style.height = `${Math.ceil(naturalH * scale)}px`;
}

function fitClimateBody() {
  fitHomeFitBody(document.querySelector("#homeClimateBody"));
}

/* Re-fit whatever scales itself to its card.

   ResizeObserver is Safari 13.1, so on an older tablet the observer below
   never starts and nothing ever re-fits: the ecobee dial kept its old size
   while the card around it grew. Calling this straight from the resize drag
   works everywhere, and is cheap enough to run on every move. */
function refitHomeCards() {
  layoutAreaGrid();
  fitClimateBody();
  drawTempSparks();
}

/* Re-fit areas and climate live while their cards are resized. The sensors
   card scales through CSS container queries instead. */
(function initHomeFitObservers() {
  if (typeof ResizeObserver === "undefined") return;
  const observer = new ResizeObserver(() => {
    layoutAreaGrid();
    fitClimateBody();
    drawTempSparks();
  });
  const areasCard = document.querySelector(".home-areas.home-card");
  const climateCard = document.querySelector("#homeClimatePanel");
  const sensorsCard = document.querySelector("#homeSensorsPanel");
  if (areasCard) observer.observe(areasCard);
  if (climateCard) observer.observe(climateCard);
  if (sensorsCard) observer.observe(sensorsCard);
})();

function renderHomeSensorPicker() {
  const picker = document.querySelector("#homeSensorPicker");
  if (!picker) return;
  const sources = homeTempSources();
  const chosen = selectedTempSensorIds(sources);
  picker.innerHTML = sources.length
    ? sources.map((s) => `
        <label class="home-picker-row">
          <input type="checkbox" data-temp-sensor-id="${escapeHtml(s.id)}" ${chosen.has(s.id) ? "checked" : ""}>
          <span class="home-picker-name">${escapeHtml(s.name)}</span>
          <span class="mono home-picker-temp">${Number(s.temp).toFixed(1)}${s.unit}</span>
        </label>`).join("")
    : `<div class="home-empty">No temperature sensors available</div>`;
}

/* The camera the Home card is showing right now, so a pick from the dropdown
   knows what it is replacing. */
let shownHomeCameraId = null;

function homeCameraList() {
  const tuyaCams = latestTuyaDevices.filter(isTuyaCamera).map(tuyaCameraCard);
  return [...latestCameras, ...tuyaCams];
}

function renderHomeCamera() {
  const body = document.querySelector("#homeCameraBody");
  const select = document.querySelector("#homeCameraSelect");
  if (!body || !select) return;

  const cameras = homeCameraList();
  let savedId = null;
  try { savedId = localStorage.getItem(HOME_CAMERA_KEY); } catch {}
  // A motion episode shows its camera without touching the saved choice, so
  // the card goes back to the one you picked when the episode ends.
  const wantedId = homeCameraOverride ?? savedId;
  const camera = cameras.find((c) => cameraIdFor(c) === wantedId) || cameras[0] || null;

  // Rebuilding the option list resets the dropdown, so leave it alone when
  // the cameras have not changed.
  renderHtml(select, cameras.map((c) => {
    const id = cameraIdFor(c);
    return `<option value="${escapeHtml(id)}"${camera && cameraIdFor(camera) === id ? " selected" : ""}>${escapeHtml(c.name || id)}</option>`;
  }).join(""));
  select.hidden = cameras.length === 0;
  syncMotionWatchToggle();

  // While an episode runs the card is managed node by node rather than
  // re-rendered, so leave it alone here.
  const route = pathEpisodeCameras();
  if (route.length) {
    syncPathSlots(route);
    shownHomeCameraId = activePathCameraId();
    renderHomeCameraExtra();
    return;
  }
  /* No episode wants the card, so it must not still be holding path slots.
     An episode that was released or ended by itself used to leave them in
     place, and with renderHtml's cache describing the older markup the card
     could go on showing two cameras' slots instead of the one chosen. */
  if (body.dataset.pathMode === "1") exitPathMode();

  shownHomeCameraId = camera ? cameraIdFor(camera) : null;
  if (!camera) {
    renderHtml(body, `<div class="home-empty">No cameras found</div>`);
    renderHtml(document.querySelector("#homeCameraExtra"), "");
    return;
  }
  renderHtml(body, homeCameraMarkup(camera));
  renderHomeCameraExtra();
}

/* ── Under the picture: the other cameras, and who was seen last ──────────
   The picture keeps its 16:9 shape, so a card taller than that has room to
   spare. It holds a row of the other cameras (tap to switch) and one line
   naming the camera that saw somebody most recently.

   "Saw somebody" is the NPU detector's own sensor, which the Security zones
   already carry: binary_sensor.<camera>_npu_person, where <camera> is the
   camera's name in lower case with underscores. Those zones bring their age
   with them, so nothing new is fetched for this. */
const CAMERA_STRIP_SIZE = 4;
const CAMERA_STRIP_REFRESH_MS = 30_000;
const CAMERA_RECENT_MINUTES = 10;   /* a green dot means "just now-ish" */

/* Only cameras that look outside. A thumbnail of the living room adds nothing
   to a glance at the doors, and puts the room on a wall panel anyone walking
   past can see. The server decides (a camera's `outdoor:` in the config, or its
   name); the browser only reads the flag. */
function isOutdoorCamera(camera) {
  return camera?.outdoor === true;
}

/* Strip order: the approach route first, in the order somebody walking it
   passes the cameras (camera_paths in devices.local.yaml - garage, frontyard,
   front door), then every other outdoor camera. The back yard is not on the
   route, so it sits at the end, which is where it belongs: it is the one you
   look at on purpose rather than the one that catches an arrival. */
function outdoorCameraOrder(cameras) {
  const route = [];
  for (const path of cameraPathList()) {
    for (const step of path.steps) if (!route.includes(step.camera_id)) route.push(step.camera_id);
  }
  const rank = (camera) => {
    const at = route.indexOf(cameraIdFor(camera));
    return at === -1 ? route.length : at;
  };
  return [...cameras].sort((a, b) => rank(a) - rank(b));
}

function cameraDetectorKey(camera) {
  return String(camera.name || "").trim().toLowerCase().replace(/\s+/g, "_");
}

/* cameraId -> minutes since that camera last saw a person, newest first. */
function cameraSightings() {
  const zones = latestAlarmData?.zones || [];
  const byKey = new Map();
  for (const zone of zones) {
    const match = /^binary_sensor\.(.+)_npu_person$/i.exec(String(zone.id || ""));
    if (!match) continue;
    const minutes = zone.state === "motion" ? 0
      : Number.isFinite(zone.age_seconds) ? zone.age_seconds / 60 : null;
    if (minutes === null) continue;
    byKey.set(match[1].toLowerCase(), minutes);
  }
  return homeCameraList()
    .filter(isOutdoorCamera)
    .map((camera) => ({ camera, minutes: byKey.get(cameraDetectorKey(camera)) }))
    .filter((entry) => entry.minutes != null)
    .sort((a, b) => a.minutes - b.minutes);
}

function agoLabel(minutes) {
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = minutes / 60;
  return hours < 24 ? `${hours.toFixed(1)} h` : `${Math.round(hours / 24)} d`;
}

function renderHomeCameraExtra() {
  const host = document.querySelector("#homeCameraExtra");
  if (!host) return;
  const cameras = outdoorCameraOrder(homeCameraList().filter(isOutdoorCamera));
  if (!cameras.length) { renderHtml(host, ""); return; }

  const shown = shownHomeCameraId;
  const sightings = cameraSightings();
  const minutesById = new Map(sightings.map((s) => [cameraIdFor(s.camera), s.minutes]));
  const others = cameras.filter((camera) => cameraIdFor(camera) !== shown).slice(0, CAMERA_STRIP_SIZE);
  if (!others.length) { renderHtml(host, ""); return; }

  const strip = others.map((camera) => {
    const id = cameraIdFor(camera);
    const minutes = minutesById.get(id);
    const recent = minutes != null && minutes <= CAMERA_RECENT_MINUTES;
    const cached = loadCachedSnapshot(id);   /* a battery camera has no live URL */
    const src = cached || camera.snapshot_url || snapshotUrlFor(camera);
    return `
      <button class="cam-thumb" type="button" data-home-camera-pick="${escapeHtml(id)}"
              title="Show ${escapeHtml(camera.name || id)}">
        <img src="${escapeHtml(src)}" alt="" loading="lazy" data-camera-thumb="${escapeHtml(id)}">
        <span class="cam-thumb-name">${escapeHtml(camera.name || id)}</span>
        ${recent ? '<span class="cam-thumb-dot" title="Someone seen recently"></span>' : ""}
      </button>`;
  }).join("");

  const [first, ...rest] = sightings;
  const line = first
    ? `<span class="cam-last-label">Last person</span>
       <span class="cam-last-pill${first.minutes <= CAMERA_RECENT_MINUTES ? " recent" : ""}">
         ${escapeHtml(first.camera.name || "")} · ${agoLabel(first.minutes)}</span>
       ${rest.length ? `<span class="cam-last-rest">then ${rest.slice(0, 2).map((s) =>
         `${escapeHtml(s.camera.name || "")} ${agoLabel(s.minutes)}`).join(", ")}</span>` : ""}`
    : `<span class="cam-last-label">No outdoor camera has reported a person yet</span>`;

  renderHtml(host, `<div class="cam-strip" style="grid-template-columns:repeat(${others.length}, minmax(0, 1fr))">${strip}</div>`
    + `<div class="cam-last">${line}</div>`);
}

/* Fresh thumbnails without rebuilding the strip: only the src changes, so the
   picture never blinks back to a placeholder. */
function refreshCameraThumbs() {
  const host = document.querySelector("#homeCameraExtra");
  if (!host || !document.querySelector('.view-panel.active[data-view-panel="home"]') || document.hidden) return;
  for (const img of host.querySelectorAll("[data-camera-thumb]")) {
    const camera = latestCameraById.get(img.dataset.cameraThumb);
    if (camera) img.src = camera.snapshot_url || snapshotUrlFor(camera);
  }
}
setInterval(refreshCameraThumbs, CAMERA_STRIP_REFRESH_MS);

document.addEventListener("click", (event) => {
  const pick = event.target.closest("[data-home-camera-pick]");
  if (!pick) return;
  const id = pick.dataset.homeCameraPick;
  const previous = shownHomeCameraId;
  const wasLive = Boolean(previous) && activeCameraIds.has(previous);
  releaseMotionEpisodes();
  if (previous && previous !== id) activeCameraIds.delete(previous);
  if (wasLive) activeCameraIds.add(id);
  try { localStorage.setItem(HOME_CAMERA_KEY, id); } catch {}
  renderHomeCamera();
});

/* The picture and its controls. Shared so a path slot and the ordinary card
   cannot drift into looking like two different things. */
function homeCameraMarkup(camera) {
  const cameraId = cameraIdFor(camera);
  const live = activeCameraIds.has(cameraId);
  return `
    <div class="home-camera-frame" data-home-camera-toggle="${escapeHtml(cameraId)}" role="button" tabindex="0"
         title="${live ? "Tap to stop the live view" : "Tap to start the live view"}">
      ${cameraMedia(camera)}${cameraBatteryBadge(camera)}
      ${live ? "" : `<span class="home-camera-play" aria-hidden="true"><i class="ti ti-player-play-filled"></i></span>`}
    </div>
    <div class="home-camera-meta">
      <span class="home-camera-name">${escapeHtml(camera.name)}${camera.room ? ` · ${escapeHtml(camera.room)}` : ""}</span>
      <span class="home-camera-controls">
        <button class="home-camera-btn" data-home-camera-toggle="${escapeHtml(cameraId)}" type="button"
          title="${live ? "Stop the live view" : "Start the live view"}"
          aria-label="${live ? "Stop the live view" : "Start the live view"}">
          <i class="ti ${live ? "ti-player-stop-filled" : "ti-player-play-filled"}" aria-hidden="true"></i>
        </button>
        <button class="home-camera-btn" data-home-camera-fullscreen="${escapeHtml(cameraId)}" type="button"
          title="Full screen" aria-label="View full screen">
          <i class="ti ti-maximize" aria-hidden="true"></i>
        </button>
      </span>
    </div>`;
}

/* Make the card hold exactly these cameras, adding and removing slots one node
   at a time.

   Deliberately not renderHtml. Replacing the card's innerHTML re-creates every
   <iframe> inside it, and a re-created iframe reloads - so rebuilding the card
   to add the next camera would drop the stream currently on screen and leave a
   black gap at exactly the moment somebody is walking into view. Touching only
   the nodes that changed leaves the others playing, untouched.

   The cost of going around renderHtml is that its cache no longer describes
   this element, so it is cleared on the way in and on the way out. */
function syncPathSlots(cameras) {
  const body = document.querySelector("#homeCameraBody");
  if (!body) return;

  if (body.dataset.pathMode !== "1") {
    body.textContent = "";
    body.dataset.pathMode = "1";
    lastRenderedHtml.delete(body);
  }

  const wantedIds = new Set(cameras.map(cameraIdFor));
  for (const slot of [...body.querySelectorAll("[data-path-slot]")]) {
    if (!wantedIds.has(slot.dataset.pathSlot)) slot.remove();
  }
  for (const camera of cameras) {
    const id = cameraIdFor(camera);
    if (body.querySelector(`[data-path-slot="${CSS.escape(id)}"]`)) continue;
    const slot = document.createElement("div");
    slot.className = "home-camera-slot";
    slot.dataset.pathSlot = id;
    slot.innerHTML = homeCameraMarkup(camera);
    body.appendChild(slot);
  }
  applyPathSlots();
}

function exitPathMode() {
  const body = document.querySelector("#homeCameraBody");
  if (!body) return;
  delete body.dataset.pathMode;
  lastRenderedHtml.delete(body);   // the cache describes markup we replaced
}

/* Which slot is on screen. A class, never a re-render - see the path notes. */
function applyPathSlots() {
  const showing = activePathCameraId();
  for (const slot of document.querySelectorAll("[data-path-slot]")) {
    slot.classList.toggle("showing", slot.dataset.pathSlot === showing);
  }
  /* The picker is markup this function deliberately does not rebuild, so it
     would otherwise keep naming the camera the route started on while the card
     below it shows the one they have walked to. Setting the value is enough. */
  const select = document.querySelector("#homeCameraSelect");
  if (select && showing && select.value !== showing) select.value = showing;
}


/* ── Home camera: watch in place ──

   Tapping the card used to jump to the Cameras view. It now starts and stops
   the stream where it sits, with explicit controls, because the reason to tap
   a camera is almost always to look at it rather than to go somewhere. */
document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-home-camera-toggle]");
  if (!trigger) return;
  event.preventDefault();
  event.stopPropagation();

  const cameraId = trigger.dataset.homeCameraToggle;
  /* Read before releasing: releasing stops the route's streams, which would
     turn a tap on "stop" into a tap on "play". */
  const wasLive = activeCameraIds.has(cameraId);
  /* Whatever the motion watch was doing, the person watching wins. */
  releaseMotionEpisodes();
  if (wasLive) {
    activeCameraIds.delete(cameraId);
  } else {
    activeCameraIds.add(cameraId);
  }
  renderHomeCamera();

  const camera = latestCameraById.get(cameraId);
  if (camera && activeCameraIds.has(cameraId) && camera.battery_powered) {
    captureSnapshotOnce(camera).catch(() => {});
  }
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-home-camera-fullscreen]");
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();

  // A still frame is a poor thing to go full screen with, so start it first.
  const cameraId = button.dataset.homeCameraFullscreen;
  if (!activeCameraIds.has(cameraId)) {
    activeCameraIds.add(cameraId);
    renderHomeCamera();
  }
  expandHomeCamera(cameraId);
});


/* ── Motion watch: the panel shows the door by itself ──────────────────────

   A camera with a `motion_entity` in devices.local.yaml is paired with a
   binary_sensor. When that sensor reads motion the Home card switches to that
   camera and starts playing; `motion_linger_seconds` after it reads clear
   again, the stream stops and the card goes back to the camera you chose.

   Three decisions worth knowing, because each one is a thing that would
   otherwise be wrong at 2am:

   * Every screen decides for itself, and starts out saying no. A dashboard
     left open on a phone would otherwise pull a video stream over cellular
     because a cat walked past the door. The switch lives in the camera card
     and in this browser's localStorage, so the wall panel and the laptop can
     each opt in without agreeing with each other.

   * The saved camera choice is never overwritten. The episode sets an override
     the card prefers, so ending it restores your pick without having to
     remember and write back - a write that would survive a badly timed reload
     and leave the door camera as your permanent choice.

   * A person beats the automation. Touching the stream button or the camera
     dropdown releases the episode: it stops managing the card and will not
     yank the picture away five minutes later. The next rise starts fresh.

   State is per page load. A reload mid-episode re-derives it from the sensor:
   still moving, the camera comes back; already clear, it does not. */

const MOTION_WATCH_DEFAULT_LINGER_MS = 300_000;
/* Home Assistant spells a tripped binary_sensor "on". Zigbee2MQTT occupancy
   has arrived here as "true" and "detected" through other bridges, and a
   sensor that is merely unavailable must never read as motion. */
const MOTION_ON_STATES = new Set(["on", "true", "detected", "open", "motion"]);

/* cameraId -> { released, stopTimer } for every episode currently in flight. */
const motionEpisodes = new Map();

/* Per browser, and off until somebody asks for it. */
const HOME_CAMERA_AUTO_KEY = "home_camera_motion_auto";

function motionWatchEnabled() {
  try {
    return localStorage.getItem(HOME_CAMERA_AUTO_KEY) === "1";
  } catch {
    return false;   /* private window, storage blocked: stay out of the way */
  }
}

function setMotionWatchEnabled(enabled) {
  try {
    localStorage.setItem(HOME_CAMERA_AUTO_KEY, enabled ? "1" : "0");
  } catch {}
  if (enabled) {
    /* Do not make somebody who just asked for this wait for the next refresh
       to find out whether there is already someone on the doorstep. */
    updatePathWatch();
    updateMotionWatch();
  } else {
    stopAllPathEpisodes();
    stopAllMotionEpisodes();
  }
  logActivity(`Auto camera on motion ${enabled ? "enabled" : "disabled"} on this screen`);
}

/* Any camera at all paired with a sensor - otherwise the switch is decoration. */
function anyCameraWatchesMotion() {
  return (latestCameras || []).some((camera) => camera.motion_entity)
      || cameraPathList().length > 0;
}

function syncMotionWatchToggle() {
  const wrap = document.querySelector("#homeCameraAutoWrap");
  const box = document.querySelector("#homeCameraAuto");
  if (!wrap || !box) return;
  wrap.hidden = !anyCameraWatchesMotion();
  box.checked = motionWatchEnabled();
}

function motionSensorIsTripped(entityId, reportedState) {
  /* The server sends the state alongside the camera, because the browser
     cannot always find it: the NPU detector's entities are kept out of the
     device list on purpose, so looking for them there finds nothing. The
     device list is still consulted as a fallback, which keeps a sensor that
     the dashboard already knows about working if Home Assistant is briefly
     unreachable from the server. */
  if (reportedState !== undefined && reportedState !== null) {
    return MOTION_ON_STATES.has(String(reportedState).trim().toLowerCase());
  }
  const device = (latestTuyaDevices || []).find(
    (d) => d.id === entityId || d.entity_id === entityId,
  );
  if (!device || device.online === false) return null;   /* null: no opinion */
  return MOTION_ON_STATES.has(String(device.state ?? "").trim().toLowerCase());
}

function motionLingerMs(camera) {
  const seconds = Number(camera.motion_linger_seconds);
  return Number.isFinite(seconds) && seconds >= 0
    ? seconds * 1000
    : MOTION_WATCH_DEFAULT_LINGER_MS;
}

function openMotionEpisode(camera) {
  const cameraId = cameraIdFor(camera);
  motionEpisodes.set(cameraId, { released: false, stopTimer: null });
  activeCameraIds.add(cameraId);
  homeCameraOverride = cameraId;
  renderHomeCamera();
  logActivity(`Motion at ${camera.room || camera.name} - showing ${camera.name}`);
  if (camera.battery_powered) captureSnapshotOnce(camera).catch(() => {});
}

function closeMotionEpisode(cameraId) {
  const episode = motionEpisodes.get(cameraId);
  if (!episode) return;
  motionEpisodes.delete(cameraId);
  if (episode.released) return;      /* somebody took the card over; leave it */

  activeCameraIds.delete(cameraId);
  if (homeCameraOverride === cameraId) homeCameraOverride = null;
  renderHomeCamera();
  logActivity("Motion clear - camera stopped");
}

/* ── Following somebody up the drive ───────────────────────────────────────

   A camera path is an ordered route - garage, frontyard, front door - where
   each camera has a sensor watching it. When somebody trips the first one the
   card opens every camera on the route at once and shows the one they are at,
   then follows them along it.

   Opening all of them, rather than the current one and the next, is not
   enthusiasm. Moving or re-creating an <iframe> reloads it, so a card that
   swapped which cameras it held would tear down the very stream it had just
   spent three seconds pre-warming. Instead the markup lists every camera on the
   route for the whole episode - identical on every render, so renderHtml leaves
   it alone - and following the person is a class change on slots that are
   already playing. The switch is instant because nothing reconnects.

   Advancing is one-way. The presence hold keeps the garage sensor reading true
   for a minute after somebody has walked out of it, so "the furthest camera
   that has seen them" is the only reading that does not bounce backwards to a
   view they have already left.

   The cost is real - three streams decode on the panel instead of one - so it
   lasts only as long as the episode, and the linger that ends it is the same
   five minutes the single-camera watch uses. */

function cameraPathList() {
  return (latestCameraPaths || []).filter((path) => (path.steps || []).length > 1);
}

function pathCameraIds() {
  const ids = new Set();
  for (const path of cameraPathList()) {
    for (const step of path.steps) ids.add(step.camera_id);
  }
  return ids;
}

/* path name -> { index, stopTimer, released }. Index is the step being shown. */
const pathEpisodes = new Map();

/* The cameras a live episode holds open: the one on screen, and the one they
   are walking towards.

   Not the whole route. Three 1080p WebRTC streams put this Raspberry Pi 4 at
   80% CPU with two Chromium processes pegged at ~85% of a core each, and none
   of them finished connecting - measured on the panel, after trying it. Two is
   enough for the handoff to be instant, because the only stream that has to be
   ready is the next one. */
function pathEpisodeCameras() {
  const cameras = [];
  for (const path of cameraPathList()) {
    const episode = pathEpisodes.get(path.name);
    /* A released episode is still tracked, so the same motion cannot start it
       again, but it no longer owns the card. */
    if (!episode || episode.released) continue;
    for (const offset of [0, 1]) {
      const step = path.steps[episode.index + offset];
      if (!step) continue;
      const camera = latestCameraById.get(step.camera_id);
      if (camera) cameras.push(camera);
    }
  }
  return cameras;
}

/* The camera a live path episode wants on screen, or null when none is. */
function activePathCameraId() {
  for (const path of cameraPathList()) {
    const episode = pathEpisodes.get(path.name);
    if (episode && !episode.released) return path.steps[episode.index]?.camera_id ?? null;
  }
  return null;
}

function openPathEpisode(path, index) {
  pathEpisodes.set(path.name, { index, stopTimer: null, released: false });
  homeCameraOverride = path.steps[index].camera_id;
  applyPathCameras();
  logActivity(`${path.name}: ${path.steps[index].name}`);
}

function advancePathEpisode(path, episode, index) {
  episode.index = index;
  homeCameraOverride = path.steps[index].camera_id;
  /* No full re-render: the slot they are walking into is already open and
     already playing, so this adds the *next* one and shows this one. Rebuilding
     the card here would reload every iframe in it, which is the whole reason
     the slots are managed as nodes rather than as a block of markup. */
  applyPathCameras();
  logActivity(`${path.name}: ${path.steps[index].name}`);
}

function closePathEpisode(pathName) {
  const path = cameraPathList().find((p) => p.name === pathName);
  const episode = pathEpisodes.get(pathName);
  if (!episode || !path) return;
  pathEpisodes.delete(pathName);
  if (episode.released) return;

  for (const step of path.steps) activeCameraIds.delete(step.camera_id);
  if (homeCameraOverride === path.steps[episode.index]?.camera_id) homeCameraOverride = null;
  exitPathMode();
  renderHomeCamera();
  logActivity(`${path.name}: clear`);
}

/* Bring the card in line with what the episode wants open: exactly the current
   camera and the next one, playing, with the current one on screen. */
function applyPathCameras() {
  const wanted = pathEpisodeCameras();
  const wantedIds = new Set(wanted.map(cameraIdFor));

  for (const id of pathCameraIds()) {
    if (!wantedIds.has(id)) activeCameraIds.delete(id);
  }
  for (const id of wantedIds) activeCameraIds.add(id);
  syncPathSlots(wanted);
}

function stopAllPathEpisodes() {
  for (const name of [...pathEpisodes.keys()]) {
    const episode = pathEpisodes.get(name);
    if (episode?.stopTimer) clearTimeout(episode.stopTimer);
    if (episode) episode.stopTimer = null;
    closePathEpisode(name);
  }
}

function updatePathWatch() {
  if (!motionWatchEnabled()) return;

  for (const path of cameraPathList()) {
    const seen = path.steps.map(
      (step) => motionSensorIsTripped(step.motion_entity, step.state) === true);
    const furthest = seen.lastIndexOf(true);
    const episode = pathEpisodes.get(path.name);

    if (!episode) {
      if (furthest >= 0) openPathEpisode(path, furthest);
      continue;
    }
    if (furthest >= 0) {
      if (episode.stopTimer) {
        clearTimeout(episode.stopTimer);
        episode.stopTimer = null;
      }
      /* Forward only: a held sensor behind them must not drag the view back. */
      if (furthest > episode.index && !episode.released) {
        advancePathEpisode(path, episode, furthest);
      }
    } else if (!episode.stopTimer) {
      if (episode.released) {
        pathEpisodes.delete(path.name);
      } else {
        const linger = Number(path.linger_seconds);
        episode.stopTimer = setTimeout(
          () => closePathEpisode(path.name),
          (Number.isFinite(linger) && linger >= 0 ? linger : 300) * 1000,
        );
      }
    }
  }
}

/* Turning the switch off puts the card back now, rather than leaving a stream
   the automation started running until the linger happens to expire. */
function stopAllMotionEpisodes() {
  for (const [cameraId, episode] of [...motionEpisodes]) {
    if (episode.stopTimer) clearTimeout(episode.stopTimer);
    episode.stopTimer = null;
    closeMotionEpisode(cameraId);
  }
}

/* Touching the card hands control back to the person for as long as the
   current motion lasts. Called from the stream button and the dropdown. */
function releaseMotionEpisodes() {
  let released = false;
  let heldPath = false;
  for (const episode of pathEpisodes.values()) {
    if (episode.stopTimer) clearTimeout(episode.stopTimer);
    episode.stopTimer = null;
    if (!episode.released) heldPath = true;
    episode.released = true;
    released = true;
  }
  /* The route's streams go with it, now rather than when the motion clears.
     Keeping them meant the card went on showing the route, and even set the
     dropdown back to it, until the sensor settled - with a detector that kept
     re-triggering, a pick from the dropdown could take minutes to show - and
     the Pi 4 kept decoding two streams the whole time. */
  if (heldPath) {
    for (const id of pathCameraIds()) activeCameraIds.delete(id);
    exitPathMode();
  }
  for (const episode of motionEpisodes.values()) {
    if (episode.stopTimer) clearTimeout(episode.stopTimer);
    episode.stopTimer = null;
    episode.released = true;
    released = true;
  }
  if (released) homeCameraOverride = null;
}

function updateMotionWatch() {
  if (!motionWatchEnabled()) return;

  for (const camera of latestCameras || []) {
    if (!camera.motion_entity) continue;
    // A camera on a path is driven by the path, which knows what comes next.
    // Two rules on one card would fight over which camera is showing.
    if (pathCameraIds().has(cameraIdFor(camera))) continue;
    const tripped = motionSensorIsTripped(camera.motion_entity, camera.motion_state);
    if (tripped === null) continue;          /* sensor missing or offline */

    const cameraId = cameraIdFor(camera);
    const episode = motionEpisodes.get(cameraId);

    if (tripped) {
      if (!episode) {
        openMotionEpisode(camera);
      } else if (episode.stopTimer) {
        /* Motion came back inside the linger window: it never left. */
        clearTimeout(episode.stopTimer);
        episode.stopTimer = null;
      }
    } else if (episode && !episode.stopTimer) {
      if (episode.released) {
        motionEpisodes.delete(cameraId);     /* forget it quietly */
      } else {
        episode.stopTimer = setTimeout(
          () => closeMotionEpisode(cameraId), motionLingerMs(camera),
        );
      }
    }
  }
}

/* ── Full screen camera ──

   Built from scratch and attached to <body>, deliberately.

   Four earlier attempts expanded the card's own markup in place and every one
   showed black on an older iPad: the frame's height came from aspect-ratio,
   then a percentage-padding stand-in, then a vh rule, then inline pixels, and
   whatever failed to resolve collapsed the picture while the backdrop stayed.
   A fresh element inherits none of that - no card rules, no ratio, no
   containing-block chain - and its size is set in pixels on the element
   itself.

   The Fullscreen API is not used at all. Where it is unavailable it silently
   does nothing, where it is present it behaves differently per browser, and
   this overlay fills the viewport on every device without either problem. */
function closeCameraOverlay() {
  document.querySelector("#cameraOverlay")?.remove();
}

function expandHomeCamera(cameraId) {
  const camera = latestCameraById.get(cameraId);
  if (!camera) return;
  closeCameraOverlay();

  const width = window.innerWidth || document.documentElement.clientWidth || 1024;
  const height = Math.round((window.innerHeight || document.documentElement.clientHeight || 768) * 0.82);

  const overlay = document.createElement("div");
  overlay.id = "cameraOverlay";
  overlay.setAttribute(
    "style",
    "position:fixed;top:0;left:0;right:0;bottom:0;width:100%;height:100%;" +
    "z-index:9999;background:#000;text-align:center;"
  );
  overlay.innerHTML =
    `<div id="cameraOverlayMedia">${cameraMedia(camera)}</div>` +
    `<button id="cameraOverlayClose" type="button" style="position:absolute;top:10px;right:10px;` +
    `padding:10px 16px;font-size:15px;border-radius:8px;border:1px solid #555;` +
    `background:rgba(0,0,0,0.6);color:#fff;">Close</button>` +
    `<div style="position:absolute;left:0;right:0;bottom:8px;color:#8a9;font-size:12px;">` +
    `${escapeHtml(camera.name || "")}</div>`;
  document.body.appendChild(overlay);

  // Size the media itself: the container cannot be relied on to hand a height
  // down to something that asks for 100% of it.
  const media = overlay.querySelector(".camera-media");
  if (media) {
    media.setAttribute(
      "style",
      `position:static;display:block;margin:0 auto;width:${width}px;height:${height}px;object-fit:contain;border:0;`
    );
  }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#cameraOverlayClose") || event.target.id === "cameraOverlay") {
    closeCameraOverlay();
  }
});


/* ── Bluetooth: the Bluetooth page, and the speaker line on Music ──
   Every known device is an app tile; tapping it connects or disconnects, and
   the last tile scans for more. */
let latestBluetooth = null;
let bluetoothBusy = null;   /* mac being connected or disconnected, or "scan" */

async function refreshBluetooth() {
  latestBluetooth = await requestJson("/api/bluetooth/devices").catch(() => null);
  renderBluetoothCard();
  renderBluetoothTiles();
  renderMediaApps();
}

function connectedSpeakers() {
  const devices = latestBluetooth?.status === "ok" ? latestBluetooth.devices || [] : [];
  return devices.filter((device) => device.connected);
}

/* Music page: reflects the connected speaker. */
function renderBluetoothCard() {
  const body = document.querySelector("#btDeviceList");
  if (!body) return;
  const connected = connectedSpeakers();
  const status = connected.length
    ? `Connected · ${connected.map((device) => escapeHtml(device.name)).join(", ")}`
    : "No speaker connected";
  body.innerHTML = `
    <div class="home-music-placeholder">
      <i class="ti ti-music" aria-hidden="true"></i>
      <div class="home-music-status">${status}</div>
      <small>Music playback is coming. Connect a speaker under Speakers.</small>
    </div>`;
}

function renderMediaApps() {
  const connected = connectedSpeakers();
  const music = document.querySelector("#mediaMusicSub");
  if (music) music.textContent = connected.length ? `On ${connected[0].name}` : "No speaker connected";
  const bt = document.querySelector("#mediaBluetoothSub");
  if (bt) {
    const known = latestBluetooth?.status === "ok" ? (latestBluetooth.devices || []).length : 0;
    bt.textContent = connected.length ? `${connected.length} connected` : known ? `${known} known` : "Speakers";
  }
  const yt = document.querySelector("#mediaYoutubeSub");
  if (yt) {
    let last = "";
    try { last = localStorage.getItem(YOUTUBE_LAST_KEY) || ""; } catch {}
    yt.textContent = last ? "Resume last link" : "Paste a link";
  }
}

function renderBluetoothTiles() {
  const grid = document.querySelector("#btTiles");
  if (!grid) return;
  const scanTile = `
    <button type="button" class="app-tile" data-bt-scan style="--app-a:#64748b;--app-b:#475569"${bluetoothBusy ? " disabled" : ""}>
      <span class="app-tile-icon"><i class="ti ${bluetoothBusy === "scan" ? "ti-loader-2 spin" : "ti-radar-2"}" aria-hidden="true"></i></span>
      <span class="app-tile-name">${bluetoothBusy === "scan" ? "Scanning…" : "Scan"}</span>
      <span class="app-tile-sub">${bluetoothBusy === "scan" ? "About 8 seconds" : "Find speakers nearby"}</span>
    </button>`;
  const meta = document.querySelector("#btMeta");
  if (!latestBluetooth || latestBluetooth.status !== "ok") {
    grid.innerHTML = `<div class="home-empty">${escapeHtml(latestBluetooth?.message || "Bluetooth status unavailable")}</div>${scanTile}`;
    if (meta) meta.textContent = "Speakers near the board";
    return;
  }
  const devices = latestBluetooth.devices || [];
  if (meta) {
    const on = devices.filter((d) => d.connected).length;
    meta.textContent = devices.length ? `${devices.length} known · ${on} connected` : "No devices known yet";
  }
  grid.innerHTML = devices.map((device) => {
    const isAudio = /audio|headset|headphone|speaker/i.test(String(device.icon || ""));
    const busy = bluetoothBusy === device.mac;
    const action = device.connected ? "disconnect" : "connect";
    const sub = busy ? (device.connected ? "Disconnecting…" : "Connecting…")
      : device.connected ? "Connected · tap to disconnect" : "Tap to connect";
    return `
      <button type="button" class="app-tile${device.connected ? " is-on" : ""}" data-bt-action="${action}"
              data-bt-mac="${escapeHtml(device.mac)}" title="${escapeHtml(device.mac)}"
              style="--app-a:${isAudio ? "#f472b6;--app-b:#a855f7" : "#3b82f6;--app-b:#1d4ed8"}"${bluetoothBusy ? " disabled" : ""}>
        ${device.connected ? '<span class="app-tile-badge" aria-hidden="true"></span>' : ""}
        <span class="app-tile-icon"><i class="ti ${busy ? "ti-loader-2 spin" : isAudio ? "ti-device-speaker" : "ti-bluetooth"}" aria-hidden="true"></i></span>
        <span class="app-tile-name">${escapeHtml(device.name)}</span>
        <span class="app-tile-sub">${sub}</span>
      </button>`;
  }).join("") + scanTile;
}

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-bt-action]");
  if (!btn || bluetoothBusy) return;
  const mac = btn.dataset.btMac;
  const action = btn.dataset.btAction;
  bluetoothBusy = mac;
  renderBluetoothTiles();
  try {
    const result = await requestJson(`/api/bluetooth/devices/${encodeURIComponent(mac)}/${action}`, { method: "POST" });
    logActivity(result.message || `Bluetooth ${action} ${result.status}`, result.status === "ok" ? "normal" : "warn");
  } catch (error) {
    console.error(error);
    logActivity("Bluetooth action failed", "error");
  }
  bluetoothBusy = null;
  await refreshBluetooth();
});

document.addEventListener("click", async (event) => {
  if (!event.target.closest("button[data-bt-scan]") || bluetoothBusy) return;
  bluetoothBusy = "scan";
  renderBluetoothTiles();
  try {
    latestBluetooth = await requestJson("/api/bluetooth/scan", { method: "POST" });
    logActivity("Bluetooth scan finished");
  } catch (error) {
    console.error(error);
  }
  bluetoothBusy = null;
  renderBluetoothCard();
  renderBluetoothTiles();
  renderMediaApps();
});

refreshBluetooth().catch(console.error);

/* ── Custom device cards: user-defined cards with hand-picked devices ── */
const HOME_CUSTOM_CARDS_KEY = "home_custom_cards";
let editingCustomCardId = null;

function loadCustomCards() {
  try { return JSON.parse(localStorage.getItem(HOME_CUSTOM_CARDS_KEY) || "[]") || []; } catch { return []; }
}

function saveCustomCards(cards) {
  try { localStorage.setItem(HOME_CUSTOM_CARDS_KEY, JSON.stringify(cards)); } catch {}
}

/* Lights and plugs render as square tiles inside custom cards: drag the
   tile to rearrange, hit its power button to toggle. */
function customCardTileHtml(item) {
  const icon = AREA_KIND_ICONS[item.kind] || "ti-cpu";
  const on = item.data.is_on === true;
  return `
    <div class="custom-light-tile ${on ? "on" : ""}" draggable="true"
      data-tile-key="${escapeHtml(item.key)}" title="Drag to rearrange">
      <button class="area-lights-toggle tile-power ${on ? "on" : ""}" type="button"
        data-custom-toggle="${escapeHtml(String(item.data.host))}"
        title="Turn ${on ? "off" : "on"} ${escapeHtml(item.name)}">
        <i class="ti ti-power"></i>
      </button>
      <i class="ti ${icon} custom-tile-icon" aria-hidden="true"></i>
      <span class="custom-tile-name">${escapeHtml(item.name)}</span>
    </div>`;
}

/* Sensors, cameras and thermostats render as tiles too, so a custom card is
   one uniform grid rather than tiles stacked above a list of rows.

   An alerting sensor is the whole reason anyone glances at a card like this, so
   it is marked by border and ground rather than by a small word in the corner -
   which is also what makes it readable for colour-blind users and in a
   screenshot. */
/* Pick the icon from what the sensor actually measures, not from the generic
   "sensor" kind - a door, a smoke alarm and a leak detector all looked alike.
   A grouped device carries several readings, so the first non-battery one wins:
   battery is present on almost everything and identifies nothing. */
function customCardSensorIcon(item) {
  if (item.kind !== "sensor") {
    return `<i class="ti ${AREA_KIND_ICONS[item.kind] || "ti-cpu"}" aria-hidden="true"></i>`;
  }
  const readings = item.data.readings || [];
  const identifying = readings.find((r) => !String(r.category || "").includes("battery"));
  return tuyaHaIcon(identifying || readings[0] || {});
}

function customCardSensorTileHtml(item) {
  let value = "";
  let goto = "tuya";
  let alert = false;
  if (item.kind === "thermostat") {
    value = item.data.temperature != null ? `${Math.round(Number(item.data.temperature))}°` : "--";
    goto = "climate";
  } else if (item.kind === "camera") {
    value = "View";
    goto = "cameras";
  } else if (item.kind === "sensor") {
    const reading = item.data.readings.find((r) => String(r.category || "").includes("temperature"));
    const num = reading ? readingMetricNumber(reading) : NaN;
    alert = item.data.readings.some(isAlertDetected);
    value = Number.isFinite(num) ? `${Math.round(num)}°` : (alert ? "Alert" : "OK");
  }
  return `
    <div class="custom-sensor-tile${alert ? " alert" : ""}" data-goto-view="${goto}"
         role="button" tabindex="0" title="${escapeHtml(item.name)} — open the related view">
      <span class="custom-sensor-icon">${customCardSensorIcon(item)}</span>
      <span class="custom-sensor-value mono">${escapeHtml(String(value))}</span>
      <span class="custom-sensor-name">${escapeHtml(item.name)}</span>
    </div>`;
}

function renderCustomHomeCards() {
  const grid = document.querySelector("#homeCardGrid");
  if (!grid) return;
  const cards = loadCustomCards();
  const inventoryByKey = new Map(collectHomeInventory().map((item) => [item.key, item]));

  for (const el of grid.querySelectorAll(".home-custom-card")) {
    const id = el.dataset.homeCard.slice("custom:".length);
    if (!cards.some((c) => c.id === id)) el.remove();
  }

  for (const card of cards) {
    let el = grid.querySelector(`.home-card[data-home-card="custom:${CSS.escape(card.id)}"]`);
    if (!el) {
      el = document.createElement("div");
      el.className = "panel home-panel home-card home-custom-card";
      el.dataset.homeCard = `custom:${card.id}`;
      el.innerHTML = `
        <div class="home-panel-head">
          <span class="home-card-grip" title="Drag to rearrange"><i class="ti ti-grip-vertical"></i></span>
          <span class="panel-title"><i class="ti ti-layout-list"></i> <span data-custom-name></span></span>
          <button class="home-gear-btn" data-custom-edit="${escapeHtml(card.id)}" type="button" title="Edit name or linked devices">
            <i class="ti ti-pencil"></i>
          </button>
        </div>
        <div class="home-custom-body" data-custom-body></div>
        <span class="home-card-resize" title="Drag to resize · double-click to reset"><i class="ti ti-arrow-down-right"></i></span>`;
      grid.appendChild(el);
    }
    el.querySelector("[data-custom-name]").textContent = card.name;
    const items = (card.devices || [])
      .map((key) => inventoryByKey.get(key))
      .filter(Boolean);
    /* Lights and plugs keep the order the card was configured in, because they
       are drag-reorderable and that order is persisted (see saveCustomCardOrder,
       which writes them ahead of everything else). Sensors cannot be dragged, so
       leaving them in pick order gives no control and no predictability -
       alphabetical does. */
    const controls = items.filter((item) => item.kind === "light" || item.kind === "plug");
    const readouts = items
      .filter((item) => item.kind !== "light" && item.kind !== "plug")
      .sort((a, b) => String(a.name).localeCompare(String(b.name)));
    const tiles = controls.map(customCardTileHtml)
      .concat(readouts.map(customCardSensorTileHtml))
      .join("");
    renderHtml(
      el.querySelector("[data-custom-body]"),
      tiles
        ? `<div class="custom-tile-grid">${tiles}</div>`
        : `<div class="home-empty">No devices linked — click the pencil to pick some.</div>`
    );
  }
  applyHomeCardLayout();
}

function openCustomCardModal(cardId = null) {
  const modal = document.querySelector("#customCardModal");
  if (!modal) return;
  editingCustomCardId = cardId;
  const card = loadCustomCards().find((c) => c.id === cardId) || null;
  const title = document.querySelector("#customCardModalTitle");
  if (title) title.textContent = card ? "Edit Card" : "New Card";
  const nameInput = document.querySelector("#customCardNameInput");
  if (nameInput) nameInput.value = card ? card.name : "";
  const deleteBtn = document.querySelector("#customCardDelete");
  if (deleteBtn) deleteBtn.hidden = !card;
  const errorBox = document.querySelector("#customCardError");
  if (errorBox) errorBox.hidden = true;

  const chosen = new Set(card?.devices || []);
  const list = document.querySelector("#customCardDeviceList");
  if (list) {
    const inventory = collectHomeInventory().sort((a, b) =>
      a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind.localeCompare(b.kind)
    );
    list.innerHTML = inventory.map((item) => `
      <label class="assign-device-row">
        <input type="checkbox" data-custom-device-key="${escapeHtml(item.key)}" ${chosen.has(item.key) ? "checked" : ""}>
        <span class="assign-device-icon"><i class="ti ${AREA_KIND_ICONS[item.kind] || "ti-cpu"}"></i></span>
        <span class="assign-device-name">${escapeHtml(item.name)}</span>
      </label>`).join("");
  }
  modal.hidden = false;
  nameInput?.focus();
}

function closeCustomCardModal() {
  const modal = document.querySelector("#customCardModal");
  if (modal) modal.hidden = true;
  editingCustomCardId = null;
}

function saveCustomCardFromModal() {
  const name = document.querySelector("#customCardNameInput")?.value.trim() || "";
  if (!name) {
    const errorBox = document.querySelector("#customCardError");
    const errorText = document.querySelector("#customCardErrorText");
    if (errorText) errorText.textContent = "Card name cannot be empty";
    if (errorBox) errorBox.hidden = false;
    return;
  }
  const devices = [...document.querySelectorAll("#customCardDeviceList input[data-custom-device-key]:checked")]
    .map((box) => box.dataset.customDeviceKey);
  const cards = loadCustomCards();
  if (editingCustomCardId) {
    const card = cards.find((c) => c.id === editingCustomCardId);
    if (card) { card.name = name; card.devices = devices; }
  } else {
    cards.push({ id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), name, devices });
  }
  saveCustomCards(cards);
  closeCustomCardModal();
  renderCustomHomeCards();
  logActivity(`Card "${name}" saved`);
}

function deleteCustomCardFromModal() {
  if (!editingCustomCardId) return;
  const cards = loadCustomCards();
  const card = cards.find((c) => c.id === editingCustomCardId);
  if (!card) { closeCustomCardModal(); return; }
  if (!window.confirm(`Delete card "${card.name}"?`)) return;
  saveCustomCards(cards.filter((c) => c.id !== editingCustomCardId));
  // Drop its saved grid cell too.
  const layout = loadHomeLayout();
  delete layout[`custom:${editingCustomCardId}`];
  saveHomeLayout(layout);
  logActivity(`Card "${card.name}" deleted`);
  closeCustomCardModal();
  renderCustomHomeCards();
}

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-custom-edit]");
  if (!btn) return;
  openCustomCardModal(btn.dataset.customEdit);
});

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-custom-toggle]");
  if (!btn) return;
  event.preventDefault();
  event.stopPropagation();
  const host = String(btn.dataset.customToggle);
  const tile = btn.closest(".custom-light-tile");
  const command = btn.classList.contains("on") ? "off" : "on";
  btn.classList.toggle("on");
  tile?.classList.toggle("on");
  btn.disabled = true;
  try {
    if (host.startsWith("matter:")) {
      await requestJson(`/api/matter/devices/${host.slice(7)}/commands/${command}`, { method: "POST" });
    } else {
      await requestJson(`/api/devices/${host}/commands/${command}`, { method: "POST" });
    }
    logActivity(`${command === "on" ? "Turned on" : "Turned off"} device from card`);
    patchLocalDeviceState(host, { is_on: command === "on" });
    await refreshDeviceSource(host);
  } catch (error) {
    console.error(error);
    btn.classList.toggle("on");
    tile?.classList.toggle("on");
  } finally {
    btn.disabled = false;
  }
});

/* ── Home card layout: free grid placement ─────────────────────────────
   Cards live on a 12-column grid with fixed row height. Every card keeps
   its own cell {x, y, w, h}; moving or resizing one card never shifts the
   others, so any arrangement — including stacked columns — sticks. */
const HOME_CARD_LAYOUT_KEY = "home_card_layout";
/* Bump when DEFAULT_HOME_LAYOUT changes shape. A browser that stored cells for
   the built-in cards under an older table drops them on the next load and picks
   the new defaults up; anything the user added themselves is kept, because a
   custom card has no default to fall back to.

   Without this a stored cell outlives every future change: the wall panel had
   Climate frozen at y4/h8 from an older table, so when Weather shrank to two
   rows the freed row just sat there as a gap. */
const HOME_CARD_LAYOUT_VERSION_KEY = "home_card_layout_version";
const HOME_CARD_LAYOUT_VERSION = "2026-09-17-no-home-heading";
const HOME_GRID_COLS = 12;
/* Fallback row height, used only where the grid has no measurable height yet
   (first paint) or is stacked into a flex column on a phone. Above 1101px the
   CSS divides the real height into HOME_GRID_ROWS shares instead - see
   "Fit the Home view to the screen" in styles.css. */
const HOME_GRID_ROW = 40;
const HOME_GRID_ROWS = 20;
const HOME_GRID_GAP = 16;

/* Three columns of four on the grid:

     Weather        Camera    Areas
     Climate        Alarm
     Temperatures

   Alarm sits directly under Camera, matching the phone order in index.html:
   a camera view and "is anything open" answer the same question, so they are
   read together.

   Every column totals exactly HOME_GRID_ROWS, and that is the whole point:
   with 1fr rows the three columns then end flush with each other and with the
   bottom of the screen, instead of being tuned to agree. Change a height here
   and change another in the same column to match, or that column stops lining
   up - the totals are the invariant, not the individual numbers.

     left    6 + 5 + 9  = 20     Weather, (Climate | Quick actions), Temperatures
     middle 11 + 9      = 20     Camera, Alarm
     right  20          = 20     Areas

   Two rows of that are load-bearing across columns, not just within one.
   Weather plus Climate spans rows 1-11, which is exactly Camera, so the left
   and middle columns break at the same place; Temperatures and Alarm then both
   run 12-20 and line up across the view. Move one and its opposite number has
   to move with it.

   Weather is six rows since 2026-09-17, when it took over the clock and the
   date and grew a 7-day strip: about 260px on the wall panel, comfortably
   what the clock, today and the week need. The rows came from Climate (the ecobee dial scales itself) and
   Temperatures (the sensor grid scrolls). It still scales with its own height
   through a container query - see "#homeWeatherPanel" in styles.css - dropping
   the week first and the date second on a short window.

   The previous table totalled 20 / 15 / 12, which on the 1920x1080 wall panel
   meant the left column ran 220px past the bottom of the screen while Areas
   stopped 228px short of it. Camera took most of the freed space because it is
   the card that uses it; Weather gave up two rows it was not using.

   Only applies to a browser with no saved layout - an existing one is left
   alone, and Reset Layout is what adopts this. A browser that already has a
   layout still gets a card it has never seen, because cardLayoutOf() falls
   back to this table for any card the saved layout has no entry for; what it
   will not do is move a card the user has already placed. */
const DEFAULT_HOME_LAYOUT = {
  weather:     { x: 1, y: 1,  w: 4, h: 6 },
  /* Climate keeps its dial and its height and gives up half its width, so the
     buttons pressed most often sit beside it rather than a scroll away. */
  climate:     { x: 1, y: 7,  w: 2, h: 5 },
  quick:       { x: 3, y: 7,  w: 2, h: 5 },
  tempsensors: { x: 1, y: 12, w: 4, h: 9 },
  camera:      { x: 5, y: 1,  w: 4, h: 11 },
  alarm:       { x: 5, y: 12, w: 4, h: 9 },
  areas:       { x: 9, y: 1,  w: 4, h: 20 },
};

function loadHomeLayout() {
  let stored;
  try { stored = JSON.parse(localStorage.getItem(HOME_CARD_LAYOUT_KEY) || "{}") || {}; } catch { return {}; }

  let version = null;
  try { version = localStorage.getItem(HOME_CARD_LAYOUT_VERSION_KEY); } catch {}
  if (version === HOME_CARD_LAYOUT_VERSION) return stored;

  // Stale table: keep only cards this file has no opinion about.
  const kept = {};
  for (const [id, cell] of Object.entries(stored)) {
    if (!DEFAULT_HOME_LAYOUT[id]) kept[id] = cell;
  }
  try {
    localStorage.setItem(HOME_CARD_LAYOUT_KEY, JSON.stringify(kept));
    localStorage.setItem(HOME_CARD_LAYOUT_VERSION_KEY, HOME_CARD_LAYOUT_VERSION);
  } catch {}
  return kept;
}

function saveHomeLayout(layout) {
  try {
    localStorage.setItem(HOME_CARD_LAYOUT_KEY, JSON.stringify(layout));
    localStorage.setItem(HOME_CARD_LAYOUT_VERSION_KEY, HOME_CARD_LAYOUT_VERSION);
  } catch {}
}

/* Below 1100px the layout falls back to a flex column (see CSS); fit logic
   switches to natural heights there. */
function homeGridMode() {
  const grid = document.querySelector("#homeCardGrid");
  return !!grid && getComputedStyle(grid).display === "grid";
}

/* Whether cards can be dragged and resized, which is a different question from
   whether the grid has fixed heights. On a small screen the layout is placed by
   CSS rather than by the saved cells, so a drag would write an inline style the
   stylesheet then overrides - the card would simply refuse to move, which reads
   as broken rather than as disabled.

   CSS owns the answer (--home-arrangeable) so there is one place that decides,
   the same way homeGridMode() reads the computed display instead of repeating
   the breakpoint in JS. */
function homeCardsArrangeable() {
  const grid = document.querySelector("#homeCardGrid");
  if (!grid || !homeGridMode()) return false;
  return getComputedStyle(grid).getPropertyValue("--home-arrangeable").trim() !== "0";
}

function setCardCell(card, lay) {
  card.style.gridColumn = `${lay.x} / span ${lay.w}`;
  card.style.gridRow = `${lay.y} / span ${lay.h}`;
}

/* Read the cell a card is actually occupying, from the inline style
   applyHomeCardLayout wrote. */
function readCardCell(card) {
  const column = /^(\d+) \/ span (\d+)$/.exec(card.style.gridColumn || "");
  const row = /^(\d+) \/ span (\d+)$/.exec(card.style.gridRow || "");
  if (!column || !row) return null;
  return { x: +column[1], w: +column[2], y: +row[1], h: +row[2] };
}

function cardLayoutOf(card) {
  const id = card.dataset.homeCard;
  const stored = loadHomeLayout()[id] || DEFAULT_HOME_LAYOUT[id];
  if (stored) return { ...stored };
  // Falling back to {1,1} teleported an unplaced card to the top the instant
  // it was touched, before the finger had moved - which is what made the
  // temperatures card impossible to drag. Start from where it actually is.
  return readCardCell(card) || { x: 1, y: 1, w: 4, h: 6 };
}

function persistCardLayout(card, lay) {
  const layout = loadHomeLayout();
  layout[card.dataset.homeCard] = lay;
  saveHomeLayout(layout);
}

/* ── Which Home cards are shown ──

   Hiding is deliberately separate from layout: a hidden card keeps its size,
   position and linked devices, so showing it again puts it back where it was
   rather than dumping it at the bottom. */
const HOME_HIDDEN_CARDS_KEY = "home_hidden_cards";

const HOME_CARD_LABELS = {
  quick: "Quick actions",
  weather: "Weather",
  camera: "Camera",
  climate: "Climate",
  alarm: "Security",
  areas: "Areas",
};

function loadHiddenHomeCards() {
  try {
    return new Set(JSON.parse(localStorage.getItem(HOME_HIDDEN_CARDS_KEY) || "[]") || []);
  } catch {
    return new Set();
  }
}

function saveHiddenHomeCards(hidden) {
  try { localStorage.setItem(HOME_HIDDEN_CARDS_KEY, JSON.stringify([...hidden])); } catch {}
}

/* Hiding frees the card's cell; showing puts the card back at the bottom.

   Keeping the stored cell would leave a hole in the grid that nothing could
   reclaim without dragging every other card around it, so the slot is given
   up on hide. Coming back at the bottom is the same treatment a newly created
   card gets, and it is somewhere the card can be seen and then moved. */
function releaseHomeCardCell(id) {
  const layout = loadHomeLayout();
  delete layout[id];
  saveHomeLayout(layout);
}

function placeHomeCardAtBottom(id) {
  const layout = loadHomeLayout();
  const hidden = loadHiddenHomeCards();
  const size = layout[id] || DEFAULT_HOME_LAYOUT[id] || { w: 4, h: 6 };

  // Only cards actually on screen reserve space; a hidden one holds nothing.
  const occupied = [...new Set([...Object.keys(DEFAULT_HOME_LAYOUT), ...Object.keys(layout)])]
    .filter((key) => key !== id && !hidden.has(key))
    .map((key) => layout[key] || DEFAULT_HOME_LAYOUT[key])
    .filter(Boolean);

  const bottom = occupied.reduce((max, cell) => Math.max(max, cell.y + cell.h), 1);
  // The grid is a fixed HOME_GRID_ROWS tall, so "the bottom" has a limit now.
  const y = Math.min(bottom, Math.max(1, HOME_GRID_ROWS - size.h + 1));
  layout[id] = { x: 1, y, w: size.w, h: size.h };
  saveHomeLayout(layout);
}

function homeCardLabel(card) {
  const id = card.dataset.homeCard || "";
  if (HOME_CARD_LABELS[id]) return HOME_CARD_LABELS[id];
  const title = card.querySelector(".panel-title");
  return (title ? title.textContent : "").trim() || id;
}

function renderHomeCardsModal() {
  const list = document.querySelector("#homeCardsList");
  const grid = document.querySelector("#homeCardGrid");
  if (!list || !grid) return;
  const hidden = loadHiddenHomeCards();
  const cards = [...grid.querySelectorAll(".home-card")];
  if (!cards.length) {
    list.innerHTML = `<div class="home-empty">No cards yet.</div>`;
    return;
  }
  list.innerHTML = cards.map((card) => {
    const id = card.dataset.homeCard || "";
    const shown = !hidden.has(id);
    return `
      <label class="net-row home-card-toggle">
        <span class="net-row-icon"><i class="ti ${shown ? "ti-eye" : "ti-eye-off"}"></i></span>
        <span class="net-row-name">${escapeHtml(homeCardLabel(card))}</span>
        <input type="checkbox" data-home-card-visible="${escapeHtml(id)}" ${shown ? "checked" : ""} />
      </label>`;
  }).join("");
}

function resetHomeLayout() {
  try { localStorage.removeItem(HOME_CARD_LAYOUT_KEY); } catch {}
  try { localStorage.removeItem(HOME_HIDDEN_CARDS_KEY); } catch {}
  applyHomeCardLayout();
  logActivity("Home layout reset to default");
}

(function initHomeCardControls() {
  const modal = document.querySelector("#homeCardsModal");
  const closeModal = () => { if (modal) modal.hidden = true; };

  document.querySelector("#homeCardsButton")?.addEventListener("click", () => {
    renderHomeCardsModal();
    if (modal) modal.hidden = false;
  });
  document.querySelector("#closeHomeCardsModal")?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });

  document.querySelector("#homeCardsShowAll")?.addEventListener("click", () => {
    // Unhide one at a time: placeHomeCardAtBottom ignores cards still marked
    // hidden, so revealing them all first would stack them on the same row.
    const hidden = loadHiddenHomeCards();
    for (const id of [...hidden]) {
      hidden.delete(id);
      saveHiddenHomeCards(hidden);
      placeHomeCardAtBottom(id);
    }
    applyHomeCardLayout();
    renderHomeCardsModal();
    logActivity("All Home cards shown");
  });

  document.addEventListener("change", (event) => {
    const box = event.target.closest("input[data-home-card-visible]");
    if (!box) return;
    const id = box.dataset.homeCardVisible;
    const hidden = loadHiddenHomeCards();
    if (box.checked) {
      hidden.delete(id);
      saveHiddenHomeCards(hidden);
      placeHomeCardAtBottom(id);
    } else {
      hidden.add(id);
      saveHiddenHomeCards(hidden);
      releaseHomeCardCell(id);
    }
    applyHomeCardLayout();
    renderHomeCardsModal();
  });

  document.querySelector("#homeResetLayout")?.addEventListener("click", () => {
    resetHomeLayout();
  });
})();

/* Two cards on the same cells do not error or reflow -- CSS grid stacks them,
   and the one painted second simply hides the other. That is how the Security
   card went missing on a tablet: its default cell is the one Temperatures used
   to hold, so any browser with a *saved* Temperatures position (a resize writes
   x and y unchanged) put the new card underneath it.

   So placement resolves collisions. A card the user has positioned keeps
   exactly where they put it; a card falling back to a default moves down until
   it is clear. Only the second kind can move, because the first kind is
   somebody's decision. */
function cellsOf(lay) {
  const cells = [];
  for (let col = lay.x; col < lay.x + lay.w; col++) {
    for (let row = lay.y; row < lay.y + lay.h; row++) cells.push(`${col},${row}`);
  }
  return cells;
}

function firstFreeBelow(lay, taken) {
  const found = { ...lay };
  // Bounded: the grid has no bottom, but a runaway loop would hang the page.
  for (let attempt = 0; attempt < 200; attempt++) {
    if (!cellsOf(found).some((cell) => taken.has(cell))) return found;
    found.y += 1;
  }
  return found;
}

function applyHomeCardLayout() {
  const grid = document.querySelector("#homeCardGrid");
  if (!grid) return;
  const layout = loadHomeLayout();
  const hidden = loadHiddenHomeCards();
  let changed = false;

  const visible = [];
  for (const card of grid.querySelectorAll(".home-card")) {
    const id = card.dataset.homeCard;
    // A hidden card keeps its stored layout; it is only taken off the screen,
    // and it reserves no cells, so what is left can close over the hole.
    card.hidden = hidden.has(id);
    if (card.hidden) continue;
    visible.push(card);
  }
  const taken = new Set();

  // Pass one: positions the user chose. These are never moved.
  for (const card of visible) {
    const lay = layout[card.dataset.homeCard];
    if (!lay) continue;
    setCardCell(card, lay);
    cellsOf(lay).forEach((cell) => taken.add(cell));
  }

  // Pass two: everything else, in DOM order so the result is stable.
  for (const card of visible) {
    const id = card.dataset.homeCard;
    if (layout[id]) continue;

    let lay = DEFAULT_HOME_LAYOUT[id];
    if (!lay) {
      // New (custom) card: park it below everything currently placed.
      const placed = Object.entries(DEFAULT_HOME_LAYOUT)
        .filter(([key]) => !layout[key])
        .map(([, l]) => l)
        .concat(Object.values(layout));
      const bottom = placed.reduce((max, l) => Math.max(max, l.y + l.h), 1);
      lay = { x: 1, y: bottom, w: 4, h: 6 };
    }

    const resolved = firstFreeBelow(lay, taken);
    setCardCell(card, resolved);
    cellsOf(resolved).forEach((cell) => taken.add(cell));

    /* Persist only when the card actually had to move, or was custom. Writing
       every default back would freeze this browser's layout against future
       changes to DEFAULT_HOME_LAYOUT, which Reset Layout is supposed to adopt.

       A cell remembered here still only survives within one layout version -
       HOME_CARD_LAYOUT_VERSION drops it when the defaults change shape, which
       is what stops a position from outliving the table it was resolved
       against. */
    if (!DEFAULT_HOME_LAYOUT[id] || resolved.y !== lay.y) {
      layout[id] = resolved;
      changed = true;
    }
  }
  if (changed) saveHomeLayout(layout);
}

/* Rows are a share of the screen now, so drag and resize cannot assume 40px:
   on this panel a row is nearer 29px, and a card would jump about a third
   further than the pointer. Measure the row the grid actually drew. */
function homeGridPitch(grid) {
  const cellW = (grid.clientWidth - HOME_GRID_GAP * (HOME_GRID_COLS - 1)) / HOME_GRID_COLS;
  const usableH = grid.clientHeight - HOME_GRID_GAP * (HOME_GRID_ROWS - 1);
  const rowH = usableH > 0 ? usableH / HOME_GRID_ROWS : 0;
  // Before first layout, or stacked on a phone, fall back to the fixed row.
  const pitchY = rowH > 1 ? rowH + HOME_GRID_GAP : HOME_GRID_ROW + HOME_GRID_GAP;
  return { pitchX: cellW + HOME_GRID_GAP, pitchY };
}


(function initHomeCardLayout() {
  const grid = document.querySelector("#homeCardGrid");
  if (!grid) return;

  renderCustomHomeCards();
  applyHomeCardLayout();

  /* Move: pointer-drag from the header grip; only this card changes cell. */
  onDragStart(grid, (event) => {
    const grip = event.target.closest(".home-card-grip");
    const card = grip?.closest(".home-card");
    if (!card || !homeCardsArrangeable()) return;
    event.preventDefault();
    const start = dragPoint(event);
    const { pitchX, pitchY } = homeGridPitch(grid);
    if (!pitchX || !pitchY) return;
    const startX = start.clientX;
    const startY = start.clientY;
    const lay = cardLayoutOf(card);
    // Where the card started, so movement can be expressed as a delta.
    const originX = lay.x;
    const originY = lay.y;
    card.classList.add("dragging");

    /* Deltas, not absolute positions measured against the grid.

       Moving a card can shorten the page - and where the document is the
       scroller, as it is on a tablet, the browser then clamps the scroll
       offset. A grid rectangle captured at drag start is stale the moment that
       happens, and every later move resolves to row 1, pinning the card to the
       top. A delta cannot go stale: it is the same arithmetic the resize
       handle has always used. */
    const onMove = (point) => {
      const dx = Math.round((point.clientX - startX) / pitchX);
      const dy = Math.round((point.clientY - startY) / pitchY);
      lay.x = Math.min(Math.max(1, originX + dx), HOME_GRID_COLS - lay.w + 1);
      // The grid is exactly HOME_GRID_ROWS tall. Dragging past the last row used
      // to create implicit rows, which is what put a card below the screen.
      lay.y = Math.min(Math.max(1, originY + dy), Math.max(1, HOME_GRID_ROWS - lay.h + 1));
      setCardCell(card, lay);
    };
    trackDrag(event, {
      onMove,
      onEnd: () => {
        card.classList.remove("dragging");
        // Cards are allowed to overlap: a card stays exactly where it is put,
        // rather than being shuffled to the nearest free row.
        persistCardLayout(card, lay);
      },
    });
  });

  /* Resize: corner grip adjusts the card's column/row span. */
  onDragStart(grid, (event) => {
    const handle = event.target.closest(".home-card-resize");
    const card = handle?.closest(".home-card");
    if (!card || !homeCardsArrangeable()) return;
    event.preventDefault();
    const { pitchX, pitchY } = homeGridPitch(grid);
    const start = dragPoint(event);
    const startX = start.clientX;
    const startY = start.clientY;
    const lay = cardLayoutOf(card);
    const startW = lay.w;
    const startH = lay.h;
    card.classList.add("resizing");

    const onMove = (point) => {
      // Overlapping is allowed, so a card grows freely past its neighbours.
      lay.w = Math.min(Math.max(2, startW + Math.round((point.clientX - startX) / pitchX)), HOME_GRID_COLS - lay.x + 1);
      lay.h = Math.min(Math.max(3, startH + Math.round((point.clientY - startY) / pitchY)),
                       Math.max(3, HOME_GRID_ROWS - lay.y + 1));
      setCardCell(card, lay);
      refitHomeCards();
    };
    trackDrag(event, {
      onMove,
      onEnd: () => {
        card.classList.remove("resizing");
        persistCardLayout(card, lay);
        refitHomeCards();
      },
    });
  });

  /* Double-click the corner grip: reset the card to its default cell. */
  grid.addEventListener("dblclick", (event) => {
    const handle = event.target.closest(".home-card-resize");
    const card = handle?.closest(".home-card");
    if (!card) return;
    const layout = loadHomeLayout();
    delete layout[card.dataset.homeCard];
    saveHomeLayout(layout);
    applyHomeCardLayout();
  });
})();

function showHomeOverview() {
  const overview = document.querySelector("#homeOverview");
  const detail   = document.querySelector("#homeAreaDetail");
  if (overview) overview.hidden = false;
  if (detail)   detail.hidden = true;
}

function areaThermoCardHtml(thermostat) {
  const temp = thermostat.temperature != null ? Math.round(Number(thermostat.temperature)) : "--";
  const unit = thermostat.temperature_unit?.includes("F") ? "°F" : "°C";
  const humidity = thermostat.humidity != null ? ` · ${thermostat.humidity}%` : "";
  return `
    <div class="area-thermo-card" data-goto-view="climate" role="button" tabindex="0">
      <span class="area-thermo-icon"><i class="ti ti-temperature"></i></span>
      <div class="area-thermo-info">
        <h3>${escapeHtml(thermostat.name)}</h3>
        <p>${escapeHtml(String(thermostat.hvac_mode || "off").toUpperCase())} · ${escapeHtml(thermostat.equipment_status || "idle")}${humidity}</p>
      </div>
      <div class="area-thermo-temp mono">${temp}<small>${unit}</small></div>
    </div>`;
}

/* ── Shared mixed-device renderer ──
   Used by both the Areas detail view and device group panels. Extracted rather
   than copied so the two cannot drift apart as kinds are added. Takes inventory
   entries ({key, kind, name, room, data}); returns subsection HTML. The switch
   grid cannot be built as a string, so hydrateGenericGroupBody finishes it. */
function genericGroupSectionsHtml(devices) {
  const of = (kind) => devices.filter((d) => d.kind === kind).map((d) => d.data);
  const switches    = devices.filter((d) => d.kind === "light" || d.kind === "plug").map((d) => d.data);
  const sensors     = of("sensor");
  const cameras     = of("camera");
  const thermostats = of("thermostat");
  const ambient     = of("ambient");
  const humidifiers = of("humidifier");
  const environment = of("environment");
  const bridges     = of("bridge");

  const sections = [];
  /* First: a bridge being down is the reason everything else on the page is
     stale, so it has to be read before the devices behind it. */
  if (bridges.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-router"></i> Bridges</div>
        <div class="device-grid bridge-tile-grid">${bridges.map(bridgeTileHtml).join("")}</div>
      </div>`);
  }
  if (switches.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-bulb"></i> Lights &amp; Plugs</div>
        <div class="device-grid" id="areaSwitchGrid"></div>
      </div>`);
  }
  if (thermostats.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-temperature"></i> Climate</div>
        <div class="area-thermo-row">${thermostats.map(areaThermoCardHtml).join("")}</div>
      </div>`);
  }
  if (sensors.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-radar-2"></i> Sensors</div>
        <div class="device-grid sensor-tile-grid">${sensors.map((g) => renderSensorDeviceCard(g, "sensors")).join("")}</div>
      </div>`);
  }
  if (cameras.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-video"></i> Cameras</div>
        <div class="camera-grid">${cameras.map((camera) => cameraCardHtml(camera)).join("")}</div>
      </div>`);
  }
  if (ambient.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-lamp-2"></i> Ambient Lights</div>
        <div class="ambient-grid">${ambient.map(ambientLightCard).join("")}</div>
      </div>`);
  }
  if (humidifiers.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-droplet"></i> Humidifiers</div>
        <div class="ambient-grid">${humidifiers.map(humidifierCard).join("")}</div>
      </div>`);
  }
  if (environment.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-temperature-celsius"></i> Environment</div>
        <div class="device-grid sensor-tile-grid">${environment.map(environmentSensorCard).join("")}</div>
      </div>`);
  }
  return sections.join("");
}

function hydrateGenericGroupBody(bodyEl, devices) {
  const switches = devices.filter((d) => d.kind === "light" || d.kind === "plug").map((d) => d.data);
  const switchGrid = bodyEl?.querySelector("#areaSwitchGrid");
  if (switchGrid) renderDeviceGroup(switchGrid, switches, "No switches.");
}

function renderAreaDetail(area) {
  const overview = document.querySelector("#homeOverview");
  const detail   = document.querySelector("#homeAreaDetail");
  if (!detail) return;
  if (overview) overview.hidden = true;
  detail.hidden = false;

  const iconEl = document.querySelector("#areaDetailIcon");
  if (iconEl) iconEl.innerHTML = `<i class="ti ti-${escapeHtml(area.icon)}"></i>`;
  const nameEl = document.querySelector("#areaDetailName");
  if (nameEl) nameEl.textContent = area.name;
  const metaEl = document.querySelector("#areaDetailMeta");
  if (metaEl) metaEl.textContent = `${area.devices.length} device${area.devices.length === 1 ? "" : "s"}`;
  const deleteBtn = document.querySelector("#areaDeleteButton");
  if (deleteBtn) deleteBtn.hidden = !area.custom;
  const manageBtn = document.querySelector("#areaManageButton");
  if (manageBtn) manageBtn.hidden = false;

  const body = document.querySelector("#areaDetailBody");
  if (!body) return;

  if (area.devices.length === 0) {
    body.innerHTML = `
      <div class="area-empty">
        <i class="ti ti-layout-grid-add"></i>
        <p>No devices in this area yet.</p>
        <button class="btn-primary" id="areaEmptyManage" type="button">Assign Devices</button>
      </div>`;
    return;
  }

  body.innerHTML = genericGroupSectionsHtml(area.devices);
  hydrateGenericGroupBody(body, area.devices);
}

async function refreshAreas() {
  areasDoc = await requestJson("/api/areas").catch(() => areasDoc);
}

async function toggleAreaLights(areaId) {
  const area = resolveHomeAreas().find((a) => a.id === areaId);
  if (!area) return;
  const switches = area.devices.filter((d) => d.kind === "light" || d.kind === "plug");
  if (switches.length === 0) return;
  const anyOn = switches.some((d) => d.data.is_on === true);
  const command = anyOn ? "off" : "on";
  await Promise.all(
    switches.map((d) => sendCommand(d.data.host, command, { skipRefresh: true }).catch(console.error))
  );
  logActivity(`${area.name} lights → ${command}`);
  await loadDevices();
}

/* ── New Area modal ── */
let areaModalIcon = "home";

function renderAreaIconPicker() {
  const picker = document.querySelector("#areaIconPicker");
  if (!picker) return;
  picker.innerHTML = AREA_ICON_CHOICES.map((icon) => `
    <button class="area-icon-choice ${icon === areaModalIcon ? "selected" : ""}"
      data-area-icon="${icon}" type="button" title="${icon}">
      <i class="ti ti-${icon}"></i>
    </button>`).join("");
}

function openAreaModal() {
  const modal = document.querySelector("#areaModal");
  if (!modal) return;
  areaModalIcon = "home";
  const input = document.querySelector("#areaNameInput");
  if (input) input.value = "";
  const error = document.querySelector("#areaModalError");
  if (error) error.hidden = true;
  renderAreaIconPicker();
  modal.hidden = false;
  input?.focus();
}

function closeAreaModal() {
  const modal = document.querySelector("#areaModal");
  if (modal) modal.hidden = true;
}

function showAreaModalError(message) {
  const error = document.querySelector("#areaModalError");
  const text  = document.querySelector("#areaModalErrorText");
  if (text) text.textContent = message;
  if (error) error.hidden = false;
}

function apiErrorDetail(error, fallback) {
  try {
    const payload = JSON.parse(error.message);
    if (payload && payload.detail) return String(payload.detail);
  } catch {}
  return fallback;
}

async function createAreaFromModal() {
  const input = document.querySelector("#areaNameInput");
  const name = (input?.value || "").trim();
  if (!name) {
    showAreaModalError("Give the area a name first.");
    input?.focus();
    return;
  }
  try {
    await requestJson("/api/areas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, icon: areaModalIcon }),
    });
  } catch (error) {
    showAreaModalError(apiErrorDetail(error, "Could not create the area."));
    return;
  }
  closeAreaModal();
  logActivity(`Area "${name}" created`);
  await refreshAreas();
  renderHomeView();
}

/* ── Manage Devices modal ── */

async function openAssignModal() {
  if (!currentAreaId) return;
  const modal = document.querySelector("#assignModal");
  if (!modal) return;
  const area = resolveHomeAreas().find((a) => a.id === currentAreaId);
  const title = document.querySelector("#assignModalTitle");
  if (title) title.textContent = `Manage Devices — ${area ? area.name : ""}`;
  renderAssignList();
  modal.hidden = false;
}

function renderAssignList() {
  const list = document.querySelector("#assignDeviceList");
  if (!list) return;

  const areas = resolveHomeAreas();
  const membership = new Map();
  areas.forEach((area) => area.devices.forEach((item) => membership.set(item.key, area.id)));

  const inventory = collectHomeInventory().sort((a, b) =>
    a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind.localeCompare(b.kind)
  );

  const optionsFor = (selectedId) =>
    ['<option value="">Unassigned</option>']
      .concat(areasDoc.areas.map((a) =>
        `<option value="${escapeHtml(a.id)}"${a.id === selectedId ? " selected" : ""}>${escapeHtml(a.name)}</option>`))
      .join("");

  list.innerHTML = inventory.map((item) => {
    const areaId = membership.get(item.key);
    const inCurrent = areaId === currentAreaId;
    return `
      <div class="assign-device-row ${inCurrent ? "in-area" : ""}">
        <span class="assign-device-icon"><i class="ti ${AREA_KIND_ICONS[item.kind] || "ti-cpu"}"></i></span>
        <span class="assign-device-name">${escapeHtml(item.name)}</span>
        <select class="assign-area-select" data-assign-key="${escapeHtml(item.key)}" aria-label="Area for ${escapeHtml(item.name)}">
          ${optionsFor(areaId === "auto:unassigned" ? "" : areaId)}
        </select>
      </div>`;
  }).join("");
}

function closeAssignModal() {
  const modal = document.querySelector("#assignModal");
  if (modal) modal.hidden = true;
}

async function deleteCurrentArea() {
  if (!currentAreaId || currentAreaId.startsWith("auto:")) return;
  const area = areasDoc.areas.find((a) => a.id === currentAreaId);
  const name = area ? area.name : "this area";
  if (!window.confirm(`Delete "${name}"? Its devices move to Unassigned.`)) return;
  try {
    await requestJson(`/api/areas/${encodeURIComponent(currentAreaId)}`, { method: "DELETE" });
  } catch (error) {
    console.error(error);
    return;
  }
  logActivity(`Area "${name}" deleted`);
  currentAreaId = null;
  await refreshAreas();
  renderHomeView();
}

/* ── Home view events ── */
document.addEventListener("click", (event) => {
  const toggle = event.target.closest(".area-lights-toggle");
  if (toggle) {
    event.preventDefault();
    event.stopPropagation();
    toggleAreaLights(toggle.dataset.areaLights).catch(console.error);
    return;
  }
  if (event.target.closest("#areaAddCard")) {
    openAreaModal();
    return;
  }
  const card = event.target.closest(".area-card[data-area-id]");
  if (card) {
    currentAreaId = card.dataset.areaId;
    renderHomeView();
    return;
  }
  if (event.target.closest("#areaEmptyManage")) {
    openAssignModal().catch(console.error);
    return;
  }
  const gotoCard = event.target.closest("[data-goto-view]");
  if (gotoCard) {
    // data-goto-view is also used by the Home view's thermostat dial, camera
    // frame and device rows, and by Area detail cards. Only a jump from the
    // Devices overview should arm the back button.
    arrivedFromDevices = Boolean(gotoCard.closest('[data-view-panel="devices"]'));
    activateView(gotoCard.dataset.gotoView);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;

  /* Anything carrying role="button" and a tabindex promises to work from the
     keyboard. These jump-to-view tiles declared that and only ever responded to
     a mouse, which leaves a focus ring sitting on something that does nothing. */
  const goto = event.target.closest?.('[data-goto-view][role="button"]');
  if (goto) {
    event.preventDefault();
    activateView(goto.dataset.gotoView);
    return;
  }

  const card = event.target.closest?.(".area-card[data-area-id]");
  if (!card) return;
  event.preventDefault();
  currentAreaId = card.dataset.areaId;
  renderHomeView();
});

document.addEventListener("change", (event) => {
  const checkbox = event.target.closest("input[data-temp-sensor-id]");
  if (!checkbox) return;
  const sources = homeTempSources();
  const chosen = selectedTempSensorIds(sources);
  if (checkbox.checked) chosen.add(checkbox.dataset.tempSensorId);
  else chosen.delete(checkbox.dataset.tempSensorId);
  try { localStorage.setItem(HOME_TEMP_SENSORS_KEY, JSON.stringify([...chosen])); } catch {}
  renderHomeTempSensors();
});

document.addEventListener("change", async (event) => {
  const select = event.target.closest("select[data-assign-key]");
  if (!select) return;
  const deviceKey = select.dataset.assignKey;
  const targetAreaId = select.value || null;
  select.disabled = true;
  try {
    await requestJson("/api/areas/assignments", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_key: deviceKey, area_id: targetAreaId }),
    });
    await refreshAreas();
    renderHomeView();
  } catch (error) {
    console.error(error);
  }
  renderAssignList();
});

(function initHomeView() {
  /* Custom card modal */
  document.querySelector("#addCustomCardButton")?.addEventListener("click", () => openCustomCardModal());
  document.querySelector("#closeCustomCardModal")?.addEventListener("click", closeCustomCardModal);
  document.querySelector("#customCardCancel")?.addEventListener("click", closeCustomCardModal);
  document.querySelector("#customCardSave")?.addEventListener("click", saveCustomCardFromModal);
  document.querySelector("#customCardDelete")?.addEventListener("click", deleteCustomCardFromModal);
  document.querySelector("#customCardNameInput")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") saveCustomCardFromModal();
  });

  /* Area tile drag-to-reorder inside the Areas card */
  const areaGridEl = document.querySelector("#areaGrid");
  let draggedAreaCard = null;
  enablePointerReorder({
    container: areaGridEl,
    itemSelector: ".area-card[data-area-id]",
    handleSelector: "[data-area-drag]",
    onReorder: (grid) => {
      const order = [...grid.querySelectorAll(".area-card[data-area-id]")].map((c) => c.dataset.areaId);
      try { localStorage.setItem(HOME_AREA_ORDER_KEY, JSON.stringify(order)); } catch {}
      logActivity("Areas rearranged");
    },
  });

  document.querySelector("#homeSensorGear")?.addEventListener("click", () => {
    const picker = document.querySelector("#homeSensorPicker");
    if (!picker) return;
    picker.hidden = !picker.hidden;
    if (!picker.hidden) renderHomeSensorPicker();
  });
  document.querySelector("#homeCameraSelect")?.addEventListener("change", (event) => {
    /* Picking a camera by hand is the clearest possible "I have this" - the
       override has to go, or the card would ignore the choice just made. */
    const next = event.target.value;
    const previous = shownHomeCameraId;
    const wasLive = Boolean(previous) && activeCameraIds.has(previous);
    releaseMotionEpisodes();
    /* One stream on the card: the camera being replaced stops, and if it was
       live the new one starts live rather than as a still waiting for a tap. */
    if (previous && previous !== next) activeCameraIds.delete(previous);
    if (wasLive) activeCameraIds.add(next);
    try { localStorage.setItem(HOME_CAMERA_KEY, next); } catch {}
    renderHomeCamera();
  });
  document.querySelector("#homeCameraAuto")?.addEventListener("change", (event) => {
    setMotionWatchEnabled(event.target.checked);
  });

  document.querySelector("#addAreaButton")?.addEventListener("click", openAreaModal);
  document.querySelector("#areaBackButton")?.addEventListener("click", () => {
    currentAreaId = null;
    renderHomeView();
  });
  document.querySelector("#areaManageButton")?.addEventListener("click", () => openAssignModal().catch(console.error));
  document.querySelector("#areaDeleteButton")?.addEventListener("click", () => deleteCurrentArea().catch(console.error));

  document.querySelector("#closeAreaModal")?.addEventListener("click", closeAreaModal);
  document.querySelector("#areaCancel")?.addEventListener("click", closeAreaModal);
  document.querySelector("#areaCreate")?.addEventListener("click", () => createAreaFromModal().catch(console.error));
  document.querySelector("#areaNameInput")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") createAreaFromModal().catch(console.error);
  });
  document.querySelector("#areaIconPicker")?.addEventListener("click", (event) => {
    const choice = event.target.closest("button[data-area-icon]");
    if (!choice) return;
    areaModalIcon = choice.dataset.areaIcon;
    renderAreaIconPicker();
  });

  document.querySelector("#closeAssignModal")?.addEventListener("click", closeAssignModal);
  document.querySelector("#assignDone")?.addEventListener("click", closeAssignModal);
})();

/* ── Send commands ── */

/* Which API owns a device's state, from the host prefix the card carries.
   "ha:" devices are served by /api/devices, which merges the Home Assistant
   cards in alongside the TP-Link ones. */
function deviceSourceOf(host) {
  const h = String(host || "");
  if (h.startsWith("matter:")) return "matter";
  if (h.startsWith("tuya:")) return "tuya";
  /* A Home Assistant entity can sit in either list. Stick S3 is an ha: host
     whose card lives in the Tuya grid, so refreshing /api/devices for it read
     a list it is not in and left the card showing the pre-command state until
     the next full poll. */
  if (h.startsWith("ha:")) {
    const entityId = h.slice(3);
    const inTuya = (latestTuyaDevices || []).some(
      (device) => String(device.entity_id ?? device.id) === entityId);
    return inTuya ? "tuya" : "switches";
  }
  return "switches";
}

/* Show what we just asked for, before asking the server what happened.

   A Matter brightness command turns the light on as a side effect, and the
   server's subscription can report the new level a beat after the command
   returns. Patching the local model first means the repaint below shows the
   user's own action rather than briefly snapping back to the old value; the
   60 s poll reconciles if the command did not take. */
/* ── A command is not believed until something confirms it ──

   /api/devices is a cache served instantly while a re-poll runs behind it, and
   a Home Assistant entity needs a moment before HA's own integration has
   polled the device and updated the state machine. So the read taken straight
   after a command usually still reports the state from *before* it: the card
   painted the new state, snapped back to the old one, and then flipped a
   second time when the truth arrived two or more seconds later.

   The expected state is therefore held until a read agrees with it, or until
   the window closes - whichever comes first. A command that genuinely failed
   still reverts at once, because the HTTP error does that separately; a switch
   that is offline settles on the truth when the window closes, having flickered
   nought times on the way there instead of twice. */
const PENDING_COMMAND_MS = 12000;
const pendingCommands = new Map();

/* What identifies a device across the lists a command might have to survive.

   Not simply `host`: cards sourced from Home Assistant carry the literal string
   "Home Assistant" there, which is not an address and is the *same* for every
   one of them - so keying on it matched nothing for Stick S3 and would have
   applied one light's command to all seventy-four of them. The entity id is
   the real identity for those. */
function deviceHostKey(device) {
  if (device.node_id != null) return `matter:${device.node_id}`;
  if (device.entity_id) return String(device.entity_id);
  if (device.host && device.host !== "Home Assistant") return String(device.host);
  return String(device.id ?? "");
}

function notePendingCommand(host, patch) {
  if (!host) return;
  pendingCommands.set(String(host), { patch, until: Date.now() + PENDING_COMMAND_MS });
}

/* Re-assert anything a command asked for that the server has not caught up
   with yet. Called after every read, before anything is painted from it. */
function applyPendingCommands() {
  if (!pendingCommands.size) return;
  const now = Date.now();
  for (const [host, pending] of pendingCommands) {
    if (pending.until <= now) pendingCommands.delete(host);
  }
  for (const list of [latestSwitchDevices, latestMatterDevices, latestTuyaDevices]) {
    for (const device of list || []) {
      const pending = pendingCommands.get(deviceHostKey(device));
      if (!pending) continue;
      if (Object.entries(pending.patch).every(([key, value]) => device[key] === value)) {
        // The server agrees now, so stop overriding it.
        pendingCommands.delete(deviceHostKey(device));
        continue;
      }
      Object.assign(device, pending.patch);
    }
  }
}

/* ── What brightness a light comes back on at ──

   Home Assistant reports no brightness at all for a light that is off, so the
   card fell back to a placeholder - and the dial jumped to that placeholder the
   instant you switched on, then again to the real level when the device
   answered. Remembering the last level actually observed lets the dial open
   where the light is about to be. */
const lastKnownBrightness = new Map();

function rememberBrightness(host, brightness) {
  const level = Number(brightness);
  if (!host || !Number.isFinite(level) || level <= 0) return;
  lastKnownBrightness.set(String(host), Math.round(level));
}

function recalledBrightness(host) {
  return lastKnownBrightness.get(String(host));
}

function patchLocalDeviceState(host, patch) {
  const lists = [latestSwitchDevices, latestMatterDevices];
  for (const list of lists) {
    for (const device of list || []) {
      const deviceHost = device.host ?? (device.node_id != null ? `matter:${device.node_id}` : device.id);
      if (String(deviceHost) === String(host)) Object.assign(device, patch);
    }
  }
}

/* Re-read only the source that owns the device a command just addressed.

   loadDevices() fans out to nine endpoints and Promise.all-waits for the
   slowest of them. Measured on the board: /api/matter/devices answers in 5 ms
   and the cached /api/devices in 3 ms, while /api/tuya/devices takes 2.9 s
   against Tuya's cloud and /api/weather 0.9 s. So every Stick S3 toggle waited
   on Tuya's cloud, and a 5 ms device felt like a 3 s one -- next to the Home
   app, which talks to the device directly, the dashboard looked broken.

   A command only invalidates the device it addressed. Everything else keeps
   repainting on the 60 s poll and the Home Assistant event stream, unchanged.
   A failed targeted read falls back to the full refresh rather than leaving
   the card showing an optimistic value nothing confirmed. */
async function refreshDeviceSource(host) {
  const source = deviceSourceOf(host);
  try {
    if (source === "matter") {
      const data = await requestJson("/api/matter/devices");
      latestMatterDevices = data.devices || [];
      _updateMatterServerStatus(data.matter_online ?? false);
      _renderMatterDeviceList(latestMatterDevices);
    } else if (source === "tuya") {
      const data = await requestJson("/api/tuya/devices");
      latestTuyaDevices = data.devices;
      applyPendingCommands();
      renderTuyaDevices(latestTuyaDevices);
    } else {
      const data = await requestJson("/api/devices");
      latestSwitchDevices = data.devices;
    }
  } catch (error) {
    console.error(error);
    await loadDevices();
    return;
  }

  applyPendingCommands();
  renderDevices(latestSwitchDevices, latestCameras, latestMatterDevices);
  renderDevicesOverview();
  renderHomeView();
  refreshActiveDynamicGroupPanel();
  if (statusDot) statusDot.classList.add("online");
  apiStatus.textContent = "Online";
}

async function sendCommand(host, command, options = {}) {
  apiStatus.textContent = "Sending";
  if (host.startsWith("matter:")) {
    const nodeId = host.slice(7);
    await requestJson(`/api/matter/devices/${nodeId}/commands/${command}`, { method: "POST" });
  } else if (host.startsWith("ha:")) {
    const entityId = host.slice(3);
    await requestJson(`/api/home-assistant/entities/${encodeURIComponent(entityId)}/commands/${command}`, { method: "POST" });
  } else {
    await requestJson("/api/devices/" + host + "/commands/" + command, { method: "POST" });
  }
  logActivity("Switch " + host.split(".").pop() + " turned " + command);
  if (command === "on" || command === "off") {
    patchLocalDeviceState(host, { is_on: command === "on" });
    notePendingCommand(host, { is_on: command === "on" });
  }
  if (options.skipRefresh !== true) await refreshDeviceSource(host);
}

async function sendTuyaCommand(deviceId, command) {
  apiStatus.textContent = "Sending";
  await requestJson(`/api/tuya/devices/${deviceId}/commands/${command}`, { method: "POST" });
  if (command === "on" || command === "off") notePendingCommand(deviceId, { is_on: command === "on" });
  await refreshDeviceSource("tuya:" + deviceId);
}

async function sendTuyaCardCommand(deviceId, command, source) {
  if (source === "home_assistant") {
    await sendHomeAssistantCommand(deviceId, command);
    return;
  }
  await sendTuyaCommand(deviceId, command);
}

async function sendHomeAssistantCommand(entityId, command) {
  apiStatus.textContent = "Sending";
  await requestJson(`/api/home-assistant/entities/${encodeURIComponent(entityId)}/commands/${command}`, { method: "POST" });
  logActivity(`HA ${entityId.split(".")[1] || entityId} → ${command}`);
  if (command === "on" || command === "off") {
    notePendingCommand("ha:" + entityId, { is_on: command === "on" });
    notePendingCommand(entityId, { is_on: command === "on" });
  }
  await refreshDeviceSource("ha:" + entityId);
}

async function renameCamera(cameraId, name) {
  apiStatus.textContent = "Saving";
  const updated = await requestJson(`/api/cameras/${encodeURIComponent(cameraId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  updateCachedCameraName(cameraId, updated.name || name);
  apiStatus.textContent = "Online";
  return latestCameraById.get(cameraId);
}

function updateCachedCameraName(cameraId, name) {
  const camera = latestCameraById.get(cameraId);
  if (camera) camera.name = name;
  const configuredCamera = latestCameras.find((item) => cameraIdFor(item) === cameraId);
  if (configuredCamera) configuredCamera.name = name;
  const tuyaCamera = latestTuyaDevices.find((item) => cameraIdFor(item) === cameraId);
  if (tuyaCamera) tuyaCamera.name = name;
}

/* ── View navigation ── */
function activateView(viewName) {
  /* A dynamic group panel — user-created, or the synthetic Unassigned bucket —
     is built on demand. syncDeviceGroupNav() pre-creates them, but it runs from
     loadDeviceGroups() and the inventory may still be empty then, in which case
     Unassigned did not exist yet and got no panel. Create it here, before the
     toggle below, which can only activate a panel that is already in the DOM. */
  const group = findDeviceGroup(viewName);
  const isDynamicGroup = Boolean(group) && !group.builtin;
  if (isDynamicGroup) ensureDeviceGroupPanel(group);

  railButtonEls().forEach((btn) => {
    const view = btn.dataset.view;
    btn.classList.toggle("active", view === viewName || PAGE_PARENTS[viewName] === view);
  });
  viewPanelEls().forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === viewName);
  });
  document.body.classList.toggle("home-assistant-mode", viewName === "homeassistant");
  if (viewName === "ambient") {
    loadAmbientLights().catch((error) => console.error(error));
  }
  if (viewName === "humidifier") {
    loadHumidifiers().catch((error) => console.error(error));
  }
  if (viewName === "environment") {
    loadEnvironmentSensors().catch((error) => console.error(error));
  }
  if (viewName === "ir") {
    loadIRHubs().catch((error) => console.error(error));
  }
  if (viewName === "media" || viewName === "music" || viewName === "bluetooth") {
    refreshBluetooth().catch((error) => console.error(error));
  }
  if (viewName === "media") renderMediaApps();
  if (viewName !== "youtube") stopYoutube();
  if (viewName === "news") {
    loadNewsSettings().catch((error) => console.error(error));
  }
  if (viewName === "about") {
    loadAboutInfo();
  }
  if (viewName === "settings") {
    renderSettingsApps();
  }
  if (viewName === "automations") {
    loadAutomationProposals().catch((error) => console.error(error));
  }
  if (viewName === "status") {
    loadHouseDigest().catch((error) => console.error(error));
    loadStatusOverview();
    loadHouseLearning();
    loadSecurityActivity();
  }
  if (viewName === "alarm") {
    loadSecurityActivity();
  }
  if (viewName === "zigbee") {
    loadZigbeeFrame().catch((error) => console.error(error));
    loadZigbeeBridgeCard().catch((error) => console.error(error));
  }
  if (viewName === "discovery") {
    requestJson("/api/matter/devices")
      .then((data) => {
        _updateMatterServerStatus(data.matter_online ?? false);
        _renderMatterDeviceList(data.devices || []);
      })
      .catch(() => _updateMatterServerStatus(false));
  }
  if (viewName === "devices") {
    renderDevicesOverview();
  }
  /* DEVICE_GROUP_VIEWS is built from the persisted groups, so the synthetic
     Unassigned bucket is never in it. Keying only off that list left it with no
     back button and no rendered panel. */
  if (DEVICE_GROUP_VIEWS.includes(viewName) || isDynamicGroup) {
    setDevicesBackVisible(arrivedFromDevices);
    if (!document.querySelector(`[data-view-panel="${CSS.escape(viewName)}"] .device-grid, [data-view-panel="${CSS.escape(viewName)}"] .ambient-grid`)) {
      renderDynamicGroupPanel(viewName);
    }
  } else {
    setDevicesBackVisible(false);
  }
}

/* ── Helper: update dial/gauge in new-style card ── */
function updateCardDial(card, isNowOn) {
  if (!card || !card.classList.contains("new-style")) return;
  const dialCenter = card.querySelector(".dial-center");
  if (dialCenter) {
    const isPlug   = card.dataset.category === "smart_plug";
    const locked   = card.dataset.dimmable === "false";
    /* The card's own data-brightness first - it is what the device last
       reported - then the level remembered for this host, and only then a
       default. Reaching the default means we have genuinely never seen this
       light on. */
    const brightness = locked ? 100 : (parseInt(card.dataset.brightness, 10)
      || recalledBrightness(card.dataset.host)
      || (isNowOn ? 100 : 10));
    dialCenter.innerHTML = isPlug
      ? buildPowerGauge(isNowOn, 0, 1500)
      : buildDimControlDial(brightness, isNowOn, !locked);
    if (!isPlug && !locked) attachDimDrag(card);
  }
  // Update the ON/OFF label (middle span[1] for lights, last span for plugs)
  const footer = card.querySelector(".device-footer");
  if (footer) {
    const spans  = footer.querySelectorAll("span");
    const isPlug = card.dataset.category === "smart_plug";
    const onSpan = isPlug ? spans[spans.length - 1] : spans[1];
    if (onSpan) {
      onSpan.textContent = isNowOn ? "ON" : "OFF";
      onSpan.style.color = isNowOn ? "var(--t-accent)" : "var(--t-text-dim2)";
    }
  }
}

function recordManualLightOverride(host, override) {
  if (host === undefined || host === null || String(host) === "") return null;
  manualLightCommandRevision += 1;
  const entry = { ...override, host: String(host), revision: manualLightCommandRevision };
  manualLightOverrides.set(String(host), entry);
  return entry;
}

function markManualLightCommand(card, command) {
  if (card?.dataset?.category === "light_switch") {
    recordManualLightOverride(card.dataset.host, { type: "command", command });
  }
}

function manualOverridesSince(sceneHosts, sceneStartRevision) {
  return Array.from(manualLightOverrides.values()).filter((override) =>
    sceneHosts.has(override.host) && override.revision > sceneStartRevision
  );
}

async function reapplyManualLightOverrides(sceneHosts, sceneStartRevision) {
  const overrides = manualOverridesSince(sceneHosts, sceneStartRevision);
  if (overrides.length === 0) return false;
  await Promise.allSettled(overrides.map((override) => {
    if (override.type === "brightness") {
      return requestJson("/api/devices/" + encodeURIComponent(override.host) + "/brightness", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: override.level }),
      });
    }
    return requestJson("/api/devices/" + override.host + "/commands/" + override.command, { method: "POST" });
  }));
  logActivity("Light scene: manual override restored");
  return true;
}

function updateDeviceCardSwitchState(card, isNowOn) {
  if (!card) return;
  const button = card.querySelector("button[data-command]");
  card.classList.toggle("on", isNowOn);
  if (button) {
    button.classList.toggle("on", isNowOn);
    button.dataset.command = isNowOn ? "off" : "on";
    button.setAttribute("aria-pressed", String(isNowOn));
  }
  const statusEl = card.querySelector(".device-status");
  if (statusEl && !card.classList.contains("new-style")) {
    const parts = statusEl.textContent.split(" · ");
    const room  = parts.slice(1).join(" · ");
    statusEl.textContent = (isNowOn ? "On" : "Off") + (room ? " · " + room : "");
  }
  updateCardDial(card, isNowOn);
}

function applyLightSceneOptimistic(lightCards, command) {
  const isNowOn = command === "on";
  lightCards.forEach((card) => updateDeviceCardSwitchState(card, isNowOn));
}

/* ── Event delegation ── */

/* Optimistic toggle — update UI immediately, revert on API error */
document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-command]");
  if (!button) return;
  const host    = button.dataset.host;
  const command = button.dataset.command;
  const card    = button.closest(".device-card");
  const isNowOn = command === "on";

  markManualLightCommand(card, command);
  updateDeviceCardSwitchState(card, isNowOn);

  sendCommand(host, command, { skipRefresh: activeLightSceneCount > 0 && card?.dataset?.category === "light_switch" }).catch((error) => {
    /* Revert optimistic update on failure */
    updateDeviceCardSwitchState(card, !isNowOn);
    apiStatus.textContent = "Error";
    logActivity(`Error toggling device: ${apiErrorDetail(error)}`, "error");
    console.error(error);
  });
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tuya-command]");
  if (!button) return;
  sendTuyaCardCommand(button.dataset.deviceId, button.dataset.tuyaCommand, button.dataset.deviceSource).catch((error) => {
    apiStatus.textContent = "Error";
    console.error(error);
  });
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-ha-command]");
  if (!button) return;
  sendHomeAssistantCommand(button.dataset.haEntityId, button.dataset.haCommand).catch((error) => {
    apiStatus.textContent = "Error";
    console.error(error);
  });
});

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-thermo-mode]");
  if (!btn) return;
  const id = btn.dataset.thermoId;
  thermoArticlesFor(id).forEach((article) => applyThermoModeUI(article, id, btn.dataset.thermoMode));
});

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-thermo-fan]");
  if (!btn) return;
  const id  = btn.dataset.thermoId;
  const ui  = thermoUIState.get(id);
  if (!ui) return;
  ui.fan = btn.dataset.thermoFan;
  thermoArticlesFor(id).forEach((article) => {
    article.querySelectorAll(".thermo-fan-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.thermoFan === ui.fan);
    });
  });
});

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-thermo-preset]");
  if (!btn) return;
  const id      = btn.dataset.thermoId;
  const ui      = thermoUIState.get(id);
  const preset  = THERMO_PRESETS.find((p) => p.id === btn.dataset.thermoPreset);
  if (!ui || !preset) return;
  ui.target = preset.target;
  ui.preset = preset.id;
  thermoArticlesFor(id).forEach((article) => {
    article.querySelectorAll(".thermo-preset-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.thermoPreset === preset.id);
    });
    applyThermoModeUI(article, id, preset.mode);
  });
});

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-thermo-step]");
  if (!btn) return;
  const id   = btn.dataset.thermoId;
  const ui   = thermoUIState.get(id);
  const step = Number(btn.dataset.thermoStep);
  if (!ui || !Number.isFinite(step)) return;
  ui.target = Math.max(10, Math.min(32, ui.target + step));
  ui.preset = null;
  refreshThermoDial(id);
});

/* ── Dim +/- buttons ── */
document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-dim-step]");
  if (!btn) return;
  event.preventDefault();
  event.stopPropagation();
  const card = btn.closest(".device-card");
  const delta = Number(btn.dataset.dimStep);
  if (!Number.isFinite(delta)) return;
  stepLightBrightness(card, delta);
});

/* ── Dim lock toggle ── */
document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-dim-lock]");
  if (!btn) return;
  const host = btn.dataset.dimLock;
  const card = btn.closest(".device-card");
  if (!card) return;
  const nowLocked = card.dataset.dimLocked !== "true";
  card.dataset.dimLocked = nowLocked;
  persistDimLock(host, nowLocked);
  const wrap = card.querySelector(".dial-wrap");
  wrap?.classList.toggle("dial-locked", nowLocked);
  const icon = btn.querySelector("i");
  if (icon) icon.className = `ti ti-lock${nowLocked ? "" : "-open"}`;
  btn.title = nowLocked ? "Unlock brightness" : "Lock brightness";
  btn.classList.toggle("locked", nowLocked);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-camera-toggle]");
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  const cameraId = button.dataset.cameraToggle;
  const camera   = latestCameraById.get(cameraId);
  if (!camera) return;
  const activating = !activeCameraIds.has(cameraId);
  if (activating) {
    activeCameraIds.add(cameraId);
  } else {
    activeCameraIds.delete(cameraId);
  }
  const card = button.closest(".camera-card");
  card.querySelector(".camera-frame").innerHTML  = cameraMedia(camera) + cameraBatteryBadge(camera);
  card.querySelector(".camera-action").innerHTML = cameraAction(camera);

  if (activating && camera.battery_powered) {
    captureSnapshotOnce(camera).catch(() => {});
  }
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-camera-edit]");
  if (!button) return;
  event.preventDefault();
  const camera = latestCameraById.get(button.dataset.cameraEdit);
  if (!camera) return;
  const row  = button.closest(".camera-title-row");
  const card = button.closest(".camera-card");
  row.outerHTML = cameraTitleEditor(camera);
  const input = card.querySelector("[data-camera-name-input]");
  input.focus();
  input.select();
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-camera-edit-cancel]");
  if (!button) return;
  event.preventDefault();
  const camera = latestCameraById.get(button.dataset.cameraEditCancel);
  if (!camera) return;
  const form = button.closest(".camera-title-editor");
  form.outerHTML = cameraTitle(camera);
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-camera-edit-form]");
  if (!form) return;
  event.preventDefault();
  const cameraId = form.dataset.cameraEditForm;
  const input    = form.querySelector("[data-camera-name-input]");
  const name     = input.value.trim();
  if (!name) { input.focus(); return; }
  form.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  renameCamera(cameraId, name)
    .then((camera) => { if (camera) form.outerHTML = cameraTitle(camera); })
    .catch((error) => {
      apiStatus.textContent = "Error";
      form.querySelectorAll("button").forEach((b) => { b.disabled = false; });
      console.error(error);
    });
});



/* ── Light and plug drag ordering ── */
document.addEventListener("dragstart", (event) => {
  const card = event.target.closest(".device-card[data-host]");
  if (!card) return;
  if (card.dataset.category === "light_switch" && !isLightDragUnlocked()) {
    event.preventDefault();
    return;
  }
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", card.dataset.host || "");
  card.classList.add("dragging");
});

document.addEventListener("dragend", (event) => {
  const card = event.target.closest(".device-card[data-host]");
  if (!card) return;
  const grid = card.closest("#lightGrid, #plugGrid");
  card.classList.remove("dragging");
  const category = grid?.id === "plugGrid" ? "smart_plug" : grid?.id === "lightGrid" ? "light_switch" : null;
  if (grid && category) saveDeviceOrderFromDom(grid, category); // dragend persistence
});

document.addEventListener("dragover", (event) => {
  const target = event.target.closest(".device-card[data-host]");
  const grid = target?.closest("#lightGrid, #plugGrid");
  const dragging = grid?.querySelector(".device-card.dragging");
  if (!target || !grid || !dragging || target === dragging) return;
  event.preventDefault();
  const rect = target.getBoundingClientRect();
  const insertAfter = event.clientY > rect.top + rect.height / 2;
  grid.insertBefore(dragging, insertAfter ? target.nextSibling : target);
});

document.addEventListener("drop", (event) => {
  const target = event.target.closest(".device-card[data-host]");
  const grid = target?.closest("#lightGrid, #plugGrid");
  if (!target || !grid) return;
  event.preventDefault();
  saveDeviceOrderFromDom(grid, grid.id === "plugGrid" ? "smart_plug" : "light_switch");
  logActivity(grid.id === "plugGrid" ? "Plug order saved" : "Light order saved");
});
/* ── Camera drag ordering ── */
enablePointerReorder({
  container: cameraGrid,
  itemSelector: ".camera-card[data-camera-id]",
  handleSelector: "[data-camera-drag]",
  onReorder: () => {
    saveCameraOrderFromDom();
    logActivity("Camera order saved");
  },
});

/* ── Home card tile drag ordering (custom-card lights) ──
   The grid flows left-to-right, so insertion position follows the pointer's
   horizontal side of the hovered tile. */
const TILE_DRAG_SELECTOR = ".custom-light-tile[data-tile-key]";

function saveCustomTileOrderFromDom(cardEl) {
  const id = cardEl?.dataset.homeCard?.slice("custom:".length);
  if (!id) return;
  const cards = loadCustomCards();
  const card = cards.find((c) => c.id === id);
  if (!card) return;
  const tileKeys = [...cardEl.querySelectorAll(".custom-light-tile[data-tile-key]")]
    .map((tile) => tile.dataset.tileKey);
  const rows = (card.devices || []).filter((key) => !tileKeys.includes(key));
  card.devices = [...tileKeys, ...rows];
  saveCustomCards(cards);
}

function persistTileOrder(tile) {
  saveCustomTileOrderFromDom(tile.closest(".home-custom-card"));
  logActivity("Card switches rearranged");
}

document.addEventListener("dragstart", (event) => {
  const tile = event.target.closest?.(TILE_DRAG_SELECTOR);
  if (!tile) return;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", tile.dataset.tileKey || "");
  tile.classList.add("dragging");
});

document.addEventListener("dragend", (event) => {
  const tile = event.target.closest?.(TILE_DRAG_SELECTOR);
  if (!tile) return;
  tile.classList.remove("dragging");
  persistTileOrder(tile);
});

document.addEventListener("dragover", (event) => {
  const target = event.target.closest?.(TILE_DRAG_SELECTOR);
  const grid = target?.closest(".custom-tile-grid");
  // querySelector scoped to the grid keeps reordering within one card.
  const dragging = grid?.querySelector(".dragging");
  if (!target || !grid || !dragging || target === dragging) return;
  event.preventDefault();
  const rect = target.getBoundingClientRect();
  const insertAfter = event.clientX > rect.left + rect.width / 2;
  grid.insertBefore(dragging, insertAfter ? target.nextSibling : target);
});

document.addEventListener("drop", (event) => {
  const target = event.target.closest?.(TILE_DRAG_SELECTOR);
  const grid = target?.closest(".custom-tile-grid");
  const dragging = grid?.querySelector(".dragging");
  if (!target || !grid || !dragging) return;
  event.preventDefault();
  persistTileOrder(dragging);
});
/* Palette picker */
document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-theme-id]");
  if (!btn) return;
  const id = btn.dataset.themeId;
  applyTheme(id);
  renderPalettePicker();
  try { localStorage.setItem("palette_theme", id); } catch {}
});

/* ── Morning digest ──
   Served from a file the 04:00 timer wrote, so this is a plain read and never
   waits on the model. The facts are collapsed but present: the prose is the
   model's retelling, and when a sentence reads oddly the numbers behind it are
   the thing you actually want. */
async function loadHouseDigest() {
  const card = document.querySelector("#digestCard");
  if (!card) return;
  let digest;
  try {
    digest = await requestJson("/api/digest");
  } catch {
    card.hidden = true;
    return;
  }
  if (!digest.available) {
    card.hidden = true;
    return;
  }

  const when = document.querySelector("#digestWhen");
  if (when) {
    const at = new Date((digest.generated_at || 0) * 1000);
    when.textContent = Number.isNaN(at.getTime()) ? "" : at.toLocaleString();
  }

  const body = document.querySelector("#digestBody");
  if (body) {
    /* The notes are what Python decided was worth saying, and they are always
       there. The model's prose is shown above them when it managed to write
       any - a nicety on top, never the thing the digest depends on. */
    const notes = (digest.notes || [])
      .map((note) => `<li>${escapeHtml(note)}</li>`).join("");
    const prose = digest.summary
      ? `<p>${escapeHtml(digest.summary)}</p>`
      : "";
    body.innerHTML = prose + (notes ? `<ul class="digest-notes">${notes}</ul>` : "")
      || `<p class="digest-noprose">Nothing to report.</p>`;
  }

  const facts = document.querySelector("#digestFacts");
  if (facts) facts.textContent = digest.facts_text || "";
  card.hidden = false;
}

/* ── Status: a board of small charts ──
   Each log gets its own diagram - activity by hour, the busiest sensors,
   camera sightings, the board's memory and temperature, batteries, services -
   so every chart reads on its own and the whole view is a glance. The board
   computes the hourly figures (/api/status/overview, cached two minutes);
   this only draws them. Colour means kind, and the four kinds were checked
   for colour-blind separation on the card ground. */
const STATUS_POLL_MS = 2 * 60_000;
const STATUS_LOW_BATTERY = 50;
const STATUS_BUSIEST = 6;
let latestStatusOverview = null;

/* A sensor's name as the Status view shows it: the place, in English. */
function statusName(name) {
  return shortZoneName(name);
}

function statusHourLabel(iso) {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? "" : String(at.getHours()).padStart(2, "0");
}

function statusUptime(bootIso, now = Date.now()) {
  const boot = new Date(bootIso || "").getTime();
  if (!Number.isFinite(boot) || boot > now) return null;
  const hours = Math.floor((now - boot) / 3_600_000);
  const days = Math.floor(hours / 24);
  return days ? `${days} d ${hours % 24} h` : `${hours} h`;
}

/* Events per hour as columns, the house's day in one shape. */
function statusColumnsSvg(totals, hours) {
  const w = 320, h = 104, slot = (w - 8) / 24;
  const max = Math.max(1, ...totals);
  const bars = totals.map((value, i) => {
    const bh = value ? Math.max(2, (value / max) * (h - 26)) : 2;
    const label = `${statusHourLabel(hours[i])}:00 · ${value} event${value === 1 ? "" : "s"}`;
    return `<rect class="st-col${value ? "" : " empty"}" x="${(4 + i * slot).toFixed(1)}" y="${(h - 14 - bh).toFixed(1)}" width="${(slot - 2).toFixed(1)}" height="${bh.toFixed(1)}" rx="2"><title>${label}</title></rect>`;
  }).join("");
  const ticks = [0, 6, 12, 18].map((i) =>
    `<text class="st-axis" x="${(4 + i * slot).toFixed(1)}" y="${h - 2}">${statusHourLabel(hours[i])}</text>`).join("");
  return `<svg class="st-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Events per hour, last 24 hours">${bars}${ticks}</svg>`;
}

/* A line over the day; hours without a sample leave a gap rather than a
   straight line pretending to know what happened. */
function statusSparklineSvg(values, kind, unit = "", decimals = 0) {
  const points = values.map((v, i) => [i, v]).filter(([, v]) => typeof v === "number" && Number.isFinite(v));
  if (!points.length) return `<p class="st-empty">No samples yet.</p>`;
  const lo = Math.min(...points.map(([, v]) => v));
  const hi = Math.max(...points.map(([, v]) => v));
  const pad = (hi - lo) * 0.2 || 1;
  const w = 300, h = 78, last = values.length - 1 || 1;
  const X = (i) => 4 + (i / last) * (w - 8);
  const Y = (v) => 14 + (1 - (v - (lo - pad)) / (hi - lo + 2 * pad)) * (h - 28);

  const segments = [];
  let run = [];
  values.forEach((v, i) => {
    if (typeof v === "number" && Number.isFinite(v)) run.push([i, v]);
    else if (run.length) { segments.push(run); run = []; }
  });
  if (run.length) segments.push(run);
  const path = (seg) => seg.map(([i, v], n) => `${n ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const areas = segments.map((seg) =>
    `<path class="st-area ${kind}" d="${path(seg)} L${X(seg[seg.length - 1][0]).toFixed(1)},${h - 12} L${X(seg[0][0]).toFixed(1)},${h - 12} Z"/>`).join("");
  const lines = segments.map((seg) => `<path class="st-line ${kind}" d="${path(seg)}"/>`).join("");
  const [lastI, lastV] = points[points.length - 1];
  const fmt = (v) => `${v.toFixed(decimals)}${unit}`;
  return `<svg class="st-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Last 24 hours, now ${fmt(lastV)}">
    ${areas}${lines}
    <circle class="st-dot ${kind}" cx="${X(lastI).toFixed(1)}" cy="${Y(lastV).toFixed(1)}" r="3"/>
    <text class="st-axis" x="${w - 4}" y="10" text-anchor="end">now ${fmt(lastV)}</text>
    <text class="st-axis" x="4" y="${h - 1}">low ${fmt(lo)} · high ${fmt(hi)}</text>
  </svg>`;
}

function statusBarsHtml(rows, max, unit = "") {
  if (!rows.length) return `<p class="st-empty">Nothing in the last 24 hours.</p>`;
  const top = Math.max(1, max);
  return `<div class="st-bars">${rows.map((row) => `
    <div class="st-bar-row"><span class="st-bar-name" title="${escapeHtml(row.title || row.name)}">${escapeHtml(row.name)}</span>
      <span class="st-bar"><i class="${row.kind}" style="width:${Math.max(3, Math.min(100, (row.value / top) * 100)).toFixed(1)}%"></i></span>
      <span class="st-bar-val mono">${row.value}${unit}</span></div>`).join("")}</div>`;
}

function setStatusText(selector, text, tone) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.textContent = text;
  if (tone !== undefined) {
    el.classList.toggle("st-good", tone === "good");
    el.classList.toggle("st-warn", tone === "warn");
  }
}

function renderStatusStrip(data) {
  const payload = latestAlarmData;
  const state = payload?.panel?.entity_id ? normalizeAlarmPanelState(payload.panel.state) : alarmState;
  const zones = payload?.zones || [];
  const open = alarmBreachedCount(zones);
  setStatusText("#statusAlarm",
    state === "disarmed" ? "Disarmed" : state === "home" ? "Home" : state === "away" ? "Away"
      : state === "arming" ? "Arming" : "ALARM", state === "alarm" ? "warn" : null);
  /* Every zone, motion included, so "active" rather than "open". */
  setStatusText("#statusAlarmSub", !zones.length ? "Security" : open ? `${open} active` : "all sensors normal");

  if (!data) return;
  const activity = data.activity || [];
  setStatusText("#statusEvents", String(data.events_total ?? 0));
  setStatusText("#statusEventsSub", `${activity.length} sensors & cameras`);

  const services = data.services || [];
  const down = services.filter((s) => !s.ok);
  setStatusText("#statusServicesCount", `${services.length - down.length}/${services.length}`, down.length ? "warn" : "good");
  setStatusText("#statusServicesSub", down.length ? `${down.map((s) => s.name).join(", ")} down` : "all running");

  const board = data.board || {};
  const uptime = statusUptime(board.boot);
  setStatusText("#statusUptime", uptime || "–");
  const boot = new Date(board.boot || "");
  setStatusText("#statusUptimeSub", Number.isNaN(boot.getTime()) ? "Orange Pi 6 Plus"
    : `since ${boot.toLocaleDateString(undefined, { day: "numeric", month: "short" })} ${boot.toTimeString().slice(0, 5)}`);

  const temps = (board.temp || []).filter((v) => typeof v === "number");
  setStatusText("#statusBoardTemp", temps.length ? `${Math.round(temps[temps.length - 1])}°C` : "–");
  setStatusText("#statusBoardTempSub", temps.length ? `peak ${Math.round(Math.max(...temps))}°C` : "No samples");

  const batteries = data.batteries || [];
  const low = batteries.filter((b) => b.percent < STATUS_LOW_BATTERY);
  setStatusText("#statusBatteriesLow", String(low.length), low.length ? "warn" : "good");
  setStatusText("#statusBatteriesSub", batteries.length ? `lowest ${batteries[0].percent}%` : "No battery sensors");
}

function renderStatusOverview(data = latestStatusOverview) {
  renderStatusStrip(data);
  if (!data) return;
  const set = (selector, html) => { const el = document.querySelector(selector); if (el) el.innerHTML = html; };
  const hours = data.hours || [];
  const activity = data.activity || [];

  const totals = hours.map((_, h) => activity.reduce((sum, s) => sum + (s.counts?.[h] || 0), 0));
  set("#statusActivity", statusColumnsSvg(totals, hours));
  setStatusText("#statusActivityMeta", `${data.events_total ?? 0} events`);

  const busiest = activity.filter((s) => s.total > 0).slice(0, STATUS_BUSIEST);
  set("#statusBusiest", statusBarsHtml(
    busiest.map((s) => ({ name: statusName(s.name), title: s.name, value: s.total, kind: s.kind })),
    busiest.length ? busiest[0].total : 1));

  const cameras = activity.filter((s) => s.kind === "camera" && s.total > 0);
  set("#statusCameras", statusBarsHtml(
    cameras.map((s) => ({ name: statusName(s.name), title: s.name, value: s.total, kind: "camera" })),
    cameras.length ? cameras[0].total : 1));

  const board = data.board || {};
  set("#statusMemory", statusSparklineSvg(board.mem || [], "motion", " MB"));
  set("#statusTemp", statusSparklineSvg(board.temp || [], "camera", "°C"));

  const batteries = data.batteries || [];
  set("#statusBatteries", statusBarsHtml(
    batteries.slice(0, STATUS_BUSIEST).map((b) => ({ name: statusName(b.name), title: b.name, value: b.percent,
      kind: b.percent < STATUS_LOW_BATTERY ? "low" : "door" })), 100, "%"));
  const low = batteries.filter((b) => b.percent < STATUS_LOW_BATTERY).length;
  setStatusText("#statusBatteryMeta", low ? `${low} low` : "all good");

  const services = data.services || [];
  const down = services.filter((s) => !s.ok).length;
  set("#statusServices", services.map((s) => `
    <div class="st-svc${s.ok ? "" : " down"}" title="${escapeHtml(s.unit)} · ${escapeHtml(s.state)}">
      <i class="st-svc-dot" aria-hidden="true"></i>
      <span>${escapeHtml(s.name)}<small>${s.scope === "container" ? "container" : s.scope === "system" ? "system unit" : "user unit"}${s.ok ? "" : ` · ${escapeHtml(s.state)}`}</small></span>
    </div>`).join(""));
  setStatusText("#statusServicesMeta", down ? `${down} not running` : `${services.length} running`);

  if (data.status === "needs_auth" || data.status === "home_assistant_unavailable") {
    set("#statusActivity", `<p class="st-empty">Home Assistant is ${data.status === "needs_auth" ? "not connected" : "not answering"}.</p>`);
  }
}

async function loadStatusOverview() {
  try {
    latestStatusOverview = await requestJson("/api/status/overview");
  } catch (error) {
    console.error(error);
  }
  renderStatusOverview();
}

setInterval(() => {
  if (document.hidden || !document.querySelector('.view-panel.active[data-view-panel="status"]')) return;
  loadStatusOverview();
  loadHouseLearning();
}, STATUS_POLL_MS);

/* ── House learning (Phase 0) ──
   The collector keeps every Home Assistant event; this tile says how much it
   holds, how far that is from enough to learn a routine (every weekday seen
   LEARN_WEEKS times), and asks for labels on the moments worth one - the
   Phase 1 models learn from those, and they cannot be recovered later. */
const LEARN_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];  /* Python's weekday(): Monday is 0 */
const LEARN_LABELS = [
  { label: "normal", icon: "ti-check", text: "Normal" },
  { label: "false_alarm", icon: "ti-x", text: "False alarm" },
  { label: "unusual", icon: "ti-alert-triangle", text: "Unusual" },
];
let latestLearning = null;

function browserTimeZone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { return "UTC"; }
}

/* Days until every weekday has been seen `needed` times, counting today (it
   will be complete by midnight). Monday-first, like the server. */
function learnDaysToReady(coverage, needed, today = new Date()) {
  const remaining = coverage.map((seen) => Math.max(0, needed - seen));
  if (remaining.every((n) => n === 0)) return 0;
  const start = (today.getDay() + 6) % 7;
  for (let day = 0; day < 7 * needed + 7; day++) {
    const weekday = (start + day) % 7;
    if (remaining[weekday] > 0) remaining[weekday] -= 1;
    if (remaining.every((n) => n === 0)) return day + 1;
  }
  return null;
}

function learnAgo(ts, now = Date.now()) {
  const minutes = Math.max(0, Math.round((now - ts * 1000) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} h ago` : `${Math.round(hours / 24)} d ago`;
}

function formatBytes(bytes) {
  if (!(bytes > 0)) return "0 MB";
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;
}

function learnStatsHtml(data) {
  const since = data.first_ts ? new Date(data.first_ts * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "–";
  const rows = [
    ["Events kept", Number(data.events || 0).toLocaleString()],
    ["Since", since],
    ["Today", Number(data.events_today || 0).toLocaleString()],
    ["Devices seen", String(data.entities || 0)],
    ["Storage", formatBytes(data.db_bytes)],
  ];
  const daily = data.daily || [];
  const max = Math.max(1, ...daily.map((d) => d.events));
  const bars = daily.map((d) => {
    const at = new Date(`${d.date}T12:00:00`);
    const label = `${at.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })} · ${d.events.toLocaleString()} events${d.complete ? "" : " (partial)"}`;
    return `<i class="learn-day${d.complete ? "" : " partial"}" style="height:${Math.max(6, (d.events / max) * 100).toFixed(0)}%" title="${escapeHtml(label)}"></i>`;
  }).join("");
  return `
    <div class="learn-sub">What it has kept</div>
    <dl class="learn-stats">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd class="mono">${escapeHtml(v)}</dd></div>`).join("")}</dl>
    <div class="learn-days" role="img" aria-label="Events kept per day, last ${daily.length} days">${bars}</div>`;
}

function learnReadyHtml(data) {
  const needed = data.weeks_needed || 4;
  const coverage = data.weekday_coverage || [0, 0, 0, 0, 0, 0, 0];
  const seen = coverage.reduce((sum, n) => sum + Math.min(n, needed), 0);
  const pct = Math.round((seen / (7 * needed)) * 100);
  const days = learnDaysToReady(coverage, needed);
  const eta = data.ready || days === 0 ? "Enough to start learning routines."
    : days == null ? "" : `About ${days} more day${days === 1 ? "" : "s"} until every weekday has been seen ${needed} times.`;
  const pips = LEARN_WEEKDAYS.map((name, i) => `
    <div class="learn-weekday" title="${name}: ${coverage[i]} complete day${coverage[i] === 1 ? "" : "s"}">
      <span>${name}</span>
      <span class="learn-pips">${Array.from({ length: needed }, (_, k) => `<i class="${k < coverage[i] ? "on" : ""}"></i>`).join("")}</span>
    </div>`).join("");
  return `
    <div class="learn-sub">Ready to learn routines</div>
    <div class="learn-progress"><span class="learn-bar"><i style="width:${pct}%"></i></span><b class="mono">${pct}%</b></div>
    <div class="learn-weekdays">${pips}</div>
    <p class="learn-note">${escapeHtml(eta)} ${data.days_complete || 0} complete day${data.days_complete === 1 ? "" : "s"} so far.</p>`;
}

function learnReviewHtml(data) {
  const labels = data.labels || {};
  const total = LEARN_LABELS.reduce((sum, l) => sum + (labels[l.label] || 0), 0);
  const items = (data.review || []).map((item) => `
    <li class="learn-item" data-event-id="${item.id}">
      <span class="learn-item-what"><i class="ti ${item.kind === "camera" ? "ti-user-scan" : "ti-door"}" aria-hidden="true"></i>
        <span>${escapeHtml(statusName(item.name))}<small>${item.kind === "camera" ? "person seen" : "opened"} · ${escapeHtml(learnAgo(item.ts))}</small></span></span>
      <span class="learn-item-actions">${LEARN_LABELS.map((l) => `
        <button type="button" class="learn-label" data-learn-label="${l.label}" title="${l.text}" aria-label="${l.text}"><i class="ti ${l.icon}" aria-hidden="true"></i></button>`).join("")}</span>
    </li>`).join("");
  return `
    <div class="learn-sub">Teach it <small>${total} label${total === 1 ? "" : "s"} · ${labels.false_alarm || 0} false alarm${labels.false_alarm === 1 ? "" : "s"}</small></div>
    ${items ? `<ul class="learn-list">${items}</ul>` : `<p class="learn-note">Nothing new to review in the last 24 hours.</p>`}`;
}

/* ── What the nightly run learned (Phase 1) ── */
const LEARN_ALERT_TEXT = {
  unusual_time: "Unusual hour",
  unusually_busy: "Unusually busy",
  unusually_quiet: "Unusually quiet",
};

function learnProfileText(config) {
  if (!config) return "";
  const profile = config.profile === "workweek" ? "weekdays vs weekends" : "each weekday on its own";
  return `${profile}, remembers ~${config.half_life_days} days`;
}

/* The learned week: rows Monday..Sunday, columns the 24 hours, darker where
   the house is more likely to be active. One hue - it is a single quantity. */
function learnRoutineHtml(routine) {
  if (!Array.isArray(routine) || routine.length !== 7) return `<p class="learn-note">No routine yet.</p>`;
  const rows = routine.map((hours, day) => `
    <span class="learn-heat-day">${LEARN_WEEKDAYS[day]}</span>
    <span class="learn-heat-row">${hours.map((p, hour) => `<i style="opacity:${(0.06 + 0.94 * Math.pow(Math.max(0, Math.min(1, p)), 2)).toFixed(2)}" title="${LEARN_WEEKDAYS[day]} ${String(hour).padStart(2, "0")}:00 · active ${Math.round(p * 100)}% of the time"></i>`).join("")}</span>`).join("");
  const axis = [0, 6, 12, 18].map((h) => `<span style="left:${((h / 24) * 100).toFixed(2)}%">${String(h).padStart(2, "0")}</span>`).join("");
  return `
    <div class="learn-sub">When the house is usually active</div>
    <div class="learn-heat" role="img" aria-label="Learned weekly routine">${rows}
      <span></span><span class="learn-heat-axis">${axis}</span></div>
    <p class="learn-note">Darker: more likely someone is moving about indoors that hour.</p>`;
}

function learnSparkSvg(values) {
  const points = values.map((v, i) => [i, v]).filter(([, v]) => typeof v === "number");
  if (points.length < 2) return `<p class="learn-note">The trend appears after a few nights.</p>`;
  const w = 220, h = 44, last = values.length - 1;
  const lo = Math.min(0, ...points.map(([, v]) => v)), hi = Math.max(0.5, ...points.map(([, v]) => v));
  const X = (i) => 4 + (i / last) * (w - 8);
  const Y = (v) => 4 + (1 - (v - lo) / (hi - lo || 1)) * (h - 8);
  const d = points.map(([i, v], n) => `${n ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  return `<svg class="learn-spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="How much better than a guess, night by night">
    <path class="learn-spark-line" d="${d}"/></svg>`;
}

function learnScoreHtml(learning) {
  const m = learning.metrics || {};
  const acc = m.house_accuracy, base = m.house_baseline_accuracy, skill = m.skill;
  const when = learning.last_run ? new Date(learning.last_run * 1000) : null;
  const stage = learning.status === "learning" ? "Learning"
    : `Warming up · ${learning.days} of ${learning.ready_days} days`;
  const pct = (v) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "–");
  return `
    <div class="learn-sub">How well it predicts ${learning.promoted ? `<small class="learn-new">new model tonight</small>` : ""}</div>
    <div class="learn-score"><b class="mono">${pct(acc)}</b><span>of hours predicted right<small>a guess from the average: ${pct(base)}</small></span></div>
    <p class="learn-note">Across all sensors, <b>${typeof skill === "number" ? `${Math.round(skill * 100)}% better` : "–"}</b> than a guess that ignores the clock, scored on the ${m.test_days || 0} most recent days it had not seen.</p>
    ${learnSparkSvg((learning.history || []).map((r) => r.skill))}
    <p class="learn-note">${escapeHtml(stage)}${when ? ` · trained ${escapeHtml(when.toLocaleDateString(undefined, { day: "numeric", month: "short" }))} ${escapeHtml(when.toTimeString().slice(0, 5))}` : ""}<br>${escapeHtml(learnProfileText(learning.config))} · best of ${m.candidates || 0}</p>`;
}

/* Several sensors tripping in the same hour are one moment - someone upstairs
   at 11:00 wakes the bedroom, hallway and landing sensors together - so they
   are one row. The label goes to the first sensor's event. */
function groupLearnAlerts(alerts) {
  const groups = [];
  const byKey = new Map();
  alerts.forEach((alert) => {
    const key = `${alert.ts}|${alert.kind}`;
    let group = byKey.get(key);
    if (!group) {
      group = { ...alert, names: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    group.names.push(statusName(alert.name));
    if (!group.event_id && alert.event_id && !alert.label) { group.event_id = alert.event_id; group.label = null; }
  });
  return groups.map((group) => ({
    ...group,
    name: group.names.length > 2 ? `${group.names.slice(0, 2).join(", ")} +${group.names.length - 2}` : group.names.join(", "),
  }));
}

function learnAlertsHtml(learning) {
  const alerts = groupLearnAlerts(learning.alerts || []);
  const labels = learning.alert_labels || {};
  const judged = Object.values(labels).reduce((a, b) => a + b, 0);
  const precision = judged ? `${Math.round(((labels.unusual || 0) / judged) * 100)}% worth it so far` : "no labels yet";
  const items = alerts.map((alert) => `
    <li class="learn-item${alert.label ? " learned" : ""}"${alert.event_id ? ` data-event-id="${alert.event_id}"` : ""}>
      <span class="learn-item-what"><i class="ti ti-${alert.kind === "unusually_quiet" ? "volume-off" : alert.kind === "unusually_busy" ? "flame" : "clock-exclamation"} learn-alert-icon" aria-hidden="true"></i>
        <span>${escapeHtml(alert.name)} · ${escapeHtml(LEARN_ALERT_TEXT[alert.kind] || alert.kind)}<small>${escapeHtml(alert.detail)} · ${escapeHtml(learnAgo(alert.ts))}</small></span></span>
      ${alert.event_id && !alert.label ? `<span class="learn-item-actions">${LEARN_LABELS.map((l) => `
        <button type="button" class="learn-label" data-learn-label="${l.label}" title="${l.text}" aria-label="${l.text}"><i class="ti ${l.icon}" aria-hidden="true"></i></button>`).join("")}</span>` : ""}
    </li>`).join("");
  return `
    <div class="learn-sub">Would have flagged <small>silently · ${escapeHtml(precision)}</small></div>
    ${items ? `<ul class="learn-list">${items}</ul>` : `<p class="learn-note">Nothing unexpected in the last two days.</p>`}`;
}

function renderLearnedModel(learning) {
  const host = document.querySelector("#learnModel");
  if (!host) return;
  if (!learning || !learning.runs) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  const set = (selector, html) => { const el = host.querySelector(selector); if (el) el.innerHTML = html; };
  set("#learnRoutine", learnRoutineHtml(learning.routine));
  set("#learnScore", learnScoreHtml(learning));
  set("#learnAlerts", learnAlertsHtml(learning));
}

function renderHouseLearning(data = latestLearning) {
  const card = document.querySelector("#learnCard");
  if (!card) return;
  const set = (selector, html) => { const el = card.querySelector(selector); if (el) el.innerHTML = html; };
  if (!data || !data.available) {
    setStatusText("#learnMeta", "Collector not started");
    set("#learnStats", `<p class="learn-note">The house memory starts with the house-memory service. Nothing is kept until it runs.</p>`);
    set("#learnReady", "");
    set("#learnReview", "");
    return;
  }
  const running = data.collector?.running;
  const meta = card.querySelector("#learnMeta");
  if (meta) {
    meta.innerHTML = `<i class="learn-dot${running ? " on" : ""}" aria-hidden="true"></i>${running ? "Collecting" : "Collector stopped"}${data.last_ts ? ` · last event ${escapeHtml(learnAgo(data.last_ts))}` : ""}`;
  }
  const labelled = Object.values(data.labels || {}).reduce((a, b) => a + b, 0);
  const learning = data.learning || {};
  card.querySelectorAll(".learn-step").forEach((step) => {
    const name = step.dataset.step;
    step.classList.toggle("done", (name === "collect" && running) || (name === "learn" && learning.status === "learning"));
    step.classList.toggle("active", name === "label" ? labelled > 0 : name === "learn" ? Boolean(learning.runs) : false);
  });
  const learnStep = card.querySelector('.learn-step[data-step="learn"] small');
  if (learnStep) {
    learnStep.textContent = !learning.runs ? "routines & anomalies"
      : learning.status === "learning" ? "nightly, 03:30" : `warming up · ${learning.days}/${learning.ready_days} days`;
  }
  renderLearnedModel(learning);
  set("#learnStats", learnStatsHtml(data));
  set("#learnReady", learnReadyHtml(data));
  set("#learnReview", learnReviewHtml(data));
}

async function loadHouseLearning() {
  try {
    latestLearning = await requestJson(`/api/memory/summary?tz=${encodeURIComponent(browserTimeZone())}`);
  } catch (error) {
    console.error(error);
  }
  renderHouseLearning();
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-learn-label]");
  if (!button) return;
  const item = button.closest("[data-event-id]");
  if (!item) return;
  item.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  try {
    await requestJson("/api/memory/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: Number(item.dataset.eventId), label: button.dataset.learnLabel }),
    });
    item.classList.add("learned");
    loadHouseLearning();
  } catch (error) {
    console.error(error);
    item.querySelectorAll("button").forEach((b) => { b.disabled = false; });
  }
});

/* ── Automations: the LLM authors, Home Assistant executes ──
   Drafting is slow by nature - a 4B model on eight CPU cores takes tens of
   seconds - so the button reports progress rather than pretending to be fast,
   and only one draft runs at a time (the server enforces that too; Ollama
   serialises requests regardless). Nothing here installs anything: a draft
   becomes a proposal file, and installing it is a separate, explicit press. */
let automationDrafting = false;

async function loadAutomationProposals() {
  const host = document.querySelector("#automationProposals");
  if (!host) return;
  let payload;
  try {
    payload = await requestJson("/api/automations/proposals");
  } catch (error) {
    host.innerHTML = `<div class="home-empty">Could not load proposals — ${escapeHtml(apiErrorDetail(error))}</div>`;
    return;
  }
  renderAutomationProposals(payload.proposals || []);
}

function renderAutomationProposals(proposals) {
  const host = document.querySelector("#automationProposals");
  const badge = document.querySelector("#proposalCount");
  if (badge) badge.textContent = proposals.length ? String(proposals.length) : "–";
  if (!host) return;

  if (!proposals.length) {
    host.innerHTML = `<div class="home-empty">No proposals yet. Describe a rule above and press Draft.</div>`;
    return;
  }

  host.innerHTML = proposals.map((proposal) => {
    /* The hints are the reason a human is in the loop: each one is a defect
       this model actually produced, that validation cannot catch because it is
       about intent rather than syntax. They are shown, never hidden. */
    const hints = (proposal.hints || []).map((hint) =>
      `<li><i class="ti ti-alert-triangle" aria-hidden="true"></i> ${escapeHtml(hint)}</li>`).join("");
    return `
      <div class="panel automation-proposal" data-proposal="${escapeHtml(proposal.name)}">
        <div class="home-panel-head">
          <span class="panel-title"><i class="ti ti-file-text"></i> ${escapeHtml(proposal.alias)}</span>
          <span class="section-meta">${escapeHtml(proposal.request)}</span>
        </div>
        ${hints ? `<ul class="automation-hints">${hints}</ul>` : ""}
        <pre class="automation-yaml">${escapeHtml(proposal.yaml)}</pre>
        <div class="automation-actions">
          <button class="btn-primary" type="button" data-install-proposal="${escapeHtml(proposal.name)}">Install</button>
          <button class="btn-secondary" type="button" data-delete-proposal="${escapeHtml(proposal.name)}">Discard</button>
        </div>
      </div>`;
  }).join("");
}

function setAutomationStatus(message, kind = "info") {
  const box = document.querySelector("#automationStatus");
  if (!box) return;
  box.hidden = !message;
  box.className = `automation-status automation-status-${kind}`;
  box.innerHTML = message;
}

async function draftAutomation() {
  if (automationDrafting) return;
  const input = document.querySelector("#automationRequest");
  const button = document.querySelector("#automationDraftBtn");
  const request = (input?.value || "").trim();
  if (!request) {
    setAutomationStatus("Say what the automation should do.", "warn");
    return;
  }

  automationDrafting = true;
  if (button) { button.disabled = true; button.textContent = "Drafting…"; }
  setAutomationStatus('<i class="ti ti-loader-2 spin"></i> Asking the local model — this takes about a minute.');

  try {
    const draft = await requestJson("/api/automations/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request }),
    });
    if (!draft.ok) {
      /* Validation failed against the real house, so there is no proposal to
         show. Say what was wrong rather than offering a broken automation. */
      const problems = (draft.problems || []).map((p) => `<li>${escapeHtml(p)}</li>`).join("");
      setAutomationStatus(
        `The draft did not check out after ${draft.attempts} attempt(s):<ul>${problems}</ul>` +
        `Try naming the entity you mean.`, "warn");
      return;
    }
    setAutomationStatus(
      `Drafted in ${draft.elapsed}s. Review it below — it is not running yet.`, "ok");
    if (input) input.value = "";
    await loadAutomationProposals();
  } catch (error) {
    setAutomationStatus(escapeHtml(apiErrorDetail(error)), "warn");
  } finally {
    automationDrafting = false;
    if (button) { button.disabled = false; button.textContent = "Draft"; }
  }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#automationDraftBtn")) {
    draftAutomation().catch((error) => console.error(error));
    return;
  }

  const install = event.target.closest("[data-install-proposal]");
  if (install) {
    const name = install.dataset.installProposal;
    install.disabled = true;
    install.textContent = "Installing…";
    requestJson(`/api/automations/proposals/${encodeURIComponent(name)}/install`, { method: "POST" })
      .then((result) => {
        setAutomationStatus(
          `Installed “${escapeHtml(result.alias || name)}”. Home Assistant reloaded its automations.`, "ok");
        return loadAutomationProposals();
      })
      .catch((error) => {
        setAutomationStatus(escapeHtml(apiErrorDetail(error)), "warn");
        install.disabled = false;
        install.textContent = "Install";
      });
    return;
  }

  const discard = event.target.closest("[data-delete-proposal]");
  if (discard) {
    const name = discard.dataset.deleteProposal;
    requestJson(`/api/automations/proposals/${encodeURIComponent(name)}`, { method: "DELETE" })
      .then(() => loadAutomationProposals())
      .catch((error) => setAutomationStatus(escapeHtml(apiErrorDetail(error)), "warn"));
  }
});

/* Sidebar navigation — delegated, so nav items added at runtime work without
   registration and no item can ever be bound twice. */
document.addEventListener("click", (event) => {
  const item = event.target.closest(".room-item[data-view]");
  if (!item) return;
  arrivedFromDevices = false;
  activateView(item.dataset.view);
});

/* Back to the Devices overview */
document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-back-to-devices]")) return;
  arrivedFromDevices = false;
  activateView("devices");
});

document.addEventListener("click", (event) => {
  const open = event.target.closest("[data-manage-group]");
  if (open) {
    openManageDevicesModal(open.dataset.manageGroup);
    return;
  }
  if (event.target.closest("#closeManageDevices") || event.target.closest("#manageDevicesDone")) {
    const modal = document.querySelector("#manageDevicesModal");
    if (modal) modal.hidden = true;
  }
});

document.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".manage-device-check");
  if (checkbox) toggleManageDevice(checkbox).catch((error) => console.error(error));
});

/* ── News (header) ──
   One headline at a time, beside a few prices, between the logo and the clock.
   The board fetches and caches the feeds (see news_feed.py), so polling here is
   cheap; what to show is chosen in Settings > News and saved on the board.

   The header is a fixed 72px that `main` subtracts from the screen height, so
   everything here is one line: the headline truncates rather than wraps.
   Tapping it moves to the next one. It is not a link: the wall panel is a kiosk
   with nobody there to come back from a news site. */
const NEWS_POLL_MS = 5 * 60_000;
const NEWS_ROTATE_MS = 8_000;
const NEWS_FADE_MS = 300;
const NEWS_KIND_LABELS = { breaking: "Breaking", world: "Top story", finance: "Markets" };
let newsHeadlines = [];
let newsIndex = 0;
/* A pointer over the headline holds it, but only for a while: a tap on the
   wall panel fires mouseenter and never the matching mouseleave, which would
   otherwise stop the headlines rotating until the next reload. */
const NEWS_HOLD_MS = 30_000;
let newsHeldUntil = 0;

function newsAge(published) {
  if (!published) return "";
  const minutes = Math.max(0, Math.round((Date.now() / 1000 - published) / 60));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours} h ago` : `${Math.round(hours / 24)} d ago`;
}

function newsMarketSpark(values, rising) {
  if (!Array.isArray(values) || values.length < 2) return "";
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const path = values.map((v, i) => {
    const x = (i * 36) / (values.length - 1);
    const y = 13 - ((v - lo) / (hi - lo || 1)) * 12;
    return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="header-news-spark ${rising ? "up" : "down"}" viewBox="0 0 36 14" preserveAspectRatio="none" aria-hidden="true"><path d="${path}"/></svg>`;
}

function renderNewsMarkets(markets) {
  const box = document.querySelector("#headerNewsMarkets");
  if (!box) return;
  box.innerHTML = markets.map((m) => {
    const change = Number(m.change_percent);
    const known = Number.isFinite(change);
    const rising = !known || change >= 0;
    const price = Number(m.price).toLocaleString("en-US", {
      minimumFractionDigits: m.decimals, maximumFractionDigits: m.decimals,
    });
    return `
      <div class="header-news-market">
        <span class="header-news-market-name">${escapeHtml(m.name)}</span>
        <span class="header-news-market-row">
          <span class="header-news-price">${escapeHtml(price)}</span>
          ${newsMarketSpark(m.spark, rising)}
          <span class="header-news-change ${rising ? "up" : "down"}">${known ? `${rising ? "▲" : "▼"}${Math.abs(change).toFixed(2)}%` : "—"}</span>
        </span>
      </div>`;
  }).join("");
}

function showHeadline(animate) {
  const story = document.querySelector("#headerNewsStory");
  const title = document.querySelector("#headerNewsTitle");
  const kind = document.querySelector("#headerNewsKind");
  const meta = document.querySelector("#headerNewsMeta");
  if (!story || !title || !newsHeadlines.length) return;
  newsIndex = ((newsIndex % newsHeadlines.length) + newsHeadlines.length) % newsHeadlines.length;
  const item = newsHeadlines[newsIndex];
  const paint = () => {
    if (kind) {
      kind.className = `header-news-kind kind-${item.kind}`;
      kind.textContent = NEWS_KIND_LABELS[item.kind] || "News";
    }
    const position = newsHeadlines.length > 1 ? `${newsIndex + 1}/${newsHeadlines.length}` : "";
    if (meta) meta.textContent = [item.source, newsAge(item.published), position].filter(Boolean).join(" · ");
    title.textContent = item.title;
    story.title = newsHeadlines.length > 1 ? `${item.title}\n\nTap for the next headline` : item.title;
    story.classList.remove("fading");
  };
  if (!animate) { paint(); return; }
  story.classList.add("fading");
  setTimeout(paint, NEWS_FADE_MS);
}

function renderNews(data) {
  const news = document.querySelector("#headerNews");
  if (!news) return;
  const headlines = data?.headlines || [];
  const markets = data?.markets || [];
  if (!data?.settings?.enabled || (!headlines.length && !markets.length)) {
    news.hidden = true;
    newsHeadlines = [];
    return;
  }
  const current = newsHeadlines[newsIndex]?.title;
  newsHeadlines = headlines;
  const kept = headlines.findIndex((h) => h.title === current);
  newsIndex = kept >= 0 ? kept : 0;
  news.classList.toggle("no-story", !headlines.length);
  news.classList.toggle("no-markets", !markets.length);
  news.hidden = false;
  showHeadline(false);
  renderNewsMarkets(markets);
}

/* A failed read retries soon, backing off to the normal poll, rather than
   waiting the full five minutes. A page that reloads for a new build does so
   while deploy-dashboard.sh is restarting the service, so its first read can
   land in the gap: that left the wall panel without news for five minutes
   after the build that introduced it. Whatever is on screen stays meanwhile.
   Only a failure schedules a timer; the regular poll is a plain interval. A
   success that re-armed a timeout made a loop wherever timers run at once. */
const NEWS_RETRY_FIRST_MS = 10_000;
let newsRetryMs = NEWS_RETRY_FIRST_MS;
let newsRetryTimer = null;

async function loadNews() {
  try {
    renderNews(await requestJson("/api/news"));
    newsRetryMs = NEWS_RETRY_FIRST_MS;
  } catch (error) {
    console.error(error);
    clearTimeout(newsRetryTimer);
    newsRetryTimer = setTimeout(loadNews, newsRetryMs);
    newsRetryMs = Math.min(newsRetryMs * 2, NEWS_POLL_MS);
  }
}

(function initHeaderNews() {
  const story = document.querySelector("#headerNewsStory");
  if (!story) return;
  const hold = () => { newsHeldUntil = Date.now() + NEWS_HOLD_MS; };
  story.addEventListener("mouseenter", hold);
  story.addEventListener("mousemove", hold);
  story.addEventListener("mouseleave", () => { newsHeldUntil = 0; });
  story.addEventListener("click", () => {
    if (newsHeadlines.length < 2) return;
    newsIndex += 1;
    newsHeldUntil = Date.now() + NEWS_ROTATE_MS;
    showHeadline(true);
  });
  setInterval(() => {
    if (Date.now() < newsHeldUntil || newsHeadlines.length < 2 || document.hidden) return;
    newsIndex += 1;
    showHeadline(true);
  }, NEWS_ROTATE_MS);
  loadNews();
  setInterval(loadNews, NEWS_POLL_MS);
})();

/* ── Settings > News ── */
const NEWS_LIST_FLAG = { breaking_sources: "breaking", finance_sources: "finance", market_ids: "markets" };
let newsSettingsDoc = null;

function renderNewsSettings() {
  if (!newsSettingsDoc) return;
  const { settings, available } = newsSettingsDoc;
  document.querySelectorAll("[data-news-flag]").forEach((input) => {
    const flag = input.dataset.newsFlag;
    input.checked = Boolean(settings[flag]);
    input.disabled = flag !== "enabled" && !settings.enabled;
  });
  const options = {
    breaking_sources: available.breaking_sources,
    finance_sources: available.finance_sources,
    market_ids: available.markets,
  };
  document.querySelectorAll("[data-news-list]").forEach((box) => {
    const key = box.dataset.newsList;
    const chosen = new Set(settings[key] || []);
    const active = settings.enabled && settings[NEWS_LIST_FLAG[key]];
    box.closest(".settings-row")?.classList.toggle("is-off", !active);
    box.innerHTML = (options[key] || []).map((option) => `
      <button type="button" class="settings-chip${chosen.has(option.id) ? " on" : ""}"
              data-news-option="${escapeHtml(option.id)}" aria-pressed="${chosen.has(option.id)}"
              ${active ? "" : "disabled"}>${escapeHtml(option.name)}</button>`).join("");
  });
}

async function loadNewsSettings() {
  newsSettingsDoc = await requestJson("/api/news/settings");
  renderNewsSettings();
}

async function saveNewsSettings(next) {
  const status = document.querySelector("#newsSettingsStatus");
  const previous = newsSettingsDoc;
  newsSettingsDoc = { ...newsSettingsDoc, settings: next };
  renderNewsSettings();
  if (status) status.textContent = "Saving…";
  try {
    newsSettingsDoc = await requestJson("/api/news/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
    renderNewsSettings();
    if (status) status.textContent = "Saved. Every screen shows this within five minutes.";
    loadNews();
  } catch (error) {
    newsSettingsDoc = previous;
    renderNewsSettings();
    if (status) status.textContent = `Not saved: ${apiErrorDetail(error)}`;
  }
}

(function initNewsSettings() {
  const root = document.querySelector("#newsSettings");
  if (!root) return;
  root.addEventListener("change", (event) => {
    const input = event.target.closest("[data-news-flag]");
    if (!input || !newsSettingsDoc) return;
    saveNewsSettings({ ...newsSettingsDoc.settings, [input.dataset.newsFlag]: input.checked });
  });
  root.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-news-option]");
    if (!chip || !newsSettingsDoc) return;
    const key = chip.closest("[data-news-list]").dataset.newsList;
    const id = chip.dataset.newsOption;
    const chosen = newsSettingsDoc.settings[key] || [];
    const nextList = chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id];
    saveNewsSettings({ ...newsSettingsDoc.settings, [key]: nextList });
  });
})();

/* ── Media > YouTube ──
   Paste a link, it plays here. Only the video id is taken from the link, and
   the player is YouTube's privacy-enhanced embed, so nothing else from the
   pasted text reaches the page.

   Full screen covers the page with the player rather than calling the
   Fullscreen API, for the reason the camera overlay does not (see
   test_touch_interactions.py): the API does nothing on an iPhone and behaves
   differently everywhere else. On the wall panel, whose browser is already
   full screen, covering the page is the whole display. The stage is restyled in
   place, not moved, because moving an iframe reloads it and restarts the video.
   For a desktop monitor, the player's own full-screen control still works. */
const YOUTUBE_LAST_KEY = "youtube_last_url";
const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_EMBED_ORIGIN = "https://www.youtube-nocookie.com";

function youtubeStartSeconds(value) {
  if (!value) return 0;
  if (/^\d+$/.test(value)) return Number(value);
  const match = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(value);
  if (!match) return 0;
  return Number(match[1] || 0) * 3600 + Number(match[2] || 0) * 60 + Number(match[3] || 0);
}

function parseYoutubeLink(text) {
  const raw = String(text || "").trim();
  if (YOUTUBE_ID.test(raw)) return { id: raw, start: 0 };
  let url;
  try {
    url = new URL(/^[a-z]+:\/\//i.test(raw) ? raw : `https://${raw}`);
  } catch {
    return null;
  }
  const host = url.hostname.replace(/^(www|m|music)\./, "");
  const parts = url.pathname.split("/").filter(Boolean);
  let id = null;
  if (host === "youtu.be") {
    id = parts[0];
  } else if (host === "youtube.com" || host === "youtube-nocookie.com") {
    if (parts[0] === "watch") id = url.searchParams.get("v");
    else if (["shorts", "embed", "live", "v"].includes(parts[0])) id = parts[1];
  }
  if (!id || !YOUTUBE_ID.test(id)) return null;
  return { id, start: youtubeStartSeconds(url.searchParams.get("t") || url.searchParams.get("start")) };
}

function playYoutube(text) {
  const error = document.querySelector("#youtubeError");
  const frame = document.querySelector("#youtubeFrame");
  const video = parseYoutubeLink(text);
  if (!video) {
    if (error) {
      error.textContent = "That isn't a YouTube video link. Copy the address of a video (youtube.com/watch?v=… or youtu.be/…) and paste it here.";
      error.hidden = false;
    }
    return;
  }
  if (error) error.hidden = true;
  const params = new URLSearchParams({
    autoplay: "1", playsinline: "1", rel: "0", enablejsapi: "1", origin: window.location.origin,
  });
  if (video.start) params.set("start", String(video.start));
  frame.innerHTML = `<iframe id="youtubeIframe" src="${YOUTUBE_EMBED_ORIGIN}/embed/${video.id}?${params}"
    title="YouTube video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
    allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
  const open = document.querySelector("#youtubeOpen");
  if (open) open.href = `https://www.youtube.com/watch?v=${video.id}${video.start ? `&t=${video.start}s` : ""}`;
  const fullscreen = document.querySelector("#youtubeFullscreen");
  if (fullscreen) fullscreen.disabled = false;
  try { localStorage.setItem(YOUTUBE_LAST_KEY, String(text).trim()); } catch {}
}

/* Pause rather than tear down, so coming back to Media resumes where it was. */
function stopYoutube() {
  const iframe = document.querySelector("#youtubeIframe");
  if (!iframe?.contentWindow) return;
  try {
    iframe.contentWindow.postMessage(JSON.stringify({ event: "command", func: "pauseVideo", args: [] }), YOUTUBE_EMBED_ORIGIN);
  } catch {}
}

function setYoutubeCovering(on) {
  const stage = document.querySelector("#youtubeStage");
  const exit = document.querySelector("#youtubeExit");
  stage?.classList.toggle("is-fullscreen", on);
  document.body.classList.toggle("youtube-covering", on);
  if (exit) exit.hidden = !on;
  if (on) exit?.focus();
}

(function initYoutube() {
  const form = document.querySelector("#youtubeForm");
  const input = document.querySelector("#youtubeUrl");
  if (!form || !input) return;
  try { input.value = localStorage.getItem(YOUTUBE_LAST_KEY) || ""; } catch {}
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    playYoutube(input.value);
  });
  document.querySelector("#youtubeFullscreen")?.addEventListener("click", () => setYoutubeCovering(true));
  document.querySelector("#youtubeExit")?.addEventListener("click", () => setYoutubeCovering(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("youtube-covering")) setYoutubeCovering(false);
  });
})();

/* ── Settings ──
   A page of app tiles; each opens its own view with a way back. The Settings
   item in the sidebar stays lit on those pages (PAGE_PARENTS). Each tile says where its
   setting stands, so the page answers most questions without opening one. */
/* An app's page keeps its launcher lit in the sidebar. */
const PAGE_PARENTS = {
  theme: "settings", startup: "settings", news: "settings", about: "settings", homecards: "settings",
  youtube: "media", music: "media",
  ir: "devices",
};

async function renderSettingsApps() {
  const setSub = (id, text) => {
    const el = document.querySelector(id);
    if (el && text) el.textContent = text;
  };
  setSub("#settingsThemeSub", THEMES[currentThemeId]?.label);
  setSub("#settingsHomeSub", document.querySelector("#homeMeta")?.textContent);
  const select = document.querySelector("#defaultViewSelect");
  setSub("#settingsStartupSub", select?.options[select.selectedIndex]?.text);
  try {
    const doc = newsSettingsDoc || await requestJson("/api/news/settings");
    const { settings } = doc;
    const sources = (settings.breaking ? settings.breaking_sources.length : 0)
      + (settings.finance ? settings.finance_sources.length : 0);
    const prices = settings.markets ? settings.market_ids.length : 0;
    setSub("#settingsNewsSub", settings.enabled ? `${sources} sources · ${prices} prices` : "Off");
  } catch {}
  try {
    const response = await fetch(`/static/build_info.json?ts=${Date.now()}`, { cache: "no-store" });
    if (response.ok) {
      const info = await response.json();
      setSub("#settingsAboutSub", [info.version && `v${info.version}`, info.build != null && `build ${info.build}`].filter(Boolean).join(" · "));
    }
  } catch {}
}

/* ── Startup (default) view ── */
const DEFAULT_VIEW_KEY = "default_view";

function getDefaultView() {
  try {
    const saved = localStorage.getItem(DEFAULT_VIEW_KEY);
    if (saved && railButtonEls().some((btn) => btn.dataset.view === saved)) return saved;
  } catch {}
  return "home";
}

/* Options are rebuilt from railButtonEls(), which is queried fresh -- so this
   can be called again once loadDeviceGroups() has synced the nav and a
   custom group's <li> exists, without duplicating the option-building logic. */
function populateDefaultViewSelect(select) {
  select.innerHTML = railButtonEls().filter((btn) => btn.dataset.view !== "settings").map((btn) => {
    const label = [...btn.childNodes]
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent.trim())
      .join("").trim() || btn.dataset.view;
    return `<option value="${escapeHtml(btn.dataset.view)}">${escapeHtml(label)}</option>`;
  }).join("");
}

(function initDefaultView() {
  const select = document.querySelector("#defaultViewSelect");
  if (select) {
    populateDefaultViewSelect(select);
    select.value = getDefaultView();
    select.addEventListener("change", () => {
      try { localStorage.setItem(DEFAULT_VIEW_KEY, select.value); } catch {}
      logActivity(`Startup view → ${select.options[select.selectedIndex]?.text || select.value}`);
    });
  }

  // Activate immediately so the dashboard is never blank while the device
  // groups document is in flight. At this instant railButtonEls() only sees
  // the seven built-in <li>s shipped in index.html, so a saved default_view
  // naming a custom group falls back to "home" here -- corrected below once
  // the nav exists.
  const initialView = getDefaultView();
  activateView(initialView);

  loadAmbientLights().catch((error) => console.error(error));
  loadHumidifiers().catch((error) => console.error(error));
  loadEnvironmentSensors().catch((error) => console.error(error));
  loadIRHubs().catch((error) => console.error(error));

  // Once the group nav is synced, a custom group's <li> exists: rebuild the
  // dropdown so it lists that group, and re-resolve the saved default_view --
  // now validating against the full nav -- so a saved custom-group id is
  // honoured instead of the "home" fallback above. Only re-activate if the
  // resolved view actually differs, so the common case (no saved pref, or a
  // built-in pref) never re-activates and never flickers.
  loadDeviceGroups()
    .then(() => {
      if (select) {
        populateDefaultViewSelect(select);
        select.value = getDefaultView();
      }
      const resolvedView = getDefaultView();
      if (resolvedView !== initialView) activateView(resolvedView);
    })
    .catch((error) => console.error(error));
})();

/* Light drag lock */
if (lightDragLock) {
  lightDragLock.addEventListener("click", () => {
    setLightDragUnlocked(!isLightDragUnlocked());
    applyLightDragLockState();
  });
}

/* Refresh button */
refreshButton.addEventListener("click", () => {
  loadDevices().catch((error) => {
    apiStatus.textContent = "Error";
    logActivity("Refresh failed", "error");
    console.error(error);
  });
});

/* HA back button */
if (homeAssistantBack) {
  homeAssistantBack.addEventListener("click", () => activateView("lights"));
}

/* ── Light scenes ── */
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-light-scene]");
  if (!btn) return;
  const command = btn.dataset.lightScene;
  const lightCards = Array.from(document.querySelectorAll('.device-card[data-category="light_switch"]'));
  if (lightCards.length === 0) return;
  const sceneStartRevision = manualLightCommandRevision;
  const sceneHosts = new Set(lightCards.map((card) => String(card.dataset.host || "")).filter((host) => host !== ""));
  btn.disabled = true;
  activeLightSceneCount += 1;
  apiStatus.textContent = "Running scene";
  applyLightSceneOptimistic(lightCards, command);
  try {
    await Promise.allSettled(
      lightCards.map((card) => {
        const host = card.dataset.host;
        if (host === undefined || host === null || String(host) === "") return Promise.resolve();
        if (host.startsWith("matter:")) {
          const nodeId = host.slice(7);
          return requestJson(`/api/matter/devices/${nodeId}/commands/${command}`, { method: "POST" });
        }
        return requestJson("/api/devices/" + host + "/commands/" + command, { method: "POST" });
      })
    );
    logActivity(command === "on" ? "Light scene: all on" : "Light scene: all off");
    await reapplyManualLightOverrides(sceneHosts, sceneStartRevision);
    await loadDevices().catch(console.error);
  } finally {
    activeLightSceneCount = Math.max(0, activeLightSceneCount - 1);
    btn.disabled = false;
  }
});

/* ── Ambient light actions ── */
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-ambient-command]");
  if (!btn) return;
  const lightId = btn.dataset.ambientId;
  const command = btn.dataset.ambientCommand;
  const card = btn.closest(".ambient-card");
  const buttons = card ? [...card.querySelectorAll("button[data-ambient-command]")] : [btn];
  const status = card?.querySelector(".ambient-status");
  buttons.forEach((item) => { item.disabled = true; item.classList.remove("active"); });
  btn.classList.add("active");
  if (status) status.textContent = command === "on" ? "Turning on..." : "Turning off...";
  apiStatus.textContent = "Sending";
  try {
    await requestJson("/api/ambient-lights/" + encodeURIComponent(lightId) + "/commands/" + command, { method: "POST" });
    await loadAmbientLights();
    apiStatus.textContent = "Online";
    logActivity("Ambient light turned " + command);
  } catch (error) {
    buttons.forEach((item) => { item.disabled = false; });
    if (status) status.textContent = "Command failed";
    apiStatus.textContent = "Error";
    logActivity("Ambient command unavailable", "warn");
    console.error(error);
  }
});

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-ambient-discover]");
  if (!btn) return;
  apiStatus.textContent = "Scanning BLE";
  requestJson("/api/ambient-lights/govee-ble/discover")
    .then((payload) => {
      const count = (payload.devices || []).length;
      logActivity(count ? "Govee BLE devices found: " + count : "No Govee BLE devices found", count ? "normal" : "warn");
      apiStatus.textContent = "Online";
    })
    .catch((error) => {
      apiStatus.textContent = "Error";
      logActivity("Govee BLE discovery unavailable", "error");
      console.error(error);
    });
});

/* ── Ambient light rename (inline) ── */
document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-ambient-edit]");
  if (!btn) return;
  event.preventDefault();
  const lightId = btn.dataset.ambientEdit;
  const nameRow = btn.closest(".ambient-name-row");
  if (!nameRow || nameRow.querySelector("input")) return;
  const heading = nameRow.querySelector("h3");
  const current = heading.textContent;
  const input = document.createElement("input");
  input.className = "ambient-name-input";
  input.maxLength = 80;
  input.value = current;
  input.setAttribute("aria-label", "Light name");
  heading.replaceWith(input);
  btn.style.display = "none";
  input.focus();
  input.select();
  let done = false;
  const cancel = () => {
    if (done) return;
    done = true;
    input.replaceWith(heading);
    btn.style.display = "";
  };
  const commit = async () => {
    if (done) return;
    const name = input.value.trim();
    if (!name || name === current) { cancel(); return; }
    done = true;
    apiStatus.textContent = "Saving";
    try {
      await requestJson("/api/ambient-lights/" + encodeURIComponent(lightId), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      await loadAmbientLights();
      apiStatus.textContent = "Online";
      logActivity("Ambient light renamed to " + name);
    } catch (error) {
      apiStatus.textContent = "Error";
      logActivity("Rename failed", "warn");
      console.error(error);
      done = false;
      cancel();
    }
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    else if (e.key === "Escape") { e.preventDefault(); cancel(); }
  });
  input.addEventListener("blur", commit);
});

/* ── Humidifier actions ── */
async function sendHumidifierCommand(humidifierId, command, body, logMsg) {
  apiStatus.textContent = "Sending";
  try {
    await requestJson("/api/humidifiers/" + encodeURIComponent(humidifierId) + "/commands/" + command, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    await loadHumidifiers();
    apiStatus.textContent = "Online";
    if (logMsg) logActivity(logMsg);
    return true;
  } catch (error) {
    apiStatus.textContent = "Error";
    logActivity("Humidifier command unavailable", "warn");
    console.error(error);
    return false;
  }
}

// Power (dial centre toggle).
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-humidifier-command]");
  if (!btn) return;
  const command = btn.dataset.humidifierCommand;
  btn.disabled = true;
  await sendHumidifierCommand(btn.dataset.humidifierId, command, null, "Humidifier turned " + command);
});

// Mist level +/- stepper.
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-humidifier-mist-step]");
  if (!btn) return;
  const step = Number(btn.dataset.humidifierMistStep);
  const min = Number(btn.dataset.min);
  const max = Number(btn.dataset.max);
  const level = Math.max(min, Math.min(max, Number(btn.dataset.current) + step));
  if (level === Number(btn.dataset.current)) return;
  btn.disabled = true;
  await sendHumidifierCommand(btn.dataset.humidifierId, "mist_level", { level }, "Humidifier mist level → " + level);
});

// Night light on/off.
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-humidifier-nightlight]");
  if (!btn) return;
  const state = btn.dataset.humidifierNightlight;
  btn.disabled = true;
  await sendHumidifierCommand(btn.dataset.humidifierId, "nightlight_" + state, null, "Night light " + state);
});

// Night light colour picker — reveal the full palette on click of the current swatch.
document.addEventListener("click", (event) => {
  const toggle = event.target.closest("button[data-humidifier-color-toggle]");
  if (!toggle) return;
  const palette = toggle.parentElement?.querySelector(".humid-swatches");
  if (palette) palette.hidden = !palette.hidden;
});

// Night light colour selection.
document.addEventListener("click", async (event) => {
  const sw = event.target.closest("button[data-humidifier-color]");
  if (!sw) return;
  const body = { red: Number(sw.dataset.red), green: Number(sw.dataset.green), blue: Number(sw.dataset.blue) };
  await sendHumidifierCommand(sw.dataset.humidifierId, "nightlight_color", body, "Night light colour set");
});

// Night light scene.
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-humidifier-scene]");
  if (!btn) return;
  const value = Number(btn.dataset.humidifierScene);
  btn.disabled = true;
  await sendHumidifierCommand(btn.dataset.humidifierId, "nightlight_scene", { value }, "Night light scene set");
});

// Night light brightness — reflect the value live, send on release.
document.addEventListener("input", (event) => {
  const slider = event.target.closest("input[data-humidifier-brightness]");
  if (!slider) return;
  const label = slider.parentElement?.querySelector(".humid-bright-val");
  if (label) label.textContent = slider.value + "%";
});
document.addEventListener("change", async (event) => {
  const slider = event.target.closest("input[data-humidifier-brightness]");
  if (!slider) return;
  const level = Number(slider.value);
  await sendHumidifierCommand(slider.dataset.humidifierId, "nightlight_brightness", { level }, "Night light brightness → " + level + "%");
});

/* ── All On / All Off (Plugs) ── */
document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-plug-all]");
  if (!btn) return;
  const command  = btn.dataset.plugAll;
  const plugCards = Array.from(document.querySelectorAll('.device-card[data-category="smart_plug"]'));
  if (plugCards.length === 0) return;
  apiStatus.textContent = "Sending";
  await Promise.allSettled(
    plugCards.map((card) => {
      const host = card.dataset.host;
      if (!host) return Promise.resolve();
      return requestJson(`/api/devices/${host}/commands/${command}`, { method: "POST" });
    })
  );
  await loadDevices().catch(console.error);
});

/* ── Notification actions ── */
document.addEventListener("click", (event) => {
  // Tells the server about every new device, exactly as Close does for one, so
  // the other screens drop them on their next refresh too.
  const dismissNewBtn = event.target.closest("button[data-notif-dismiss-new]");
  if (dismissNewBtn) {
    for (const [id, notif] of [...notifMap]) {
      if (notif.type !== "new_device") continue;
      if (notif.entityId) {
        requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/ignore`, { method: "POST" }).catch(console.error);
      }
      notifMap.delete(id);
    }
    renderNotifications();
    return;
  }

  const closeBtn = event.target.closest("button[data-notif-close]");
  if (closeBtn) {
    const notif = notifMap.get(closeBtn.dataset.notifClose);
    if (notif?.type === "new_device" && notif.entityId) {
      requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/ignore`, { method: "POST" }).catch(console.error);
    }
    dismissNotification(closeBtn.dataset.notifClose);
    return;
  }

  const respondBtn = event.target.closest("button[data-notif-respond]");
  if (respondBtn) {
    const notif = notifMap.get(respondBtn.dataset.notifRespond);
    if (notif?.type === "new_device") {
      window.openNewDeviceModal(notif);
      return;
    }
    if (notif) respondToNotification(notif);
    dismissNotification(respondBtn.dataset.notifRespond);
  }
});

/* ── Alarm actions ── */
document.addEventListener("click", (event) => {
  if (event.target.closest("button[data-arm-mode]")) {
    requestArmMode(event.target.closest("button[data-arm-mode]").dataset.armMode).catch(console.error);
    return;
  }
  if (event.target.closest("#sosTriggerBtn")) {
    // It sits in a row of small buttons now; a stray tap must not sound the siren.
    if (!window.confirm("Trigger the alarm now? The siren will sound.")) return;
    triggerSOS();
    return;
  }
  if (event.target.closest("#sirenTestBtn")) {
    if (sirenTesting) return;
    sirenTesting = true;
    renderAlarmSection();
    setTimeout(() => { sirenTesting = false; renderAlarmSection(); }, 2000);
  }
});

/* ── Doorbell: VIEW LIVE ── */
document.addEventListener("click", (event) => {
  const liveBtn = event.target.closest("button[data-doorbell-live]");
  if (liveBtn) {
    const cameraId = liveBtn.dataset.doorbellLive;
    doorbellLiveIds.add(cameraId);
    renderCameras(latestCameras, latestTuyaDevices);
    startLiveTimer(cameraId);
    return;
  }

  const endBtn = event.target.closest("button[data-doorbell-end]");
  if (endBtn) {
    const cameraId = endBtn.dataset.doorbellEnd;
    doorbellLiveIds.delete(cameraId);
    stopLiveTimer(cameraId);
    renderCameras(latestCameras, latestTuyaDevices);
    return;
  }

  const snapBtn = event.target.closest("button[data-doorbell-snap]");
  if (snapBtn) {
    const cameraId = snapBtn.dataset.doorbellSnap;
    const card      = document.querySelector(`[data-camera-id="${CSS.escape(cameraId)}"]`);
    if (!card) return;
    const existing = card.querySelector(".live-snap-toast");
    if (existing) return;
    const toast = document.createElement("div");
    toast.className = "live-snap-toast";
    toast.textContent = "Snapshot saved";
    card.querySelector(".doorbell-live-view")?.appendChild(toast);
    setTimeout(() => toast.remove(), 1400);
    return;
  }

  const ringBtn = event.target.closest("button[data-doorbell-ring]");
  if (ringBtn) {
    const cameraId   = ringBtn.dataset.doorbellRing;
    const cameraName = ringBtn.dataset.cameraName || "Doorbell";
    pushNotification("doorbell", `${cameraName} — someone's there`, "Doorbell pressed just now", { cameraId });
    return;
  }
});

/* ── Hold-to-talk ──
   Bound for touch as well: without Pointer Events the icon never reacted. */
const talkStart = (event) => {
  const btn = event.target.closest("button[data-doorbell-talk]");
  if (!btn) return;
  btn.querySelector(".live-ctrl-icon")?.classList.add("talking");
};
const talkEnd = (event) => {
  const btn = event.target.closest("button[data-doorbell-talk]");
  if (!btn) return;
  btn.querySelector(".live-ctrl-icon")?.classList.remove("talking");
};
document.addEventListener("pointerdown", talkStart);
document.addEventListener("touchstart", talkStart, { passive: true });
document.addEventListener("pointerup", talkEnd);
document.addEventListener("touchend", talkEnd);
document.addEventListener("touchcancel", talkEnd);
document.addEventListener("pointerleave", (event) => {
  const btn = event.target.closest("button[data-doorbell-talk]");
  if (!btn) return;
  btn.querySelector(".live-ctrl-icon")?.classList.remove("talking");
}, true);

/* ── Bootstrap ── */
try {
  const saved = localStorage.getItem("palette_theme");
  if (saved && THEMES[saved]) applyTheme(saved);
  else applyTheme("slate");
} catch {
  applyTheme("slate");
}
renderPalettePicker();
(function renderThemePreviewDials() {
  const off = document.querySelector("#themeDialOff");
  const on  = document.querySelector("#themeDialOn");
  if (off) off.innerHTML = buildDimControlDial(70, false, true);
  if (on)  on.innerHTML  = buildDimControlDial(70, true,  true);
})();
renderAlarmSection();

/* ── Zigbee2MQTT embed ──
   Zigbee2MQTT is a separate web app on its own port, so the iframe is
   cross-origin and cannot see the token the browser stored for that origin.
   Its frontend reads ?token= for exactly this case, and /api/zigbee/frontend
   supplies it from the board - behind the same dashboard login.

   Only the browser knows which address it reached the board on, so the host
   comes from window.location rather than from the server. */
let zigbeeFrameLoaded = false;

function _zigbeeUiUrl(port, token) {
  /* No fallback address on purpose: a literal here would be a second place the
     board's address is written down, and it would be wrong the moment the board
     moves. location.hostname is always set for a page served over http. */
  const host = window.location.hostname;
  const base = `http://${host}:${port || 8080}`;
  return token ? `${base}/?token=${encodeURIComponent(token)}` : base;
}

function _showZigbeeFallback(message) {
  const fallback = document.querySelector("#zigbeeFallback");
  const embed = document.querySelector('[data-view-panel="zigbee"] .home-assistant-embed');
  if (embed) embed.hidden = true;
  if (!fallback) return;
  fallback.hidden = false;
  fallback.innerHTML = message;
}

async function loadZigbeeFrame() {
  const frame = document.querySelector("#zigbeeFrame");
  const openLink = document.querySelector("#zigbeeOpen");
  const meta = document.querySelector("#zigbeeMeta");
  if (!frame || zigbeeFrameLoaded) return;

  let info;
  try {
    info = await requestJson("/api/zigbee/frontend");
  } catch (error) {
    _showZigbeeFallback("Could not reach the dashboard API to load Zigbee2MQTT.");
    return;
  }

  const url = _zigbeeUiUrl(info.port, info.token);
  if (openLink) openLink.href = url;

  if (!info.available) {
    /* No token file means the Zigbee stack was never installed on this host.
       Say that, rather than framing a login prompt nobody can satisfy. */
    _showZigbeeFallback(
      "Zigbee2MQTT is not set up on this board yet. Run " +
      "<code>scripts/install-zigbee2mqtt.sh</code> with the coordinator plugged in."
    );
    if (meta) meta.textContent = "Not installed";
    return;
  }

  /* Zigbee2MQTT ships an ES-module bundle. On a browser that cannot parse that
     syntax the iframe renders as a dead shell, exactly like the go2rtc player,
     so send those browsers to a real tab instead of a blank box. */
  if (LEGACY_JS) {
    _showZigbeeFallback(
      `This browser is too old to run the Zigbee2MQTT interface inline. ` +
      `<a href="${url}" target="_blank" rel="noreferrer">Open it in a new tab</a> instead.`
    );
    if (meta) meta.textContent = "Opens in a tab";
    return;
  }

  frame.src = url;
  zigbeeFrameLoaded = true;
  if (meta) meta.textContent = "Pair and manage sensors";
}

/* How long the bridge has held its current state, in words. Coarse on purpose:
   the useful distinction is "just now" versus "this has been broken for hours",
   not the exact minute. */
function _zigbeeSince(iso) {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const mins = Math.floor((Date.now() - then) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h`;
  return `${Math.floor(hours / 24)} d`;
}

/* Zigbee coordinator health.

   A dead bridge is silent: every Zigbee device just stops updating, and nothing
   on screen says why. One replug went unnoticed for 66 minutes. This fetch only
   stores the payload -- zigbeeBridgeDevice() turns it into the coordinator's
   tile in the Bridges group, which is where it is read. Failure is stored as
   "no payload", which reads as Unknown rather than Offline: not being able to
   ask is a different problem from the bridge being down. */
async function loadZigbeeHealth() {
  try {
    latestZigbeeBridge = await requestJson("/api/zigbee/bridge");
  } catch (error) {
    latestZigbeeBridge = null;
  }
  /* The Bridges panel is a dynamic group panel, so it only repaints when
     something asks it to. Both the overview tile count and an open panel have
     to see the new state. */
  renderDevicesOverview();
  const active = document.querySelector(".view-panel.active");
  if (active && findDeviceGroup(active.dataset.viewPanel)) {
    renderDynamicGroupPanel(active.dataset.viewPanel);
  }
}

/* The coordinator's own controls. Zigbee2MQTT publishes permit join as a switch
   entity, so left alone it lands on the Devices view among the household lights;
   the backend keeps it out of there and surfaces it here instead. */
async function loadZigbeeBridgeCard() {
  const card = document.querySelector("#zigbeeBridgeCard");
  const meta = document.querySelector("#zigbeeBridgeMeta");
  const button = document.querySelector("#zigbeePermitBtn");
  const label = document.querySelector("#zigbeePermitLabel");
  if (!card) return;

  let info;
  try {
    info = await requestJson("/api/zigbee/bridge");
  } catch (error) {
    card.hidden = true;
    return;
  }
  if (!info.available) {
    card.hidden = true;
    return;
  }

  card.hidden = false;
  const parts = [];
  if (info.connected === true) parts.push("Connected");
  else if (info.connected === false) parts.push("Disconnected");
  if (info.version) parts.push(`Zigbee2MQTT ${info.version}`);
  if (meta) meta.textContent = parts.join(" · ") || "Zigbee2MQTT";

  if (!info.permit_join_entity) {
    if (button) button.hidden = true;
    return;
  }
  if (button) {
    button.hidden = false;
    button.dataset.entityId = info.permit_join_entity;
    button.dataset.on = info.permit_join === true ? "1" : "0";
    button.classList.toggle("is-open", info.permit_join === true);
  }
  /* Pairing is the whole reason to open this view, so the button says what will
     happen next rather than naming the underlying entity's state. */
  if (label) label.textContent = info.permit_join === true ? "Stop pairing" : "Permit join";
}

document.querySelector("#zigbeePermitBtn")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const entityId = button.dataset.entityId;
  if (!entityId) return;
  const turningOn = button.dataset.on !== "1";
  button.disabled = true;
  try {
    await requestJson(
      `/api/home-assistant/entities/${encodeURIComponent(entityId)}/commands/${turningOn ? "on" : "off"}`,
      { method: "POST" }
    );
    logActivity(turningOn ? "Zigbee network open for pairing" : "Zigbee pairing closed");
    /* Zigbee2MQTT closes the window on its own after a couple of minutes, so the
       card is re-read rather than assumed to match what we just sent. */
    await loadZigbeeBridgeCard();
  } catch (error) {
    logActivity("Could not change Zigbee permit join", "error");
  } finally {
    button.disabled = false;
  }
});

/* The Discovery panel's button is a shortcut to the same view, not a second
   way of reaching Zigbee2MQTT. */
document.querySelector("#openZigbeeUI")?.addEventListener("click", () => {
  activateView("zigbee");
});

function _updateMatterServerStatus(online) {
  const text = document.querySelector("#matterServerStatus");
  const dot = document.querySelector("#matterServerDot");
  if (text) text.textContent = online ? "Online" : "Offline";
  if (dot) dot.className = "app-tile-dot " + (online ? "online" : "offline");
}

function _renderMatterDeviceList(devices) {
  const list = document.querySelector("#matterDeviceList");
  if (!list) return;
  const count = document.querySelector("#matterDeviceCount");
  if (count) count.textContent = devices.length ? `${devices.length} paired` : "";
  if (!devices.length) {
    list.innerHTML = '<div class="home-empty">No Matter devices paired yet. Use Add device.</div>';
    return;
  }
  list.innerHTML = devices.map((d) => `
    <div class="app-tile is-static" style="--app-a:#22d3ee;--app-b:#0e7490">
      <button class="app-tile-remove" data-matter-remove="${d.node_id}"
              title="Remove ${escapeHtml(d.name)}" aria-label="Remove ${escapeHtml(d.name)}" type="button">
        <i class="ti ti-trash" aria-hidden="true"></i>
      </button>
      <span class="app-tile-icon"><i class="ti ti-antenna" aria-hidden="true"></i></span>
      <span class="app-tile-name">${escapeHtml(d.name)}</span>
      <span class="app-tile-sub">${d.room ? escapeHtml(d.room) : "No room"}</span>
    </div>
  `).join("");
}

/* ── MATTER COMMISSIONING MODAL ── */
(function initMatterModal() {
  const modal      = document.querySelector("#matterModal");
  const step1      = document.querySelector("#matterStep1");
  const step2      = document.querySelector("#matterStep2");
  const spinner    = document.querySelector("#matterSpinner");
  const statusText = document.querySelector("#matterCommissionStatus");
  const errorBox   = document.querySelector("#matterError");
  const errorText  = document.querySelector("#matterErrorText");
  if (!modal) return;

  function openModal() {
    modal.hidden = false;
    _showMatterStep(1);
    document.querySelector("#matterSetupCode").value = "";
    document.querySelector("#matterName").value  = "";
    document.querySelector("#matterRoom").value  = "";
  }

  function closeModal() { modal.hidden = true; }

  function _showMatterStep(n) {
    step1.hidden = n !== 1;
    step2.hidden = n !== 2;
    errorBox.hidden = true;
    spinner.style.display = "block";
  }

  function _showMatterError(msg) {
    spinner.style.display = "none";
    errorBox.hidden = false;
    errorText.textContent = msg;
  }

  document.querySelector("#openMatterModal")?.addEventListener("click", openModal);
  document.querySelector("#closeMatterModal")?.addEventListener("click", closeModal);
  document.querySelector("#matterCancel")?.addEventListener("click", closeModal);
  document.querySelector("#matterRetry")?.addEventListener("click", () => _showMatterStep(1));
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  document.querySelector("#matterPair")?.addEventListener("click", async () => {
    const code = document.querySelector("#matterSetupCode").value.trim();
    const name = document.querySelector("#matterName").value.trim();
    const room = document.querySelector("#matterRoom").value.trim();
    if (!code) { document.querySelector("#matterSetupCode").focus(); return; }
    if (!name) { document.querySelector("#matterName").focus(); return; }

    _showMatterStep(2);
    statusText.textContent = "Connecting…";

    const steps = ["Connecting…", "Pairing…", "Commissioning…"];
    let stepIdx = 0;
    const timer = setInterval(() => {
      if (stepIdx < steps.length - 1) statusText.textContent = steps[++stepIdx];
    }, 8000);

    try {
      const resp = await fetch("/api/matter/commission", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setup_code: code, name, room: room || null }),
      });
      clearInterval(timer);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${resp.status}`);
      }
      spinner.style.display = "none";
      statusText.textContent = "Done ✓";
      setTimeout(() => { closeModal(); loadDevices(); }, 1200);
    } catch (e) {
      clearInterval(timer);
      _showMatterError(e.message);
    }
  });

  document.querySelector("#matterDeviceList")?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-matter-remove]");
    if (!btn) return;
    const nodeId = btn.dataset.matterRemove;
    if (!confirm("Remove this Matter device? It will need to be factory reset to pair again.")) return;
    try {
      await fetch(`/api/matter/devices/${nodeId}`, { method: "DELETE" });
      loadDevices();
    } catch {
      logActivity("Failed to remove Matter device", "error");
    }
  });
})();

/* ── NEW-DEVICE CONFIRMATION MODAL ── */
(function initNewDeviceModal() {
  const modal = document.querySelector("#newDeviceModal");
  if (!modal) return;
  let currentNotif = null;

  function openModal(notif) {
    currentNotif = notif;
    document.querySelector("#newDeviceName").value = notif.suggestedName || "";
    document.querySelector("#newDeviceRoom").value = notif.suggestedRoom || "";
    document.querySelector("#newDeviceCategory").value = notif.suggestedCategory || "light_switch";
    modal.hidden = false;
  }

  function closeModal() {
    modal.hidden = true;
    currentNotif = null;
  }

  document.querySelector("#closeNewDeviceModal")?.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  document.querySelector("#newDeviceIgnore")?.addEventListener("click", async () => {
    if (!currentNotif) return;
    const notif = currentNotif;
    closeModal();
    dismissNotification(notif.id);
    await requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/ignore`, { method: "POST" }).catch(console.error);
  });

  document.querySelector("#newDeviceConfirm")?.addEventListener("click", async () => {
    if (!currentNotif) return;
    const notif = currentNotif;
    const name = document.querySelector("#newDeviceName").value.trim();
    const room = document.querySelector("#newDeviceRoom").value.trim();
    const category = document.querySelector("#newDeviceCategory").value;
    if (!name) { document.querySelector("#newDeviceName").focus(); return; }
    closeModal();
    dismissNotification(notif.id);
    await requestJson(`/api/home-assistant/devices/${encodeURIComponent(notif.entityId)}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, room: room || null, category }),
    }).catch(console.error);
    await loadDevices();
  });

  window.openNewDeviceModal = openModal;
})();

/* ═════════════════ CONNECTED DEVICES ═════════════════ */

function renderNetworkModalList(payload) {
  const list = document.querySelector("#networkModalList");
  if (!list) return;
  const groups = (payload?.groups || []).filter((group) => (group.devices || []).length);
  if (!groups.length) {
    list.innerHTML = `<div class="home-empty">No devices with an address of their own.</div>`;
    return;
  }
  list.innerHTML = groups.map((group) => {
    const rows = group.devices.map((device) => {
      // online is null for write-only devices, where we genuinely do not know.
      const dot = device.online === null
        ? ""
        : `<span class="net-row-dot ${device.online ? "online" : "offline"}"
                 title="${device.online ? "Reachable" : "Not responding"}"></span>`;
      return `
        <div class="net-row">
          <span class="net-row-icon"><i class="ti ${escapeHtml(device.icon || "ti-device-desktop")}"></i></span>
          <span class="net-row-name">
            ${escapeHtml(device.name || "Unknown device")}
            <span class="net-row-address">${escapeHtml(device.address || "")}</span>
          </span>
          <span class="net-row-status">
            <span class="net-row-detail">${escapeHtml(device.detail || "")}</span>
            ${dot}
          </span>
        </div>`;
    }).join("");
    return `
      <div class="net-group-head">
        <span>${escapeHtml(group.label)}</span>
        <span class="net-group-count">${group.devices.length}</span>
      </div>
      ${rows}`;
  }).join("");
}

async function refreshNetworkDevices() {
  const payload = await requestJson("/api/network/devices");
  const badge = document.querySelector("#networkCount");
  if (badge) badge.textContent = payload.total ?? "–";
  renderNetworkModalList(payload);
  return payload;
}

(function initNetworkUi() {
  const modal = document.querySelector("#networkModal");
  const list = document.querySelector("#networkModalList");
  const closeModal = () => { if (modal) modal.hidden = true; };

  document.querySelector("#openNetworkModal")?.addEventListener("click", () => {
    if (modal) modal.hidden = false;
    if (list) list.innerHTML = `<div class="home-empty"><i class="ti ti-loader-2 spin"></i> Loading…</div>`;
    refreshNetworkDevices().catch((error) => {
      console.error(error);
      if (list) list.innerHTML = `<div class="home-empty">Could not load connected devices.</div>`;
    });
  });

  const rescanBtn = document.querySelector("#networkModalRescan");
  const hint = document.querySelector("#networkModalHint");
  rescanBtn?.addEventListener("click", async () => {
    rescanBtn.disabled = true;
    if (hint) hint.textContent = "";
    if (list) {
      list.innerHTML = `<div class="home-empty"><i class="ti ti-loader-2 spin"></i>
        Re-checking devices and looking for changed addresses…</div>`;
    }
    try {
      const payload = await requestJson("/api/network/devices/rescan", { method: "POST" });
      const badge = document.querySelector("#networkCount");
      if (badge) badge.textContent = payload.total ?? "–";
      renderNetworkModalList(payload);
      if (hint) hint.textContent = `Updated ${new Date().toLocaleTimeString()}`;
      logActivity("Rescanned connected devices");
      // Addresses may have moved, so the rest of the dashboard is stale too.
      loadDevices().catch(console.error);
    } catch (error) {
      console.error(error);
      if (list) list.innerHTML = `<div class="home-empty">Rescan failed.</div>`;
      logActivity("Connected devices rescan failed", "error");
    }
    rescanBtn.disabled = false;
  });

  document.querySelector("#closeNetworkModal")?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) closeModal();
  });

  // Fill the card's count without opening the modal; the listing is cheap and
  // shares the device cache the dashboard already refreshed.
  refreshNetworkDevices().catch(console.error);
})();

/* ── Build watch ───────────────────────────────────────────────────────────
   A deploy replaces app.js on the board. It cannot replace the copy a browser
   is already running, and nothing tells that browser to go and look. On a
   phone you reload without thinking about it; the wall panel has nobody to do
   that, so it would sit on the build it booted with for weeks while the board
   served a newer one.

   So: remember the build this page loaded, notice when the board reports a
   different one, and reload.

   The reload waits for the server to answer first. deploy-dashboard.sh copies
   the files and *then* restarts the service, so the new build number is
   visible for a moment while the dashboard is still coming back - reloading
   into that window parks the panel on a Chromium error page that nobody is
   there to dismiss, which is worse than the stale page it replaced. */
const BUILD_POLL_MS = 60_000;
let loadedBuild = null;

async function fetchBuild() {
  const response = await fetch(`/static/build_info.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) return null;
  const info = await response.json();
  return info.build ?? null;
}

async function loadBuildInfo() {
  try {
    const build = await fetchBuild();
    if (build === null) return;
    loadedBuild = build;
    if (buildBadge) buildBadge.textContent = `#${build}`;
  } catch {}
}

/* Settings > About. Read when the view opens, so the page always describes
   the build the board is serving, not only the one this tab loaded. */
async function loadAboutInfo() {
  const version = document.querySelector("#aboutVersion");
  const deployed = document.querySelector("#aboutDeployed");
  const board = document.querySelector("#aboutBoard");
  if (board) board.textContent = `Orange Pi 6 Plus · ${window.location.hostname}`;
  try {
    const response = await fetch(`/static/build_info.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) return;
    const info = await response.json();
    if (version) version.textContent = info.version ? `v${info.version}` : "—";
    if (buildBadge && info.build != null) buildBadge.textContent = `#${info.build}`;
    if (deployed && info.deployed_at) {
      const when = new Date(info.deployed_at);
      deployed.textContent = Number.isNaN(when.getTime())
        ? info.deployed_at
        : when.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    }
  } catch {}
}

async function reloadWhenServerAnswers(attempt = 0) {
  try {
    const response = await fetch(`/api/health?ts=${Date.now()}`, { cache: "no-store" });
    if (response.ok) {
      location.reload();
      return;
    }
  } catch {}
  /* Two minutes of retries: longer than any deploy takes, and short enough
     that a board which is genuinely down leaves the last good page on screen
     rather than replacing it with an error. */
  if (attempt < 60) setTimeout(() => reloadWhenServerAnswers(attempt + 1), 2_000);
}

function watchForNewBuild() {
  setInterval(async () => {
    try {
      const build = await fetchBuild();
      if (build === null) return;
      /* The read at page load can fail - a deploy in flight, a flaky moment.
         The first number we actually see is the baseline, never a change. */
      if (loadedBuild === null) {
        loadedBuild = build;
        if (buildBadge) buildBadge.textContent = `#${build}`;
        return;
      }
      if (build !== loadedBuild) reloadWhenServerAnswers();
    } catch {}
  }, BUILD_POLL_MS);
}

loadBuildInfo();
watchForNewBuild();

loadDevices().catch((error) => {
  apiStatus.textContent = "Error";
  logActivity("Failed to load devices", "error");
  console.error(error);
});

loadZigbeeHealth().catch((error) => console.error(error));
loadMotionLog().catch((error) => console.error(error));
loadHomeAlarmSelection().catch((error) => console.error(error));

/* Kept even once the live stream below is connected: this is the reconciliation
   pass that repairs anything the stream missed while the laptop was asleep or the
   connection was down, and the only thing refreshing sources Home Assistant does
   not report (the TP-Link poll, camera reachability). */
/* Auto-refresh every 60 s */
setInterval(() => {
  loadDevices().catch(console.error);
  /* Refreshed on the same cycle so an outage that starts while the dashboard is
     already open still surfaces, rather than only on reload. */
  loadZigbeeHealth().catch(console.error);
}, 60_000);

/* ── Live updates ──────────────────────────────────────────────────────────
   A door sensor on a 60 s poll is useless: you open the door and the dashboard
   agrees up to a minute later. /api/events/stream pushes a notification when
   Home Assistant reports a state change, and we answer it by running the normal
   refresh. Deliberately a trigger and not a state feed - one code path builds
   the cards, so the stream cannot leave the page disagreeing with the server.

   Everything here is best-effort. If the stream never opens, the 60 s poll above
   still runs and the dashboard is exactly as live as it was before. */
const LIVE_REFRESH_DEBOUNCE_MS = 250;
/* Two events a second apart should give two refreshes; a burst from a bridge
   reconnect should give one. A trailing debounce does both. */
let liveRefreshTimer = null;
function scheduleLiveRefresh() {
  if (liveRefreshTimer) clearTimeout(liveRefreshTimer);
  liveRefreshTimer = setTimeout(() => {
    liveRefreshTimer = null;
    loadDevices().catch(console.error);
    /* A detection is exactly the kind of event this stream exists for, so the
       log follows the same push rather than waiting for the 60s poll. */
    loadMotionLog().catch(console.error);
  }, LIVE_REFRESH_DEBOUNCE_MS);
}

/* The view a "show_view" frame asks for, or null. Checked here as well as on the
   server, so a malformed frame can never open an arbitrary panel. */
const WALL_PANEL_VIEWS = new Set(["home", "cameras", "alarm", "devices", "climate", "status"]);
function wallPanelView(data) {
  try {
    const view = String(JSON.parse(data || "{}").view || "").toLowerCase();
    return WALL_PANEL_VIEWS.has(view) ? view : null;
  } catch {
    return null;
  }
}

function connectLiveUpdates() {
  if (typeof EventSource !== "function") return;   /* older Safari: poll only */
  /* The whole wiring is guarded, not just the constructor. This is an
     enhancement on top of a dashboard that already works, so nothing here may
     throw during page load - including against an EventSource that exists but
     is not a real one. */
  try {
    const source = new EventSource("/api/events/stream");
    if (!source || typeof source.addEventListener !== "function") return;

    source.addEventListener("changed", scheduleLiveRefresh);

    /* The Voice Panel's wall-panel remote. The server only sends this to the
       wall panel's own stream, never to a phone or the PC. */
    source.addEventListener("show_view", (event) => {
      const view = wallPanelView(event.data);
      if (view) activateView(view);
    });

    source.addEventListener("unavailable", (event) => {
      /* The server reached a conclusion rather than failing: no token, no
         aiohttp, Home Assistant down. Retrying in a tight loop would not fix any
         of those, so stop and leave the poll in charge. */
      let reason = "";
      try { reason = (JSON.parse(event.data || "{}").reason) || ""; } catch {}
      console.info("Live updates unavailable, falling back to polling.", reason);
      try { source.close(); } catch {}
    });

    /* EventSource reconnects on its own after a transient drop. It gives up only
       when the connection is closed, which is the branch worth retrying - slowly,
       so a dashboard left open against a dead server does not hammer it. */
    source.addEventListener("error", () => {
      if (source.readyState === EventSource.CLOSED) {
        setTimeout(connectLiveUpdates, 30_000);
      }
    });
  } catch {
    /* Poll-only from here; the dashboard is exactly as live as it was before. */
  }
}
connectLiveUpdates();
