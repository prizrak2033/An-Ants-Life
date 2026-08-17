"""
Colony names.

An archive of past colonies is only worth keeping if you can tell them
apart, and "colony #3" is not a thing anyone remembers. Names are drawn
from the kind of ground a nest sits on, so they read as places.
"""
from __future__ import annotations
import random

_FIRST = (
    "Amber", "Hollow", "Ember", "Bitter", "Quiet", "Long", "Red", "Deep",
    "Grey", "Thorn", "Pale", "Iron", "Salt", "Dust", "Low", "Far",
)
_SECOND = (
    "Reach", "Hollow", "Furrow", "Barrow", "Warren", "Verge", "Drift",
    "Rise", "Bank", "Mire", "Hearth", "Span", "Combe", "Fold",
)


def colony_name() -> str:
    return f"{random.choice(_FIRST)} {random.choice(_SECOND)}"
