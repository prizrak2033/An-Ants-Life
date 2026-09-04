"""
Ant AI decision-making system.

This module contains the logic for ant behavior, including:
- Movement target selection based on role
- Enemy detection and engagement
- Pheromone following for foraging
- Random exploration and patrolling
"""

import random
import math
from typing import Tuple, Optional, TYPE_CHECKING
from ants.intents import Intent
from ants.roles import Role
from colony.directives import DirectiveKind

if TYPE_CHECKING:
    from state import GameState
    from ants.ant import Ant


def _rand_point(cfg, cx: float, cy: float, r: float) -> Tuple[float, float]:
    """Generate a random point within radius r of (cx, cy), clamped to world bounds."""
    x = cx + (random.random() - 0.5) * 2 * r
    y = cy + (random.random() - 0.5) * 2 * r
    x = min(max(0, x), cfg.WORLD_W)
    y = min(max(0, y), cfg.WORLD_H)
    return x, y


def _wander_point(cfg, ant: 'Ant', radius: float, turn_spread: float = 0.35) -> Tuple[float, float]:
    """Pick a wander target that mostly continues the ant's current heading,
    with a small random turn each tick, instead of a fresh independent
    direction every tick. An independent direction each tick averages out
    to a slow, memoryless random walk; persisting heading (a "correlated"
    random walk) covers ground far faster, closer to how real foragers move.
    """
    if ant.vx or ant.vy:
        heading = math.atan2(ant.vy, ant.vx)
    else:
        heading = random.uniform(0, 2 * math.pi)
    heading += random.uniform(-turn_spread, turn_spread)
    x = min(max(0.0, ant.x + math.cos(heading) * radius), cfg.WORLD_W)
    y = min(max(0.0, ant.y + math.sin(heading) * radius), cfg.WORLD_H)
    return x, y


def _closest_enemy(state: 'GameState', x: float, y: float, radius: float) -> Tuple[Optional[object], float]:
    """Find the closest enemy within radius using squared distance for performance.
    
    Returns:
        Tuple of (enemy object or None, actual distance to enemy or 1e9 if none found)
    """
    best = None
    best_dist_sq = radius * radius  # Use squared distance to avoid sqrt
    
    for e in state.enemies:
        dx = e.x - x
        dy = e.y - y
        dist_sq = dx * dx + dy * dy
        
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best = e
    
    # Return actual distance (sqrt) only if enemy found
    actual_dist = math.sqrt(best_dist_sq) if best is not None else 1e9
    return best, actual_dist


def _closest_laden_raider(state: 'GameState', x: float, y: float, radius: float):
    """Nearest raider actually carrying stolen food, if any is in range."""
    best = None
    best_dist_sq = radius * radius
    for e in state.enemies:
        if e.carrying <= 0:
            continue
        dx = e.x - x
        dy = e.y - y
        dist_sq = dx * dx + dy * dy
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best = e
    return best


def _flee_point(state: 'GameState', ant: 'Ant', cfg) -> Optional[Tuple[float, float]]:
    """Somewhere directly away from the nearest threat, if one is close.

    For workers and scouts only. They are not fighters - a worker has 4
    HP and 1 attack, so it loses to a 5 HP raider and an 8 HP predator
    every time - and they were the colony's largest single source of
    casualties precisely because nothing told them to leave.
    """
    if not cfg.ANT_FLEE_ENABLE:
        return None
    # At home they stand. A forager's chip damage is worthless against a
    # predator in open ground, but in front of the queen it is the
    # difference between a warrior being stopped and not.
    nest_x, nest_y = state.nest_pos
    if math.hypot(ant.x - nest_x, ant.y - nest_y) <= cfg.ANT_FLEE_HOME_RADIUS:
        return None
    threat, _ = _closest_enemy(state, ant.x, ant.y, cfg.ANT_FLEE_RADIUS)
    if threat is None:
        return None
    dx, dy = ant.x - threat.x, ant.y - threat.y
    d = math.hypot(dx, dy)
    if d < 1e-6:
        # Standing on it: any direction beats staying put. Derived from
        # the id rather than drawn at random, so a reloaded save replays.
        dx, dy, d = math.cos(ant.id), math.sin(ant.id), 1.0
    nx, ny = dx / d, dy / d
    step = cfg.ANT_FLEE_STEP

    def _reachable(ux, uy):
        """Where the ant would actually get to, after the world bounds."""
        return (min(max(0.0, ant.x + ux * step), cfg.WORLD_W),
                min(max(0.0, ant.y + uy * step), cfg.WORLD_H))

    best = _reachable(nx, ny)
    # Running straight away from something that has you against an edge
    # clamps to where you already are, which reads as standing still and
    # dying. Slide along the boundary instead: a cornered ant should try
    # to get past the threat, not freeze in front of it.
    if math.hypot(best[0] - ant.x, best[1] - ant.y) < step * 0.5:
        for ux, uy in ((-ny, nx), (ny, -nx)):
            side = _reachable(ux, uy)
            if math.hypot(side[0] - ant.x, side[1] - ant.y) > \
               math.hypot(best[0] - ant.x, best[1] - ant.y):
                best = side
    return best


