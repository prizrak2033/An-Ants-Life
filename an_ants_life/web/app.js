// An Ant's Life - live view. Polls /state and redraws the canvas.
"use strict";

const canvas = document.getElementById("world");
const ctx = canvas.getContext("2d");

// Palette (mirrors the CSS custom properties in index.html; canvas fills
// need raw RGB for alpha blending, so they're duplicated here as tuples).
const ROLE_COLOR = { WORKER: "#199e70", SCOUT: "#c98500", SOLDIER: "#9085e9" };
const ENEMY_COLOR = "#e66767";
const FOOD_COLOR = "#fab219";
const CLAIMED_COLOR = "#3987e5";
const QUEEN_COLOR = "#ffffff";

const DIVERGING_BLUE = [57, 135, 229];   // friendly territory
const DIVERGING_RED = [230, 103, 103];   // enemy territory
const DIVERGING_GRAY = [56, 56, 53];     // contested / neutral
const PHERO_FOOD_RGB = [57, 135, 229];   // blue, sequential
const PHERO_HOME_RGB = [217, 89, 38];    // orange, sequential

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
      ctx.fillStyle = divergingColor(v);
      ctx.globalAlpha = 0.5;
      ctx.fillRect(cx * cw, cy * ch, cw + 1, ch + 1);
    }
  }
  ctx.globalAlpha = 1;
}

function drawPheromoneChannel(grid, cols, rows, cell, scaleX, scaleY, rgb) {
  const cw = cell * scaleX, ch = cell * scaleY;
  const [r, g, b] = rgb;
  for (let cx = 0; cx < cols; cx++) {
    for (let cy = 0; cy < rows; cy++) {
      const v = grid[cx * rows + cy];
      if (v < 0.05) continue;
      const alpha = Math.min(0.55, v / 3.0);
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
  ctx.fillStyle = ENEMY_COLOR;
  for (const [x, y] of enemies) {
    const px = x * scaleX, py = y * scaleY;
    ctx.beginPath();
    ctx.arc(px, py, 2.6, 0, Math.PI * 2);
    ctx.fill();
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

  drawTerritory(data.territory, scaleX, scaleY);
  drawPheromoneChannel(data.pheromones.food, data.pheromones.cols, data.pheromones.rows, data.pheromones.cell, scaleX, scaleY, PHERO_FOOD_RGB);
  drawPheromoneChannel(data.pheromones.home, data.pheromones.cols, data.pheromones.rows, data.pheromones.cell, scaleX, scaleY, PHERO_HOME_RGB);
  drawNest(data.nest, scaleX, scaleY);
  drawFoodSources(data.food_sources, scaleX, scaleY);
  drawEnemies(data.enemies, scaleX, scaleY);
  drawAnts(data.ants, scaleX, scaleY);
  drawQueen(data.nest, data.queen, scaleX, scaleY);
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

  document.getElementById("chapter-banner").textContent = data.chapter.active ? data.chapter.title : "A quiet colony, no chapter underway.";

  const chronicleEl = document.getElementById("chronicle");
  chronicleEl.innerHTML = "";
  for (const line of data.chronicle.slice().reverse()) {
    const li = document.createElement("li");
    li.textContent = line;
    chronicleEl.appendChild(li);
  }

  document.getElementById("m-deposits").textContent = data.metrics.food_deposits;
  document.getElementById("m-kills").textContent = data.metrics.enemy_kills;
  document.getElementById("m-lost").textContent = data.metrics.ants_killed;
  document.getElementById("m-born").textContent = data.metrics.ants_born;
  document.getElementById("m-raids").textContent = data.metrics.raids;

  document.getElementById("pause-btn").textContent = data.paused ? "Resume" : "Pause";

  const overlay = document.getElementById("game-over-overlay");
  if (data.game_over) {
    overlay.classList.add("show");
    document.getElementById("game-over-sub").textContent =
      `Survived ${data.t.toFixed(0)}s · ${data.metrics.enemy_kills} enemies killed · ${data.metrics.ants_born} ants born`;
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
