"""A save file is something another person can send you.

Saves are JSON and never `pickle`, so loading one cannot execute
anything — that is the property worth protecting and it is unchanged.
What these cover is the layer below it: a save whose *values* are wrong,
whether through corruption, a hand edit, or someone being funny.

Each case here crashed the game or silently cheated before ADR-0007.
"""
from __future__ import annotations

import copy
import random
import unittest

from tests.harness import DT
from config import SimConfig
from state import GameState
from persistence.codec import dump_state, load_state, CorruptSave


def _good_save():
    random.seed(11)
    return dump_state(GameState(SimConfig()))


def _tampered(**config_over):
    data = copy.deepcopy(_good_save())
    data["config"].update(config_over)
    return data


class TestATamperedSaveStillOpens(unittest.TestCase):
    """Rejected values fall back to defaults rather than failing the
    load. For a single-player game, opening is worth more than being
    strict."""

    def _loads_with(self, field, default_expected, **over):
        st = load_state(_tampered(**over))
        st.step(DT)
        self.assertEqual(getattr(st.cfg, field), default_expected)

    def test_a_zero_divisor_does_not_crash_the_load(self):
        self._loads_with("PHERO_GRID", SimConfig().PHERO_GRID, PHERO_GRID=0)

    def test_a_negative_dimension_is_refused(self):
        self._loads_with("WORLD_W", SimConfig().WORLD_W, WORLD_W=-120)

    def test_the_wrong_type_is_refused(self):
        self._loads_with("WORLD_W", SimConfig().WORLD_W, WORLD_W="abc")
        self._loads_with("ENEMY_ENABLE", SimConfig().ENEMY_ENABLE,
                         ENEMY_ENABLE="yes")

    def test_an_absurd_magnitude_is_refused(self):
        self._loads_with("ANT_SPEED", SimConfig().ANT_SPEED, ANT_SPEED=1e9)

    def test_nan_and_infinity_are_refused(self):
        self._loads_with("ANT_SPEED", SimConfig().ANT_SPEED, ANT_SPEED=float("nan"))
        self._loads_with("ANT_SPEED", SimConfig().ANT_SPEED, ANT_SPEED=float("inf"))

    def test_negative_upkeep_does_not_grant_infinite_food(self):
        """The one that was a silent cheat rather than a crash."""
        self._loads_with("FOOD_UPKEEP_PER_ANT_PER_SEC",
                         SimConfig().FOOD_UPKEEP_PER_ANT_PER_SEC,
                         FOOD_UPKEEP_PER_ANT_PER_SEC=-5.0)


class TestLegitimateSavesAreUntouched(unittest.TestCase):
    """Validation that rejects real saves would be worse than none."""

    def test_an_unmodified_save_round_trips(self):
        st = load_state(copy.deepcopy(_good_save()))
        st.step(DT)
        self.assertEqual(st.cfg, SimConfig())

    def test_zero_is_still_legal_where_it_means_off(self):
        """Several fields use 0 to disable a system. Blanket-rejecting
        non-positive values would break saves written with enemies off."""
        st = load_state(_tampered(ENEMY_BASE_SPAWN_CHANCE_PER_SEC=0.0))
        st.step(DT)
        self.assertEqual(st.cfg.ENEMY_BASE_SPAWN_CHANCE_PER_SEC, 0.0)

    def test_a_flag_a_player_legitimately_changed_survives(self):
        st = load_state(_tampered(ENEMY_ENABLE=False))
        self.assertFalse(st.cfg.ENEMY_ENABLE)


class TestAnInconsistentSaveSaysSo(unittest.TestCase):
    """Dimensions describe the grids stored beside them. When they
    disagreed, the error was an IndexError from deep inside terrain
    loading, naming nothing."""

    def test_a_world_size_that_contradicts_the_terrain_is_named(self):
        with self.assertRaises(CorruptSave) as caught:
            load_state(_tampered(WORLD_W=150))
        message = str(caught.exception)
        self.assertIn("terrain", message)
        self.assertIn("inconsistent", message)

    def test_a_scent_grid_of_the_wrong_size_is_named(self):
        data = copy.deepcopy(_good_save())
        data["pheromones"]["food"] = data["pheromones"]["food"][:-5]
        with self.assertRaises(CorruptSave) as caught:
            load_state(data)
        self.assertIn("inconsistent", str(caught.exception))


class TestTheFilesystemIsNotReachable(unittest.TestCase):
    """Save names come from the client. They become filenames."""

    def test_a_name_cannot_escape_the_save_directory(self):
        from persistence.store import SaveStore
        store = SaveStore()
        for hostile in ("../../etc/passwd", "/etc/passwd", "..\\..\\win.ini",
                        "a/b/c", "....//....//x"):
            path = store.save_path(hostile)
            self.assertEqual(path.parent.resolve(), store.dir.resolve(),
                             f"{hostile!r} escaped to {path}")

    def test_an_empty_or_hostile_name_still_produces_a_usable_file(self):
        from persistence.store import SaveStore
        store = SaveStore()
        for name in ("", "   ", "../..", "???"):
            self.assertTrue(store.save_path(name).name.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
