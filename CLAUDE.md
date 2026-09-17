# Working rules for this project

These are not general advice. Each one is here because it was broken, in
this repository, and the incident is named so the rule can be argued with
rather than obeyed blindly.

## What this project is for

Built for its author's own learning and enjoyment, with the intention of
refactoring and growing it into something distributable - to friends, or
sold. That target changes what counts as progress.

**The measurement work has done its job.** The design truth is known and
recorded in the README: the colony is too autonomous to be worth
directing, four redistribution mechanics failed identically, and only
rule-changes pay. A fifth agency experiment would be scholarship, not
game development.

**The binding constraint is now that nobody has ever played it.** This
project has research-grade evidence about its mechanics and no evidence
at all that anyone enjoys it. It is a sandbox that decays, with no goal,
no win, and no reason to start a second run. Balance work is the
comfortable work because it is measurable; it is not the work that
matters for where this is going.

Roadmap, in order. Each is one session:

1. **Play it.** The author plays for fifteen minutes and reports what
   confused or bored them. Everything below is guesswork until this
   happens.
2. **Win condition.** A goal - survive to X, reach population Y, drive
   off N assaults. Turns a sandbox into a game.
3. **First sixty seconds.** Onboarding. A new player currently meets
   twenty controls and no instruction.
4. **Variety.** More works, enemy kinds or map events. Replay value.
5. **Packaging.** Runnable by someone who does not have Python.

## How we work together

The author is a self-taught developer and cybersecurity professional
with a master's in sociology and political economy, and is building this
to learn. Uses speech-to-text, so messages ramble - extract the intent,
never ask for a rephrase. Has ADD: lead with the answer, keep sections
short and skimmable, do not bury the point in preamble.

- **Always end with a Y/n question, and say what each answer will do.**
  Not "shall I proceed?" but "Y = I do this specific thing, n = I do
  this other specific thing instead."
- **Offer clickable options** rather than prose menus, so a decision is
  one click instead of a typed paragraph.
- **One recommendation, not a survey.** They will push back if they
  disagree, and they have no ego about being corrected. Being redirected
  is more use to them than being agreed with.
- **Say when they are off the mark**, and offer the better option with
  the reasoning. This is explicitly wanted.
- **Teach while doing.** Briefly say *why* something works. The goal is
  to understand the system, not to receive a black box. Second-order
  effects and unintended consequences are the interesting part.
- **One objective per session**, stated at the top. Batch the work and
  report once rather than narrating each step - the conversation is the
  expensive part, not the compute. Background experiments are cheap.
- **Everything durable goes in this file.** It loads free every session;
  anything re-explained in chat is paid for twice.

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
python3 -m server 8731        # play it; --port 8731 and -p 8731 also work
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
