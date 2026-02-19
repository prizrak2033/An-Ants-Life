from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
import random

from ants.ant import Ant
from ants.roles import Role

@dataclass
class Queen:
    x: float
    y: float
    hp: int
    hp_max: int

@dataclass
class ColonyState:
    cfg: any
    ants: List[Ant] = field(default_factory=list)
    food_store: float = 0.0
    stress: float = 0.0

    queen: Queen = field(init=False)

    # “shared scratchpad” for systems
    emergency: Dict = field(default_factory=dict)
    metrics: Dict = field(default_factory=lambda: {
        "food_pickups": 0,
        "food_deposits": 0,
        "raids": 0,
        "ants_killed": 0,
        "role_conversions": 0,
        "border_incidents": 0,
        "expansions": 0,
        "claims": 0,
        "enemy_kills": 0,
    })

    def __post_init__(self):
        cfg = self.cfg
        self.food_store = cfg.FOOD_PER_SOURCE * 0.6
        self.queen = Queen(cfg.NEST_X, cfg.NEST_Y, cfg.QUEEN_HP_MAX, cfg.QUEEN_HP_MAX)

        # Build initial ants
        aid = 1
        for _ in range(cfg.INITIAL_WORKERS):
            self.ants.append(Ant(aid, Role.WORKER, cfg.NEST_X + random.uniform(-4, 4), cfg.NEST_Y + random.uniform(-4, 4)))
            aid += 1
        for _ in range(cfg.INITIAL_SCOUTS):
            self.ants.append(Ant(aid, Role.SCOUT, cfg.NEST_X + random.uniform(-4, 4), cfg.NEST_Y + random.uniform(-4, 4)))
            aid += 1
        for _ in range(cfg.INITIAL_SOLDIERS):
            self.ants.append(Ant(aid, Role.SOLDIER, cfg.NEST_X + random.uniform(-4, 4), cfg.NEST_Y + random.uniform(-4, 4)))
            aid += 1
