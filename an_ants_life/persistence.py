from __future__ import annotations

import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable

from .ants.ant import Ant
from .ants.roles import Role
from .colony.colony_state import Queen
from .colony.history import HistoryEvent, HistoryLog
from .colony.milestones import ChapterState
from .enemies.red_ant import RedAnt
from .state import GameState
from .world.food import FoodSource

DEFAULT_SAVE_DIR = Path(".an_ants_life_saves")
DEFAULT_PROFILE = "default"
SAVE_VERSION = 3


def resolve_save_path(
    save_path: Path | None = None,
    *,
    profile: str = DEFAULT_PROFILE,
    save_dir: Path = DEFAULT_SAVE_DIR,
) -> Path:
    if save_path is not None:
        return save_path
    return save_dir / f"{normalize_profile_name(profile)}.json"


def normalize_profile_name(profile: str) -> str:
    candidate = profile.strip()
    if not candidate:
        raise ValueError("Profile name cannot be empty")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if any(ch not in allowed for ch in candidate):
        raise ValueError("Profile names may only contain letters, numbers, underscores, and hyphens")
    return candidate


def list_save_profiles(save_dir: Path = DEFAULT_SAVE_DIR) -> list[dict[str, Any]]:
    if not save_dir.exists():
        return []

    profiles: list[dict[str, Any]] = []
    for save_file in sorted(save_dir.glob("*.json")):
        try:
            with save_file.open("r", encoding="utf-8") as handle:
                payload = _migrate_payload(json.load(handle))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        meta = _require_dict(payload, "meta")
        summary = _require_dict(payload, "summary")
        profiles.append(
            {
                "profile": str(meta.get("profile") or save_file.stem),
                "path": save_file,
                "summary": summary,
                "version": payload["version"],
            }
        )
    return profiles


def load_game(save_path: Path, cfg) -> GameState:
    if not save_path.exists():
        return GameState(cfg)

    with save_path.open("r", encoding="utf-8") as handle:
        payload = _migrate_payload(json.load(handle))

    data = _require_dict(payload, "state")
    state = GameState(cfg)
    state.t = _as_float(data.get("t", 0.0))
    state.tick = max(0, _as_int(data.get("tick", 0)))
    state._next_enemy_id = max(1, _as_int(data.get("_next_enemy_id", 1)))

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
    for channel, grid in _require_dict(pheromones, "grids").items():
        if channel in state.pheromones.grids:
            state.pheromones.grids[channel] = _merge_grid(grid, state.pheromones.grids[channel])

    territory = _require_dict(data, "territory")
    state.territory.grid = _merge_grid(territory.get("grid", state.territory.grid), state.territory.grid)
    state.territory._last_border_incident_tick = _as_int(territory.get("last_border_incident_tick", -10_000))
    state.territory._last_expansion_tick = _as_int(territory.get("last_expansion_tick", -10_000))

    colony = _require_dict(data, "colony")
    state.colony.food_store = max(0.0, _as_float(colony.get("food_store", state.colony.food_store)))
    state.colony.stress = min(1.0, max(0.0, _as_float(colony.get("stress", state.colony.stress))))

    queen = _require_dict(colony, "queen")
    state.colony.queen = Queen(
        x=_clamp_position(_as_float(queen.get("x", cfg.NEST_X)), cfg.WORLD_W),
        y=_clamp_position(_as_float(queen.get("y", cfg.NEST_Y)), cfg.WORLD_H),
        hp=max(0, _as_int(queen.get("hp", cfg.QUEEN_HP_MAX))),
        hp_max=max(1, _as_int(queen.get("hp_max", cfg.QUEEN_HP_MAX))),
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
            x=_clamp_position(_as_float(item.get("x")), cfg.WORLD_W),
            y=_clamp_position(_as_float(item.get("y")), cfg.WORLD_H),
            vx=_as_float(item.get("vx", 0.0)),
            vy=_as_float(item.get("vy", 0.0)),
            carrying=max(0.0, _as_float(item.get("carrying", 0.0))),
            hp=max(0, _as_int(item.get("hp", cfg.ANT_HP_MAX))),
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
        ],
        max_events=cfg.HISTORY_MAX_EVENTS,
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
            x=_clamp_position(_as_float(item.get("x")), cfg.WORLD_W),
            y=_clamp_position(_as_float(item.get("y")), cfg.WORLD_H),
            hp=max(0, _as_int(item.get("hp", cfg.REDANT_HP))),
            vx=_as_float(item.get("vx", 0.0)),
            vy=_as_float(item.get("vy", 0.0)),
            last_combat_tick=_as_int(item.get("last_combat_tick", -10_000)),
        )
        for item in _require_list(data, "enemies")
    ]
    _restore_random_state(payload)
    return state


