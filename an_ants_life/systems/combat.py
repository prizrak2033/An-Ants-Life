"""
Combat resolution: ants and red ants trade damage when within engage
range (subject to a per-unit cooldown), and enemies that reach the
queen's threat radius strike her directly.
"""
from __future__ import annotations
import math

from ants.roles import Role
from enemies.kinds import EnemyKind
from world.food import FoodSource
from colony.history import EventKind


def _drop_loot(state, enemy) -> None:
    """A raider cut down before it escapes spills what it was carrying
    back onto the ground, so intercepting one actually saves the food
    rather than merely denying the kill."""
    if enemy.carrying <= 0:
        return
    world = state.world
    world.food_sources.append(
        FoodSource(world._next_food_id, enemy.x, enemy.y, enemy.carrying)
    )
    world._next_food_id += 1
    state.colony.metrics["loot_recovered"] += enemy.carrying
    state.history.emit(
        state.t, state.tick, EventKind.ENEMY_LOOT_RECOVERED,
        {"enemy_id": enemy.id, "amt": round(enemy.carrying, 1)},
        cause="raider_intercepted",
        impact={"food_recovered": float(enemy.carrying)},
        tags=["combat", "raid"]
    )
    enemy.carrying = 0.0


def _atk_for_role(cfg, role: Role) -> int:
    if role in (Role.SOLDIER, Role.PRAETORIAN):
        return cfg.ANT_SOLDIER_ATK
    if role == Role.SCOUT:
        return cfg.ANT_SCOUT_ATK
    return cfg.ANT_WORKER_ATK


def _maybe_promote(state, ant) -> None:
    """A soldier that fought an intruder inside the queen's chamber is
    raised to the praetorian guard.

    Promotion is earned at the spot that decides the game rather than
    bought, and it is capped by the colony's standing orders so the
    player chooses how much of the army to lock down at home.
    """
    cfg = state.cfg
    if not cfg.PRAETORIAN_ENABLE or ant.role is not Role.SOLDIER:
        return

    nest_x, nest_y = state.nest_pos
    dx, dy = ant.x - nest_x, ant.y - nest_y
    if dx * dx + dy * dy > cfg.PRAETORIAN_CHAMBER_RADIUS ** 2:
        return

    want = min(state.policy.praetorian_target, cfg.PRAETORIAN_MAX)
    current = sum(1 for a in state.colony.ants if a.role is Role.PRAETORIAN)
    if current >= want:
        return

    ant.role = Role.PRAETORIAN
    ant.hp = min(cfg.ANT_HP_MAX + cfg.PRAETORIAN_BONUS_HP,
                 ant.hp + cfg.PRAETORIAN_BONUS_HP)
    state.colony.metrics["praetorians_raised"] += 1
    state.history.emit(
        state.t, state.tick, EventKind.PRAETORIAN_RAISED,
        {"ant_id": ant.id, "count": current + 1},
        cause="defended_the_queen",
        impact={"praetorians": 1},
        tags=["growth", "queen"]
    )


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
            ant.hp -= enemy.atk

            state.history.emit(
                state.t, tick, EventKind.ENEMY_CONTACT,
                {"ant_id": ant.id, "enemy_id": enemy.id, "kind": enemy.kind.value,
                 "role": ant.role.value},
                cause="engagement",
                tags=["combat"]
            )
            if enemy.hp <= 0:
                state.colony.metrics["enemy_kills"] += 1
                state.history.emit(
                    state.t, tick, EventKind.ENEMY_KILL,
                    {"ant_id": ant.id, "enemy_id": enemy.id, "kind": enemy.kind.value},
                    cause="combat",
                    impact={"enemy_kills": 1},
                    tags=["combat"]
                )
                _drop_loot(state, enemy)
            if ant.hp <= 0:
                state.colony.metrics["ants_killed"] += 1
                state.history.emit(
                    state.t, tick, EventKind.ENEMY_DEATH,
                    {"ant_id": ant.id, "enemy_id": enemy.id, "role": ant.role.value},
                    cause="combat",
                    impact={"ants_killed": 1},
                    tags=["combat"]
                )
            else:
                # Survived a fight; if it was in the queen's chamber, that
                # is what earns a place in her guard.
                _maybe_promote(state, ant)
            break

    nest_x, nest_y = state.nest_pos
    for enemy in state.enemies:
        if enemy.hp <= 0:
            continue
        # Only warriors come for the queen: raiders are there for the food
        # and predators are hunting foragers, so neither presses the nest.
        if enemy.kind != EnemyKind.WARRIOR:
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
