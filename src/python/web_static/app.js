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
const weatherIcon       = document.querySelector("#weatherIcon");
const weatherTemp       = document.querySelector("#weatherTemp");
const weatherCondition  = document.querySelector("#weatherCondition");
const weatherFeels      = document.querySelector("#weatherFeels");
const weatherHumidity   = document.querySelector("#weatherHumidity");
const weatherWind       = document.querySelector("#weatherWind");
const weatherPressure   = document.querySelector("#weatherPressure");
const weatherUv         = document.querySelector("#weatherUv");
const deviceCount       = document.querySelector("#deviceCount");
const onCount           = document.querySelector("#onCount");
const cameraCount       = document.querySelector("#cameraCount");
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

const railButtons = Array.from(document.querySelectorAll(".room-item[data-view]"));
const viewPanels  = Array.from(document.querySelectorAll(".view-panel[data-view-panel]"));

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
const activeCameraIds   = new Set();
let latestCameras       = [];
let latestTuyaDevices   = [];
let latestAlarmData     = null;
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

/* ── API helper ── */
async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
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

  wrap.addEventListener("pointerdown", (e) => {
    if (card.dataset.dimLocked === "true") return;
    const lv = levelFromPointer(e.clientX, e.clientY);
    if (lv === null) return;
    dragging = true;
    pendingLevel = lv;
    wrap.setPointerCapture(e.pointerId);
    updateDialLines(wrap, lv, card.classList.contains("on"));
    card.dataset.brightness = lv;
  });

  wrap.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const lv = levelFromPointer(e.clientX, e.clientY);
    if (lv === null) return;
    pendingLevel = lv;
    updateDialLines(wrap, lv, card.classList.contains("on"));
    card.dataset.brightness = lv;
  });

  wrap.addEventListener("pointerup", async () => {
    if (!dragging) return;
    dragging = false;
    const lv = pendingLevel;
    pendingLevel = null;
    if (lv !== null) {
      try {
        await sendBrightness(card.dataset.host, lv);
      } catch (err) {
        console.error("Brightness set failed:", err);
      }
    }
  });

  wrap.addEventListener("pointercancel", () => { dragging = false; pendingLevel = null; });
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
  const resp = await fetch("/api/devices/" + encodeURIComponent(host) + "/brightness", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level }),
  });
  if (resp.ok === false) throw new Error("Brightness set failed: " + resp.status);
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
function renderDevices(devices, cameras) {
  const lightDevices = devices.filter((d) => d.category === "light_switch");
  const plugDevices  = devices.filter((d) => d.category === "smart_plug");

  deviceCount.textContent    = String(devices.length);
  onCount.textContent        = String(devices.filter((d) => d.is_on === true).length);
  lightCount.textContent     = String(lightDevices.length);
  plugCount.textContent      = String(plugDevices.length);
  cameraTabCount.textContent = String(cameras.length);

  renderLightScenes(lightDevices);
  renderLightDragLock();
  renderDeviceGroup(lightGrid, applyDeviceOrder(lightDevices, "light_switch"), "No TP-Link light switches found. Run discovery on the Raspberry Pi first.");
  renderPlugSection(plugDevices);
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

function applyDeviceOrder(devices, category) {
  const order = savedDeviceOrder(category);
  if (order.length === 0) return devices;
  const indexByHost = new Map(order.map((host, index) => [host, index]));
  return [...devices].sort((a, b) => {
    const aIndex = indexByHost.has(String(a.host)) ? indexByHost.get(String(a.host)) : Number.MAX_SAFE_INTEGER;
    const bIndex = indexByHost.has(String(b.host)) ? indexByHost.get(String(b.host)) : Number.MAX_SAFE_INTEGER;
    return aIndex - bIndex;
  });
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
  const lights = payload?.lights || [];
  if (ambientCount) ambientCount.textContent = String(lights.length);
  if (!ambientGrid) return;
  if (lights.length === 0) {
    ambientGrid.innerHTML = '<div class="empty">No ambient lights configured yet. Add Govee/Lepro entries to configs/devices.local.yaml.</div>';
    return;
  }
  ambientGrid.innerHTML = lights.map(ambientLightCard).join("");
}

function ambientLightCard(light) {
  const providerLabel = light.provider === "govee_ble" ? "Govee Bluetooth" : light.provider === "alexa" ? "Alexa bridge" : light.provider;
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
    '<div><h3>' + escapeHtml(light.name) + '</h3><p>' + escapeHtml(light.room || light.model || "Ambient") + '</p></div>',
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
    plugGrid.innerHTML = '<div class="empty">No TP-Link smart plugs found. Run discovery on the Raspberry Pi first.</div>';
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
            <h3 class="device-name">${escapeHtml(device.name)}</h3>
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
            <h3 class="device-name">${escapeHtml(device.name)}</h3>
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

function renderSensorDeviceCard(group) {
  const { name } = group;
  const readings = expandSensorReadings(group.readings);
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
  const visibleDevices = devices.filter((d) => !isTuyaCamera(d));
  tuyaCount.textContent = String(visibleDevices.length);

  if (visibleDevices.length === 0) {
    tuyaGrid.innerHTML = '<div class="empty">No Tuya devices found from Home Assistant yet.</div>';
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

  const groups = groupSensorDevices(visibleDevices);

  const alertGroupCount = groups.filter((g) =>
    g.readings.some((d) => isAlertDetected(d) && !String(d.category || "").includes("battery"))
  ).length;

  const banner = alertGroupCount
    ? `<div class="sdc-alert-banner"><i class="ti ti-alert-triangle"></i> ${alertGroupCount} device${alertGroupCount > 1 ? "s" : ""} need${alertGroupCount > 1 ? "" : "s"} attention</div>`
    : "";

  tuyaGrid.innerHTML = banner + groups.map(renderSensorDeviceCard).join("");
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
const THERMO_ROOMS = [
  { id: "living",  name: "Living Room", temp: 21, occupied: true  },
  { id: "kitchen", name: "Kitchen",     temp: 20, occupied: false },
  { id: "bedroom", name: "Bedroom",     temp: 19, occupied: true  },
  { id: "office",  name: "Office",      temp: 22, occupied: true  },
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
  const ui   = thermoUIState.get(thermostatId);
  const wrap = document.querySelector(`.thermo-dial-wrap[data-thermo-dial="${thermostatId}"]`);
  if (!ui || !wrap) return;

  const MIN = 10, MAX = 32, SEGS = 40;
  const litSegs  = Math.round(((ui.target - MIN) / (MAX - MIN)) * SEGS);
  const arcColor = THERMO_MODE_COLORS[ui.mode] || "var(--t-text-dim2)";

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

  wrap.addEventListener("pointerdown", (e) => {
    dragging = true;
    wrap.setPointerCapture(e.pointerId);
    setFromPointer(e.clientX, e.clientY);
  });
  wrap.addEventListener("pointermove",  (e) => { if (dragging) setFromPointer(e.clientX, e.clientY); });
  wrap.addEventListener("pointerup",    () => { dragging = false; });
  wrap.addEventListener("pointercancel",() => { dragging = false; });
}

function renderThermostats(payload) {
  const thermostats = payload?.thermostats || [];
  thermostatCount.textContent = String(thermostats.length);

  if (thermostats.length > 0) {
    const first = thermostats[0];
    if (first.temperature != null) {
      const u = first.temperature_unit?.includes("F") ? "°F" : "°C";
      indoorTemp.textContent = `${Math.round(first.temperature)}${u}`;
    }
  }

  if (thermostats.length === 0) {
    thermostatGrid.innerHTML = `<div class="empty">${escapeHtml(payload?.message || "No Ecobee thermostats configured yet. Add them to configs/devices.local.yaml.")}</div>`;
    return;
  }

  const MODES_DEF = [
    { id: "heat", label: "HEAT", color: THERMO_MODE_COLORS.heat },
    { id: "cool", label: "COOL", color: THERMO_MODE_COLORS.cool },
    { id: "auto", label: "AUTO", color: THERMO_MODE_COLORS.auto },
    { id: "off",  label: "OFF",  color: null },
  ];

  thermostatGrid.innerHTML = thermostats.map((th) => {
    const ui      = getThermoUI(th);
    const current = th.temperature != null ? Math.round(Number(th.temperature)) : "--";
    const status  = th.status || payload.status || "unknown";
    const humidity = th.humidity != null ? `${th.humidity}%` : "--";

    const modeButtons = MODES_DEF.map((m) => {
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

    const roomRows = THERMO_ROOMS.map((r) => {
      const tColor = tempRangeColor(r.temp);
      return `<div class="thermo-room-row">
        <div class="thermo-room-left">
          <span class="thermo-occ-dot${r.occupied ? " occupied" : ""}"></span>
          <div>
            <p class="thermo-room-name">${r.name}</p>
            <p class="thermo-room-status">${r.occupied ? "Occupied" : "Empty"}</p>
          </div>
        </div>
        <span class="thermo-room-temp" style="color:${tColor}">${r.temp}°</span>
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
  }).join("");

  document.querySelectorAll(".thermo-dial-wrap").forEach(attachThermoDrag);
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
  if (weatherFeels) weatherFeels.textContent = "--°C";
  if (weatherHumidity) weatherHumidity.textContent = "--%";
  if (weatherWind) weatherWind.textContent = "--";
  if (weatherPressure) weatherPressure.textContent = "--";
  if (weatherUv) weatherUv.textContent = "--";
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

  if (headerWeather) headerWeather.title = (weather.condition || "Outdoor") + " · feels like " + feelsDisplay;
  if (weatherIcon) weatherIcon.className = "ti " + icon;
  if (weatherTemp) weatherTemp.textContent = tempDisplay;
  if (weatherCondition) weatherCondition.textContent = weather.condition || "Outdoor";
  if (weatherFeels) weatherFeels.textContent = feelsDisplay;
  if (weatherHumidity) weatherHumidity.textContent = humidityDisplay;
  if (weatherWind) weatherWind.textContent = windDisplay;
  if (weatherPressure) weatherPressure.textContent = pressureDisplay;
  if (weatherUv) weatherUv.textContent = uvDisplay;
  if (outdoorTemp) outdoorTemp.textContent = tempDisplay;

  const conditionEl = document.querySelector("#statCondition");
  if (conditionEl) conditionEl.textContent = weather.condition || "Outdoor";
}

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

async function cacheSnapshotsInBackground(cameras) {
  for (const camera of cameras) {
    if (!camera.view_url || activeCameraIds.has(cameraIdFor(camera))) continue;
    const cameraId = cameraIdFor(camera);
    try {
      const response = await fetch(camera.snapshot_url || snapshotUrlFor(camera));
      if (!response.ok) continue;
      const blob = await response.blob();
      await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          const dataUri = reader.result;
          saveCachedSnapshot(cameraId, dataUri);
          const img = cameraGrid.querySelector(`img[data-camera-snap="${CSS.escape(cameraId)}"]`);
          if (img) img.src = dataUri;
          resolve();
        };
        reader.onerror = resolve;
        reader.readAsDataURL(blob);
      });
    } catch {}
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

function applyCameraOrder(cameras) {
  const order = savedCameraOrder();
  if (order.length === 0) return cameras;
  const indexById = new Map(order.map((id, index) => [id, index]));
  return [...cameras].sort((a, b) => {
    const aIndex = indexById.has(cameraIdFor(a)) ? indexById.get(cameraIdFor(a)) : Number.MAX_SAFE_INTEGER;
    const bIndex = indexById.has(cameraIdFor(b)) ? indexById.get(cameraIdFor(b)) : Number.MAX_SAFE_INTEGER;
    return aIndex - bIndex;
  });
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
    <article class="camera-card" data-camera-id="${escapeHtml(cameraId)}" draggable="true">
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
      return `<iframe class="camera-media camera-player" src="${liveUrl}" title="${camera.name} live WebRTC view" allow="autoplay; fullscreen; microphone"></iframe>`;
    }
    if (liveType === "snapshot" || liveType === "mjpeg" || liveType === "doorbell") {
      const separator = liveUrl.includes("?") ? "&" : "?";
      return `<img class="camera-media" src="${liveUrl}${separator}ts=${Date.now()}" alt="${escapeHtml(camera.name)} live view" />`;
    }
    return `<video class="camera-media" src="${liveUrl}" controls muted playsinline></video>`;
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
  const zonesHtml = alarmZones.map((z) => {
    const breached = z.state === "open" || z.state === "motion";
    const color    = breached ? "var(--t-alert)" : "var(--t-text-dim2)";
    const statusTxt = z.type === "motion" ? (breached ? "Motion" : "Clear") : (breached ? "Open" : "Closed");
    return `<div class="zone-row">
      <div class="zone-left">${zoneIconSVG(z.type, breached)}<span class="zone-name">${escapeHtml(z.name)}</span></div>
      <div class="zone-right">
        <span class="zone-state" style="color:${color}">${statusTxt}</span>
        <span class="zone-time">· ${escapeHtml(z.time)}</span>
      </div>
    </div>`;
  }).join("");

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
    <span class="alarm-section-label">ZONES</span>
    <div class="zone-list">${zonesHtml}</div>
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

  const [deviceData, cameraData, tuyaData, weatherData, ecobeeData, homeAssistantData, alarmData] = await Promise.all([
    requestJson("/api/devices"),
    requestJson("/api/cameras"),
    requestJson("/api/tuya/devices"),
    requestJson("/api/weather"),
    requestJson("/api/ecobee/thermostats"),
    requestJson("/api/home-assistant/entities"),
    requestJson("/api/alarm"),
  ]);

  notifyDoorbellEvents(cameraData.cameras);

  latestCameras     = cameraData.cameras;
  latestTuyaDevices = tuyaData.devices;
  latestAlarmData   = alarmData;

  renderDevices(deviceData.devices, cameraData.cameras);
  renderTuyaDevices(tuyaData.devices);
  renderThermostats(ecobeeData);
  renderHomeAssistant(homeAssistantData);
  renderCameras(cameraData.cameras, tuyaData.devices);
  renderWeather(weatherData);
  renderAlarmSection(alarmData);

  if (statusDot) statusDot.classList.add("online");
  apiStatus.textContent = "Online";

  logActivity("Devices refreshed");

  cacheSnapshotsInBackground(cameraData.cameras).catch(console.error);
}

/* ── Send commands ── */
async function sendCommand(host, command, options = {}) {
  apiStatus.textContent = "Sending";
  await requestJson("/api/devices/" + host + "/commands/" + command, { method: "POST" });
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
  railButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  });
  viewPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === viewName);
  });
  document.body.classList.toggle("home-assistant-mode", viewName === "homeassistant");
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
    logActivity("Error toggling device", "error");
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
  const article = btn.closest("article");
  if (!article) return;
  applyThermoModeUI(article, id, btn.dataset.thermoMode);
});

document.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-thermo-fan]");
  if (!btn) return;
  const id  = btn.dataset.thermoId;
  const ui  = thermoUIState.get(id);
  if (!ui) return;
  ui.fan = btn.dataset.thermoFan;
  btn.closest("article")?.querySelectorAll(".thermo-fan-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.thermoFan === ui.fan);
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
  const article = btn.closest("article");
  article?.querySelectorAll(".thermo-preset-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.thermoPreset === preset.id);
  });
  applyThermoModeUI(article, id, preset.mode);
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
  if (activeCameraIds.has(cameraId)) {
    activeCameraIds.delete(cameraId);
  } else {
    activeCameraIds.add(cameraId);
  }
  const card = button.closest(".camera-card");
  card.querySelector(".camera-frame").innerHTML  = cameraMedia(camera) + cameraBatteryBadge(camera);
  card.querySelector(".camera-action").innerHTML = cameraAction(camera);
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
document.addEventListener("dragstart", (event) => {
  const card = event.target.closest(".camera-card[data-camera-id]");
  if (!card) return;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", card.dataset.cameraId || "");
  card.classList.add("dragging");
});

document.addEventListener("dragend", (event) => {
  const card = event.target.closest(".camera-card[data-camera-id]");
  if (!card) return;
  card.classList.remove("dragging");
  saveCameraOrderFromDom(); // dragend persistence
});

document.addEventListener("dragover", (event) => {
  const target = event.target.closest(".camera-card[data-camera-id]");
  const dragging = cameraGrid?.querySelector(".camera-card.dragging");
  if (!target || !dragging || target === dragging) return;
  event.preventDefault();
  const rect = target.getBoundingClientRect();
  const insertAfter = event.clientY > rect.top + rect.height / 2;
  cameraGrid.insertBefore(dragging, insertAfter ? target.nextSibling : target);
});

document.addEventListener("drop", (event) => {
  const target = event.target.closest(".camera-card[data-camera-id]");
  if (!target) return;
  event.preventDefault();
  saveCameraOrderFromDom();
  logActivity("Camera order saved");
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

/* Sidebar navigation */
railButtons.forEach((btn) => {
  btn.addEventListener("click", () => activateView(btn.dataset.view));
});

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
  if (closeBtn) { dismissNotification(closeBtn.dataset.notifClose); return; }

  const respondBtn = event.target.closest("button[data-notif-respond]");
  if (respondBtn) {
    const notif = notifMap.get(respondBtn.dataset.notifRespond);
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

/* ── Hold-to-talk ── */
document.addEventListener("pointerdown", (event) => {
  const btn = event.target.closest("button[data-doorbell-talk]");
  if (!btn) return;
  btn.querySelector(".live-ctrl-icon")?.classList.add("talking");
});
document.addEventListener("pointerup", (event) => {
  const btn = event.target.closest("button[data-doorbell-talk]");
  if (!btn) return;
  btn.querySelector(".live-ctrl-icon")?.classList.remove("talking");
});
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
renderAlarmSection();

loadDevices().catch((error) => {
  apiStatus.textContent = "Error";
  logActivity("Failed to load devices", "error");
  console.error(error);
});

/* Auto-refresh every 60 s */
setInterval(() => {
  loadDevices().catch(console.error);
}, 60_000);
