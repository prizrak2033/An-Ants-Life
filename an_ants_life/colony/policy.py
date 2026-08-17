"""
Colony policy: the standing orders the player sets, as opposed to the
directives they place on the map.

Defaults reproduce the tuned automatic behaviour exactly, so an
untouched game plays precisely as it did before agency existed. The
player takes over a caste target only by moving it, which is what
`auto_defense` tracks - otherwise the automatic threat response and a
deliberate player choice would quietly fight each other over the same
number.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ColonyPolicy:
    scout_target: float = 0.08
    soldier_target: float = 0.18
    # How many soldiers the colony is willing to lock down as permanent
    # guards. A count rather than a fraction: it is insurance against a
    # single event, not a standing share of the army.
    praetorian_target: int = 3
    # While true, the soldier target still rises with border pressure the
    # way it always has. Moving the soldier slider hands that over.
    auto_defense: bool = True
    # All ants fall back to the nest. Foraging stops, so this is a real
    # cost rather than a free panic button.
    rally: bool = False

    @classmethod
    def from_config(cls, cfg) -> "ColonyPolicy":
        return cls(
            scout_target=cfg.GROWTH_TARGET_SCOUT_FRAC,
            soldier_target=cfg.GROWTH_TARGET_SOLDIER_FRAC,
        )

    def set_praetorian_target(self, cfg, count: int) -> None:
        self.praetorian_target = int(_clamp(count, 0, cfg.PRAETORIAN_MAX))

    def set_targets(self, cfg, scout: float = None, soldier: float = None) -> None:
        if scout is not None:
            self.scout_target = _clamp(scout, 0.0, cfg.POLICY_MAX_SCOUT_FRAC)
        if soldier is not None:
            self.soldier_target = _clamp(soldier, 0.0, cfg.POLICY_MAX_SOLDIER_FRAC)
            # An explicit choice takes precedence over the auto response.
            self.auto_defense = False

    def effective_soldier_target(self, cfg, pressure: float) -> float:
        if not self.auto_defense:
            return self.soldier_target
        pressure = _clamp(pressure, 0.0, 1.0)
        return self.soldier_target + (
            cfg.GROWTH_THREAT_SOLDIER_FRAC - self.soldier_target) * pressure


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)
