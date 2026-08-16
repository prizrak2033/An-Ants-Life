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
        x, y = cfg.NEST_X, cfg.NEST_Y
        for _ in range(20):
            x = random.uniform(0, cfg.WORLD_W)
            y = random.uniform(0, cfg.WORLD_H)
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

    def maybe_respawn_food(self) -> None:
        cfg = self.cfg
        active = sum(1 for s in self.food_sources if s.amount > 0)
        if active >= cfg.INITIAL_FOOD_SOURCES:
            return
        if random.random() < cfg.FOOD_SOURCE_RESPAWN_CHANCE_PER_TICK:
            self._spawn_food_source()
