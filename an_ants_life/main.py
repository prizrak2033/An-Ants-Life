"""
An Ant's Life - Main simulation entry point.

This is an ant colony simulation game inspired by SimAnt, featuring:
- Worker, Scout, and Soldier ants with different behaviors
- Pheromone-based pathfinding
- Territory control mechanics
- Enemy red ants and combat
- Food gathering and colony management
"""

from config import SimConfig
from state import GameState

from systems.time import Timekeeper

from ui.hud import render_hud
from ui.debug import debug_dump


def run() -> None:
    """Main game loop - runs the ant colony simulation."""
    cfg = SimConfig()
    state = GameState(cfg)
    clock = Timekeeper(cfg)

    while True:
        dt = clock.step()
        state.step(dt)

        if state.tick % cfg.HUD_EVERY_TICKS == 0:
            render_hud(state)

        debug_dump(state, every_ticks=cfg.DEBUG_EVERY_TICKS)

        # End condition
        if state.colony.queen.hp <= 0:
            print("\n💀 GAME OVER: Queen eliminated.")
            break


if __name__ == "__main__":
    run()
