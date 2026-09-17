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

from ants.roles import Role
from colony.directives import DirectiveKind
from colony.history import EventKind


def update_directives(state, dt: float) -> None:
    board = state.directives

    for d in board.decay(dt):
        state.history.emit(
            state.t, state.tick, EventKind.DIRECTIVE_EXPIRED,
            {"kind": d.kind.value, "x": round(d.x, 1), "y": round(d.y, 1)},
            cause="scent_faded", tags=["directive"]
        )

    # Before the early return below. Alarm has nothing to do with the
    # directive board, and leaving it down there meant the guard only
    # answered calls while the player happened to have a mark placed -
    # which is to say, almost never.
    _assign_alarm_responders(state)

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

    _assign_defend_detachment(state)
    # Re-run now the detachment is known, so the two share one budget.
    _assign_alarm_responders(state)


def _assign_alarm_responders(state) -> None:
    """Decide which soldiers may answer a call for help.

    Shares one budget with the defend detachment rather than keeping its
    own. Two independent limits that each respect the floor can still
    breach it together - the detachment takes its share, alarm answers
    with what is left, and the nest keeps its guard either way. Leaving
    the nest undefended is exactly how the defend directive used to kill
    queens, which is what DIRECTIVE_DEFEND_MIN_GARRISON exists for.

    Praetorians are never eligible. Nothing moves them off the queen.
    """
    cfg = state.cfg
    if not cfg.ALARM_ENABLE:
        state.colony.emergency["alarm_responders"] = frozenset()
        state.colony.emergency["alarm_calls"] = ()
        return

    # One sweep of the grid for the whole colony. Alarm is sparse, so
    # this is a short list; a radius search per soldier would re-read the
    # same few hundred cells a dozen times a frame for the same answers.
    state.colony.emergency["alarm_calls"] = tuple(
        state.pheromones.hotspots("alarm", cfg.ALARM_MIN_LEVEL))

    soldiers = sorted((a for a in state.colony.ants if a.role is Role.SOLDIER),
                      key=lambda a: a.id)
    detached = state.colony.emergency.get("defend_detachment", frozenset())
    free = [a for a in soldiers if a.id not in detached]
    # The floor counts every soldier already away, however it left.
    spare = len(soldiers) - len(detached) - cfg.DIRECTIVE_DEFEND_MIN_GARRISON
    state.colony.emergency["alarm_responders"] = (
        frozenset(a.id for a in free[-spare:]) if spare > 0 else frozenset()
    )


def _assign_defend_detachment(state) -> None:
    """Decide which soldiers may leave for a defend mark.

    Chosen here, once per tick, rather than per ant in the AI, because
    the limit is about the group: a share of the guard *and* never
    dropping the nest below an absolute floor. Selection is by sorted id
    so membership is stable - a soldier that oscillates between post and
    nest guards neither.
    """
    cfg = state.cfg
    if not state.directives.of_kind(DirectiveKind.DEFEND):
        state.colony.emergency["defend_detachment"] = frozenset()
        return

    soldiers = sorted((a for a in state.colony.ants if a.role is Role.SOLDIER),
                      key=lambda a: a.id)
    spare = len(soldiers) - cfg.DIRECTIVE_DEFEND_MIN_GARRISON
    allowed = min(spare, int(len(soldiers) * cfg.DIRECTIVE_DEFEND_MAX_SHARE))
    state.colony.emergency["defend_detachment"] = (
        frozenset(a.id for a in soldiers[-allowed:]) if allowed > 0 else frozenset()
    )
