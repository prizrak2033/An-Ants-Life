"""
Game State management for An Ant's Life.

This module defines the GameState class which holds all the simulation state
including the world, colony, enemies, and various subsystems.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
from config import SimConfig

from colony.colony_state import ColonyState
from colony.history import HistoryLog
from colony.milestones import MilestoneTracker
from colony.directives import DirectiveBoard
from colony.policy import ColonyPolicy

from world.map import WorldMap
from world.pheromones import PheromoneSystem
from world.territory import TerritoryModel
from world.terrain import TerrainMap

from systems.enemies import update_enemies
from systems.directives import update_directives
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
    # None while the colony's story is still running; set by the
    # milestone tracker to the ending that closed it.
    ending: Optional[str] = None

    terrain: TerrainMap = field(init=False)
    world: WorldMap = field(init=False)
    pheromones: PheromoneSystem = field(init=False)
    territory: TerritoryModel = field(init=False)

    colony: ColonyState = field(init=False)
    history: HistoryLog = field(init=False)
    milestones: MilestoneTracker = field(init=False)
    directives: DirectiveBoard = field(init=False)
    policy: ColonyPolicy = field(init=False)

    enemies: list = field(default_factory=list)
    _next_enemy_id: int = 1
    
    # Cache nest coordinates to avoid tuple creation in hot loops
    nest_pos: Tuple[float, float] = field(init=False)

    def __post_init__(self) -> None:
        # Terrain first: food placement and pheromone decay both read it.
        self.terrain = TerrainMap(self.cfg)
        self.world = WorldMap(self.cfg, self.terrain)
        self.pheromones = PheromoneSystem(self.cfg, self.terrain)
        self.territory = TerritoryModel(self.cfg)

        self.colony = ColonyState(self.cfg)
        self.history = HistoryLog(self.cfg.HISTORY_MAX_EVENTS, self.cfg.HISTORY_MAX_NOTABLE)
        self.milestones = MilestoneTracker(self.cfg)
        self.directives = DirectiveBoard(self.cfg)
        self.policy = ColonyPolicy.from_config(self.cfg)
        
        # Cache nest position
        self.nest_pos = (self.cfg.NEST_X, self.cfg.NEST_Y)

    def step(self, dt: float) -> None:
        """Advance the simulation by one tick. Shared by every runner
        (console main loop, web server) so the pipeline can't drift."""
        self.t += dt
        self.tick += 1

        update_enemies(self, dt)
        self.territory.update(self)
        # Directives lay their scent before pheromones decay, so a mark's
        # contribution is subject to the same evaporation as a real trail.
        update_directives(self, dt)
        self.pheromones.decay_and_diffuse(dt)

        for ant in self.colony.ants:
            ant.update(self, dt)

        update_combat(self, dt)
        update_objectives(self, dt)
        update_stress(self, dt)
        update_growth(self, dt)
        update_emergencies(self, dt)

        self.milestones.update(self)
