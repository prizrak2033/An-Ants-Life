# An Ant's Life

An ant colony simulation inspired by the 1990s SimAnt — a colony you steer
rather than command, where foraging, defence and expansion emerge from
individual ants following simple local rules.

Ants do not path-find. They lay and follow pheromone trails, and the routes
between the nest and the food are a consequence of that, not a plan. Most of
the interesting behaviour in the game falls out of this one property.

## Running it

The web UI is the real interface:

```bash
cd an_ants_life
python3 server.py 8801          # then open http://127.0.0.1:8801
```

There is also a terminal mode that prints a HUD and, when the colony's story
ends, its saga:

```bash
cd an_ants_life
python3 main.py
```

No dependencies beyond the standard library. Python 3.9+.

### Running the tests

```bash
cd an_ants_life
python3 -m unittest discover -s tests -t .            # fast tier, ~2 min
ANTS_SLOW=1 python3 -m unittest discover -s tests -t .  # + full 300s/900s baselines
```

Standard library only, like the rest of the project. The audio suite starts
its own server and drives a real browser; it skips itself when playwright or
Chromium is unavailable. `tests/harness.py` is the measurement tool the
balance work runs on — use it for any tuning change rather than reasoning
about the config.

All tuning lives in `an_ants_life/config.py` as a single frozen `SimConfig`
dataclass — world size, ant speeds, combat, enemy pressure, growth targets,
directive limits, the audio mix. Changing the game is editing that file.

## What's in it

Legend: **✅ verified by measurement** · **◐ built and working, not
independently verified** · **○ not built**

### Simulation core
- ✅ Pheromone stigmergy — laden ants lay a `food` trail home; searchers follow
  the gradient outward. Getting this invariant right took foraging from 0.34×
  to 13.3× its broken throughput. The grid's blur was separately found to be
  destroying the scent it shed toward empty cells, so trails evaporated ~24×
  faster than configured; retention now matches `FOOD_PHERO_DECAY_PER_SEC`.
- ✅ Correlated random-walk exploration (not memoryless — measured materially
  better ground coverage).
- ✅ Worker / scout / soldier / praetorian castes with distinct AI.
- ✅ Framerate-independent rates — food respawn, enemy spawns, pheromone
  diffusion and the whole territory model are per second, so they hold across
  a 15–120fps range rather than drifting with tick count. Twelve tick-based
  *durations* still remain; see Known gaps.

### Colony and growth
- ✅ Queen-driven births as the only source of replenishment.
- ✅ Caste targets that shift under threat (soldier fraction 0.26 → 0.36).
- ✅ Carrying-capacity signal split into food-balance flow and a world-regen
  ceiling. The first version was circular — derived from measured income, so
  throttling lowered its own estimate.
- ✅ Stress and famine emergency regimes with worker reassignment.

### World
- ✅ Five terrain types across biomes. Rock is *cost* terrain, not a wall —
  making it impassable jammed 69.6% of ants against geometry.
- ✅ Sliding collision with committed-side deflection.
- ✅ Territory control grid with border pressure.
- ✅ Food sources that deplete and respawn.

### Enemies and combat
- ✅ Three enemy types with genuinely different behaviour, not just different
  stats: warriors engage, raiders steal and flee, predators hunt.
- ✅ Raid loot recovery — soldiers break off to chase laden raiders. This went
  from 0% recovered to 66% intercepted.
- ✅ Enemy pressure curve tuned against the current baseline.

### Player agency
- ✅ Directives placed on the map: forage, defend, explore.
- ✅ Capped, distance-weighted recruitment — only idle ants answer, and no
  more than `DIRECTIVE_RECRUIT_CAP`. Deliberately writes no pheromone, so a
  mark cannot become a self-reinforcing trail.
- ✅ Guaranteed nest garrison floor. Without it the defend directive drained
  the nest and the queen died with zero defenders — which is how *every*
  measured colony death happens.
- ✅ Praetorian guard caste, promoted from soldiers, leashed to the queen.
  Validated as a strategic unlock (4/12 → 8/12 survival for a forward-army
  playstyle) rather than a flat stat bonus — it is neutral when playing at
  home, which is the point.
- ✅ Recall / rally, standing orders, policy sliders.
- ◐ Layer toggles and presets for the map overlays.

### Narrative
- ✅ Significance-filtered event log (82% of raw events are routine churn).
- ✅ Bounded history ring with O(1) recency lookup — was O(n) over an
  unbounded log, called several times per tick.
- ◐ Declarative scored chapters with hysteresis to stop churn (17 chapters in
  600s before `CHAPTER_MIN_TICKS`, some lasting 0–3s).
- ◐ Prose narration, milestones, endings, and a persistent saga.

