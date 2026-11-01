# Remaining implementation gaps — the execution outline

Dated-frozen: published `2026-10-30`. A plan that changes is a new plan (or declare it
in genome.toml `core.living_plans` and keep a 'Resume here' section).

**Owner:** `docs/plans/` (this document). **Gate:** `python3 scripts/genome lint --all`
returns 0 errors. **Register:** every row below traces to a `PQ-` row in `TODO.md`, and each
step closes its row with `genome status <id> done --evidence`, not by editing it out.
**Scope:** this repo (the kernel) and the fleet it governs. It does not supersede the
two dated-frozen proposals it sequences
(`2026-10-28-KB-MANAGEMENT-PROTOCOL.md` + its addendum), the pre-upgrade audit
(`../audit/2026-10-28-pre-upgrade-implementation-audit.md`), or the operator's own
publishing step (`PUBLISHING.md`).

## Why this outline exists

The previous pass (2026-10-30, commits `9f62c6f` + `71d0cc1`) made this repo
genome-managed for the first time and closed the documentation gaps. Ten open rows
remain, and they are not ten independent chores: **two of them are the same defect seen
from two sides**, three are one measurement trap with three symptoms, and one of them
is currently blocking the fleet from hearing about a fix this repo already shipped.
That ordering is what this document records.

The measured state, all of it re-derived on 2026-10-30 at VERSION `2026.10.30-23`
(6,762 lines, 27 `src/` modules, built artifact byte-stable — `python3
scripts/build.py --check` exit 0):

| fact | measurement |
|---|---|
| suites | `test_genome` 38/38, `test_package` 8/8, `test_package_modes` 5/5, `check_ps1` parity ok at 292 lines, `probe-outline-languages` 9/9 |
| lint / doctor | `lint: clean [core, records]`, `doctor: healthy`, `installs verify` exit 2 (4 real findings) |
| live lint codes | 14 flat E (max E017) + 41 family E/W + 10 flat W; **E018/E019/E020 free**, M-codes a brand-new namespace |
| the fleet | **78 vendored CLI files registered, 77 on disk** (one ghost row), of which **75 sit at `2026.10.27-13`**, `operant` at `2026.10.21-2`, `artificial-route` at `2026.10.22-17` |
| the shipping reference | the four skills roots still sit at `4733cfd` = `2026.10.30-22`, while this repo and `origin/main` are at `d86499b` = `2026.10.30-23` and in sync (0/0) |
| what the dispatch would do | `genome installs upgrade` (dry run): **78 copies "behind 2026.10.30-22"**, 585 lines added / 5 removed each — measured 2026-10-30, nothing applied |
| evals | 16 evals, 108 fixtures, `evals/grade.py` needs `<id> <repo>` and a harness caller |

## Mechanism

**Tier 0 unblocks the fleet's knowledge of a fix that already shipped.** The fence-aware
`broken_zones()` (commit `9f62c6f`) is live at `2026.10.30-23` in this repo and in the
wheel, but the four skills roots a launch reads from are at `-22`, so a launch running the
skill's own copy still fails E006 on a manual that shows the marker format. That is the same
defect at a different locus, which is exactly what the AGENTS.md four-loci table was
written to stop.

**Tier 1 is the protocol's three gates, and their numbering is already derived** — M017 /
E018 / E019 (operant feed F0119, restated in the addendum because this repo has no feed).
The addendum's frontier check was re-run here from the shipped script and still holds.

