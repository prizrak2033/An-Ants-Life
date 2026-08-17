"""
Turns a GameState into plain data and back.

Fidelity is the whole point: a resumed colony should be the one you
left, not one that merely looks like it. So this captures the awkward
things too - the pheromone and territory fields, the generated terrain,
the history log with its recency index, chapter progress and which
milestones are already spent, live directives and who is answering
them, and the RNG state, without which a resumed run would diverge from
the one that was saved.

Saves carry their own config rather than trusting the running defaults,
so a colony saved before a balance change still resumes on the numbers
it was played under. Unknown config keys are dropped and missing ones
fall back to current defaults, so a save from an older build loads
instead of crashing.
"""
from __future__ import annotations
import random
from collections import deque
from dataclasses import fields as dataclass_fields
from typing import Any, Dict

from config import SimConfig
from state import GameState

from ants.ant import Ant
from ants.roles import Role
from colony.directives import Directive, DirectiveKind
from colony.history import HistoryEvent, Significance
from colony.milestones import ChapterRecord, ChapterState
from colony.policy import ColonyPolicy
from enemies.enemy import Enemy
from enemies.kinds import EnemyKind
from world.food import FoodSource
from world.terrain import Terrain, TerrainMap

SAVE_VERSION = 1

_TERRAIN_BY_CODE = {
    str(i): t for i, t in enumerate(
        (Terrain.SOIL, Terrain.SAND, Terrain.LITTER, Terrain.ROCK, Terrain.WATER))
}


# ---------- config ----------

# The AUDIO_* settings are presentation, not simulation state, and are
# deliberately not saved. Two reasons, one of each kind:
#
# Right: a save restores a colony, not a mixing desk. Baking the mix in
# would pin every old save to the levels that happened to be set when it
# was written, so retuning the sound would silently not reach them.
#
# Necessary: JSON has no tuples, so the event table round-trips as lists
# of lists. That alone makes a loaded config unequal to an identical
# fresh one and, because SimConfig is frozen and therefore hashable,
# unhashable as well. Stripped on read too, not just skipped on write,
# so any save already carrying the field is handled.
def _is_persisted(name: str) -> bool:
    return not name.startswith("AUDIO_")


def _config_to_dict(cfg: SimConfig) -> Dict[str, Any]:
    return {f.name: getattr(cfg, f.name)
            for f in dataclass_fields(cfg) if _is_persisted(f.name)}


def _config_from_dict(data: Dict[str, Any]) -> SimConfig:
    known = {f.name for f in dataclass_fields(SimConfig) if _is_persisted(f.name)}
    return SimConfig(**{k: v for k, v in (data or {}).items() if k in known})


# ---------- pieces ----------

def _event_to_dict(e: HistoryEvent) -> Dict[str, Any]:
    return {"t": e.t, "tick": e.tick, "kind": e.kind, "cause": e.cause,
            "impact": e.impact, "tags": e.tags, "data": e.data}


def _event_from_dict(d: Dict[str, Any]) -> HistoryEvent:
    return HistoryEvent(t=d["t"], tick=d["tick"], kind=d["kind"], cause=d.get("cause"),
                        impact=d.get("impact") or {}, tags=d.get("tags") or [],
                        data=d.get("data") or {})


def _ant_to_dict(a: Ant) -> Dict[str, Any]:
    return {"id": a.id, "role": a.role.value, "x": a.x, "y": a.y, "vx": a.vx, "vy": a.vy,
            "carrying": a.carrying, "hp": a.hp, "last_combat_tick": a.last_combat_tick,
            "detour_until_tick": a.detour_until_tick, "detour_side": a.detour_side,
            "recruited_to": a.recruited_to}


def _ant_from_dict(d: Dict[str, Any]) -> Ant:
    return Ant(id=d["id"], role=Role(d["role"]), x=d["x"], y=d["y"], vx=d["vx"], vy=d["vy"],
               carrying=d["carrying"], hp=d["hp"], last_combat_tick=d["last_combat_tick"],
               detour_until_tick=d.get("detour_until_tick", -1),
               detour_side=d.get("detour_side", 1),
               recruited_to=d.get("recruited_to"))


def _enemy_to_dict(e: Enemy) -> Dict[str, Any]:
    return {"id": e.id, "kind": e.kind.value, "x": e.x, "y": e.y, "hp": e.hp,
            "speed": e.speed, "atk": e.atk, "terr_influence": e.terr_influence,
            "vx": e.vx, "vy": e.vy, "last_combat_tick": e.last_combat_tick,
            "detour_until_tick": e.detour_until_tick, "detour_side": e.detour_side,
            "spawn_x": e.spawn_x, "spawn_y": e.spawn_y,
            "steal_progress": e.steal_progress, "carrying": e.carrying,
            "fleeing": e.fleeing, "escaped": e.escaped}


