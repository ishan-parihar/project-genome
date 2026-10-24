# core.md — the always-on roles and their mechanics

Contents: roles · mutability classes · register · plans (dated and living) · worklog forms · archive forms ·
operator questions and rulings · generated zones · budgets · wake / ask / close internals · outward pair

## Roles (default paths; `genome.toml [paths]` remaps any of them)

| Role | Default path | Class | Owns the question |
|---|---|---|---|
| agents | `AGENTS.md` | current | what is this, what is the gate, which doc answers what (routing table) |
| state | `docs/handoff/STATE.md` | current-snapshot | where the project stands right now |
| entry | `docs/handoff/README.md` | current | what a fresh agent does, in order; what to stop and ask |
| register | `TODO.md` | rows update, verdicts append | what is left, and what was decided about each item |
| plans | `docs/plans/` | dated-frozen, or living (below) | how we will do X |
| audits | `docs/audit/` | dated-frozen | what was checked, what was found (verified vs asserted) |
| ledger | `docs/kb/CLOSED.md` | append-only | what was tried and rejected, with the re-open condition |
| worklog | `docs/kb/WORKLOG.md` | append-only | what happened, unit of work by unit of work |
| asks | `docs/kb/ASKS.md` | rows update | what we asked the operator, and what they ruled |
| runbook | `docs/RUNBOOK.md` | current, surgical edits | exact commands, environment traps |
| archive | `docs/archive/` | write-once | superseded history, findably |
| readme / docs | `README.md`, `docs/` | current | the outward pair: audience questions and depth |

**State holds no history.** Its first `## ` block is the current snapshot, and it is what `wake` prints. Older
snapshots go to the worklog or the archive. A state page that accumulates dated blocks has become a log, and its
"current state" is whichever block an agent reads first.

## Register

`| id | status | item / verdict | notes |`, with statuses `open in-progress done rejected blocked`.

The only sanctioned transition is `genome status <id> <state> --evidence <path>`. It appends
`→ [date] \`path\` — verdict: …` into the item cell; it never rewrites. Rows are never deleted: a closed row is
the project's memory of what was decided.

