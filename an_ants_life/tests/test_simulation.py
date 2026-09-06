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
from ants.ai import choose_intent


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


class TestNonCombatantsFlee(unittest.TestCase):
    """Workers and scouts run; soldiers and praetorians do not.

    Foragers had no awareness of enemies at all and were 62% of all
    casualties over long runs, in fights they cannot win - 4 HP and 1
    attack against a 5 HP raider or an 8 HP predator. Losing them is what
    the colony can least afford, because each replacement is an egg out
    of the same budget that feeds everybody.
    """

    def _state_with_threat(self, role, dist=3.0, **over):
        from enemies.enemy import make_enemy
        from enemies.kinds import EnemyKind
        from ants.ant import Ant
        random.seed(1)
        cfg = SimConfig(ENEMY_ENABLE=False, **over)
        st = GameState(cfg)
        ant = Ant(1, role, cfg.NEST_X + 25.0, cfg.NEST_Y, hp=cfg.ANT_HP_MAX)
        st.colony.ants = [ant]
        enemy = make_enemy(cfg, 1, EnemyKind.PREDATOR, ant.x + dist, ant.y)
        st.enemies = [enemy]
        return st, ant, enemy

    @staticmethod
    def _closes_on(intent, ant, enemy):
        """Does the chosen target take the ant toward the threat?"""
        now = math.hypot(ant.x - enemy.x, ant.y - enemy.y)
        tx, ty = intent.target
        return math.hypot(tx - enemy.x, ty - enemy.y) < now

    def test_worker_runs_from_a_predator(self):
        st, ant, enemy = self._state_with_threat(Role.WORKER)
        intent = choose_intent(st, ant)
        self.assertFalse(self._closes_on(intent, ant, enemy),
                         "worker walked toward the predator")

    def test_laden_worker_runs_rather_than_pressing_home(self):
        """The errand does not outrank survival: a laden worker that
        presses on loses itself and the food together."""
        st, ant, enemy = self._state_with_threat(Role.WORKER)
        ant.carrying = 1.0
        intent = choose_intent(st, ant)
        self.assertFalse(self._closes_on(intent, ant, enemy))
        self.assertEqual(intent.deposit_channel, "food",
                         "a fleeing laden ant should still mark its route")

    def test_scout_runs_too(self):
        st, ant, enemy = self._state_with_threat(Role.SCOUT)
        intent = choose_intent(st, ant)
        self.assertFalse(self._closes_on(intent, ant, enemy))

    def test_soldiers_still_engage(self):
        st, ant, enemy = self._state_with_threat(Role.SOLDIER)
        intent = choose_intent(st, ant)
        self.assertTrue(self._closes_on(intent, ant, enemy),
                        "soldier fled instead of engaging")

    def test_praetorian_still_engages_in_the_chamber(self):
        st, ant, enemy = self._state_with_threat(Role.PRAETORIAN)
        # Praetorians are leashed, so stage this inside the chamber.
        ant.x, ant.y = st.cfg.NEST_X + 2.0, st.cfg.NEST_Y
        enemy.x, enemy.y = ant.x + 3.0, ant.y
        intent = choose_intent(st, ant)
        self.assertTrue(self._closes_on(intent, ant, enemy),
                        "praetorian fled instead of holding the queen")

    def test_far_threats_are_ignored(self):
        st, ant, enemy = self._state_with_threat(Role.WORKER, dist=40.0)
        intent = choose_intent(st, ant)
        self.assertIsNotNone(intent.target)
        # Nothing nearby to run from, so it should be doing its job.
        self.assertGreater(math.hypot(intent.target[0] - enemy.x,
                                      intent.target[1] - enemy.y), 1.0)

    def test_a_cornered_ant_slides_instead_of_freezing(self):
        """Running straight away from a threat that has you against an
        edge clamps to where you already are. That reads as standing
        still and dying, so a cornered ant goes sideways instead."""
        st, ant, enemy = self._state_with_threat(Role.WORKER)
        ant.x, ant.y = 0.5, st.cfg.WORLD_H / 2      # hard against the left wall
        enemy.x, enemy.y = ant.x + 3.0, ant.y       # threat inward, escape blocked
        intent = choose_intent(st, ant)
        moved = math.hypot(intent.target[0] - ant.x, intent.target[1] - ant.y)
        self.assertGreater(moved, st.cfg.ANT_FLEE_STEP * 0.5,
                           "cornered ant froze in front of the threat")
        self.assertFalse(self._closes_on(intent, ant, enemy))

    def test_foragers_stand_their_ground_at_the_nest(self):
        """The exception that makes the mechanic work.

        Fleeing everywhere cut casualties 46% and still dropped survival
        from 6/6 to 4/6, because a worker's hopeless chip damage was
        holding the nest up: a warrior has 3 HP and a worker does 1, so
        three of them stop one before it reaches the queen. In the field
        that damage buys nothing; at home it buys the queen's life.
        """
        st, ant, enemy = self._state_with_threat(Role.WORKER)
        ant.x, ant.y = st.cfg.NEST_X + 4.0, st.cfg.NEST_Y
        enemy.x, enemy.y = ant.x + 3.0, ant.y
        from ants.ai import _flee_point
        self.assertIsNone(_flee_point(st, ant, st.cfg),
                          "forager fled from the queen's doorstep")

    def test_foragers_run_once_clear_of_the_nest(self):
        st, ant, enemy = self._state_with_threat(Role.WORKER)
        ant.x = st.cfg.NEST_X + st.cfg.ANT_FLEE_HOME_RADIUS + 8.0
        ant.y = st.cfg.NEST_Y
        enemy.x, enemy.y = ant.x + 3.0, ant.y
        from ants.ai import _flee_point
        self.assertIsNotNone(_flee_point(st, ant, st.cfg),
                             "forager stood and died in open ground")


