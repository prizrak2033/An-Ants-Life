# ADR-0002: The player spends food rather than directing ants

**Status:** accepted · **Date:** 2026-09-17

## Context

The game shipped with directives (forage, defend, explore), a recall, and
caste policy sliders. All of them point the colony at something.

Three paired experiments with scripted players, at increasing
sophistication, found that an attentive player **never** beat a passive
one. The only effect reaching significance in every run was that playing
*reduced food delivery*. A fourth mechanic, forager flee, cut casualties
41% and lost more colonies (29/32 → 23/32).

The cause is not signalling, which the second and third experiments were
built to rule out. Every tool had the same shape: *do what the colony
already does, but where I point*. Against emergent behaviour tuned over
many sessions, pointing is noise, and noise costs throughput.

## Decision

New player capabilities must **change a rule**, not relocate labour.

The player spends gathered food on permanent alterations to how the
colony works — currently a nursery (every egg cheaper) and a fungus
garden (every ant eats less). These attack terms in the colony's size
equation that no ant can perceive or affect.

## Consequences

This is the only thing ever measured to beat doing nothing here. Buying
both works moved survival 25/32 → 31/32, p=0.031 — the first survival
effect in the project's history.

A proposed feature that moves ants around is now presumed to fail, and
the burden is on the proposal to say why it differs from the four that
already did. That is a strong filter and it will occasionally reject
something good.

**The uncomfortable part:** the existing directives, recall and sliders
all still ship, and all are measured to be worthless or harmful. They are
kept because removing them would make the game emptier without making it
better, and because a player expects to be able to point at things. This
is an unresolved tension, not a settled one.

Later measurement weakened part of this: the two works are a build
*order*, not a choice — the nursery is the better first buy on 24 of 32
seeds. See `SPEC.md` O3.
