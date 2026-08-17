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

All tuning lives in `an_ants_life/config.py` as a single frozen `SimConfig`
dataclass — world size, ant speeds, combat, enemy pressure, growth targets,
directive limits, the audio mix. Changing the game is editing that file.

## What's in it

Legend: **✅ verified by measurement** · **◐ built and working, not
independently verified** · **○ not built**

### Simulation core
- ✅ Pheromone stigmergy — laden ants lay a `food` trail home; searchers follow
  the gradient outward. Getting this invariant right took foraging from 0.34×
  to 13.3× its broken throughput.
- ✅ Correlated random-walk exploration (not memoryless — measured materially
  better ground coverage).
- ✅ Worker / scout / soldier / praetorian castes with distinct AI.
- ✅ Framerate-independent stepping — food respawn is time-based, not
  per-tick probability.

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
  from 0% recovered to 55% intercepted.
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

Measured on the current build, 12 seeds, headless with fixed `dt`:

| | 300s | 900s |
|---|---|---|
| survived | 12/12 | 8/12 |
| deposits/sec | 1.424 | 0.995 |
| food ratio (deposits ÷ upkeep) | 2.04× | 1.92× |
| time in famine | 0.8% | 1.6% |
| raid loot intercepted | 55% | 58% |
| median end population | 42 | 11 |

**The colony is tuned for the first five minutes and decays after that.**
At 300s every colony survives comfortably, peaking near 50 ants and settling
at 30–58. At 900s four colonies die outright (at 403s, 709s, 741s and 774s),
and five of the eight survivors end with fewer than ten ants. Median
population falls from a peak of 52 to 11 — a 79% decline — so only about
three runs in twelve are genuinely healthy at the fifteen-minute mark.

This is the clearest open gameplay problem. It is not starvation: the food
ratio stays comfortably above 1.0 throughout, and famine accounts for 1.6% of
elapsed time. Attrition is outrunning the queen's birth rate.

## Known gaps

1. **The verification scripts are not in the repo.** The balance harness, the
   persistence tests and the four audio suites were written in a scratchpad
   directory and do not survive the session. This is the single biggest hole:
   almost every number above came from a script that no longer exists.
2. **Long-run decay.** See the baseline above — the colony holds for five
   minutes and hollows out by fifteen. Attrition outruns births while food
   stays adequate, which points at the growth rate or the enemy pressure
   curve rather than the economy. This is the next real balance problem.
3. **Sound has never been heard.** See above.
4. **Visual readability is unconfirmed.** Overlays once hid the ants entirely;
   toggles, presets and larger outlined ants were added in response, but the
   result has not been confirmed by eye.
5. No tests run in CI, because there are no committed tests.

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
