"""
Configuration settings for the Ant Colony Simulation.

This module contains all the simulation parameters, including world size,
ant behavior, combat settings, and various game mechanics.
"""

from dataclasses import dataclass
from typing import Tuple


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

    # Workers and scouts break off and run when a threat gets this close.
    # They had no awareness of enemies at all, which made them 62% of all
    # casualties over long runs - and they cannot win those fights: a
    # worker has 4 HP and 1 attack against a 5 HP raider or an 8 HP
    # predator, so it loses every time. Losing foragers is what the
    # colony can least afford, since replacing each one costs a full egg
    # out of the same food budget that feeds everybody.
    #
    # Fleeing works because every enemy is slower than an ant (40 against
    # 34, 28 and 22), so this is an escape rather than a delay. The radius
    # sits between COMBAT_ENGAGE_RADIUS, so they break off before contact,
    # and the soldiers' COMBAT_SCAN_RADIUS, so a fleeing worker draws its
    # escort in rather than running past it.
    #
    # ANT_FLEE_HOME_RADIUS is the exception, and it is not a detail - it
    # is the whole mechanic. Inside it they stand and fight. Fleeing
    # everywhere was measured and it worked exactly as designed on its
    # own terms - casualties fell 46%, births finally overtook losses,
    # and the standing population went from 27 to 43 - while survival
    # collapsed from 6/6 to 4/6, and to 2/6 at wider radii.
    #
    # The reason is that a worker's hopeless chip damage was holding the
    # nest up. A warrior has 3 HP and a worker does 1, so three of them
    # kill one before it reaches the queen; they were dying, but they
    # were dying in front of her. Take that away and warriors walk in.
    # So foragers run in the field, where predators and raiders hunt them
    # for nothing, and hold their ground at home, where dying buys
    # something.
    #
    # Off by default, on the evidence. Over 32 paired seeds at 900s the
    # mechanic does everything it was built to do and still costs the game:
    # casualties fall 41% (-37.6 per run, 95% CI [-44.3, -30.2]) and the
    # standing population rises by about ten ants (+9.9, CI [+4.6, +15.6]),
    # both real effects, with food throughput unchanged. Survival went
    # 29/32 to 23/32, and the paired split was 7 seeds where turning this
    # on killed a colony that otherwise lived against 1 the other way
    # (p=0.07 - short of the usual bar, but lopsided, and pointing the
    # same way as an earlier twelve-seed run).
    #
    # Which is the trade: a colony that is bigger, better fed and losing
    # fewer ants, and that dies more often, because the deaths that end
    # the game are the ones at the queen's chamber and those are exactly
    # the ones this stops paying for. Survival is the objective;
    # population and casualty counts are means to it.
    #
    # Worth turning back on if nest defence is ever carried by something
    # other than workers throwing themselves at warriors - the economic
    # half of this is measured and real.
    ANT_FLEE_ENABLE: bool = False
    ANT_FLEE_RADIUS: float = 9.0
    ANT_FLEE_STEP: float = 16.0
    ANT_FLEE_HOME_RADIUS: float = 22.0
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
    TERRAIN_DETOUR_SECONDS: float = 0.4667

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
    # How fast scent spreads to neighbouring cells, per second. It was
    # applied once per tick and so scaled with framerate; 0.10 a tick at
    # 30fps is the 3.0 a second kept here.
    PHERO_DIFFUSE: float = 3.0
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
    EMERGENCY_FAMINE_MIN_SECONDS: float = 6.0
    EMERGENCY_FAMINE_STRESS_BONUS: float = 0.25

    EMERGENCY_RAID_STRESS_GATE: float = 0.90
    EMERGENCY_RAID_CHANCE_PER_SEC: float = 0.075
    EMERGENCY_RAID_COOLDOWN_SECONDS: float = 30.0
    EMERGENCY_RAID_MIN_KILLS: int = 1
    EMERGENCY_RAID_MAX_KILLS: int = 3

    EMERGENCY_FAMINE_CONVERT_SCOUTS_TO_WORKERS: int = 1
    EMERGENCY_FAMINE_CONVERT_SOLDIERS_TO_WORKERS: int = 1

    # Territory
    TERR_CELL: int = 6
    # All per second. These were per tick, and TerritoryModel.update()
    # took no dt at all, so the entire territory model - and the pressure
    # signal that enemy spawns and stress read from it - ran a third slow
    # whenever the frame rate dipped toward MAX_DT. Each value is its old
    # per-tick figure times the 30fps target, so 30fps play is unchanged.
    TERR_DECAY_PER_SEC: float = 0.45
    TERR_DIFFUSE_PER_SEC: float = 1.8

    TERR_INFL_WORKER: float = 3.0
    TERR_INFL_SCOUT: float = 6.0
    TERR_INFL_SOLDIER: float = 4.8

    TERR_AMBIENT_ENEMY_PUSH_PER_SEC: float = 0.012
    TERR_ENEMY_NOISE_PER_SEC: float = 0.30

    TERR_BORDER_INCIDENT_PRESSURE: float = 0.72
    TERR_EXPANSION_CONTROL: float = 0.58
    TERR_EVENT_COOLDOWN_SECONDS: float = 10.0

    TERR_HOME_BIAS_RADIUS_CELLS: int = 5
    TERR_HOME_BIAS_VALUE: float = 0.6
    TERR_PRESSURE_SAMPLE_RADIUS_CELLS: int = 4

    # Enemies (shared)
    ENEMY_ENABLE: bool = True
    # Per second, not per tick. Food respawn was converted to a time rate
    # so the economy would not shift with framerate; enemy pressure - the
    # other half of the same balance - was left per tick, and Timekeeper
    # hands out a real variable dt clamped at MAX_DT. A loaded machine
    # dropping to 20fps therefore lost a third of its enemy spawns while
    # food regen held steady, so the played game was quietly easier than
    # the benchmarked one. 0.0045 a tick at 30fps is the 0.135 kept here.
    ENEMY_BASE_SPAWN_CHANCE_PER_SEC: float = 0.135
    # Left at 1.0 deliberately. Scaling spawns harder with lost territory
    # was tested at 1.3 and 1.6 and made outcomes *less* responsive to
    # play, not more: a colony already losing ground gets buried faster,
    # which is a spiral rather than a challenge.
    ENEMY_SPAWN_PRESSURE_MULT: float = 1.0
    # Retuned against the corrected 26% soldier baseline. Once the caste
    # default stopped being a trap, passive play survived 11 of 12 runs
    # and there was simply no room left for attention to matter - some of
    # the old difficulty had been resting on the bad default rather than
    # on the enemies.
    #
    # At six concurrent and this spawn rate, passive play sits at 6/12
    # while attentive play (recall during a siege, plus forage marks)
    # reaches 8/12 with 16% more food. Pushing further was tested and
    # rejected: at seven concurrent with pressure feedback, survival fell
    # to 1/8 regardless of play, which is not difficulty but noise.
    ENEMY_MAX_ALIVE: int = 6

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
    WARRIOR_TERR_INFLUENCE: float = 4.8   # per second

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
    RAIDER_TERR_INFLUENCE: float = 3.0    # per second
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
    PREDATOR_TERR_INFLUENCE: float = 6.0  # per second
    PREDATOR_HUNT_RADIUS: float = 24.0

    # Combat (1)
    COMBAT_ENABLE: bool = True
    COMBAT_SCAN_RADIUS: float = 14.0
    COMBAT_ENGAGE_RADIUS: float = 4.0
    COMBAT_COOLDOWN_SECONDS: float = 0.3333

    ANT_HP_MAX: int = 4
    ANT_WORKER_ATK: int = 1
    ANT_SCOUT_ATK: int = 1
    ANT_SOLDIER_ATK: int = 3

    # Praetorian guard.
    #
    # Earned, not bred: a soldier that fights an intruder inside the
    # queen's chamber is promoted, which ties the reward to precisely the
    # event that decides games. A praetorian then never leaves her - not
    # for a defend mark, not to chase a thief, not on recall.
    #
    # Deliberately given no combat bonus. Measurement is unambiguous that
    # a garrison of zero *is* death, so a caste that cannot be drawn away
    # is already strong on position alone; stacking damage on top would
    # likely trivialise the game. BONUS_HP is the gentler knob if they
    # ever measure too weak.
    #
    # The cost is real: promotion consumes a field soldier and leaves a
    # deficit the queen must pay to refill, and a praetorian neither
    # forages nor holds ground anywhere but home.
    PRAETORIAN_ENABLE: bool = True
    PRAETORIAN_MAX: int = 6
    PRAETORIAN_GUARD_RADIUS: float = 10.0
    PRAETORIAN_CHAMBER_RADIUS: float = 11.0
    PRAETORIAN_BONUS_HP: int = 0
    # Enemy attack lives per kind, in the enemy block above.

    # Economy
    #
    # World food regeneration is the colony's real budget, and it sets the
    # equilibrium population. Replacement births are paid out of the same
    # budget as upkeep, so the standing population the world can hold is
    #
    #   P = (regen - GROWTH_EGG_FOOD_COST * loss_rate) / FOOD_UPKEEP_PER_ANT_PER_SEC
    #   where regen = FOOD_PER_SOURCE / FOOD_SOURCE_RESPAWN_SECONDS
    #
    # That formula predicts measured outcomes closely: at a 38s respawn it
    # gives 13.5 against an observed 15, at 30s it gives 28 against 27, and
    # at 24s it gives 44 against 43. Use it rather than guessing.
    #
    # The share going to replacement is the thing to understand here. At a
    # measured 0.098 ants lost per second, replacement alone costs 0.59
    # food/s - about three quarters of everything the world produces at a
    # 38s respawn, leaving a quarter to actually feed anybody. That is why
    # a 38s world peaked near 52 ants and then hollowed out to 15, killing
    # a third of runs by the fifteen-minute mark: the boom was funded by
    # the one-time starting endowment (180 in sources plus 40 stored) and
    # the world could never refinance it.
    #
    # 30s buys a colony that booms to ~56 and settles near 27 with no
    # famine and every run surviving - an arc with a real carrying
    # capacity in it. Going further (24s holds ~43) removes the pressure
    # rather than balancing it. Retune this interval, not the ants, to
    # change how big a colony the world supports.
    FOOD_UPKEEP_PER_ANT_PER_SEC: float = 0.015
    FOOD_RESERVE_BUFFER_SEC: float = 60.0
    FOOD_SOURCE_MIN_DIST_FROM_NEST: float = 20.0
    FOOD_SOURCE_EDGE_MARGIN: float = 10.0
    FOOD_SOURCE_RESPAWN_SECONDS: float = 30.0

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
    # Raised from 0.18 after measuring the caste mix directly: holding a
    # fixed 18% survived 6 of 12 runs while 28% survived 12 of 12 *and*
    # gathered more food (857 deposits against 752), because a colony
    # that keeps its guard keeps its workers. Every colony death is the
    # queen killed with an empty nest, so under-defending was not a
    # trade-off at all - it was simply losing. The old default sat at the
    # dangerous end of that curve, which made the starting position a
    # trap rather than a choice.
    GROWTH_TARGET_SOLDIER_FRAC: float = 0.26
    GROWTH_THREAT_SOLDIER_FRAC: float = 0.36

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
    CHAPTER_COOLDOWN_SECONDS: float = 20.0
    CHAPTER_WINDOW_SECONDS: float = 30.0
    CHAPTER_END_GRACE_SECONDS: float = 12.0
    # A chapter must run this long before anything can displace it, and
    # the challenger has to fit clearly better rather than by a hair.
    # Without both, the saga churned out chapters lasting 0-3 seconds -
    # a list of titles rather than a story.
    CHAPTER_MIN_SECONDS: float = 10.0
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

    # ---- Audio ---------------------------------------------------------
    # Levels are linear amplitudes on the audio bus, not decibels, and are
    # summed before a soft ceiling at AUDIO_LIMITER_KNEE. Rough scale: the
    # loudest one-shot asks for 0.85 and the ambient bed sits near 0.02.
    #
    # The browser holds matching defaults so the page still makes sound if
    # it cannot reach the server, but this is the source of truth. Changing
    # a level here takes effect on reload, with no rebuild.
    AUDIO_DEFAULT_VOLUME: float = 0.6

    # Ambient drone: the colony's own body. Thickens with population and
    # opens up as stress falls, so a colony in trouble sounds like one.
    # Deliberately far below the one-shots - at 0.05 + 0.05*body it
    # measured 0.061 rms against 0.095 for the loudest event and sat on
    # top of the quiet blips rather than beneath them.
    AUDIO_DRONE_BASE: float = 0.02
    AUDIO_DRONE_PER_POP: float = 0.02
    AUDIO_DRONE_DEAD: float = 0.008
    AUDIO_DRONE_POP_REFERENCE: float = 30.0
    AUDIO_DRONE_CUTOFF_MIN: float = 160.0
    AUDIO_DRONE_CUTOFF_RANGE: float = 340.0

    # Threat throb: only present when something is near the nest. Both the
    # level and the modulation depth scale with threat, so at threat zero
    # the branch is genuinely silent rather than merely quiet - an LFO
    # sums into a gain param instead of scaling it, so a fixed depth here
    # would sound the tone continuously at every threat level.
    AUDIO_THREAT_LEVEL: float = 0.055
    AUDIO_THREAT_LFO_DEPTH: float = 0.05
    AUDIO_THREAT_FREQ: float = 44.0
    AUDIO_THREAT_LFO_FREQ: float = 1.6

    # Chitter: sparse clicks whose rate follows delivery income, capped so
    # a thriving colony stays a texture rather than a rattle.
    AUDIO_CHITTER_LEVEL: float = 0.05
    AUDIO_CHITTER_INCOME_REFERENCE: float = 2.2
    AUDIO_CHITTER_MAX_RATE: float = 0.9

    # Below the knee the bus is exactly unity, so a lone event arrives at
    # the level it asked for; above it the curve bends toward full scale
    # so stacked voices cannot clip.
    AUDIO_LIMITER_KNEE: float = 0.6
    # A bandpass keeps only freq/Q of white noise's spectrum, so noise
    # bursts are compensated back up. That matches on power, which
    # overshoots on peak because noise peaks well above its rms; this
    # trims for crest factor.
    AUDIO_NOISE_CREST_TRIM: float = 0.63

    # Nothing retriggers faster than this per kind, and no more than
    # AUDIO_MAX_VOICES sound at once. A colony under sustained attack
    # would otherwise stack dozens of identical voices into mud.
    AUDIO_EVENT_COOLDOWN: float = 0.35
    AUDIO_MAX_VOICES: int = 8

    # One-shots, as (event kind, voice, frequency Hz, seconds, level).
    # Only events the chronicle already considers worth reporting appear
    # here; a sound per forage delivery would be a machine gun rather than
    # information. The level column is the mix - it is what makes a strike
    # on the queen read as more urgent than a policy tick.
    AUDIO_EVENT_VOICES: Tuple[Tuple[str, str, float, float, float], ...] = (
        ("queen_hit",                 "thud",   70.0, 0.45, 0.85),
        ("emergency_raid",            "noise", 320.0, 0.55, 0.70),
        ("emergency_famine_start",    "fall",  420.0, 0.90, 0.45),
        ("emergency_famine_end",      "rise",  330.0, 0.80, 0.40),
        ("ending",                    "fall",  180.0, 2.40, 0.60),

        ("praetorian_raised",         "chord", 392.0, 0.70, 0.34),
        ("milestone",                 "chord", 523.0, 0.90, 0.32),
        ("chapter_start",             "bell",  494.0, 1.60, 0.30),
        ("chapter_end",               "bell",  330.0, 1.60, 0.24),

        ("enemy_loot_recovered",      "blip",  740.0, 0.20, 0.28),
        ("enemy_escape",              "fall",  520.0, 0.40, 0.30),
        ("enemy_steal",               "thud",  140.0, 0.22, 0.30),
        ("objective_claimed",         "blip",  620.0, 0.16, 0.20),
        ("territory_expansion",       "blip",  440.0, 0.16, 0.14),
        ("territory_border_incident", "noise", 240.0, 0.25, 0.26),
        ("rally_called",              "fall",  300.0, 0.55, 0.40),
        ("rally_ended",               "rise",  300.0, 0.45, 0.28),
        ("directive_placed",          "blip",  880.0, 0.12, 0.16),
        ("emergency_famine_reassign", "blip",  300.0, 0.18, 0.18),
        ("policy_changed",            "blip",  520.0, 0.10, 0.12),
    )

    # Debug/HUD
    # These two stay in ticks on purpose. They are a render cadence -
    # how often to reprint - not a simulation rate, and "every N
    # frames" is the right unit for that. Everything that affects the
    # world is expressed per second.
    HUD_EVERY_TICKS: int = 15
    DEBUG_ENABLE: bool = True
    DEBUG_EVERY_TICKS: int = 120
    DEBUG_PHERO_MAP_RADIUS_CELLS: int = 8
    DEBUG_PHERO_MAP_MODE: str = "territory"  # "food" | "home" | "territory"
