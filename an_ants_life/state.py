"""
Game State management for An Ant's Life.

This module defines the GameState class which holds all the simulation state
including the world, colony, enemies, and various subsystems.
"""

from dataclasses import dataclass, field
from typing import Tuple
from config import SimConfig

from colony.colony_state import ColonyState
from colony.history import HistoryLog
from colony.milestones import MilestoneTracker

from world.map import WorldMap
from world.pheromones import PheromoneSystem
from world.territory import TerritoryModel


@dataclass
class GameState:
    cfg: SimConfig
    t: float = 0.0
    tick: int = 0

    world: WorldMap = field(init=False)
    pheromones: PheromoneSystem = field(init=False)
    territory: TerritoryModel = field(init=False)

    colony: ColonyState = field(init=False)
    history: HistoryLog = field(init=False)
    milestones: MilestoneTracker = field(init=False)

    enemies: list = field(default_factory=list)
    _next_enemy_id: int = 1
    
    # Cache nest coordinates to avoid tuple creation in hot loops
    nest_pos: Tuple[float, float] = field(init=False)

    def __post_init__(self) -> None:
        self.world = WorldMap(self.cfg)
        self.pheromones = PheromoneSystem(self.cfg)
        self.territory = TerritoryModel(self.cfg)

        self.colony = ColonyState(self.cfg)
        self.history = HistoryLog()
        self.milestones = MilestoneTracker(self.cfg)
        
        # Cache nest position
        self.nest_pos = (self.cfg.NEST_X, self.cfg.NEST_Y)
