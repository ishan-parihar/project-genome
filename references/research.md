# research.md — evidence discipline for projects whose numbers come from experiments

Contents: the evidence store · evidence classes · quarantine · hypotheses · pre-registration · trial ledgers ·
lessons vs records · the research loop

Research knowledge decays in a specific way. A figure gets typed into a doc, the code that produced it is fixed,
and the sentence outlives the fix. An invalidated number keeps being quoted. A rejected idea comes back because
nobody wrote down what would re-open it. This module makes those failures loud.

## Evidence store (`paths.evidence`)

Artefacts (JSON, CSV, reports) are written by tools, never by hand. Each one names:
- its run;
- its inputs and their fingerprints;
- the code version;
- the seed.

Docs **cite the artefact path** and quote a number only next to it. `genome figure <value>` lists every live
occurrence of a number, excluding the archive and the evidence store. Run it before you correct a figure, so the
correction reaches every sentence that quoted it.

Keep regenerable bulk (parquet, pickles, journals, caches) untracked. ops `bulk_globs` enforces that. Only small
verdict artefacts belong in git.

## Evidence classes

Every figure on a research surface (`research.surfaces`, by default state and the agent contract) carries a class
tag somewhere in its section:

| Class | Meaning |
|---|---|
| `[CERT]` | passed the project's full robustness battery |
| `[FORWARD]` | recorded after a freeze, on untouched time |
| `[LIVE]` | realised in production |
| `[OUT-OF-SAMPLE]` | held-out, but without the full battery |
| `[IN-SAMPLE]` | anything else |

The vocabulary is `research.classes`. Only expectation-grade classes (`[CERT]`, `[FORWARD]`, `[LIVE]`) may be
presented as what to expect. The linter cannot judge "presented as an expectation", so that stays a review item.

**W201** fires when a section holds a figure (`research.figure_pattern`, by default percentages) but no class tag.
The fix is a tag, or a pointer to the artefact instead of the number. Sections, not lines, carry the tag: a bold
lead such as `**Readings `[OUT-OF-SAMPLE]`:**` covers the bullets under it.

## Quarantine (`paths.quarantine`)

`| figures | where they appeared | why invalid | invalidating record | date |`. Each figure is backticked exactly as
it appears in prose.

```bash
genome quarantine "+6.9%/mo" "44.86%" --why "selection bias: universe DSR 0.03" --by PQF-RG-025 --where "PROGRESS 2026-10-13"
```

This registers the figures and prints every live occurrence to strike now. Append-only history (worklog,
ledger, feed, pre-registrations) is counted but not listed: it keeps what it said, and the quarantine row is the
correction. Only a table whose first header names figures is read, so the quarantine file may carry other tables.
From then on, **E202** fails lint when
a quarantined figure reappears on a research surface. Quarantine instead of deleting, because a figure that simply
disappears gets re-derived and quoted again.

## Hypotheses (`paths.hypotheses`)

`| id | status | hypothesis | verdict | reopen-if |`, with statuses `open testing accepted rejected parked`.

```bash
genome hyp add "a 5-seed ensemble shrinks the refit SD below the cell's growth"
genome hyp verdict H29 rejected --evidence models/te/seeds_h1_v6e.json \
    --reopen "a variance source other than the sample is identified" --note "SD 0.83 vs +1.66"
```

| Code | Rule | Why |
|---|---|---|
| E205 | accepted / rejected needs evidence: a backticked repo path that exists, or a `worklog NNNN` citation that resolves | a verdict without its measurement is unfalsifiable |
| E206 | rejected needs a re-open condition | the door to a closed idea is new evidence, never enthusiasm |
| E204 | the status is in the vocabulary | — |

`--status rejected` and a bare `rejected` after the ID are the same. `research.hyp_prefix` renames the IDs when
`H1` already means something in the project (a timeframe): `hyp_prefix = "HY"`. `wake` lists the open and testing
ones.

The register of hypotheses is the research ledger. Software projects use the core `ledger` (CLOSED.md) for the
same purpose.

**A register the repo already keeps** (an assumption table inside a protocol doc) stays where it is: map the role
to the section, `hypotheses = "docs/protocol.md#Assumption register"`. The register is the first table under that
heading, and its columns are found by header name:

| Column | Header contains |
|---|---|
| id | (the first column) |
| status | `status` |
| text | `hypothes`, `assumption`, `claim` or `question` |
| evidence | `verdict` or `evidence` |
| reopen | `reopen` or `re-open` |

- **Statuses.** Only the first word of a status cell is read (`rejected (ruling 12)` is `rejected`).
  `research.hyp_statuses = ["qualified", "replaced"]` adds words to the vocabulary.
- **Absent columns.** A check that needs an absent column is skipped (E206 without a re-open column).
- **`hyp verdict`.** It appends the dated evidence to the evidence cell rather than replacing it, so the earlier
  deconstruction stays readable.
- **Surfaces.** `research.surfaces` names where figures must carry a class. `research.quarantine_surfaces` widens
  only the E202 sweep — where a struck figure may not reappear. It defaults to the research surfaces, so a skill
  reference that quotes measurements is unguarded until you name it: `quarantine_surfaces = ["SKILL.md",
  "docs/**"]`. E202 reads the wider list; W201 still reads the narrower one.

Never keep two registers of verdicts, a protocol table and `HYPOTHESES.md`. An agent routed to the thinner one
concludes that nothing was tried.

## Pre-registration (`paths.prereg`)

A confirmatory test is meaningful only if its criteria were fixed before the result was seen.

```bash
genome prereg freeze evidence/prereg/transfer_2026-10-16.json    # sha + HEAD recorded; commit, then run
genome prereg check
```

**E203** fires when a frozen spec changes afterwards. Re-freezing needs `--reason`, and both rows stay visible.

- **Results.** The hash covers the spec part: everything above the first `## Results` or `## Verdict` heading. The
  run's results can then be appended to the same document.
- **Backfilling.** To register a spec frozen before adoption, run `genome prereg freeze <spec> --at <commit>`. It
  hashes the spec as that commit holds it and records that commit. It refuses when the spec part has changed
  since.

## Trial ledgers

Selection-bias corrections (deflated Sharpe, PBO, multiple-testing) need the count of everything tried, not just
the winners. Keep the trial ledger as an evidence artefact that the search tools append to. Map it with
`paths.evidence`, or a `native:` note in the contract. Report its size wherever a selected result is quoted. The
genome doesn't compute statistics; it makes sure the denominator is findable.

## Lessons vs records

A measured lesson that agents must not re-litigate belongs to one of two homes:
- as a clause in the governing record (records module), when it is law;
- as a rejected hypothesis with its re-open condition, when it is a closed experiment.

A list of numbered lessons inside a protocol doc is a third owner of the same knowledge. Fold it into those two.

## The research loop (per iteration)

1. `genome wake`, then `genome ask` for the protocol section of the phase you are entering.
2. Before you run, `genome prereg freeze` any confirmatory spec.
3. Run. Artefacts land in the evidence store.
4. Write the verdict: `genome hyp verdict …` with the artefact path. The worklog carries readings with classes and
   a method review: which axes were fixed, and what would falsify the result.
5. If a number was invalidated: `genome figure`, then `genome quarantine`, and strike the occurrences.
6. Operator feedback: `genome q rule … --applied <owner>`, and amend that owner in the same session.
7. `genome close`.
