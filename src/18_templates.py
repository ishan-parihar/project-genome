# ---------------------------------------------------------------- templates

def genome_toml(mods: list[str], gate: str) -> str:
    roles = [r for m in mods for r in MODULE_ROLES[m]]
    out = ["# genome.toml — modules on, role → path map, module settings. Edit freely.",
           "[genome]", f"schema_version = {SCHEMA_VERSION}", f"modules = {json.dumps(mods)}", "", "[paths]"]
    out += [f'{r} = "{DEFAULT_PATHS[r]}"' for r in roles]
    out += ["", "[core]", f'gate = "{gate}"            # build/test gate run by `genome close`',
            'worklog_form = "file"      # or "numbered" (worklog = a directory of NNNN-date-slug.md + INDEX.md)',
            'archive_form = "flat"      # or "generations" (archive/<generation>/ + README manifest, no tombstones)',
            "living_plans = []          # plans that evolve (phase rows, a 'Resume here' section)",
            '# resume = "docs/plans/<living-plan>.md#Resume here"   # what `genome wake` shows',
            "budgets = {}               # e.g. { \"AGENTS.md\" = 60000 } — bytes; entry surfaces stay cheap to read",
            "emitters = []              # extra commands `genome close` runs to regenerate derived files",
            "checklist = []             # judgement items `genome close` reminds you of",
            "never_commit = []          # globs `genome close` leaves out of the named-path commit list"]
    if "records" in mods:
        out += ["", "[records]", 'prefix = ""                # e.g. "PQF" → PQF-AD-001',
                'mode = "immutable"         # or "amendable" (dated ## Amendment sections)']
    if "research" in mods:
        out += ["", "[research]", f"classes = {json.dumps(list(CLASSES))}",
                "surfaces = []              # globs where every figure needs a class (default: state + agents)"]
    if "ops" in mods:
        out += ["", "[ops]", "owner_globs = []           # doc locations that must be listed in the ownership map",
                "link_surfaces = []         # docs whose backticked paths must exist",
                "link_prefixes = []         # e.g. [\"docs/\", \"scripts/\"]: any backticked path starting so is checked, dirs too",
                "code_globs = []            # code that must be reachable from a live surface",
                "code_roots = []            # files whose mentions make code live (bin/, tests/, ...)",
                'bulk_globs = ["*.parquet", "*.pkl", "*.npz"]', "max_bytes = 5000000",
                'secrets = []               # e.g. [".env:API_KEY", "~/.config/x/token"] — scanned in diffs, never printed',
                '# jobs = "bin/jobs status"   # shown by `genome wake`']
    return "\n".join(out) + "\n"


def agents_tpl(mods: list[str], gate: str) -> str:
    rows_ = [("what is this / how to build / the rules (for agents)", "this file"),
             ("what is this, how do I install and run it (for readers)", "`README.md`"),
             ("how does it work, in depth (for readers)", "`docs/`"),
             ("how the pieces fit together (the architecture)", "this file § Architecture"),
             ("where does the project stand right now", "`docs/handoff/STATE.md`"),
             ("what does a fresh agent read, in order", "`docs/handoff/README.md`"),
             ("what is left to do, and what was decided about each item", "`TODO.md`"),
             ("what did we ask the operator, and what did they rule", "`docs/kb/ASKS.md`"),
             ("how will we do X (plans)", "`docs/plans/`"),
             ("what was audited, what was found", "`docs/audit/`"),
             ("what was tried and rejected — do not re-litigate", "`docs/kb/CLOSED.md`"),
             ("exact commands, environment traps", "`docs/RUNBOOK.md`"),
             ("what happened, session by session", "`docs/kb/WORKLOG.md`"),
             ("superseded history", "`docs/archive/`")]
    if "records" in mods:
        rows_ += [("why X is the way it is (decisions) / what bit us (regressions)", "`docs/RECORDS.md`")]
    if "research" in mods:
        rows_ += [("which hypotheses were tested, and their verdicts", "`docs/kb/HYPOTHESES.md`"),
                  ("which figures must never be quoted again", "`docs/kb/QUARANTINE.md`"),
                  ("which confirmatory tests were frozen before running", "`docs/kb/PREREG.md`"),
                  ("where the measured numbers live", "`evidence/README.md`")]
    if "ops" in mods:
        rows_ += [("which doc owns which question (ownership map)", "`docs/INDEX.md`")]
    if "agents" in mods:
        rows_ += [("cross-agent messages, claims, mentions", "`docs/kb/feed.md`"),
                  ("in-flight work per workflow", "`docs/kb/workflows/`")]
    table = "\n".join(f"| {q} | {a} |" for q, a in rows_)
    return f"""# AGENTS.md — the entry contract

Orientation, the gate, and **which document owns which question**.
Start every session with `genome wake`; find an answer with `genome ask "<question>"`;
end every iteration with `genome close`.

## What this project is

(one paragraph)

## Architecture

(how the pieces fit together: the parts, what each is for, and how they connect.
The card's `architecture` class points here until a repo names a different owner.)

## Gate

```
{gate or "(declare the build/test gate in genome.toml [core] gate)"}
```

## Routing table — which document answers what

| question | answer lives in |
|---|---|
{table}

## Rules

1. One owner per question; amend the owner, never add a second.
2. Every document has a mutability class; append-only files only gain lines.
3. Nothing is deleted: superseded → `genome archive --reason`.
4. Terminal states name their evidence; numbers cite the artefact they came from.
5. Operator feedback amends its owner doc or record in the same session (`genome q rule ... --applied`).
"""


