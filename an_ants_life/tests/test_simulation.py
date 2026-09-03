"""Core simulation invariants.

Each assertion here corresponds to a bug that actually happened. The
colony has twice shipped in a state where it gathered no food at all, and
once where two thirds of the ants were pinned against terrain while every
aggregate number still looked plausible - so the tests check the things
those failures would have broken, not merely that step() returns.
"""
from __future__ import annotations

import math
import random
import unittest

from tests.harness import DT, SLOW, aggregate, report, run
from config import SimConfig
from state import GameState
from ants.roles import Role


class TestForaging(unittest.TestCase):
    """The economy has to actually work; it has silently failed before."""

    def test_colony_gathers_food(self):
        r = run(1, 60.0)
        self.assertGreater(r["deposits"], 0, "colony gathered nothing in 60s")
        self.assertGreater(r["pickups"], 0, "no ant ever picked food up")

    def test_every_deposit_was_picked_up_first(self):
        # Scouts once collected food and never checked `carrying` on the
        # way home, so pickups climbed while deposits stayed at zero.
        r = run(2, 60.0)
        self.assertLessEqual(
            r["deposits"], r["pickups"],
            "more deposits than pickups - food is being created in transit")

    def test_laden_ants_lay_the_food_trail(self):
        # The stigmergy invariant. It was inverted once: searchers laid
        # `food` and laden ants laid `home`, which no one reads, and
        # foraging collapsed to a third of a random walk.
        random.seed(7)
        st = GameState(SimConfig())
        # Sample the peak rather than the end state. The world can run
        # out of food entirely, and a colony with nothing to carry lays
        # no trail - which is correct behaviour, not a broken invariant.
        peak = 0.0
        for _ in range(int(90.0 / DT)):
            st.step(DT)
            peak = max(peak, sum(sum(row) for row in st.pheromones.grids["food"]))
        self.assertGreater(
            peak, 1.0,
            "no `food` pheromone laid - laden ants are not marking their route")


class TestPhysicalIntegrity(unittest.TestCase):
    """Ants must stay real: on the map, finite, and able to move."""

    def setUp(self):
        random.seed(11)
        self.cfg = SimConfig()
        self.state = GameState(self.cfg)
        for _ in range(int(60.0 / DT)):
            self.state.step(DT)

    def test_ants_stay_inside_the_world(self):
        for a in self.state.colony.ants:
            self.assertTrue(0 <= a.x <= self.cfg.WORLD_W, f"ant {a.id} off map at x={a.x}")
            self.assertTrue(0 <= a.y <= self.cfg.WORLD_H, f"ant {a.id} off map at y={a.y}")

    def test_no_nan_positions(self):
        for a in self.state.colony.ants:
            self.assertFalse(math.isnan(a.x) or math.isnan(a.y), f"ant {a.id} has NaN position")

    def test_dead_ants_are_removed(self):
        for a in self.state.colony.ants:
            self.assertGreater(a.hp, 0, f"ant {a.id} survived the cull at {a.hp} hp")

    def test_population_respects_its_ceiling(self):
        self.assertLessEqual(len(self.state.colony.ants), self.cfg.GROWTH_MAX_POPULATION)

    def test_ants_are_not_jammed_against_terrain(self):
        """Rock was once impassable and pinned 69.6% of the colony.

        Every aggregate still looked fine, which is why this measures
        movement directly: sample positions a second apart and count how
        many ants covered almost no ground.
        """
        before = {a.id: (a.x, a.y) for a in self.state.colony.ants}
        for _ in range(int(1.0 / DT)):
            self.state.step(DT)
        moved, stuck = 0, 0
        for a in self.state.colony.ants:
            if a.id not in before:
                continue
            ox, oy = before[a.id]
            moved += 1
            if math.hypot(a.x - ox, a.y - oy) < 0.5:
                stuck += 1
        self.assertGreater(moved, 0, "no ants survived to measure")
        frac = stuck / moved
        self.assertLess(frac, 0.25, f"{frac:.0%} of ants barely moved in a second - terrain jam")


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_outcome(self):
        a = run(5, 45.0)
        b = run(5, 45.0)
        for key in ("deposits", "pop_end", "born", "lost", "queen_hp"):
            self.assertEqual(a[key], b[key], f"{key} differs between identical seeds")


