// An Ant's Life - live view. Polls /state and redraws the canvas.
"use strict";

const canvas = document.getElementById("world");
const ctx = canvas.getContext("2d");

// Palette (mirrors the CSS custom properties in index.html; canvas fills
// need raw RGB for alpha blending, so they're duplicated here as tuples).
const ROLE_COLOR = { WORKER: "#199e70", SCOUT: "#c98500", SOLDIER: "#9085e9",
                     PRAETORIAN: "#e8e0c0" };
// Enemy kinds share the red "hostile" family so they read as threats at a
// glance, separated by shape and lightness rather than unrelated hues.
const ENEMY_COLOR = { WARRIOR: "#e66767", RAIDER: "#d55181", PREDATOR: "#a32222" };
const FOOD_COLOR = "#fab219";
const CLAIMED_COLOR = "#3987e5";
const QUEEN_COLOR = "#ffffff";

const DIVERGING_BLUE = [57, 135, 229];   // friendly territory
const DIVERGING_RED = [230, 103, 103];   // enemy territory
const DIVERGING_GRAY = [56, 56, 53];     // contested / neutral
// The territory layer already owns blue<->red, so trails take colors from
// outside that pair: gold ties the supply route to the food it carries,
// and explored ground is a neutral wash that reads as ground covered
// rather than as a third data series competing for attention.
const PHERO_FOOD_RGB = [250, 178, 25];   // gold - active supply route
const PHERO_HOME_RGB = [154, 164, 178];  // neutral - explored ground

// Terrain, indexed by the wire codes in world/terrain.py's _ORDER.
// Deliberately dark and low-chroma: this is the ground everything else is
// read against, so it has to describe the map without competing with the
// territory heatmap or the trails drawn on top of it. SOIL is null - it is
// the base surface and gets left unpainted.
const TERRAIN_FILL = [null, "#3a3125", "#243522", "#414147", "#123c4a"];

// Static for the life of a map, so it is rasterized once and blitted.
let terrainCache = { key: null, canvas: null };

function terrainLayer(terr, w, h, scaleX, scaleY) {
  const key = `${w}x${h}:${terr.tiles}`;
  if (terrainCache.key === key) return terrainCache.canvas;

  const off = document.createElement("canvas");
  off.width = w;
  off.height = h;
  const c = off.getContext("2d");
  const cw = terr.cell * scaleX, ch = terr.cell * scaleY;

  for (let cx = 0; cx < terr.cols; cx++) {
    for (let cy = 0; cy < terr.rows; cy++) {
      const code = terr.tiles.charCodeAt(cx * terr.rows + cy) - 48;
      const fill = TERRAIN_FILL[code];
      if (!fill) continue;
      c.fillStyle = fill;
      c.fillRect(cx * cw, cy * ch, cw + 1, ch + 1);
    }
  }
  terrainCache = { key, canvas: off };
  return off;
}

const DIRECTIVE_COLOR = { FORAGE: "#fab219", DEFEND: "#9085e9", EXPLORE: "#3987e5" };

// UI-only state. The server owns the simulation; this is just which tool
// the player has in hand and the last frame's data for hit-testing.
let activeTool = "none";
let lastFrame = null;
// Which overlays are drawn. The colony itself is never a layer - ants,
// enemies, food and the queen always render, since they are the game.
const layers = { terrain: true, territory: true, trails: true, directives: true };
// Sliders are player-owned while being dragged: echoing the server's
// value back into a control the user is holding fights their input.
let sliderHeld = null;
// Which finished colony the player has waved away, so the epitaph does
// not pop back on the next poll while they look over the final map.
let dismissedEnding = null;

const audio = new ColonyAudio();
// The mix is defined in config.py. Fetched once, since it is fixed for
// the session, and failure is survivable - audio.js carries matching
// defaults, so an unreachable route costs the server's values, not the
// sound. Nothing is audible until the sound button is pressed anyway,
// which leaves this ample time to land.
fetch("/audio-config")
  .then((r) => (r.ok ? r.json() : null))
  .then((cfg) => {
    applyAudioConfig(cfg);
    audio.setVolume(AUDIO_LEVELS.default_volume);
    volumeSlider.value = Math.round(AUDIO_LEVELS.default_volume * 100);
  })
  .catch(() => {});
