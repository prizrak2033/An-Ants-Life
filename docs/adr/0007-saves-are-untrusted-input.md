# ADR-0007: Save files are untrusted input

**Status:** accepted · **Date:** 2026-10-14

## Context

A save is JSON written by the game and read by the game, so its contents
were trusted implicitly: `_config_from_dict` filtered unknown field
*names* and passed every value straight into `SimConfig`.

The project intends people to send each other colonies. That makes a
save file untrusted input from another person, and a threat-modelling
pass tested what one could do. A hand-edited save could crash the game
on load (`PHERO_GRID: 0`, or any wrong type), grant infinite food
(`FOOD_UPKEEP_PER_ANT_PER_SEC: -5`), or produce an `IndexError` from
deep inside terrain loading with nothing naming the cause.

None of it is a compromise — saves are JSON and not `pickle`, so there
is no code execution path. All of it is a bad time for someone opening
a colony a friend sent them.

## Decision

Values from a save are validated, not merely filtered by name:

- **Type must match the field's default.** `bool` is checked before
  `int`, since in Python it is one.
- **NaN, infinities and anything beyond ±1e6** are rejected.
- **Divisors and dimensions must be positive** — an explicit list.
- **Negative where the default is not negative** is rejected. Zero stays
  legal, because several fields use it to turn a system off.
- **Anything rejected falls back to the current default**, so an odd or
  old save still opens and plays rather than failing.
- **Structural mismatches raise `CorruptSave`** with a sentence naming
  what disagrees, instead of an `IndexError` far from the cause.

Saves stay JSON. Nothing here is signed or checksummed.

## Consequences

Opening a shared colony is now a safe operation in the way that matters:
it either works, or it says what is wrong with the file.

**The uncomfortable part:** silent fallback means a save can load with
different values than it was written with and say nothing. For a
corrupt file that is the right outcome; for a legitimate save written by
a future build with a wider range, it is a quiet behaviour change. The
alternative — refusing to load — is worse for a single-player game, and
the structural check still catches the cases where quiet substitution
would produce nonsense.

**Not signing saves** is a real decision, not an oversight. A signature
would stop tampering, but tampering with your own single-player save
harms nobody, and the key would have to ship with the game, so it would
stop nothing an attacker cares about. Validation addresses the actual
failure — crashes — and integrity is accepted as out of scope.

The `±1e6` sanity bound is arbitrary. It is wide enough that no
legitimate value approaches it and narrow enough that nothing allocates
a grid big enough to matter.
