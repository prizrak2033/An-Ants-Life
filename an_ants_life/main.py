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
from .ui.debug import debug_dump
from .ui.hud import render_hud


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
    return parser.parse_args()


def _maybe_autosave(state: GameState, save_path: Path, autosave_ticks: int) -> None:
    if autosave_ticks > 0 and state.tick % autosave_ticks == 0:
        save_game(state, save_path)


def run(
    *,
    save_path: Path = DEFAULT_SAVE_FILE,
    autosave_ticks: int = 300,
    max_ticks: int | None = None,
    new_game: bool = False,
) -> None:
    """Main game loop - runs the ant colony simulation."""
    cfg = SimConfig()
    state = GameState(cfg) if new_game else load_game(save_path, cfg)
    clock = Timekeeper(cfg)

    try:
        while True:
            dt = clock.step()
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

            if state.tick % cfg.HUD_EVERY_TICKS == 0:
                render_hud(state)

            debug_dump(state, every_ticks=cfg.DEBUG_EVERY_TICKS)
            _maybe_autosave(state, save_path, autosave_ticks)

            if state.colony.queen.hp <= 0:
                print("\n💀 GAME OVER: Queen eliminated.")
                break
            if max_ticks is not None and state.tick >= max_ticks:
                print(f"\n⏸️ Paused after {state.tick} ticks.")
                break
    except KeyboardInterrupt:
        print("\n⏸️ Simulation interrupted. Saving colony state...")
    finally:
        save_game(state, save_path)


if __name__ == "__main__":
    args = _parse_args()
    run(
        save_path=args.save_file,
        autosave_ticks=args.autosave_ticks,
        max_ticks=args.max_ticks,
        new_game=args.new_game,
    )
