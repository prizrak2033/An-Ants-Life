"""The food-spending decision.

Works are the one thing a player can do that the colony cannot do for
itself. Three earlier experiments found that directing ants never beat
leaving them alone, because every tool the player had merely redirected
work the colony was already doing well. A work spends food on a
permanent change to the rules instead, so these tests check the two
things that makes or breaks: that the food actually leaves the store
exactly once, and that each work changes the term it claims to.
"""
from __future__ import annotations

import random
import unittest

from tests.harness import DT
from config import SimConfig
from state import GameState
from server import apply_player_action, work_cost, WORK_COSTS
from systems.growth import egg_cost


def _state(food: float = 200.0, **over):
    random.seed(4)
    cfg = SimConfig(**over)
    st = GameState(cfg)
    st.colony.food_store = food
    return st, cfg


class TestBuying(unittest.TestCase):
    def test_a_work_costs_exactly_its_price_once(self):
        st, cfg = _state(200.0)
        for work in WORK_COSTS:
            before = st.colony.food_store
            self.assertTrue(apply_player_action(st, cfg, {"action": "build", "work": work}))
            self.assertAlmostEqual(st.colony.food_store, before - work_cost(cfg, work))
            self.assertIn(work, st.colony.works)

    def test_building_twice_is_refused_and_costs_nothing(self):
        st, cfg = _state(200.0)
        apply_player_action(st, cfg, {"action": "build", "work": "nursery"})
        paid = st.colony.food_store
        self.assertFalse(apply_player_action(st, cfg, {"action": "build", "work": "nursery"}))
        self.assertEqual(st.colony.food_store, paid)
        self.assertEqual(st.colony.works.count("nursery"), 1)

    def test_what_cannot_be_afforded_is_refused_not_queued(self):
        """A pending build would quietly commit every future delivery."""
        st, cfg = _state(work_cost(SimConfig(), "garden") - 1.0)
        self.assertFalse(apply_player_action(st, cfg, {"action": "build", "work": "garden"}))
        self.assertEqual(st.colony.works, [])
        self.assertGreater(st.colony.food_store, 0.0)

    def test_a_work_that_does_not_exist_buys_nothing(self):
        st, cfg = _state(500.0)
        before = st.colony.food_store
        self.assertFalse(apply_player_action(st, cfg, {"action": "build", "work": "moat"}))
        self.assertEqual(st.colony.works, [])
        self.assertEqual(st.colony.food_store, before)

    def test_neither_work_is_affordable_at_the_opening_whistle(self):
        """The decision has to cost something to be a decision. The
        colony opens well short of even one, so a work is always a
        stretch of foraging the player chose to spend rather than a
        button that happens to be lit."""
        cfg = SimConfig()
        opening = GameState(cfg).colony.food_store
        self.assertLess(opening, min(work_cost(cfg, w) for w in WORK_COSTS))

    def test_the_build_flag_turns_the_whole_feature_off(self):
        st, cfg = _state(500.0, BUILD_ENABLE=False)
        self.assertFalse(apply_player_action(st, cfg, {"action": "build", "work": "nursery"}))
        self.assertEqual(st.colony.works, [])


class TestNursery(unittest.TestCase):
    def test_eggs_get_cheaper_by_the_configured_discount(self):
        st, cfg = _state(200.0)
        full = egg_cost(st)
        self.assertAlmostEqual(full, cfg.GROWTH_EGG_FOOD_COST)
        apply_player_action(st, cfg, {"action": "build", "work": "nursery"})
        self.assertAlmostEqual(egg_cost(st), full * (1.0 - cfg.BUILD_NURSERY_EGG_DISCOUNT))

    def test_a_birth_spends_the_discounted_price(self):
        from systems.growth import _update_births
        st, cfg = _state(400.0)
        apply_player_action(st, cfg, {"action": "build", "work": "nursery"})
        st.colony.emergency["food_reserve_target"] = 0.0
        st.colony.emergency["last_birth_tick"] = -10_000
        pop = len(st.colony.ants)
        before = st.colony.food_store
        _update_births(st)
        self.assertEqual(len(st.colony.ants), pop + 1)
        self.assertAlmostEqual(before - st.colony.food_store, egg_cost(st))

    def test_the_ceiling_readout_moves(self):
        """Cheaper replacements leave more regen for upkeep. If the HUD
        number does not move, the player is told the food bought nothing."""
        from systems.stress import update_stress
        st, cfg = _state(200.0)
        update_stress(st, DT)
        plain = st.colony.emergency["carrying_capacity"]
        apply_player_action(st, cfg, {"action": "build", "work": "nursery"})
        update_stress(st, DT)
        self.assertGreater(st.colony.emergency["carrying_capacity"], plain)


