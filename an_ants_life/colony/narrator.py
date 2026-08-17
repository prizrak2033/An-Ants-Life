"""
Turns log events into sentences.

The chronicle is meant to read as the colony's story, so events are
rendered as prose rather than as their raw kind and cause. Anything
without a phrasing here falls back to a cleaned-up version of the kind,
so a newly added event degrades to something readable instead of
vanishing or printing an identifier at the player.
"""
from __future__ import annotations
from typing import Callable, Dict, List

from colony.history import EventKind, HistoryEvent, Significance


def _amt(ev: HistoryEvent, key: str = "amt") -> str:
    v = ev.data.get(key, 0)
    return f"{v:.0f}" if isinstance(v, float) else str(v)


_KIND_ARTICLE = {"WARRIOR": "A warrior", "RAIDER": "A raider", "PREDATOR": "A predator"}


def _enemy_name(ev: HistoryEvent) -> str:
    return _KIND_ARTICLE.get(ev.data.get("kind", ""), "An intruder")


_PHRASINGS: Dict[str, Callable[[HistoryEvent], str]] = {
    EventKind.EMERGENCY_FAMINE_START:
        lambda e: "The stores ran dry. Famine takes hold.",
    EventKind.EMERGENCY_FAMINE_END:
        lambda e: "The famine breaks — the larders are filling again.",
    EventKind.EMERGENCY_FAMINE_REASSIGN:
        lambda e: f"{_amt(e, 'converted')} ants are pulled off their duties to forage.",
    EventKind.EMERGENCY_RAID:
        lambda e: f"A raid tears through the nest. {_amt(e, 'kills')} ants are lost.",

    EventKind.TERR_BORDER_INCIDENT:
        lambda e: "Fighting flares along the border.",
    EventKind.TERR_EXPANSION:
        lambda e: "The colony pushes its borders outward.",
    EventKind.TERR_REGIME_SHIFT:
        lambda e: "The balance of the frontier shifts.",

    EventKind.ENEMY_SPAWN:
        lambda e: f"{_enemy_name(e)} crosses onto colony ground.",
    EventKind.ENEMY_KILL:
        lambda e: f"{_enemy_name(e)} is cut down.",
    EventKind.ENEMY_DEATH:
        lambda e: "An ant falls in the fighting.",
    EventKind.ENEMY_STEAL:
        lambda e: (f"A raider breaks into the nest stores and seizes {_amt(e)} food."
                   if e.data.get("target") == "nest_stores"
                   else f"A raider plunders a food pile — {_amt(e)} food taken."),
    EventKind.ENEMY_ESCAPE:
        lambda e: f"The thief reaches the treeline. {_amt(e)} food is gone for good.",
    EventKind.ENEMY_LOOT_RECOVERED:
        lambda e: f"Soldiers run the thief down and recover {_amt(e)} food.",

    EventKind.QUEEN_HIT:
        lambda e: "The queen is struck in her own chamber.",
    EventKind.OBJ_CLAIMED:
        lambda e: "A food site is secured and claimed.",

    EventKind.PRAETORIAN_RAISED:
        lambda e: "A soldier who held the queen's chamber is raised to her guard.",
    EventKind.DIRECTIVE_PLACED:
        lambda e: {
            "FORAGE": "Scent is laid toward a new foraging ground.",
            "DEFEND": "The colony is set to hold a line.",
            "EXPLORE": "Scouts are sent to range over new ground.",
        }.get(e.data.get("kind", ""), "A directive is laid down."),
    EventKind.DIRECTIVE_EXPIRED:
        lambda e: "A directive fades from the ground.",
    EventKind.POLICY_CHANGED:
        lambda e: e.data.get("text", "The colony's priorities shift."),
    EventKind.RALLY_CALLED:
        lambda e: "Every ant is called back to the nest.",
    EventKind.RALLY_ENDED:
        lambda e: "The recall is lifted; the colony spreads out again.",

    EventKind.CHAPTER_START:
        lambda e: f"— {e.data.get('title', 'A new chapter')} begins —",
    EventKind.CHAPTER_END:
        lambda e: f"— {e.data.get('title', 'The chapter')} closes —",
    EventKind.MILESTONE:
        lambda e: e.data.get("text", "The colony reaches a milestone."),
    EventKind.ENDING:
        lambda e: e.data.get("text", "The colony's story ends."),
}


def narrate(ev: HistoryEvent) -> str:
    phrasing = _PHRASINGS.get(ev.kind)
    if phrasing is not None:
        return phrasing(ev)
    return ev.kind.replace("_", " ").capitalize() + "."


def chronicle_lines(history, n: int = 12) -> List[dict]:
    """The recent story as display-ready lines, newest last.

    Consecutive repeats of the same beat are folded into one line with a
    count. A steadily expanding colony emits the same border event every
    few seconds, and unfolded it crowded everything else out of the feed -
    the same way routine churn did before significance filtering.
    """
    # Over-fetch so a long run of repeats still leaves room for what
    # came before it once collapsed.
    raw = history.chronicle(n * 3)
    lines: List[dict] = []
    for ev in raw:
        text = narrate(ev)
        if lines and lines[-1]["kind"] == ev.kind and lines[-1]["text"] == text:
            lines[-1]["repeat"] += 1
            lines[-1]["t"] = ev.t
            continue
        lines.append({
            "kind": ev.kind,
            "t": ev.t,
            "text": text,
            "major": ev.significance >= Significance.MAJOR,
            "repeat": 1,
        })
    return lines[-n:]