def _enemy_from_dict(d: Dict[str, Any]) -> Enemy:
    e = Enemy(id=d["id"], kind=EnemyKind(d["kind"]), x=d["x"], y=d["y"], hp=d["hp"],
              speed=d["speed"], atk=d["atk"], terr_influence=d["terr_influence"])
    e.vx, e.vy = d["vx"], d["vy"]
    e.last_combat_tick = d["last_combat_tick"]
    e.detour_until_tick = d.get("detour_until_tick", -1)
    e.detour_side = d.get("detour_side", 1)
    e.spawn_x, e.spawn_y = d.get("spawn_x", e.x), d.get("spawn_y", e.y)
    e.steal_progress = d.get("steal_progress", 0.0)
    e.carrying = d.get("carrying", 0.0)
    e.fleeing = d.get("fleeing", False)
    e.escaped = d.get("escaped", False)
    return e


def _flat(grid) -> list:
    return [v for col in grid for v in col]


def _unflat(flat, cols: int, rows: int) -> list:
    return [list(flat[c * rows:(c + 1) * rows]) for c in range(cols)]


# ---------- whole state ----------

def dump_state(state: GameState) -> Dict[str, Any]:
    colony = state.colony
    hist = state.history
    tracker = state.milestones
    rng = random.getstate()

    return {
        "version": SAVE_VERSION,
        "config": _config_to_dict(state.cfg),
        "t": state.t,
        "tick": state.tick,
        "ending": state.ending,
        "colony_name": getattr(state, "colony_name", None),
        # (version, internal state tuple, gauss_next) - listified for JSON.
        "rng": [rng[0], list(rng[1]), rng[2]],
        "terrain": state.terrain.code_string(),
        "world": {
            "next_food_id": state.world._next_food_id,
            "food": [{"id": s.id, "x": s.x, "y": s.y, "amount": s.amount,
                      "claimed": s.claimed} for s in state.world.food_sources],
        },
        "pheromones": {
            "food": _flat(state.pheromones.grids["food"]),
            "home": _flat(state.pheromones.grids["home"]),
        },
        "territory": {
            "grid": _flat(state.territory.grid),
            "last_border_incident_tick": state.territory._last_border_incident_tick,
            "last_expansion_tick": state.territory._last_expansion_tick,
        },
        "colony": {
            "food_store": colony.food_store,
            "stress": colony.stress,
            "next_ant_id": colony._next_ant_id,
            "queen": {"x": colony.queen.x, "y": colony.queen.y,
                      "hp": colony.queen.hp, "hp_max": colony.queen.hp_max},
            "emergency": colony.emergency,
            "metrics": colony.metrics,
            "ants": [_ant_to_dict(a) for a in colony.ants],
        },
        "enemies": [_enemy_to_dict(e) for e in state.enemies],
        "next_enemy_id": state._next_enemy_id,
        "history": {
            "events": [_event_to_dict(e) for e in hist.events],
            "saga": [_event_to_dict(e) for e in hist.saga],
            "counts": hist.counts,
            "last_tick": hist._last_tick,
        },
        "milestones": {
            "chapter": {"active": tracker.chapter.active, "title": tracker.chapter.title,
                        "score": tracker.chapter.score,
                        "started_tick": tracker.chapter.started_tick,
                        "started_t": tracker.chapter.started_t,
                        "last_signal_tick": tracker.chapter.last_signal_tick},
            "past_chapters": [{"title": c.title, "started_t": c.started_t,
                               "ended_t": c.ended_t} for c in tracker.past_chapters],
            "earned": sorted(tracker._earned),
            "records": tracker.milestones,
            "last_change_tick": tracker._last_chapter_change_tick,
            "last_predator_tick": tracker._last_predator_tick,
            "pop_samples": [list(s) for s in tracker._pop_samples],
            "pressure_samples": list(tracker._pressure_samples),
        },
        "directives": {
            "next_id": state.directives._next_id,
            "items": [{"id": d.id, "kind": d.kind.value, "x": d.x, "y": d.y,
                       "strength": d.strength, "created_t": d.created_t,
                       "recruits": d.recruits} for d in state.directives.items],
        },
        "policy": {"scout_target": state.policy.scout_target,
                   "praetorian_target": state.policy.praetorian_target,
                   "soldier_target": state.policy.soldier_target,
                   "auto_defense": state.policy.auto_defense,
                   "rally": state.policy.rally},
    }


