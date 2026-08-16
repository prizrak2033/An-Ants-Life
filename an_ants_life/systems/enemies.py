"""
Enemy spawning and movement: red ants intrude from the map edges, more
often as border pressure rises, and advance toward the nest.
"""
from __future__ import annotations
import math
import random
from typing import Tuple

from enemies.red_ant import RedAnt
from colony.history import EventKind


def _spawn_point(cfg) -> Tuple[float, float]:
    edge = random.choice(("top", "bottom", "left", "right"))
    if edge == "top":
        return random.uniform(0, cfg.WORLD_W), 0.0
    if edge == "bottom":
        return random.uniform(0, cfg.WORLD_W), float(cfg.WORLD_H)
    if edge == "left":
        return 0.0, random.uniform(0, cfg.WORLD_H)
    return float(cfg.WORLD_W), random.uniform(0, cfg.WORLD_H)


def update_enemies(state, dt: float) -> None:
    cfg = state.cfg
    if not cfg.REDANT_ENABLE:
        return

    pressure = state.colony.emergency.get("territory_pressure", 0.0)
    spawn_chance = cfg.REDANT_BASE_SPAWN_CHANCE_PER_TICK * (1.0 + pressure * cfg.REDANT_SPAWN_PRESSURE_MULT)

    if len(state.enemies) < cfg.REDANT_MAX_ALIVE and random.random() < spawn_chance:
        x, y = _spawn_point(cfg)
        enemy = RedAnt(id=state._next_enemy_id, x=x, y=y, hp=cfg.REDANT_HP)
        state._next_enemy_id += 1
        state.enemies.append(enemy)
        state.history.emit(
            state.t, state.tick, EventKind.ENEMY_SPAWN,
            {"enemy_id": enemy.id, "x": round(x, 1), "y": round(y, 1)},
            cause="border_pressure",
            tags=["enemy"]
        )

    nest_x, nest_y = state.nest_pos
    for enemy in state.enemies:
        dx, dy = nest_x - enemy.x, nest_y - enemy.y
        d = math.hypot(dx, dy) + 1e-6
        enemy.vx, enemy.vy = (dx / d) * cfg.REDANT_SPEED, (dy / d) * cfg.REDANT_SPEED
        enemy.x += enemy.vx * dt
        enemy.y += enemy.vy * dt
