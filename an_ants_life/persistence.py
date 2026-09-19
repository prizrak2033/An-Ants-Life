from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .ants.ant import Ant
from .ants.roles import Role
from .colony.colony_state import Queen
from .colony.history import HistoryEvent, HistoryLog
from .colony.milestones import ChapterState
from .enemies.red_ant import RedAnt
from .state import GameState
from .world.food import FoodSource

DEFAULT_SAVE_FILE = Path(".an_ants_life_save.json")
SAVE_VERSION = 1


def load_game(save_path: Path, cfg) -> GameState:
    if not save_path.exists():
        return GameState(cfg)

    with save_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if payload.get("version") != SAVE_VERSION:
        raise ValueError(f"Unsupported save version: {payload.get('version')!r}")

    data = _require_dict(payload, "state")
    state = GameState(cfg)
    state.t = _as_float(data.get("t", 0.0))
    state.tick = _as_int(data.get("tick", 0))
    state._next_enemy_id = _as_int(data.get("_next_enemy_id", 1))

    world = _require_dict(data, "world")
    state.world.food_sources = [
        FoodSource(
            id=_as_int(item.get("id")),
            x=_as_float(item.get("x")),
            y=_as_float(item.get("y")),
            amount=max(0.0, _as_float(item.get("amount"))),
            claimed=bool(item.get("claimed", False)),
        )
        for item in _require_list(world, "food_sources")
    ]
    state.world._next_food_id = _as_int(world.get("next_food_id", len(state.world.food_sources) + 1))

    pheromones = _require_dict(data, "pheromones")
    state.pheromones.grids = {
        channel: _grid_from_json(grid)
        for channel, grid in _require_dict(pheromones, "grids").items()
    }

    territory = _require_dict(data, "territory")
    state.territory.grid = _grid_from_json(territory.get("grid", state.territory.grid))
    state.territory._last_border_incident_tick = _as_int(territory.get("last_border_incident_tick", -10_000))
    state.territory._last_expansion_tick = _as_int(territory.get("last_expansion_tick", -10_000))

    colony = _require_dict(data, "colony")
    state.colony.food_store = max(0.0, _as_float(colony.get("food_store", state.colony.food_store)))
    state.colony.stress = min(1.0, max(0.0, _as_float(colony.get("stress", state.colony.stress))))

    queen = _require_dict(colony, "queen")
    state.colony.queen = Queen(
        x=_as_float(queen.get("x", cfg.NEST_X)),
        y=_as_float(queen.get("y", cfg.NEST_Y)),
        hp=_as_int(queen.get("hp", cfg.QUEEN_HP_MAX)),
        hp_max=_as_int(queen.get("hp_max", cfg.QUEEN_HP_MAX)),
    )

    state.colony.emergency = _dict_with_json_scalars(colony.get("emergency", {}))
    state.colony.metrics = {
        str(key): _as_int(value)
        for key, value in _dict_with_json_scalars(colony.get("metrics", {})).items()
    }
    state.colony.ants = [
        Ant(
            id=_as_int(item.get("id")),
            role=Role(item.get("role", Role.WORKER.value)),
            x=_as_float(item.get("x")),
            y=_as_float(item.get("y")),
            vx=_as_float(item.get("vx", 0.0)),
            vy=_as_float(item.get("vy", 0.0)),
            carrying=max(0.0, _as_float(item.get("carrying", 0.0))),
            hp=_as_int(item.get("hp", cfg.ANT_HP_MAX)),
            last_combat_tick=_as_int(item.get("last_combat_tick", -10_000)),
        )
        for item in _require_list(colony, "ants")
    ]

    history = _require_dict(data, "history")
    state.history = HistoryLog(
        events=[
            HistoryEvent(
                t=_as_float(item.get("t")),
                tick=_as_int(item.get("tick")),
                kind=str(item.get("kind")),
                cause=item.get("cause"),
                impact=_dict_with_json_scalars(item.get("impact", {})),
                tags=[str(tag) for tag in item.get("tags", [])],
                data=_dict_with_json_scalars(item.get("data", {})),
            )
            for item in _require_list(history, "events")
        ]
    )

    milestones = _require_dict(data, "milestones")
    chapter = _require_dict(milestones, "chapter")
    state.milestones.chapter = ChapterState(
        active=bool(chapter.get("active", False)),
        title=str(chapter.get("title", "—")),
        started_tick=_as_int(chapter.get("started_tick", -1)),
        last_signal_tick=_as_int(chapter.get("last_signal_tick", -1)),
    )
    state.milestones._last_chapter_change_tick = _as_int(
        milestones.get("last_chapter_change_tick", -10_000)
    )

    state.enemies = [
        RedAnt(
            id=_as_int(item.get("id")),
            x=_as_float(item.get("x")),
            y=_as_float(item.get("y")),
            hp=_as_int(item.get("hp", cfg.REDANT_HP)),
            vx=_as_float(item.get("vx", 0.0)),
            vy=_as_float(item.get("vy", 0.0)),
            last_combat_tick=_as_int(item.get("last_combat_tick", -10_000)),
        )
        for item in _require_list(data, "enemies")
    ]
    return state


def save_game(state: GameState, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SAVE_VERSION,
        "state": {
            "t": state.t,
            "tick": state.tick,
            "_next_enemy_id": state._next_enemy_id,
            "world": {
                "next_food_id": state.world._next_food_id,
                "food_sources": [asdict(source) for source in state.world.food_sources],
            },
            "pheromones": {"grids": state.pheromones.grids},
            "territory": {
                "grid": state.territory.grid,
                "last_border_incident_tick": state.territory._last_border_incident_tick,
                "last_expansion_tick": state.territory._last_expansion_tick,
            },
            "colony": {
                "food_store": state.colony.food_store,
                "stress": state.colony.stress,
                "queen": asdict(state.colony.queen),
                "emergency": state.colony.emergency,
                "metrics": state.colony.metrics,
                "ants": [asdict(ant) | {"role": ant.role.value} for ant in state.colony.ants],
            },
            "history": {
                "events": [
                    {
                        **asdict(event),
                        "tags": list(event.tags),
                        "data": dict(event.data),
                        "impact": dict(event.impact or {}),
                    }
                    for event in state.history.events
                ]
            },
            "milestones": {
                "chapter": asdict(state.milestones.chapter),
                "last_chapter_change_tick": state.milestones._last_chapter_change_tick,
            },
            "enemies": [asdict(enemy) for enemy in state.enemies],
        },
    }
    _atomic_write_json(save_path, payload)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _as_int(value: Any) -> int:
    return int(value)


def _as_float(value: Any) -> float:
    return float(value)


def _require_dict(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Expected object for {key}")
    return value


def _require_list(mapping: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = mapping.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Expected list for {key}")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Expected objects in list for {key}")
    return value


def _grid_from_json(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        raise ValueError("Expected grid rows")
    return [[_as_float(cell) for cell in row] for row in value if isinstance(row, list)]


def _dict_with_json_scalars(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[str(key)] = item
    return result
