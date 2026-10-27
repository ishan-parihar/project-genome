# KB MANAGEMENT PROTOCOL — SQLite state, admission gates, one-active-per-agent

**Status:** upgrade proposal for `project-genome`. Nothing here is implemented yet.
**Author:** the operant KB-management session, 2026-10-27/28 (feed F0109/F0110; the
operant-side plan of record is
`docs/plans/2026-10-28-kb-management-protocol-v2-sqlite-state-gates-one-active-per-.md`
in the operant repo — this document is the same proposal restated at the
SKILL level, where the operator ratifies it for every adopting project, and
adds the detection-side lint).
**Applies to:** every project under genome management that opts into the
`kb` module this proposal defines.

---

## The problem this solves

A genome-managed project's four churn surfaces — WORKLOG, the findings
ledger (BUGS), the register (TODO), and WORKFLOW boards — are today four
markdown formats with four hand-rolled writer paths. The costs, all
observed in live development (evidence in the operant survey
`docs/audit/2026-10-27-kb-surface-management-the-operant-survey-and-its-long-horizo.md`,
limitations L1–L6):

1. **Concurrency is convention, not constraint.** Two agents posting to the
   feed between each other's read and write produced duplicate auto-labels
   (two `[F0096]` in one file, recorded in that project's feed). Workflow
   boards multiplied: 6 boards accumulated, 5 of them long finished, still
   listed as live until a human swept them.
2. **State and file are the same thing.** An append-only worklog can never
   shrink; a dated-frozen plan can never carry a status. So the two facts
   every long-horizon project needs — "this is current" and "this is
   finished" — have no machine representation anywhere.
3. **Minting is ungated.** A new plan or audit file can be created while
   five predecessors sit undisposed. Nothing asks the one question that
   keeps a KB honest: before you add a document, where did the last one's
   knowledge GO?

The operator's ruling this proposal implements, verbatim from the request:
"WORKLOG/BUGS/TODO/WORKFLOW like elements [must be] manageable through the
genome CLI and sqlite database with a standardized schema… plan/audit
files must throw an error when a new file has been detected without
approving the status of existing files… only one active file per agent
must be allowed in a WORKFLOW/TODO."

## The principle

**SQLite is the write model; markdown is the read model.** Agents and humans
keep reading exactly the files they read today. Every mutating verb
(`genome log/post/bugs/claim/done/…`) writes a row, then re-renders the
file from the rows. The file stops being the source of truth and becomes
its projection — which is what makes compaction, concurrency, and lifecycle
state possible without touching a single reader.

## The schema (the standardized grammar)

One database per project: `.genome/kb.sqlite` (git-ignored — the genome's
`never_commit` already carries `.genome/**`). Six tables, one grammar:

```sql
CREATE TABLE entries (          -- the four churn surfaces, one row shape
  id TEXT PRIMARY KEY,          -- W-0007 | F0103 | bugs-id | rg-1364-001 | T-003
  kind TEXT NOT NULL,           -- worklog | feed | bugs | todo | workflow | transient
  agent TEXT,                   -- claiming agent; NULL = unclaimed
  status TEXT NOT NULL,         -- open in-progress done rejected blocked consolidating
  title TEXT NOT NULL,
  body TEXT,
  evidence TEXT,                -- terminal rows: '→ [YYYY-MM-DD] path-or-iter'
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_kind_status ON entries(kind, status);
CREATE UNIQUE INDEX idx_active_per_agent ON entries(agent)   -- ONE active per agent
  WHERE status IN ('open','in-progress','consolidating')
    AND kind IN ('workflow','todo');
CREATE TABLE transients (       -- the lifecycle register for plans/audits/scratch
  path TEXT PRIMARY KEY, kind TEXT, status TEXT NOT NULL,
  consolidation_target TEXT,    -- where the durable knowledge landed
  evidence TEXT
);
CREATE TABLE sync_state (path TEXT PRIMARY KEY, mtime TEXT, sha TEXT);
```

Statuses move through the existing vocabulary plus one new state,
`consolidating`: shipped code whose durable knowledge is being folded into
the project's core-architecture docs. Terminal `archived` (for transients)
is unreachable without either a `consolidation_target` or an explicit
`nothing-durable` evidence cell — the forcing function that keeps
"implemented" from meaning "forgot to write down."

## The gates

**M017 (mint-time, hard):** `genome plan` / `genome audit` refuse to mint
when any `transients` row lacks an approved disposition, or when the
minting agent already holds an active workflow/todo row. `--force` with a
recorded reason exists for genuinely urgent audits; the reason lands in
the feed.

**E017 (lint-time, hard):** the operator's "when a new file **has been
detected**" wording is a detection check, not only a gate on the minting
command — agents can create files with `write`, not `genome plan`. Lint
walks the plans/audit globs, and a dated file with no `transients` row is
an error naming both the file and the fix (`genome tadopt <path>` adopts
it, or delete it). This makes the register complete regardless of how the
file arrived.

**E018 (lint-time, hard):** more than one active workflow/todo row per
agent — normally impossible via the UNIQUE index, but lint catches rows
that predate adoption or were hand-edited into the file.

## Migration and back-fill

`genome migrate kb` parses the four markdown files (formats unchanged from
today), inserts rows, and re-renders to prove the round trip. Idempotent;
`--check` diffs file-vs-database and fails on drift either way. Operant's
measured start state for the record: worklog 426 lines / 102 feed entries /
45 plans / 33 audits / 6 boards (5 of them done — swept by hand this
session; `migrate` would have found the same five).

## What this deliberately does not do

- No auto-archival: the machine proposes (M017/E017/E018, doctor
  listings), the agent disposes. Law 5 (claim before work) stays.
- No renumbering of anything already published (the duplicate feed labels
  stay; the schema prevents the next one).
- No new module required for reading: every existing consumer of the
  markdown files works unchanged, because the files still exist and still
  carry the same text.

## Ratification points for the operator

1. `consolidating` joins `STATUS_VOCAB` at the skill level (every project).
2. Thresholds: compact at 400 lines / 14 days; scratch TTL 7 days.
3. Back-fill: adopt 45 plans + 33 audits as `open` rows, or triage first.
4. E017's `--force` escape — keep or drop.
5. The vendored `scripts/genome` copy convention: this proposal replaces
   it with the PATH install (`install.sh` now migrates pre-installer
   copies and wires `~/.local/bin/genome` — landed 2026-10-28, commits
   `0151979` + `82c7211`).
