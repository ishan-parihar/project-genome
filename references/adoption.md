# adoption.md — bringing an existing repo under the genome

Contents: the recipe · pointer forms · legacy kb.toml repos · detaching from an external record CLI (arch) ·
worked configuration: a large R&D repo · triage order

## The recipe

1. Copy the CLI in: `cp <skill>/scripts/genome scripts/genome`.
2. Write `genome.toml`: either `genome init --modules records,research,ops` (it keeps every existing file and
   writes only what is missing), or by hand. With a hand-written `genome.toml` in place, `genome init` keeps it and
   creates each enabled role that is missing **at its mapped path**; it never touches an existing file or a
   `native:` / `overlay:` role.
3. Map every role to the path the repo already uses. Moving files to fit the tool is never the goal.
4. Run `genome lint --advisory` and `genome doctor`, and triage (order below).
5. Get `genome lint` green before the next record, verdict or ruling lands.
6. Point the agent contract's first lines at the loop: `genome wake`, `genome ask`, `genome close`.

## Pointer forms

| Value | Meaning | Tooling behaviour |
|---|---|---|
| `"path"` | the role lives here | checked, written |
| `"native:<note>"` | a repo-native mechanism owns it (a guard-tested ledger in AGENTS.md, a gap register inside the plan) | reported as native, never written, never "missing" |
| `"overlay:<path>"` | it lives in the operator's private overlay repo | same; writers refuse and say where |

## Legacy kb.toml repos (project-kb)

`genome` reads `kb.toml` unchanged:
- `[paths]` keeps its meaning;
- `pointer_ignore` and `dated_pattern` are honoured from `[paths]`;
- the modules default to core, records and agents (what `kb` had).

The commands are the same, apart from these:

| Command | Change |
|---|---|
| `kb ad` / `kb rg` | now `genome rec recon …`, then `genome rec new ad|rg …`: prior art is a gate now |
| `kb wf done` | now `genome done` |

New behaviour to expect on the first lint:
- **E001 checks more pointer shapes:** any file extension, plus package-relative paths resolved by tail. A
  reference to a file that really does not exist now shows up.
- **W010** fires on long docs with no contents line.

To opt into more, rename `kb.toml` to `genome.toml` and add `[genome] modules = [...]`.

## Detaching from an external record CLI (e.g. `arch` in an organism of pools)

Detaching makes the project self-contained: its law, history and tooling live in the repo, so nothing outside can
change its R&D doctrine.

1. **Records.**
   - Point `paths.decisions` / `regressions` at the existing record dirs.
   - Set `records.prefix` (e.g. `PQF`) and `mode = "amendable"` when the records already carry dated amendment
     sections.
   - The frontmatter (`ID / Title / Status / Date / Description / Severity`) is already the genome's format.
2. **Retired records.** Copy them from the external archive (e.g. `~/organism/organism/archive/<pool>/`) into
   `records.archive`, with `Status` and `SupersededBy` set. When the external archive is incomplete, restore them
   from git history: `git log --diff-filter=D --name-only -- <records dirs>` finds the deleting commit, and
   `git show <commit>^:<path>` gives the file. Import them before the first `genome rec new`; it never reuses an ID
   any record or the records index cites, but an ID cited only in code is invisible to it. Then `genome rec emit` writes the ID map, and W105
   (unknown cited IDs) goes quiet.
3. **Mutation receipts.**
   - Stop writing per-mutation receipt files: genome records mutations inside the record (`## Revisions`), and the
     session worklog cites them.
   - Fold any existing receipts into one digest.
4. **Generated zones in the agent contract.**
   - Replace the external emitter's blocks (fleet routing, CLI registries, department tables) with genome zones,
     or delete them when they describe the external organism rather than the project.
   - The records table becomes `records.zones = { "AGENTS.md" = ["records"], "<doctrine>.md" = ["idmap"] }`.
5. **Doctrine text.** Amend the records that say "the external CLI is the only entry point" in the same session,
   so they name `genome rec …`.
6. **Hooks.** Remove the organism's registry/route hooks (`_org.yaml` entries, cron "employees", smoke checks that
   call the external CLI), or keep them inert. Smoke runs `genome lint` instead.
7. **Links and pointers out.**
   - Tracked symlinks into the external tree are E307: linked skills (its governance meta-skill competes with
     `genome rec`), linked CLIs. Remove them, or vendor the file. A tool only operations still needs goes in
     `ops.external_ok`, and the contract's CLI list marks it as external.
   - Records that say "retired verbatim to `~/<external>/archive/…`" now point at `records.archive`. Add the old
     location to `ops.stale_terms`, so a copied sentence cannot bring it back.
   - Do the same for any section the adoption moved, such as `INDEX §Quarantine`.
