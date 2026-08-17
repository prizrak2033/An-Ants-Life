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


def choose_intent(state: 'GameState', ant: 'Ant') -> Intent:
    """Choose the next action for an ant based on its role and current state."""
    cfg = state.cfg
    nest = state.nest_pos  # Use cached nest position

    # Soldiers: intercept nearest enemy near nest / within scan radius
    if ant.role == Role.SOLDIER:
        e, d = _closest_enemy(state, ant.x, ant.y, cfg.COMBAT_SCAN_RADIUS)
        if e is not None:
            return Intent(target=(e.x, e.y), deposit_channel="home")
        # patrol around nest
        return Intent(target=_rand_point(cfg, nest[0], nest[1], 18.0), deposit_channel="home")

    # Workers: forage when empty, return home when carrying.
    #
    # Trail roles follow the standard stigmergy invariant: only an ant
    # actually carrying food lays the "food" trail (marking the route back
    # to a real source), while searching ants lay "home" breadcrumbs and
    # climb the food gradient outward to get recruited to that source.
    if ant.role == Role.WORKER:
        if ant.carrying > 0:
            return Intent(target=nest, deposit_channel="food")
        # sense nearby food directly
        src = state.world.nearest_food((ant.x, ant.y), cfg.ANT_SENSE_RADIUS)
        if src is not None:
            return Intent(target=(src.x, src.y), deposit_channel="home")
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
    return Intent(target=_wander_point(cfg, ant, 42.0, turn_spread=0.25), deposit_channel="home")
