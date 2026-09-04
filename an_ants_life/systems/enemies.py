"""
Enemy spawning and movement.

Intruders arrive from the map edges, more often as border pressure
rises, then act on their own agenda: warriors drive at the nest,
raiders rob food and run, predators hunt foragers in the open.
"""
from __future__ import annotations
import math
import random
from typing import Optional, Tuple

from enemies.kinds import EnemyKind
from enemies.enemy import Enemy, make_enemy
from colony.history import EventKind

_KINDS = (EnemyKind.WARRIOR, EnemyKind.RAIDER, EnemyKind.PREDATOR)


def _random_edge_point(cfg) -> Tuple[float, float]:
    edge = random.choice(("top", "bottom", "left", "right"))
    if edge == "top":
        return random.uniform(0, cfg.WORLD_W), 0.0
    if edge == "bottom":
        return random.uniform(0, cfg.WORLD_W), float(cfg.WORLD_H)
    if edge == "left":
        return 0.0, random.uniform(0, cfg.WORLD_H)
    return float(cfg.WORLD_W), random.uniform(0, cfg.WORLD_H)


def _spawn_point(state, cfg) -> Optional[Tuple[float, float]]:
    """A passable point on the border, or None if the border is walled
    off here. Spawning inside rock would strand the enemy permanently -
    it cannot slide out of a tile it is already stuck in - and it would
    hold an enemy slot forever."""
    for _ in range(24):
        x, y = _random_edge_point(cfg)
        if state.terrain.passable(x, y):
            return x, y
    return None


def _steer(state, cfg, enemy: Enemy, tx: float, ty: float, dt: float) -> None:
    terrain = state.terrain
    if state.t >= enemy.detour_until_t:
        dx, dy = tx - enemy.x, ty - enemy.y
        d = math.hypot(dx, dy) + 1e-6
        speed = enemy.speed * terrain.speed_mult(enemy.x, enemy.y)
        enemy.vx, enemy.vy = (dx / d) * speed, (dy / d) * speed

    px = min(max(0.0, enemy.x + enemy.vx * dt), cfg.WORLD_W)
    py = min(max(0.0, enemy.y + enemy.vy * dt), cfg.WORLD_H)
    (enemy.x, enemy.y), blocked = terrain.move(enemy.x, enemy.y, px, py)

    if blocked:
        if state.t >= enemy.detour_until_t:
            enemy.detour_side = 1 if (enemy.id & 1) else -1
        turned = terrain.deflect(enemy.x, enemy.y, enemy.vx, enemy.vy, dt, enemy.detour_side)
        if turned is not None:
            enemy.vx, enemy.vy, enemy.detour_side = turned
            enemy.detour_until_t = state.t + cfg.TERRAIN_DETOUR_SECONDS
            px = min(max(0.0, enemy.x + enemy.vx * dt), cfg.WORLD_W)
            py = min(max(0.0, enemy.y + enemy.vy * dt), cfg.WORLD_H)
            (enemy.x, enemy.y), _ = terrain.move(enemy.x, enemy.y, px, py)


def _nearest_ant(state, enemy: Enemy, radius: float):
    best, best_sq = None, radius * radius
    for ant in state.colony.ants:
        dx, dy = ant.x - enemy.x, ant.y - enemy.y
        d_sq = dx * dx + dy * dy
        if d_sq < best_sq:
            best_sq, best = d_sq, ant
    return best


def _nearest_food(state, enemy: Enemy) -> Optional[object]:
    best, best_sq = None, float("inf")
    for src in state.world.food_sources:
        if src.amount <= 0:
            continue
        dx, dy = src.x - enemy.x, src.y - enemy.y
        d_sq = dx * dx + dy * dy
        if d_sq < best_sq:
            best_sq, best = d_sq, src
    return best


def _pick_kind(cfg) -> EnemyKind:
    return random.choices(
        _KINDS,
        weights=[cfg.ENEMY_WEIGHT_WARRIOR, cfg.ENEMY_WEIGHT_RAIDER, cfg.ENEMY_WEIGHT_PREDATOR],
    )[0]