8. **Existing registers.** Map a hypotheses or assumption table that already lives in a protocol doc with
   `path#heading` (research.md). Do not start a second register beside it.
9. **Existing pre-registrations.** Register each one with `genome prereg freeze <spec> --at <its freezing
   commit>`. An empty prereg role beside real preregs tells an agent that nothing was pre-registered.

## Worked configuration: a large R&D repo

This is a research program with numbered worklogs, generation archives, a living plan, amendable records and
housekeeping gates. The genome replaces a hand-built 800-line housekeeping, index and lint layer with this
configuration:

```toml
[genome]
modules = ["core", "records", "research", "ops"]

[paths]
agents = "AGENTS.md"
state = "docs/PROGRESS.md"
entry = "sub-systems/rd/docs/architecture/INDEX.md"
register = "native:the gap register inside the FOUNDATION-REBUILD plan"
ledger = "native:core/hypotheses.md (a rejected row carries its re-open condition)"
worklog = "core/worklog"
asks = "core/asks.md"
plans = "sub-systems/rd/research/audits"
audits = "sub-systems/rd/research/audits"
runbook = "sub-systems/live-ops/docs/ad12-operations-manual.md"
archive = "archive/docs-archive"
decisions = "core/decisions"
regressions = "core/regressions"
records_index = "core/doctrine-of-record.md"
evidence = "sub-systems/rd/research/models"
hypotheses = "skills/quantitative-strategy-rd/references/trade-engine.md#Assumption register"
quarantine = "core/quarantine.md"
prereg = "core/prereg.md"
ownership_map = "sub-systems/rd/docs/architecture/INDEX.md"

[core]
gate = "bin/smoke"
worklog_form = "numbered"
archive_form = "generations"
living_plans = ["sub-systems/rd/research/audits/FOUNDATION-REBUILD-2026-10-12-plan.md"]
resume = "sub-systems/rd/research/audits/FOUNDATION-REBUILD-2026-10-12-plan.md#Resume here"
budgets = { "AGENTS.md" = 60000, "docs/PROGRESS.md" = 16000, "core/doctrine-of-record.md" = 30000, "skills/quantitative-strategy-rd/SKILL.md" = 70000 }
checklist = ["method review of every verdict written into the worklog",
             "operator feedback amended its governing record (genome q rule --applied)",
             "every new figure carries its evidence class; invalidated ones are in core/quarantine.md",
             "staged diff: 0 hits for the MT5 password and the keyring pass (genome secrets)"]
never_commit = ["sub-systems/rd/research/models/scratch/**", "/README.md",
                "Shared/data/signal_corpus/corpus_manifest.json"]

[records]
prefix = "PQF"
mode = "amendable"
archive = "archive/records"
governed_by = "core/doctrine-of-record.md"
required = { AD = ["ID", "Title", "Status", "Date"], RG = ["ID", "Title", "Severity"] }
zones = { "AGENTS.md" = ["records"], "core/doctrine-of-record.md" = ["idmap", "regressions"], "skills/quantitative-strategy-rd/references/regression-guards.md" = ["regressions"] }

[research]
surfaces = ["docs/PROGRESS.md", "AGENTS.md"]
hyp_prefix = "A"
hyp_statuses = ["retired", "replaced", "qualified", "confirmed", "fixed", "settled", "identity"]

[ops]
owner_globs = ["sub-systems/*/docs/**/*.md", "sub-systems/rd/research/audits/*", "sub-systems/rd/research/notes/*",
               "skills/*/references/**/*.md"]
owner_exempt = ["skills/quantitative-strategy-rd/references/regression-guards.md"]
link_surfaces = ["AGENTS.md", "sub-systems/*/AGENTS.md", "kb/*.md", "docs/PROGRESS.md", "core/doctrine-of-record.md", "core/*.md",
                 "sub-systems/rd/docs/architecture/INDEX.md", "sub-systems/rd/docs/architecture/axis-library.md",
                 "sub-systems/rd/research/audits/FOUNDATION-REBUILD-2026-10-12-plan.md",
                 "skills/**/*.md", "sub-systems/live-ops/docs/*.md"]
link_prefixes = ["core/", "docs/", "scripts/", "Shared/", "sub-systems/", "skills/", "bin/", "tests/", "archive/"]
code_globs = ["scripts/**/*.py", "scripts/**/*.sh", "Shared/**/*.py", "Shared/**/*.sh", "bin/*"]
code_roots = ["skills/**", "sub-systems/live-ops/docs/*", "cron-jobs/*", "bin/*", "tests/*.py", "smoke.yaml",
              "genome.toml", "_org.yaml"]
bulk_globs = ["*.parquet", "*.pkl", "*.npz", "*.journal",
              "sub-systems/rd/research/models/scratch/funnel/ledgers/*",
              "sub-systems/rd/research/models/scratch/funnel/run1_*/*",
              "sub-systems/rd/research/models/scratch/funnel/memo/*",
              "sub-systems/rd/research/models/scratch/funnel/book_*/*",
              "sub-systems/rd/research/models/scratch/pathstore/*",
              "sub-systems/rd/research/models/scratch/family_labels/*",
              "sub-systems/rd/ea-source-mql5/EA/logs/*",
              "Shared/data/_quarantine/*/*_parquet/*"]
max_bytes = 5000000
secrets = [".env:BROKER_PASSWORD", "~/.config/app/.keyring_pass"]
jobs = "bin/rdjob status | grep -E 'running|queued' || echo '(no job running)'"
py_paths = ["scripts/pipelines", "Shared/engines", "Shared", "scripts/tools"]
# layout (was _org.yaml + lint_org.py; _org.yaml stays as the organism's pool declaration only)
root_files = ["AGENTS.md", "README.md", "_org.yaml", "smoke.yaml", "genome.toml", ".gitignore", ".gitattributes"]
dir_suffixes = { "scripts" = [".py", ".sh", ".md", ".json", ".txt"], "Shared" = [".py", ".md", ".json", ".csv", ".mqh"], "Shared/data" = "*", "core" = [".md"], "kb" = [".md"], "cron-jobs" = [".md"], "tests" = [".py", ".csv", ".json"], "docs" = [".md"] }
dir_requires = { "sub-systems/*" = "AGENTS.md", "skills/*" = "SKILL.md" }
stale_terms = ["Scripts/Python", "STRATEGIES/PHANTOM", "ops/vps-logcheck"]
stale_exempt = ["**/worklog/**", "*REORG-PLAN*"]
```

