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

CI runs the fast tier on every push and pull request
(`.github/workflows/tests.yml`). The slow balance tier is opt-in: it runs on
the default branch, or on demand via workflow dispatch, since twelve 300s and
twelve 900s colonies take minutes.

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
  a 15–120fps range rather than drifting with tick count. The tick-based
  *durations* were converted too, including the stamps carried on ants,
  enemies, the history index and the save format. `HUD_EVERY_TICKS` and
  `DEBUG_EVERY_TICKS` stay in ticks on purpose: they are a render cadence.

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
  from 0% recovered to around 60% intercepted, varying with whether foragers
  flee (they chip at raiders too, so fleeing costs a few points of it).
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
- ○ Forager flee behaviour, built and measured and **shipped off**
  (`ANT_FLEE_ENABLE`). It cuts casualties 41% and loses more colonies; see
  Known gaps for the numbers and why that is not a contradiction.
- ◐ Layer toggles and presets for the map overlays.

### Narrative
- ✅ Significance-filtered event log (82% of raw events are routine churn).
- ✅ Bounded history ring with O(1) recency lookup — was O(n) over an
  unbounded log, called several times per tick.
- ◐ Declarative scored chapters with hysteresis to stop churn (17 chapters in
  600s before `CHAPTER_MIN_SECONDS`, some lasting 0–3s).
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

Measured on the shipped configuration, 12 seeds, headless with fixed `dt`
(`ANTS_SLOW=1 python3 -m unittest discover -s tests -t .`):

| | 300s | 900s |
|---|---|---|
| survived | 12/12 | 11/12 |
| deposits/sec | 1.542 | 1.224 |
| food ratio (deposits / upkeep) | 2.03x | 1.99x |
| time in famine | 0.9% | 2.4% |
| raid loot intercepted | 56% | 64% |
| median peak -> end population | 59 -> 46 | 59 -> 34 |
| end population, full range (middle half) | 30-59 (38-55) | 10-47 (12-38) |
| births / losses | 382 / 215 | 1057 / 1087 |

**Read the last row before the one above it.** At 900s the median colony
ends at 34 ants, and a quarter of them end at 12 or fewer. The median is
the least interesting number in that column: the spread is the finding.
A fifteen-minute colony is not reliably anything, and any change measured
against the median alone is being read off the narrowest part of a very
wide distribution.

### Read these numbers with the right confidence

**Twelve seeds cannot separate differences of a few runs, and the medians
move more than they look like they should.** The same configuration, on the
same twelve seeds, measured a median end population of 22 in one run and 34
in another. Nothing between those two runs should have changed 30fps
behaviour - the tick-to-seconds conversions were built to be neutral - but
they are not *bit*-identical (`0.3333` is not `10/30`, and the chapter
sampler moved from `tick % 30` to elapsed time). A one-tick difference early
in a 27,000-tick run is enough for a chaotic system to finish somewhere
completely different.

So read a survival count of 10/12 against 11/12 as a tie, and a median
population of 34 against 42 as suggestive rather than settled. What is
trustworthy is what reproduced across separate runs: the carrying-capacity
formula below did, and so did the direction of the births-versus-losses
balance. `tests/harness.py` reports medians with no dispersion, which is what
made these differences look firmer than they were - adding a spread or a
survival interval is worth doing before the next tuning decision leans on it.

### The economy sets colony size, and it is arithmetic

Replacement births come out of the same budget as upkeep, so the standing
population the world can hold is

```
P = (regen - GROWTH_EGG_FOOD_COST * loss_rate) / FOOD_UPKEEP_PER_ANT_PER_SEC
    where regen = FOOD_PER_SOURCE / FOOD_SOURCE_RESPAWN_SECONDS
```

This is the one relationship that has reproduced across separate runs: a 38s
respawn predicts 13.5 against an observed 15, 30s predicts 28 against 27, and
24s predicts 44 against 43. Use it rather than guessing, and retune the
respawn interval rather than the ants.

### Long-run decay: improved, not closed

The collapse is gone - one run in twelve dies at 900s now, against four
before the economy was retuned - but the colony still peaks near 60 and
falls away, and births and losses are running level (1057 against 1087)
rather than ahead. The wide end-population spread above is the same story
told a second way: some colonies hold in the forties, others are down to
a dozen ants, and the difference is not yet something the player controls.

## Known gaps

1. **Attrition is the binding constraint, and the flee experiment showed
   why it is hard.** Foragers were 62% of all casualties, in fights they
   cannot win, so they were given a flee behaviour (`ANT_FLEE_ENABLE`,
   default **off**). Over 32 paired seeds at 900s it did everything it was
   designed to do: casualties fell 41% (−37.6 per run, 95% CI [−44.3,
   −30.2]), standing population rose about ten ants (+9.9, CI [+4.6,
   +15.6]), food throughput unchanged. Survival went 29/32 → 23/32, on a
   paired split of 7 seeds where enabling it killed a colony that
   otherwise lived against 1 the other way (p=0.07 — short of the usual
   bar, but lopsided and matching an earlier twelve-seed run).

   The trade is the finding: a colony that is bigger, better fed and
   losing fewer ants dies *more often*, because the deaths that end the
   game happen at the queen's chamber and those are exactly the ones the
   mechanic stops paying for. Any future work on attrition has to keep
   nest defence intact, or carry it with something other than workers
   throwing themselves at warriors — and if it does, the economic half of
   this is measured, real, and one flag away.

2. **Food is not the constraint.** Famine is under 1% and the ratio holds
   above 1.6x. The levers are the casualty rate and `GROWTH_EGG_FOOD_COST`,
   not regen.
3. **Sound has never been heard.** Every level was tuned by offline
   measurement in a container with no audio device.
4. **The visuals have had one pass, not a verdict.** Ants are drawn as
   oriented bodies, the field layers are smooth rather than tiled, and the
   palette is warm; that was checked against screenshots at each step. Nobody
   has actually played it, so readability in motion is still unconfirmed.

## Where things live

```
.github/workflows/  CI: fast tier per push, balance tier on demand
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
