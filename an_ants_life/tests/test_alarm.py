"""The alarm channel: a worker's only way of saying it is in trouble.

Measured missing. Over 8 runs at 900s non-combatants were 59% of all
casualties and 91.2% of them died with no fighter inside soldier scan
radius, a median 37.7 away from the nearest ant that could have helped.

The risk in fixing that is not the signal, it is the answer. Soldiers
leaving the nest is precisely how the defend directive used to kill
queens, and `DIRECTIVE_DEFEND_MIN_GARRISON` exists because of it. The
floor tests here were written before the mechanic was measured at all,
because that failure has history.
"""
from __future__ import annotations

import random
import unittest

from tests.harness import DT
from config import SimConfig
from state import GameState
from ants.ant import Ant
from ants.roles import Role
from ants.ai import choose_intent
from systems.directives import update_directives


def _colony(n_soldiers, **over):
    random.seed(11)
    # Explicitly on. The channel ships disabled - it cuts casualties 7%
    # and costs 16% of the colony's food - but it is kept working behind
    # the flag, so these test it rather than the default.
    over.setdefault("ALARM_ENABLE", True)
    cfg = SimConfig(ENEMY_ENABLE=False, **over)
    st = GameState(cfg)
    st.colony.ants.clear()
    nx, ny = st.nest_pos
    for i in range(n_soldiers):
        st.colony.ants.append(Ant(i + 1, Role.SOLDIER, nx, ny, hp=cfg.ANT_HP_MAX))
    return st, cfg


class TestTheNestIsNeverLeftOpen(unittest.TestCase):
    def test_answering_never_takes_the_garrison_below_its_floor(self):
        for n in range(0, 20):
            st, cfg = _colony(n)
            st.pheromones.deposit("alarm", (st.nest_pos[0] + 30, st.nest_pos[1]), 50.0)
            update_directives(st, DT)
            away = len(st.colony.emergency["alarm_responders"])
            self.assertGreaterEqual(
                n - away, min(n, cfg.DIRECTIVE_DEFEND_MIN_GARRISON),
                f"{n} soldiers, {away} answered, floor is "
                f"{cfg.DIRECTIVE_DEFEND_MIN_GARRISON}")

    def test_a_small_garrison_answers_nothing(self):
        """Below the floor there is no one to spare, however loud it is."""
        st, cfg = _colony(cfg_floor := SimConfig().DIRECTIVE_DEFEND_MIN_GARRISON)
        st.pheromones.deposit("alarm", (st.nest_pos[0] + 20, st.nest_pos[1]), 99.0)
        update_directives(st, DT)
        self.assertEqual(st.colony.emergency["alarm_responders"], frozenset())

    def test_the_two_ways_out_of_the_nest_share_one_budget(self):
        """Two limits that each respect the floor can still breach it
        together, which is the whole reason they are computed as one."""
        from colony.directives import DirectiveKind
        st, cfg = _colony(12)
        st.directives.place(DirectiveKind.DEFEND, st.nest_pos[0] + 25,
                            st.nest_pos[1], st.t)
        st.pheromones.deposit("alarm", (st.nest_pos[0] + 30, st.nest_pos[1]), 50.0)
        update_directives(st, DT)
        detached = st.colony.emergency["defend_detachment"]
        answering = st.colony.emergency["alarm_responders"]
        self.assertEqual(detached & answering, frozenset(),
                         "a soldier was counted in both parties at once")
        self.assertGreaterEqual(12 - len(detached) - len(answering),
                                cfg.DIRECTIVE_DEFEND_MIN_GARRISON)

    def test_praetorians_never_answer(self):
        st, cfg = _colony(10)
        nx, ny = st.nest_pos
        guard = Ant(99, Role.PRAETORIAN, nx, ny, hp=cfg.ANT_HP_MAX)
        st.colony.ants.append(guard)
        st.pheromones.deposit("alarm", (nx + 25, ny), 50.0)
        update_directives(st, DT)
        self.assertNotIn(99, st.colony.emergency["alarm_responders"])
        intent = choose_intent(st, guard, DT)
        self.assertLess(
            ((intent.target[0] - nx) ** 2 + (intent.target[1] - ny) ** 2) ** 0.5,
            cfg.PRAETORIAN_GUARD_RADIUS + 1.0,
            "a praetorian left the queen's chamber for an alarm")


