"""
Applies player directives to the world.

Forage marks used to deposit food scent directly. That was a broadcast,
not recruitment: pheromone diffuses, so a single mark pulled the entire
workforce onto one pile regardless of distance, roughly halving deposits
and measurably making played colonies worse than untouched ones.

Marks now recruit instead (see DirectiveBoard.try_recruit), and nothing
here writes to the pheromone grid at all. Amplification is left to the
colony: recruits that find food lay a genuine trail home, and that trail
draws others on its own merit, so a mark over a good patch grows into a
supply line while a mark over nothing quietly attracts no one.

This system's remaining job is bookkeeping - fading marks out, and
recounting who is answering each one.
"""
from __future__ import annotations

from colony.history import EventKind


def update_directives(state, dt: float) -> None:
    board = state.directives

    for d in board.decay(dt):
        state.history.emit(
            state.t, state.tick, EventKind.DIRECTIVE_EXPIRED,
            {"kind": d.kind.value, "x": round(d.x, 1), "y": round(d.y, 1)},
            cause="scent_faded", tags=["directive"]
        )

    if not board.items:
        return

    # Recount from the live roster so an ant that died, or picked up food
    # and dropped its errand, frees its slot without any explicit release.
    counts = {}
    for ant in state.colony.ants:
        rid = getattr(ant, "recruited_to", None)
        if rid is not None:
            counts[rid] = counts.get(rid, 0) + 1

    live_ids = set()
    for d in board.items:
        d.recruits = counts.get(d.id, 0)
        live_ids.add(d.id)

    # Release anyone still holding a mark that has since expired.
    for ant in state.colony.ants:
        if ant.recruited_to is not None and ant.recruited_to not in live_ids:
            ant.recruited_to = None
