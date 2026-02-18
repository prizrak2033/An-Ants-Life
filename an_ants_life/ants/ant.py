from __future__ import annotations
from dataclasses import dataclass
import math

from ants.roles import Role
from ants.ai import choose_intent
from colony.history import EventKind

def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

@dataclass
class Ant:
    id: int
    role: Role
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    carrying: float = 0.0

    def update(self, state, dt: float):
        cfg = state.cfg
        intent = choose_intent(state, self)

        # Deposit pheromones
        if intent.deposit_channel == "food":
            state.pheromones.deposit("food", (self.x, self.y), cfg.FOOD_PHERO_DEPOSIT_AMOUNT)
        elif intent.deposit_channel == "home":
            state.pheromones.deposit("home", (self.x, self.y), cfg.HOME_PHERO_DEPOSIT_AMOUNT)

        # Movement
        if intent.target is not None:
            tx, ty = intent.target
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy) + 1e-6
            nx, ny = dx / d, dy / d
            speed = cfg.ANT_SPEED
            self.vx, self.vy = nx * speed, ny * speed

        self.x += self.vx * dt
        self.y += self.vy * dt

        self.x = _clamp(self.x, 0, cfg.WORLD_W)
        self.y = _clamp(self.y, 0, cfg.WORLD_H)

        self._handle_food_and_nest(state)

    def _handle_food_and_nest(self, state):
        cfg = state.cfg
        nest = (cfg.NEST_X, cfg.NEST_Y)

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
