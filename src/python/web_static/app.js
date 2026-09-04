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
const thermostatGrid    = document.querySelector("#thermostatGrid");
const homeAssistantFrame = document.querySelector("#homeAssistantFrame");
const homeAssistantOpen = document.querySelector("#homeAssistantOpen");
const homeAssistantBack = document.querySelector("#homeAssistantBack");
const cameraGrid        = document.querySelector("#cameraGrid");
const lightCount        = document.querySelector("#lightCount");
const plugCount         = document.querySelector("#plugCount");
const ambientCount      = document.querySelector("#ambientCount");
const tuyaCount         = document.querySelector("#tuyaCount");
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
let latestTuyaDevices   = [];
let latestAlarmData     = null;
let latestSwitchDevices = [];
let latestMatterDevices = [];
let latestThermostats   = [];
let latestAmbientLights = [];
let latestHumidifiers   = [];
let latestEnvironmentSensors = [];
let areasDoc            = { areas: [], assignments: {} };
let currentAreaId       = null;
let doorbellEventsReady = false;
const latestCameraById  = new Map();
const lastDoorbellEventById = new Map();
let manualLightCommandRevision = 0;
let activeLightSceneCount = 0;
const manualLightOverrides = new Map();

/* ── Live clock ── */
function tick() {
  const now = new Date();
  const clockEl = document.querySelector("#clock");
  const dateEl  = document.querySelector("#dateDisplay");
  if (clockEl) clockEl.textContent = now.toTimeString().slice(0, 8);
  if (dateEl)  dateEl.textContent  = now.toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "long", year: "numeric"
  });
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