class TestHarnessStatistics(unittest.TestCase):
    """The reporting has to be able to say "cannot tell".

    A balance decision was very nearly made on a median that moved from
    22 to 34 between two runs of an identical configuration. Medians
    alone cannot express that, so these check the tools that can.
    """

    def test_spread_reports_the_range_not_just_the_middle(self):
        from tests.harness import spread
        s = spread([1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(s["median"], 4.5)
        self.assertEqual((s["min"], s["max"]), (1, 8))
        self.assertLess(s["lo"], s["median"])
        self.assertGreater(s["hi"], s["median"])

    def test_interval_straddles_zero_when_there_is_no_effect(self):
        from tests.harness import bootstrap_ci
        lo, hi = bootstrap_ci([-1, 0, 1, -1, 0, 1, 0, 0, 1, -1])
        self.assertLessEqual(lo, 0.0)
        self.assertGreaterEqual(hi, 0.0)

    def test_interval_excludes_zero_for_a_real_shift(self):
        from tests.harness import bootstrap_ci
        lo, hi = bootstrap_ci([5, 6, 7, 5, 6, 7, 6, 6, 5, 7])
        self.assertGreater(lo, 0.0)

    def test_interval_is_reproducible(self):
        """Its own Random, seeded - so a reported interval can be checked
        later, and so resampling never disturbs the stream the simulation
        is seeded from."""
        from tests.harness import bootstrap_ci
        vals = [3, -1, 4, 1, -5, 9, 2, 6]
        self.assertEqual(bootstrap_ci(vals), bootstrap_ci(vals))
        random.seed(99)
        before = random.random()
        random.seed(99)
        bootstrap_ci(vals)
        self.assertEqual(before, random.random())

    def test_paired_survival_ignores_the_runs_that_agree(self):
        from tests.harness import mcnemar_p
        # Runs that live under both configs, or die under both, say
        # nothing about which config is better.
        self.assertEqual(mcnemar_p(0, 0), 1.0)
        # A single disagreement is not evidence.
        self.assertEqual(mcnemar_p(1, 0), 1.0)
        # A lopsided pile of them is.
        self.assertLess(mcnemar_p(8, 0), 0.05)
        # An even split is not, however many there are.
        self.assertEqual(mcnemar_p(6, 6), 1.0)

    def test_comparison_is_paired_on_seeds(self):
        """Both arms must see the same worlds; that is the whole point."""
        from tests.harness import compare
        cmp = compare((1, 2), 20.0, label_a="off", label_b="on",
                      arm_a={"ANT_FLEE_ENABLE": False}, arm_b={})
        self.assertEqual(cmp["n"], 2)
        self.assertIn("pop_end", cmp["metrics"])
        self.assertIn("distinguishable", cmp["survival"])
        for m in cmp["metrics"].values():
            lo, hi = m["ci"]
            self.assertLessEqual(lo, hi)
