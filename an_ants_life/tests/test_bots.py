"""Guards on the two rules that make a bot result mean anything.

A scripted player is only evidence about human play if it is held to the
same limits a human is. These check both, because either one failing
would turn the whole experiment into a measurement of an oracle.
"""
from __future__ import annotations

import dataclasses
import random
import unittest

from tests.bots import (AttentiveBot, Bot, PassiveBot, View, observe,
                        run_with_bot, compare_bots)
from tests.harness import DT
from config import SimConfig
from state import GameState
from server import apply_player_action


def _state(seed=1, secs=60.0):
    random.seed(seed)
    st = GameState(SimConfig())
    for _ in range(int(secs / DT)):
        st.step(DT)
    return st


class TestBotsSeeOnlyWhatThePlayerSees(unittest.TestCase):
    def test_view_carries_no_simulation_internals(self):
        """No ant roster, no pheromone field, no hidden enemy state.

        The interface draws ants and trails, but it does not hand the
        player a queryable list of them, and nothing here should let a
        bot reason over one.
        """
        fields = {f.name for f in dataclasses.fields(View)}
        for leak in ("ants", "pheromones", "territory", "terrain",
                     "colony", "state", "history", "grid"):
            self.assertNotIn(leak, fields, f"View exposes {leak}")

    def test_view_only_reports_food_the_map_shows(self):
        st = _state()
        view = observe(st)
        self.assertTrue(all(amount > 0 for _, _, amount in view.food),
                        "exhausted piles are not drawn, so must not be seen")

    def test_view_matches_the_readouts_the_interface_prints(self):
        st = _state()
        view = observe(st)
        self.assertEqual(view.population, len(st.colony.ants))
        self.assertEqual(view.queen_hp, st.colony.queen.hp)
        self.assertAlmostEqual(view.food_store, st.colony.food_store, places=6)


class TestBotsActOnlyThroughThePlayerInterface(unittest.TestCase):
    def test_every_command_a_bot_issues_is_a_real_player_action(self):
        """Recorded, then replayed through the same entry point the HTTP
        handler uses. Anything it refuses was never a legal move."""
        random.seed(3)
        cfg = SimConfig()
        st = GameState(cfg)
        bot = AttentiveBot()
        bot.reset()
        issued = []

        def record(cmd):
            issued.append(cmd)
            return apply_player_action(st, cfg, cmd)

        next_t = 0.0
        for _ in range(int(240.0 / DT)):
            if st.t >= next_t:
                bot.act(observe(st), record)
                next_t = st.t + bot.decide_every
            st.step(DT)

        self.assertGreater(len(issued), 0, "attentive bot never did anything")
        fresh = GameState(SimConfig())
        for cmd in issued:
            self.assertTrue(apply_player_action(fresh, cfg, cmd),
                            f"bot issued something the interface rejects: {cmd}")

    def test_unknown_actions_are_refused(self):
        cfg = SimConfig()
        st = GameState(cfg)
        self.assertFalse(apply_player_action(st, cfg, {"action": "win"}))
        self.assertFalse(apply_player_action(st, cfg, {"action": "spawn_ants"}))


class TestArms(unittest.TestCase):
    def test_passive_arm_does_nothing_at_all(self):
        r = run_with_bot(1, 60.0, PassiveBot())
        self.assertEqual(r["actions"], 0)

    def test_attentive_arm_plays_at_a_human_cadence(self):
        r = run_with_bot(1, 120.0, AttentiveBot())
        self.assertGreater(r["actions"], 0)
        # An order every few seconds at most - not a machine spraying
        # commands, which would not be evidence about a person.
        self.assertLess(r["actions"], 120.0 / AttentiveBot.decide_every)

    def test_comparison_is_paired_and_reports_both_arms(self):
        cmp = compare_bots((1, 2), 45.0, PassiveBot(), AttentiveBot())
        self.assertEqual(cmp["n"], 2)
        self.assertEqual(cmp["label_a"], "passive")
        self.assertEqual(cmp["label_b"], "attentive")
        self.assertEqual(cmp["actions_a"], 0)
        self.assertIn("survival", cmp)

    def test_a_bot_run_is_reproducible(self):
        a = run_with_bot(5, 60.0, AttentiveBot())
        b = run_with_bot(5, 60.0, AttentiveBot())
        self.assertEqual(a["pop_end"], b["pop_end"])
        self.assertEqual(a["actions"], b["actions"])


if __name__ == "__main__":
    unittest.main()
