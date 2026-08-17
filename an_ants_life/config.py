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
    # Soldiers break off to run down a raider that is actually carrying
    # loot, well beyond their normal nest patrol. Laden raiders are slower
    # than an ant, so this is a chase the colony can win - and it is the
    # only way stolen food ever comes back.
    SOLDIER_RECOVERY_RADIUS: float = 48.0

    # Food sources
    INITIAL_FOOD_SOURCES: int = 6
    FOOD_PER_SOURCE: float = 30.0
    CARRY_CAPACITY: float = 1.0
    INITIAL_FOOD_STORE: float = 40.0

    # Terrain / biomes
    #
    # Blobs are deliberately small and scattered rather than long walls:
    # nothing in the game pathfinds, so an ant only gets past an obstacle
    # by sliding along it, and a long wall would strand foragers behind it.
    TERRAIN_ENABLE: bool = True
    TERRAIN_CELL: int = 3
    TERRAIN_NEST_CLEAR_RADIUS: float = 14.0

    TERRAIN_ROCK_BLOBS: int = 8
    TERRAIN_SAND_BLOBS: int = 5
    TERRAIN_LITTER_BLOBS: int = 7
    TERRAIN_BLOB_MIN_R: float = 4.0
    TERRAIN_BLOB_MAX_R: float = 10.0

    # Water is the only true barrier, so it is kept to a few small ponds -
    # every unit of hard obstacle is surface for ants to jam against.
    TERRAIN_WATER_BLOBS: int = 3
    TERRAIN_WATER_MAX_R: float = 5.0

    ROCK_SPEED_MULT: float = 0.45

    # How long a mover commits to a detour heading after hitting a face.
    # Without persistence it re-aims at the obstacle the very next tick
    # and vibrates against it instead of travelling around.
    TERRAIN_DETOUR_TICKS: int = 14

    SAND_SPEED_MULT: float = 0.85
    LITTER_SPEED_MULT: float = 0.95
    # Sand is the interesting one: trails burn off far faster, so a supply
    # line dragged across it needs constant traffic to survive.
    SAND_PHERO_DECAY_MULT: float = 2.2
    LITTER_PHERO_DECAY_MULT: float = 0.8
    # How much more often food appears on leaf litter than bare ground,
    # which is what makes a patch of ground worth holding.
    LITTER_FOOD_BIAS: float = 5.0

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

    # Enemies (shared)
    ENEMY_ENABLE: bool = True
    ENEMY_BASE_SPAWN_CHANCE_PER_TICK: float = 0.0028
    ENEMY_SPAWN_PRESSURE_MULT: float = 1.0
    # Four rather than the five of the single-enemy era: each kind is
    # individually more dangerous than the old uniform red ant, so the same
    # concurrent cap measured considerably harsher.
    ENEMY_MAX_ALIVE: int = 4

    # Spawn mix. Warriors stay the most common threat so nest defence
    # remains the baseline concern; predators are rare because they are
    # individually expensive to deal with.
    ENEMY_WEIGHT_WARRIOR: float = 0.52
    ENEMY_WEIGHT_RAIDER: float = 0.36
    ENEMY_WEIGHT_PREDATOR: float = 0.08

    # Warrior: the classic red ant - drives at the nest, hits the queen.
    WARRIOR_HP: int = 3
    WARRIOR_SPEED: float = 28.0
    WARRIOR_ATK: int = 1
    WARRIOR_TERR_INFLUENCE: float = 0.16

    # Raider: fast and fragile. Ignores the queen, robs a food source and
    # runs for the edge; food that leaves the map is gone for good, so
    # intercepting one before it escapes is the whole counterplay.
    # Tough enough to usually survive the loot pause. At 2 HP a raider died
    # to two worker hits every time, and since trails concentrate foragers
    # exactly at food piles it never once got away - which made both the
    # theft and the recovery chase dead mechanics.
    RAIDER_HP: int = 5
    RAIDER_SPEED: float = 34.0
    RAIDER_ATK: int = 1
    RAIDER_TERR_INFLUENCE: float = 0.10
    RAIDER_STEAL_AMOUNT: float = 8.0
    RAIDER_STEAL_RADIUS: float = 3.0
    # Looting holds the raider still beside the pile, and the load slows
    # its run for the edge. Without both, the counterplay does not exist:
    # sources often sit near an edge, so a grab-and-go raider was clear of
    # the map about 0.14s after stealing - roughly four ticks, when the
    # combat cooldown alone is ten.
    RAIDER_STEAL_SECONDS: float = 2.5
    RAIDER_LADEN_SPEED_MULT: float = 0.55

    # Predator: a solitary hunter. Slow, tanky, hits hard, and cares about
    # neither the queen nor food - it eats foragers in the open, which is
    # the one threat that nest-hugging soldiers do not answer.
    PREDATOR_HP: int = 8
    PREDATOR_SPEED: float = 22.0
    # At 2 it two-shot workers, and because a predator actively hunts ants
    # instead of beelining past them like a warrior, that alone drove
    # colonies from a ~20-40 population down to single digits.
    PREDATOR_ATK: int = 1
    PREDATOR_TERR_INFLUENCE: float = 0.20
    PREDATOR_HUNT_RADIUS: float = 24.0

    # Combat (1)
    COMBAT_ENABLE: bool = True
    COMBAT_SCAN_RADIUS: float = 14.0
    COMBAT_ENGAGE_RADIUS: float = 4.0
    COMBAT_TICK_COOLDOWN: int = 10

    ANT_HP_MAX: int = 4
    ANT_WORKER_ATK: int = 1
    ANT_SCOUT_ATK: int = 1
    ANT_SOLDIER_ATK: int = 3
    # Enemy attack lives per kind, in the enemy block above.

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
    FOOD_SOURCE_EDGE_MARGIN: float = 10.0
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
    # A chapter must run this long before anything can displace it, and
    # the challenger has to fit clearly better rather than by a hair.
    # Without both, the saga churned out chapters lasting 0-3 seconds -
    # a list of titles rather than a story.
    CHAPTER_MIN_TICKS: int = 300
    CHAPTER_SUPERSEDE_MARGIN: float = 0.5

    # Player agency
    #
    # Directives are marks on the world, not orders to ants: the cost of
    # one is that it fades and that only so many can be held at once.
    # A forage mark works purely by laying scent the normal recruitment
    # loop then follows, so agency rides on the emergent machinery rather
    # than bypassing it.
    DIRECTIVE_MAX_PER_KIND: int = 3
    DIRECTIVE_LIFETIME_SECONDS: float = 75.0
    # A forage mark recruits nearby searching ants rather than laying
    # scent. Depositing pheromone was a broadcast - it diffuses, so one
    # mark pulled the whole workforce across the map and roughly halved
    # deposits. These three numbers are the whole cost model: only ants
    # within the radius hear it, only so many can answer, and nearer ones
    # answer more readily.
    DIRECTIVE_RECRUIT_RADIUS: float = 38.0
    DIRECTIVE_RECRUIT_CAP: int = 8
    DIRECTIVE_RECRUIT_CHANCE_PER_SEC: float = 1.2
    DIRECTIVE_DEFEND_PATROL_RADIUS: float = 12.0
    # A defend mark can only ever draw part of the guard, and never below
    # an absolute floor at the nest.
    #
    # Both limits are load-bearing. Every colony death measured - in
    # played and passive runs alike - is the queen being killed with the
    # garrison at zero; starvation and border pressure are never the
    # proximate cause. A proportional cap alone is not enough protection
    # when the corps is small, because half of six is three, and a
    # detachment of three still measured as decisive (7/12 surviving
    # against 10/12 without it).
    DIRECTIVE_DEFEND_MAX_SHARE: float = 0.5
    DIRECTIVE_DEFEND_MIN_GARRISON: int = 4
    DIRECTIVE_EXPLORE_ROAM_RADIUS: float = 26.0

    # Delivery rate is spiky per tick, so the carrying-capacity readout is
    # smoothed over roughly this long before being shown.
    CAPACITY_SMOOTHING_SECONDS: float = 25.0
    # Share of world food regen left for upkeep once combat attrition has
    # taken its cut on replacement births. Calibrated against the
    # populations runs actually settle at (~20-40) rather than from the
    # attrition fraction alone, which put the line at 18 and flagged
    # perfectly healthy colonies as over-extended.
    CAPACITY_ATTRITION_ALLOWANCE: float = 0.55

    POLICY_MAX_SCOUT_FRAC: float = 0.35
    POLICY_MAX_SOLDIER_FRAC: float = 0.60

    # Persistence
    AUTOSAVE_ENABLE: bool = True
    AUTOSAVE_EVERY_SECONDS: float = 30.0

    # Chronicle / history
    CHRONICLE_SHOW: bool = True
    CHRONICLE_N_EVENTS: int = 12
    # The raw log is a bounded ring: it was previously unbounded and grew
    # for the whole session. MAJOR beats are kept separately and in full,
    # so the saga survives regardless of this cap.
    HISTORY_MAX_EVENTS: int = 600
    HISTORY_MAX_NOTABLE: int = 240

    # Debug/HUD
    HUD_EVERY_TICKS: int = 15
    DEBUG_ENABLE: bool = True
    DEBUG_EVERY_TICKS: int = 120
    DEBUG_PHERO_MAP_RADIUS_CELLS: int = 8
    DEBUG_PHERO_MAP_MODE: str = "territory"  # "food" | "home" | "territory"