class TestGarden(unittest.TestCase):
    """The garden attacks the denominator of the size equation: what an
    ant costs to keep. Nothing else in the game touches that term."""

    def test_every_ant_eats_less(self):
        from systems.stress import upkeep_per_ant
        st, cfg = _state(200.0)
        full = upkeep_per_ant(st)
        self.assertAlmostEqual(full, cfg.FOOD_UPKEEP_PER_ANT_PER_SEC)
        apply_player_action(st, cfg, {"action": "build", "work": "garden"})
        self.assertAlmostEqual(upkeep_per_ant(st),
                               full * (1.0 - cfg.BUILD_GARDEN_UPKEEP_CUT))

    def test_the_store_actually_drains_slower(self):
        """The rate is only worth anything if it reaches the larder."""
        from systems.stress import update_stress

        def drained(build: bool) -> float:
            st, cfg = _state(200.0)
            if build:
                apply_player_action(st, cfg, {"action": "build", "work": "garden"})
            before = st.colony.food_store
            st.colony.metrics["food_deposits"] = 0  # no income to mask it
            for _ in range(int(10.0 / DT)):
                update_stress(st, DT)
            return before - st.colony.food_store

        plain, garden = drained(False), drained(True)
        self.assertLess(garden, plain)
        self.assertAlmostEqual(garden / plain, 1.0 - SimConfig().BUILD_GARDEN_UPKEEP_CUT,
                               places=2)

    def test_the_reserve_target_follows_the_discount(self):
        """Denominated in seconds of upkeep. Left on the old rate it would
        hold back a buffer the colony no longer needs and cancel part of
        what was just bought."""
        from systems.stress import update_stress
        st, cfg = _state(200.0)
        update_stress(st, DT)
        plain = st.colony.emergency["food_reserve_target"]
        apply_player_action(st, cfg, {"action": "build", "work": "garden"})
        update_stress(st, DT)
        self.assertLess(st.colony.emergency["food_reserve_target"], plain)

    def test_the_ceiling_moves_about_as_far_as_the_nursery_does(self):
        """Comparable size by a different route is what makes the two a
        choice rather than a ranking. Predicted from the model in config:
        36.7 plain, 46.9 nursery, 45.8 garden."""
        from systems.stress import update_stress

        def ceiling(work) -> float:
            st, cfg = _state(200.0)
            if work:
                apply_player_action(st, cfg, {"action": "build", "work": work})
            update_stress(st, DT)
            return st.colony.emergency["carrying_capacity"]

        plain, nursery, garden = ceiling(None), ceiling("nursery"), ceiling("garden")
        self.assertAlmostEqual(plain, 36.7, delta=0.5)
        self.assertAlmostEqual(nursery, 46.9, delta=0.5)
        self.assertAlmostEqual(garden, 45.8, delta=0.5)


class TestPersistence(unittest.TestCase):
    def test_works_survive_a_save(self):
        from persistence.codec import dump_state, load_state
        st, cfg = _state(200.0)
        apply_player_action(st, cfg, {"action": "build", "work": "nursery"})
        back = load_state(dump_state(st))
        self.assertEqual(back.colony.works, ["nursery"])
        self.assertAlmostEqual(egg_cost(back), egg_cost(st))


class TestSnapshot(unittest.TestCase):
    def test_the_player_can_see_what_is_built_and_what_things_cost(self):
        from server import _build_snapshot
        st, cfg = _state(200.0)
        apply_player_action(st, cfg, {"action": "build", "work": "garden"})
        works = _build_snapshot(st, paused=False)["works"]
        self.assertEqual(works["built"], ["garden"])
        self.assertEqual(set(works["costs"]), set(WORK_COSTS))
        self.assertAlmostEqual(works["costs"]["nursery"], cfg.BUILD_NURSERY_COST)


if __name__ == "__main__":
    unittest.main()
