"""Headless simulation runner.

The real game is driven by a Timekeeper against the wall clock. Every
measurement here bypasses it and steps a fixed dt instead, so a run is
deterministic given its seed and takes as long as the CPU needs rather
than as long as the colony lives.

This is the module every balance number in the README came from.
"""
from __future__ import annotations

import math
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
        "pop_end_spread": spread([r["pop_end"] for r in rows]),
        "pop_peak_median": statistics.median(r["pop_peak"] for r in rows),
        "born": sum(r["born"] for r in rows),
        "lost": sum(r["lost"] for r in rows),
        "intercepted": recovered / loot if loot else 0.0,
    }


def spread(values) -> dict:
    """Median plus the range the middle half of the runs fall in.

    A bare median hides how wide the outcomes are, and these outcomes are
    wide: a colony is a chaotic system, so two runs of the same config on
    the same seed diverge as soon as anything at all differs between
    them. Reporting only the middle of that made differences look far
    firmer than they were.
    """
    vals = sorted(values)
    n = len(vals)
    if not n:
        return {"median": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    return {
        "median": statistics.median(vals),
        "lo": vals[max(0, int(n * 0.25) - (1 if n % 4 == 0 else 0))],
        "hi": vals[min(n - 1, int(n * 0.75))],
        "min": vals[0],
        "max": vals[-1],
        "n": n,
    }


def bootstrap_ci(values, iters: int = 4000, alpha: float = 0.05) -> tuple:
    """Percentile bootstrap interval for the mean, standard library only.

    Assumption-free, which matters here: these distributions are skewed
    and small, and a normal approximation would promise precision the
    data does not have. Uses its own Random so it cannot disturb the
    global stream the simulation is seeded from.
    """
    vals = list(values)
    if len(vals) < 2:
        return (0.0, 0.0)
    rng = random.Random(20240906)
    n = len(vals)
    means = []
    for _ in range(iters):
        means.append(sum(rng.choice(vals) for _ in range(n)) / n)
    means.sort()
    return (means[int(iters * alpha / 2)], means[int(iters * (1 - alpha / 2)) - 1])


def mcnemar_p(only_a: int, only_b: int) -> float:
    """Two-sided exact p for a paired binary outcome.

    Survival is paired here - the same seed is run under both configs -
    so the runs that lived under both, or died under both, carry no
    information about which config is better. Only the disagreements do.
    """
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def compare(seeds, sim_seconds: float = 900.0, label_a: str = "A",
            label_b: str = "B", arm_a: dict = None, arm_b: dict = None) -> dict:
    """Run two configurations over the same seeds and say whether they differ.

    Paired on purpose. Comparing independent samples wastes most of the
    signal, because the seed decides the map, the food placement and the
    early enemy draw - differences between two configurations are far
    smaller than differences between two worlds. Pairing removes the
    world from the comparison.

    It does not remove everything: once the two arms behave differently
    they consume the random stream differently and their trajectories
    part company, so this measures a real effect plus trajectory noise,
    not a clean difference. That is why the intervals matter.
    """
    arm_a = arm_a or {}
    arm_b = arm_b or {}
    rows_a = [run(s, sim_seconds, **arm_a) for s in seeds]
    rows_b = [run(s, sim_seconds, **arm_b) for s in seeds]

    out = {"label_a": label_a, "label_b": label_b, "n": len(seeds),
           "sim_seconds": sim_seconds, "metrics": {}}

    for key in ("pop_end", "deposits_per_sec", "born", "lost"):
        deltas = [b[key] - a[key] for a, b in zip(rows_a, rows_b)]
        lo, hi = bootstrap_ci(deltas)
        out["metrics"][key] = {
            "a": spread([r[key] for r in rows_a]),
            "b": spread([r[key] for r in rows_b]),
            "mean_delta": statistics.mean(deltas),
            "ci": (lo, hi),
            # An interval straddling zero means this many runs cannot
            # tell the two apart - not that they are the same.
            "distinguishable": (lo > 0) or (hi < 0),
        }

    only_a = sum(1 for a, b in zip(rows_a, rows_b) if a["survived"] and not b["survived"])
    only_b = sum(1 for a, b in zip(rows_a, rows_b) if b["survived"] and not a["survived"])
    out["survival"] = {
        "a": sum(1 for r in rows_a if r["survived"]),
        "b": sum(1 for r in rows_b if r["survived"]),
        "only_a": only_a,
        "only_b": only_b,
        "p": mcnemar_p(only_a, only_b),
        "distinguishable": mcnemar_p(only_a, only_b) < 0.05,
    }
    return out


def compare_report(cmp: dict) -> str:
    a, b, n = cmp["label_a"], cmp["label_b"], cmp["n"]
    lines = [f"=== {a}  vs  {b}   ({n} paired seeds, {cmp['sim_seconds']:.0f}s) ==="]
    sv = cmp["survival"]
    verdict = "DIFFERENT" if sv["distinguishable"] else "not distinguishable"
    lines.append(f"  survived      {sv['a']}/{n} -> {sv['b']}/{n}   "
                 f"(disagreed on {sv['only_a'] + sv['only_b']} seeds: "
                 f"{sv['only_a']} only-{a}, {sv['only_b']} only-{b}; "
                 f"p={sv['p']:.3f}) {verdict}")
    for key, m in cmp["metrics"].items():
        lo, hi = m["ci"]
        verdict = "DIFFERENT" if m["distinguishable"] else "not distinguishable"
        lines.append(
            f"  {key:<17} {m['a']['median']:.2f} -> {m['b']['median']:.2f}   "
            f"delta {m['mean_delta']:+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  {verdict}")
    return "\n".join(lines)


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
        f"  pop end range {agg['pop_end_spread']['min']:.0f}-{agg['pop_end_spread']['max']:.0f} "
        f"(middle half {agg['pop_end_spread']['lo']:.0f}-{agg['pop_end_spread']['hi']:.0f})",
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
