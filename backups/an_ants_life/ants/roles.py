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
