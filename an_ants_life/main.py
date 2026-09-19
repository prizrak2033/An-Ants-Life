"""
An Ant's Life - Main simulation entry point.

This is an ant colony simulation game inspired by SimAnt, featuring:
- Worker, Scout, and Soldier ants with different behaviors
- Pheromone-based pathfinding
- Territory control mechanics
- Enemy red ants and combat
- Food gathering and colony management
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import SimConfig
from .persistence import (
    DEFAULT_PROFILE,
    DEFAULT_SAVE_DIR,
    list_save_profiles,
    load_game,
    resolve_save_path,
    save_game,
)
from .state import GameState
from .systems.combat import update_combat
from .systems.emergencies import update_emergencies
from .systems.enemies import update_enemies
from .systems.objectives import update_objectives
from .systems.stress import update_stress
from .systems.time import Timekeeper
from .ui.debug import build_debug_dump
from .ui.hud import build_hud_lines

LOGGER = logging.getLogger("an_ants_life")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run An Ant's Life.")
    parser.add_argument(
        "--save-file",
        type=Path,
        default=None,
        help="Explicit JSON save file used to resume the colony between runs.",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=DEFAULT_SAVE_DIR,
        help="Directory containing named save profiles.",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Named save profile to load from the save directory.",
    )
    parser.add_argument(
        "--autosave-ticks",
        type=int,
        default=300,
        help="Ticks between automatic saves; use 0 to disable autosave.",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="Optional tick limit for smoke tests or short runs.",
    )
    parser.add_argument(
        "--new-game",
        action="store_true",
        help="Ignore any existing save file and start a fresh colony.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
        help="Controls console verbosity for HUD, debug output, and lifecycle messages.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List discovered named save profiles and exit.",
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(message)s")


def _maybe_autosave(
    state: GameState,
    save_path: Path,
    autosave_ticks: int,
    *,
    profile: str | None = None,
) -> None:
    if autosave_ticks > 0 and state.tick % autosave_ticks == 0:
        save_game(state, save_path, profile=profile)


def advance_simulation(
    state: GameState,
    dt: float,
    save_path: Path,
    autosave_ticks: int,
    *,
    profile: str | None = None,
) -> None:
    state.t += dt
    state.tick += 1

    update_enemies(state, dt)
    state.territory.update(state)
    state.pheromones.decay_and_diffuse(dt)

    for ant in state.colony.ants:
        ant.update(state, dt)

    update_combat(state, dt)
    update_objectives(state, dt)
    update_stress(state, dt)
    update_emergencies(state, dt)
    state.milestones.update(state)

    if state.tick % state.cfg.HUD_EVERY_TICKS == 0:
        for line in build_hud_lines(state):
            LOGGER.info(line)

    debug_dump = build_debug_dump(state, every_ticks=state.cfg.DEBUG_EVERY_TICKS)
    if debug_dump:
        LOGGER.debug(debug_dump)

    _maybe_autosave(state, save_path, autosave_ticks, profile=profile)


def get_stop_message(state: GameState, max_ticks: int | None) -> str | None:
    if state.colony.queen.hp <= 0:
        return "💀 GAME OVER: Queen eliminated."
    if max_ticks is not None and state.tick >= max_ticks:
        return f"⏸️ Paused after {state.tick} ticks."
    return None


def run(
    *,
    save_path: Path,
    autosave_ticks: int = 300,
    max_ticks: int | None = None,
    new_game: bool = False,
    log_level: str = "INFO",
    profile: str | None = None,
) -> None:
    """Main game loop - runs the ant colony simulation."""
    configure_logging(log_level)
    cfg = SimConfig()
    if new_game:
        state = GameState(cfg)
    else:
        try:
            state = load_game(save_path, cfg)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning("⚠️ Could not load save from %s: %s. Starting a new colony.", save_path, exc)
            state = GameState(cfg)
    clock = Timekeeper(cfg)

    try:
        while True:
            dt = clock.step()
            advance_simulation(state, dt, save_path, autosave_ticks, profile=profile)
            stop_message = get_stop_message(state, max_ticks)
            if stop_message is not None:
                LOGGER.warning(stop_message)
                break
    except KeyboardInterrupt:
        LOGGER.warning("⏸️ Simulation interrupted. Saving colony state...")
    finally:
        save_game(state, save_path, profile=profile)


def main() -> None:
    args = _parse_args()
    configure_logging(args.log_level)
    if args.list_profiles:
        profiles = list_save_profiles(args.save_dir)
        if not profiles:
            LOGGER.warning("No save profiles found in %s", args.save_dir)
            return
        for profile in profiles:
            summary = profile["summary"]
            LOGGER.warning(
                "%s: tick=%s food=%.1f queen=%s/%s ants=%s enemies=%s chapter=%s",
                profile["profile"],
                summary.get("tick", 0),
                float(summary.get("food_store", 0.0)),
                summary.get("queen_hp", 0),
                summary.get("queen_hp_max", 0),
                _total_ants_from_summary(summary),
                summary.get("enemy_count", 0),
                summary.get("chapter") or "-",
            )
        return

    resolved_save_path = resolve_save_path(args.save_file, profile=args.profile, save_dir=args.save_dir)
    run(
        save_path=resolved_save_path,
        autosave_ticks=args.autosave_ticks,
        max_ticks=args.max_ticks,
        new_game=args.new_game,
        log_level=args.log_level,
        profile=args.profile if args.save_file is None else None,
    )


def _total_ants_from_summary(summary: dict) -> int:
    ants = summary.get("ants", {})
    if isinstance(ants, dict):
        return int(ants.get("total", 0))
    return 0


if __name__ == "__main__":
    main()