This is the configuration pioneer-qf adopted on 2026-10-17 (secrets renamed here). The adoption also:
- restored 95 retired records from git history into `archive/records/` (the ID map is generated from them);
- moved the quarantine table out of the ownership map into `core/quarantine.md`, each figure backticked;
- replaced the hand-built indexes with zones placed by `<!-- genome:zone NAME -->` placeholders;
- wrote manifests for 9 archive generations that had none;
- archived `housekeeping.py`, `emit_indexes.py` and `lint_org.py`, and removed the organism's `bin/arch` link.

A trial with an equivalent mapping (2026-10-17) found 4 genuine defects that the hand-built gate missed:
- two duplicate worklog numbers;
- two citations of files that no longer exist.

It also found:
- a living plan whose "Resume here" was a bold line, which is supported;
- about 260 archive files in older generations whose manifests do not list them.

**A quarantine kept as prose in another doc** (a register inside an index page): move its rows into the
quarantine role, backtick each figure exactly as it appears, and leave a one-line pointer in the old place. E202 can
only check backticked figures, and one register keeps one owner.

**Runtime files.** `genome init` (new or adopted repo) adds `*.genome-lock`, `*.genome-tmp` and `.genome/` to
`.gitignore`. Never a bare `*.lock`: that would hide `Cargo.lock` or `uv.lock`.

**Existing generated files.** An index the repo already generates without genome zone markers (a worklog
`INDEX.md`, a records table in AGENTS.md) gets a genome zone appended on first emit. Delete the old generated
block in the same commit, so the file has one owner, and retire the old emitter.

## Triage order (most damage first)

1. **E202 / quarantine.** Invalidated numbers on entry surfaces mislead every session.
2. **E001 / E303 / E005.** Pointers to nowhere send agents searching.
3. **E103 / E104 / E006.** Records and generated zones must be true before anything cites them.
4. **E014 / E016 / W011 / W012.** Worklog numbering, budgets, living-plan shape: what makes resuming cheap.
5. **E301 / E304 / E305.** The home base: unlisted docs, dead code, bulk.
6. **W201 / W013 / W014.** Evidence classes and feedback application: these keep it honest from now on.
7. **W007 / W010 / W008 / W009.** History manifests and readability.
