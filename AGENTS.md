# AGENTS.md — the entry contract

Orientation, the gate, and **which document owns which question**.
Start every session with `genome wake`; find an answer with `genome ask "<question>"`;
end every iteration with `genome close`.

## What this project is

**project-genome is the skill that runs every other project in the portfolio.** It ships
two things from one source: a stdlib CLI (`scripts/genome`, built by `scripts/build.py`
from `src/NN_*.py`) and the Claude Code skill bundle (`SKILL.md` + `references/`).
Every repo under `~/Documents/github/my-projects` that carries a `genome.toml` either
runs a vendored copy of that CLI or installs it; this repo is where they all get it
from. **Editing `src/` here is editing the kernel the whole fleet lints against** — a
change lands as far as every repo's next `genome lint`.

Two front doors, deliberately different:

| surface | for | owns |
|---|---|---|
| `README.md` | a human deciding whether to install | what it is, install commands, the features |
| `SKILL.md` | the harness that loads the skill | the trigger description — when to reach for this skill |
| this file | an agent working **in this repo** | the kernel's own architecture, its rules, and which of its docs answers what |

The rules that apply to every adopting project live in `references/core.md`; they are
written there because this repo obeys them too, not because this repo is special.

## Architecture

One file, built from parts. `scripts/build.py` concatenates `src/NN_*.py` in name order
(blueprints embedded as one generated part just before the main part) into a single
plain stdlib script. The build is byte-stable: the same `src/` always produces the same
`scripts/genome`, which is why a vendored copy and a PyPI install are the same bytes and
why `scripts/releases.txt` can compare checksums.

```
src/NN_*.py           27 source modules, the only place the CLI is edited
scripts/build.py      the concatenator; --check exits 1 when scripts/genome is stale
scripts/genome        the built artifact (6,749 lines) — generated, never hand-edited
scripts/releases.txt  VERSION -> sha256, the release ledger `genome upgrade` compares
references/*.md       10 manuals: the rules, the modules, the lint codes, blueprints
blueprints/*.toml     5 ready-made KB shapes, embedded into the build
evals/                16 graded scenarios + the grader; how the skill is tested end to end
project_genome/       the thin package wrapper: `python -m project_genome`, the console
                      script, and the runpy shim that keeps __file__ honest
install.sh / .ps1     the two installers (same chain: uv tool, pipx, pip, then
                      --skill: one canonical copy at ~/.agents/skills + a link per
                      harness root + a .skill-lock.json entry)
docs/PUBLISHING.md    the PyPI release path (the operator's credential, the operator's step)
```

**The one rule that shapes everything:** the CLI is *one file* with *zero dependencies*.
That is what makes it copy-one-file installable, vendorable into a repo, and identical
wherever it runs. Any change that needs an import breaks the property, so `src/` is
stdlib-only and the wrapper executes the file through `runpy` rather than importing it.

**Six modules, on by configuration:** `core` (roles, routing, register, handoff), `records`
(decisions and regressions), `research` (evidence classes, hypotheses, pre-registration),
`ops` (ownership map, budgets), `agents` (parallel-agent claims and feed), `outline` (a
derived structural zone gated against drift). A small app needs `core`; the rest scale up.

## Gate

```
python3 scripts/test_genome.py     # 38/38 suites: the CLI, against a scratch copy
```

The `[core] gate` here is `pytest -q`, but **`pytest` has nothing to collect** — the
tests are the three self-check scripts, and the one that gates a release is
`scripts/test_package.py`, which installs the actual wheel and asserts byte parity with
the vendored `scripts/genome`.

| suite | what it proves | last measured |
|---|---|---|
| `scripts/test_genome.py` | 38/38 cases: the CLI against a scratch copy, never your project | 2026-10-30 |
| `scripts/test_package.py` | 8/8: the wheel installs, the console script and `-m` both run, byte parity | 2026-10-30 |
| `scripts/test_package_modes.py` | 5/5: the sdist path, the whole command surface in installed mode, the exit codes a CI job chains on, and the Python floor | 2026-10-30 |

## Routing table — which document answers what