def choose_intent(state: 'GameState', ant: 'Ant', dt: float = 1.0 / 30.0) -> Intent:
    """Choose the next action for an ant based on its role and current state."""
    cfg = state.cfg
    nest = state.nest_pos  # Use cached nest position
    board = state.directives

    # Praetorians hold the queen's chamber and nothing moves them - not a
    # defend mark, not a fleeing thief, not a recall. That immovability is
    # the whole of what they offer, which is why they are checked before
    # every other consideration.
    if ant.role == Role.PRAETORIAN:
        # Leashed to the chamber: chasing something to the edge of its
        # reach must not become chasing it across the map.
        if math.hypot(ant.x - nest[0], ant.y - nest[1]) > cfg.PRAETORIAN_GUARD_RADIUS:
            return Intent(target=nest, deposit_channel="home")
        e, _ = _closest_enemy(state, ant.x, ant.y, cfg.PRAETORIAN_GUARD_RADIUS)
        if e is not None:
            return Intent(target=(e.x, e.y), deposit_channel="home")
        return Intent(
            target=_rand_point(cfg, nest[0], nest[1], cfg.PRAETORIAN_GUARD_RADIUS * 0.7),
            deposit_channel="home")

    # Rally: the colony pulls back to the nest. Foraging stops entirely,
    # which is the cost - soldiers still answer anything already on top
    # of them, since falling back is not the same as refusing to fight.
    if state.policy.rally:
        if ant.role == Role.SOLDIER:
            e, _ = _closest_enemy(state, ant.x, ant.y, cfg.COMBAT_SCAN_RADIUS)
            if e is not None:
                return Intent(target=(e.x, e.y), deposit_channel="home")
        return Intent(target=nest, deposit_channel="home")

    # Soldiers: run down food thieves first, else intercept nearby enemies
    if ant.role == Role.SOLDIER:
        thief = _closest_laden_raider(state, ant.x, ant.y, cfg.SOLDIER_RECOVERY_RADIUS)
        if thief is not None:
            return Intent(target=(thief.x, thief.y), deposit_channel="home")
        e, d = _closest_enemy(state, ant.x, ant.y, cfg.COMBAT_SCAN_RADIUS)
        if e is not None:
            return Intent(target=(e.x, e.y), deposit_channel="home")
        # Patrol the nest, or a defend mark if the player has set a line.
        # Membership of the detachment is decided once per tick for the
        # guard as a whole, since the limit is a group property: a share
        # of it, and never below a floor left at the nest.
        if ant.id in state.colony.emergency.get("defend_detachment", ()):
            hold = board.nearest(DirectiveKind.DEFEND, ant.x, ant.y)
            if hold is not None:
                return Intent(target=_rand_point(cfg, hold.x, hold.y,
                                                 cfg.DIRECTIVE_DEFEND_PATROL_RADIUS),
                              deposit_channel="home")
        return Intent(target=_rand_point(cfg, nest[0], nest[1], 18.0), deposit_channel="home")

    # Everything below is a worker or a scout - every soldier path above
    # returns - and neither of them fights. Running comes before the
    # errand, whatever the errand is: a laden worker that presses on
    # through a predator loses both itself and the food it was carrying.
    # It keeps laying its own channel while it runs, so a trail is not
    # forgotten just because it was interrupted.
    flee = _flee_point(state, ant, cfg)
    if flee is not None:
        return Intent(target=flee,
                      deposit_channel="food" if ant.carrying > 0 else "home")

    # Workers: forage when empty, return home when carrying.
    #
    # Trail roles follow the standard stigmergy invariant: only an ant
    # actually carrying food lays the "food" trail (marking the route back
    # to a real source), while searching ants lay "home" breadcrumbs and
    # climb the food gradient outward to get recruited to that source.
    if ant.role == Role.WORKER:
        if ant.carrying > 0:
            ant.recruited_to = None  # it has food; the errand is over
            return Intent(target=nest, deposit_channel="food")

        # Food it can already see beats any standing order. This ordering
        # is what keeps a mark from dragging workers past closer pickings
        # and doubling everyone's round trip.
        src = state.world.nearest_food((ant.x, ant.y), cfg.ANT_SENSE_RADIUS)
        if src is not None:
            ant.recruited_to = None
            return Intent(target=(src.x, src.y), deposit_channel="home")

        # Honour a mark already answered.
        if ant.recruited_to is not None:
            mark = board.by_id(ant.recruited_to)
            if mark is None:
                ant.recruited_to = None
            else:
                return Intent(target=(mark.x, mark.y), deposit_channel="home")

        # Otherwise consider answering one - only searching ants are
        # eligible, and only from nearby.
        mark = board.try_recruit(ant, dt)
        if mark is not None:
            ant.recruited_to = mark.id
            return Intent(target=(mark.x, mark.y), deposit_channel="home")

        # follow a real forager's trail outward toward its source
        pt = state.pheromones.sample_best_direction(
            "food", (ant.x, ant.y), step=cfg.PHERO_FOLLOW_STEP, away_from=nest
        )
        if pt is not None:
            return Intent(target=pt, deposit_channel="home")
        # wander, persisting heading so exploration actually covers ground
        return Intent(target=_wander_point(cfg, ant, 20.0), deposit_channel="home")

    # Scouts: wide roam, sense food, return home when carrying
    if ant.carrying > 0:
        return Intent(target=nest, deposit_channel="food")
    src = state.world.nearest_food((ant.x, ant.y), cfg.ANT_SENSE_RADIUS)
    if src is not None:
        return Intent(target=(src.x, src.y), deposit_channel="home")
    pt = state.pheromones.sample_best_direction(
        "food", (ant.x, ant.y), step=cfg.PHERO_FOLLOW_STEP, away_from=nest
    )
    if pt is not None and random.random() < 0.4:
        return Intent(target=pt, deposit_channel="home")
    # Range around an explore mark if one is set, else around the nest.
    survey = board.nearest(DirectiveKind.EXPLORE, ant.x, ant.y)
    if survey is not None:
        return Intent(target=_rand_point(cfg, survey.x, survey.y,
                                         cfg.DIRECTIVE_EXPLORE_ROAM_RADIUS),
                      deposit_channel="home")
    return Intent(target=_wander_point(cfg, ant, 42.0, turn_spread=0.25), deposit_channel="home")
