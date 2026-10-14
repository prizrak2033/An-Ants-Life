# Threat model

Most threat models for small projects are theatre: a page of STRIDE
tables for software with one user and no network. The useful version
asks three questions and stops.

1. **What is worth protecting?**
2. **Where does untrusted input cross into trusted code?** (the trust
   boundaries — this is the whole exercise)
3. **At each boundary: what goes wrong, and are we fixing or accepting
   it?**

Everything below follows from finding the boundaries. There are three.

## What is worth protecting

Honestly, not much, and saying so is part of the exercise.

- **The player's machine.** The only thing with real value here.
- **The player's saved colonies.** Hours of play, locally stored, not
  backed up.
- **The project's reputation.** A game that crashes when a friend opens
  a shared save is not a security problem, but it is the failure most
  likely to actually happen.

No accounts, no credentials, no personal data, no payment, no network
service. Nothing here is worth attacking for gain.

## Boundary 1: the HTTP control endpoint

The simulation runs behind `http.server`, and the browser POSTs JSON
commands to `/control`.

**Bound to `127.0.0.1`, not `0.0.0.0`.** Nothing on the network can
reach it. Anyone already executing code on the machine can, but they
could also just read the save files directly, so this adds nothing to
their position.

The accepted actions are a fixed set — `PLAYER_ACTIONS` plus a handful
of runner controls — and anything unrecognised is refused. Values are
clamped (`set_speed` snaps to 1, 2 or 4; directive coordinates clamp to
the world), because the endpoint is open to anyone with `curl` even
though the UI only offers legal values.

**Status: fixed and accepted.** No authentication, deliberately: on a
single-user local game it would be ceremony, and the bind address is
the real control.

## Boundary 2: save files

**The most interesting boundary, and the one that was wrong.**

A save is JSON, written by the game, loaded by the game. But the
intended future of this project is people sending each other colonies —
which makes a save file *untrusted input from another person*.

What is already right: saves are **JSON, never `pickle`**. This matters
more than everything else on this page. `pickle.load` on a file someone
sent you is arbitrary code execution; `json.load` is not. Save names
from the client are stripped to alphanumerics, hyphens, underscores and
spaces before touching the filesystem, so there is no path traversal.

What was wrong, found by testing rather than reading:

| Hand-edited save | Was | Now |
|---|---|---|
| `PHERO_GRID: 0` | `ZeroDivisionError` on load | ignored, default used |
| `WORLD_W: "abc"` | `TypeError` on load | ignored, default used |
| `FOOD_UPKEEP…: -5` | silently infinite food | ignored, default used |
| `ANT_SPEED: 1e9` | accepted | ignored, out of sane range |
| `WORLD_W: 150` | `IndexError` from deep in terrain loading | clear `CorruptSave` message |

None of these is a compromise. All of them are a bad time for someone
opening a colony a friend sent. The last one was a **pre-existing bug**
that the threat model surfaced: the config and the stored grids have to
describe the same world, and when they disagreed the error arrived far
from its cause.

**Status: fixed.** Values from a save are type-checked, range-checked
and sanity-checked, and anything rejected falls back to the current
default so odd or old saves still open. Structural mismatches raise
`CorruptSave` with a sentence saying what is inconsistent. See
[ADR-0007](adr/0007-saves-are-untrusted-input.md).

## Boundary 3: the browser page

The UI is hand-written, loads no third-party script and no CDN, and
talks only to its own origin.

The one thing to keep right: **colony names and save labels are player
text that gets rendered**. They are written with `textContent`, never
`innerHTML`, so a save labelled `<img onerror=…>` is drawn as those
characters rather than parsed. This is the kind of thing that breaks
silently during a refactor.

**Status: accepted, with one thing to not break.**

## What is deliberately not defended

- **Cheating.** Single-player. A player who edits a save to give
  themselves food has only affected their own game. The validation above
  exists to prevent *crashes*, and blocking the obvious cheats is a side
  effect, not the goal.
- **Denial of service.** Someone who can run the game can already stop
  it.
- **The save directory.** Plain JSON on disk, no encryption, no
  integrity check. Protecting it from someone with filesystem access is
  not achievable and not worth attempting.

## What would change this

This page assumes a local, single-player game. Any of these would
require redoing it from the top:

- Binding to anything other than loopback
- Accounts, scores or anything uploaded
- Loading mods, plugins or Python from user files
- Save files that carry code rather than data