// Sound follows the chronicle, which is already significance-filtered.
// Entries are keyed by timestamp so only genuinely new beats fire, and
// a fresh colony resets the mark rather than replaying its whole past.
let lastHeardT = -1;

function playNewEvents(data) {
  if (!audio.enabled) return;
  const entries = data.chronicle || [];
  if (lastHeardT < 0) {
    // First frame heard: adopt the present rather than sounding history.
    lastHeardT = entries.length ? entries[entries.length - 1].t : 0;
    return;
  }
  if (entries.length && entries[entries.length - 1].t < lastHeardT) {
    lastHeardT = entries[entries.length - 1].t;  // restarted or resumed
  }
  let newest = lastHeardT;
  for (const e of entries) {
    if (e.t > lastHeardT) {
      audio.event(e.kind);
      if (e.t > newest) newest = e.t;
    }
  }
  lastHeardT = newest;
}

function lerp(a, b, t) { return a + (b - a) * t; }

function divergingColor(v) {
  v = Math.max(-1, Math.min(1, v));
  const [r, g, b] = v >= 0
    ? [lerp(DIVERGING_GRAY[0], DIVERGING_BLUE[0], v), lerp(DIVERGING_GRAY[1], DIVERGING_BLUE[1], v), lerp(DIVERGING_GRAY[2], DIVERGING_BLUE[2], v)]
    : [lerp(DIVERGING_GRAY[0], DIVERGING_RED[0], -v), lerp(DIVERGING_GRAY[1], DIVERGING_RED[1], -v), lerp(DIVERGING_GRAY[2], DIVERGING_RED[2], -v)];
  return `rgb(${r | 0}, ${g | 0}, ${b | 0})`;
}

function drawTerritory(terr, scaleX, scaleY) {
  const cw = terr.cell * scaleX, ch = terr.cell * scaleY;
  for (let cx = 0; cx < terr.cols; cx++) {
    for (let cy = 0; cy < terr.rows; cy++) {
      const v = terr.grid[cx * terr.rows + cy];
      // Fade with how decided the cell is, instead of a flat wash. A
      // constant alpha painted neutral ground just as heavily as held
      // ground, which blanketed the whole map and buried the terrain
      // underneath; now contested ground shows the terrain through it.
      const strength = Math.abs(v);
      if (strength < 0.06) continue;
      ctx.fillStyle = divergingColor(v);
      ctx.globalAlpha = Math.min(0.55, strength * 0.62);
      ctx.fillRect(cx * cw, cy * ch, cw + 1, ch + 1);
    }
  }
  ctx.globalAlpha = 1;
}

// The two channels live on wildly different scales - only laden ants lay
// the sparse "food" supply route (peaks well under 1), while every
// searching ant lays "home" breadcrumbs continuously (peaks in the
// hundreds). Normalizing each against its own peak keeps both legible
// instead of one washing the map out and the other vanishing; `floor`
// stops a nearly-empty channel from amplifying noise to full strength.
function drawPheromoneChannel(grid, cols, rows, cell, scaleX, scaleY, rgb, maxAlpha, floor) {
  let peak = floor;
  for (let i = 0; i < grid.length; i++) {
    if (grid[i] > peak) peak = grid[i];
  }

  const cw = cell * scaleX, ch = cell * scaleY;
  const [r, g, b] = rgb;
  for (let cx = 0; cx < cols; cx++) {
    for (let cy = 0; cy < rows; cy++) {
      const v = grid[cx * rows + cy];
      if (v <= 0) continue;
      // gamma < 1 lifts mid-strength trails into visibility
      const alpha = maxAlpha * Math.pow(v / peak, 0.6);
      if (alpha < 0.012) continue;
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
      ctx.fillRect(cx * cw, cy * ch, cw + 1, ch + 1);
    }
  }
}