### Persistence
- ✅ Resumable saves with atomic writes (temp file + rename).
- ✅ RNG state serialized, so a resumed run is deterministic.
- ✅ Archive of finished colonies.
- ✅ Autosave every 30s.

### Audio
- ✅ Fully procedural — no asset files. Ambient bed (drone that thickens with
  population, threat throb, income-driven chitter) plus 20 event voices, all
  gated by the same significance filter the chronicle uses.
- ✅ All 20 voices measured within 0.79–1.17× of their designed level; none
  silent, none clipping; six stacked voices stay under full scale without
  altering a single voice.
- ✅ Mix published from `config.py` via `/audio-config`, with matching
  in-page fallbacks.
- ◐ **Aesthetic balance is unverified — nobody has actually listened to it.**
  Every level was tuned by offline measurement. Levels that measure correctly
  can still sound wrong together.

## Current baseline

Measured on the current build, 12 seeds, headless with fixed `dt`
(`ANTS_SLOW=1 python3 -m unittest discover -s tests -t .`):

| | 300s | 900s |
|---|---|---|
| survived | 12/12 | 10/12 |
| deposits/sec | 1.501 | 1.089 |
| food ratio (deposits ÷ upkeep) | 2.10× | 1.94× |
| time in famine | 0.0% | 0.0% |
| raid loot intercepted | 66% | 64% |
| median end population | 45 | 22 |

**The economy is the thing that sets colony size, and it is arithmetic.**
Replacement births come out of the same budget as upkeep, so the standing
population the world can hold is

```
P = (regen − GROWTH_EGG_FOOD_COST × loss_rate) / FOOD_UPKEEP_PER_ANT_PER_SEC
    where regen = FOOD_PER_SOURCE / FOOD_SOURCE_RESPAWN_SECONDS
```

That formula tracks measured outcomes closely — a 38s respawn predicts 13.5
against an observed 15, 30s predicts 28 against 27, 24s predicts 44 against
43 — so use it rather than guessing when changing how big a colony the world
supports. Retune the respawn interval, not the ants.

**Long-run decay is improved, not solved.** At 900s the colony now survives
10 runs in 12 (was 8) and ends at a median of 22 ants (was 11), with famine
gone entirely. But it still peaks near 56 and falls to 22, and losses still
outrun births 1078 to 934. The remaining gap is not food supply: it is that
combat casualties consume a large share of the food budget as replacement
births. Closing it means spending less on casualties, not printing more food.

## Known gaps

1. **Attrition still outruns births over long runs.** Losses exceed births
   1078 to 934 across twelve 900s runs, so population slides from 56 to 22
   and two colonies still die. Food is not the constraint — famine is 0% and
   the ratio holds near 1.9×. The levers are casualty rate and
   `GROWTH_EGG_FOOD_COST`, not regen.
2. **Twelve tick-based durations remain.** Combat cooldown, birth spacing,
   chapter windows and the emergency-raid timers are all counted in ticks, so
   they stretch when the frame rate dips toward `MAX_DT` while the rate-based
   systems beside them hold steady. The rates have been converted; these
   durations are a larger retune.
3. **Sound has never been heard.** Every level was tuned by offline
   measurement in a container with no audio device.
4. **Visual readability is unconfirmed.** Overlays once hid the ants entirely;
   toggles, presets and larger outlined ants were added in response, but the
   result has not been confirmed by eye.
5. **No CI.** The suite exists and passes but nothing runs it automatically.

## Where things live

```
an_ants_life/
  config.py         all tuning, one frozen dataclass
  state.py          GameState; owns the world and steps it
  main.py           terminal entry point
  server.py         HTTP server, snapshot builder, command queue
  ants/             ant model, roles, intents, AI (ai.py is the brain)
  colony/           colony state, growth policy, directives, history,
                    narrator, milestones, naming
  enemies/          enemy kinds and behaviour
  systems/          per-tick systems: combat, enemies, growth, stress,
                    emergencies, directives, objectives, time
  world/            map, terrain, pheromones, territory, food
  ui/               terminal HUD, chronicle, debug dumps
  persistence/      save codec and store
  tests/            harness.py plus the simulation, persistence and
                    audio suites - see "Running the tests"
  web/              index.html, app.js (canvas frontend), audio.js
```

The simulation runs on its own thread; player input arrives on HTTP threads
and is queued, then drained at a tick boundary, so an action lands wholly
within one tick or not at all.

## A note on how this was built

Nearly every balance decision here was made by measuring, not by intuition —
and several strongly-held guesses turned out to be wrong under measurement.
Rock terrain was made *more* passable, not less, because smaller obstacles
made jamming worse. The starting caste mix was a trap that halved survival.
The carrying-capacity metric had to be rebuilt because it was circular. When
changing tuning, prefer a control run over a plausible story.
