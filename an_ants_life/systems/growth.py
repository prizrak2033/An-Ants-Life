"""
Growth and recovery: the queen turns a food surplus into new ants, and
slowly heals while the colony is fed and the nest is clear.

These are the colony's only ways back from attrition. Without them both
population and queen HP are strictly depleting resources, so any run
long enough ends the same way no matter how well it is played.
"""
from __future__ import annotations
import random

from ants.ant import Ant
from ants.roles import Role
from colony.history import EventKind


def update_growth(state, dt: float) -> None:
    _update_queen_recovery(state, dt)
    _update_births(state)


def _update_queen_recovery(state, dt: float) -> None:
    cfg = state.cfg
    colony = state.colony
    queen = colony.queen

    if queen.hp <= 0 or queen.hp >= queen.hp_max:
        return
    if colony.emergency.get("hunger", 0.0) > cfg.QUEEN_REGEN_MAX_HUNGER:
        return

    nest_x, nest_y = state.nest_pos
    safe_sq = cfg.QUEEN_REGEN_SAFE_RADIUS * cfg.QUEEN_REGEN_SAFE_RADIUS
    for enemy in state.enemies:
        dx, dy = enemy.x - nest_x, enemy.y - nest_y
        if dx * dx + dy * dy <= safe_sq:
            return  # under threat, no recovery

    # Queen HP is an int, so accumulate fractional healing in the systems
    # scratchpad and bank whole points as they come due.
    progress = colony.emergency.get("queen_heal_progress", 0.0) + cfg.QUEEN_REGEN_PER_SEC * dt
    healed = int(progress)
    if healed:
        queen.hp = min(queen.hp_max, queen.hp + healed)
        progress -= healed
    colony.emergency["queen_heal_progress"] = progress


def _pick_role(state) -> Role:
    """Seek the configured caste mix, raising the soldier target with
    border pressure, instead of rolling fixed weights that can never
    refill a caste that has been drained to zero."""
    cfg = state.cfg
    ants = state.colony.ants
    total = len(ants)
    if total == 0:
        return Role.WORKER

    pressure = max(0.0, min(1.0, state.colony.emergency.get("territory_pressure", 0.0)))
    soldier_target = cfg.GROWTH_TARGET_SOLDIER_FRAC + (
        cfg.GROWTH_THREAT_SOLDIER_FRAC - cfg.GROWTH_TARGET_SOLDIER_FRAC
    ) * pressure

    soldiers = sum(1 for a in ants if a.role == Role.SOLDIER)
    scouts = sum(1 for a in ants if a.role == Role.SCOUT)

    soldier_deficit = soldier_target - soldiers / total
    scout_deficit = cfg.GROWTH_TARGET_SCOUT_FRAC - scouts / total

    if soldier_deficit > 0 and soldier_deficit >= scout_deficit:
        return Role.SOLDIER
    if scout_deficit > 0:
        return Role.SCOUT
    return Role.WORKER


def _update_births(state) -> None:
    cfg = state.cfg
    if not cfg.GROWTH_ENABLE:
        return

    colony = state.colony
    if len(colony.ants) >= cfg.GROWTH_MAX_POPULATION:
        return

    reserve_target = colony.emergency.get("food_reserve_target", 1.0)
    if colony.food_store < reserve_target * cfg.GROWTH_SURPLUS_MULT:
        return

    last_birth_tick = colony.emergency.get("last_birth_tick", -10_000)
    if (state.tick - last_birth_tick) < cfg.GROWTH_MIN_TICKS_BETWEEN_BIRTHS:
        return

    colony.food_store -= cfg.GROWTH_EGG_FOOD_COST
    colony.emergency["last_birth_tick"] = state.tick

    role = _pick_role(state)
    nest_x, nest_y = state.nest_pos
    ant = Ant(
        colony.next_ant_id(), role,
        nest_x + random.uniform(-3, 3), nest_y + random.uniform(-3, 3),
        hp=cfg.ANT_HP_MAX,
    )
    colony.ants.append(ant)
    colony.metrics["ants_born"] += 1

    state.history.emit(
        state.t, state.tick, EventKind.ANT_BORN,
        {"ant_id": ant.id, "role": role.value},
        cause="food_surplus",
        impact={"population": 1},
        tags=["growth"]
    )
