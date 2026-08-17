"""
Stress system: tracks colony hunger from ongoing food upkeep and
combines it with territory pressure to produce an overall stress
level, which decays naturally over time.
"""
from __future__ import annotations


def update_stress(state, dt: float) -> None:
    cfg = state.cfg
    colony = state.colony

    population = len(colony.ants)
    upkeep = population * cfg.FOOD_UPKEEP_PER_ANT_PER_SEC * dt
    colony.food_store = max(0.0, colony.food_store - upkeep)

    reserve_target = max(1.0, population * cfg.FOOD_UPKEEP_PER_ANT_PER_SEC * cfg.FOOD_RESERVE_BUFFER_SEC)
    hunger = max(0.0, min(1.0, 1.0 - colony.food_store / reserve_target))
    colony.emergency["hunger"] = hunger
    colony.emergency["food_reserve_target"] = reserve_target

    state.world.maybe_respawn_food(dt)

    pressure = colony.emergency.get("territory_pressure", 0.0)

    colony.stress += cfg.STRESS_FROM_HUNGER * hunger * dt
    colony.stress += cfg.TERR_STRESS_FROM_PRESSURE * pressure * dt
    colony.stress -= cfg.STRESS_DECAY_PER_SEC * dt
    colony.stress = max(0.0, min(1.0, colony.stress))
