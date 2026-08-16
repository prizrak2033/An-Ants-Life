"""
Red ant enemy entity: rival-colony raiders that intrude on territory,
fight ants, and threaten the queen.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RedAnt:
    id: int
    x: float
    y: float
    hp: int
    vx: float = 0.0
    vy: float = 0.0
    last_combat_tick: int = -10_000