| question | answer lives in |
|---|---|
| what is this / how to build / the rules (for agents) | this file |
| what is this, how do I install and run it (for readers) | `README.md` |
| when should a harness load this skill | `SKILL.md` |
| how the pieces fit together (the architecture) | this file § Architecture |
| where does the project stand right now | `docs/handoff/STATE.md` |
| what does a fresh agent read, in order | `docs/handoff/README.md` |
| what is left to do, and what was decided about each item | `TODO.md` |
| what did we ask the operator, and what did they rule | `docs/kb/ASKS.md` |
| how will we do X (plans) | `docs/plans/` — the live execution order is `docs/plans/2026-10-30-remaining-implementation-gaps-outline.md` |
| what was audited, what was found | `docs/audit/` |
| what was tried and rejected — do not re-litigate | `docs/kb/CLOSED.md` |
| exact commands, environment traps | `docs/RUNBOOK.md` |
| what happened, session by session | `docs/kb/WORKLOG.md` |
| superseded history | `docs/archive/` |
| why X is the way it is (decisions) / what bit us (regressions) | `docs/RECORDS.md` |
| **the rules themselves** (every module, every lint code) | `references/core.md` and its siblings |
| **the lint code list**, and which are free to mint | `references/lint-rules.md` |
| **the PyPI release path** | `docs/PUBLISHING.md` |
| **the eval suite and its grader** | `evals/evals.json`, `evals/grade.py` |

## The four loci — where a kernel fix must land

A defect found in a launch's copy is not fixed where it was found. The four loci
are named by the meta-directory's own audit (`SURFACE-AREA-AUTOPSY`, 2026-10-22, in the
meta-root's `docs/audit/`, not this repo's) and re-measured here on 2026-10-30:

| locus | path | what it is |
|---|---|---|
| 1 | this repo's `src/` | the only place the kernel is edited |
| 2 | `~/.agents/skills/project-genome/` | the installed skill; its `src/` is **byte-identical** to this repo's (`diff -rq`, 2026-10-30), so it is a deploy target, not a second source |
| 3 | each venture's `scripts/genome` | **77 vendored CLI files across the fleet**, at three versions (measured 2026-10-30: 75 at `2026.10.27-13`, 1 at `2026.10.22-17`, 1 at `2026.10.21-2`) |
| 4 | `~/.local/bin/genome` | this machine's own install, on PATH |

A kernel change is not done until it is built, released, and the fleet that needs it is
upgraded. `genome upgrade --apply` is the dispatch; the vendored-copy guard refuses to
reset a `scripts/genome` that carries uncommitted local work (the guard was added to
both installers after a reset discarded a working-tree copy in operant).

## Rules

1. One owner per question; amend the owner, never add a second.
2. Every document has a mutability class; append-only files only gain lines.
3. Nothing is deleted: superseded → `genome archive --reason`.
4. Terminal states name their evidence; numbers cite the artefact they came from.
5. Operator feedback amends its owner doc or record in the same session (`genome q rule ... --applied`).
6. **Never hand-edit `scripts/genome` or `references/`'s generated zones.** `scripts/genome`
   is built from `src/`; run `python3 scripts/build.py`. `dist/` is generated too.
7. **The CLI stays one stdlib-only file.** No imports, no dependencies. A change that
   breaks copy-one-file installability breaks the property the whole design rests on.
8. **A new lint code takes the next free flat number, never a gap.** The live
   catalogue, derived from the shipped script on 2026-10-30 (`grep -rhoE` over `src/`):
   **14 E-codes and 10 W-codes** — E001-E006, E008-E010, E013-E017 (max **E017**; free
   **E018/E019/E020**) and W000, W006-W014. The gaps — **E007, E011, E012** and
   **W001-W005** — are deliberately not reused, because older fleet copies may carry them
   with meanings a new code cannot derive. (The 2026-10-28 audit's "44 E-codes and 21
   W-codes" counts every code the module can emit, including ones assembled at runtime and
   doc tables alone; the 14/10 here is what the source literally names.) This is the rule
   the KB-protocol addendum was written to enforce
   (`docs/plans/2026-10-28-KB-GATE-NUMBERING-ADDENDUM.md`).
9. **Worklog entries are committed.** A logged-but-uncommitted entry is invisible to
   every session that reads from the entry contract.
10. **`logged ≠ adopted`.** A `genome q rule` without `--applied` leaves its informant
    silently logged-only, so an unapplied ruling is indistinguishable from an
    unimplemented one until someone reads the queue. The applied path is the check.
