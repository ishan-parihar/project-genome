---
name: project-genome
description: "Sets up, adopts and runs a project's knowledge genome: documentation roles with mutability classes plus a stdlib `genome` CLI whose modules scale from a small app to a multi-year R&D program — decision/regression records (recon-gated, amendable, merged with an ID map), research evidence (evidence classes, quarantined figures, hypotheses with verdicts, frozen pre-registrations), housekeeping gates (ownership map, dead links, unreachable code, tracked bulk, secrets, budgets) and parallel-agent claims. Gives one-call orientation (`wake`), section-level retrieval (`ask`) and iteration close (`close`) for token-efficient agents. Use whenever the user sets up or rescues project docs, a KB, handoff/state docs, worklogs, ADRs or regression records, a research or experiment log, a custom knowledge base with its own lifecycle (a subjective mind map, a multi-person relational map, a literature review from papers toward novel hypotheses, an ontology built by derivation, or any schema of your own: blueprints), invalidated numbers, operator rulings that must reach the docs, record consolidation, housekeeping, resuming after compaction, parallel agents, or migrates off kb/kb.toml or an external arch record CLI."
---

# project-genome

Project knowledge fails in a few predictable ways:
- two documents answer one question and drift apart;
- a document has no declared mutability, so state rots, ledgers get rewritten and frozen evidence gets edited;
- nothing routes a question to its owner, so agents read everything.

Research projects add more:
- a number in a doc stops matching the artefact that produced it;
- an invalidated figure keeps being quoted;
- feedback from the operator never reaches the record it should change;
- every session spends a fifth of its context just re-orienting.

The genome prevents these with **roles that have owners and mutability classes**, and a CLI that checks them. It
also makes the cheap path the default one: `wake` to orient, `ask` to find, `close` to finish.

The CLI is `scripts/genome`: one file, stdlib only, Python ≥ 3.11. It finds the project root by walking up for
`genome.toml`, or for a legacy `kb.toml`, which it reads unchanged. `scripts/test_genome.py` is its self-check (independent cases; `python3 scripts/test_genome.py [case]`). The source is `src/NN_*.py`; `python3 scripts/build.py` concatenates it into `scripts/genome` byte for byte, so edit `src/` and rebuild.

## Modules: pick what the project's complexity needs

| Module | Turn it on when | Adds |
|---|---|---|
| **core** (always) | any project that outlives one session | agent contract, state, entry, register, plans/audits, worklog, archive, runbook, operator questions and rulings (`q`), generated zones, byte budgets, `wake` / `ask` / `close` / `doctor` |
| **records** | decisions or paid-for lessons must be citable forever | AD / RG records: `rec recon` → `rec new` (prior art first), `rec amend` (dated amendment sections), `rec supersede/merge/retire` with an emitted ID map |
| **research** | numbers are produced by experiments and quoted in docs | evidence classes on every figure, quarantine register, hypotheses with verdicts and re-open conditions, frozen pre-registrations, `figure` (propagation check) |
| **ops** | the repo is big enough to rot quietly | ownership map completeness, dead links across docs, unreachable code, tracked bulk, secret scan of diffs, running-job edit guard, jobs in `wake` |
| **agents** | more than one agent works at once | per-workflow boards with flock-guarded claims, the agent feed and mention inbox |

Not modules, available in every repo: **blueprints** (ready-made and custom knowledge bases: `references/blueprints.md`), **kinds** (declare your own entity types with lifecycles and typed relations: `references/kinds.md`), the **index and graph** (`ask --index`, `graph`, `place`), and **federation and drift** (`card`, `federate`, `ask --all`, `covers`/`verified`, `upgrade`: `references/federation.md`).

**Profiles** (`genome init --profile …`):

| Profile | Modules |
|---|---|
| `software` | core, records |
| `research` | core, records, research, ops |
| `team` | core, records, agents |
| `full` | all five |

A module is added later by editing `[genome] modules` in `genome.toml`. Its checks and commands then switch on;
`genome modules` shows what is on. Start with the smallest set that covers the project's real failure modes,
because every module adds checks someone must keep green.

## Blueprints: a knowledge base for any purpose

