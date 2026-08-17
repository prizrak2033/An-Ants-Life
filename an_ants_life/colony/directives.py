"""
Player directives: marks laid on the world that bias what the colony
does, without ever taking the wheel from an individual ant.

The game's behaviour comes from stigmergy - ants read the world, not
orders - so agency is expressed in the same language. A forage
directive does not command anybody; it lays scent, and the existing
recruitment loop does the rest. Defend and explore marks only move the
anchor an ant patrols or roams around. Nothing here sets an ant's
position or overrides its decisions.

Directives fade. They are pheromone, not policy, so holding a position
means re-committing to it rather than setting it once and forgetting.
That fade, plus a hard cap on how many can be active, is the whole cost
model - there is no resource price, because the interesting constraint
is attention, not food.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class DirectiveKind(Enum):
    FORAGE = "FORAGE"    # lay food scent here; workers recruit themselves
    DEFEND = "DEFEND"    # soldiers anchor their patrol here
    EXPLORE = "EXPLORE"  # scouts range around here


@dataclass
class Directive:
    id: int
    kind: DirectiveKind
    x: float
    y: float
    strength: float = 1.0
    created_t: float = 0.0
    # Live count of ants currently answering this mark, recomputed each
    # tick from the roster so deaths release their slot automatically.
    recruits: int = 0

    @property
    def spent(self) -> bool:
        return self.strength <= 0.0


class DirectiveBoard:
    def __init__(self, cfg):
        self.cfg = cfg
        self.items: List[Directive] = []
        self._next_id = 1

    def place(self, kind: DirectiveKind, x: float, y: float, t: float) -> Directive:
        """Add a mark, retiring the oldest of its kind if at the cap.

        The cap is per kind so committing to a defensive line cannot
        silently consume the player's ability to direct foraging.
        """
        same = [d for d in self.items if d.kind is kind]
        limit = self.cfg.DIRECTIVE_MAX_PER_KIND
        while len(same) >= limit:
            oldest = min(same, key=lambda d: d.created_t)
            self.items.remove(oldest)
            same.remove(oldest)

        d = Directive(self._next_id, kind, x, y, 1.0, t)
        self._next_id += 1
        self.items.append(d)
        return d

    def remove(self, directive_id: int) -> bool:
        for d in self.items:
            if d.id == directive_id:
                self.items.remove(d)
                return True
        return False

    def clear(self, kind: Optional[DirectiveKind] = None) -> int:
        before = len(self.items)
        if kind is None:
            self.items.clear()
        else:
            self.items = [d for d in self.items if d.kind is not kind]
        return before - len(self.items)

    def decay(self, dt: float) -> List[Directive]:
        """Fade every mark; return those that expired this tick."""
        rate = 1.0 / max(1e-6, self.cfg.DIRECTIVE_LIFETIME_SECONDS)
        expired = []
        for d in self.items:
            d.strength -= rate * dt
            if d.spent:
                expired.append(d)
        if expired:
            self.items = [d for d in self.items if not d.spent]
        return expired

    def nearest(self, kind: DirectiveKind, x: float, y: float,
                radius: float = 1e9) -> Optional[Directive]:
        best, best_sq = None, radius * radius
        for d in self.items:
            if d.kind is not kind:
                continue
            dx, dy = d.x - x, d.y - y
            dsq = dx * dx + dy * dy
            if dsq < best_sq:
                best_sq, best = dsq, d
        return best

    def of_kind(self, kind: DirectiveKind) -> List[Directive]:
        return [d for d in self.items if d.kind is kind]

    def by_id(self, directive_id: int) -> Optional[Directive]:
        for d in self.items:
            if d.id == directive_id:
                return d
        return None

    def try_recruit(self, ant, dt: float) -> Optional[Directive]:
        """Maybe sign this ant up to a nearby forage mark.

        This replaced a global scent broadcast, which is what made marks
        counterproductive: pheromone diffuses, so every worker on the map
        answered one mark at once and average round trips roughly doubled.
        Recruitment here is deliberately local and finite, the way it is
        in a real colony - a mark can only hold so many, only ants close
        enough hear about it, and nearer ones answer more readily.

        Amplification beyond the cap is left to the colony: recruits that
        actually find food lay a real trail home, and that trail recruits
        further on its own merits. A mark over an empty patch produces no
        trail and so quietly recruits nobody else.
        """
        cfg = self.cfg
        radius = cfg.DIRECTIVE_RECRUIT_RADIUS
        best, best_d = None, radius
        for d in self.items:
            if d.kind is not DirectiveKind.FORAGE:
                continue
            if d.recruits >= cfg.DIRECTIVE_RECRUIT_CAP:
                continue
            dist = math.hypot(d.x - ant.x, d.y - ant.y)
            if dist < best_d:
                best_d, best = dist, d
        if best is None:
            return None

        # Falls off with distance, so a mark pulls from its own
        # neighbourhood rather than dragging the far side of the map over.
        nearness = 1.0 - (best_d / radius)
        chance = cfg.DIRECTIVE_RECRUIT_CHANCE_PER_SEC * dt * nearness * best.strength
        if random.random() < chance:
            best.recruits += 1  # provisional; recomputed authoritatively each tick
            return best
        return None
