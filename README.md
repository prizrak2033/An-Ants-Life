# An-Ants-Life
An Ant's Life An Ant's Life is an ambitious and evolving video game project inspired by the classic 1990s title SimAnt. Initially conceived as a simple simulation to address the notorious stuttering issues that plagued the original game.

## Run

Run the simulation as a package from the repository root:

```bash
python -m an_ants_life
```

Useful options:

- `--new-game` starts a fresh colony and ignores any existing save.
- `--save-file /path/to/save.json` changes the save location.
- `--autosave-ticks 300` controls autosave frequency.
- `--max-ticks 500` runs a bounded simulation for smoke tests.
- `--log-level WARNING` suppresses routine HUD output.

The game now persists colony progress to `.an_ants_life_save.json` by default.
