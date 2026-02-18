from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from colony.history import EventKind

@dataclass
class ChapterState:
    active: bool = False
    title: str = "—"
    started_tick: int = -1
    last_signal_tick: int = -1

class MilestoneTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.chapter = ChapterState()
        self._last_chapter_change_tick = -10_000

    def update(self, state):
        cfg = self.cfg
        if not cfg.CHAPTER_ENABLE:
            return

        if (state.tick - self._last_chapter_change_tick) < cfg.CHAPTER_COOLDOWN_TICKS and not self.chapter.active:
            return

        window_start = max(0, state.tick - cfg.CHAPTER_WINDOW_TICKS)
        famine_active = state.colony.emergency.get("famine_active", False)
        pressure = state.colony.emergency.get("territory_pressure", 0.0)

        raids_recent = state.history.any_since(window_start, [EventKind.EMERGENCY_RAID, EventKind.ENEMY_KILL, EventKind.QUEEN_HIT])
        border_recent = state.history.any_since(window_start, [EventKind.TERR_BORDER_INCIDENT])
        claims_recent = state.history.any_since(window_start, [EventKind.OBJ_CLAIMED])

        title: Optional[str] = None
        if famine_active and pressure >= 0.65 and raids_recent:
            title = "Chapter: The Hungry Border Winter"
        elif pressure >= 0.78 and raids_recent:
            title = "Chapter: The Red Tide on the Frontier"
        elif pressure >= 0.70 and border_recent:
            title = "Chapter: Contested Lines"
        elif claims_recent and pressure <= 0.55 and not famine_active:
            title = "Chapter: The Claimed Harvest"
        elif pressure <= 0.40 and not famine_active:
            title = "Chapter: A Brief Calm"

        if title is not None:
            if not self.chapter.active:
                self.chapter.active = True
                self.chapter.title = title
                self.chapter.started_tick = state.tick
                self.chapter.last_signal_tick = state.tick
                self._last_chapter_change_tick = state.tick
                state.history.emit(
                    state.t, state.tick, EventKind.CHAPTER_START,
                    {"title": title, "pressure": round(pressure, 3)},
                    cause="pattern_match",
                    impact={"chapter": title},
                    tags=["chapter"]
                )
            else:
                self.chapter.last_signal_tick = state.tick
                self.chapter.title = title

        if self.chapter.active:
            stale = (state.tick - self.chapter.last_signal_tick) >= cfg.CHAPTER_END_GRACE_TICKS
            if stale:
                ended_title = self.chapter.title
                self.chapter = ChapterState()
                self._last_chapter_change_tick = state.tick
                state.history.emit(
                    state.t, state.tick, EventKind.CHAPTER_END,
                    {"title": ended_title},
                    cause="stability_return",
                    impact={"chapter": ended_title},
                    tags=["chapter", "recovery"]
                )
