# project-genome

Project knowledge fails in a few predictable ways: two documents answer one question and drift apart; a document has no declared mutability, so state rots and frozen evidence gets edited; nothing routes a question to its owner, so every agent reads everything. Research projects add a worse one — a number in a doc stops matching the artefact that produced it, and the stale figure keeps getting quoted.

project-genome prevents this with **documentation roles that have owners and mutability classes**, and a stdlib CLI that checks them. One call orients a fresh agent (`wake`), one finds the answer (`ask`), one closes the session (`close`).

```console
$ genome wake
# genome wake — my-projects @ main e6575e4 (1 dirty) [agents, core, records]

## STATE  docs/handoff/STATE.md:6-26
## State — 2026-10-23, after the identity surface audit and its integration plan

- **The identity surface is mapped, and it is not as fragmented as feared**: the audit
  measures 14 loci across three pools and finds the canonical store sound —
  aspect files, single-writer CLI, real pooling symlinks — so the migration
  must not re-fragment it. The fragmentation is narrower and named.
```

- **One file, zero dependencies.** The CLI is `scripts/genome`, Python ≥ 3.11, stdlib only. No install step beyond having the file.
- **Self-checking.** `scripts/test_genome.py` runs 37 independent cases against a scratch copy; it never writes your project.
- **Scales by module.** A small app needs `core`. A multi-year R&D program turns on records, research evidence, ops gates, and multi-agent boards — same CLI.
- **Federates.** Per-project genomes exchange typed cards (`federate`), so a portfolio of repos answers questions as one (`ask --all`).

## Install

**As an agent skill** (the canonical path — the skill carries the methodology, the CLI, and the references):

```bash
npx skills add ishan-parihar/project-genome --agent '*' --skill '*' -y
```

**As a plain checkout** (nothing else needed — the CLI has no dependencies):

```bash
curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash
```

or manually:

```bash
git clone https://github.com/ishan-parihar/project-genome.git ~/.agents/skills/project-genome
python3 ~/.agents/skills/project-genome/scripts/test_genome.py   # 37/37 must pass
```

Point your harness at the CLI once: `GENOME=~/.agents/skills/project-genome/scripts/genome`.

**The install registry.** The installer records every install it creates in
`~/.config/genome/installs.json` (skills roots + PATH bins; override with
`GENOME_INSTALLS`). After upgrading anywhere — re-run install.sh — one command
proves the machine is consistent:

```bash
genome installs verify     # MISSING a path, or STALE vs the recorded VERSION -> exit 2
genome installs scan        # any install the installer never registered
genome installs list        # what this machine tracks, with live versions
```

Vendored copies inside adopting repos are informational (`installs register
vendored <path>`); they upgrade with `genome upgrade --apply` in that repo.

### What it touches

- Writes only inside your project (`genome.toml`, or legacy `kb.toml`, read unchanged, plus the directories your module set declares), with two exceptions that write to the HOME, never to repos: the install registry (`~/.config/genome/installs.json`, via install.sh or `genome installs register`) and the federation card cache (`~/.cache/genome/cards`).
- No telemetry, no network at run time. `genome upgrade` is the only command that may fetch, and only to compare the vendored copy's hash against `scripts/releases.txt`.
- Reversibility: delete `genome.toml` and the genome-owned directories. Your documents are plain markdown + YAML throughout.

## Getting started

```bash
cd your-project
$GENOME init --profile core     # or: records | research | ops | agents (composable)
$GENOME wake                    # orient: state, next reads, open asks
$GENOME ask "who owns the pricing figure?"   # section-level retrieval
$GENOME log "shipped the parser"             # close: worklog, one per unit of work
```

Profiles: `core` (always) — state, entry, register, worklog, runbook, operator Q&A, `wake`/`ask`/`close`/`doctor`. Add modules when the project's complexity earns them:

| Module | Turn it on when | Adds |
|---|---|---|
| **records** | decisions or paid-for lessons must be citable forever | AD/RG records: recon-gated, amendable with dated sections, merged with an ID map |
| **research** | numbers come from experiments and get quoted in docs | evidence classes on figures, quarantine register, hypotheses with verdicts, frozen pre-registrations, figure propagation checks |
| **ops** | the repo is big enough to rot quietly | ownership-map completeness, dead links, unreachable code, tracked bulk, secret scan of diffs, running-job edit guard |
| **agents** | more than one agent works at once | per-workflow boards with flock-guarded claims, agent feed, mention inbox |

Not modules, in every repo: **blueprints** (ready-made and custom knowledge bases), **kinds** (your own entity types with lifecycles), the index and graph (`ask --index`, `graph`), and federation (`card`, `federate`, `ask --all`, `covers`/`verified`, `upgrade`).

