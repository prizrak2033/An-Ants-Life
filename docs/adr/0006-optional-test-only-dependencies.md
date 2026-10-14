# ADR-0006: One optional test-only dependency is permitted

**Status:** accepted · **Date:** 2026-10-14
· **Amends:** [ADR-0001](0001-standard-library-only.md)

## Context

ADR-0001 says no third-party dependencies "anywhere, including test-only
and development-only packages".

**That was not true when it was written.** `tests/test_audio.py` imports
`playwright`, which drives a headless Chromium to render the game's Web
Audio graph through an `OfflineAudioContext` and measure what it
actually sounds like. It is the reason every suite run reports two
skipped tests, and nobody had noticed the contradiction.

It surfaced the first time a test was written to check the documentation
against the code, which found it within seconds of existing.

The audio measurements are not decorative. They caught a compressor
attenuating signal below its threshold, a WaveShaper curve built over
the wrong domain making everything 2.8x too loud, and band-passed noise
keeping 1% of its power. None of that is reachable without a real audio
engine, and no stdlib substitute exists.

## Decision

The rule is tightened to what it was always doing, rather than being
quietly broken:

- **The shipped game imports nothing third-party.** Anyone can clone it
  and run `python3 -m server` with a bare Python install. This is the
  part that matters and it is unchanged.
- **The test suite may use optional tools**, provided each one is
  declared in `OPTIONAL_TEST_ONLY` in `tests/test_docs.py` and skips
  rather than fails when absent. A fresh clone must be able to run its
  own suite.
- Adding one still requires asking first, per `CLAUDE.md`.

Both halves are now enforced by tests rather than asserted in prose.

## Consequences

ADR-0001's reasoning survives intact — the zero-install promise to
anyone handed this project is the whole point, and it was never actually
at risk. Only its overstatement is corrected.

`playwright` is the single permitted entry. Anything else is a test
failure naming the offender, not a thing someone discovers in a year.

**The uncomfortable part:** two of the ninety-odd tests do not run on a
clean machine, so the suite reports green while measuring slightly less
than it claims. Anyone relying on the audio tests must install the tool
deliberately. That is a real gap, accepted because the alternative is
having no audio verification at all.

**The broader lesson, which is why this ADR exists rather than a quiet
edit:** ADR-0001 was confidently wrong for a month and nobody caught it,
because prose is not checked by anything. The fix was not to write more
carefully. It was to make the claim executable.
