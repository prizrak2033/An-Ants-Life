"""
Enemy entity.

Per-kind stats are copied onto the instance at spawn rather than looked
up from config in the movement/combat loops, matching how Ant carries
its own hp.
"""
from __future__ import annotations
from dataclasses import dataclass

from enemies.kinds import EnemyKind


@dataclass
class Enemy:
    id: int
    kind: EnemyKind
    x: float
    y: float
    hp: int
    speed: float
    atk: int
    terr_influence: float

    vx: float = 0.0
    vy: float = 0.0
    last_combat_tick: int = -10_000
    detour_until_tick: int = -1
    detour_side: int = 1

    # Where it entered the map; a laden raider hauls its loot back here.
    spawn_x: float = 0.0
    spawn_y: float = 0.0

    # Raiders only: seconds spent loading up, food in hand, and whether
    # they've turned for the edge.
    steal_progress: float = 0.0
    carrying: float = 0.0
    fleeing: bool = False
    escaped: bool = False


_STAT_FIELDS = {
    EnemyKind.WARRIOR: ("WARRIOR_HP", "WARRIOR_SPEED", "WARRIOR_ATK", "WARRIOR_TERR_INFLUENCE"),
    EnemyKind.RAIDER: ("RAIDER_HP", "RAIDER_SPEED", "RAIDER_ATK", "RAIDER_TERR_INFLUENCE"),
    EnemyKind.PREDATOR: ("PREDATOR_HP", "PREDATOR_SPEED", "PREDATOR_ATK", "PREDATOR_TERR_INFLUENCE"),
}


def make_enemy(cfg, eid: int, kind: EnemyKind, x: float, y: float) -> Enemy:
    hp_f, speed_f, atk_f, terr_f = _STAT_FIELDS[kind]
    return Enemy(
        id=eid, kind=kind, x=x, y=y,
        hp=getattr(cfg, hp_f),
        speed=getattr(cfg, speed_f),
        atk=getattr(cfg, atk_f),
        terr_influence=getattr(cfg, terr_f),
        spawn_x=x, spawn_y=y,
    )