/* ── Sidebar collapsibles: Settings group + Recent Activity ── */
(function initSidebarCollapsibles() {
  const settingsToggle = document.querySelector("#systemSettingsToggle");
  settingsToggle?.addEventListener("click", () => {
    const open = settingsToggle.classList.toggle("open");
    document.querySelectorAll(".system-settings-item").forEach((item) => {
      item.hidden = !open;
    });
    settingsToggle.title = open ? "Hide theme and startup settings" : "Show theme and startup settings";
  });

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
let DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"];
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
const BUILTIN_TILE_VIEWS = new Set(["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]);

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
  const badge = document.querySelector("#deviceGroupCount");

  if (badge) badge.textContent = String(distinctDeviceCount());

  if (!grid) return;
  grid.innerHTML = deviceGroupTileData().map((tile) => `
    <article class="device-group-tile" data-goto-view="${escapeHtml(tile.view)}"${tile.color ? ` style="--group-color:${tile.color}"` : ""}>
      <div class="device-group-tile-accent" aria-hidden="true"></div>
      <div class="device-group-tile-body">
        <div class="device-group-tile-head">
          <i class="ti ${escapeHtml(tile.icon)}" aria-hidden="true"></i>${escapeHtml(tile.label)}
        </div>
        <div class="device-group-tile-count">${tile.count}</div>
        <div class="device-group-tile-summary">${escapeHtml(tile.summary)}</div>
      </div>
    </article>
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
  if (host.startsWith("matter:")) {
    const nodeId = host.slice(7);
    const resp = await fetch(`/api/matter/devices/${nodeId}/commands/brightness?brightness=${level}`, {
      method: "POST",
    });
    if (!resp.ok) throw new Error("Brightness set failed: " + resp.status);
    return resp.json();
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

  deviceCount.textContent    = String(devices.length + matterDevices.length);
  onCount.textContent        = String([...devices, ...matterDevices].filter((d) => d.is_on === true).length);
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
function renderLightScenes(lightDevices) {
  if (!lightScenes) return;
  const disabled = lightDevices.length === 0 ? " disabled" : "";
  lightScenes.innerHTML = [
    '<button class="scene-button all-on" data-light-scene="on" type="button"' + disabled + '>',
    '<span class="scene-icon"><i class="ti ti-sun-filled" aria-hidden="true"></i></span>',
    '<span class="scene-copy"><strong>All Lights On</strong><small>Wake every room</small></span>',
    '<span class="scene-spark" aria-hidden="true"></span>',
    '</button>',
    '<button class="scene-button all-off" data-light-scene="off" type="button"' + disabled + '>',
    '<span class="scene-icon"><i class="ti ti-moon-filled" aria-hidden="true"></i></span>',
    '<span class="scene-copy"><strong>All Lights Off</strong><small>Settle the house</small></span>',
    '<span class="scene-spark" aria-hidden="true"></span>',
    '</button>'
  ].join("");
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
  const powerLabel = light.is_on === true ? "On" : light.is_on === false ? "Off" : "Unknown";
  const onActive = light.is_on === true ? " active" : "";
  const offActive = light.is_on === false ? " active" : "";
  const powerButtons = light.controllable
    ? '<div class="ambient-actions"><button class="command primary' + onActive + '" data-ambient-command="on" data-ambient-id="' + escapeHtml(light.id) + '">On</button><button class="command' + offActive + '" data-ambient-command="off" data-ambient-id="' + escapeHtml(light.id) + '">Off</button></div>'
    : '<div class="ambient-actions"><button class="command" disabled>Setup needed</button></div>';
  const brightnessControl = light.controllable && light.capabilities?.brightness
    ? '<div class="ambient-control-row"><i class="ti ti-sun"></i><input type="range" min="1" max="100" value="80" data-ambient-brightness data-ambient-id="' + escapeHtml(light.id) + '"><span>80%</span></div>'
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

/* ── Environment sensors (Govee cloud thermo-hygrometers) ── */
async function loadEnvironmentSensors() {
  const payload = await requestJson("/api/environment-sensors");
  latestEnvironmentSensors = payload.sensors || [];
  renderEnvironmentSensors();
  renderDevicesOverview();
}

function environmentSensorCard(sensor) {
  const temp = sensor.temperature != null ? `${sensor.temperature}<small>°C</small>` : "–";
  const hum  = sensor.humidity != null ? `${sensor.humidity}<small>%</small>` : "–";
  const note = sensor.note
    ? `<p class="sdc-sub">${escapeHtml(sensor.note)}</p>`
    : "";

  return `<article class="sdc-card" data-device-id="${escapeHtml(sensor.name)}">
    <div class="sdc-header">
      <div>
        <h3 class="sdc-name">${escapeHtml(sensor.name)}</h3>
        <p class="sdc-sub">${escapeHtml([sensor.room, sensor.model].filter(Boolean).join(" · ") || "Govee")}</p>
      </div>
      <span class="sdc-badge">${sensor.online ? "ONLINE" : "OFFLINE"}</span>
    </div>
    <div class="sdc-gauges-row">
      <div class="sdc-gauge"><i class="ti ti-temperature"></i><span class="gauge-value">${temp}</span></div>
      <div class="sdc-gauge"><i class="ti ti-droplet"></i><span class="gauge-value">${hum}</span></div>
    </div>
    ${note}
  </article>`;
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

    return `
      <div class="device-card new-style ${isOn ? "on" : ""}"
           draggable="true"
           data-host="${device.host}"
           data-category="${escapeHtml(device.category || "")}">
        <div class="device-top">
          <div>
            <h3 class="device-name">${escapeHtml(device.name)}${device.provider === "matter" ? '<span class="matter-badge">MATTER</span>' : ""}</h3>
            <p class="device-status">${escapeHtml(device.room || "")}</p>
          </div>
          <div class="device-top-right">
            ${deviceDragHandle(device.host)}
            <button class="rocker ${isOn ? "on" : ""}"
              data-command="${nextCmd}"
              data-host="${device.host}"
              type="button"
              aria-pressed="${isOn}"
              aria-label="${isOn ? "Turn off" : "Turn on"} ${escapeHtml(device.name)}">
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
          <span style="color:${isOn ? "var(--t-accent)" : "var(--t-text-dim2)"}">
            ${isOn ? "ON" : "OFF"}
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
    const brightness  = device.brightness ?? (isOn ? 100 : 10);
    const dimLocked   = dimmable && isDimLocked(device.host);

    return `
      <div class="device-card new-style ${isOn ? "on" : ""}"
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
            <p class="device-status">${escapeHtml(device.room || "")}</p>
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
              aria-label="${isOn ? "Turn off" : "Turn on"} ${escapeHtml(device.name)}">
              <div class="rocker-pad"></div>
            </button>
          </div>
        </div>
        <div class="dial-center dim-control-row">
          ${buildDimControlDial(brightness, isOn, dimmable)}
        </div>
        <div class="device-footer">
          <span>${plug ? "TODAY" : (dimmable ? "DIM" : "FIXED")}</span>
          <span style="color:${isOn ? "var(--t-accent)" : "var(--t-text-dim2)"}">
            ${isOn ? "ON" : "OFF"}
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
  if (mode !== "environment" && mode !== "sensors") return readings;
  return readings.filter((reading) => {
    const key = sensorCapabilityKey(reading);
    if (key === "battery") return true;
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
  return mode === "environment" ? "environment" : "tuya";
}

function visibleSensorGroups(mode) {
  const visible = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  const groupId = sensorTileGroupId(mode);
  return groupSensorDevices(visible)
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
      const aAlert = a.readings.some(
        (d) => isAlertDetected(d) && !String(d.category || "").includes("battery")
      );
      const bAlert = b.readings.some(
        (d) => isAlertDetected(d) && !String(d.category || "").includes("battery")
      );
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
  const hasAlert = alertDevices.some((d) => isAlertDetected(d));

  // Gauge columns (numeric sensors)
  const gauges = [];

  if (tempDev) {
    const val = readingMetricNumber(tempDev);
    if (Number.isFinite(val)) {
      const pct = Math.min(100, Math.max(0, ((val - 16) / (30 - 16)) * 100));
      gauges.push(`<div class="sdc-reading">
        ${thermoGaugeSVG(val, pct)}
        <div class="sdc-val"><span class="sdc-num">${val.toFixed(1)}</span><span class="sdc-unit">°C</span></div>
        <div class="sdc-label">${tempComfortLabel(val)}</div>
      </div>`);
    }
  }

  if (humDev) {
    const val = readingMetricNumber(humDev);
    if (Number.isFinite(val)) {
      gauges.push(`<div class="sdc-reading">
        ${dropletGaugeSVG(val, val, humDev.id)}
        <div class="sdc-val"><span class="sdc-num">${Math.round(val)}</span><span class="sdc-unit">%</span></div>
        <div class="sdc-label">${humidComfortLabel(val)}</div>
      </div>`);
    }
  }

  if (illumDev) {
    const val = readingMetricNumber(illumDev);
    if (Number.isFinite(val)) {
      const pct = Math.min(100, (val / 1000) * 100);
      gauges.push(`<div class="sdc-reading">
        ${sunGaugeSVG(val, pct)}
        <div class="sdc-val"><span class="sdc-num">${Math.round(val)}</span><span class="sdc-unit">lx</span></div>
        <div class="sdc-label">${lxComfortLabel(val)}</div>
      </div>`);
    }
  }

  // Alert / binary-sensor status rows
  const alertRows = [];
  if (occDev) {
    const det = isAlertDetected(occDev);
    alertRows.push(`<div class="sdc-status-row">
      <span class="sdc-dot ${det ? "sdc-dot-alert" : "sdc-dot-clear"}"></span>
      <span class="sdc-status-lbl${det ? " is-alert" : ""}">${det ? "MOTION DETECTED" : "ALL CLEAR"}</span>
    </div>`);
  }
  if (doorDev) {
    const det = isAlertDetected(doorDev);
    alertRows.push(`<div class="sdc-status-row">
      <span class="sdc-dot ${det ? "sdc-dot-alert" : "sdc-dot-clear"}"></span>
      <span class="sdc-status-lbl${det ? " is-alert" : ""}">${det ? "OPEN" : "CLOSED"}</span>
    </div>`);
  }
  if (moistDev) {
    const det = isAlertDetected(moistDev);
    alertRows.push(`<div class="sdc-status-row">
      <span class="sdc-dot ${det ? "sdc-dot-alert" : "sdc-dot-clear"}"></span>
      <span class="sdc-status-lbl${det ? " is-alert" : ""}">${det ? "LEAK DETECTED" : "DRY"}</span>
    </div>`);
  }
  if (smokeDev) {
    const det = isAlertDetected(smokeDev);
    alertRows.push(`<div class="sdc-status-row">
      <span class="sdc-dot ${det ? "sdc-dot-alert" : "sdc-dot-clear"}"></span>
      <span class="sdc-status-lbl${det ? " is-alert" : ""}">${det ? "SMOKE DETECTED" : "NORMAL"}</span>
    </div>`);
  }
  if (tamperDev) {
    const det = isAlertDetected(tamperDev);
    alertRows.push(`<div class="sdc-status-row">
      <span class="sdc-dot ${det ? "sdc-dot-alert" : "sdc-dot-clear"}"></span>
      <span class="sdc-status-lbl${det ? " is-alert" : ""}">${det ? "TAMPER ALERT" : "SECURE"}</span>
    </div>`);
  }
  if (problemDev) {
    const det = isAlertDetected(problemDev);
    alertRows.push(`<div class="sdc-status-row">
      <span class="sdc-dot ${det ? "sdc-dot-alert" : "sdc-dot-clear"}"></span>
      <span class="sdc-status-lbl${det ? " is-alert" : ""}">${det ? "PROBLEM" : "ONLINE"}</span>
    </div>`);
  }

  // Light control (Tuya LED strips exposed as HA lights)
  let lightHtml = "";
  if (lightDev) {
    lightHtml = `<div class="sdc-light-row">
      <i class="ti ti-bulb" style="color:${lightDev.is_on ? "var(--t-glow)" : "var(--t-text-dim2)"}"></i>
      <span>${lightDev.is_on ? "On" : "Off"}</span>
      <button class="rocker ${lightDev.is_on ? "on" : ""} sdc-rocker"
        data-tuya-command="${lightDev.is_on ? "off" : "on"}"
        data-device-id="${escapeHtml(lightDev.id)}"
        data-device-source="${lightDev.source || "direct"}"
        type="button"><div class="rocker-pad"></div></button>
    </div>`;
  }

  // Battery strip
  let battHtml = "";
  if (battDev) {
    const bPct = Number(battDev.state);
    if (Number.isFinite(bPct)) {
      const color = bPct > 50 ? "var(--t-glow)" : bPct > 20 ? "#FFB400" : "var(--t-alert)";
      const icon  = bPct > 75 ? "ti-battery-4" : bPct > 50 ? "ti-battery-3" : bPct > 25 ? "ti-battery-2" : "ti-battery-1";
      battHtml = `<div class="sdc-battery">
        <i class="ti ${icon}" style="color:${color}"></i>
        <span style="color:${color}">${Math.round(bPct)}%</span>
      </div>`;
    }
  }

  const subtitle = sensorDeviceSubtitle(readings);

  return `<article class="sdc-card${hasAlert ? " sdc-card-alert" : ""}" data-device-id="${escapeHtml(name)}">
    <div class="sdc-header">
      <div>
        <h3 class="sdc-name">${escapeHtml(name)}</h3>
        <p class="sdc-sub">${escapeHtml(subtitle)}</p>
      </div>
      <span class="sdc-badge">${capN > 1 ? `${capN}-IN-1` : readings[0]?.type || "Sensor"}</span>
    </div>
    ${gauges.length ? `<div class="sdc-gauges-row">${gauges.join("")}</div>` : ""}
    ${alertRows.length ? `<div class="sdc-alert-rows">${alertRows.join("")}</div>` : ""}
    ${lightHtml}
    ${battHtml}
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

  const alertGroupCount = groups.filter((g) =>
    g.readings.some((d) => isAlertDetected(d) && !String(d.category || "").includes("battery"))
  ).length;

  const banner = alertGroupCount
    ? `<div class="sdc-alert-banner"><i class="ti ti-alert-triangle"></i> ${alertGroupCount} device${alertGroupCount > 1 ? "s" : ""} need${alertGroupCount > 1 ? "" : "s"} attention</div>`
    : "";

  tuyaGrid.innerHTML = banner + groups.map((g) => renderSensorDeviceCard(g, "sensors")).join("");
  renderDevicesOverview();
  renderEnvironmentSensors();
  renderForeignKinds("tuya", ["sensor"], "#tuyaGrid");
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
      indoorTemp.textContent = `${Math.round(first.temperature)}${u}`;
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
  const host = window.location.hostname || "192.168.0.176";
  return `http://${host}:8123/lovelace/default_view`;
}

/* ── Weather ── */
function weatherHeaderIcon(code) {
  const num = Number(code);
  if ([0, 1].includes(num)) return "ti-sun";
  if ([2, 3, 45, 48].includes(num)) return "ti-cloud";
  if (num >= 51 && num < 80) return "ti-cloud-rain";
  return "ti-cloud";
}

function setHeaderWeatherUnavailable(message) {
  if (headerWeather) headerWeather.title = message || "Weather is not configured yet.";
  if (weatherIcon) weatherIcon.className = "ti ti-cloud";
  if (weatherTemp) weatherTemp.textContent = "--°C";
  if (weatherCondition) weatherCondition.textContent = "Weather unavailable";
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

  if (weatherIcon) weatherIcon.className = "ti " + icon;
  if (weatherTemp) weatherTemp.textContent = tempDisplay;
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
  cameraCount.textContent    = String(allCameras.length);
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
      return `<iframe class="camera-media camera-player" src="${liveUrl}" title="${camera.name} live WebRTC view" allow="autoplay; fullscreen; microphone"></iframe>`;
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
  area.innerHTML = [...notifMap.values()].map((n) => {
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
  }).join("");
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
  if (type === "window") return `<svg width="16" height="16" viewBox="0 0 22 22"><rect x="3" y="3" width="16" height="16" rx="1" fill="none" stroke="${color}" stroke-width="1.5"/><line x1="11" y1="3" x2="11" y2="19" stroke="${color}" stroke-width="1.5"/><line x1="3" y1="11" x2="19" y2="11" stroke="${color}" stroke-width="1.5"/></svg>`;
  return `<svg width="16" height="16" viewBox="0 0 22 22"><circle cx="11" cy="11" r="2.2" fill="${color}"/><circle cx="11" cy="11" r="6" fill="none" stroke="${color}" stroke-width="1.3" opacity="0.45"/></svg>`;
}

function renderAlarmSection(payload = latestAlarmData) {
  const panel = document.querySelector("#alarmPanel");
  if (!panel) return;

  const haState = payload?.panel?.entity_id ? normalizeAlarmPanelState(payload.panel.state) : null;
  const displayState = haState || alarmState;
  const STATE_COLOR = { disarmed: null, arming: "#F2B84B", home: "#F2B84B", away: "#7ED9A0", alarm: null };
  const shieldColor = displayState === "alarm" ? "var(--t-alert)" : STATE_COLOR[displayState];
  const pulsing     = displayState === "alarm" || displayState === "arming";

  const statusText =
    displayState === "disarmed" ? "Disarmed" :
    displayState === "arming"   ? (haState ? "Arming" : `Arming ${alarmPending === "home" ? "Home" : "Away"} in ${alarmCountdown}s`) :
    displayState === "home"     ? "Armed · Home" :
    displayState === "away"     ? "Armed · Away" :
    "SOS ALARM ACTIVE";

  const modes = [
    { id: "disarmed", label: "DISARM",   iconColor: "var(--t-text-dim2)",
      icon: `<svg width="18" height="18" viewBox="0 0 22 22"><rect x="5" y="10" width="12" height="9" rx="2" fill="none" stroke="${alarmState==="disarmed"?"var(--t-accent)":"var(--t-text-dim2)"}" stroke-width="1.6"/><path d="M7.5 10V7a3.5 3.5 0 016.5-1.8" fill="none" stroke="${alarmState==="disarmed"?"var(--t-accent)":"var(--t-text-dim2)"}" stroke-width="1.6" stroke-linecap="round"/><circle cx="11" cy="14.2" r="1.3" fill="${alarmState==="disarmed"?"var(--t-accent)":"var(--t-text-dim2)"}"/></svg>`,
      activeClass: "active-disarm" },
    { id: "home",     label: "ARM HOME",
      icon: `<svg width="18" height="18" viewBox="0 0 22 22"><path d="M3 11L11 4l8 7" fill="none" stroke="${alarmState==="home"||alarmPending==="home"?"#F2B84B":"var(--t-text-dim2)"}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M5.5 9.5V18h11V9.5" fill="none" stroke="${alarmState==="home"||alarmPending==="home"?"#F2B84B":"var(--t-text-dim2)"}" stroke-width="1.6" stroke-linejoin="round"/><rect x="9.3" y="12.5" width="3.4" height="5.5" fill="none" stroke="${alarmState==="home"||alarmPending==="home"?"#F2B84B":"var(--t-text-dim2)"}" stroke-width="1.4"/></svg>`,
      activeClass: "active-home" },
    { id: "away",     label: "ARM AWAY",
      icon: `<svg width="16" height="18" viewBox="0 0 18 20"><path d="M9 1 L17 4 V10 C17 15 13.5 18.3 9 19.5 C4.5 18.3 1 15 1 10 V4 Z" fill="none" stroke="${alarmState==="away"||alarmPending==="away"?"#7ED9A0":"var(--t-text-dim2)"}" stroke-width="1.6" stroke-linejoin="round"/></svg>`,
      activeClass: "active-away" },
  ];

  const modesHtml = modes.map((m) => {
    const isActive = (displayState === m.id) || (!haState && displayState === "arming" && alarmPending === m.id);
    return `<button class="arm-mode-btn ${isActive ? m.activeClass : ""}" data-arm-mode="${m.id}">
      ${m.icon}
      <span class="arm-mode-label">${m.label}</span>
    </button>`;
  }).join("");

  const alarmZones = payload?.zones?.length ? payload.zones : ALARM_ZONES;
  /* Tiles rather than rows, matching the temperature card: a zone list is a
     grid of small facts, and rows wasted the card's width while making each
     entry too small to read at a glance. Breached zones lead - when something
     is open, that is the only part of this card anyone is reading. */
  const zonesSorted = [...alarmZones].sort((a, b) => {
    const ab = (a.state === "open" || a.state === "motion") ? 0 : 1;
    const bb = (b.state === "open" || b.state === "motion") ? 0 : 1;
    return ab - bb || String(a.name).localeCompare(String(b.name));
  });
  const zonesHtml = zonesSorted.map((z) => {
    const breached = z.state === "open" || z.state === "motion";
    const unknown  = z.state === "unknown";
    const color    = breached ? "var(--t-alert)" : "var(--t-text-dim2)";
    const statusTxt = z.type === "motion" ? (breached ? "Motion" : "Clear") : (breached ? "Open" : "Closed");
    return `<div class="zone-tile${breached ? " breached" : ""}${unknown ? " unknown" : ""}"
                 title="${escapeHtml(z.name)} — ${statusTxt}">
      <span class="zone-tile-icon">${zoneIconSVG(z.type, breached)}</span>
      <span class="zone-tile-state" style="color:${color}">${statusTxt}</span>
      <span class="zone-tile-name">${escapeHtml(z.name)}</span>
    </div>`;
  }).join("");
  const breachedCount = zonesSorted.filter((z) => z.state === "open" || z.state === "motion").length;
  /* The count belongs next to the label, not buried in the tiles: it answers
     "is anything open?" without reading every tile. */
  const zonesLabel = alarmZones.length
    ? `ZONES <span class="alarm-zone-count${breachedCount ? " breached" : ""}">${
         breachedCount ? `${breachedCount} open` : "all clear"}</span>`
    : "ZONES";

  const disarmSilenceBtn = displayState === "alarm"
    ? `<button class="disarm-silence-btn" data-arm-mode="disarmed">DISARM TO SILENCE</button>` : "";

  const haControls = payload?.controls || [];
  const haControlsHtml = haControls.length ? `
    <span class="alarm-section-label">HOME ASSISTANT PANEL</span>
    <div class="alarm-ha-controls">
      ${haControls.map((control) => {
        const isOn = control.state === "on";
        const stateText = formatStatus(control.state || control.status || "unknown");
        const action = isOn ? "off" : "on";
        const button = control.controllable
          ? `<button class="command ${isOn ? "" : "primary"}" data-ha-command="${action}" data-ha-entity-id="${escapeHtml(control.entity_id)}">${isOn ? "Turn off" : "Turn on"}</button>`
          : `<span class="camera-note">${escapeHtml(stateText)}</span>`;
        return `<div class="alarm-ha-row">
          <div><strong>${escapeHtml(control.name)}</strong><small>${escapeHtml(stateText)}</small></div>
          ${button}
        </div>`;
      }).join("")}
    </div>` : "";

  const panelName = payload?.panel?.name || "Local alarm panel";

  const alarmBadgeEl = document.querySelector("#alarmBadge");
  if (alarmBadgeEl) alarmBadgeEl.textContent = displayState === "alarm" ? "!" : displayState === "disarmed" ? "–" : "ON";

  panel.innerHTML = `
    <div class="alarm-shield-wrap">
      ${alarmShieldSVG(shieldColor, pulsing)}
      <span class="alarm-status-text ${displayState === "alarm" ? "alarm-active" : ""}">${statusText}</span>
      <span class="alarm-source-text">${escapeHtml(panelName)}</span>
    </div>
    <div class="arm-mode-grid">${modesHtml}</div>
    ${disarmSilenceBtn}
    ${haControlsHtml}
    <span class="alarm-section-label">${zonesLabel}</span>
    <div class="zone-tile-grid">${zonesHtml || `<div class="home-empty">No zones reported</div>`}</div>
    <div class="siren-row">
      <span class="siren-label">SIREN</span>
      <button class="siren-test-btn ${sirenTesting ? "testing" : ""}" id="sirenTestBtn">
        ${sirenTesting ? "TESTING…" : "TEST"}
      </button>
    </div>
    <button class="sos-btn" id="sosTriggerBtn">SOS — TRIGGER ALARM</button>`;
}

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
  latestTuyaDevices   = tuyaData.devices;
  latestAlarmData     = alarmData;
  latestSwitchDevices = deviceData.devices;
  latestMatterDevices = matterData.devices || [];
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
};

function areaSlug(name) {
  return String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/* Flatten every dashboard device into {key, kind, name, room, data} entries.
   Keys must stay stable across refreshes — they anchor area assignments. */
function collectHomeInventory() {
  const inventory = [];

  for (const device of [...latestSwitchDevices, ...latestMatterDevices]) {
    inventory.push({
      key: `dev:${device.host}`,
      kind: device.category === "smart_plug" ? "plug" : "light",
      name: device.name,
      room: device.room || "",
      data: device,
    });
  }

  const visibleSensors = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  for (const group of groupSensorDevices(visibleSensors)) {
    inventory.push({
      key: `sensor:${areaSlug(group.name)}`,
      kind: "sensor",
      name: group.name,
      room: group.readings[0]?.room || "",
      data: group,
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

  const areaCountBadge = document.querySelector("#areaCount");
  if (areaCountBadge) areaCountBadge.textContent = String(shown.length);
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

/* Every temperature source on the dashboard: ecobee remote sensors plus any
   Tuya/HA sensor group that reports a temperature reading. */
function homeTempSources() {
  const sources = [];
  for (const th of latestThermostats) {
    const unit = th.temperature_unit?.includes("F") ? "°F" : "°C";
    for (const sensor of th.sensors || []) {
      if (sensor.temperature == null) continue;
      sources.push({
        id: `ecobee:${th.id}:${sensor.name}`,
        name: sensor.name,
        temp: Math.round(Number(sensor.temperature)),
        unit,
        occupied: sensor.occupied,
      });
    }
  }
  const visibleSensors = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  for (const group of groupSensorDevices(visibleSensors)) {
    const reading = group.readings.find((r) => String(r.category || "").includes("temperature"));
    if (!reading) continue;
    const value = readingMetricNumber(reading);
    if (!Number.isFinite(value)) continue;
    sources.push({ id: `tuya:${areaSlug(group.name)}`, name: group.name, temp: Math.round(value), unit: "°" });
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

/* Temperature sensors card: ecobee remote sensors + Tuya/HA readings as
   thermometer tiles — drag to rearrange, sized by the card (CSS container
   queries handle the scaling). */
const HOME_TEMP_ORDER_KEY = "home_temp_sensor_order";

function orderedTempSources(sources) {
  try {
    const saved = JSON.parse(localStorage.getItem(HOME_TEMP_ORDER_KEY) || "[]");
    if (Array.isArray(saved) && saved.length) {
      const pos = new Map(saved.map((id, index) => [id, index]));
      return [...sources].sort(
        (a, b) => (pos.has(a.id) ? pos.get(a.id) : Infinity) - (pos.has(b.id) ? pos.get(b.id) : Infinity)
      );
    }
  } catch {}
  return sources;
}

function renderHomeTempSensors() {
  const body = document.querySelector("#homeTempSensorsBody");
  if (!body) return;

  const sources = homeTempSources();
  const chosen = selectedTempSensorIds(sources);
  const tiles = orderedTempSources(sources.filter((s) => chosen.has(s.id))).map((s) => `
    <div class="temp-sensor-tile" draggable="true" data-temp-tile-id="${escapeHtml(s.id)}"
         title="${escapeHtml(s.name)} — drag to rearrange">
      ${s.occupied != null ? `<span class="thermo-occ-dot${s.occupied ? " occupied" : ""}" title="${s.occupied ? "Occupied" : "Unoccupied"}"></span>` : ""}
      <span class="temp-tile-icon" style="color:${tempRangeColor(s.temp)}"><i class="ti ti-temperature" aria-hidden="true"></i></span>
      <span class="temp-tile-value mono" style="color:${tempRangeColor(s.temp)}">${s.temp}${s.unit}</span>
      <span class="temp-tile-name">${escapeHtml(s.name)}</span>
    </div>`).join("");

  renderHtml(body, sources.length
    ? (tiles ? `<div class="temp-tile-grid">${tiles}</div>` : `<div class="home-empty">No sensors selected — use the filter above</div>`)
    : `<div class="home-empty">No temperature sensors found</div>`);
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
}

/* Re-fit areas and climate live while their cards are resized. The sensors
   card scales through CSS container queries instead. */
(function initHomeFitObservers() {
  if (typeof ResizeObserver === "undefined") return;
  const observer = new ResizeObserver(() => {
    layoutAreaGrid();
    fitClimateBody();
  });
  const areasCard = document.querySelector(".home-areas.home-card");
  const climateCard = document.querySelector("#homeClimatePanel");
  if (areasCard) observer.observe(areasCard);
  if (climateCard) observer.observe(climateCard);
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
          <span class="mono home-picker-temp">${s.temp}${s.unit}</span>
        </label>`).join("")
    : `<div class="home-empty">No temperature sensors available</div>`;
}

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
  const camera = cameras.find((c) => cameraIdFor(c) === savedId) || cameras[0] || null;

  // Rebuilding the option list resets the dropdown, so leave it alone when
  // the cameras have not changed.
  renderHtml(select, cameras.map((c) => {
    const id = cameraIdFor(c);
    return `<option value="${escapeHtml(id)}"${camera && cameraIdFor(camera) === id ? " selected" : ""}>${escapeHtml(c.name || id)}</option>`;
  }).join(""));
  select.hidden = cameras.length === 0;

  if (!camera) {
    renderHtml(body, `<div class="home-empty">No cameras found</div>`);
    return;
  }
  const cameraId = cameraIdFor(camera);
  const live = activeCameraIds.has(cameraId);
  renderHtml(body, `
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
    </div>`);
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
  if (activeCameraIds.has(cameraId)) {
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


/* ── Bluetooth: music card on Home, scan/connect modal under Discovery ── */
let latestBluetooth = null;

async function refreshBluetooth() {
  latestBluetooth = await requestJson("/api/bluetooth/devices").catch(() => null);
  renderBluetoothCard();
  renderBtModalList();
}

/* Home card: playback placeholder that just reflects the connected speaker. */
function renderBluetoothCard() {
  const body = document.querySelector("#btDeviceList");
  if (!body) return;
  const devices = latestBluetooth?.status === "ok" ? latestBluetooth.devices || [] : [];
  const connected = devices.filter((device) => device.connected);
  const status = connected.length
    ? `Connected · ${connected.map((device) => escapeHtml(device.name)).join(", ")}`
    : "No speaker connected";
  body.innerHTML = `
    <div class="home-music-placeholder">
      <i class="ti ti-music" aria-hidden="true"></i>
      <div class="home-music-status">${status}</div>
      <small>Music playback coming soon — pair speakers via Discovery → Bluetooth</small>
    </div>`;
}

function renderBtModalList() {
  const list = document.querySelector("#btModalList");
  if (!list) return;
  if (!latestBluetooth) {
    list.innerHTML = `<div class="home-empty">Bluetooth status unavailable</div>`;
    return;
  }
  if (latestBluetooth.status !== "ok") {
    list.innerHTML = `<div class="home-empty">${escapeHtml(latestBluetooth.message || "Bluetooth unavailable")}</div>`;
    return;
  }
  const devices = latestBluetooth.devices || [];
  if (!devices.length) {
    list.innerHTML = `<div class="home-empty">No devices known yet — press Scan to discover speakers nearby.</div>`;
    return;
  }
  list.innerHTML = devices.map((device) => {
    const isAudio = /audio|headset|headphone|speaker/i.test(String(device.icon || ""));
    return `
      <div class="custom-device-row bt-device-row">
        <span class="assign-device-icon"><i class="ti ${isAudio ? "ti-music" : "ti-bluetooth"}"></i></span>
        <span class="custom-device-name">
          ${escapeHtml(device.name)}
          <small class="bt-mac mono">${device.type ? `${escapeHtml(device.type)} · ` : ""}${escapeHtml(device.mac)}</small>
        </span>
        ${device.connected ? `<span class="bt-status">Connected</span>` : ""}
        <button class="command ${device.connected ? "" : "primary"}" type="button"
          data-bt-action="${device.connected ? "disconnect" : "connect"}"
          data-bt-mac="${escapeHtml(device.mac)}">
          ${device.connected ? "Disconnect" : "Connect"}
        </button>
      </div>`;
  }).join("");
}

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-bt-action]");
  if (!btn) return;
  const mac = btn.dataset.btMac;
  const action = btn.dataset.btAction;
  btn.disabled = true;
  btn.textContent = action === "connect" ? "Connecting…" : "Disconnecting…";
  try {
    const result = await requestJson(`/api/bluetooth/devices/${encodeURIComponent(mac)}/${action}`, { method: "POST" });
    logActivity(result.message || `Bluetooth ${action} ${result.status}`, result.status === "ok" ? "normal" : "warn");
  } catch (error) {
    console.error(error);
    logActivity("Bluetooth action failed", "error");
  }
  await refreshBluetooth();
});

(function initBluetoothUi() {
  const modal = document.querySelector("#btModal");
  const openModal = () => {
    if (modal) modal.hidden = false;
    refreshBluetooth().catch(console.error);
  };
  const closeModal = () => { if (modal) modal.hidden = true; };

  document.querySelector("#btScanNav")?.addEventListener("click", openModal);
  document.querySelector("#closeBtModal")?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });

  const scanBtn = document.querySelector("#btModalScan");
  scanBtn?.addEventListener("click", async () => {
    const list = document.querySelector("#btModalList");
    scanBtn.disabled = true;
    if (list) list.innerHTML = `<div class="home-empty"><i class="ti ti-loader-2 spin"></i> Scanning for ~8 seconds…</div>`;
    try {
      latestBluetooth = await requestJson("/api/bluetooth/scan", { method: "POST" });
      logActivity("Bluetooth scan finished");
    } catch (error) {
      console.error(error);
      latestBluetooth = null;
    }
    renderBluetoothCard();
    renderBtModalList();
    scanBtn.disabled = false;
  });
  refreshBluetooth().catch(console.error);
})();

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

function customCardRowHtml(item) {
  const icon = AREA_KIND_ICONS[item.kind] || "ti-cpu";
  let value = "";
  let goto = "tuya";
  if (item.kind === "thermostat") {
    value = item.data.temperature != null ? `${Math.round(Number(item.data.temperature))}°` : "--";
    goto = "climate";
  } else if (item.kind === "camera") {
    value = "view";
    goto = "cameras";
  } else if (item.kind === "sensor") {
    const reading = item.data.readings.find((r) => String(r.category || "").includes("temperature"));
    const num = reading ? readingMetricNumber(reading) : NaN;
    value = Number.isFinite(num) ? `${Math.round(num)}°`
      : item.data.readings.some(isAlertDetected) ? "Alert" : "OK";
  }
  return `
    <div class="custom-device-row" data-goto-view="${goto}" role="button" tabindex="0"
         title="Open the related view">
      <span class="assign-device-icon"><i class="ti ${icon}"></i></span>
      <span class="custom-device-name">${escapeHtml(item.name)}</span>
      <span class="custom-device-value mono">${escapeHtml(String(value))}</span>
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
    const tiles = items
      .filter((item) => item.kind === "light" || item.kind === "plug")
      .map(customCardTileHtml)
      .join("");
    const rows = items
      .filter((item) => item.kind !== "light" && item.kind !== "plug")
      .map(customCardRowHtml)
      .join("");
    renderHtml(
      el.querySelector("[data-custom-body]"),
      (tiles ? `<div class="custom-tile-grid">${tiles}</div>` : "") + rows ||
        `<div class="home-empty">No devices linked — click the pencil to pick some.</div>`
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
    await loadDevices();
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
const HOME_GRID_COLS = 12;
const HOME_GRID_ROW = 40;
const HOME_GRID_GAP = 16;

/* Three columns of four on the grid:

     Weather   Camera         Areas
     Climate   Temperatures
     Music

   Only applies to a browser with no saved layout - an existing one is left
   alone, and Reset Layout is what adopts this. */
const DEFAULT_HOME_LAYOUT = {
  weather:     { x: 1, y: 1,  w: 4, h: 5 },
  climate:     { x: 1, y: 6,  w: 4, h: 9 },
  bluetooth:   { x: 1, y: 15, w: 4, h: 6 },
  camera:      { x: 5, y: 1,  w: 4, h: 7 },
  tempsensors: { x: 5, y: 8,  w: 4, h: 6 },
  areas:       { x: 9, y: 1,  w: 4, h: 12 },
  zigbeehealth:{ x: 9, y: 13, w: 4, h: 5 },
};

function loadHomeLayout() {
  try { return JSON.parse(localStorage.getItem(HOME_CARD_LAYOUT_KEY) || "{}") || {}; } catch { return {}; }
}

function saveHomeLayout(layout) {
  try { localStorage.setItem(HOME_CARD_LAYOUT_KEY, JSON.stringify(layout)); } catch {}
}

/* Below 1100px the layout falls back to a flex column (see CSS); fit logic
   switches to natural heights there. */
function homeGridMode() {
  const grid = document.querySelector("#homeCardGrid");
  return !!grid && getComputedStyle(grid).display === "grid";
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
  weather: "Weather",
  camera: "Camera",
  climate: "Climate",
  bluetooth: "Music",
  areas: "Areas",
  zigbeehealth: "Zigbee",
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
  layout[id] = { x: 1, y: bottom, w: size.w, h: size.h };
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

function applyHomeCardLayout() {
  const grid = document.querySelector("#homeCardGrid");
  if (!grid) return;
  const layout = loadHomeLayout();
  const hidden = loadHiddenHomeCards();
  let changed = false;
  for (const card of grid.querySelectorAll(".home-card")) {
    const id = card.dataset.homeCard;
    // A hidden card keeps its stored layout; it is only taken off the screen.
    card.hidden = hidden.has(id);
    if (card.hidden) continue;
    let lay = layout[id] || DEFAULT_HOME_LAYOUT[id];
    if (!lay) {
      // New (custom) card: park it below everything currently placed.
      const placed = Object.entries(DEFAULT_HOME_LAYOUT)
        .filter(([key]) => !layout[key])
        .map(([, l]) => l)
        .concat(Object.values(layout));
      const bottom = placed.reduce((max, l) => Math.max(max, l.y + l.h), 1);
      lay = { x: 1, y: bottom, w: 4, h: 6 };
      layout[id] = lay;
      changed = true;
    }
    setCardCell(card, lay);
  }
  if (changed) saveHomeLayout(layout);
}

function homeGridPitch(grid) {
  const cellW = (grid.clientWidth - HOME_GRID_GAP * (HOME_GRID_COLS - 1)) / HOME_GRID_COLS;
  return { pitchX: cellW + HOME_GRID_GAP, pitchY: HOME_GRID_ROW + HOME_GRID_GAP };
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
    if (!card || !homeGridMode()) return;
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
      lay.y = Math.max(1, originY + dy);
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
    if (!card || !homeGridMode()) return;
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
      lay.h = Math.max(3, startH + Math.round((point.clientY - startY) / pitchY));
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

  const sections = [];
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
        <div class="device-grid">${sensors.map((g) => renderSensorDeviceCard(g, "sensors")).join("")}</div>
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
        <div class="device-grid">${environment.map(environmentSensorCard).join("")}</div>
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
    try { localStorage.setItem(HOME_CAMERA_KEY, event.target.value); } catch {}
    renderHomeCamera();
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
  if (options.skipRefresh !== true) await loadDevices();
}

async function sendTuyaCommand(deviceId, command) {
  apiStatus.textContent = "Sending";
  await requestJson(`/api/tuya/devices/${deviceId}/commands/${command}`, { method: "POST" });
  await loadDevices();
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
  await loadDevices();
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
    btn.classList.toggle("active", btn.dataset.view === viewName);
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
    const brightness = locked ? 100 : (parseInt(card.dataset.brightness, 10) || (isNowOn ? 100 : 10));
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

/* ── Home card tile drag ordering (custom-card lights + temp sensors) ──
   Both grids flow left-to-right, so insertion position follows the pointer's
   horizontal side of the hovered tile. */
const TILE_DRAG_SELECTOR = ".custom-light-tile[data-tile-key], .temp-sensor-tile[data-temp-tile-id]";

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

function saveTempTileOrderFromDom() {
  const ids = [...document.querySelectorAll("#homeTempSensorsBody .temp-sensor-tile")]
    .map((tile) => tile.dataset.tempTileId);
  try { localStorage.setItem(HOME_TEMP_ORDER_KEY, JSON.stringify(ids)); } catch {}
}

function persistTileOrder(tile) {
  if (tile.matches(".custom-light-tile")) {
    saveCustomTileOrderFromDom(tile.closest(".home-custom-card"));
    logActivity("Card switches rearranged");
  } else {
    saveTempTileOrderFromDom();
    logActivity("Temperature sensors rearranged");
  }
}

document.addEventListener("dragstart", (event) => {
  const tile = event.target.closest?.(TILE_DRAG_SELECTOR);
  if (!tile) return;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", tile.dataset.tileKey || tile.dataset.tempTileId || "");
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
  const grid = target?.closest(".custom-tile-grid, .temp-tile-grid");
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
  const grid = target?.closest(".custom-tile-grid, .temp-tile-grid");
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
  select.innerHTML = railButtonEls().map((btn) => {
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
    // Keep the row from hijacking clicks meant for the select.
    select.addEventListener("click", (event) => event.stopPropagation());
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
  const host = window.location.hostname || "192.168.0.234";
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

/* Zigbee health on the Home view.

   A dead bridge is silent: every Zigbee device just stops updating, and nothing
   on screen says why. One replug went unnoticed for 66 minutes. This tile states
   the coordinator's state outright, and separates "offline" (the bridge is down,
   act on it) from "unknown" (we cannot reach Home Assistant to ask, which is a
   different problem). */
async function loadZigbeeHealthCard() {
  const body = document.querySelector("#homeZigbeeBody");
  const stateEl = document.querySelector("#homeZigbeeState");
  const metaEl = document.querySelector("#homeZigbeeMeta");
  if (!body) return;

  const render = (state, text, meta) => {
    body.dataset.state = state;
    if (stateEl) stateEl.textContent = text;
    if (metaEl) metaEl.textContent = meta || "";
  };

  let info;
  try {
    info = await requestJson("/api/zigbee/bridge");
  } catch (error) {
    render("unknown", "Unknown", "Dashboard could not reach the bridge API");
    return;
  }

  if (!info.available) {
    render("unknown", "Unknown", "Home Assistant unreachable, or MQTT not set up");
    return;
  }

  const since = _zigbeeSince(info.connection_changed);
  const version = info.version ? `Zigbee2MQTT ${info.version}` : "Zigbee2MQTT";

  if (info.connected === true) {
    render("online", "Online", since ? `${version} · up ${since}` : version);
  } else if (info.connected === false) {
    render("offline", "Offline", since ? `Down for ${since} · ${version}` : version);
  } else {
    render("unknown", "Unknown", `${version} · no connection state published`);
  }
}

document.querySelector("#homeZigbeeOpen")?.addEventListener("click", () => {
  activateView("zigbee");
});

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
  const badge = document.querySelector("#matterServerStatus");
  if (!badge) return;
  badge.textContent = online ? "Online" : "Offline";
  badge.className = "discovery-server-badge " + (online ? "online" : "offline");
}

function _renderMatterDeviceList(devices) {
  const list = document.querySelector("#matterDeviceList");
  if (!list) return;
  if (!devices.length) {
    list.innerHTML = '<p style="font-size:13px;color:var(--muted)">No Matter devices paired yet.</p>';
    return;
  }
  list.innerHTML = devices.map((d) => `
    <div class="discovery-device-row">
      <div>
        <div class="discovery-device-row-name">${escapeHtml(d.name)}</div>
        ${d.room ? `<div class="discovery-device-row-room">${escapeHtml(d.room)}</div>` : ""}
      </div>
      <button class="discovery-remove-btn"
              data-matter-remove="${d.node_id}"
              title="Remove ${escapeHtml(d.name)}"
              type="button">
        <i class="ti ti-trash"></i>
      </button>
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

async function loadBuildInfo() {
  if (!buildBadge) return;
  try {
    const response = await fetch(`/static/build_info.json?ts=${Date.now()}`);
    if (!response.ok) return;
    const info = await response.json();
    if (info.build !== undefined) buildBadge.textContent = `Build #${info.build}`;
  } catch {}
}

loadBuildInfo();

loadDevices().catch((error) => {
  apiStatus.textContent = "Error";
  logActivity("Failed to load devices", "error");
  console.error(error);
});

loadZigbeeHealthCard().catch((error) => console.error(error));

/* Kept even once the live stream below is connected: this is the reconciliation
   pass that repairs anything the stream missed while the laptop was asleep or the
   connection was down, and the only thing refreshing sources Home Assistant does
   not report (the TP-Link poll, camera reachability). */
/* Auto-refresh every 60 s */
setInterval(() => {
  loadDevices().catch(console.error);
  /* Refreshed on the same cycle so an outage that starts while the dashboard is
     already open still surfaces, rather than only on reload. */
  loadZigbeeHealthCard().catch(console.error);
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
  }, LIVE_REFRESH_DEBOUNCE_MS);
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
