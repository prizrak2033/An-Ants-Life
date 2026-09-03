"""Headless simulation runner.

The real game is driven by a Timekeeper against the wall clock. Every
measurement here bypasses it and steps a fixed dt instead, so a run is
deterministic given its seed and takes as long as the CPU needs rather
than as long as the colony lives.

This is the module every balance number in the README came from.
"""
from __future__ import annotations

import os
import random
import statistics
import sys

# Modules are imported as top-level names (`from config import ...`), so
# the package directory - not this one - has to be on the path. Derived
# from __file__ so the suite runs from any working directory.
_PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from config import SimConfig          # noqa: E402
from state import GameState           # noqa: E402
from enemies.kinds import EnemyKind    # noqa: E402

DT = 1.0 / 30.0

# The slow tier runs full-length colonies across many seeds and takes
# minutes. Off unless asked for, so the default suite stays usable.
SLOW = os.environ.get("ANTS_SLOW") == "1"


def run(seed: int, sim_seconds: float = 300.0, **cfg_over) -> dict:
    """One colony, start to finish or to the horizon, whichever comes first."""
    random.seed(seed)
    cfg = SimConfig(**cfg_over)
    state = GameState(cfg)

    ticks = int(sim_seconds / DT)
    first_deposit_t = None
    upkeep_total = 0.0
    famine_ticks = 0
    pop_samples = []

    for _ in range(ticks):
        pop_before = len(state.colony.ants)
        state.step(DT)
        upkeep_total += pop_before * cfg.FOOD_UPKEEP_PER_ANT_PER_SEC * DT
        if first_deposit_t is None and state.colony.metrics["food_deposits"] > 0:
            first_deposit_t = state.t
        if state.colony.emergency.get("famine_active"):
            famine_ticks += 1
        pop_samples.append(len(state.colony.ants))
        if state.colony.queen.hp <= 0:
            break

    m = state.colony.metrics
    return {
        "t": state.t,
        "survived": state.colony.queen.hp > 0 and state.t >= sim_seconds - 1.0,
        "deposits": m["food_deposits"],
        "pickups": m["food_pickups"],
        "deposits_per_sec": m["food_deposits"] / max(state.t, 1e-9),
        "upkeep_per_sec": upkeep_total / max(state.t, 1e-9),
        "first_deposit_t": first_deposit_t,
        "famine_frac": famine_ticks / max(len(pop_samples), 1),
        "pop_start": pop_samples[0] if pop_samples else 0,
        "pop_end": pop_samples[-1] if pop_samples else 0,
        "pop_min": min(pop_samples) if pop_samples else 0,
        "pop_peak": max(pop_samples) if pop_samples else 0,
        "food_end": state.colony.food_store,
        "born": m["ants_born"],
        "lost": m["ants_killed"],
        "queen_hp": state.colony.queen.hp,
        "stolen": m["food_stolen"],
        "recovered": m["loot_recovered"],
        "kills": m["enemy_kills"],
    }


def aggregate(seeds, sim_seconds: float = 300.0, **cfg_over) -> dict:
    """Run a set of seeds and reduce them to the figures worth comparing."""
    rows = [run(s, sim_seconds, **cfg_over) for s in seeds]
    dps = statistics.mean(r["deposits_per_sec"] for r in rows)
    ups = statistics.mean(r["upkeep_per_sec"] for r in rows)
    stolen = sum(r["stolen"] for r in rows)
    recovered = sum(r["recovered"] for r in rows)
    loot = stolen + recovered
    return {
        "rows": rows,
        "n": len(rows),
        "survived": sum(1 for r in rows if r["survived"]),
        "died_at": sorted(round(r["t"]) for r in rows if not r["survived"]),
        "deposits_per_sec": dps,
        "ratio": dps / ups if ups else 0.0,
        "famine_frac": statistics.mean(r["famine_frac"] for r in rows),
        "pop_end_median": statistics.median(r["pop_end"] for r in rows),
        "pop_peak_median": statistics.median(r["pop_peak"] for r in rows),
        "born": sum(r["born"] for r in rows),
        "lost": sum(r["lost"] for r in rows),
        "intercepted": recovered / loot if loot else 0.0,
    }


def report(label: str, agg: dict) -> str:
    """One block of human-readable numbers, the shape used throughout."""
    return "\n".join([
        f"=== {label} ===",
        f"  survived      {agg['survived']}/{agg['n']}",
        f"  died at       {agg['died_at']}",
        f"  deposits/sec  {agg['deposits_per_sec']:.3f}",
        f"  ratio         {agg['ratio']:.2f}x",
        f"  famine        {agg['famine_frac'] * 100:.1f}%",
        f"  pop peak/end  {agg['pop_peak_median']:.0f} -> {agg['pop_end_median']:.0f} (median)",
        f"  born/lost     {agg['born']} / {agg['lost']}",
        f"  intercepted   {agg['intercepted'] * 100:.0f}%",
    ])


def enemy_census(seed: int, sim_seconds: float = 300.0, **cfg_over) -> dict:
    """Per-kind spawn accounting, for tuning enemy pressure."""
    random.seed(seed)
    cfg = SimConfig(**cfg_over)
    st = GameState(cfg)
    spawned = {k: 0 for k in EnemyKind}
    seen = set()
    for _ in range(int(sim_seconds / DT)):
        st.step(DT)
        for e in st.enemies:
            if e.id not in seen:
                seen.add(e.id)
                spawned[e.kind] += 1
        if st.colony.queen.hp <= 0:
            break
    m = st.colony.metrics
    return {
        "t": st.t,
        "spawned": {k.value: v for k, v in spawned.items()},
        "stolen": round(m["food_stolen"], 1),
        "recovered": round(m["loot_recovered"], 1),
        "kills": m["enemy_kills"],
        "lost": m["ants_killed"],
        "pop": len(st.colony.ants),
        "queen": st.colony.queen.hp,
    }