`genome init --blueprint <name|file>` installs a whole knowledge base (kinds with lifecycles, a playbook, routes,
a wake queue, views) on a new or existing genome, enforcing who may decide what (`human_only`), what must be cited,
and what a retraction invalidates, on write rather than in prose.

| Blueprint | For |
|---|---|
| `mind-topology` | a private map of one mind: engrams, emotions, shadows, processes, complexes; loops and leverage by graph |
| `intersubjective` | several people's maps: attachment, transactional analysis, patterns; what crosses between maps (`--across of`) |
| `literature-research` | papers → verbatim claims → graded findings → testable hypotheses; Swanson gaps; retractions cascade |
| `ontology` | axioms → derivations → theses on a human-gated ladder; witnesses corroborate, never ground |

Custom: `genome blueprint new <name> [--from base]`, edit, then `genome blueprint check <file>`, which drives the real CLI
through every kind, relation, state and taint edge and fails with the first step that broke. `blueprint list|show`
inspect. Subjective blueprints are `privacy = local`: `close` refuses with a git remote. Read `references/blueprints.md`
before authoring one, and a blueprint's own playbook (`docs/playbooks/<name>.md`) once before using it.

## The laws (what the checks enforce, and why)

1. **One owner per question.** A second document answering the same thing will drift from the first. So amend
   the owner; never add a sibling. ops: every doc in an owner location is listed in the ownership map.
2. **Every document has a mutability class**, because readers need to know whether a doc can be trusted
   unchanged:

   | Class | Roles |
   |---|---|
   | current-snapshot | state |
   | current | contract, entry, runbook |
   | living plan | phase rows move; it has a "Resume here" section |
   | dated-frozen | audits, pre-registrations |
   | append-only | worklog, ledger, feed, quarantine |
   | rows-update-verdicts-append | register, hypotheses, asks |
   | amendable law or immutable law | records |
   | generated | zones, which are never hand-edited |
3. **Nothing is deleted.** `genome archive <path> --reason`, or `--section "<heading>"` for one stale part of a
   living plan. History stays findable, and live docs stay small.
4. **Every verdict names its evidence, and every figure its class.** A terminal row without an evidence path is
   unfalsifiable. A figure without `[CERT]` / `[OUT-OF-SAMPLE]` / `[IN-SAMPLE]`… invites being read as an
   expectation. Docs cite the artefact path rather than retyping the number.
5. **Feedback reaches its owner the same session.** `genome q rule Qn "<ruling>" --applied <owner path>`. A
   ruling with no applied path is a warning on every lint, because unapplied feedback is how the same mistake
   comes back.
6. **Prior art before a new record.** `genome rec recon <keywords>` shows the records and owner sections that
   already cover the topic. `rec new` refuses without a fresh recon token and an `--orthogonal` reason. Most
   lessons belong as an amendment to an existing owner.
7. **Cheap to read.** Entry surfaces carry byte budgets. Big docs are reached by section through `ask`, never
   read whole. History moves out of state into the worklog and archive. Every file an agent opens costs context
   and can mislead it.

## The agent loop

```bash
genome wake                       # one call: state top block, Resume-here, operator asks, jobs, inbox, health
genome ask "how is the funnel cache keyed"     # → path:lines § heading; read only that range
genome ask "..." --show           # print the best section directly (60 lines)
# … work …
genome close                      # emit zones, lint, secret scan, gate; prints the judgement items and named paths
```

These replace the habit of reading AGENTS.md, then PROGRESS, then the plan, then INDEX, then the latest worklog in
full. On a large R&D repo that habit costs about 50k tokens per cold start; `wake` is about 2–4 kB. Read
`wake`'s pointers, then `ask` for anything else.

`close` does not commit. It prints `git add -- <paths>` with the `core.never_commit` globs left out, so the
commit stays deliberate and uses named paths. It exits 2 on any of:
- a lint error;
- a secret value in the diff (the value is never printed);
- a failed gate.

## Command map

