"""
Pheromone grid system: two decaying, diffusing scent channels (food and
home) that ants deposit into as they move and sample gradients from
when foraging.
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple


class PheromoneSystem:
    def __init__(self, cfg, terrain=None):
        self.cfg = cfg
        self.cell = cfg.PHERO_GRID
        self.cols = max(1, int(cfg.WORLD_W // self.cell) + 1)
        self.rows = max(1, int(cfg.WORLD_H // self.cell) + 1)
        self.grids: Dict[str, List[List[float]]] = {
            "food": [[0.0] * self.rows for _ in range(self.cols)],
            "home": [[0.0] * self.rows for _ in range(self.cols)],
        }

        # Terrain never changes, so resolve each pheromone cell's decay
        # multiplier once here rather than per tick in the decay loop.
        if terrain is None:
            self._decay_mult = [[1.0] * self.rows for _ in range(self.cols)]
        else:
            self._decay_mult = [
                [terrain.decay_mult((cx + 0.5) * self.cell, (cy + 0.5) * self.cell)
                 for cy in range(self.rows)]
                for cx in range(self.cols)
            ]

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
        """Evaporate each channel, then blur it into its neighbours.

        Two passes rather than one. Decaying and diffusing in the same
        sweep meant a cell shed `D` of its *decayed* value while its
        neighbours were credited from its *undecayed* value, so the grid
        quietly gained mass; separating them keeps the blur conservative.

        The blur must also reach cells that are currently empty. It used
        to skip any cell whose own decayed value fell under a threshold,
        which looks like a cheap skip-the-empty-cells optimisation and is
        actually a leak: the share a trail sheds outward lands on empty
        neighbours, and skipping them destroys it instead of spreading
        it. Measured, a trail kept 9.7% of its scent per second and an
        isolated deposit 2.4%, against the 45% the configured decay rate
        asks for - so FOOD_PHERO_DECAY_PER_SEC was contributing about a
        sixth of the real evaporation and tuning it did almost nothing.
        The food channel suffered worst, because it is laid in thin
        trails whose neighbours are mostly empty, while the home channel
        is smeared across the whole map and largely masked the problem.
        """
        cfg = self.cfg
        decay_rates = {"food": cfg.FOOD_PHERO_DECAY_PER_SEC,
                       "home": cfg.HOME_PHERO_DECAY_PER_SEC}
        # A rate per second, like the decay beside it. Applied once per
        # tick it scaled with framerate instead of with time.
        diffuse = min(1.0, cfg.PHERO_DIFFUSE * dt)

        for channel, grid in self.grids.items():
            rate = decay_rates[channel] * dt
            decayed = [
                [grid[cx][cy] * max(0.0, 1.0 - rate * self._decay_mult[cx][cy])
                 for cy in range(self.rows)]
                for cx in range(self.cols)
            ]

            new_grid = [[0.0] * self.rows for _ in range(self.cols)]
            for cx in range(self.cols):
                col = decayed[cx]
                left = decayed[cx - 1] if cx > 0 else None
                right = decayed[cx + 1] if cx + 1 < self.cols else None
                for cy in range(self.rows):
                    neighbor_sum = 0.0
                    n = 0
                    if left is not None:
                        neighbor_sum += left[cy]
                        n += 1
                    if right is not None:
                        neighbor_sum += right[cy]
                        n += 1
                    if cy > 0:
                        neighbor_sum += col[cy - 1]
                        n += 1
                    if cy + 1 < self.rows:
                        neighbor_sum += col[cy + 1]
                        n += 1

                    v = col[cy]
                    # Only genuinely dead neighbourhoods may be skipped:
                    # nothing here and nothing nearby to flow in.
                    if v <= 0.0 and neighbor_sum <= 0.0:
                        continue
                    if n:
                        v += (neighbor_sum / n - v) * diffuse
                    if v >= 1e-6:
                        new_grid[cx][cy] = v
            self.grids[channel] = new_grid

    def sample_best_direction(
        self, channel: str, pos: Tuple[float, float], step: float,
        away_from: Optional[Tuple[float, float]] = None,
    ) -> Optional[Tuple[float, float]]:
        """Climb the strongest nearby gradient in `channel`.

        `away_from` (typically the nest) restricts the search to cells no
        closer to that point than the caller already is. A laden ant lays
        its trail walking food -> nest, and near the nest every trail
        superimposes, so the nest end is always the global maximum -
        plain gradient-climbing would walk foragers inward, back to the
        one place with no food. Constraining the step outward makes a
        trail lead to its source instead of its destination.
        """
        x, y = pos
        cx, cy = self._cell_of(x, y)

        cur_dist = None
        if away_from is not None:
            cur_dist = math.hypot(x - away_from[0], y - away_from[1])

        best_dir = None
        best_level = 1e-3  # ignore near-empty trails
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                ncx, ncy = cx + dx, cy + dy
                level = self._level_at_cell(channel, ncx, ncy)
                if level <= best_level:
                    continue
                if cur_dist is not None:
                    wx = (ncx + 0.5) * self.cell
                    wy = (ncy + 0.5) * self.cell
                    if math.hypot(wx - away_from[0], wy - away_from[1]) < cur_dist:
                        continue
                best_level = level
                best_dir = (dx, dy)

        if best_dir is None:
            return None

        dx, dy = best_dir
        d = math.hypot(dx, dy)
        tx = min(max(0.0, x + (dx / d) * step), self.cfg.WORLD_W)
        ty = min(max(0.0, y + (dy / d) * step), self.cfg.WORLD_H)
        return tx, ty
