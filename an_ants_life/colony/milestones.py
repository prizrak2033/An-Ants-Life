"""
The colony's story: chapters, milestones and endings.

Chapters are pattern matches over recent history rather than scripted
events, so the name a stretch of play gets is earned by what actually
happened. Each definition scores itself against the current signals and
the best-fitting one wins - the old flat if/elif chain made priority an
accident of source order, and adding a chapter meant working out where
in the ladder it had to sit to not be shadowed.

Milestones are one-shot: the first harvest, the first thief run down.
They never repeat, and together with the chapters they make up the saga
the colony leaves behind.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, List, Optional, Tuple

from colony.history import EventKind
from enemies.kinds import EnemyKind


@dataclass
class Signals:
    """Everything the chapter tests read, gathered once per update."""
    tick: int = 0
    t: float = 0.0
    famine: bool = False
    hunger: float = 0.0
    pressure: float = 0.0
    stress: float = 0.0
    population: int = 0
    pop_trend: float = 0.0       # fractional change across the window
    queen_frac: float = 1.0
    high_pressure_frac: float = 0.0  # share of the window spent under pressure

    raids: bool = False
    border: bool = False
    claims: bool = False
    theft: bool = False
    recovered: bool = False
    queen_hit: bool = False
    predator: bool = False
    expansion: bool = False


@dataclass(frozen=True)
class ChapterDef:
    title: str
    score: Callable[[Signals], float]


def _defs() -> Tuple[ChapterDef, ...]:
    """Scores are specificity: a chapter demanding more conditions
    outranks a vaguer one describing the same moment."""
    return (
        ChapterDef("The Queen's Peril",
                   lambda s: 5.0 if (s.queen_frac <= 0.55 and s.queen_hit) else 0.0),
        ChapterDef("The Hungry Border Winter",
                   lambda s: 4.2 if (s.famine and s.pressure >= 0.6 and s.raids) else 0.0),
        ChapterDef("The Season of Thieves",
                   lambda s: 4.0 if (s.famine and s.theft) else 0.0),
        ChapterDef("The Red Tide on the Frontier",
                   lambda s: 3.6 if (s.pressure >= 0.75 and s.raids) else 0.0),
        ChapterDef("The Long Siege",
                   lambda s: 3.5 if (s.high_pressure_frac >= 0.6 and s.raids) else 0.0),
        ChapterDef("The Predator's Shadow",
                   lambda s: 3.2 if (s.predator and s.pop_trend <= -0.08) else 0.0),
        ChapterDef("What Was Taken Back",
                   lambda s: 3.0 if (s.recovered and not s.famine) else 0.0),
        ChapterDef("The Thinning",
                   lambda s: 2.8 if (s.pop_trend <= -0.25) else 0.0),
        ChapterDef("Contested Lines",
                   lambda s: 2.6 if (s.pressure >= 0.65 and s.border) else 0.0),
        ChapterDef("The Lean Season",
                   lambda s: 2.5 if (s.famine and not s.raids) else 0.0),
        ChapterDef("The Swelling Brood",
                   lambda s: 2.4 if (s.pop_trend >= 0.30 and s.expansion) else 0.0),
        ChapterDef("The Claimed Harvest",
                   lambda s: 2.0 if (s.claims and s.pressure <= 0.5 and not s.famine) else 0.0),
        ChapterDef("A Brief Calm",
                   lambda s: 1.0 if (s.pressure <= 0.40 and not s.famine) else 0.0),
    )


# key, title, prose, test
_MILESTONES: Tuple[Tuple[str, str, str, Callable[[Signals, object], bool]], ...] = (
    ("first_harvest", "The First Harvest",
     "The first forager returns laden. The colony can feed itself.",
     lambda s, st: st.colony.metrics["food_deposits"] >= 1),
    ("first_blood", "First Blood",
     "The colony kills its first intruder.",
     lambda s, st: st.colony.metrics["enemy_kills"] >= 1),
    ("first_claim", "Ground Held",
     "A food site is claimed and held against the frontier.",
     lambda s, st: st.colony.metrics["claims"] >= 1),
    ("thief_caught", "Justice on the Frontier",
     "Soldiers run down a thief and take back what was stolen.",
     lambda s, st: st.colony.metrics["loot_recovered"] > 0),
    ("brood_fifty", "Fifty Strong",
     "Fifty ants now answer to the queen.",
     lambda s, st: s.population >= 50),
    ("famine_survived", "Through the Lean Time",
     "The colony comes out the far side of its first famine.",
     lambda s, st: st.history.count(EventKind.EMERGENCY_FAMINE_END) >= 1),
    ("endure_five", "Five Minutes Standing",
     "Five minutes on, the nest still holds.",
     lambda s, st: s.t >= 300.0),
    ("endure_fifteen", "The Colony Comes of Age",
     "Fifteen minutes on, the colony is an established power.",
     lambda s, st: s.t >= 900.0),
)


@dataclass
class ChapterState:
    active: bool = False
    title: str = "—"
    score: float = 0.0
    started_t: float = 0.0
    last_signal_t: float = -1.0


@dataclass
class ChapterRecord:
    title: str
    started_t: float
    ended_t: float

    @property
    def duration(self) -> float:
        return max(0.0, self.ended_t - self.started_t)


class MilestoneTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.chapter = ChapterState()
        self.past_chapters: List[ChapterRecord] = []
        self.milestones: List[Dict] = []
        self._earned: set = set()
        self._last_chapter_change_t = -1e18
        self._last_predator_t = -1e18
        self._last_sample_t = -1e18
        # Sampled once a second; cheap, and enough to see a trend.
        self._pop_samples: Deque[Tuple[int, int]] = deque(maxlen=180)
        self._pressure_samples: Deque[float] = deque(maxlen=180)
        self._defs = _defs()

    # ---------- signals ----------

    def _sample(self, state) -> None:
        # Read predator presence off the live roster rather than rescanning
        # the event log for spawn records every tick.
        if any(e.kind is EnemyKind.PREDATOR for e in state.enemies):
            self._last_predator_t = state.t

        # Once a simulated second, not every 30 ticks - the same thing
        # at 30fps, and a different thing at any other frame rate.
        if state.t - self._last_sample_t < 1.0:
            return
        self._last_sample_t = state.t
        self._pop_samples.append((state.t, len(state.colony.ants)))
        self._pressure_samples.append(
            state.colony.emergency.get("territory_pressure", 0.0))

    def _gather(self, state) -> Signals:
        cfg = self.cfg
        colony = state.colony
        window = max(0.0, state.t - cfg.CHAPTER_WINDOW_SECONDS)
        hist = state.history

        pop = len(colony.ants)
        trend = 0.0
        if self._pop_samples:
            oldest_t, oldest_pop = self._pop_samples[0]
            if oldest_pop > 0 and (state.t - oldest_t) > 0:
                trend = (pop - oldest_pop) / oldest_pop

        high = 0.0
        if self._pressure_samples:
            high = sum(1 for p in self._pressure_samples if p >= 0.6) / len(self._pressure_samples)

        queen = colony.queen
        return Signals(
            tick=state.tick, t=state.t,
            famine=bool(colony.emergency.get("famine_active", False)),
            hunger=colony.emergency.get("hunger", 0.0),
            pressure=colony.emergency.get("territory_pressure", 0.0),
            stress=colony.stress,
            population=pop,
            pop_trend=trend,
            queen_frac=(queen.hp / queen.hp_max) if queen.hp_max else 0.0,
            high_pressure_frac=high,
            raids=hist.any_since(window, [EventKind.EMERGENCY_RAID, EventKind.QUEEN_HIT,
                                          EventKind.ENEMY_KILL]),
            border=hist.any_since(window, [EventKind.TERR_BORDER_INCIDENT]),
            claims=hist.any_since(window, [EventKind.OBJ_CLAIMED]),
            theft=hist.any_since(window, [EventKind.ENEMY_ESCAPE, EventKind.ENEMY_STEAL]),
            recovered=hist.any_since(window, [EventKind.ENEMY_LOOT_RECOVERED]),
            queen_hit=hist.any_since(window, [EventKind.QUEEN_HIT]),
            predator=(state.t - self._last_predator_t) <= cfg.CHAPTER_WINDOW_SECONDS,
            expansion=hist.any_since(window, [EventKind.TERR_EXPANSION]),
        )

    # ---------- update ----------

    def update(self, state) -> None:
        cfg = self.cfg
        self._sample(state)
        sig = self._gather(state)

        self._check_endings(state, sig)
        self._check_milestones(state, sig)

        if not cfg.CHAPTER_ENABLE or state.ending is not None:
            return

        best_title, best_score = None, 0.0
        for d in self._defs:
            s = d.score(sig)
            if s > best_score:
                best_title, best_score = d.title, s

        cooling = (state.t - self._last_chapter_change_t) < cfg.CHAPTER_COOLDOWN_SECONDS
        if best_title is not None:
            if not self.chapter.active:
                if not cooling:
                    self._open(state, best_title, sig, best_score)
            elif best_title == self.chapter.title:
                self.chapter.last_signal_t = state.t
                self.chapter.score = best_score
            else:
                # A better-fitting chapter can take over, but only once the
                # current one has actually had a run and only if it fits
                # clearly better - otherwise the saga becomes a list of
                # titles that each lasted a second or two.
                settled = (state.t - self.chapter.started_t) >= cfg.CHAPTER_MIN_SECONDS
                clearly_better = best_score >= self.chapter.score + cfg.CHAPTER_SUPERSEDE_MARGIN
                if settled and clearly_better:
                    # Closing the old one explicitly keeps the saga honest;
                    # it used to silently rename itself, losing the beat.
                    self._close(state, "superseded")
                    self._open(state, best_title, sig, best_score)
                else:
                    self.chapter.last_signal_t = state.t

        if self.chapter.active:
            stale = (state.t - self.chapter.last_signal_t) >= cfg.CHAPTER_END_GRACE_SECONDS
            if stale:
                self._close(state, "stability_return")

    def _open(self, state, title: str, sig: Signals, score: float = 0.0) -> None:
        self.chapter = ChapterState(
            active=True, title=title, score=score,
            started_t=state.t, last_signal_t=state.t,
        )
        self._last_chapter_change_t = state.t
        state.history.emit(
            state.t, state.tick, EventKind.CHAPTER_START,
            {"title": title, "pressure": round(sig.pressure, 3)},
            cause="pattern_match", impact={"chapter": title}, tags=["chapter"]
        )

    def _close(self, state, cause: str) -> None:
        ch = self.chapter
        self.past_chapters.append(
            ChapterRecord(title=ch.title, started_t=ch.started_t, ended_t=state.t))
        self.chapter = ChapterState()
        self._last_chapter_change_t = state.t
        state.history.emit(
            state.t, state.tick, EventKind.CHAPTER_END,
            {"title": ch.title, "duration": round(state.t - ch.started_t, 1)},
            cause=cause, impact={"chapter": ch.title}, tags=["chapter"]
        )

    def _check_milestones(self, state, sig: Signals) -> None:
        for key, title, text, test in _MILESTONES:
            if key in self._earned:
                continue
            try:
                hit = test(sig, state)
            except (KeyError, AttributeError):
                continue
            if not hit:
                continue
            self._earned.add(key)
            self.milestones.append({"key": key, "title": title, "text": text, "t": state.t})
            state.history.emit(
                state.t, state.tick, EventKind.MILESTONE,
                {"key": key, "title": title, "text": f"{title} — {text}"},
                cause="milestone", tags=["milestone"]
            )

    def _check_endings(self, state, sig: Signals) -> None:
        if state.ending is not None:
            return

        if state.colony.queen.hp <= 0:
            ending, text = "queen_lost", (
                "The queen is dead. Whatever the colony was, it ends here.")
        elif sig.population <= 0:
            # The queen cannot forage; an empty nest is already over, and
            # without this the sim would idle on a colony of nobody.
            ending, text = "colony_extinct", (
                "The last ant falls. The queen sits alone in a silent nest.")
        else:
            return

        state.ending = ending
        state.history.emit(
            state.t, state.tick, EventKind.ENDING,
            {"ending": ending, "text": text},
            cause=ending, tags=["ending"]
        )
        if self.chapter.active:
            self._close(state, ending)