class TestCastes(unittest.TestCase):
    def test_queen_replenishes_every_caste(self):
        """_pick_role seeks the configured mix rather than rolling fixed
        weights, so a caste drained to zero can refill."""
        random.seed(3)
        st = GameState(SimConfig())
        for _ in range(int(120.0 / DT)):
            st.step(DT)
        roles = {r: 0 for r in (Role.WORKER, Role.SCOUT, Role.SOLDIER)}
        for a in st.colony.ants:
            if a.role in roles:
                roles[a.role] += 1
        self.assertGreater(roles[Role.WORKER], 0, "no workers left")
        self.assertGreater(roles[Role.SOLDIER], 0, "no soldiers left")


class TestBalance(unittest.TestCase):
    """Balance is a range, not an equality - these are the guard rails."""

    def test_short_horizon_colony_survives(self):
        agg = aggregate((1, 2, 3), 120.0)
        self.assertEqual(agg["survived"], 3, "\n" + report("120s", agg))

    def test_food_income_beats_upkeep(self):
        agg = aggregate((1, 2, 3), 120.0)
        self.assertGreater(agg["ratio"], 1.0, "\n" + report("120s", agg))

    @unittest.skipUnless(SLOW, "slow tier; set ANTS_SLOW=1")
    def test_full_baseline_300s(self):
        agg = aggregate(tuple(range(1, 13)), 300.0)
        print("\n" + report("300s x12", agg))
        self.assertGreaterEqual(agg["survived"], 11, "\n" + report("300s x12", agg))
        self.assertGreater(agg["ratio"], 1.5)

    @unittest.skipUnless(SLOW, "slow tier; set ANTS_SLOW=1")
    def test_long_horizon_900s(self):
        """The known-bad case. Recorded, not asserted green: the colony
        hollows out by fifteen minutes and this is the number to move."""
        agg = aggregate(tuple(range(1, 13)), 900.0)
        print("\n" + report("900s x12", agg))
        self.assertGreater(agg["survived"], 0)


if __name__ == "__main__":
    unittest.main()


