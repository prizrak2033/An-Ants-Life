"""
Stress system: tracks colony hunger from ongoing food upkeep and
combines it with territory pressure to produce an overall stress
level, which decays naturally over time.
"""
from __future__ import annotations


def _update_carrying_capacity(state, cfg, colony, population: int, dt: float) -> None:
    """Two separate readings, because conflating them is a trap.

    `food_balance` is a flow: what the colony is actually bringing in
    against what it burns. It says whether the colony is currently
    feeding itself.

    `carrying_capacity` is a ceiling derived from the world's food
    regeneration, which no player action changes. An earlier version
    derived capacity from measured income instead, and that number is
    circular the moment anyone acts on it: throttling foraging lowers
    income, which lowers the estimate, which says throttle harder. A bot
    following it did measurably worse than doing nothing (3/12 surviving
    against 9/12). The ceiling has to come from the world, not from how
    hard the colony happens to be working.
    """
    delivered = colony.metrics["food_deposits"]
    previous = colony.emergency.get("_deposits_mark", delivered)
    colony.emergency["_deposits_mark"] = delivered

    rate = (delivered - previous) / dt if dt > 0 else 0.0
    # Smoothed hard: raw per-tick delivery rate is spiky (a tick either
    # has a delivery in it or does not).
    smoothing = min(1.0, dt / cfg.CAPACITY_SMOOTHING_SECONDS)
    income = colony.emergency.get("income_per_sec", 0.0)
    income += (rate - income) * smoothing
    colony.emergency["income_per_sec"] = income

    upkeep_each = max(1e-9, cfg.FOOD_UPKEEP_PER_ANT_PER_SEC)
    upkeep = population * upkeep_each
    colony.emergency["upkeep_per_sec"] = upkeep
    colony.emergency["food_balance"] = income - upkeep

    # World regen is the hard ceiling; combat attrition then spends a
    # large share of it on replacing losses, so the liveable figure is a
    # fraction of the naive one.
    regen = cfg.FOOD_PER_SOURCE / max(1e-6, cfg.FOOD_SOURCE_RESPAWN_SECONDS)
    colony.emergency["carrying_capacity"] = (
        regen * cfg.CAPACITY_ATTRITION_ALLOWANCE) / upkeep_each


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

    _update_carrying_capacity(state, cfg, colony, population, dt)

    state.world.maybe_respawn_food(dt)

    pressure = colony.emergency.get("territory_pressure", 0.0)

    colony.stress += cfg.STRESS_FROM_HUNGER * hunger * dt
    colony.stress += cfg.TERR_STRESS_FROM_PRESSURE * pressure * dt
    colony.stress -= cfg.STRESS_DECAY_PER_SEC * dt
    colony.stress = max(0.0, min(1.0, colony.stress))
