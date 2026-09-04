"""
Emergency events: sustained hunger triggers a famine (which reassigns
scouts and soldiers to foraging), and high stress under enemy pressure
can trigger a raid that costs ants, rate-limited by a cooldown.
"""
from __future__ import annotations
import random

from ants.roles import Role
from colony.history import EventKind


def update_emergencies(state, dt: float) -> None:
    cfg = state.cfg
    colony = state.colony
    emergency = colony.emergency

    _update_famine(state, cfg, colony, emergency)
    _update_raid(state, cfg, colony, emergency, dt)


def _update_famine(state, cfg, colony, emergency) -> None:
    hunger = emergency.get("hunger", 0.0)
    active = emergency.get("famine_active", False)
    started_t = emergency.get("famine_started_t", -1.0)

    if not active:
        if hunger >= cfg.EMERGENCY_FAMINE_ON_HUNGER:
            emergency["famine_active"] = True
            emergency["famine_started_t"] = state.t
            colony.stress = min(1.0, colony.stress + cfg.EMERGENCY_FAMINE_STRESS_BONUS)
            state.history.emit(
                state.t, state.tick, EventKind.EMERGENCY_FAMINE_START,
                {"hunger": round(hunger, 3)},
                cause="food_shortage",
                impact={"stress": cfg.EMERGENCY_FAMINE_STRESS_BONUS},
                tags=["emergency", "famine"]
            )
            _reassign_for_famine(state, cfg, colony)
        return

    elapsed = state.t - started_t
    if hunger <= cfg.EMERGENCY_FAMINE_OFF_HUNGER and elapsed >= cfg.EMERGENCY_FAMINE_MIN_SECONDS:
        emergency["famine_active"] = False
        state.history.emit(
            state.t, state.tick, EventKind.EMERGENCY_FAMINE_END,
            {"hunger": round(hunger, 3)},
            cause="food_recovered",
            tags=["emergency", "famine", "recovery"]
        )
    else:
        state.history.emit(
            state.t, state.tick, EventKind.EMERGENCY_FAMINE_PRESSURE,
            {"hunger": round(hunger, 3)},
            cause="ongoing_shortage",
            tags=["emergency", "famine"]
        )


def _reassign_for_famine(state, cfg, colony) -> None:
    converted = 0
    for role, limit in (
        (Role.SCOUT, cfg.EMERGENCY_FAMINE_CONVERT_SCOUTS_TO_WORKERS),
        (Role.SOLDIER, cfg.EMERGENCY_FAMINE_CONVERT_SOLDIERS_TO_WORKERS),
    ):
        n = 0
        for ant in colony.ants:
            if n >= limit:
                break
            if ant.role == role:
                ant.role = Role.WORKER
                n += 1
        colony.metrics["role_conversions"] += n
        converted += n

    if converted:
        state.history.emit(
            state.t, state.tick, EventKind.EMERGENCY_FAMINE_REASSIGN,
            {"converted": converted},
            cause="famine_response",
            impact={"role_conversions": converted},
            tags=["emergency", "famine"]
        )


def _update_raid(state, cfg, colony, emergency, dt: float) -> None:
    last_raid_t = emergency.get("last_raid_t", -1e18)
    if (state.t - last_raid_t) < cfg.EMERGENCY_RAID_COOLDOWN_SECONDS:
        return
    if colony.stress < cfg.EMERGENCY_RAID_STRESS_GATE:
        return
    if random.random() >= cfg.EMERGENCY_RAID_CHANCE_PER_SEC * dt:
        return

    emergency["last_raid_t"] = state.t
    kills = min(random.randint(cfg.EMERGENCY_RAID_MIN_KILLS, cfg.EMERGENCY_RAID_MAX_KILLS), len(colony.ants))
    victims = random.sample(colony.ants, kills) if kills else []
    victim_ids = {v.id for v in victims}
    colony.ants = [a for a in colony.ants if a.id not in victim_ids]

    colony.metrics["raids"] += 1
    colony.metrics["ants_killed"] += kills

    state.history.emit(
        state.t, state.tick, EventKind.EMERGENCY_RAID,
        {"kills": kills, "stress": round(colony.stress, 3)},
        cause="enemy_raid",
        impact={"ants_killed": kills},
        tags=["emergency", "raid"]
    )
