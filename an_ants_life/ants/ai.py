import random
import math
from ants.intents import Intent
from ants.roles import Role

def _rand_point(cfg, cx, cy, r):
    x = cx + (random.random() - 0.5) * 2 * r
    y = cy + (random.random() - 0.5) * 2 * r
    x = max(0, min(cfg.WORLD_W, x))
    y = max(0, min(cfg.WORLD_H, y))
    return x, y

def _closest_enemy(state, x, y, radius):
    best = None
    bestd = 1e9
    for e in state.enemies:
        d = math.hypot(e.x - x, e.y - y)
        if d < bestd and d <= radius:
            bestd = d
            best = e
    return best, bestd

def choose_intent(state, ant):
    cfg = state.cfg
    nest = (cfg.NEST_X, cfg.NEST_Y)

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
