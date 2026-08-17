// An Ant's Life - live view. Polls /state and redraws the canvas.
"use strict";

const canvas = document.getElementById("world");
const ctx = canvas.getContext("2d");

// Palette (mirrors the CSS custom properties in index.html; canvas fills
// need raw RGB for alpha blending, so they're duplicated here as tuples).
const ROLE_COLOR = { WORKER: "#199e70", SCOUT: "#c98500", SOLDIER: "#9085e9" };
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

function drawAnts(ants, scaleX, scaleY) {
  for (const [x, y, role, carrying] of ants) {
    const px = x * scaleX, py = y * scaleY;
    ctx.beginPath();
    ctx.arc(px, py, carrying ? 2.6 : 1.9, 0, Math.PI * 2);
    ctx.fillStyle = ROLE_COLOR[role] || "#ffffff";
    ctx.fill();
    if (carrying) {
      ctx.beginPath();
      ctx.arc(px, py, 1.0, 0, Math.PI * 2);
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

  if (data.terrain) {
    ctx.drawImage(terrainLayer(data.terrain, canvas.width, canvas.height, scaleX, scaleY), 0, 0);
  }
  drawTerritory(data.territory, scaleX, scaleY);
  const ph = data.pheromones;
  // Ambient explored-area wash first, then supply routes on top of it.
  drawPheromoneChannel(ph.home, ph.cols, ph.rows, ph.cell, scaleX, scaleY, PHERO_HOME_RGB, 0.14, 2.0);
  drawPheromoneChannel(ph.food, ph.cols, ph.rows, ph.cell, scaleX, scaleY, PHERO_FOOD_RGB, 0.70, 0.15);
  drawNest(data.nest, scaleX, scaleY);
  drawFoodSources(data.food_sources, scaleX, scaleY);
  drawEnemies(data.enemies, scaleX, scaleY);
  drawAnts(data.ants, scaleX, scaleY);
  drawQueen(data.nest, data.queen, scaleX, scaleY);
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

function updateSidebar(data) {
  document.getElementById("tick-readout").textContent = `tick ${data.tick} · t ${data.t.toFixed(1)}s`;

  let workers = 0, scouts = 0, soldiers = 0;
  for (const [, , role] of data.ants) {
    if (role === "WORKER") workers++;
    else if (role === "SCOUT") scouts++;
    else if (role === "SOLDIER") soldiers++;
  }
  document.getElementById("n-worker").textContent = workers;
  document.getElementById("n-scout").textContent = scouts;
  document.getElementById("n-soldier").textContent = soldiers;

  document.getElementById("v-food").textContent = data.colony.food_store.toFixed(1);

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

  document.getElementById("m-deposits").textContent = data.metrics.food_deposits;
  document.getElementById("m-kills").textContent = data.metrics.enemy_kills;
  document.getElementById("m-lost").textContent = data.metrics.ants_killed;
  document.getElementById("m-born").textContent = data.metrics.ants_born;
  document.getElementById("m-raids").textContent = data.metrics.raids;

  document.getElementById("pause-btn").textContent = data.paused ? "Resume" : "Pause";

  const overlay = document.getElementById("game-over-overlay");
  if (data.game_over) {
    overlay.classList.add("show");
    document.getElementById("game-over-title").textContent =
      data.ending === "colony_extinct" ? "The Nest Falls Silent" : "The Queen Is Dead";
    document.getElementById("game-over-epitaph").textContent = data.ending_text || "";
    document.getElementById("game-over-sub").textContent =
      `Survived ${clockOf(data.t)} · ${data.saga.chapters.length + (data.chapter.active ? 1 : 0)} chapters · `
      + `${data.saga.milestones.length} milestones · ${data.metrics.enemy_kills} enemies killed`;
  } else {
    overlay.classList.remove("show");
  }
}

async function poll() {
  try {
    const res = await fetch("/state", { cache: "no-store" });
    const data = await res.json();
    render(data);
    updateSidebar(data);
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

document.getElementById("pause-btn").addEventListener("click", () => sendControl("pause_toggle"));
document.getElementById("restart-btn").addEventListener("click", () => sendControl("restart"));
document.getElementById("game-over-restart").addEventListener("click", () => sendControl("restart"));

poll();
setInterval(poll, 120);
