from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


class EventKind:
    # Foraging
    FORAGE_PICKUP = "forage_pickup"
    FORAGE_DEPOSIT = "forage_deposit"

    # Stress regimes
    STRESS_SPIKE = "stress_spike"
    STRESS_RECOVERY = "stress_recovery"

    # Famine / raids
    EMERGENCY_FAMINE_START = "emergency_famine_start"
    EMERGENCY_FAMINE_PRESSURE = "emergency_famine_pressure"
    EMERGENCY_FAMINE_REASSIGN = "emergency_famine_reassign"
    EMERGENCY_FAMINE_END = "emergency_famine_end"
    EMERGENCY_RAID = "emergency_raid"

    # Territory
    TERR_BORDER_INCIDENT = "territory_border_incident"
    TERR_EXPANSION = "territory_expansion"
    TERR_REGIME_SHIFT = "territory_regime_shift"

    # Enemies / combat
    ENEMY_SPAWN = "enemy_spawn"
    ENEMY_CONTACT = "enemy_contact"
    ENEMY_KILL = "enemy_kill"
    ENEMY_DEATH = "enemy_death"
    ENEMY_STEAL = "enemy_steal"
    ENEMY_ESCAPE = "enemy_escape"
    ENEMY_LOOT_RECOVERED = "enemy_loot_recovered"

    # Queen
    QUEEN_HIT = "queen_hit"

    # Objectives
    OBJ_CLAIMED = "objective_claimed"

    # Growth
    ANT_BORN = "ant_born"

    # Chapters / saga
    CHAPTER_START = "chapter_start"
    CHAPTER_END = "chapter_end"
    MILESTONE = "milestone"
    ENDING = "ending"


class Significance:
    """How much an event matters to the story being told.

    The log records everything, but the chronicle is a narrative, not a
    trace: measured over a 10-minute run, 82% of events were routine
    foraging and combat churn, so showing "the last N events" showed
    nothing but noise. Only NOTABLE and above reach the reader.
    """
    NOISE = 0    # routine churn - counted, never narrated
    MINOR = 1    # background colour
    NOTABLE = 2  # belongs in the chronicle
    MAJOR = 3    # a story beat; kept in the saga permanently


SIGNIFICANCE: Dict[str, int] = {
    EventKind.FORAGE_PICKUP: Significance.NOISE,
    EventKind.FORAGE_DEPOSIT: Significance.NOISE,
    EventKind.ENEMY_CONTACT: Significance.NOISE,
    EventKind.ANT_BORN: Significance.NOISE,
    EventKind.EMERGENCY_FAMINE_PRESSURE: Significance.NOISE,

    EventKind.ENEMY_SPAWN: Significance.MINOR,
    EventKind.ENEMY_KILL: Significance.MINOR,
    EventKind.ENEMY_DEATH: Significance.MINOR,
    EventKind.STRESS_SPIKE: Significance.MINOR,
    EventKind.STRESS_RECOVERY: Significance.MINOR,

    EventKind.TERR_EXPANSION: Significance.NOTABLE,
    EventKind.TERR_BORDER_INCIDENT: Significance.NOTABLE,
    EventKind.TERR_REGIME_SHIFT: Significance.NOTABLE,
    EventKind.OBJ_CLAIMED: Significance.NOTABLE,
    EventKind.ENEMY_STEAL: Significance.NOTABLE,
    EventKind.EMERGENCY_FAMINE_REASSIGN: Significance.NOTABLE,

    EventKind.EMERGENCY_FAMINE_START: Significance.MAJOR,
    EventKind.EMERGENCY_FAMINE_END: Significance.MAJOR,
    EventKind.EMERGENCY_RAID: Significance.MAJOR,
    EventKind.ENEMY_ESCAPE: Significance.MAJOR,
    EventKind.ENEMY_LOOT_RECOVERED: Significance.MAJOR,
    EventKind.QUEEN_HIT: Significance.MAJOR,
    EventKind.CHAPTER_START: Significance.MAJOR,
    EventKind.CHAPTER_END: Significance.MAJOR,
    EventKind.MILESTONE: Significance.MAJOR,
    EventKind.ENDING: Significance.MAJOR,
}


@dataclass
class HistoryEvent:
    t: float
    tick: int
    kind: str
    cause: Optional[str] = None
    impact: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def significance(self) -> int:
        return SIGNIFICANCE.get(self.kind, Significance.MINOR)


class HistoryLog:
    """Append-only event log with bounded memory and O(1) recency lookup.

    `any_since` used to scan every event ever recorded, and the chapter
    system calls it several times per tick against a log that grew without
    limit for the whole session. Keeping the newest tick per kind answers
    the same question in constant time and lets the raw log stay bounded.
    """

    def __init__(self, max_events: int = 600, max_notable: int = 240) -> None:
        self.events: Deque[HistoryEvent] = deque(maxlen=max_events)
        self.notable: Deque[HistoryEvent] = deque(maxlen=max_notable)
        self.saga: List[HistoryEvent] = []          # MAJOR beats, kept whole
        self.counts: Dict[str, int] = {}
        self._last_tick: Dict[str, int] = {}

    def emit(
        self,
        t: float,
        tick: int,
        kind: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        cause: Optional[str] = None,
        impact: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> HistoryEvent:
        ev = HistoryEvent(
            t=t, tick=tick, kind=kind,
            cause=cause, impact=impact or {},
            tags=tags or [], data=data or {}
        )
        self.events.append(ev)
        self.counts[kind] = self.counts.get(kind, 0) + 1
        self._last_tick[kind] = tick

        sig = ev.significance
        if sig >= Significance.NOTABLE:
            self.notable.append(ev)
        if sig >= Significance.MAJOR:
            self.saga.append(ev)
        return ev

    def recent(self, n: int = 8) -> List[HistoryEvent]:
        """Newest raw events, noise included. For debugging, not the UI."""
        if n <= 0:
            return []
        return list(self.events)[-n:]

    def chronicle(self, n: int = 10) -> List[HistoryEvent]:
        """Newest events worth telling the player about."""
        if n <= 0:
            return []
        return list(self.notable)[-n:]

    def last(self) -> Optional[HistoryEvent]:
        return self.events[-1] if self.events else None

    def count(self, kind: str) -> int:
        return self.counts.get(kind, 0)

    def last_tick_of(self, kind: str) -> int:
        return self._last_tick.get(kind, -10**9)

    def any_since(self, tick: int, kinds: List[str]) -> bool:
        return any(self._last_tick.get(k, -10**9) >= tick for k in kinds)
