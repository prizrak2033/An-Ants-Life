"""Scripted players, for measuring how much playing the game matters.

The colony's end population over a fifteen-minute run spans roughly 10 to
47. Nothing in the project could say how much of that spread is the
player's doing and how much is the seed, and that is a question worth
settling before any more balance work: if attention does not move the
outcome, then this is a simulation people watch rather than a game they
play, and tuning attrition is rearranging furniture.

Two rules make the answer mean something.

A bot sees only what the interface renders. `View` below is a strict
subset of the snapshot the browser already draws - no ant list, no
pheromone field, no enemy the map does not show. A bot that could read
simulation internals would be an oracle, and beating a passive run with
one would prove nothing about a person.

A bot acts only through `server.apply_player_action`, the same entry
point the HTTP handler uses. It cannot reach into GameState, so it cannot
do anything that someone holding the interface could not do.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from tests.harness import DT, compare_rows
from config import SimConfig
from state import GameState
from server import apply_player_action, work_cost, WORK_COSTS, _garrison


@dataclass
class View:
    """What a player can see. A subset of the rendered snapshot."""
    t: float
    population: int
    food_store: float
    hunger: float
    pressure: float
    queen_hp: int
    queen_hp_max: int
    garrison_home: int
    garrison_floor: int
    nest: Tuple[float, float]
    food: List[Tuple[float, float, float]]          # x, y, amount
    enemies: List[Tuple[float, float, str]]         # x, y, kind
    marks: List[Tuple[int, str, float, float]]      # id, kind, x, y
    # A war band gathering at the border, which the map draws and the
    # chronicle announces. This is the only threat in the game slow
    # enough to answer: a lone warrior is at the queen inside two
    # seconds, which no recall can beat.
    massing: int                                   # warriors mustering, 0 if none
    massing_seconds: float                         # until they advance
    inbound: int                                   # band warriors already advancing
    # The food-spending decision. Both are on the screen from the first
    # frame, priced, with the larder next to them - the player is meant
    # to be choosing between them long before either is affordable.
    works: List[str]                               # already built
    work_costs: dict                               # name -> food price


def observe(state: GameState) -> View:
    colony = state.colony
    g = _garrison(state)
    return View(
        t=state.t,
        population=len(colony.ants),
        food_store=colony.food_store,
        hunger=colony.emergency.get("hunger", 0.0),
        pressure=colony.emergency.get("territory_pressure", 0.0),
        queen_hp=colony.queen.hp,
        queen_hp_max=colony.queen.hp_max,
        garrison_home=g["home"],
        garrison_floor=g["floor"],
        nest=state.nest_pos,
        food=[(s.x, s.y, s.amount) for s in state.world.food_sources if s.amount > 0],
        enemies=[(e.x, e.y, e.kind.value) for e in state.enemies],
        marks=[(d.id, d.kind.value, d.x, d.y) for d in state.directives.items],
        massing=sum(1 for e in state.enemies
                    if e.band and e.muster_until_t > state.t),
        massing_seconds=max([e.muster_until_t - state.t for e in state.enemies
                             if e.band and e.muster_until_t > state.t] or [0.0]),
        inbound=sum(1 for e in state.enemies
                    if e.band and e.muster_until_t <= 0.0),
        works=list(colony.works),
        work_costs={w: work_cost(state.cfg, w) for w in WORK_COSTS},
    )


class Bot:
    name = "bot"
    # How often it looks at the screen and decides. A person does not
    # re-evaluate thirty times a second.
    decide_every = 2.0

    def reset(self) -> None:
        pass

    def act(self, view: View, issue: Callable[[dict], bool]) -> None:
        raise NotImplementedError


class PassiveBot(Bot):
    """Opens the game and watches. The control arm."""
    name = "passive"

    def act(self, view, issue):
        return


class AttentiveBot(Bot):
    """Plays the three moves the interface is built around.

    Deliberately not clever. Every move here is one an earlier session
    already measured as helpful - marking food, recalling during a siege,
    leaning the caste mix toward soldiers under pressure - so this is a
    test of whether attention pays, not a search for an optimal policy. A
    bot that outplayed any human would answer a different question.
    """
    name = "attentive"
    decide_every = 2.0

    ANSWER_MUSTER_WITHIN = 6.0   # seconds before a band advances
    # A warrior has 3 HP and a soldier deals 3, so a defender is worth
    # roughly a warrior. Answer only when the band is close to matching
    # the garrison actually standing at the nest.
    OUTMATCHED_RATIO = 0.8
    SIEGE_RADIUS = 20.0          # warriors this close are on the queen
    LIFT_SIEGE_RADIUS = 30.0     # hysteresis, so rally does not flicker
    MARK_MIN_DIST = 24.0         # near food needs no help finding
    MARK_REFRESH = 40.0          # marks expire at 75s
    MAX_MARKS = 2

    def reset(self):
        self._marked = {}
        self._rallying = False
        self._soldier_target = None
        self._guard_set = False

    def act(self, view, issue):
        self._defend(view, issue)
        self._forage(view, issue)
        self._standing_orders(view, issue)

    # -- recall when the queen is actually threatened -------------------
    def _defend(self, view, issue):
        nx, ny = view.nest
        radius = self.LIFT_SIEGE_RADIUS if self._rallying else self.SIEGE_RADIUS
        pressing = [e for e in view.enemies
                    if e[2] == "WARRIOR" and math.hypot(e[0] - nx, e[1] - ny) <= radius]

        # A band about to advance, or already on its way, is answered
        # before it arrives - but only if the garrison cannot take it.
        # The warning reports the band's size precisely so that call can
        # be made, and recalling for every band is how this policy first
        # went wrong: halting the whole economy for a fight roughly 18
        # soldiers were going to win anyway cost 14 births a run to save
        # 12.7 casualties, and six colonies with it.
        band = 0
        if view.massing and view.massing_seconds <= self.ANSWER_MUSTER_WITHIN:
            band = view.massing
        elif view.inbound > 0:
            band = view.inbound
        band_coming = band > 0 and band >= view.garrison_home * self.OUTMATCHED_RATIO

        # Rally stops foraging outright, so it is worth it only when the
        # nest is both threatened and short of defenders - which is the
        # state every measured colony death has been found in.
        want = band_coming or (bool(pressing) and view.garrison_home <= view.garrison_floor)
        if want and not self._rallying:
            issue({"action": "set_rally", "on": True})
            self._rallying = True
        elif not pressing and not band_coming and self._rallying:
            issue({"action": "set_rally", "on": False})
            self._rallying = False

    # -- point the colony at food it has found --------------------------
    def _forage(self, view, issue):
        if self._rallying:
            return  # nobody is foraging; a mark now would be noise
        nx, ny = view.nest
        far = [f for f in view.food
               if math.hypot(f[0] - nx, f[1] - ny) >= self.MARK_MIN_DIST]
        far.sort(key=lambda f: -f[2])

        live = {(round(m[2]), round(m[3])) for m in view.marks if m[1] == "FORAGE"}
        placed = 0
        for fx, fy, _amt in far[:self.MAX_MARKS]:
            key = (round(fx), round(fy))
            last = self._marked.get(key, -1e9)
            if key in live and view.t - last < self.MARK_REFRESH:
                continue
            if view.t - last < self.MARK_REFRESH:
                continue
            issue({"action": "place_directive", "kind": "forage", "x": fx, "y": fy})
            self._marked[key] = view.t
            placed += 1
            if placed >= 1:
                break  # one deliberate order per look, not a spray

        # Forget piles that are gone, so their keys can be reused.
        alive = {(round(f[0]), round(f[1])) for f in view.food}
        for key in list(self._marked):
            if key not in alive:
                del self._marked[key]

    # -- lean the caste mix with the pressure ---------------------------
    def _standing_orders(self, view, issue):
        if not self._guard_set and view.t > 30.0:
            issue({"action": "set_policy", "praetorian": 3})
            self._guard_set = True

        want = 0.36 if view.pressure > 0.45 else (0.26 if view.pressure < 0.20 else None)
        if want is not None and want != self._soldier_target:
            issue({"action": "set_policy", "soldier": want})
            self._soldier_target = want


class BuilderBot(Bot):
    """Spends food and does nothing else.

    Deliberately not an attentive player with building bolted on. Three
    experiments found that directing ants never beat leaving them alone,
    so mixing the two arms would leave any result unattributable: this
    one is passive in every respect except the purchase, which makes
    passive-vs-builder a clean read on whether the spending decision by
    itself is worth anything.

    The order is a parameter because which work to buy first is the
    decision the player is actually being asked to make, and a bot that
    hard-coded one answer could not measure the other.
    """
    name = "builder"
    decide_every = 2.0

    # Buying is not free even when it is affordable: the birth gate is a
    # food threshold, so draining the store to the floor trades ants for
    # the work. Waiting for a cushion on top of the price is what a
    # player watching the larder would do.
    RESERVE = 40.0

    def __init__(self, order=("nursery", "rampart"), name=None):
        self.order = tuple(order)
        self.name = name or f"build-{'-'.join(self.order)}"

    def reset(self):
        pass

    def act(self, view, issue):
        for work in self.order:
            if work in view.works:
                continue
            cost = view.work_costs.get(work)
            if cost is None:
                continue
            if view.food_store >= cost + self.RESERVE:
                issue({"action": "build", "work": work})
            # Whether it bought or not, stop here: the next work waits
            # its turn, or the cheaper one always wins by default.
            return


def run_with_bot(seed: int, sim_seconds: float, bot: Bot, **cfg_over) -> dict:
    """One colony played by `bot`. Same row shape as harness.run()."""
    random.seed(seed)
    cfg = SimConfig(**cfg_over)
    state = GameState(cfg)
    bot.reset()

    ticks = int(sim_seconds / DT)
    upkeep_total = 0.0
    famine_ticks = 0
    pop_samples = []
    actions = 0
    next_decision = 0.0

    def issue(cmd):
        nonlocal actions
        ok = apply_player_action(state, cfg, cmd)
        actions += 1 if ok else 0
        return ok

    for _ in range(ticks):
        if state.t >= next_decision:
            bot.act(observe(state), issue)
            next_decision = state.t + bot.decide_every

        pop_before = len(state.colony.ants)
        state.step(DT)
        upkeep_total += pop_before * cfg.FOOD_UPKEEP_PER_ANT_PER_SEC * DT
        if state.colony.emergency.get("famine_active"):
            famine_ticks += 1
        pop_samples.append(len(state.colony.ants))
        if state.colony.queen.hp <= 0:
            break

    m = state.colony.metrics
    return {
        "t": state.t,
        "survived": state.colony.queen.hp > 0 and state.t >= sim_seconds - 1.0,
        "deposits": m["food_deposits"],
        "deposits_per_sec": m["food_deposits"] / max(state.t, 1e-9),
        "upkeep_per_sec": upkeep_total / max(state.t, 1e-9),
        "famine_frac": famine_ticks / max(len(pop_samples), 1),
        "pop_end": pop_samples[-1] if pop_samples else 0,
        "pop_peak": max(pop_samples) if pop_samples else 0,
        "born": m["ants_born"],
        "lost": m["ants_killed"],
        "queen_hp": state.colony.queen.hp,
        "actions": actions,
        "works": list(state.colony.works),
    }


def compare_bots(seeds, sim_seconds: float, bot_a: Bot, bot_b: Bot, **cfg_over) -> dict:
    """Both players over the same seeds - same maps, same food, same draws."""
    rows_a = [run_with_bot(s, sim_seconds, bot_a, **cfg_over) for s in seeds]
    rows_b = [run_with_bot(s, sim_seconds, bot_b, **cfg_over) for s in seeds]
    out = compare_rows(rows_a, rows_b, bot_a.name, bot_b.name, sim_seconds)
    out["actions_a"] = sum(r["actions"] for r in rows_a)
    out["actions_b"] = sum(r["actions"] for r in rows_b)
    return out