```console
$ genome ask "proof set"
  10.5  docs/OFFERINGS.md:31-39  § The proof set  (9 lines)
  10.5  docs/OFFERINGS.md:78-85  § The proof set  (8 lines)
   7.0  docs/plans/2026-10-18-revenue-trajectory-….md:29-50  § 4. Offers and proof  (22 lines)
```

Section-level hits with line ranges and owning headings — an agent reads the three sections, not the corpus.

## The methodology

The genome is a set of **roles**: every document answers exactly one question, owned by exactly one file, with a declared mutability class. The CLI enforces the classes instead of trusting discipline:

- **LIVE** documents are current snapshots — a state doc says what is true *now* and gets overwritten, never appended.
- **Append-only** registers (worklogs, feeds, quarantines) are written to, never edited; corrections ride new entries.
- **Generated** zones carry the stamp of the command that produced them and are never hand-edited — stale ones are regenerated, not patched.
- **Frozen** evidence (pre-registrations, superseded records) can be dated and pointed to, but not rewritten; amendments add dated sections.

When two documents disagree, `doctor` names the owner that wins instead of leaving the contradiction for the next reader to rediscover. When a figure is quoted, the research module can re-derive it from the artefact that produced it (`figure`). When the operator rules on a question, the ruling lands on the document that owns the topic — or `ask` keeps surfacing the ask forever.

Three commands carry the daily loop:

| Command | Question it answers | Contract |
|---|---|---|
| `wake` | *where am I, what's next?* | one-call orientation: state, next reads, open asks, running jobs |
| `ask` | *who owns this?* | section-level retrieval over the registered corpus, with an index and graph behind it |
| `close` | *what did this session change?* | worklog entry, register updates, the state doc refreshed — the next `wake` sees it |

`doctor` is the audit: ownership completeness, dead links, mutability violations, undated figures, tracked bulk, secret-scan on diffs. It exits non-zero when something rotting would otherwise exit silently.

## Modules in depth

<details>
<summary><strong>records</strong> — decisions and paid-for lessons, citable forever</summary>

AD/RG records with a lifecycle, not a folder of ADRs: `rec recon` forces a prior-art pass before a new record exists; `rec new` writes it; `rec amend` adds a dated amendment section instead of mutating the record's body; `rec supersede` / `merge` / `retire` emit an ID map so every historical citation keeps resolving. The gate is recon: you cannot file a decision without naming what already exists.

</details>

<details>
<summary><strong>research</strong> — numbers that survive contact with time</summary>

Every figure carries an evidence class (measured / derived / asserted), an owner artefact, and a date. Invalidated figures go to a **quarantine register** with the measurement that killed them, so the stale number cannot be re-quoted innocently. Hypotheses carry verdicts and re-open conditions. Pre-registrations freeze before the experiment runs. `figure` re-derives a quoted figure from its artefact and names the drift when they disagree.

</details>

<details>
<summary><strong>ops</strong> — the repo is big enough to rot quietly</summary>

The ownership map must be complete or `doctor` fails; dead links are checked across docs, not per-file; unreachable code and tracked bulk are named with their owners; diffs are secret-scanned before they land; a running job's files are edit-guarded; `wake` surfaces running jobs so a second agent doesn't clobber the first.

</details>

<details>
<summary><strong>agents</strong> — more than one agent, one board</summary>

Per-workflow claim boards with flock-guarded rows (two agents cannot hold the same claim), an append-only agent feed, and a mention inbox. The contract that makes parallel agents safe is the same one that makes them fast: claims, not hopes.

</details>

<details>
<summary>Blueprints: genomes that aren't code projects</summary>

`blueprints/` ships ready-made knowledge bases for shapes the core doesn't assume: `venture-pipeline.toml` (a revenue pipeline with lanes and outcomes), `literature-research.toml` (papers → hypotheses), `ontology.toml` (derivation-built ontologies), `mind-topology.toml` (a subjective mind map), `intersubjective.toml` (multi-person relational maps). Each declares its own document roles, mutability classes, and gates; `genome init --blueprint <name>` adopts one, and `references/blueprints.md` is the format for rolling your own.

</details>

## Development

```
src/NN_*.py        the source modules (edit here)
scripts/build.py   concatenates src/ into scripts/genome byte for byte
scripts/test_genome.py   the self-check: 37 independent cases, scratch-copy isolated
scripts/probe-outline-languages.py   the outline derivation across every language in the fleet
evals/             graded evals + fixtures
```

Edit `src/`, rebuild with `python3 scripts/build.py`, verify with `python3 scripts/test_genome.py`. The version ledger in `scripts/releases.txt` tells `genome upgrade` a hand-patched vendored copy from a release.

## License

MIT — see [LICENSE](LICENSE).
