"""
Objectives: the colony can claim secured food sites once local
territory control there is strong enough, easing measured border
pressure as a reward for holding ground.
"""
from __future__ import annotations

from colony.history import EventKind


def update_objectives(state, dt: float) -> None:
    cfg = state.cfg
    if not cfg.OBJ_ENABLE:
        return

    claims = [s for s in state.world.food_sources if s.claimed]

    if len(claims) < cfg.OBJ_MAX_CLAIMS:
        for source in state.world.food_sources:
            if source.claimed or source.amount <= 0:
                continue
            control = state.territory.control_at(source.x, source.y)
            if control < cfg.OBJ_CLAIM_CONTROL_THRESHOLD:
                continue

            source.claimed = True
            claims.append(source)
            state.colony.metrics["claims"] += 1
            state.history.emit(
                state.t, state.tick, EventKind.OBJ_CLAIMED,
                {"source_id": source.id, "control": round(control, 3)},
                cause="territory_secured",
                impact={"claims": 1},
                tags=["objective"]
            )
            if len(claims) >= cfg.OBJ_MAX_CLAIMS:
                break

    pressure = state.colony.emergency.get("territory_pressure", 0.0)
    reduction = len(claims) * cfg.OBJ_CLAIM_PRESSURE_REDUCTION
    state.colony.emergency["territory_pressure"] = max(0.0, pressure - reduction)
