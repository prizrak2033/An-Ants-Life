import tempfile
import unittest
from pathlib import Path

from an_ants_life.config import SimConfig
from an_ants_life.main import advance_simulation, get_stop_message
from an_ants_life.persistence import load_game, save_game
from an_ants_life.state import GameState


class RuntimeTests(unittest.TestCase):
    def test_history_is_bounded(self) -> None:
        state = GameState(SimConfig())
        for idx in range(state.cfg.HISTORY_MAX_EVENTS + 25):
            state.emit_history("test_event", {"idx": idx})
        self.assertEqual(len(state.history.events), state.cfg.HISTORY_MAX_EVENTS)
        self.assertEqual(state.history.events[0].data["idx"], 25)

    def test_persistence_round_trip_clamps_invalid_values(self) -> None:
        cfg = SimConfig()
        state = GameState(cfg)
        state.tick = 7
        state.colony.food_store = 12.5
        state.colony.queen.hp = 3
        state.colony.ants[0].x = cfg.WORLD_W + 10
        state.colony.ants[0].carrying = 2.0

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "save.json"
            save_game(state, save_path)
            raw = save_path.read_text(encoding="utf-8")
            raw = raw.replace(f'"x": {cfg.WORLD_W + 10}', '"x": 9999')
            raw = raw.replace('"tick": 7', '"tick": -4')
            save_path.write_text(raw, encoding="utf-8")

            loaded = load_game(save_path, cfg)

        self.assertEqual(loaded.tick, 0)
        self.assertEqual(loaded.colony.food_store, 12.5)
        self.assertEqual(loaded.colony.queen.hp, 3)
        self.assertEqual(loaded.colony.ants[0].x, cfg.WORLD_W)

    def test_advance_simulation_updates_tick_and_stop_message(self) -> None:
        state = GameState(SimConfig())
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "save.json"
            advance_simulation(state, dt=0.01, save_path=save_path, autosave_ticks=1)
            self.assertEqual(state.tick, 1)
            self.assertTrue(save_path.exists())
        self.assertEqual(get_stop_message(state, max_ticks=1), "⏸️ Paused after 1 ticks.")


if __name__ == "__main__":
    unittest.main()
