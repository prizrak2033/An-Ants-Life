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

from colony.history import EventKind
from colony.milestones import ChapterRecord
from systems.time import Timekeeper

from ui.hud import render_hud
from ui.debug import debug_dump


def _ending_text(state) -> str:
    for ev in reversed(state.history.saga):
        if ev.kind == EventKind.ENDING:
            return ev.data.get("text", "The colony's story ends.")
    return "The colony's story ends."


def _print_saga(state) -> None:
    """The colony's story, once it has one to tell."""
    tracker = state.milestones
    print(f"\n  Survived {state.t:.0f}s · {len(state.colony.ants)} ants at the end")

    if tracker.milestones:
        print("\n  Milestones")
        for m in tracker.milestones:
            print(f"    [{m['t']:6.0f}s] {m['title']} — {m['text']}")

    chapters = list(tracker.past_chapters)
    if tracker.chapter.active:
        chapters.append(ChapterRecord(tracker.chapter.title, tracker.chapter.started_t, state.t))
    if chapters:
        print("\n  Chapters")
        for c in chapters:
            print(f"    [{c.started_t:6.0f}s] {c.title} ({c.duration:.0f}s)")


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

        # End condition. The milestone tracker owns which endings exist and
        # narrates them, so the loop just reports what it decided.
        if state.ending is not None:
            render_hud(state)
            print(f"\n💀 {_ending_text(state)}")
            _print_saga(state)
            break


if __name__ == "__main__":
    run()
