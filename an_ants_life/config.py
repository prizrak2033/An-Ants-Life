"""
Configuration settings for the Ant Colony Simulation.

This module contains all the simulation parameters, including world size,
ant behavior, combat settings, and various game mechanics.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimConfig:
    # World
    WORLD_W: int = 120
    WORLD_H: int = 70

    # Time
    TARGET_FPS: int = 30
    MAX_DT: float = 0.05

    # Nest
    NEST_X: float = 60.0
    NEST_Y: float = 35.0

    # Ants
    INITIAL_WORKERS: int = 25
    INITIAL_SCOUTS: int = 3
    INITIAL_SOLDIERS: int = 4

    ANT_SPEED: float = 40.0
    ANT_SENSE_RADIUS: float = 18.0

    # Food sources
    INITIAL_FOOD_SOURCES: int = 6
    FOOD_PER_SOURCE: float = 30.0
    CARRY_CAPACITY: float = 1.0
    INITIAL_FOOD_STORE: float = 40.0

    # Pheromones
    PHERO_GRID: int = 4
    PHERO_DIFFUSE: float = 0.10
    FOOD_PHERO_DECAY_PER_SEC: float = 0.55
    HOME_PHERO_DECAY_PER_SEC: float = 0.45
    FOOD_PHERO_DEPOSIT_AMOUNT: float = 1.35
    HOME_PHERO_DEPOSIT_AMOUNT: float = 0.85
    PHERO_FOLLOW_STEP: float = 14.0

    # Stress
    STRESS_DECAY_PER_SEC: float = 0.20
    STRESS_FROM_HUNGER: float = 0.50
    TERR_STRESS_FROM_PRESSURE: float = 0.28

    # Emergencies
    EMERGENCY_FAMINE_ON_HUNGER: float = 0.70
    EMERGENCY_FAMINE_OFF_HUNGER: float = 0.35
    EMERGENCY_FAMINE_MIN_TICKS: int = 180
    EMERGENCY_FAMINE_STRESS_BONUS: float = 0.25

    EMERGENCY_RAID_STRESS_GATE: float = 0.90
    EMERGENCY_RAID_CHANCE_PER_TICK: float = 0.0025
    EMERGENCY_RAID_COOLDOWN_TICKS: int = 900
    EMERGENCY_RAID_MIN_KILLS: int = 1
    EMERGENCY_RAID_MAX_KILLS: int = 3

    EMERGENCY_FAMINE_CONVERT_SCOUTS_TO_WORKERS: int = 1
    EMERGENCY_FAMINE_CONVERT_SOLDIERS_TO_WORKERS: int = 1

    # Territory
    TERR_CELL: int = 6
    TERR_DECAY_PER_TICK: float = 0.015
    TERR_DIFFUSE: float = 0.06

    TERR_INFL_WORKER: float = 0.10
    TERR_INFL_SCOUT: float = 0.20
    TERR_INFL_SOLDIER: float = 0.16

    TERR_AMBIENT_ENEMY_PUSH: float = 0.0004
    TERR_ENEMY_NOISE: float = 0.010

    TERR_BORDER_INCIDENT_PRESSURE: float = 0.72
    TERR_EXPANSION_CONTROL: float = 0.58
    TERR_EVENT_COOLDOWN_TICKS: int = 300

    TERR_HOME_BIAS_RADIUS_CELLS: int = 5
    TERR_HOME_BIAS_VALUE: float = 0.6
    TERR_PRESSURE_SAMPLE_RADIUS_CELLS: int = 4

    # Enemies: Red ants
    REDANT_ENABLE: bool = True
    REDANT_BASE_SPAWN_CHANCE_PER_TICK: float = 0.0028
    REDANT_SPAWN_PRESSURE_MULT: float = 1.0
    REDANT_MAX_ALIVE: int = 5
    REDANT_SPEED: float = 28.0
    REDANT_HP: int = 3
    REDANT_TERR_INFLUENCE: float = 0.16

    # Combat (1)
    COMBAT_ENABLE: bool = True
    COMBAT_SCAN_RADIUS: float = 14.0
    COMBAT_ENGAGE_RADIUS: float = 4.0
    COMBAT_TICK_COOLDOWN: int = 10

    ANT_HP_MAX: int = 4
    ANT_WORKER_ATK: int = 1
    ANT_SCOUT_ATK: int = 1
    ANT_SOLDIER_ATK: int = 3
    REDANT_ATK: int = 1

    # Economy
    #
    # World food regeneration is the colony's real budget, and it sets the
    # equilibrium population: roughly
    #   (FOOD_PER_SOURCE / FOOD_SOURCE_RESPAWN_SECONDS) / FOOD_UPKEEP_PER_ANT_PER_SEC
    # Note the naive figure overstates it: measured over long runs, combat
    # attrition spends ~2/3 of the food budget on replacement births (at
    # GROWTH_EGG_FOOD_COST each), so the realised equilibrium is roughly a
    # third of that. At these values the world carries ~20-40 ants. Retune
    # the respawn interval, not the ants, to change how big a colony the
    # world can support.
    FOOD_UPKEEP_PER_ANT_PER_SEC: float = 0.015
    FOOD_RESERVE_BUFFER_SEC: float = 60.0
    FOOD_SOURCE_MIN_DIST_FROM_NEST: float = 20.0
    FOOD_SOURCE_RESPAWN_SECONDS: float = 38.0

    # Growth
    GROWTH_ENABLE: bool = True
    GROWTH_EGG_FOOD_COST: float = 6.0
    # Food store must exceed reserve_target * this to lay an egg. Sized to
    # damp overshoot: the colony starts on a one-time windfall (initial
    # store plus standing food) far larger than the sustainable regen rate,
    # and a thinner cushion converts that windfall into a population the
    # world cannot feed, which then crashes well past equilibrium.
    GROWTH_SURPLUS_MULT: float = 2.5
    GROWTH_MIN_TICKS_BETWEEN_BIRTHS: int = 90
    GROWTH_MAX_POPULATION: int = 60

    # Caste production seeks these fractions rather than rolling fixed
    # weights: combat deaths and famine reassignment both drain soldiers,
    # and a fixed weight can't refill a caste that has hit zero. The
    # soldier target scales toward the threat value as border pressure
    # rises, so a colony under attack raises defenders.
    GROWTH_TARGET_SCOUT_FRAC: float = 0.08
    GROWTH_TARGET_SOLDIER_FRAC: float = 0.18
    GROWTH_THREAT_SOLDIER_FRAC: float = 0.32

    # Queen/Colony health (2)
    QUEEN_HP_MAX: int = 40
    QUEEN_THREAT_RADIUS: float = 6.0
    QUEEN_DAMAGE_PER_HIT: int = 2

    # Without regeneration queen HP is a one-way ratchet and every long
    # run ends in her death regardless of how well the colony plays. She
    # recovers only while the colony is fed and the nest is clear, so
    # surviving damage is earned through the food economy.
    QUEEN_REGEN_PER_SEC: float = 0.20
    QUEEN_REGEN_MAX_HUNGER: float = 0.50
    QUEEN_REGEN_SAFE_RADIUS: float = 14.0

    # Objectives (3)
    OBJ_ENABLE: bool = True
    OBJ_CLAIM_RADIUS: float = 10.0
    OBJ_CLAIM_CONTROL_THRESHOLD: float = 0.62
    OBJ_CLAIM_PRESSURE_REDUCTION: float = 0.06  # reduces measured pressure when claimed
    OBJ_MAX_CLAIMS: int = 3

    # Chapters
    CHAPTER_ENABLE: bool = True
    CHAPTER_COOLDOWN_TICKS: int = 600
    CHAPTER_WINDOW_TICKS: int = 900
    CHAPTER_END_GRACE_TICKS: int = 360

    # Chronicle
    CHRONICLE_SHOW: bool = True
    CHRONICLE_N_EVENTS: int = 12

    # Debug/HUD
    HUD_EVERY_TICKS: int = 15
    DEBUG_ENABLE: bool = True
    DEBUG_EVERY_TICKS: int = 120
    DEBUG_PHERO_MAP_RADIUS_CELLS: int = 8
    DEBUG_PHERO_MAP_MODE: str = "territory"  # "food" | "home" | "territory"
