# Working rules for this project

These are not general advice. Each one is here because it was broken, in
this repository, and the incident is named so the rule can be argued with
rather than obeyed blindly.

## Dependencies: standard library only

Every import in `an_ants_life/` is stdlib or a local module. There is no
`requirements.txt`, no `pyproject.toml`, no virtualenv, and the browser
UI is hand-written canvas with no framework or CDN script.

**Ask before adding anything third-party — every time, before writing the
import, not after.** That includes test-only and dev-only packages, and
it includes "just for this one script". If the answer has not been given
in the current session, ask; do not infer it from the fact that something
is installed in the container.

Verify the claim rather than trusting it:

```bash
grep -rn "^import \|^from " --include=*.py an_ants_life/ \
  | awk '{print $2}' | cut -d. -f1 | sort -u
```

If a task seems to need a dependency, say what it would buy and what the
stdlib alternative costs, and let the user decide. `statistics`,
`random`, `json`, `unittest` and `http.server` have covered everything so
far, including bootstrap confidence intervals and an exact McNemar test.

## Never call a change safe before the tests say so

**The incident.** Twice in one session a commit was pushed with the
reasoning "this is copy-only / a flag flip, the suite cannot regress from
it". The second time it could: flipping `ALARM_ENABLE` exposed a
`frozenset` being JSON-serialised, and saving a colony crashed. The
branch carried a broken save for three commits.

The rules that follow from it:

- **Wait for green before pushing.** The suite takes under three minutes.
  There is no deadline in this project that is worth a broken branch.
- **If something must be pushed before the suite finishes, say
  "unverified" and name what is unchecked.** Never "this shouldn't
  regress" — that is a prediction dressed up as a result.
- **A targeted module passing is not the suite passing.** `test_alarm`
  was green while `test_persistence` was crashing on the same change.
- **Reason about the blast radius, not the diff size.** A one-line
  default change reaches every code path that reads it. "Small change"
  says nothing about risk.

## Be cautious in the specific ways this codebase punishes

- **Read the surrounding function before inserting into it.** The alarm
  responder assignment first went below an early `return` in
  `update_directives`, so the guard only answered calls while a directive
  happened to be on the board.
- **One bug can hide another.** `defend_detachment` had the same
  serialisation flaw for a long time and never fired, because it was only
  ever set when the board was non-empty. When a fix exposes a crash, ask
  what else was being masked.
- **Pick numbers from measurement, not feel.** `ALARM_DECAY_PER_SEC` was
  first set to 2.5 with a confident comment about why; measuring showed a
  call went silent before any soldier could cross the answer radius.
  Where a constant governs a race between two timings, compute both.
- **This is a chaotic simulation.** A one-tick divergence changes the
  outcome of a 27,000-tick run completely. Never assume two runs match
  because the change "looks inert" — check, the way the reused passive
  rows were checked bit-identical before being relied on.

## Measurement discipline

The project's results live in `README.md` under Known gaps, and they were
expensive. Protect them:

- **Paired on seeds, both arms, or it is not a comparison.** Use
  `tests/harness.py` (`compare`, `compare_rows`, `compare_report`) and
  `tests/bots.py` for scripted players.
- **Report confidence intervals and negative results.** Four
  interventions have failed here; each failure is recorded with its
  numbers, and that record is worth more than the code that produced it.
- **Do not state a mechanism as established without measuring it.** The
  first explanation given for the rampart's failure was wrong and had to
  be corrected in a pushed file.
- **A finding that has been corrected stays visible as a correction.**
  Do not quietly rewrite history in the README.

## Running things

```bash
cd an_ants_life
python3 -m unittest discover -s tests -t .      # fast tier, ~3 min
ANTS_SLOW=1 python3 -m unittest discover -s tests -t .   # adds long runs
python3 -m server 8731                           # play it; port is positional
```

Long experiments belong in the scratchpad and should run under
`multiprocessing.Pool(4)`; a 32-seed paired comparison at 900s takes
about ten minutes.

## Repository

- Develop and push only to the branch named in the session brief. Never
  push elsewhere without explicit permission.
- No pull request unless it is explicitly asked for.
- `saves/` is local play data and is gitignored.
- Do not put a model identifier in commits, code comments, or anything
  else that lands in the repository.
