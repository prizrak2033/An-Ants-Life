"""
Ant role definitions.

This module defines the different roles that ants can have in the colony:
WORKER, SCOUT, and SOLDIER, each with distinct behaviors.
"""

from enum import Enum

class Role(Enum):
    WORKER = "WORKER"
    SCOUT = "SCOUT"
    SOLDIER = "SOLDIER"
    # Never born, only promoted, and never leaves the queen. Exists
    # because every other role - and every player directive - points
    # outward, while every colony death happens at the nest.
    PRAETORIAN = "PRAETORIAN"
