# Architecture Decision Records

One decision per file, numbered, written once.

An ADR is **frozen when accepted**. It is never edited to reflect a
change of mind — a new ADR is written that supersedes it, and both stay.
The trail of superseded decisions is the point: it shows how the
thinking moved, and it stops a rejected idea being re-proposed without
new information.

Compare with the other documents here:

| File | Says | Lifecycle |
|---|---|---|
| `README.md` | what this project is | rewritten freely |
| `SPEC.md` | what is true now | revised in place |
| `docs/adr/*` | how one truth was arrived at | frozen, superseded |
| `CLAUDE.md` | how to work in this repo | revised in place |

## Format

**Context** — what forced a decision. **Decision** — what was chosen, in
the active voice. **Consequences** — what follows, including the bad
parts. If the consequences section has nothing uncomfortable in it, the
decision probably was not a real trade.

Keep each one to a page. A long ADR is usually two decisions wearing one
coat.

## Status values

`proposed` · `accepted` · `superseded by ADR-NNNN` · `deprecated`

A record may also **amend** another: a correction too small to supersede
the whole decision. ADR-0006 amends 0001 that way.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-standard-library-only.md) | Standard library only | accepted |
| [0002](0002-the-player-spends-food.md) | The player spends food rather than directing ants | accepted |
| [0003](0003-keep-failed-mechanics-disabled.md) | Failed mechanics ship disabled, not deleted | accepted |
| [0004](0004-rampart-as-the-second-work.md) | A rampart as the second work | superseded by 0005 |
| [0005](0005-fungus-garden-replaces-rampart.md) | A fungus garden replaces the rampart | accepted |
| [0006](0006-optional-test-only-dependencies.md) | One optional test-only dependency is permitted | accepted |
| [0007](0007-saves-are-untrusted-input.md) | Save files are untrusted input | accepted |