A repo whose register lives elsewhere (for example a plan's gap register) maps it `native:<note>`.

A register inside a larger document is `register = "path.md#Heading"`: only the table under that heading is the register (a legend table elsewhere in the file is not).

## Plans: dated or living

- **Dated** (default): `genome plan "<title>"` mints `docs/plans/YYYY-MM-DD-slug.md`, which is frozen at
  publication. A changed plan is a new plan, and the old one is archived. Two live plans with overlapping titles
  give W006.
- **Living**: list it in `core.living_plans`. Its phase rows move as work lands. Its contract:
  - It has a **"Resume here"** section, as a heading or a `**Resume here…**` lead line (`core.resume_heading`).
    The section holds the order of work, the in-flight state and the entry points of the next phase. `wake`
    prints it when `core.resume = "<path>#Resume here"`. W012 fires when it is missing.
  - When a section becomes history, it leaves: `genome archive <plan> --section "<heading>" --reason "…"` moves it
    to the archive and leaves a one-line pointer. The heading must match exactly one heading (headings inside
    code fences do not count), and the section holding the Resume block is refused, because its
    sub-sections would move with it. A heading still saying "superseded" gives W011.
  - It carries a byte budget in `core.budgets`, because a living plan grows by stacking outlines unless something
    pushes back.

## Worklog forms

- `worklog_form = "file"`: `genome log "<entry>"` appends `- **ts** — entry` to one file.
- `worklog_form = "numbered"`: the worklog role is a directory of `NNNN-YYYY-MM-DD-slug.md` session files.
  - `genome log "<title>" [--body … | --body-file notes.md | --body-file -]` creates the next number and
    regenerates the index zone (`INDEX.md`, zone `worklog`; E015 when stale, `genome emit` repairs it).
  - Numbering is flock-guarded with exclusive create, so two sessions logging at once never share a number.
  - A duplicate number is E014: rename one with a suffix (`0346b-…`).
  - Entries are append-only: `doctor` flags a removed line or a deleted entry over the last
    `core.append_window` commits (default 10) and in the working tree. A rename is allowed; the index is
    generated and exempt.
  - `wake` names the latest file. Read the index only when searching history; `ask` is usually cheaper.

A worklog entry records what happened and why: readings with their evidence class, the method review, the records
it changed. Decisions themselves live in records; the worklog cites them.

## Archive forms

- `archive_form = "flat"`: the file moves to `docs/archive/`, a tombstone stays at the original path, and a row is
  added to `INDEX.md`. Suits small repos.
- `archive_form = "generations"`: the file moves to `archive/<generation>/<original path>`, and a manifest row is
  added to `archive/<generation>/README.md` (`| file | superseded by | reason | date |`). No tombstone is left in
  the active tree; `archive` prints every live reader so you relink them in the same commit. Suits large repos,
  where tombstones would clutter the home base.

W007 fires for a file missing from its manifest, or once for a generation with no manifest at all.

## Operator questions and rulings (`asks`)

`| id | asked | status | question | ruling | applied |`, with statuses `open ruled withdrawn`.

```bash
genome q add "Hold back 61 symbols as a holdout?"                    # Q4 open
genome q rule Q4 "Released: breadth beats the holdout" --applied docs/plan.md core/decisions/AD-031-....md
genome q apply Q4 --applied sub-systems/x/notes.md                   # more owners later
genome q list --open
```

| Code | Fires when | Why |
|---|---|---|
| W014 | a question has been open more than `core.ask_days` (3) | it is re-asked or withdrawn, never silently lost |
| W013 | a ruling has no `applied` path | the feedback has not yet reached its owner |
| E013 | an applied path is missing | the ruling cites an owner that does not exist |

`wake` shows both open questions and unapplied rulings.

## Generated zones

```
<!-- genome:zone NAME sha=XXXXXXXXXXXX -->
…generated body…
<!-- genome:end NAME -->
```

The sha covers the body. When the body no longer matches it, someone hand-edited the zone: that is E006. Fix the
source and re-emit. The zones genome writes:
- records `records` and `idmap` (`genome rec emit`);
- `worklog` (numbered form).

A new zone is appended at the end of its file, unless the file holds a placeholder line
`<!-- genome:zone NAME -->`: the first emit replaces it in place, so a zone can sit under its own heading.

Zone names for `records.zones`: `records` (both tables), `decisions`, `regressions` (a Severity column when the
records carry one) and `idmap`. A whole generated file is a short header plus one zone.

Other emitters run from `genome close` through `core.emitters`.

## Budgets

`core.budgets = { "AGENTS.md" = 60000, "docs/STATE.md" = 16000 }` (bytes; about 4 bytes per token). Over budget is
E016. The fix is always to move history out, or to replace prose with a pointer. Adding a summary is never the
fix.

W010 flags a listed doc over `core.toc_lines` (300) with no table of contents. `ask` still finds its sections,
but a contents line helps a human, and an agent reading by offset.

## wake, ask, close

- **wake** prints, in order:
  - the git line and the enabled modules;
  - the first `## ` block of state, capped at `core.wake_lines`;
  - the Resume-here section, or open register rows when no resume is set;
  - open asks and unapplied rulings;
  - `ops.jobs` output;
  - the last worklog;
  - the mention inbox (agents, with `GENOME_AGENT_ID` set);
  - open and testing hypotheses (research);
  - the doctor and lint counts.

  One call, a few kB. Its last line points to `ask`.
- **ask** builds a section index over:
  - every role file;
  - every doc the ownership map, agent contract or entry backticks;
  - living plans;
  - active records;
  - `core.ask_globs`.

  Sections longer than 30 lines are split at bold lead lines (or every 25 lines), so a hit is a narrow range; a
  chunk is never shorter than 5 lines (a lead keeps its first sub-points), and every lead merged into a chunk keeps
  its lead weight. Generated zones and archived files are never indexed: an emitted table answers nothing its
  source does not, and history is never doctrine.
  Chunks are scored by idf-weighted overlap with the question (section heading ×3, a chunk's bold lead ×1.5,
  body ×1, path ×1). Tokens are lightly stemmed (quote / quoted, acceptance / accept). Short identifiers with a digit (V1, H1, A28) are kept, and a record
  ID in the question pins that record. It prints `path:start-end § heading (n lines)`, then any routing-table rows
  whose question matches. `--show [N]` prints the best section.
- **close** does six things, then exits 2 if anything is red:
  1. emits the zones and runs `core.emitters`;
  2. lints;
  3. scans for secrets (ops);
  4. runs `core.gate`;
  5. prints a judgement checklist: state updated? worklog written? changed records cited? plus the
     `core.checklist` items;
  6. prints the named-path `git add` line: every changed and untracked file (never a whole directory), shell-quoted,
     minus `core.never_commit`. A glob starting with `/` is anchored at the root (`/README.md` skips only the
     root README, not archive manifests); a glob without `/` matches the basename anywhere.

## Outward pair

- The **README** answers audience questions (what is this, how do I run it).
- **docs/** holds the depth the README links to.

W008 fires when a README heading and a docs page heading match. W009 fires when a docs page is reachable from
neither the README nor another page. Internal genome roles under `docs/` are exempt from both.
