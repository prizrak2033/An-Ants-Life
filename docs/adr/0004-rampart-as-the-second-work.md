# ADR-0004: A rampart as the second work

**Status:** superseded by [ADR-0005](0005-fungus-garden-replaces-rampart.md)
· **Date:** 2026-09-17

## Context

ADR-0002 established that the player spends food on rule changes. A
nursery (every egg cheaper) was the first. A second was needed, because
one option is not a decision.

The colony's size is governed roughly by

```
P = (regen − egg_cost × loss_rate) / upkeep_per_ant
```

The nursery attacks `egg_cost`. The obvious second target is
`loss_rate`: if the colony loses fewer ants, it spends less replacing
them.

## Decision

A rampart: earthworks around the nest that slow intruders to 0.55× within
20 units, priced the same as the nursery at 55 food. More attacks for the
garrison before contact, therefore fewer losses.

## Consequences

**It measured completely inert.** Alone, end population +2.03 (CI
[−5.38, +9.16]) and survival 25/32 → 26/32 (p=1.00). Added on top of a
nursery it moved nothing either.

The first explanation recorded for this was that it defended ground where
losses do not happen. **That was wrong**, and measuring 1337 deaths
refuted it: the median death is 26.7 units from the nest and 44% fall
inside the rampart's own ring. It covered nearly half the casualties and
still did nothing.

The real cause: the rampart changed **movement**, but ants die in
**combat exchanges**, whose rate is set by `COMBAT_COOLDOWN_SECONDS` and
not by how fast an enemy walks. A slowed intruder trades blows just as
often and lingers longer where ants are densest, so the attacks gained
and the exposure paid roughly cancel.

Superseded by ADR-0005. The transferable lesson: **a work must attack the
binding term in the units that term is measured in.** Slowing a thing
does not reduce a rate that is not expressed in distance.