class TestFramerateIndependence(unittest.TestCase):
    """Rates must be expressed per second, not per tick.

    Timekeeper hands out a real elapsed dt clamped at MAX_DT, so a loaded
    machine runs the same simulated minute in fewer, longer steps. Any
    rate written per tick silently changes when that happens - it has
    already happened twice here, to food respawn and to enemy spawns, and
    in both cases the played game drifted away from the benchmarked one.
    """

    @staticmethod
    def _rates(dt: float, seeds, sim_seconds: float = 90.0):
        """Events per simulated second, averaged over seeds."""
        spawns, deposits = [], []
        for seed in seeds:
            random.seed(seed)
            st = GameState(SimConfig())
            seen = set()
            for _ in range(int(sim_seconds / dt)):
                st.step(dt)
                for e in st.enemies:
                    seen.add(e.id)
            spawns.append(len(seen) / st.t)
            deposits.append(st.colony.metrics["food_deposits"] / st.t)
        return (sum(spawns) / len(spawns), sum(deposits) / len(deposits))

    def test_enemy_pressure_does_not_track_framerate(self):
        seeds = (1, 2, 3, 4)
        fast_spawn, _ = self._rates(1.0 / 60, seeds)
        slow_spawn, _ = self._rates(1.0 / 15, seeds)
        # Four seeds of a stochastic process: check the rates are in the
        # same place, not that they are equal. A per-tick rate would put
        # these a factor of four apart.
        self.assertAlmostEqual(
            fast_spawn, slow_spawn, delta=0.4 * max(fast_spawn, slow_spawn),
            msg=f"enemy spawn rate tracks framerate: {fast_spawn:.3f}/s at 60fps "
                f"vs {slow_spawn:.3f}/s at 15fps")

    def test_food_economy_does_not_track_framerate(self):
        seeds = (1, 2, 3, 4)
        _, fast_dep = self._rates(1.0 / 60, seeds)
        _, slow_dep = self._rates(1.0 / 15, seeds)
        self.assertAlmostEqual(
            fast_dep, slow_dep, delta=0.4 * max(fast_dep, slow_dep),
            msg=f"food economy tracks framerate: {fast_dep:.3f}/s at 60fps "
                f"vs {slow_dep:.3f}/s at 15fps")

    def test_pheromone_retention_does_not_track_framerate(self):
        """The diffusion term was applied per tick while the decay beside
        it was per second, so scent evaporated faster on a fast machine."""
        from world.pheromones import PheromoneSystem
        cfg = SimConfig()
        kept = []
        for dt in (1.0 / 15, 1.0 / 30, 1.0 / 60):
            p = PheromoneSystem(cfg)
            p.deposit("food", (cfg.NEST_X, cfg.NEST_Y), 100.0)
            for _ in range(int(1.0 / dt)):
                p.decay_and_diffuse(dt)
            kept.append(sum(sum(c) for c in p.grids["food"]))
        spread = (max(kept) - min(kept)) / max(kept)
        self.assertLess(spread, 0.05,
                        f"1s pheromone retention varies with framerate: {kept}")

    def test_pheromone_decay_matches_its_configured_rate(self):
        """The configured decay rate must be the decay rate.

        A lossy diffusion term used to destroy the scent a cell shed
        toward empty neighbours, leaving a trail with 9.7% of its
        strength after a second where the config asked for ~58%.
        """
        from world.pheromones import PheromoneSystem
        cfg = SimConfig()
        p = PheromoneSystem(cfg)
        for i in range(20):
            p.deposit("food", (40.0 + i, 35.0), 5.0)
        start = sum(sum(c) for c in p.grids["food"])
        for _ in range(30):
            p.decay_and_diffuse(1.0 / 30)
        kept = sum(sum(c) for c in p.grids["food"]) / start
        expected = math.exp(-cfg.FOOD_PHERO_DECAY_PER_SEC)
        self.assertAlmostEqual(
            kept, expected, delta=0.08,
            msg=f"kept {kept:.1%} after 1s, configured rate implies {expected:.1%}")

    def test_territory_does_not_track_framerate(self):
        """TerritoryModel.update() once took no dt at all, so control,
        decay and the pressure signal driving enemy spawns all ran slow
        whenever the frame rate dipped toward MAX_DT."""
        from collections import defaultdict
        from world.territory import TerritoryModel
        from ants.ant import Ant

        class _Bag:
            pass

        def fake_state(cfg):
            st = _Bag()
            st.cfg, st.enemies, st.tick, st.t = cfg, [], 0, 0.0
            st.colony = _Bag()
            st.colony.ants = [Ant(i, Role.WORKER, 50.0 + i * 2, 35.0) for i in range(10)]
            st.colony.emergency, st.colony.metrics = {}, defaultdict(int)
            st.nest_pos = (cfg.NEST_X, cfg.NEST_Y)
            st.history = _Bag()
            st.history.emit = lambda *a, **k: None
            return st

        cfg = SimConfig(TERR_ENEMY_NOISE_PER_SEC=0.0)  # jitter would mask the signal
        totals = []
        for dt in (1.0 / 15, 1.0 / 30, 1.0 / 60, 1.0 / 120):
            random.seed(1)
            st, tm = fake_state(cfg), TerritoryModel(cfg)
            for _ in range(int(10.0 / dt)):
                tm.update(st, dt)
            totals.append(sum(sum(c) for c in tm.grid))
        spread = (max(totals) - min(totals)) / max(totals)
        self.assertLess(spread, 0.10,
                        f"territory control varies with framerate: {totals}")