function drawNest(nest, scaleX, scaleY) {
  const px = nest[0] * scaleX, py = nest[1] * scaleY;
  const grad = ctx.createRadialGradient(px, py, 0, px, py, 26);
  grad.addColorStop(0, "rgba(255,255,255,0.16)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(px, py, 26, 0, Math.PI * 2);
  ctx.fill();
}

function drawFoodSources(sources, scaleX, scaleY) {
  for (const [x, y, amount, claimed] of sources) {
    if (amount <= 0) continue;
    const px = x * scaleX, py = y * scaleY;
    const r = 3 + Math.sqrt(amount) * 0.55;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = FOOD_COLOR;
    ctx.globalAlpha = 0.85;
    ctx.fill();
    ctx.globalAlpha = 1;
    if (claimed) {
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = CLAIMED_COLOR;
      ctx.stroke();
    }
  }
}

function drawEnemies(enemies, scaleX, scaleY) {
  for (const [x, y, kind, laden] of enemies) {
    const px = x * scaleX, py = y * scaleY;
    ctx.fillStyle = ENEMY_COLOR[kind] || ENEMY_COLOR.WARRIOR;

    if (kind === "PREDATOR") {
      // Bigger diamond: a predator is a single heavy threat, not one of a swarm.
      ctx.beginPath();
      ctx.moveTo(px, py - 4.4); ctx.lineTo(px + 4.4, py);
      ctx.lineTo(px, py + 4.4); ctx.lineTo(px - 4.4, py);
      ctx.closePath();
      ctx.fill();
    } else if (kind === "RAIDER") {
      ctx.beginPath();
      ctx.arc(px, py, 2.6, 0, Math.PI * 2);
      ctx.fill();
      if (laden) {
        // Gold ring marks a thief worth chasing - kill it and the food drops.
        ctx.beginPath();
        ctx.arc(px, py, 5.0, 0, Math.PI * 2);
        ctx.strokeStyle = FOOD_COLOR;
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }
    } else {
      ctx.beginPath();
      ctx.arc(px, py, 2.6, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

// Ants are the game, so they are drawn large enough to follow individually
// and ringed in dark so they stay readable on top of a bright trail or a
// saturated territory cell rather than dissolving into it.
function drawAnts(ants, scaleX, scaleY) {
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(0,0,0,0.62)";
  for (const [x, y, role, carrying] of ants) {
    const px = x * scaleX, py = y * scaleY;
    // Praetorians draw a touch larger: a handful of fixed guards ringing
    // the queen should be countable at a glance, since that count is
    // what the player is buying.
    const r = role === "PRAETORIAN" ? 3.9 : (carrying ? 4.0 : 3.2);
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = ROLE_COLOR[role] || "#ffffff";
    ctx.fill();
    ctx.stroke();
    if (carrying) {
      // A crumb of food, so a laden forager reads at a glance.
      ctx.beginPath();
      ctx.arc(px, py, 1.7, 0, Math.PI * 2);
      ctx.fillStyle = FOOD_COLOR;
      ctx.fill();
    }
  }
}

function drawQueen(nest, queen, scaleX, scaleY) {
  const px = nest[0] * scaleX, py = nest[1] * scaleY;
  const frac = queen.hp_max > 0 ? queen.hp / queen.hp_max : 0;
  ctx.beginPath();
  ctx.arc(px, py, 5, 0, Math.PI * 2);
  ctx.fillStyle = QUEEN_COLOR;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(px, py, 8, -Math.PI / 2, -Math.PI / 2 + frac * Math.PI * 2);
  ctx.strokeStyle = frac > 0.35 ? "#0ca30c" : "#d03b3b";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function render(data) {
  const scaleX = canvas.width / data.world.w;
  const scaleY = canvas.height / data.world.h;

  ctx.fillStyle = "#1a1a19";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (layers.terrain && data.terrain) {
    ctx.drawImage(terrainLayer(data.terrain, canvas.width, canvas.height, scaleX, scaleY), 0, 0);
  }
  if (layers.territory) drawTerritory(data.territory, scaleX, scaleY);
  if (layers.trails) {
    const ph = data.pheromones;
    // Ambient explored-area wash first, then supply routes on top of it.
    drawPheromoneChannel(ph.home, ph.cols, ph.rows, ph.cell, scaleX, scaleY, PHERO_HOME_RGB, 0.12, 2.0);
    drawPheromoneChannel(ph.food, ph.cols, ph.rows, ph.cell, scaleX, scaleY, PHERO_FOOD_RGB, 0.52, 0.15);
  }
  drawNest(data.nest, scaleX, scaleY);
  drawFoodSources(data.food_sources, scaleX, scaleY);
  drawEnemies(data.enemies, scaleX, scaleY);
  drawAnts(data.ants, scaleX, scaleY);
  drawQueen(data.nest, data.queen, scaleX, scaleY);
  if (layers.directives) drawDirectives(data.directives, scaleX, scaleY);
}

function drawDirectives(directives, scaleX, scaleY) {
  if (!directives) return;
  for (const d of directives) {
    const px = d.x * scaleX, py = d.y * scaleY;
    const color = DIRECTIVE_COLOR[d.kind] || "#ffffff";

    // Outer ring shrinks as the mark fades, so how much life a directive
    // has left is readable straight off the map.
    ctx.beginPath();
    ctx.arc(px, py, 7 + 9 * d.strength, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.25 + 0.45 * d.strength;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(px, py, 4.5, 0, Math.PI * 2);
    ctx.globalAlpha = 0.55 + 0.45 * d.strength;
    ctx.fillStyle = color;
    ctx.fill();

    ctx.globalAlpha = 1;
  }
}

function clockOf(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function renderChronicle(data) {
  const el = document.getElementById("chronicle");
  el.innerHTML = "";
  for (const entry of data.chronicle.slice().reverse()) {
    const li = document.createElement("li");
    if (entry.major) li.className = "major";
    const stamp = document.createElement("span");
    stamp.className = "stamp";
    stamp.textContent = clockOf(entry.t);
    li.appendChild(stamp);
    li.appendChild(document.createTextNode(entry.text));
    if (entry.repeat > 1) {
      const rep = document.createElement("span");
      rep.className = "repeat";
      rep.textContent = ` ×${entry.repeat}`;
      li.appendChild(rep);
    }
    el.appendChild(li);
  }
}

function renderSaga(data) {
  const el = document.getElementById("saga-chapters");
  el.innerHTML = "";

  const rows = data.saga.chapters.map((c) => ({
    title: c.title, meta: `${clockOf(c.started_t)} · ${Math.round(c.duration)}s`, ongoing: false,
  }));
  if (data.chapter.active) {
    rows.push({
      title: data.chapter.title,
      meta: `${clockOf(data.chapter.started_t ?? 0)} · now`,
      ongoing: true,
    });
  }

  if (rows.length === 0) {
    const p = document.createElement("div");
    p.id = "saga-empty";
    p.textContent = "The colony has no story yet.";
    el.appendChild(p);
  } else {
    for (const r of rows) {
      const li = document.createElement("li");
      if (r.ongoing) li.className = "ongoing";
      const t = document.createElement("span");
      t.className = "title";
      t.textContent = r.title;
      const m = document.createElement("span");
      m.className = "meta";
      m.textContent = r.meta;
      li.appendChild(t);
      li.appendChild(m);
      el.appendChild(li);
    }
  }

  const wrap = document.getElementById("saga-milestones-wrap");
  const ml = document.getElementById("saga-milestones");
  const stones = data.saga.milestones;
  wrap.style.display = stones.length ? "block" : "none";
  ml.innerHTML = "";
  for (const m of stones) {
    const li = document.createElement("li");
    const t = document.createElement("span");
    t.className = "title";
    t.textContent = `${clockOf(m.t)}  ${m.title}`;
    const d = document.createElement("span");
    d.className = "text";
    d.textContent = m.text;
    li.appendChild(t);
    li.appendChild(d);
    ml.appendChild(li);
  }
}

function renderDirectiveList(data) {
  const el = document.getElementById("directive-list");
  el.innerHTML = "";
  const items = data.directives || [];
  if (!items.length) {
    const p = document.createElement("div");
    p.id = "directive-empty";
    p.textContent = "No directives laid. The colony is on its own.";
    el.appendChild(p);
    return;
  }
  const share = data.policy ? Math.round((data.policy.defend_share || 0) * 100) : 50;
  for (const d of items) {
    const li = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = DIRECTIVE_COLOR[d.kind] || "#fff";
    const name = document.createElement("span");
    name.textContent = d.kind.charAt(0) + d.kind.slice(1).toLowerCase();
    if (d.kind === "DEFEND") {
      name.title = `Draws up to ${share}% of soldiers; the rest garrison the nest.`;
    }
    const where = document.createElement("span");
    where.className = "where";
    where.textContent = d.cap != null
      ? `${d.recruits}/${d.cap} ants`
      : `${Math.round(d.x)},${Math.round(d.y)}`;
    const fade = document.createElement("span");
    fade.className = "fade";
    const bar = document.createElement("i");
    bar.style.width = `${Math.round(d.strength * 100)}%`;
    fade.appendChild(bar);
    li.append(dot, name, where, fade);
    el.appendChild(li);
  }
}

function renderPolicy(data) {
  const p = data.policy;
  if (!p) return;

  const soldierPct = Math.round((p.auto_defense ? p.effective_soldier_target : p.soldier_target) * 100);
  document.getElementById("v-soldier-target").textContent = `${soldierPct}%`;
  if (sliderHeld !== "soldier") {
    document.getElementById("soldier-slider").value = Math.round(p.soldier_target * 100);
  }
  document.getElementById("soldier-note").textContent = p.auto_defense
    ? `Auto: rises with border pressure (now ${soldierPct}%).`
    : "Held at your setting.";
  document.getElementById("auto-defense").checked = p.auto_defense;

  document.getElementById("v-praetorian-target").textContent = p.praetorian_target;
  if (sliderHeld !== "praetorian") {
    document.getElementById("praetorian-slider").value = p.praetorian_target;
  }

  document.getElementById("v-scout-target").textContent = `${Math.round(p.scout_target * 100)}%`;
  if (sliderHeld !== "scout") {
    document.getElementById("scout-slider").value = Math.round(p.scout_target * 100);
  }

  const rally = document.getElementById("rally-btn");
  rally.textContent = p.rally ? "Recalled" : "Recall";
  rally.classList.toggle("tool", true);
  rally.classList.toggle("active", !!p.rally);
}

function updateSidebar(data) {
  document.getElementById("tick-readout").textContent = `tick ${data.tick} · t ${data.t.toFixed(1)}s`;
  document.getElementById("colony-name").textContent = data.colony_name || "";
  if (data.save_note) document.getElementById("save-note").textContent = data.save_note;

  let workers = 0, scouts = 0, soldiers = 0, praetorians = 0;
  for (const [, , role] of data.ants) {
    if (role === "WORKER") workers++;
    else if (role === "SCOUT") scouts++;
    else if (role === "SOLDIER") soldiers++;
    else if (role === "PRAETORIAN") praetorians++;
  }
  document.getElementById("n-worker").textContent = workers;
  document.getElementById("n-scout").textContent = scouts;
  document.getElementById("n-soldier").textContent = soldiers;
  document.getElementById("n-praetorian").textContent = praetorians;

  // Population against the world's food ceiling, plus whether the colony
  // is currently feeding itself. These are deliberately two readings: the
  // ceiling comes from world regen and no action changes it, while the
  // balance is a flow that says how today is going.
  const pop = data.colony.population;
  const capacity = data.colony.carrying_capacity || 0;
  const balance = data.colony.food_balance || 0;
  // Above the long-run line is only a problem if the colony is also
  // losing ground. Early on it lives off standing food and legitimately
  // runs well above the line while food piles up, and warning then was
  // just contradicting the balance shown beside it.
  const aboveLine = capacity > 0 && pop > capacity;
  const struggling = aboveLine && balance < 0;
  document.getElementById("v-capacity").textContent = `${pop} / ${Math.round(capacity)}`;
  const capBar = document.getElementById("bar-capacity");
  capBar.style.width = `${Math.min(100, capacity > 0 ? (pop / capacity) * 100 : 0)}%`;
  capBar.style.background = struggling ? "var(--critical)"
    : (aboveLine ? "var(--food)" : "var(--good)");
  document.getElementById("capacity-badge").style.display = struggling ? "inline-block" : "none";
  const sign = balance >= 0 ? "+" : "−";
  document.getElementById("capacity-note").innerHTML =
    (struggling ? "Past what this world can feed, and falling behind. "
      : aboveLine ? "Above the long-run line, living off standing food. " : "")
    + `Food balance <b style="color:${balance >= 0 ? "var(--good)" : "var(--critical)"}">`
    + `${sign}${Math.abs(balance).toFixed(2)}/s</b>`;

  document.getElementById("v-food").textContent = data.colony.food_store.toFixed(1);

  // The nest guard decides the game: every recorded colony death is the
  // queen killed with this at zero, so it gets stated plainly.
  const g = data.garrison || { home: 0, total: 0, floor: 0 };
  document.getElementById("v-garrison").textContent = `${g.home} / ${g.total}`;
  const bare = g.home === 0;
  const thin = !bare && g.home < g.floor;
  document.getElementById("garrison-badge").style.display = bare ? "inline-block" : "none";
  const gnote = document.getElementById("garrison-note");
  gnote.textContent = bare
    ? "Nothing stands between the queen and the next warrior."
    : thin ? `Only ${g.home} soldiers at the nest — thin.`
    : "Soldiers holding the nest.";
  gnote.style.color = bare ? "var(--critical)"
    : thin ? "var(--food)" : "var(--ink-muted)";

  const qhp = data.queen.hp, qhpMax = data.queen.hp_max;
  document.getElementById("v-queenhp").textContent = `${qhp}/${qhpMax}`;
  const qFrac = qhpMax > 0 ? qhp / qhpMax : 0;
  const qBar = document.getElementById("bar-queenhp");
  qBar.style.width = `${qFrac * 100}%`;
  qBar.style.background = qFrac > 0.35 ? "var(--good)" : "var(--critical)";

  document.getElementById("v-hunger").textContent = `${Math.round(data.colony.hunger * 100)}%`;
  document.getElementById("bar-hunger").style.width = `${data.colony.hunger * 100}%`;
  document.getElementById("famine-badge").style.display = data.colony.famine ? "inline-block" : "none";

  document.getElementById("v-stress").textContent = `${Math.round(data.colony.stress * 100)}%`;
  document.getElementById("bar-stress").style.width = `${data.colony.stress * 100}%`;

  document.getElementById("v-pressure").textContent = `${Math.round(data.colony.pressure * 100)}%`;
  document.getElementById("bar-pressure").style.width = `${data.colony.pressure * 100}%`;

  const ec = data.enemy_counts || {};
  document.getElementById("n-warrior").textContent = ec.WARRIOR || 0;
  document.getElementById("n-raider").textContent = ec.RAIDER || 0;
  document.getElementById("n-predator").textContent = ec.PREDATOR || 0;
  document.getElementById("m-stolen").textContent = (data.metrics.food_stolen || 0).toFixed(1);
  document.getElementById("m-recovered").textContent = (data.metrics.loot_recovered || 0).toFixed(1);

  document.getElementById("chapter-banner").textContent = data.chapter.active ? data.chapter.title : "A quiet colony, no chapter underway.";

  renderChronicle(data);
  renderSaga(data);
  renderDirectiveList(data);
  renderPolicy(data);

  document.getElementById("m-deposits").textContent = data.metrics.food_deposits;
  document.getElementById("m-kills").textContent = data.metrics.enemy_kills;
  document.getElementById("m-lost").textContent = data.metrics.ants_killed;
  document.getElementById("m-born").textContent = data.metrics.ants_born;
  document.getElementById("m-raids").textContent = data.metrics.raids;

  document.getElementById("pause-btn").textContent = data.paused ? "Resume" : "Pause";

  const overlay = document.getElementById("game-over-overlay");
  if (data.game_over) {
    if (dismissedEnding !== data.colony_name) overlay.classList.add("show");
    document.getElementById("game-over-title").textContent =
      data.ending === "colony_extinct" ? "The Nest Falls Silent" : "The Queen Is Dead";
    document.getElementById("game-over-epitaph").textContent = data.ending_text || "";
    document.getElementById("game-over-sub").textContent =
      `Survived ${clockOf(data.t)} · ${data.saga.chapters.length + (data.chapter.active ? 1 : 0)} chapters · `
      + `${data.saga.milestones.length} milestones · ${data.metrics.enemy_kills} enemies killed`;
  } else {
    overlay.classList.remove("show");
    dismissedEnding = null;
  }
}

async function poll() {
  try {
    const res = await fetch("/state", { cache: "no-store" });
    const data = await res.json();
    lastFrame = data;
    render(data);
    updateSidebar(data);
    audio.update(data);
    playNewEvents(data);
  } catch (err) {
    // server briefly unreachable (e.g. restarting); just retry next tick
  }
}

async function sendControl(action) {
  await fetch("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
}

function clockOfSeconds(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

// Saves and the archive are files on disk, not part of the live tick, so
// they are fetched on their own slower cadence rather than every frame.
async function refreshSaves() {
  try {
    const rows = await (await fetch("/saves", { cache: "no-store" })).json();
    const picker = document.getElementById("save-picker");
    const keep = picker.value;
    picker.innerHTML = '<option value="">— saved colonies —</option>';
    for (const r of rows) {
      const o = document.createElement("option");
      o.value = r.name;
      const who = r.colony ? `${r.colony} · ` : "";
      o.textContent = `${r.label} (${who}${clockOfSeconds(r.t)}${r.ending ? " · ended" : ""})`;
      picker.appendChild(o);
    }
    if ([...picker.options].some((o) => o.value === keep)) picker.value = keep;
  } catch (err) { /* server busy; try again next cycle */ }
}

async function refreshArchive() {
  try {
    const rows = await (await fetch("/archive", { cache: "no-store" })).json();
    const el = document.getElementById("archive-list");
    el.innerHTML = "";
    if (!rows.length) {
      const p = document.createElement("div");
      p.id = "archive-empty";
      p.textContent = "No colony has finished its story yet.";
      el.appendChild(p);
      return;
    }
    for (const r of rows.slice().reverse()) {
      const li = document.createElement("li");
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = r.colony || "A colony";
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${clockOfSeconds(r.duration)} · `
        + `${(r.chapters || []).length} chapters · ${(r.milestones || []).length} milestones`;
      li.append(name, meta);
      if (r.ending_text) {
        const ep = document.createElement("div");
        ep.className = "epitaph";
        ep.textContent = r.ending_text;
        li.appendChild(ep);
      }
      el.appendChild(li);
    }
  } catch (err) { /* server busy; try again next cycle */ }
}

async function send(payload) {
  await fetch("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// Says what a directive actually does, since none of them command ants
// directly and that is easy to misread as the tool having failed.
const TOOL_DETAIL = {
  FORAGE: "Recruits nearby idle workers, up to a limit — not the whole colony.",
  DEFEND: "Up to half the guard patrols here; the rest hold the nest.",
  EXPLORE: "Scouts range around here instead of home.",
  none: "",
};

function setTool(tool) {
  activeTool = tool;
  for (const b of document.querySelectorAll("button.tool[data-tool]")) {
    b.classList.toggle("active", b.dataset.tool === tool);
  }
  canvas.classList.toggle("placing", tool !== "none");
  document.getElementById("tool-detail").textContent = TOOL_DETAIL[tool] || "";
}

// Canvas is displayed scaled (max-width), so convert through its rect
// rather than assuming CSS pixels equal backing-store pixels.
function canvasToWorld(ev) {
  const rect = canvas.getBoundingClientRect();
  const w = lastFrame ? lastFrame.world.w : 120;
  const h = lastFrame ? lastFrame.world.h : 70;
  return {
    x: ((ev.clientX - rect.left) / rect.width) * w,
    y: ((ev.clientY - rect.top) / rect.height) * h,
  };
}

function directiveAt(world) {
  if (!lastFrame || !lastFrame.directives) return null;
  let best = null, bestD = 4.0; // world units
  for (const d of lastFrame.directives) {
    const dist = Math.hypot(d.x - world.x, d.y - world.y);
    if (dist < bestD) { bestD = dist; best = d; }
  }
  return best;
}

canvas.addEventListener("click", (ev) => {
  const world = canvasToWorld(ev);
  // Clicking an existing mark removes it, whatever tool is in hand -
  // otherwise a full board could only be cleared wholesale.
  const hit = directiveAt(world);
  if (hit) {
    send({ action: "remove_directive", id: hit.id });
    return;
  }
  if (activeTool === "none") return;
  send({ action: "place_directive", kind: activeTool, x: world.x, y: world.y });
});

for (const b of document.querySelectorAll("button.tool[data-tool]")) {
  b.addEventListener("click", () => setTool(b.dataset.tool));
}

function syncLayerButtons() {
  for (const b of document.querySelectorAll("button.layer[data-layer]")) {
    b.classList.toggle("active", !!layers[b.dataset.layer]);
  }
  if (lastFrame) render(lastFrame);
}

for (const b of document.querySelectorAll("button.layer[data-layer]")) {
  b.addEventListener("click", () => {
    layers[b.dataset.layer] = !layers[b.dataset.layer];
    syncLayerButtons();
  });
}
document.getElementById("layers-ants-only").addEventListener("click", () => {
  layers.terrain = layers.territory = layers.trails = false;
  layers.directives = true;
  syncLayerButtons();
});
document.getElementById("layers-all").addEventListener("click", () => {
  layers.terrain = layers.territory = layers.trails = layers.directives = true;
  syncLayerButtons();
});
document.getElementById("clear-directives")
  .addEventListener("click", () => send({ action: "clear_directives" }));

document.getElementById("rally-btn").addEventListener("click", () => {
  const on = !(lastFrame && lastFrame.policy && lastFrame.policy.rally);
  send({ action: "set_rally", on });
});

function wireSlider(id, key, label) {
  const el = document.getElementById(id);
  el.addEventListener("pointerdown", () => { sliderHeld = key; });
  el.addEventListener("input", () => {
    document.getElementById(label).textContent = `${el.value}%`;
  });
  const commit = () => {
    sliderHeld = null;
    send({ action: "set_policy", [key]: Number(el.value) / 100 });
  };
  el.addEventListener("change", commit);
  el.addEventListener("pointerup", commit);
}
wireSlider("soldier-slider", "soldier", "v-soldier-target");
wireSlider("scout-slider", "scout", "v-scout-target");

// A whole-number count rather than a percentage, so it gets its own wiring.
(function wirePraetorian() {
  const el = document.getElementById("praetorian-slider");
  el.addEventListener("pointerdown", () => { sliderHeld = "praetorian"; });
  el.addEventListener("input", () => {
    document.getElementById("v-praetorian-target").textContent = el.value;
  });
  const commit = () => {
    sliderHeld = null;
    send({ action: "set_policy", praetorian: Number(el.value) });
  };
  el.addEventListener("change", commit);
  el.addEventListener("pointerup", commit);
})();

document.getElementById("auto-defense").addEventListener("change", (ev) => {
  send({ action: "set_policy", auto_defense: ev.target.checked });
});

document.addEventListener("keydown", (ev) => {
  if (ev.target.tagName === "INPUT") return;
  const keys = { "1": "FORAGE", "2": "DEFEND", "3": "EXPLORE", "0": "none", "escape": "none" };
  const k = keys[ev.key.toLowerCase()];
  if (k !== undefined) setTool(k);
  if (ev.key.toLowerCase() === "p") sendControl("pause_toggle");
});

document.getElementById("pause-btn").addEventListener("click", () => sendControl("pause_toggle"));
document.getElementById("restart-btn").addEventListener("click", () => sendControl("restart"));
document.getElementById("game-over-restart").addEventListener("click", () => sendControl("restart"));
document.getElementById("game-over-dismiss").addEventListener("click", () => {
  dismissedEnding = lastFrame ? lastFrame.colony_name : null;
  document.getElementById("game-over-overlay").classList.remove("show");
});

document.getElementById("save-btn").addEventListener("click", async () => {
  const el = document.getElementById("save-name");
  const name = (el.value || "").trim() || (lastFrame && lastFrame.colony_name) || "colony";
  await send({ action: "save", name });
  el.value = "";
  setTimeout(refreshSaves, 400);
});
document.getElementById("load-btn").addEventListener("click", async () => {
  const name = document.getElementById("save-picker").value;
  if (!name) return;
  await send({ action: "load", name });
  setTimeout(() => { refreshSaves(); refreshArchive(); }, 400);
});
document.getElementById("delete-save-btn").addEventListener("click", async () => {
  const name = document.getElementById("save-picker").value;
  if (!name) return;
  await send({ action: "delete_save", name });
  setTimeout(refreshSaves, 400);
});

const soundBtn = document.getElementById("sound-btn");
const volumeSlider = document.getElementById("volume-slider");

soundBtn.addEventListener("click", async () => {
  if (audio.enabled) {
    audio.disable();
    soundBtn.textContent = "Sound off";
    soundBtn.classList.remove("active");
    volumeSlider.style.display = "none";
    return;
  }
  // Browsers only allow audio to start from a gesture, which is why this
  // lives on the button rather than running at load.
  const ok = await audio.enable();
  soundBtn.textContent = ok ? "Sound on" : "No audio";
  soundBtn.classList.toggle("active", ok);
  soundBtn.classList.add("tool");
  volumeSlider.style.display = ok ? "inline-block" : "none";
  lastHeardT = -1;  // adopt the present; don't replay what already happened
});

volumeSlider.addEventListener("input", () => {
  audio.setVolume(Number(volumeSlider.value) / 100);
});

setTool("none");
poll();
setInterval(poll, 120);
refreshSaves();
refreshArchive();
setInterval(refreshSaves, 6000);
setInterval(refreshArchive, 6000);