| Module | Commands |
|---|---|
| core | `init` `modules` `lint [--only M] [--code C…] [--all]` `doctor` `emit` `wake` `ask` `close` `--version` `handoff [--write]` `status <id> <state> --evidence p` `plan` `audit` `archive [--section H] [--generation G] [--by owner]` `log "<entry>"` `q add\|rule\|apply\|withdraw\|list` |
| records | `rec recon <kw…>` `rec new ad\|rg "<title>" --recon T --orthogonal "<why>"` `rec amend ID --title --reason --body` `rec supersede ID --by ID` `rec merge IDs --into ID` `rec retire ID` `rec list [--all]` `rec show ID` `rec emit` |
| research | `figure <value>` `quarantine <fig…> --why` `hyp add\|verdict\|list` `prereg freeze <spec>\|check` |
| ops | `secrets` (plus the ops lint gates) |
| agents | `wf new\|add\|list` `claim` `done` `claim-register` `post` `feed` |
| kinds | `new <kind> [--link rel=ID] \| --batch F` `move <id,…> <state>` `set` `link`/`unlink` `show <id,…>` `find <kind> --where` `view <name>` `impact <id> [--to S]` (preview a cascade) (all with `--json` where useful) |
| blueprints | `init --blueprint N` `blueprint list\|show N [--playbook]\|new N [--from B]\|check [N]` |
| index, graph | `index [--rebuild]` `ask --index` `graph neighbors\|path\|hubs\|cycles\|bridges\|gaps` `place "<text>"` |
| federation | `card` `federate` `ask --all` `resolve repo:<n>#<class>` `verify <doc> --reviewed` `upgrade [--apply]` `migrate` |

`--json` is on `ask`, `lint`, `doctor`, `rec list`, `new`, `show`, `find`, `graph`, `place` and `card`: one compact document, ids and line ranges, for piping.

Lint prints at most 5 lines per code, with a count of the rest, because the output is read by agents. Every code
and its fix is in `references/lint-rules.md`.

## Cold start (new repo)

```bash
mkdir -p scripts && cp <skill-dir>/scripts/genome scripts/genome && chmod +x scripts/genome
./scripts/genome init --profile research     # or software / team / full; never overwrites anything
# fill AGENTS.md (what this is + routing table), set [core] gate, then:
./scripts/genome lint
```

Copying the CLI in keeps the genome self-sustaining: a future agent needs no external path to keep it running.

## Adopting an existing repo

1. `genome init --modules …`, or hand-write `genome.toml`.
2. Map each role to the path the repo already uses. A role owned elsewhere is mapped `native:<note>` (a
   repo-native mechanism owns it) or `overlay:<path>` (the operator's private overlay). The tooling defers to
   those and never writes them.
3. `genome lint --advisory`, then triage: keep one owner per question, archive the rest, relink readers.
4. Lint green before the first new record or verdict lands.

`references/adoption.md` covers:
- legacy `kb.toml` repos (they work unchanged);
- detaching from an external record CLI such as `arch`, importing its records and archive so the project depends
  on nothing outside itself;
- a worked research configuration.

## When not to use it

- Throwaway scripts, scratch dirs and single-session experiments.
- A repo with fewer than about 3 docs and no second agent: a README is enough. The README is still the `readme`
  role, and `lint` checks it against `docs/` (W008 / W009).

## References (read only the one the task needs)

| File | Read when |
|---|---|
| `references/core.md` | core role schemas, mutability, living plans, worklog forms, archive forms, asks / rulings, zones, budgets, wake / ask / close internals |
| `references/blueprints.md` | installing a ready-made knowledge base, or authoring a custom one; the four built in; the check |
| `references/kinds.md` | declaring kinds, relations (min / required_in / taint / default / symmetric / graph), the graph and index queries |
| `references/records.md` | writing, amending or consolidating ADs / RGs; ID map; immutable vs amendable mode |
| `references/research.md` | evidence classes, quarantine, hypotheses, pre-registration, evidence store, trial ledgers |
| `references/ops.md` | housekeeping gates and their configuration; secrets; running-job guard |
| `references/agents.md` | the parallel-agent protocol: identity, claims, feed, boards |
| `references/adoption.md` | adopting a repo, kb.toml migration, detaching from `arch`, worked `genome.toml` examples |
| `references/lint-rules.md` | every E### / W### code, what it means, the fix |
