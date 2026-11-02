# Remaining implementation gaps — the execution outline

Dated-frozen: published **2026-11-01**. A plan that changes is a new plan (or declare it
in genome.toml `core.living_plans` and keep a 'Resume here' section).

## Contents

| § | what it holds |
|---|---|
| [Why this outline exists](#why-this-outline-exists) | what changed since 2026-10-30, and the five claims re-measured today |
| [Mechanism](#mechanism) | why the tiers are ordered this way |
| [Gates / success criteria](#gates--success-criteria) | the five rules this plan is judged by |
| [Tier 0](#tier-0--the-vendored-copy-its-two-reverts-and-the-convention-pq-1-pq-9) | the estate census, the two reverts, the convention decision (operator's) |
| [Tier 1](#tier-1--the-protocols-three-gates-renumbered-from-the-shipped-frontier-pq-2-pq-10) | M017, E019, E020 — renumbered, because E018 is taken |
| [Tier 2](#tier-2--the-stale-dist-trap-closed-in-the-gate-pq-4-pq-5-pq-3) | the gate builds before it measures; the sdist question; the missing E018 row |
| [Tier 3](#tier-3--what-is-not-this-seats) | the nine operator calls |
| [Completion criteria](#completion-criteria) | what "done" means, as five measurable lines |

**Owner:** `docs/plans/` (this document). **Gate:** `python3 scripts/genome lint --all` returns
0 errors. **Register:** every row below traces to a `PQ-` row in `TODO.md`, and each step
closes its row with `genome status <id> done --evidence`, not by editing it out.
**Supersedes:** `docs/plans/2026-10-30-remaining-implementation-gaps-outline.md`, whose Tier 0
and half of Tier 2 executed (the fleet passed), and whose Tier 1 numbering **collided with a
code this repo has since minted**. That document stays dated-frozen; this one is the live plan.
**Scope:** this repo (the kernel) and the fleet it governs. It does not supersede the two
dated-frozen proposals it sequences (`2026-10-28-KB-MANAGEMENT-PROTOCOL.md` + its addendum),
the upgrade-mechanism audit (`../audit/2026-10-30-UPGRADE-MECHANISM-AUDIT.md`), or the
operator's own publishing step (`../PUBLISHING.md`).

## Why this outline exists

The 2026-10-30 outline named ten gaps in tiers. Two days later its first tier is **done** —
the operator approved the fleet pass, all 76 vendored copies were swapped, and three defects
in the upgrade harness were found and fixed (one of them a dispatch that reported
`75 ok, 0 failed` over a fleet it had not touched). So the list below is not the old list with
new dates: it is what the old one, executed, actually left.

**Five things the old outline got wrong or could not have known, each re-measured today:**

1. **Its Tier 1 numbering is void.** It reserved **E018** for the protocol's lint-time gate.
   This repo shipped **E018** on 2026-11-01 for the schema_version gate (`E018 genome.toml is
   schema_version N; this CLI knows 2`). The addendum's own rule covers this: *"If a future
   genome version consumes E018/E019 before this protocol lands, shift to the next free flat
   codes and record the shift here the same way."* The frontier re-derived from the shipped
   script today is **E019 and E020 free**, E018 taken, M-codes still a brand-new namespace.
2. **Its headline figure for PQ-6 is stale.** The register says "16 evals and 108 fixtures".
   Measured from `evals/evals.json`: **16 evals** (ids 5–20) with **86 assertions** — so `108`
   is wrong twice: there is no fixture *count* (`fixtures` is a build glob in the manifest:
   `python3 evals/make_fixtures.py /var/tmp/genome-eval new old`), and the assertion total is
   86, not 108. A number cited from the register rather than measured.
3. **PQ-3's mechanism is wrong, though its outcome is right.** The sdist (59 files) carries no
   `project_genome/_genome.py` — but installing it **does** produce one, because pip builds a
   wheel from the sdist at install time and the wheel's `force-include` applies. Measured:
   a fresh sdist install from a neutral cwd resolves `site-packages/project_genome/_genome.py`
   and reports `genome 2026.10.31-40`, sha `11bf845430e0` — **identical to the wheel and to
   the live `scripts/genome`**. So the fallback `__init__.py`'s docstring describes is not the
   path a modern pip takes. The real exposure is a client that installs an sdist *without*
   building (a `--no-build-isolation`-style legacy path), which is a documentation risk, not a
   shipping defect.
4. **PQ-5 caused a live failure this session**, and PQ-4's diagnosis of it is wrong. Run from
   the repo root, `test_package_modes` failed with
   `the sdist and the wheel install DIFFERENT CLI bytes: a9263e5bbe53 vs 11bf845430e0` — the
   stale `dist/` sdist, carried from 00:17, still held the **`-34`** build (sha
   `a9263e5bbe53`, 425,643 bytes). Run from `/` it failed **identically**, so the cwd is not
   the cause; after one `uv build` (07:51) the same case passes from a neutral cwd and the
   whole suite is green. **PQ-4 and PQ-5 are one trap with two wrong diagnoses: the stale
   `dist/`, not the shadowing.**
5. **The fleet is not uniformly current, and no kernel change caused it.** 75 of 76 vendored
   copies hold `2026.10.31-40`; `pioneer-qf/bin/genome` and `holon/holon/vendor/genome.py`
   (+ its `scripts/genome` symlink) both sit at `2026.10.27-13` again, sha `979625c8aba8` /
   the `-13` bytes. Both were reverted by an operation **outside the dispatch**: pioneer-qf's
   reflog shows `reset: moving to HEAD` at 07:06 local (01:36 UTC), after its 06:01 commit;
   holon's `holon/vendor/genome.py` was rewritten at 07:40 local with no commit on top of a
   HEAD from 22:56 UTC. Neither is a bug in the upgrade. **It is the vendored-copy convention
   meeting an actively-owned repo**, and it is the largest gap on this list.

The measured state, all of it re-derived on **2026-11-01** at VERSION `2026.10.31-40`
(`scripts/genome` 7,516 lines, 27 `src/` modules, sha `11bf845430e0`):

| fact | measurement |
|---|---|
| suites | `test_genome` **39/39**, `test_package` 8/8, `probe-outline-languages` 9/9, `check_ps1` parity ok at 412 lines, `test_package_modes` green **after** `uv build` |
| lint / doctor | `lint: 0 error(s), 1 warning(s)` (W010, the worklog's own TOC), `doctor: 0 finding(s)` |
| live E-codes | flat E001–E018 emitted (max **E018**), E019/E020 free, M-codes absent; 14 flat + family codes |
| the fleet | **75/76 vendored copies at `2026.10.31-40`**; `pioneer-qf` and `holon` at `2026.10.27-13` (external reverts, above); `installs verify --against-shipped` names those two BEHIND |
| the estate's lint | `fleet lint`: **82 KB(s), 1 error, 102 warnings, 1 with no CLI** — the error is pioneer-qf's `E301` |
| packaging | wheel `project_genome/_genome.py` == `scripts/genome` (437,617 bytes, `11bf845430e0`); sdist (59 files) has no `_genome.py`, pip builds it, result matches; sdist's own `scripts/genome` when `dist/` is stale is the `-34` build |
| evals | `evals/evals.json`: 16 evals (ids 5–20), **86 assertions**; `evals/fixtures/` holds one vendored build dir; `grade.py` needs `<id> <repo>` and dies on no args (IndexError, exit 1–2) |

## Mechanism

**Tier 0 is the convention itself, and it is the only tier that can fail twice.** Every other
gap on this list was closed by writing code and re-running a suite. The vendored copy is a file
inside someone else's repository, so the upgrade that fixes it is undone by their next
`git checkout`, and the dispatch's own guard *refuses* to overwrite a copy that differs from
its record. Measuring it, proving the revert, and deciding what the convention should be is
the work — and the operator's ruling is required, because the alternative (a PATH install)
was already built (`install.sh`, `0151979`) and declined as the sole path in the protocol's
ratification item 5.

**Tier 1 is the protocol's gates, renumbered once and correctly.** M017 is safe (no M-code
exists). The two lint codes are E019 and E020 because E018 is taken, and the shift is exactly
what the addendum line 63 instructs. Nothing else about them changes.

**Tier 2 is the stale-`dist/` trap, closed as a rule the gate runs.** The case that failed did
so because nothing rebuilt `dist/` before measuring it. The fix is not discipline-in-a-doc:
the gate's first rung becomes `uv build`, and the packaging suite asserts the artifact it
measures is the one built from the current tree.

**Tier 3 names what is this seat's alone.** Nothing in Tier 3 is answered here.

## Gates / success criteria

1. `python3 scripts/genome lint --all` → 0 errors, at every commit this plan produces.
2. Every produced figure names the command that produced it on the same line.
3. Every register row transitions via `genome status <id> <state> --evidence <path>`; a
   terminal row carries `→ [YYYY-MM-DD] <evidence>` in its verdict cell (E003 reads that cell).
4. No open operator ask is answered by this plan's execution.
5. A change to another repo's working tree is recorded as a change to that repo, with that
   repo's reflog as the evidence, and is listed for its owner rather than silently re-applied.

---

## Tier 0 — the vendored copy, its three un-current rows, and the convention (PQ-1, PQ-9)

> **Corrected 2026-11-02.** The census below measured 75 of 76 and missed one. Running
> `installs verify --against-shipped` for the first time (Tier 0.1's step 1, never executed)
> names **three** un-current rows, not two, and `holon` is not among the names it prints at
> all. The measurement was wrong for two reasons: an unrun check, and a table built from the
> registry's recorded `version` instead of from disk. See the 2026-11-02 (later still)
> worklog entry for the full re-measurement, including that **operant's own worklog already
> ruled on its copy and the answer is option 3**.

### 0.1 Establish the estate's true version census, and name who moved each copy

Measured today (command: `sha256sum <repo>/scripts/genome | cut -c1-12` per registered row,
against `~/.agents/skills/project-genome/scripts/genome`):

| copy | version | sha | how it diverged |
|---|---|---|---|
| 73 vendored rows | `2026.10.31-40` | `11bf845430e0` | — (the 2026-11-01 apply) |
| `pioneer-qf/bin/genome` | `2026.10.27-13` | `979625c8aba8` | reflog `reset: moving to HEAD` 07:06 local, after its 06:01 commit. **A `kb` row, not vendored** — an activated genome (no `scripts/` copy at all) |
| `holon/holon/vendor/genome.py` (+ a `scripts/genome` **symlink** into it) | `2026.10.27-13` | the `-13` bytes | file rewritten 07:40 local, no commit above a 22:56-UTC HEAD. Not printed by `installs verify` at all — the symlink target is a question that check does not ask |
| `agentic-harness/operant/scripts/genome` | `2026.10.21-2` | `ee03491721ed` | **committed** at `-21-2` with a clean working tree: never reverted, never upgraded. Rollback artefacts `.genome/genome.pre-upgrade` (`-39`) and `genome.pre-2-full` from 2026-11-01 show an upgrade run that reached `-39` and was rolled back. Nine releases behind, 5 `fleet-hold-*` WIP branches, 3 stashes, 12 uncommitted crate files |

**This is not a dispatch failure and must not be recorded as one.** The disk-gate change
(`_version_of` after the swap) reads `landed != ref` and would have fired; it did not fire at
the time because the swap had genuinely landed. The reverts happened afterwards, from outside.
What the estate *did* expose is a blind spot in the other direction: **there is no check that
a copy is still current after the run that made it so**, which is what `installs verify
--against-shipped` run at any later time is for — and it is the check that found both.

**Do this, in this order:**

1. `genome installs verify --against-shipped` over the whole estate — it names exactly the two
   BEHIND rows above. Capture its verbatim output as the evidence for PQ-1's reclassification.
2. For each of the two: record the reverting operation from **that repo's** reflog (above is
   the measurement), and leave the working tree alone. Re-applying the dispatch over an owner's
   checkout is the act the vendored-copy guard exists to prevent.
3. Report both rows to their owner through the normal channel for that repo. The gate this
   plan ships (Tier 2) is what tells them it happened without either of us re-running a write.

**Exit:** the census above is a dated, reproduced table; PQ-1 and PQ-9 close or are restated
against it, with the operator's ruling on the convention as the remaining half.

### 0.2 The convention decision — this is the operator's call, and the row is already written

The protocol's ratification item 5 proposed replacing the vendored copy with a PATH install;
`install.sh` does exactly that (`0151979` + `82c7211`) and the kernel itself is installed on
PATH as a uv tool. The 76 remaining vendored copies are the question, and their reverts
today are the argument. The three exits, with the one measurement each needs:

1. **Keep vendoring, and accept periodic drift.** Then `installs verify --against-shipped`
   becomes a scheduled check, not a one-off — the two rows above prove it is needed. Cost:
   a recurring report the operator must read.
2. **Keep vendoring, but the manifest records the owner's intent.** A `vendored-repo` note per
   row (the manifest already carries `note`), so a writer knows a repo is actively owned before
   a dispatch touches it. Small, and it turns today's surprise into a named expectation.
3. **Migrate to PATH installs (`PATH-genome` + a thin shim).** The protocol's item 5. It
   removes the revert class entirely and makes the estate's version a single fact. It is a
   change to 76 repos' tooling and needs their owners' consent — but **one owner has already
   consented, in writing, with a measurement.** operant's 2026-10-28 worklog ruled on its own
   copy: *"the vendored scripts/genome copy is fork-without-intent (2026.10.21-2 vs
   2026.10.22-17, 485 diff lines) and should be deleted in favor of the PATH install +
   `genome upgrade`"*, and that PATH install already works (`~/.local/bin/genome` → the uv
   tool). So the cost is not 76 consents; it is 75, one of which is already resolved, and
   operant's nine-release gap is the strongest single argument for the option.

**Exit:** the operator names 1, 2, or 3 in `docs/kb/ASKS.md` (as a ruled row, with an
`--applied` owner path). Until then Tier 0's only code change is the census note of 0.1.

### 0.1b The census, as measured on 2026-11-02 from disk and HEAD

The table above was written by narrating the plan's command and reading the registry's
`version` column, which is a recorded claim. Measured properly — `sha256sum` per
registered row against `~/.agents/skills/project-genome/scripts/genome` (resolving
symlinks), then `git show HEAD:<path>` and `git status --short` for the same path —
the estate is:

```
reference: 11bf845430e0  2026.10.31-40
rows: 85   current=11  behind=3  nofile=3  uncommitted=68
```

| class | count | what it means | does `installs verify --against-shipped` see it? |
|---|---|---|---|
| current | 11 | disk == the shipped bytes, git agrees | yes |
| **uncommitted** | **68** | **disk holds `2026.10.31-40`; HEAD holds an older `scripts/genome` with ` M` in `git status`** | **no** |
| behind | 3 | `operant` (committed, clean, `2026.10.21-2`), `pioneer-qf` (a `kb` row), and `~/.local/bin/genome` (the uv tool, `8f6a1f0661da`) | yes |
| nofile | 3 | two `skill` rows that are directories with no CLI, and the meta-root `kb` row with no local CLI | n/a |

**The 68 uncommitted rows are the finding, and they dissolve this tier's premise.** The
`-40` dispatch to those repos landed correctly and completely — the guard's write was
right — and then nothing committed it. In `webdev/webdev-portfolio` the uncommitted
diff is `1 file changed, 1639 insertions(+), 16 deletions(-)`, disk version
`2026.10.31-40`, and `git status` → ` M scripts/genome`. The copies are not
gitignored.

So there is no revert class to instrument: `pioneer-qf` is the one genuine revert;
`holon` is current-on-disk-but-uncommitted (not the revert the first census claimed);
`operant` is the never-upgraded class. **The guard verifies that a write landed, and
nothing verifies that it stayed landed** — 68 repos are one `git restore`, `checkout .`,
rebase or `clean -fd` away from a nine-release regression, while `installs verify`
reports them healthy.

Not decided here, because it is 68 owners' call: whether each uncommitted row should be
committed, and whether `scripts/genome` should be gitignored in repos that treat it as
build output. The reproducible measurement (disk / HEAD / registry claim, per row) is
`census.py` under `/var/tmp/ishanp-agentic/`, and it writes nothing.

## Tier 1 — the protocol's three gates need the `kb` module first (PQ-2, PQ-10)

> **Corrected 2026-11-02.** This section previously read "renumbered from the shipped
> frontier". Measured against the code, that framing is wrong: the three codes rest on a
> store that does not exist. `modules = ["core", "records"]`; the `kb` subcommand that
> exists is the machine's KB registry, not this protocol's module; the protocol itself
> says *"Status: upgrade proposal. Nothing here is implemented yet"*; `grep -rh 'f"M0'
> src/*.py` is **0**, so M017 would be the first M-code, not the next; and
> `grep -rl transients src/` is **0 files**. Read this tier as: build `tadopt` and the
> transients register first, then the gates on top. See the 2026-11-02 (later)
> worklog entry for the full measurement.

Numbering is re-derived, not remembered, and it differs from the 2026-10-30 outline because
**E018 has been taken since**. Command: `grep -oE 'E0[0-9]{2}' scripts/genome | sort -u` (live
max E018, 2026-11-01), plus `grep -c 'f"M0' src/*.py` (zero M-codes).

### 1.1 `M017` — mint-time admission (unchanged; the number was never in use)

`cmd_plan` / `cmd_audit` mint unconditionally: they build `YYYY-MM-DD-slug.md` from a template
and write, with nothing asking whether the last plan's durable knowledge landed. Build order:

1. **`genome tadopt <path>`** — adopt an existing plan/audit as a `transients` row. It must
   exist first, or the gate is a wall between a repo and its own history (this repo has 4 plans).
2. **The transients register**, backed by `.genome/kb.sqlite` per the protocol's write model.
   Note the interaction the protocol did not flag: `close` puts `.genome/**` in `never_commit`
   and `.gitignore` already carries it, so a sqlite state file is machine-local by
   construction — correct for state, wrong for durable knowledge. The protocol answers this
   (rendered read-view stays in git, state does not); say so in the record, not later.
3. **The gate** — refuse to mint when a transients row lacks an approved disposition, or when
   the minting agent holds an active workflow/todo row. `--force` with a recorded reason lands
   in the feed **if the repo runs `agents`**; this repo runs `core` + `records`, so the reason
   lands in the worklog. M017 is therefore emitted through the M-code namespace this repo does
   not yet read in lint — the module table in `AGENTS.md` rule 8 is where a reader checks.

### 1.2 `E019` — lint-time detection of an unregistered dated plan/audit (was E018)

The operator's wording is "when a new file **has been detected**" — a detection check, not a
mint-time gate, because agents create files with `write`, not `genome plan`. Lint already walks
`docs/plans` and `docs/audit` with `dated_pattern` (E004 fires on a missing stamp;
`README.md`/`INDEX.md` are exempt). Extend that walk: a dated file with no transients row is
E019, naming the file and the fix (`genome tadopt <path>`, or delete).

**Measured proof this fires on real repos:** this repo's own `docs/plans/2026-10-27-*.md` and
the two `2026-10-28-*.md` files are invisible today — they pass, because the CLI minted them
and nothing asks whether a row exists. After E019 all four must be adopted. That back-fill is
the protocol's ratification item 3 and it is small here; operant's equivalent is 45 plans /
33 audits, which is why the decision belongs to the operator before the gate is global.

### 1.3 `E020` — one active workflow/todo row per agent (was E019)

The schema's partial `UNIQUE INDEX` makes this impossible through the CLI; lint must catch rows
that predate adoption or were hand-edited. E008 already covers "in-progress without a
well-formed claim"; E020 is the cross-board count. The live hole is measured in the 2026-10-30
outline §1.3 and has not changed: `genome claim` guards per item, nothing guards per agent
across boards.

### 1.4 The vocabulary change is still a law change

`consolidating` joining `STATUS_VOCAB` changes every repo's register rendering. Measured:
`STATUS_VOCAB` is read by E002, `cmd_status`, `emit_status`'s zone, and `register_summary`.
Implement it **last** in Tier 1 so a partial landing is still usable, and only once ruled.

**Exit of Tier 1:** `M017`/`E019`/`E020` shipped, one case each in `scripts/test_genome.py`,
their rows in `references/lint-rules.md` (the table is 14 flat rows today and carries no E018
row yet — the E018 that shipped on 2026-11-01 has **not** been added to it, and that omission is
its own small gap, recorded as 2.3), and PQ-2/PQ-10 closed with the commit sha.

## Tier 2 — the stale-`dist/` trap, closed in the gate (PQ-4, PQ-5, PQ-3)

### 2.1 PQ-5 first: it is the one that produced a live failure

`genome.toml`'s `[core] gate` today is, verbatim:

```
gate = "python3 scripts/test_genome.py && python3 scripts/test_package.py && python3 scripts/test_package_modes.py && python3 scripts/build.py --check && python3 scripts/check_ps1.py"
```

It runs `test_package_modes.py` — the suite that measures `dist/` — **without building it
first**, and it fails on that stale artifact (measured above: `a9263e5bbe53 vs 11bf845430e0`,
reproducible from both the repo root and `/`, cleared by one `uv build`). A gate that fails on
a file it never refreshed is a gate that reports the build system's state as the code's.

**The fix is one rung, and it makes the trap uncircumventable:**

```
gate = "python3 -m uv build --wheel --sdist >/dev/null && python3 scripts/test_genome.py && ..."
```

then the case `sdist_install_runs_and_matches_the_wheel` gains one assertion — that the
artifact it opened is newer than `scripts/genome` — so a stale `dist/` fails with
**"rebuild dist/ first"** rather than with two hashes it cannot explain. That is the whole of
PQ-5, and it also leaves PQ-4's cwd claim testable rather than assumed.

### 2.2 PQ-4: re-measure the cwd claim, because today it did not hold

The register and the old outline say the modes suite is honest only from a neutral cwd. Today
it failed **identically** from `/` and from the repo root, because the cause was the stale
`dist/`. So the sentence should be: *run it from a neutral cwd **and** with a fresh `dist/`* —
two conditions, both measured, not one remembered. Add a case that runs the suite from `/` so
the claim is exercised rather than asserted in a doc. If, with 2.1's freshness assertion in
place, the repo-root run then passes too, the cwd half of PQ-4 is closed as a non-issue and the
row records that.

### 2.3 PQ-3 restated, and `references/lint-rules.md`'s missing E018 row

The sdist omits `project_genome/_genome.py` (measured, 59 files) and a modern pip builds it
anyway (measured, identical bytes). Two honest exits, one to be chosen rather than drifted
into:

- (a) add the same `force-include` under `[tool.hatch.build.targets.sdist]`, which makes the
  sdist self-sufficient for a no-build client; or
- (b) state in `docs/PUBLISHING.md` that the wheel is the supported artifact, and *why*, with
  today's measurement as the sentence's evidence.

Either way, the `__init__.py` `_cli_path()` docstring's "expected `{_CLI}` ... Reinstall" is
the advice a reader sees in the case it describes, and it should name the sdist reality.

Separately and small: **E018 shipped on 2026-11-01 and has no row in `references/lint-rules.md`**
(measured: 14 flat E rows, none for E018). The table is the one a reader checks, so a shipped
code with no row is a documentation gap of the same class this plan exists to close. Add the
row in the same commit that mints E019 — frontier and rows together, as the addendum asks.

**Exit of Tier 2:** the gate builds before it measures; a stale `dist/` fails by name; the
sdist question is answered in one of two ways, in writing.

## Tier 3 — what is not this seat's

Named, with the one sentence that unblocks each. None is answered here.

1. **The vendored-copy convention (0.2).** Replace it, or accept and instrument drift. It
   changes 76 other repos and the protocol's ratification item 5 already framed it.
2. **The two reverted copies (0.1).** Re-applying the dispatch over an owner's checkout is
   the act the guard prevents; their owners are the only ones who can land the swap.
3. **`consolidating` in `STATUS_VOCAB`.** Ratification item 1; changes every register rendering.
4. **Thresholds** — compact at 400 lines / 14 days, scratch TTL 7 days (item 2). Implement as
   config with these defaults, not hardcoded.
5. **Back-fill policy** — adopt-or-triage for transients (item 3). 4 files here, 45+33 in operant.
6. **`--force`'s escape hatch** — keep or drop (item 4).
7. **E202's default** — audit finding 1: a quarantined figure quoted in `docs/audit/**` is not
   detected by default (`quarantine_surfaces` defaults to `research_surfaces` = state + agents).
   One-line fix, the audit's own § 6 leaves it to the operator.
8. **The evals run (PQ-6)** — 16 evals, 86 assertions, `grade.py <id> <repo>` + a harness
   caller. This seat records that it has not run them; the grade for `2026.10.31-40` is unwritten.
9. **Publication** — `docs/PUBLISHING.md`; a credential and one command.

## Completion criteria

1. `installs verify --against-shipped` exits 0, or exits 2 naming only the divergences whose
   owners have been told and whose reflog is recorded.
2. M017 / E019 / E020 ship with a case each, their rows in `references/lint-rules.md`, E018's
   row backfilled, and the frontier re-derived in the same commit that mints them.
3. `[core] gate` builds before it measures, and a stale `dist/` fails naming the rebuild.
4. The sdist question is answered in writing, with the measurement that decides it.
5. Every figure above still names its command, and the census table in 0.1 still measures true.
