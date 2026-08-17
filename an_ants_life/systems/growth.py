"""
Growth system: the queen turns a food surplus into new ants. This is
the colony's only source of population replenishment - without it,
population is a strictly depleting resource under any sustained
combat losses.
"""
from __future__ import annotations
import random

from ants.ant import Ant
from ants.roles import Role
from colony.history import EventKind

_ROLES = (Role.WORKER, Role.SCOUT, Role.SOLDIER)


def update_growth(state, dt: float) -> None:
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

    role = random.choices(
        _ROLES,
        weights=[cfg.GROWTH_WORKER_WEIGHT, cfg.GROWTH_SCOUT_WEIGHT, cfg.GROWTH_SOLDIER_WEIGHT],
    )[0]

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
