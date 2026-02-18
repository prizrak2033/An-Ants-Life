"""
Intent dataclass for ant decision-making.

This module defines the Intent class which represents what an ant wants to do
in a given frame, including its movement target and pheromone deposit channel.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class Intent:
    target: Optional[Tuple[float, float]] = None
    deposit_channel: Optional[str] = None  # "food" | "home" | None
