import unittest
from unittest.mock import patch

from an_ants_life.ants.roles import Role
from an_ants_life.config import SimConfig
from an_ants_life.enemies.red_ant import RedAnt
from an_ants_life.state import GameState
from an_ants_life.systems.combat import update_combat
from an_ants_life.systems.emergencies import update_emergencies


class SystemBehaviorTests(unittest.TestCase):
    def test_combat_kills_enemy_and_records_metrics(self) -> None:
        state = GameState(SimConfig())
        soldier = next(ant for ant in state.colony.ants if ant.role == Role.SOLDIER)
        soldier.x = state.cfg.NEST_X
        soldier.y = state.cfg.NEST_Y
        state.enemies = [RedAnt(id=1, x=soldier.x, y=soldier.y, hp=1)]

        update_combat(state, dt=0.01)

        self.assertEqual(len(state.enemies), 0)
        self.assertEqual(state.colony.metrics["enemy_kills"], 1)
        self.assertEqual(state.history.last().kind, "enemy_kill")

    def test_famine_reassigns_non_worker_roles(self) -> None:
        state = GameState(SimConfig())
        state.tick = 50
        state.colony.emergency["hunger"] = state.cfg.EMERGENCY_FAMINE_ON_HUNGER
        pre_workers = sum(1 for ant in state.colony.ants if ant.role == Role.WORKER)

        update_emergencies(state, dt=0.01)

        post_workers = sum(1 for ant in state.colony.ants if ant.role == Role.WORKER)
        self.assertTrue(state.colony.emergency["famine_active"])
        self.assertGreater(post_workers, pre_workers)
        self.assertGreater(state.colony.metrics["role_conversions"], 0)

    def test_territory_progression_emits_expansion(self) -> None:
        state = GameState(SimConfig())
        state.tick = state.cfg.TERR_EVENT_COOLDOWN_TICKS

        with patch("an_ants_life.world.territory.random.uniform", return_value=0.0):
            state.territory.update(state)

        self.assertGreaterEqual(state.colony.metrics["expansions"], 1)
        self.assertIn("territory_control", state.colony.emergency)
        self.assertEqual(state.history.last().kind, "territory_expansion")


if __name__ == "__main__":
    unittest.main()
