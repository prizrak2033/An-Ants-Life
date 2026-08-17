"""
Applies player directives to the world.

Only FORAGE has a world effect of its own, and it is deliberately the
dumbest possible one: it lays food scent. Workers already climb that
gradient outward looking for a source, so recruitment to a marked spot
happens through the existing trail loop rather than through a special
case in ant AI. DEFEND and EXPLORE need no world effect at all - they
are read directly as patrol and roam anchors.
"""
from __future__ import annotations

import math

from colony.directives import DirectiveKind
from colony.history import EventKind

# Unit offsets at 45 degree steps, so the deposited patch reads as round.
_RING = tuple(
    (math.cos(a), math.sin(a))
    for a in (i * math.pi / 4 for i in range(8))
)


def update_directives(state, dt: float) -> None:
    cfg = state.cfg
    board = state.directives

    for d in board.decay(dt):
        state.history.emit(
            state.t, state.tick, EventKind.DIRECTIVE_EXPIRED,
            {"kind": d.kind.value, "x": round(d.x, 1), "y": round(d.y, 1)},
            cause="scent_faded", tags=["directive"]
        )

    if not board.items:
        return

    phero = state.pheromones
    amount = cfg.DIRECTIVE_FORAGE_DEPOSIT_PER_SEC * dt
    spread = cfg.DIRECTIVE_FORAGE_RADIUS

    for d in board.of_kind(DirectiveKind.FORAGE):
        # Fades with the mark, so a stale directive stops out-shouting
        # trails the colony found on its own.
        strength = amount * d.strength
        phero.deposit("food", (d.x, d.y), strength)
        # Spread over a ring rather than one cell, or passing ants miss it.
        # Diagonals are pulled in to sit on the same radius as the
        # cardinals - four cardinal offsets alone laid a visibly
        # cross-shaped plume on the map.
        for ox, oy in _RING:
            phero.deposit("food", (d.x + ox * spread, d.y + oy * spread), strength * 0.55)