def save_game(state: GameState, save_path: Path, *, profile: str | None = None) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_save_summary(state)
    payload = {
        "version": SAVE_VERSION,
        "meta": {
            "saved_at_tick": state.tick,
            "saved_at_seconds": state.t,
            "profile": profile,
            "random_state": _jsonify_random_state(random.getstate()),
        },
        "summary": summary,
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


def build_save_summary(state: GameState) -> dict[str, Any]:
    workers = sum(1 for ant in state.colony.ants if ant.role == Role.WORKER)
    scouts = sum(1 for ant in state.colony.ants if ant.role == Role.SCOUT)
    soldiers = sum(1 for ant in state.colony.ants if ant.role == Role.SOLDIER)
    return {
        "tick": state.tick,
        "time_seconds": round(state.t, 3),
        "ants": {
            "workers": workers,
            "scouts": scouts,
            "soldiers": soldiers,
            "total": len(state.colony.ants),
        },
        "food_store": round(state.colony.food_store, 3),
        "queen_hp": state.colony.queen.hp,
        "queen_hp_max": state.colony.queen.hp_max,
        "enemy_count": len(state.enemies),
        "claimed_food_sources": sum(1 for source in state.world.food_sources if source.claimed),
        "famine_active": bool(state.colony.emergency.get("famine_active", False)),
        "chapter": state.milestones.chapter.title if state.milestones.chapter.active else None,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _migrate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Expected save payload object")

    version = payload.get("version")
    if not isinstance(version, int):
        raise ValueError(f"Unsupported save version: {version!r}")
    if version > SAVE_VERSION:
        raise ValueError(f"Unsupported save version: {version!r}")

    migrated = payload
    while version < SAVE_VERSION:
        migrator = _MIGRATIONS.get(version)
        if migrator is None:
            raise ValueError(f"Unsupported save version: {version!r}")
        migrated = migrator(migrated)
        version = migrated["version"]

    return migrated


def _migrate_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    state = _require_dict(payload, "state")
    migrated = {
        "version": 2,
        "meta": {
            "migrated_from_version": 1,
            "saved_at_tick": state.get("tick", 0),
            "saved_at_seconds": state.get("t", 0.0),
            "random_state": None,
            "profile": None,
        },
        "summary": _build_summary_from_payload_state(state),
        "state": state,
    }
    return migrated


def _migrate_v2_to_v3(payload: dict[str, Any]) -> dict[str, Any]:
    state = _require_dict(payload, "state")
    meta = dict(_require_dict(payload, "meta"))
    meta.setdefault("profile", None)
    meta["migrated_from_version"] = payload.get("version", 2)
    return {
        "version": 3,
        "meta": meta,
        "summary": _build_summary_from_payload_state(state),
        "state": state,
    }


_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
}


def _restore_random_state(payload: dict[str, Any]) -> None:
    meta = _require_dict(payload, "meta")
    random_state = meta.get("random_state")
    if random_state is None:
        return
    random.setstate(_tupleify_random_state(random_state))


def _as_int(value: Any) -> int:
    return int(value)


def _as_float(value: Any) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("Expected finite numeric value")
    return converted


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


def _merge_grid(value: Any, fallback: list[list[float]]) -> list[list[float]]:
    if not isinstance(value, list):
        return fallback
    merged = [row[:] for row in fallback]
    for cx, row in enumerate(value[: len(merged)]):
        if not isinstance(row, list):
            continue
        for cy, cell in enumerate(row[: len(merged[cx])]):
            merged[cx][cy] = _as_float(cell)
    return merged


def _dict_with_json_scalars(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[str(key)] = item
    return result


def _clamp_position(value: float, upper_bound: float) -> float:
    return max(0.0, min(upper_bound, value))


def _build_summary_from_payload_state(state: dict[str, Any]) -> dict[str, Any]:
    colony = _require_dict(state, "colony")
    ants = _require_list(colony, "ants")
    roles = [item.get("role", Role.WORKER.value) for item in ants]
    milestones = _require_dict(state, "milestones")
    chapter = _require_dict(milestones, "chapter")
    world = _require_dict(state, "world")
    food_sources = _require_list(world, "food_sources")
    famine_active = bool(_require_dict(colony, "emergency").get("famine_active", False))
    return {
        "tick": max(0, _as_int(state.get("tick", 0))),
        "time_seconds": round(_as_float(state.get("t", 0.0)), 3),
        "ants": {
            "workers": sum(1 for role in roles if role == Role.WORKER.value),
            "scouts": sum(1 for role in roles if role == Role.SCOUT.value),
            "soldiers": sum(1 for role in roles if role == Role.SOLDIER.value),
            "total": len(ants),
        },
        "food_store": round(max(0.0, _as_float(colony.get("food_store", 0.0))), 3),
        "queen_hp": max(0, _as_int(_require_dict(colony, "queen").get("hp", 0))),
        "queen_hp_max": max(1, _as_int(_require_dict(colony, "queen").get("hp_max", 1))),
        "enemy_count": len(_require_list(state, "enemies")),
        "claimed_food_sources": sum(1 for source in food_sources if bool(source.get("claimed", False))),
        "famine_active": famine_active,
        "chapter": str(chapter.get("title")) if chapter.get("active") else None,
    }


def _jsonify_random_state(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonify_random_state(item) for item in value]
    if isinstance(value, list):
        return [_jsonify_random_state(item) for item in value]
    return value


def _tupleify_random_state(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tupleify_random_state(item) for item in value)
    return value