REGISTER_TPL = """# TODO — the register

One row per work item; rows update in place, verdicts append — never delete.
`genome status <id> <state> --evidence <path>` is the supervised transition.

| id | status | item / verdict | notes |
|---|---|---|---|
"""
ENTRY_TPL = """# Entry — what a fresh agent does, in order

1. `genome wake` — state, resume point, operator questions, jobs, health in one call.
2. `genome ask "<question>"` — the one section that answers it; read that range only.
3. Before work that touches a decision: `genome rec recon <keywords>` (prior art).
4. End of iteration: `genome close`.

**Stop and ask the operator** (record it with `genome q add`): (list the decisions that belong to them)
"""
STATE_TPL = """# State

Current snapshot only (no history: that is the worklog). The first `## ` block is
what `genome wake` shows.

## State — (date)
"""
RUNBOOK_TPL = ("# Runbook — exact commands, environment traps\n\n| task | command | traps |\n|---|---|---|\n"
               "| refresh the generated zones (counts, indexes, views) | `genome emit` | "
               "stale until re-run: a generated zone shows old counts after entity writes, and hand-editing one is E006 |\n")
CLOSED_TPL = """# CLOSED — tried and rejected

Append-only. An entry names the item, the verdict, the measurement that killed it
(a path), and the re-open condition. Re-proposing needs new evidence.
"""
WORKLOG_TPL = "# Worklog\n\nAppend-only: `genome log \"<entry>\"`, one per unit of work.\n"
ASKS_TPL = """# Operator questions and rulings

`genome q add "<question>"` · `genome q rule Q1 "<ruling>" --applied <owner path>`.
A ruling is done only when its owner doc or record carries it.

| id | asked | status | question | ruling | applied |
|---|---|---|---|---|---|
"""
RECORDS_TPL = """# Records — decisions (AD) and regressions (RG)

Generated zones below are written by `genome rec emit`; never hand-edit them.
Topic → governing record notes go above the zones.
"""
HYP_TPL = """# Hypotheses — what was tested, and what was found

`genome hyp add "<hypothesis>"` · `genome hyp verdict H1 rejected --evidence <path> --reopen "<condition>"`.
Statuses: open testing accepted rejected parked. A rejection names what would re-open it.

| id | status | hypothesis | verdict | reopen-if |
|---|---|---|---|---|
"""
QUAR_TPL = """# Quarantine — figures that must never be quoted as current

Backtick each figure exactly as it appears; `genome lint` fails when one reappears on a surface.

| figures | where they appeared | why invalid | invalidating record | date |
|---|---|---|---|---|
"""
PREREG_TPL = """# Pre-registrations — confirmatory specs frozen before the run

`genome prereg freeze <spec>` records the hash; lint fails if the spec changes afterwards.

| date | spec | sha256 | head | note |
|---|---|---|---|---|
"""
EVIDENCE_TPL = """# Evidence store

Numbers are written here by tools, never by hand. Docs cite a file path, not a
transcribed value. Each artefact names its run, inputs and code version.
"""
MAP_TPL = """# Ownership map — every active doc, the question it owns, its status

Status: LIVE (current truth) · EVIDENCE (dated measured verdict) · PLAN-ACTIVE.

| File | Status | Owns | Not for |
|---|---|---|---|
"""
FEED_TPL = """# Agent feed

Append-only. `genome post "msg" --wf <wf> --to <agent>`; `genome feed --to <you>`.
"""
WF_TPL = """# Workflow: {{WF}}

`genome wf add {{WF}} "item"`, `genome claim <id>`, `genome done <id> done --evidence <path>`.

| id | status | item | claim | verdict |
|---|---|---|---|---|
"""
PLAN_TPL = """# {{TITLE}}

Dated-frozen: published `{{DATE}}`. A plan that changes is a new plan (or declare it
in genome.toml `core.living_plans` and keep a 'Resume here' section).

## Mechanism

## Gates / success criteria

(fixed before the run)

## Cost
"""
AUDIT_TPL = """# {{TITLE}}

Dated-frozen: audited `{{DATE}}`; findings mark verified vs asserted.

## Scope

## Findings

- **[verified/asserted]** finding — evidence or basis
"""
AD_BODY = """# {{ID}}: {{TITLE}}

{{MODE}}

## Context

## Decision

## Consequences
"""
RG_BODY = """# {{ID}}: {{TITLE}}

{{MODE}}

## Symptom

## Root cause

## Law

## Detection
"""


