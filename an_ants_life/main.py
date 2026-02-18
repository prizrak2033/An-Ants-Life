from config import SimConfig
from state import GameState

from systems.time import Timekeeper
from systems.enemies import update_enemies
from systems.combat import update_combat
from systems.objectives import update_objectives
from systems.stress import update_stress
from systems.emergencies import update_emergencies

from ui.hud import render_hud
from ui.debug import debug_dump


def run():
    cfg = SimConfig()
    state = GameState(cfg)
    clock = Timekeeper(cfg)

    while True:
        dt = clock.step()
        state.t += dt
        state.tick += 1

        # 1) Spawn/move enemies
        update_enemies(state, dt)

        # 2) Territory (now driven by enemies + ants)
        state.territory.update(state)

        # 3) Pheromones
        state.pheromones.decay_and_diffuse(dt)

        # 4) Ant updates (movement + foraging)
        for ant in list(state.colony.ants):
            ant.update(state, dt)

        # 5) Combat resolution (time-based, HP-based, soldiers intercept)
        update_combat(state, dt)

        # 6) Objectives (claim food sites → benefits, history)
        update_objectives(state, dt)

        # 7) Colony systems
        update_stress(state, dt)
        update_emergencies(state, dt)

        # 8) Chapters
        state.milestones.update(state)

        # 9) HUD/debug
        if state.tick % cfg.HUD_EVERY_TICKS == 0:
            render_hud(state)

        debug_dump(state, every_ticks=cfg.DEBUG_EVERY_TICKS)

        # End condition
        if state.colony.queen.hp <= 0:
            print("\n💀 GAME OVER: Queen eliminated.")
            break


if __name__ == "__main__":
    run()
