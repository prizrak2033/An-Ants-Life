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
from typing import Tuple, Optional, Any
from ants.intents import Intent
from ants.roles import Role


def _rand_point(cfg, cx: float, cy: float, r: float) -> Tuple[float, float]:
    """Generate a random point within radius r of (cx, cy), clamped to world bounds."""
    x = cx + (random.random() - 0.5) * 2 * r
    y = cy + (random.random() - 0.5) * 2 * r
    x = min(max(0, x), cfg.WORLD_W)
    y = min(max(0, y), cfg.WORLD_H)
    return x, y


def _closest_enemy(state, x: float, y: float, radius: float) -> Tuple[Optional[Any], float]:
    """Find the closest enemy within radius using squared distance for performance."""
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

def choose_intent(state, ant) -> Intent:
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

    # Workers: forage when empty, return home when carrying
    if ant.role == Role.WORKER:
        if ant.carrying > 0:
            return Intent(target=nest, deposit_channel="home")
        # bias toward food pheromone gradient (very light)
        pt = state.pheromones.sample_best_direction("food", (ant.x, ant.y), step=cfg.PHERO_FOLLOW_STEP)
        if pt is not None:
            return Intent(target=pt, deposit_channel="food")
        # wander
        return Intent(target=_rand_point(cfg, ant.x, ant.y, 20.0), deposit_channel="food")

    # Scouts: wide roam, mark home lightly
    pt = state.pheromones.sample_best_direction("food", (ant.x, ant.y), step=cfg.PHERO_FOLLOW_STEP)
    if pt is not None and random.random() < 0.4:
        return Intent(target=pt, deposit_channel="food")
    return Intent(target=_rand_point(cfg, nest[0], nest[1], 42.0), deposit_channel="home")
