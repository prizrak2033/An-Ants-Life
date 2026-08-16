"""
Debug dump: periodically prints extended diagnostics, including a
small ASCII grid of the pheromone or territory field around the nest.
"""
from __future__ import annotations


def debug_dump(state, every_ticks: int) -> None:
    cfg = state.cfg
    if not cfg.DEBUG_ENABLE:
        return
    if state.tick % every_ticks != 0:
        return

    print(f"--- debug tick={state.tick} metrics={state.colony.metrics} ---")
    print(_render_map(state))


def _render_map(state) -> str:
    cfg = state.cfg
    mode = cfg.DEBUG_PHERO_MAP_MODE
    r = cfg.DEBUG_PHERO_MAP_RADIUS_CELLS
    nest_x, nest_y = state.nest_pos

    if mode == "territory":
        cell = cfg.TERR_CELL
        lo, hi = -1.0, 1.0

        def sample(gx: int, gy: int) -> float:
            return state.territory.control_at(gx * cell, gy * cell)
    else:
        cell = cfg.PHERO_GRID
        lo, hi = 0.0, 3.0

        def sample(gx: int, gy: int) -> float:
            return state.pheromones.level_at(mode, (gx * cell, gy * cell))

    ncx, ncy = int(nest_x // cell), int(nest_y // cell)
    chars = " .:-=+*#%@"
    rows = []
    for gy in range(ncy - r, ncy + r + 1):
        row = []
        for gx in range(ncx - r, ncx + r + 1):
            v = sample(gx, gy)
            frac = max(0.0, min(1.0, (v - lo) / (hi - lo)))
            row.append(chars[int(frac * (len(chars) - 1))])
        rows.append("".join(row))
    return "\n".join(rows)
