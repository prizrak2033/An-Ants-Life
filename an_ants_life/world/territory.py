"""
Territory control model: a grid of control values in [-1, 1] (positive
is colony-held, negative is enemy-held) shaped by ant and enemy
presence, that also derives the border "pressure" reading other
systems (stress, emergencies, chapters) react to.
"""
from __future__ import annotations
import math
import random
from typing import List, Tuple

from ants.roles import Role
from colony.history import EventKind


class TerritoryModel:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cols = max(1, int(cfg.WORLD_W // cfg.TERR_CELL) + 1)
        self.rows = max(1, int(cfg.WORLD_H // cfg.TERR_CELL) + 1)
        self.grid: List[List[float]] = [[0.0] * self.rows for _ in range(self.cols)]

        nest_cx, nest_cy = self._cell_of(cfg.NEST_X, cfg.NEST_Y)
        for cx in range(self.cols):
            for cy in range(self.rows):
                if math.hypot(cx - nest_cx, cy - nest_cy) <= 3:
                    self.grid[cx][cy] = 0.3

        self._last_border_incident_tick = -10_000
        self._last_expansion_tick = -10_000

    def _cell_of(self, x: float, y: float) -> Tuple[int, int]:
        cfg = self.cfg
        cx = min(self.cols - 1, max(0, int(x // cfg.TERR_CELL)))
        cy = min(self.rows - 1, max(0, int(y // cfg.TERR_CELL)))
        return cx, cy

    def control_at(self, x: float, y: float) -> float:
        cx, cy = self._cell_of(x, y)
        return self.grid[cx][cy]

    def _add(self, x: float, y: float, amount: float) -> None:
        cx, cy = self._cell_of(x, y)
        self.grid[cx][cy] = max(-1.0, min(1.0, self.grid[cx][cy] + amount))

    def update(self, state) -> None:
        cfg = self.cfg

        for ant in state.colony.ants:
            if ant.role == Role.WORKER:
                infl = cfg.TERR_INFL_WORKER
            elif ant.role == Role.SCOUT:
                infl = cfg.TERR_INFL_SCOUT
            else:
                infl = cfg.TERR_INFL_SOLDIER
            self._add(ant.x, ant.y, infl)

        for enemy in state.enemies:
            self._add(enemy.x, enemy.y, -cfg.REDANT_TERR_INFLUENCE)

        new_grid = [[0.0] * self.rows for _ in range(self.cols)]
        for cx in range(self.cols):
            for cy in range(self.rows):
                v = self.grid[cx][cy] * (1.0 - cfg.TERR_DECAY_PER_TICK)

                neighbor_sum = 0.0
                n = 0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < self.cols and 0 <= ny < self.rows:
                        neighbor_sum += self.grid[nx][ny]
                        n += 1
                if n:
                    v += (neighbor_sum / n - v) * cfg.TERR_DIFFUSE

                v -= cfg.TERR_AMBIENT_ENEMY_PUSH
                v += random.uniform(-cfg.TERR_ENEMY_NOISE, cfg.TERR_ENEMY_NOISE)
                new_grid[cx][cy] = max(-1.0, min(1.0, v))
        self.grid = new_grid

        self._update_pressure(state)

    def _update_pressure(self, state) -> None:
        cfg = self.cfg
        nest_x, nest_y = state.nest_pos
        nest_cx, nest_cy = self._cell_of(nest_x, nest_y)

        radius_cells = 4
        vals = []
        for cx in range(self.cols):
            for cy in range(self.rows):
                if math.hypot(cx - nest_cx, cy - nest_cy) <= radius_cells:
                    vals.append(self.grid[cx][cy])
        nest_control = sum(vals) / len(vals) if vals else 0.0
        pressure = max(0.0, min(1.0, (1.0 - nest_control) / 2.0))

        state.colony.emergency["territory_pressure"] = pressure
        state.colony.emergency["territory_control"] = nest_control

        if pressure >= cfg.TERR_BORDER_INCIDENT_PRESSURE and \
                (state.tick - self._last_border_incident_tick) >= cfg.TERR_EVENT_COOLDOWN_TICKS:
            self._last_border_incident_tick = state.tick
            state.colony.metrics["border_incidents"] += 1
            state.history.emit(
                state.t, state.tick, EventKind.TERR_BORDER_INCIDENT,
                {"pressure": round(pressure, 3)},
                cause="enemy_pressure",
                impact={"pressure": pressure},
                tags=["territory"]
            )

        if nest_control >= cfg.TERR_EXPANSION_CONTROL and \
                (state.tick - self._last_expansion_tick) >= cfg.TERR_EVENT_COOLDOWN_TICKS:
            self._last_expansion_tick = state.tick
            state.colony.metrics["expansions"] += 1
            state.history.emit(
                state.t, state.tick, EventKind.TERR_EXPANSION,
                {"control": round(nest_control, 3)},
                cause="colony_growth",
                impact={"control": nest_control},
                tags=["territory"]
            )
