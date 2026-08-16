"""
Food source entities scattered across the world for ants to forage.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class FoodSource:
    id: int
    x: float
    y: float
    amount: float
    claimed: bool = False