def update_enemies(state, dt: float) -> None:
    cfg = state.cfg
    if not cfg.ENEMY_ENABLE:
        return

    pressure = state.colony.emergency.get("territory_pressure", 0.0)
    spawn_chance = (cfg.ENEMY_BASE_SPAWN_CHANCE_PER_SEC * dt
                    * (1.0 + pressure * cfg.ENEMY_SPAWN_PRESSURE_MULT))

    if len(state.enemies) < cfg.ENEMY_MAX_ALIVE and random.random() < spawn_chance:
        point = _spawn_point(state, cfg)
        if point is None:
            return
        x, y = point
        kind = _pick_kind(cfg)
        enemy = make_enemy(cfg, state._next_enemy_id, kind, x, y)
        state._next_enemy_id += 1
        state.enemies.append(enemy)
        state.history.emit(
            state.t, state.tick, EventKind.ENEMY_SPAWN,
            {"enemy_id": enemy.id, "kind": kind.value, "x": round(x, 1), "y": round(y, 1)},
            cause="border_pressure",
            tags=["enemy"]
        )

    for enemy in state.enemies:
        if enemy.kind == EnemyKind.RAIDER:
            _update_raider(state, cfg, enemy, dt)
        elif enemy.kind == EnemyKind.PREDATOR:
            _update_predator(state, cfg, enemy, dt)
        else:
            _steer(state, cfg, enemy, state.nest_pos[0], state.nest_pos[1], dt)

    if any(e.escaped for e in state.enemies):
        state.enemies = [e for e in state.enemies if not e.escaped]


def _update_raider(state, cfg, enemy: Enemy, dt: float) -> None:
    if enemy.fleeing:
        # Hauls the loot back to where it entered rather than bolting for
        # whichever edge is nearest - that run is what soldiers intercept.
        _steer(state, cfg, enemy, enemy.spawn_x, enemy.spawn_y, dt)
        if math.hypot(enemy.x - enemy.spawn_x, enemy.y - enemy.spawn_y) <= 1.0:
            enemy.escaped = True
            state.colony.metrics["food_stolen"] += enemy.carrying
            state.history.emit(
                state.t, state.tick, EventKind.ENEMY_ESCAPE,
                {"enemy_id": enemy.id, "amt": round(enemy.carrying, 1)},
                cause="raid_escaped",
                impact={"food_lost": float(enemy.carrying)},
                tags=["enemy", "raid"]
            )
        return

    src = _nearest_food(state, enemy)
    if src is None:
        # Nothing left in the field - go rob the colony's own stores.
        nest_x, nest_y = state.nest_pos
        if math.hypot(enemy.x - nest_x, enemy.y - nest_y) <= cfg.RAIDER_STEAL_RADIUS:
            if _load_up(state, cfg, enemy, dt):
                taken = min(cfg.RAIDER_STEAL_AMOUNT, state.colony.food_store)
                state.colony.food_store -= taken
                _begin_flight(cfg, enemy, taken)
                _emit_steal(state, enemy, taken, "nest_stores")
        else:
            _steer(state, cfg, enemy, nest_x, nest_y, dt)
        return

    if math.hypot(enemy.x - src.x, enemy.y - src.y) <= cfg.RAIDER_STEAL_RADIUS:
        if _load_up(state, cfg, enemy, dt):
            taken = min(cfg.RAIDER_STEAL_AMOUNT, src.amount)
            src.amount -= taken
            _begin_flight(cfg, enemy, taken)
            _emit_steal(state, enemy, taken, "food_source")
    else:
        _steer(state, cfg, enemy, src.x, src.y, dt)


def _load_up(state, cfg, enemy: Enemy, dt: float) -> bool:
    """Hold the raider still while it loads. Returns True once full.

    This pause is the counterplay: it parks the raider next to the pile
    the colony's own foragers are working, long enough for them to answer.
    """
    enemy.vx = enemy.vy = 0.0
    enemy.steal_progress += dt
    return enemy.steal_progress >= cfg.RAIDER_STEAL_SECONDS


def _begin_flight(cfg, enemy: Enemy, taken: float) -> None:
    enemy.carrying = taken
    enemy.fleeing = True
    enemy.speed = cfg.RAIDER_SPEED * cfg.RAIDER_LADEN_SPEED_MULT


def _emit_steal(state, enemy: Enemy, amount: float, target: str) -> None:
    state.history.emit(
        state.t, state.tick, EventKind.ENEMY_STEAL,
        {"enemy_id": enemy.id, "amt": round(amount, 1), "target": target},
        cause="raid",
        impact={"food_at_risk": float(amount)},
        tags=["enemy", "raid"]
    )


def _update_predator(state, cfg, enemy: Enemy, dt: float) -> None:
    prey = _nearest_ant(state, enemy, cfg.PREDATOR_HUNT_RADIUS)
    if prey is not None:
        _steer(state, cfg, enemy, prey.x, prey.y, dt)
        return

    # No prey in range: prowl, holding a heading so it sweeps ground
    # instead of jittering in place.
    if enemy.vx or enemy.vy:
        heading = math.atan2(enemy.vy, enemy.vx) + random.uniform(-0.25, 0.25)
    else:
        heading = random.uniform(0, 2 * math.pi)
    _steer(state, cfg, enemy,
           enemy.x + math.cos(heading) * 20.0,
           enemy.y + math.sin(heading) * 20.0, dt)
