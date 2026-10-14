# ADR-0001: Standard library only

**Status:** accepted · **Date:** 2026-09-17

## Context

The project needed statistics — confidence intervals on paired
experiments, a significance test for survival differences — and plotting
would have been convenient for reading results. The obvious move is
`numpy`, `scipy` and `matplotlib`.

The project is also a learning exercise, and its author wants to be able
to explain every part of it.

## Decision

No third-party dependencies, anywhere, including test-only and
development-only packages. No `requirements.txt`, no virtualenv, no
framework, no CDN script in the browser UI.

Anything needed is written by hand against the standard library.

## Consequences

The project clones and runs with `python3 -m server`. There is no
install step to go wrong, no dependency to drift, and nothing to audit
before handing it to someone. For a project that may be sent to friends,
this removes the most common first-five-minutes failure.

Percentile bootstrap confidence intervals and an exact McNemar test are
hand-written in `tests/harness.py`, roughly sixty lines. Writing them
forced an understanding of what they actually do, which a library call
would have hidden. This is a benefit here specifically because learning
is a stated goal; on a project with a deadline it would be a cost.

**The uncomfortable part:** there is no plotting. Every experimental
result is read as numbers in a terminal, which is slower and makes some
patterns easy to miss. This has been accepted rather than solved.

The constraint will eventually bind on something real — audio encoding,
or packaging a binary for people without Python. When it does, this ADR
gets superseded rather than quietly broken.
