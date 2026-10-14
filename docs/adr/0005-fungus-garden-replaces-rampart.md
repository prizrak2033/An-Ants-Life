# ADR-0005: A fungus garden replaces the rampart

**Status:** accepted · **Date:** 2026-09-17
· **Supersedes:** [ADR-0004](0004-rampart-as-the-second-work.md)

## Context

ADR-0004's rampart measured inert because it attacked movement when the
binding term was not expressed in distance. A second work was still
needed.

Of the terms in the size equation, `upkeep_per_ant` was the only one
nothing touched — and unlike defence, it is not something the colony is
already good at managing.

## Decision

A fungus garden: ants farm the colony's waste, and every ant eats 20%
less, permanently. Priced at 55 food, the same as the nursery.

The discount was chosen from arithmetic rather than feel, so that both
works land on nearly the same population ceiling by different routes —
36.7 plain, 46.9 with a nursery, 45.8 with a garden. The model had
already predicted the first two to within a point, and the tests now
assert all three.

## Consequences

The pair works. Buying both moved end population 16.5 → 36.5 (CI [+12.00,
+26.34]) and **survival 25/32 → 31/32, p=0.031** — the first and so far
only survival effect measured in this project.

**The uncomfortable part, and the reason this ADR is not a clean win:**
the garden does **not** pay on its own (+1.75, CI [−4.75, +7.78]). Its
saving scales with population × time, so on a passive-sized colony it
recovers about 50 food against a 55 price and never clears its own cost.
It is a second purchase by construction.

So the stated intent — two comparable options, best under different
conditions — **was not achieved**. The nursery is the better first buy on
24 of 32 seeds, and splitting seeds by attrition does not rescue the
story. What exists is a build *order*, not a choice. Recorded as open
question O3 in `SPEC.md` rather than papered over.

Raising the garden's cut to 0.50 was measured and would make it a real
two-way choice (nursery better on 13 seeds, garden on 18). It was not
adopted, because at that strength the population cap binds and the
economy changes character. Left as a documented option.
