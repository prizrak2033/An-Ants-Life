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
        st, cfg = _state(work_cost(SimConfig(), "rampart") - 1.0)
        self.assertFalse(apply_player_action(st, cfg, {"action": "build", "work": "rampart"}))
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


class TestRampart(unittest.TestCase):
    def _enemy_at(self, st, dist):
        from enemies.enemy import make_enemy
        from enemies.kinds import EnemyKind
        nx, ny = st.nest_pos
        e = make_enemy(st.cfg, 1, EnemyKind.WARRIOR, nx + dist, ny)
        st.enemies.append(e)
        return e

    def test_intruders_near_the_nest_are_slowed(self):
        from systems.enemies import _rampart_mult
        st, cfg = _state(200.0)
        nx, ny = st.nest_pos
        inside = (nx + cfg.BUILD_RAMPART_RADIUS * 0.5, ny)
        outside = (nx + cfg.BUILD_RAMPART_RADIUS * 2.0, ny)

        self.assertEqual(_rampart_mult(st, cfg, *inside), 1.0)
        apply_player_action(st, cfg, {"action": "build", "work": "rampart"})
        self.assertAlmostEqual(_rampart_mult(st, cfg, *inside), cfg.BUILD_RAMPART_SLOW)
        self.assertEqual(_rampart_mult(st, cfg, *outside), 1.0)

    def test_a_rampart_buys_the_garrison_time(self):
        """Measured on closing distance, not on outcomes: one raider on a
        straight run at the queen, with and without the earthworks."""
        def closed(build: bool) -> float:
            from systems.enemies import update_enemies
            # Enemies on so they move, but none arriving: the run has to
            # contain exactly the one intruder being measured.
            st, cfg = _state(200.0, ENEMY_BASE_SPAWN_CHANCE_PER_SEC=0.0,
                             ASSAULT_ENABLE=False)
            if build:
                apply_player_action(st, cfg, {"action": "build", "work": "rampart"})
            st.colony.ants.clear()  # nobody to fight it; measure travel alone
            e = self._enemy_at(st, cfg.BUILD_RAMPART_RADIUS * 0.75)
            nx, ny = st.nest_pos
            start = abs(e.x - nx)
            for _ in range(int(3.0 / DT)):
                update_enemies(st, DT)
            return start - abs(e.x - nx)

        self.assertLess(closed(True), closed(False))


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
        apply_player_action(st, cfg, {"action": "build", "work": "rampart"})
        works = _build_snapshot(st, paused=False)["works"]
        self.assertEqual(works["built"], ["rampart"])
        self.assertEqual(set(works["costs"]), set(WORK_COSTS))
        self.assertAlmostEqual(works["costs"]["nursery"], cfg.BUILD_NURSERY_COST)


if __name__ == "__main__":
    unittest.main()
