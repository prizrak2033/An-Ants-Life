"""
Ant entity class and behavior.

This module defines the Ant dataclass which represents individual ants
in the simulation, including their movement, food gathering, and interactions
with the nest and environment.
"""

from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Optional, TYPE_CHECKING

from ants.roles import Role
from ants.ai import choose_intent
from colony.history import EventKind

if TYPE_CHECKING:
    from state import GameState


def _clamp(v: float, lo: float, hi: float) -> float:
    """Clamp value v between lo and hi."""
    return min(max(v, lo), hi)

@dataclass
class Ant:
    id: int
    role: Role
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    carrying: float = 0.0
    hp: int = 3
    last_combat_tick: int = -10_000
    detour_until_tick: int = -1
    detour_side: int = 1
    # Forage mark this ant has answered, if any. Cleared the moment it
    # actually has food, so a recruit is never held to a mark once it has
    # something better to do.
    recruited_to: Optional[int] = None

    def update(self, state: GameState, dt: float) -> None:
        """Update ant position, behavior, and interactions each frame."""
        cfg = state.cfg
        intent = choose_intent(state, self, dt)

        # Deposit pheromones
        if intent.deposit_channel == "food":
            state.pheromones.deposit("food", (self.x, self.y), cfg.FOOD_PHERO_DEPOSIT_AMOUNT)
        elif intent.deposit_channel == "home":
            state.pheromones.deposit("home", (self.x, self.y), cfg.HOME_PHERO_DEPOSIT_AMOUNT)

        # Movement. While rounding an obstacle the ant holds its detour
        # heading and ignores the target, otherwise it would turn straight
        # back into the face it just hit.
        detouring = state.tick < self.detour_until_tick
        if intent.target is not None and not detouring:
            tx, ty = intent.target
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy) + 1e-6
            nx, ny = dx / d, dy / d
            speed = cfg.ANT_SPEED * state.terrain.speed_mult(self.x, self.y)
            self.vx, self.vy = nx * speed, ny * speed

        terrain = state.terrain
        px = _clamp(self.x + self.vx * dt, 0, cfg.WORLD_W)
        py = _clamp(self.y + self.vy * dt, 0, cfg.WORLD_H)
        (self.x, self.y), blocked = terrain.move(self.x, self.y, px, py)

        if blocked:
            # Hold the side chosen when this encounter began, so the ant
            # works its way around one face instead of alternating.
            if not detouring:
                self.detour_side = 1 if (self.id & 1) else -1
            turned = terrain.deflect(self.x, self.y, self.vx, self.vy, dt, self.detour_side)
            if turned is not None:
                self.vx, self.vy, self.detour_side = turned
                self.detour_until_tick = state.tick + cfg.TERRAIN_DETOUR_TICKS
                px = _clamp(self.x + self.vx * dt, 0, cfg.WORLD_W)
                py = _clamp(self.y + self.vy * dt, 0, cfg.WORLD_H)
                (self.x, self.y), _ = terrain.move(self.x, self.y, px, py)

        self._handle_food_and_nest(state)

    def _handle_food_and_nest(self, state: GameState) -> None:
        """Handle food pickup and nest deposit interactions."""
        cfg = state.cfg
        nest = state.nest_pos  # Use cached nest position

        # Pick up food
        if self.carrying <= 0:
            got = state.world.try_take_food((self.x, self.y), radius=3.0, amount=cfg.CARRY_CAPACITY)
            if got > 0:
                self.carrying = got
                state.colony.metrics["food_pickups"] += 1
                state.history.emit(
                    state.t, state.tick, EventKind.FORAGE_PICKUP,
                    {"ant_id": self.id, "amt": got, "role": self.role.value},
                    cause="foraging",
                    impact={"food_gained": float(got)},
                    tags=["forage"]
                )

        # Deposit at nest
        if self.carrying > 0:
            if (abs(self.x - nest[0]) <= 3.0) and (abs(self.y - nest[1]) <= 3.0):
                state.colony.food_store += self.carrying
                state.colony.metrics["food_deposits"] += 1
                state.history.emit(
                    state.t, state.tick, EventKind.FORAGE_DEPOSIT,
                    {"ant_id": self.id, "amt": self.carrying, "role": self.role.value},
                    cause="supply_chain",
                    impact={"food_stored": float(self.carrying)},
                    tags=["forage", "logistics"]
                )
                self.carrying = 0.0
