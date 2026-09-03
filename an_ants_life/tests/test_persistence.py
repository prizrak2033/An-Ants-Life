"""Round-trip fidelity: a resumed colony must continue identically.

Saving is easy to get *nearly* right, and the failure mode is a save that
loads without complaint and then diverges - which you notice long after
it matters. So this saves mid-run, continues the original, separately
resumes the copy, and requires the two futures to match tick for tick.
"""
from __future__ import annotations

import json
import random
import unittest

from tests.harness import DT
from config import SimConfig
from state import GameState
from persistence.codec import dump_state, load_state


def fingerprint(st) -> dict:
    """Everything that would reveal a divergence."""
    return {
        "tick": st.tick,
        "t": round(st.t, 6),
        "ending": st.ending,
        "ants": sorted((a.id, round(a.x, 6), round(a.y, 6), a.hp, a.role.value,
                        round(a.carrying, 6), a.recruited_to) for a in st.colony.ants),
        "enemies": sorted((e.id, round(e.x, 6), round(e.y, 6), e.hp, e.kind.value,
                           round(e.carrying, 6)) for e in st.enemies),
        "food": sorted((s.id, round(s.x, 6), round(s.y, 6), round(s.amount, 6))
                       for s in st.world.food_sources),
        "phero_food": round(sum(sum(c) for c in st.pheromones.grids["food"]), 6),
        "phero_home": round(sum(sum(c) for c in st.pheromones.grids["home"]), 6),
        "territory": round(sum(sum(c) for c in st.territory.grid), 6),
        "food_store": round(st.colony.food_store, 6),
        "stress": round(st.colony.stress, 6),
        "queen": st.colony.queen.hp,
        "metrics": dict(st.colony.metrics),
        "chapter": st.milestones.chapter.title,
        "past_chapters": [c.title for c in st.milestones.past_chapters],
        "saga_len": len(st.history.saga),
        "directives": sorted((d.id, d.kind.value, round(d.strength, 6))
                             for d in st.directives.items),
    }


class TestSaveRoundTrip(unittest.TestCase):
    SAVE_AT = 90.0
    CONTINUE_FOR = 60.0

    @classmethod
    def setUpClass(cls):
        random.seed(42)
        original = GameState(SimConfig())
        for _ in range(int(cls.SAVE_AT / DT)):
            original.step(DT)

        # Through real JSON, not a dict copy: the codec has to survive
        # tuples becoming lists and keys becoming strings.
        cls.blob = json.dumps(dump_state(original))
        cls.at_save = fingerprint(original)

        # Both colonies draw from Python's global RNG, so they must run
        # one after the other rather than interleaved - alternating their
        # steps makes them consume each other's random numbers and
        # guarantees divergence regardless of the codec. This is a real
        # bug that was once diagnosed as a codec fault.
        for _ in range(int(cls.CONTINUE_FOR / DT)):
            original.step(DT)
        cls.fp_original = fingerprint(original)

        restored = load_state(json.loads(cls.blob))
        for _ in range(int(cls.CONTINUE_FOR / DT)):
            restored.step(DT)
        cls.fp_restored = fingerprint(restored)

    def test_loads_to_the_same_state_it_saved(self):
        self.assertEqual(self.at_save, fingerprint(load_state(json.loads(self.blob))))

    def test_resumed_colony_does_not_diverge(self):
        differing = [k for k in self.fp_original
                     if self.fp_original[k] != self.fp_restored[k]]
        self.assertEqual(differing, [], f"diverged in: {differing}")

    def test_save_is_not_absurdly_large(self):
        kb = len(self.blob) / 1024
        self.assertLess(kb, 2048, f"save is {kb:.0f} KB")


class TestConfigIsNotPersisted(unittest.TestCase):
    """Presentation settings must not be baked into saves.

    JSON has no tuples, so the audio event table round-trips as lists,
    which leaves a loaded config unequal to an identical fresh one and -
    since SimConfig is frozen and therefore hashable - unhashable too.
    Beyond the type problem, a save restores a colony, not a mixing desk.
    """

    def test_audio_settings_are_stripped_both_ways(self):
        from persistence.codec import _config_to_dict, _config_from_dict
        fresh = SimConfig()
        blob = json.loads(json.dumps(_config_to_dict(fresh)))
        self.assertEqual([k for k in blob if k.startswith("AUDIO_")], [])

        # A save written by an older build may still carry them.
        stale = dict(blob, AUDIO_DRONE_BASE=0.9,
                     AUDIO_EVENT_VOICES=[["queen_hit", "thud", 70, 0.45, 0.85]])
        back = _config_from_dict(stale)
        self.assertEqual(back, fresh)
        self.assertEqual(back.AUDIO_DRONE_BASE, fresh.AUDIO_DRONE_BASE)
        self.assertIsInstance(back.AUDIO_EVENT_VOICES, tuple)
        hash(back)  # frozen dataclasses must stay hashable after a load

    def test_simulation_tuning_survives(self):
        from persistence.codec import _config_to_dict, _config_from_dict
        custom = SimConfig(WORLD_W=200, PRAETORIAN_MAX=3, ENEMY_MAX_ALIVE=9)
        back = _config_from_dict(json.loads(json.dumps(_config_to_dict(custom))))
        self.assertEqual((back.WORLD_W, back.PRAETORIAN_MAX, back.ENEMY_MAX_ALIVE),
                         (200, 3, 9))


if __name__ == "__main__":
    unittest.main()