class TestTheSignal(unittest.TestCase):
    def test_being_hit_raises_the_alarm_where_it_happened(self):
        from systems.combat import update_combat
        from enemies.enemy import make_enemy
        from enemies.kinds import EnemyKind
        random.seed(3)
        cfg = SimConfig(ENEMY_ENABLE=False, ALARM_ENABLE=True)
        st = GameState(cfg)
        st.colony.ants.clear()
        x, y = 50.0, 40.0
        st.colony.ants.append(Ant(1, Role.WORKER, x, y, hp=cfg.ANT_HP_MAX))
        st.enemies.append(make_enemy(cfg, 1, EnemyKind.PREDATOR, x, y))

        self.assertEqual(st.pheromones.level_at("alarm", (x, y)), 0.0)
        update_combat(st, DT)
        self.assertGreater(st.pheromones.level_at("alarm", (x, y)), 0.0)

    def test_a_call_outlives_the_crossing_it_has_to_pay_for(self):
        """An ant crosses the answer radius in about a second. A call has
        to still be audible when the answer arrives or the channel is
        decorative."""
        import math
        cfg = SimConfig(ALARM_ENABLE=True)
        crossing = cfg.ALARM_ANSWER_RADIUS / cfg.ANT_SPEED
        st = GameState(cfg)
        pos = (50.0, 40.0)
        t = 0.0
        # A fight, not a single blow: contact repeats on the combat
        # cooldown for as long as the ant lives.
        life = cfg.ANT_HP_MAX * cfg.COMBAT_COOLDOWN_SECONDS
        last = -99.0
        audible_until = 0.0
        for _ in range(int(6.0 / DT)):
            if t <= life and t - last >= cfg.COMBAT_COOLDOWN_SECONDS:
                st.pheromones.deposit("alarm", pos, cfg.ALARM_DEPOSIT_AMOUNT)
                last = t
            st.pheromones.decay_and_diffuse(DT)
            t += DT
            if st.pheromones.level_at("alarm", pos) >= cfg.ALARM_MIN_LEVEL:
                audible_until = t
        self.assertGreater(audible_until, crossing,
                           f"a call fades after {audible_until:.2f}s but the "
                           f"crossing takes {crossing:.2f}s")

    def test_the_flag_turns_the_whole_channel_off(self):
        from systems.combat import update_combat
        from enemies.enemy import make_enemy
        from enemies.kinds import EnemyKind
        random.seed(3)
        cfg = SimConfig(ENEMY_ENABLE=False, ALARM_ENABLE=False)
        st = GameState(cfg)
        st.colony.ants.clear()
        x, y = 50.0, 40.0
        st.colony.ants.append(Ant(1, Role.WORKER, x, y, hp=cfg.ANT_HP_MAX))
        st.enemies.append(make_enemy(cfg, 1, EnemyKind.PREDATOR, x, y))
        update_combat(st, DT)
        self.assertEqual(st.pheromones.level_at("alarm", (x, y)), 0.0)
        update_directives(st, DT)
        self.assertEqual(st.colony.emergency["alarm_responders"], frozenset())


class TestTheAnswer(unittest.TestCase):
    def test_a_spare_soldier_goes_to_the_call(self):
        st, cfg = _colony(14)
        nx, ny = st.nest_pos
        call = (nx + 30.0, ny)
        st.pheromones.deposit("alarm", call, 50.0)
        update_directives(st, DT)
        responders = st.colony.emergency["alarm_responders"]
        self.assertGreater(len(responders), 0, "nobody was free to answer")
        ant = next(a for a in st.colony.ants if a.id in responders)
        intent = choose_intent(st, ant, DT)
        self.assertAlmostEqual(intent.target[0], call[0], delta=cfg.PHERO_GRID)
        self.assertAlmostEqual(intent.target[1], call[1], delta=cfg.PHERO_GRID)

    def test_a_call_out_of_earshot_is_not_answered(self):
        st, cfg = _colony(14)
        nx, ny = st.nest_pos
        st.pheromones.deposit("alarm", (nx + cfg.ALARM_ANSWER_RADIUS * 2.0, ny), 50.0)
        update_directives(st, DT)
        responders = st.colony.emergency["alarm_responders"]
        ant = next(a for a in st.colony.ants if a.id in responders)
        intent = choose_intent(st, ant, DT)
        self.assertLess(abs(intent.target[0] - nx), 30.0,
                        "a soldier crossed the map for a call it cannot hear")

    def test_an_enemy_in_front_of_it_beats_a_call_elsewhere(self):
        """Alarm only ever adds reach. Inside its own scan radius the
        soldier can already see the fight, and leaving one for a louder
        one further off would just swap which ant dies."""
        from enemies.enemy import make_enemy
        from enemies.kinds import EnemyKind
        st, cfg = _colony(14)
        nx, ny = st.nest_pos
        here = st.colony.ants[-1]
        st.enemies.append(make_enemy(cfg, 1, EnemyKind.WARRIOR,
                                     here.x + 3.0, here.y))
        st.pheromones.deposit("alarm", (nx + 35.0, ny), 99.0)
        update_directives(st, DT)
        intent = choose_intent(st, here, DT)
        self.assertLess(abs(intent.target[0] - (here.x + 3.0)), 2.0,
                        "a soldier walked away from an enemy beside it")


if __name__ == "__main__":
    unittest.main()
