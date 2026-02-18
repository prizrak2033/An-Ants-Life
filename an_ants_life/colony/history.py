from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    # Queen
    QUEEN_HIT = "queen_hit"

    # Objectives
    OBJ_CLAIMED = "objective_claimed"

    # Chapters
    CHAPTER_START = "chapter_start"
    CHAPTER_END = "chapter_end"

@dataclass
class HistoryEvent:
    t: float
    tick: int
    kind: str
    cause: Optional[str] = None
    impact: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def headline(self) -> str:
        c = f" cause={self.cause}" if self.cause else ""
        return f"{self.kind}{c}"

@dataclass
class HistoryLog:
    events: List[HistoryEvent] = field(default_factory=list)

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
    ):
        self.events.append(
            HistoryEvent(
                t=t, tick=tick, kind=kind,
                cause=cause, impact=impact or {},
                tags=tags or [], data=data or {}
            )
        )

    def recent(self, n: int = 8) -> List[HistoryEvent]:
        return self.events[-n:]

    def last(self) -> Optional[HistoryEvent]:
        return self.events[-1] if self.events else None

    def any_since(self, tick: int, kinds: List[str]) -> bool:
        ks = set(kinds)
        return any(e.tick >= tick and e.kind in ks for e in self.events)
