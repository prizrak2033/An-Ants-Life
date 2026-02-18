
from dataclasses import dataclass, field
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

    def __post_init__(self):
        self.world = WorldMap(self.cfg)
        self.pheromones = PheromoneSystem(self.cfg)
        self.territory = TerritoryModel(self.cfg)

        self.colony = ColonyState(self.cfg)
        self.history = HistoryLog()
        self.milestones = MilestoneTracker(self.cfg)