def load_state(data: Dict[str, Any]) -> GameState:
    version = data.get("version")
    if version != SAVE_VERSION:
        raise ValueError(f"unsupported save version {version!r} (expected {SAVE_VERSION})")

    cfg = _config_from_dict(data.get("config"))
    state = GameState(cfg)
    state.t = data["t"]
    state.tick = data["tick"]
    state.ending = data.get("ending")
    state.colony_name = data.get("colony_name")

    rng = data.get("rng")
    if rng:
        try:
            random.setstate((rng[0], tuple(rng[1]), rng[2]))
        except (TypeError, ValueError):
            pass  # a usable colony beats refusing to load over RNG continuity

    _load_terrain(state, data.get("terrain"))

    world = data["world"]
    state.world.food_sources = [
        FoodSource(id=s["id"], x=s["x"], y=s["y"], amount=s["amount"], claimed=s["claimed"])
        for s in world["food"]
    ]
    state.world._next_food_id = world["next_food_id"]

    ph = state.pheromones
    for channel in ("food", "home"):
        ph.grids[channel] = _unflat(data["pheromones"][channel], ph.cols, ph.rows)

    terr = data["territory"]
    state.territory.grid = _unflat(terr["grid"], state.territory.cols, state.territory.rows)
    state.territory._last_border_incident_tick = terr["last_border_incident_tick"]
    state.territory._last_expansion_tick = terr["last_expansion_tick"]

    col = data["colony"]
    colony = state.colony
    colony.food_store = col["food_store"]
    colony.stress = col["stress"]
    colony._next_ant_id = col["next_ant_id"]
    colony.queen.x, colony.queen.y = col["queen"]["x"], col["queen"]["y"]
    colony.queen.hp, colony.queen.hp_max = col["queen"]["hp"], col["queen"]["hp_max"]
    colony.emergency = dict(col["emergency"])
    colony.metrics = dict(col["metrics"])
    colony.ants = [_ant_from_dict(a) for a in col["ants"]]

    state.enemies = [_enemy_from_dict(e) for e in data["enemies"]]
    state._next_enemy_id = data["next_enemy_id"]

    _load_history(state, data["history"])
    _load_milestones(state, data["milestones"])
    _load_directives(state, data["directives"])

    pol = data["policy"]
    state.policy = ColonyPolicy(scout_target=pol["scout_target"],
                                soldier_target=pol["soldier_target"],
                                praetorian_target=pol.get("praetorian_target", 3),
                                auto_defense=pol["auto_defense"],
                                rally=pol["rally"])
    return state


def _load_terrain(state: GameState, code: str) -> None:
    if not code:
        return
    t: TerrainMap = state.terrain
    expected = t.cols * t.rows
    if len(code) != expected:
        return  # world geometry changed; keep the freshly generated map
    for cx in range(t.cols):
        for cy in range(t.rows):
            t.tiles[cx][cy] = _TERRAIN_BY_CODE.get(code[cx * t.rows + cy], Terrain.SOIL)
    # Passability, speed and decay tables are derived, so rebuild them.
    t._build_lookups()
    state.pheromones = type(state.pheromones)(state.cfg, t)


def _load_history(state: GameState, data: Dict[str, Any]) -> None:
    hist = state.history
    events = [_event_from_dict(d) for d in data["events"]]
    hist.events = deque(events, maxlen=hist.events.maxlen)
    hist.notable = deque(
        [e for e in events if e.significance >= Significance.NOTABLE],
        maxlen=hist.notable.maxlen)
    hist.saga = [_event_from_dict(d) for d in data["saga"]]
    hist.counts = dict(data["counts"])
    hist._last_tick = {k: int(v) for k, v in data["last_tick"].items()}


def _load_milestones(state: GameState, data: Dict[str, Any]) -> None:
    tracker = state.milestones
    ch = data["chapter"]
    tracker.chapter = ChapterState(active=ch["active"], title=ch["title"],
                                   score=ch.get("score", 0.0),
                                   started_tick=ch["started_tick"],
                                   started_t=ch["started_t"],
                                   last_signal_tick=ch["last_signal_tick"])
    tracker.past_chapters = [
        ChapterRecord(title=c["title"], started_t=c["started_t"], ended_t=c["ended_t"])
        for c in data["past_chapters"]
    ]
    tracker._earned = set(data["earned"])
    tracker.milestones = list(data["records"])
    tracker._last_chapter_change_tick = data["last_change_tick"]
    tracker._last_predator_tick = data.get("last_predator_tick", -10 ** 9)
    tracker._pop_samples = deque((tuple(s) for s in data["pop_samples"]),
                                 maxlen=tracker._pop_samples.maxlen)
    tracker._pressure_samples = deque(data["pressure_samples"],
                                      maxlen=tracker._pressure_samples.maxlen)


def _load_directives(state: GameState, data: Dict[str, Any]) -> None:
    board = state.directives
    board._next_id = data["next_id"]
    board.items = [
        Directive(id=d["id"], kind=DirectiveKind(d["kind"]), x=d["x"], y=d["y"],
                  strength=d["strength"], created_t=d["created_t"],
                  recruits=d.get("recruits", 0))
        for d in data["items"]
    ]
