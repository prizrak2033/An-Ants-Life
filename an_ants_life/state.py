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

from systems.enemies import update_enemies
from systems.combat import update_combat
from systems.objectives import update_objectives
from systems.stress import update_stress
from systems.growth import update_growth
from systems.emergencies import update_emergencies


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

    def step(self, dt: float) -> None:
        """Advance the simulation by one tick. Shared by every runner
        (console main loop, web server) so the pipeline can't drift."""
        self.t += dt
        self.tick += 1

        update_enemies(self, dt)
        self.territory.update(self)
        self.pheromones.decay_and_diffuse(dt)

        for ant in self.colony.ants:
            ant.update(self, dt)

        update_combat(self, dt)
        update_objectives(self, dt)
        update_stress(self, dt)
        update_growth(self, dt)
        update_emergencies(self, dt)

        self.milestones.update(self)
