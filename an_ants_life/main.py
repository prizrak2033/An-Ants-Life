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
from .persistence import DEFAULT_SAVE_FILE, load_game, save_game
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
        default=DEFAULT_SAVE_FILE,
        help="JSON save file used to resume the colony between runs.",
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
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(message)s")


def _maybe_autosave(state: GameState, save_path: Path, autosave_ticks: int) -> None:
    if autosave_ticks > 0 and state.tick % autosave_ticks == 0:
        save_game(state, save_path)


def advance_simulation(state: GameState, dt: float, save_path: Path, autosave_ticks: int) -> None:
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

    _maybe_autosave(state, save_path, autosave_ticks)


def get_stop_message(state: GameState, max_ticks: int | None) -> str | None:
    if state.colony.queen.hp <= 0:
        return "💀 GAME OVER: Queen eliminated."
    if max_ticks is not None and state.tick >= max_ticks:
        return f"⏸️ Paused after {state.tick} ticks."
    return None


def run(
    *,
    save_path: Path = DEFAULT_SAVE_FILE,
    autosave_ticks: int = 300,
    max_ticks: int | None = None,
    new_game: bool = False,
    log_level: str = "INFO",
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
            advance_simulation(state, dt, save_path, autosave_ticks)
            stop_message = get_stop_message(state, max_ticks)
            if stop_message is not None:
                LOGGER.warning(stop_message)
                break
    except KeyboardInterrupt:
        LOGGER.warning("⏸️ Simulation interrupted. Saving colony state...")
    finally:
        save_game(state, save_path)


if __name__ == "__main__":
    args = _parse_args()
    run(
        save_path=args.save_file,
        autosave_ticks=args.autosave_ticks,
        max_ticks=args.max_ticks,
        new_game=args.new_game,
        log_level=args.log_level,
    )
