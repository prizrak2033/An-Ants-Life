# An Ant's Life — Project Spec

**Status:** living · **Last revised:** 2026-10-14 · **Stage:** playable prototype,
never playtested

A spec earns its place by recording decisions that would otherwise be
re-litigated. Everything below is either settled with evidence, settled
by preference, or explicitly open. Nothing here is aspiration.

---

## 1. What this is

A single-player ant colony simulation, inspired by SimAnt, played in a
browser. The player does not command ants. They place scent marks, set
standing orders for the brood the queen raises next, and spend gathered
food on permanent changes to how the colony works. Everything else
emerges from individual ants following local rules and each other's
trails.

Written in Python with no dependencies, served to a hand-written canvas
UI with no framework.

## 2. Who it is for

Primarily its author, who is learning game development, systems design
and software engineering by building it. Secondarily, eventually, people
who are handed a link or a file: friends first, possibly buyers later.

That second audience does not exist yet and no decision should be made
on its behalf until someone outside the author has played it.

## 3. Goals

Deliberately falsifiable. "Fun" is not a goal because it cannot be
checked.

- **G1.** A player finishes a run and wants to start another one.
- **G2.** A player can tell what their decisions did. Not whether they
  were optimal — whether they had any effect they could perceive.
- **G3.** A run has an ending the player recognises as an ending, not
  simply a colony that dwindles while they lose interest.
- **G4.** Someone who has never seen it can start playing without being
  told anything by the author.
- **G5.** The author understands every system in it well enough to
  explain why it behaves as it does.

G5 is not decoration. It is the reason the project exists, and it
outranks the others when they conflict.

## 4. Non-goals

The most load-bearing section here. Each of these has been considered
and rejected, and raising them again needs new information.

- **Not a real-time strategy game.** The player never selects or orders
  individual ants. If a feature requires direct unit control, it is out.
- **Not multiplayer**, networked, or account-based.
- **Not an accurate biological simulation.** Real ant species behaviour
  is inspiration, not a specification. Where realism and legibility
  conflict, legibility wins.
- **Not a 3D or sprite-art game.** Shapes on a canvas. Art direction is
  not where this project's effort goes.
- **Not a live-service or content-treadmill design.** A run is bounded.
- **No third-party dependencies** — see Constraints.
- **Not seeking a wide audience.** Built to be good, then shared. The
  reverse order would change every decision above.

## 5. Decided, with evidence

Decisions backed by measurement. Numbers are from paired-seed
experiments; method and full results are in `README.md`.

### 5.1 The player spends food; they do not direct ants

**Four interventions that redistribute the colony's existing effort have
all failed**, measured over paired seeds with scripted players: forage
and defend directives, the recall, forager flee behaviour, and an alarm
pheromone. Each one costs food delivery and returns nothing significant.

Two of them are the same idea in opposite directions — pull a worker out
of a fight (flee), or send a soldier into one (alarm). Both lose, and
both lose to a job the colony was already quietly doing well.

**What works is changing a rule.** The two "works" — a nursery that
makes every egg cheaper, and a fungus garden that makes every ant eat
less — are the only player actions ever measured to beat doing nothing.
Buying both is the only thing that has moved *survival*: 25/32 → 31/32,
p=0.031.

**Consequence:** new player capabilities should attack a term in the
colony's arithmetic, not relocate its labour. A proposed feature that
moves ants around is probably already known to fail.

### 5.2 The colony is autonomous by design, and that is a problem to solve, not a bug

Stigmergy works. The colony feeds itself, defends itself, and rebuilds
its guard without help. This is why directing it does not pay.

**Consequence:** the design problem is not "make the player better at
helping". It is "give the player something the colony structurally
cannot do for itself".

### 5.3 Framerate independence is non-negotiable

Every rate is per-second and clamped at `MAX_DT`. A pheromone bug once
left trails retaining 9.7% of their strength per second where the config
asked for ~58%, and the core mechanic ran broken for a long time without
anyone noticing.

**Consequence:** the speed control adds *ticks per frame*, never a
larger `dt`. Guarded by tests.

### 5.4 Negative results are kept

Failed mechanics ship disabled behind flags (`ANT_FLEE_ENABLE`,
`ALARM_ENABLE`) with their measurements recorded, rather than deleted.
A corrected finding stays visible as a correction — the first
explanation given for one failure was wrong, and the correction is more
instructive than the original.

## 6. Open questions

Honestly open. Do not treat any of these as settled.

- **O1. Is it enjoyable?** Nobody has played a full session. Four
  experiments predict the player will feel like a spectator. **This is
  the binding constraint on everything else** and the next thing to
  resolve.
- **O2. What is the win condition?** Survive to a time, reach a
  population, drive off N assaults, or something not yet considered.
  Should not be chosen before O1 is answered.
- **O3. Should the works be mutually exclusive?** They are currently
  sequential, not a choice — both are affordable within minutes and the
  nursery is the better first buy on 24 of 32 seeds. Making them a real
  decision needs a second option that is best under different conditions,
  which has not been found.
- **O4. Is the population cap of 60 right?** It binds at peak in several
  configurations, so added capacity evaporates. Untested.
- **O5. What does a second run offer that the first did not?** No answer
  yet. Without one, G1 fails by default.

## 7. Constraints

- **Standard library only.** No `requirements.txt`, no framework, no CDN.
  This is a hard constraint, chosen so the project stays teachable,
  auditable and trivially runnable. It has not yet cost anything: the
  statistics for every experiment, including bootstrap confidence
  intervals and an exact McNemar test, are hand-written.
- **Solo developer**, learning as he goes, working in sessions bounded by
  an AI usage budget. Favours work that fits in one session and leaves
  the repository green.
- **Python 3.9+**, any OS with a browser.
- **The simulation is chaotic.** A one-tick divergence changes the
  outcome of a 27,000-tick run completely. Nothing may be assumed
  identical without being checked.

## 8. How we know we are wrong

The evidence standard, which is what makes the rest of this document
worth trusting.

- A claim about behaviour is either **measured** or labelled a guess.
- Comparisons are **paired on seeds**, both arms, with confidence
  intervals reported.
- **Negative and null results are reported** with the same prominence as
  wins. Four of them are the most valuable content in the repository.
- A mechanism is not stated as established until it has been tested
  rather than merely reasoned.
- 91 tests must pass before anything is pushed.

## 9. Roadmap

In order. Each is roughly one working session.

1. **Playtest.** The author plays and reports what bored or confused
   them. Resolves O1. Everything below is guesswork until this happens.
2. **Win condition.** Resolves O2 and addresses G3.
3. **First sixty seconds.** Onboarding. Addresses G4.
4. **Variety.** More works, enemy kinds or map events. Addresses G1/O5.
5. **Packaging.** Runnable without Python installed.

## 10. Revision log

A spec that is never revised was never load-bearing.

| Date | Change |
|---|---|
| 2026-10-14 | First version. Captures the state after the works feature, the tooltip pass, the alarm experiment and the speed control. |
