"""
HUD: a compact one-line status readout of the colony, printed
periodically to the console.
"""
from __future__ import annotations
from ants.roles import Role
from ui.chronicle import format_chronicle


def render_hud(state) -> None:
    colony = state.colony
    workers = sum(1 for a in colony.ants if a.role == Role.WORKER)
    scouts = sum(1 for a in colony.ants if a.role == Role.SCOUT)
    soldiers = sum(1 for a in colony.ants if a.role == Role.SOLDIER)

    pressure = colony.emergency.get("territory_pressure", 0.0)
    hunger = colony.emergency.get("hunger", 0.0)
    famine = "FAMINE" if colony.emergency.get("famine_active") else "ok"
    chapter = state.milestones.chapter.title if state.milestones.chapter.active else "-"

    print(
        f"[t={state.t:7.1f}s tick={state.tick:6d}] "
        f"ants=W{workers}/S{scouts}/So{soldiers} "
        f"food={colony.food_store:6.1f} stress={colony.stress:.2f} "
        f"hunger={hunger:.2f}({famine}) pressure={pressure:.2f} "
        f"enemies={len(state.enemies):2d} queen_hp={colony.queen.hp}/{colony.queen.hp_max} "
        f"chapter={chapter}"
    )

    if state.cfg.CHRONICLE_SHOW:
        line = format_chronicle(state)
        if line:
            print(line)
