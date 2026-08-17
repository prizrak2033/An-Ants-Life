"""
World map: bounds and the food sources scattered across it.
"""
from __future__ import annotations
import math
import random
from typing import List, Optional, Tuple

from world.food import FoodSource


class WorldMap:
    def __init__(self, cfg):
        self.cfg = cfg
        self.food_sources: List[FoodSource] = []
        self._next_food_id = 1
        for _ in range(cfg.INITIAL_FOOD_SOURCES):
            self._spawn_food_source()

    def _spawn_food_source(self) -> None:
        cfg = self.cfg
        # Keep piles off the very border: edge-hugging food is awkward to
        # work, and it let laden raiders leave the map almost the instant
        # they finished looting.
        m = cfg.FOOD_SOURCE_EDGE_MARGIN
        x, y = cfg.NEST_X, cfg.NEST_Y
        for _ in range(20):
            x = random.uniform(m, cfg.WORLD_W - m)
            y = random.uniform(m, cfg.WORLD_H - m)
            if math.hypot(x - cfg.NEST_X, y - cfg.NEST_Y) >= cfg.FOOD_SOURCE_MIN_DIST_FROM_NEST:
                break
        self.food_sources.append(
            FoodSource(self._next_food_id, x, y, cfg.FOOD_PER_SOURCE)
        )
        self._next_food_id += 1

    def nearest_food(self, pos: Tuple[float, float], radius: float) -> Optional[FoodSource]:
        x, y = pos
        best = None
        best_d = radius
        for source in self.food_sources:
            if source.amount <= 0:
                continue
            d = math.hypot(source.x - x, source.y - y)
            if d <= best_d:
                best_d = d
                best = source
        return best

    def try_take_food(self, pos: Tuple[float, float], radius: float, amount: float) -> float:
        x, y = pos
        for source in self.food_sources:
            if source.amount <= 0:
                continue
            if math.hypot(source.x - x, source.y - y) <= radius:
                taken = min(amount, source.amount)
                source.amount -= taken
                return taken
        return 0.0

    def maybe_respawn_food(self, dt: float) -> None:
        """Retire exhausted sources and occasionally seed a fresh one.

        Respawn is expressed as an average interval in seconds rather than
        a per-tick probability so the food economy doesn't silently shift
        with TARGET_FPS.
        """
        cfg = self.cfg

        # Exhausted piles are gone, not invisible forever: dropping them
        # keeps the scan lists short and makes a claimed site something the
        # colony has to re-earn rather than bank permanently.
        if any(s.amount <= 0 for s in self.food_sources):
            self.food_sources = [s for s in self.food_sources if s.amount > 0]

        if len(self.food_sources) >= cfg.INITIAL_FOOD_SOURCES:
            return
        if random.random() < dt / cfg.FOOD_SOURCE_RESPAWN_SECONDS:
            self._spawn_food_source()
