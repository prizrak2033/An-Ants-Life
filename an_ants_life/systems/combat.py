"""
Combat resolution: ants and red ants trade damage when within engage
range (subject to a per-unit cooldown), and enemies that reach the
queen's threat radius strike her directly.
"""
from __future__ import annotations
import math

from ants.roles import Role
from colony.history import EventKind


def _atk_for_role(cfg, role: Role) -> int:
    if role == Role.SOLDIER:
        return cfg.ANT_SOLDIER_ATK
    if role == Role.SCOUT:
        return cfg.ANT_SCOUT_ATK
    return cfg.ANT_WORKER_ATK


def update_combat(state, dt: float) -> None:
    cfg = state.cfg
    if not cfg.COMBAT_ENABLE or not state.enemies:
        return

    tick = state.tick
    engage_sq = cfg.COMBAT_ENGAGE_RADIUS * cfg.COMBAT_ENGAGE_RADIUS

    for ant in state.colony.ants:
        if ant.hp <= 0 or (tick - ant.last_combat_tick) < cfg.COMBAT_TICK_COOLDOWN:
            continue
        for enemy in state.enemies:
            if enemy.hp <= 0:
                continue
            dx, dy = enemy.x - ant.x, enemy.y - ant.y
            if dx * dx + dy * dy > engage_sq:
                continue

            ant.last_combat_tick = tick
            enemy.last_combat_tick = tick
            enemy.hp -= _atk_for_role(cfg, ant.role)
            ant.hp -= cfg.REDANT_ATK

            state.history.emit(
                state.t, tick, EventKind.ENEMY_CONTACT,
                {"ant_id": ant.id, "enemy_id": enemy.id, "role": ant.role.value},
                cause="engagement",
                tags=["combat"]
            )
            if enemy.hp <= 0:
                state.colony.metrics["enemy_kills"] += 1
                state.history.emit(
                    state.t, tick, EventKind.ENEMY_KILL,
                    {"ant_id": ant.id, "enemy_id": enemy.id},
                    cause="combat",
                    impact={"enemy_kills": 1},
                    tags=["combat"]
                )
            if ant.hp <= 0:
                state.colony.metrics["ants_killed"] += 1
                state.history.emit(
                    state.t, tick, EventKind.ENEMY_DEATH,
                    {"ant_id": ant.id, "enemy_id": enemy.id, "role": ant.role.value},
                    cause="combat",
                    impact={"ants_killed": 1},
                    tags=["combat"]
                )
            break

    nest_x, nest_y = state.nest_pos
    for enemy in state.enemies:
        if enemy.hp <= 0:
            continue
        d = math.hypot(enemy.x - nest_x, enemy.y - nest_y)
        if d <= cfg.QUEEN_THREAT_RADIUS and (tick - enemy.last_combat_tick) >= cfg.COMBAT_TICK_COOLDOWN:
            enemy.last_combat_tick = tick
            state.colony.queen.hp -= cfg.QUEEN_DAMAGE_PER_HIT
            state.history.emit(
                state.t, tick, EventKind.QUEEN_HIT,
                {"enemy_id": enemy.id, "dmg": cfg.QUEEN_DAMAGE_PER_HIT},
                cause="queen_threatened",
                impact={"queen_hp": -cfg.QUEEN_DAMAGE_PER_HIT},
                tags=["combat", "queen"]
            )

    state.colony.ants = [a for a in state.colony.ants if a.hp > 0]
    state.enemies = [e for e in state.enemies if e.hp > 0]
