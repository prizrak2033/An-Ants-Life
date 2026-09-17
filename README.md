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
about the config. `tests/bots.py` adds two scripted players for measuring
whether a change makes *playing* matter; both are held to what the interface
shows and to `server.apply_player_action`, so a result from them is a
statement about a person rather than about an oracle.

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
  the nest and the queen died with zero defenders, which was then how every
  measured colony death happened. It is not any more — see Known gaps — but
  the floor is part of why.
- ✅ Praetorian guard caste, promoted from soldiers, leashed to the queen.
  Validated as a strategic unlock (4/12 → 8/12 survival for a forward-army
  playstyle) rather than a flat stat bonus — it is neutral when playing at
  home, which is the point.
- ✅ Recall / rally, standing orders, policy sliders.
- ✅ **Works** — spending food on a permanent rule change rather than on
  redirecting ants. Nursery (55 food, every egg 34% cheaper, forever) and
  rampart (55 food, intruders at 0.55x within 20 of the nest). The first
  player action measured to beat doing nothing; the second measured to do
  nothing at all. See Known gaps 2.
- ○ Forager flee behaviour, built and measured and **shipped off**
  (`ANT_FLEE_ENABLE`). It cuts casualties 41% and lost more colonies over 32
  paired seeds (29/32 -> 23/32, p=0.07). Kept behind the flag: the economic
  half is real and measured.
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

1. **The colony is too good at running itself, and that is why playing it
   does not pay.** Three paired experiments, each one built to rule out the
   explanation the last one suggested. Two scripted players
   (`tests/bots.py`), one watching and one playing, over the same seeds:

   ```
   shipped difficulty, 24 seeds     22/24 -> 24/24    2 disagreements  p=0.50
   harder  difficulty, 40 seeds     27/40 -> 27/40   16, exact 8-8     p=1.00
   assaults + warning, 40 seeds     30/40 -> 27/40   13, split 8-5     p=0.58
   ```

   The first was unfalsifiable and should not have been reported as a
   finding: at 92% passive survival there were two discordant pairs, and
   McNemar counts nothing else, so it could not have returned significance
   however well the attentive arm played. The second was properly powered
   and split exactly evenly. The third came after building a real siege for
   the player to answer — see the assault entry — and leans *against*
   attention.

   **Attention has never once won**, and in every run the only reliably
   measurable consequence of playing was delivering less food.

   The explanation is not signalling, which is what the second and third
   experiments were built to test and which both refuted. Every tool has
   the same shape: *do what the colony already does, but where I point*. A
   forage mark redirects ants that stigmergy would have routed anyway.
   Recall halts foraging to defend a nest the garrison mostly holds — worth
   12.7 fewer casualties and 14 fewer births, both intervals excluding
   zero, so the colony defends itself into starvation. The caste sliders
   duplicate what `auto_defense` already does from border pressure.

   Against an emergent system tuned across many sessions, a human pointing
   at things is noise, and noise costs throughput.

   So the direction is not another tool or another signal. It is a
   capability the colony **structurally lacks**: a resource decision that
   changes what is *possible* rather than where it happens. Something with
   a cost and a consequence, not a redirection.

   **That prediction held.** Works (below) are the first player action in
   this project that beats doing nothing, and the arm that tests the
   prediction most directly wins by the largest margin.

   Caveat, unchanged: this measures scripted policies, not skilled human
   judgment. But three policies of increasing sophistication, including one
   that uses the warning's own information to decide, all failed to beat
   doing nothing, and the thing that finally worked was not a policy at
   all.

2. **Works pay, but only one of them does, so there is no decision yet.**
   `BuilderBot` is passive in every respect except the purchase, so
   passive-vs-builder reads the spending decision on its own rather than
   attention with building bolted on. 32 paired seeds, 900s:

   ```
   passive -> nursery only    pop 16.5 -> 29.0   +12.50  CI [+6.62, +18.38]
                              born 95   -> 105    +13.34  CI [+6.12, +20.84]
                              survived 25/32 -> 30/32    p=0.125
   passive -> rampart only    pop 16.5 -> 20.5    +2.03  CI [-5.38,  +9.16]
                              survived 25/32 -> 26/32    p=1.000
   nursery -> nursery+rampart pop 29.0 -> 32.0    +2.25  CI [-5.06,  +9.31]
   ```

   The nursery is the whole effect. It is not fetching more food —
   deliveries are unchanged — it converts the same food into more ants, by
   attacking a term the colony cannot touch for itself: the price of an
   egg. That is exactly the mechanism gap 1 predicted.

   The rampart does nothing measurable, alone or added on top of the
   nursery. It fails for the same reason the first three experiments
   failed: **it reinforces something the colony is already good at.** Nest
   defence is not failing (gap 3), so buying more of it buys nothing. It
   is left in and left honest rather than quietly removed, because it is
   the clearest example in the project of the trap.

   Two things this does **not** establish. Survival is not distinguishable
   in any arm — colonies get bigger, not more likely to live, and the
   directional 25→30 is p=0.125. And the food-spending *decision* does not
   exist yet: every one of 64 builder runs bought everything it could
   afford, because 110 food for both is inside what a colony reaches in the
   first few minutes. A second work that is best under *different*
   conditions is what would turn a good button into a choice.

3. **Nest defence is not currently failing**, which is a correction to
   what this file used to say. "Every colony death is the queen lost with
   the garrison at zero" was true of a much older build and has been
   carried forward too long. Measured now over 10 runs at 900s: the queen
   is struck at all in 2, the praetorian guard reaches full strength
   inside two minutes, and when it is depleted it rebuilds in 6 of 7
   cases. The single run where the guard collapsed to zero was also the
   single run that died — which is suggestive, and is one data point.

4. **Food is not the constraint.** Famine is under 1% and the ratio holds
   above 1.6x.

5. **Sound has never been heard.** Every level was tuned by offline
   measurement in a container with no audio device.

6. **The visuals have had one pass, not a verdict.** Ants are drawn as
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