**Tier 2 is packaging and measurement honesty.** The sdist omits the CLI file
(`PQ-3`); the packaging suites are only honest from a neutral cwd and against a fresh
`dist/` (`PQ-4`, `PQ-5`); the fleet census has a ghost row (`PQ-1`'s hidden half).

**Tier 3 is ratification.** § "What is not this seat's" names each operator call, because
a plan that silently implements a pending ruling is the failure this whole chain exists to
prevent.

## Gates / success criteria

1. `python3 scripts/genome lint --all` → 0 errors, at every commit this plan produces.
2. `python3 scripts/genome doctor` → healthy, and `installs verify` reports only the rows
   each step deliberately left.
3. Every register row transitions via `genome status <id> <state> --evidence <path>`; a
   terminal row carries `→ [YYYY-MM-DD] <evidence>` in its verdict cell (E003 reads that cell).
4. Every figure in a produced document names its command on the same line.
5. No open operator ask is answered by this plan's execution.

---

## Tier 0 — sync the shipping reference (PQ-9, then PQ-1's measurement half)

### 0.1 Sync the four skills roots to this repo's tip

`install.sh` already does this (clone-or-update, `--skill`), and it is non-interactive —
no `read`/`/dev/tty` anywhere in it (measured). Each of the four roots is a **separate
clone** (4 distinct inodes for `src/01_constants.py`), all four at `4733cfd` and all four
clean, all four with the same `origin`. So the sync is one command per root, or one
installer run.

```
bash install.sh --skill            # or, per root: git -C <root> fetch && git -C <root> reset --hard origin/main
python3 scripts/genome installs verify
```

The second command is the check that matters: it currently exits 2 with the four findings
below, and 0.1's exit is that the two MISSING rows are gone (or are re-registered by hand)
and the skill rows report `2026.10.30-23`.

### 0.2 Reconcile the manifest's ghost rows and its two stale ones

`installs verify` (exit 2, measured 2026-10-30) reports, verbatim:

```
MISSING vendored …/holon-personal (was version 2026.10.27-13)
MISSING kb      …/holon-personal/holon (was version none)
STALE   vendored …/agentic-harness/operant — manifest says 2026.10.27-13, on disk 2026.10.21-2
STALE   vendored …/agentic-utility/proxy/artificial-route — manifest says 2026.10.27-13, on disk 2026.10.22-17
```

`holon-personal` does not exist on this machine (`ls` fails); its tree was folded into
`holon` and the two registry rows were never pruned. The registry has **no unregister
verb** — `installs` takes `list|verify|register|scan|upgrade` only — so the fix is either a
hand edit of `~/.config/genome/installs.json` (schema 1, rows keyed by path) or a new verb.
**Do not add the verb inside this step**; that is Tier 2 scope. The two STALE rows are the
honest state of two peer-owned repos (`operant` is actively committing; `artificial-route`
is hands-off), so they are re-registered to what is actually on disk, or left and named.

**Exit:** `installs verify` lists only rows whose divergence is deliberate and named.

### 0.3 Then the fleet dispatch, and it is an operator call

After 0.1, `genome installs upgrade` reports the true delta against `2026.10.30-23`; the
dry run measured today says **78 "would upgrade"** — but 78 counts the `holon-personal`
ghost, so the honest live number is **77**, and one of those 77 (`operant`) the dispatch
already knows to refuse by its own guard if it carries a local patch (it does — the dry
run prints "this copy differs from the released one"). `--apply` writes into 77 other
repositories; **that is PQ-1's operator-approved pass, scheduled, not started here.**

**Exit of Tier 0:** the shipping reference equals the repo; the registry names reality;
PQ-9 closes with `--evidence` citing `installs verify`'s clean output.

## Tier 1 — the protocol's three gates (PQ-2, PQ-10)

Numbering is derived and re-measured, not chosen: M017 (m-codes exist nowhere today),
**E018** (first free flat code above the live max E017), **E019**. The addendum's own
instruction — re-derive before coding — was followed and still holds at `2026.10.30-23`.

### 1.1 `M017` — the mint-time admission gate (new: `genome tadopt` + a `transients` table)

`cmd_plan`/`cmd_audit` (src/14_core_commands.py, `cmd_plan` at the top) mint
unconditionally today: they `mkdir`, build `YYYY-MM-DD-slug.md` from `PLAN_TPL`/
`AUDIT_TPL`, and write. Nothing asks whether the last plan's durable knowledge landed.

Build order, each step gated by a case in `scripts/test_genome.py` (which is where the
38 cases live — see `p1_kernel`, `p2_kinds`, `kb_registry` for the shape):

1. **`genome tadopt <path>`** — adopt an existing plan/audit as a `transients` row. This
   must exist first, because without it the gate is a wall between a fleet and its own
   history: every repo already has plans (this one has 3).
2. **The transients register.** Back it with `.genome/kb.sqlite` (the protocol's write
   model). Note the interaction the protocol did not flag: `close` hardcodes
   `.genome/**` into its never-commit list (line ~2330) and `.gitignore` already carries
   `.genome/`, so a sqlite write-model is machine-local by construction — which is correct
   for state and wrong for durable knowledge. The protocol answers this (rendered read-view
   stays in git, state does not); say so in the record rather than discovering it later.
3. **The gate itself** — refuse to mint when a `transients` row lacks an approved
   disposition, or when the minting agent holds an active workflow/todo row. `--force`
   with a recorded reason lands in the feed **if the repo runs the `agents` module**; this
   repo runs `core` + `records` only, so the reason lands in the worklog instead.

### 1.2 `E018` — lint-time detection of an unregistered dated plan/audit

The operator's wording is "when a new file **has been detected**", which is a detection
check, not a mint-time gate: agents create files with `write`, not `genome plan`. Lint
already walks `docs/plans` / `docs/audit` with a `dated_pattern` (E004 fires on a file
without a stamp; `README.md`/`INDEX.md` are exempt). Extend that walk: a dated file with no
`transients` row is E018, naming the file and the fix (`genome tadopt <path>`, or delete).

**Measured proof this fires on real repos:** this repo's own `docs/plans/2026-10-27-*.md`
and `2026-10-28-*.md` are invisible to lint today (they pass; they were minted by the CLI,
so nothing complains). After E018 they must all be adopted — which is the back-fill the
protocol's ratification list asks about, and it is small here: 3 files.

### 1.3 `E019` — one active workflow/todo row per agent

The schema's `UNIQUE INDEX idx_active_per_agent ... WHERE status IN (...) AND kind IN
('workflow','todo')` makes this impossible through the CLI, but lint must catch rows that
predate adoption or were hand-edited. Live measurement of today's hole (the audit's probe,
re-derived): `genome claim` guards per-item (`claimed-by X` in the notes cell) but nothing
stops one agent holding items in two boards. `E008` already covers "in-progress without a
well-formed claim"; E019 is the cross-board count.

### 1.4 The vocabulary change, and it is a law change

`consolidating` joins `STATUS_VOCAB` — but `STATUS_VOCAB` is read by E002, by `cmd_status`,
by `emit_status`'s zone, and by `register_summary`. Measured today:
`('open','in-progress','done','rejected','blocked')`. Adding a word changes every repo's
register rendering. **This is a ratification item, not an implementation detail** — see §
"What is not this seat's". Implement it last in Tier 1, so a partial landing is still
usable.

**Exit of Tier 1:** three new codes shipped, `references/lint-rules.md` carries their rows
(the table is the one a reader checks), `test_genome` gains one case per gate, and
`TODO.md` PQ-2/PQ-10 close with the commit sha as evidence.

## Tier 2 — packaging, measurement, and the two traps (PQ-3, PQ-4, PQ-5, PQ-8)

### 2.1 PQ-3 — the sdist does not ship the CLI file

Measured from `dist/project_genome-0.1.0.tar.gz` (59 files): it carries
`project_genome/__init__.py`, `__main__.py`, the whole `scripts/` + `src/` +
`references/` tree — and **no `project_genome/_genome.py`**. That path exists only in the
wheel, via `[tool.hatch.build.targets.wheel.force-include]`. So an sdist install falls back
to `<repo>/scripts/genome` at runtime (`__init__.py`'s `_cli_path()`), which works while
the source tree is present and quietly breaks on a wheel-less platform whose source tree was
deleted after the build.

Two honest exits, and one must be chosen rather than drifted into: (a) add the same
force-include for the sdist target, or (b) state in `docs/PUBLISHING.md` that the wheel is
the only supported install. `test_package_modes.py` pins the *current* behaviour (its case
`sdist_install_runs_and_matches_the_wheel` asserts the fallback produces identical bytes),
so whichever is chosen, that case is where the decision becomes a test.

### 2.2 PQ-4 + PQ-5 — the measurement traps, closed as rules

`test_package_modes.py` run from the repo root resolves the local `project_genome/`
ahead of site-packages, so an "installed" venv may be measuring the source tree. And a
stale `dist/` fails byte parity (measured today: a 05:34 `dist/` next to an 08:48
`scripts/genome` failed; after `uv build` at 08:55 it passed 5/5). Both are now written
into `docs/RUNBOOK.md`; the remaining work is to make them uncircumventable: run the
packaging suites from a neutral cwd in `genome.toml`'s `[core] gate`, and add the
`uv build` rung before them in the documented gate sequence.

### 2.3 PQ-8 — the audit this outline's evidence will be cited from

`docs/audit/` holds one audit (2026-10-28). This outline's own § "The measured state" is
the next one's evidence; promote it, dated, after Tier 0 executes — not before, because
the fleet's version delta is one of its two headline figures and Tier 0 changes it.

**Exit of Tier 2:** `pip install` from either artifact produces identical CLI bytes, the
packaging gate is honest from any cwd, and the audit names both.

## Tier 3 — what is not this seat's

Each item is named, with the one sentence that unblocks it. None is answered here.

1. **The fleet dispatch (`--apply`, 77 repos).** Operator's call, per the 2026-10-30
   standing ruling on fleet-wide rewrites. `genome installs upgrade --apply` is the
   command; its dry run is the evidence.
2. **`consolidating` joining `STATUS_VOCAB`.** The protocol's ratification item 1, and it
   changes every repo's register rendering (measured: 5 statuses today, read by E002,
   `cmd_status`, `emit_status`, `register_summary`).
3. **Thresholds** — compact at 400 lines / 14 days, scratch TTL 7 days (protocol
   ratification item 2). Implement as config with these defaults, not hardcoded.
4. **Back-fill policy** — adopt-or-triage for `transients` (ratification item 3). 3 files
   here; operant's own count is 45 plans / 33 audits.
5. **`--force`'s escape hatch** — keep or drop (ratification item 4).
6. **The vendored-copy convention's replacement** — the PATH install (ratification item
   5); `install.sh` already does it (`0151979` + `82c7211`), so the row is about the
   remaining vendored copies, not about the installer.
7. **E202's default** — the audit's finding 1: a quarantined figure quoted in
   `docs/audit/**` is *not* detected by default. Measured 2026-10-30 on a scratch repo:
   with no `quarantine_surfaces` key, the sweep is `research_surfaces` = `[state, agents]`
   default, and a struck figure quoted in an audit file passes lint clean; widening the key
   to `["docs/audit/*", "docs/handoff/STATE.md"]` fires E202 on both. The docstring says
   "plus every skill reference and audit" — the code does not do that. One-line fix,
   operator's call per the audit's own § 6.
8. **Publication** — `docs/PUBLISHING.md`; a credential and one command.
9. **The evals run** — 16 graded scenarios needing a harness caller, not a shell.

## Completion criteria

1. `installs verify` exits 0, or exits 2 naming only deliberate, owned divergences.
2. M017 / E018 / E019 ship with a case each, their rows in `references/lint-rules.md`,
   and the frontier re-derived in the same commit that mints them.
3. `pip install` from the sdist and from the wheel both produce a CLI byte-identical to
   `scripts/genome`, or `PUBLISHING.md` says which artifact is supported.
4. The packaging gate runs clean from any cwd and after any `dist/` age.
5. Every produced figure names its command; every closed register row names its commit.
