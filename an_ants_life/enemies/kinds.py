"""
Enemy type definitions.

Each kind exists to threaten the colony along a different axis, so that
one defensive posture cannot answer all of them:

- WARRIOR  drives at the nest and the queen        (military)
- RAIDER   steals food and runs for the map edge   (economic)
- PREDATOR hunts foragers out in the field         (attrition)
"""
from enum import Enum


class EnemyKind(Enum):
    WARRIOR = "WARRIOR"
    RAIDER = "RAIDER"
    PREDATOR = "PREDATOR"
