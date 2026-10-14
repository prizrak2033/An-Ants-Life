# ADR-0003: Failed mechanics ship disabled, not deleted

**Status:** accepted · **Date:** 2026-09-17

## Context

Two fully built mechanics measured as harmful or inert: forager flee
behaviour, and an alarm pheromone channel. Both worked exactly as
designed. Both lost.

The obvious tidy-up is to delete them. Dead code is a liability, and
nobody wants a configuration flag for something that does not help.

## Decision

A measured failure ships **disabled behind a config flag**, with its code
intact, its tests passing, and its measurement written into the config
comment and the README.

A finding that is later corrected stays visible **as a correction**. The
README does not get quietly rewritten to look like it was always right.

## Consequences

`ANT_FLEE_ENABLE` and `ALARM_ENABLE` both default to `False` and both
remain fully working and tested. The alarm channel carries ten tests it
does not strictly need.

The measurements are worth more than the code. Knowing that pulling a
worker *out* of a fight and sending a soldier *into* one both lose — and
that both lose to a job the colony was quietly already doing — is the
most transferable thing this project has produced. Deleting the code
would eventually have meant someone rebuilding it to re-learn the same
thing.

Keeping corrections visible has already paid once: the first explanation
given for the rampart's failure was wrong, and measuring where ants
actually die refuted it. The wrong explanation and the refutation are
both recorded, because the correction is more instructive than a clean
answer would have been.

**The uncomfortable part:** this is carried cost. Two dead code paths,
their tests, and their flags must keep working through every refactor,
for a benefit that is documentation rather than function. If the
maintenance ever gets heavy, delete the code and keep the README entry —
but not before.
