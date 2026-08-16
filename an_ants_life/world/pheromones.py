"""
Pheromone grid system: two decaying, diffusing scent channels (food and
home) that ants deposit into as they move and sample gradients from
when foraging.
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple


class PheromoneSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cell = cfg.PHERO_GRID
        self.cols = max(1, int(cfg.WORLD_W // self.cell) + 1)
        self.rows = max(1, int(cfg.WORLD_H // self.cell) + 1)
        self.grids: Dict[str, List[List[float]]] = {
            "food": [[0.0] * self.rows for _ in range(self.cols)],
            "home": [[0.0] * self.rows for _ in range(self.cols)],
        }

    def _cell_of(self, x: float, y: float) -> Tuple[int, int]:
        cx = min(self.cols - 1, max(0, int(x // self.cell)))
        cy = min(self.rows - 1, max(0, int(y // self.cell)))
        return cx, cy

    def deposit(self, channel: str, pos: Tuple[float, float], amount: float) -> None:
        cx, cy = self._cell_of(*pos)
        self.grids[channel][cx][cy] += amount

    def level_at(self, channel: str, pos: Tuple[float, float]) -> float:
        cx, cy = self._cell_of(*pos)
        return self.grids[channel][cx][cy]

    def _level_at_cell(self, channel: str, cx: int, cy: int) -> float:
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            return self.grids[channel][cx][cy]
        return 0.0

    def decay_and_diffuse(self, dt: float) -> None:
        cfg = self.cfg
        decay_rates = {"food": cfg.FOOD_PHERO_DECAY_PER_SEC, "home": cfg.HOME_PHERO_DECAY_PER_SEC}

        for channel, grid in self.grids.items():
            decay = max(0.0, 1.0 - decay_rates[channel] * dt)
            new_grid = [[0.0] * self.rows for _ in range(self.cols)]
            for cx in range(self.cols):
                for cy in range(self.rows):
                    v = grid[cx][cy] * decay
                    if v < 1e-4:
                        continue
                    neighbor_sum = 0.0
                    n = 0
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < self.cols and 0 <= ny < self.rows:
                            neighbor_sum += grid[nx][ny]
                            n += 1
                    if n:
                        v += (neighbor_sum / n - v) * cfg.PHERO_DIFFUSE
                    new_grid[cx][cy] = max(0.0, v)
            self.grids[channel] = new_grid

    def sample_best_direction(
        self, channel: str, pos: Tuple[float, float], step: float
    ) -> Optional[Tuple[float, float]]:
        x, y = pos
        cx, cy = self._cell_of(x, y)

        best_dir = None
        best_level = 1e-3  # ignore near-empty trails
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                level = self._level_at_cell(channel, cx + dx, cy + dy)
                if level > best_level:
                    best_level = level
                    best_dir = (dx, dy)

        if best_dir is None:
            return None

        dx, dy = best_dir
        d = math.hypot(dx, dy)
        tx = min(max(0.0, x + (dx / d) * step), self.cfg.WORLD_W)
        ty = min(max(0.0, y + (dy / d) * step), self.cfg.WORLD_H)
        return tx, ty
