# lint-rules.md — every code, what it means, the fix

`genome lint` exits 2 on any E###, and 0 with warnings only; `--advisory` always exits 0. Output is capped at 5
lines per code; `--code E303 --all` shows every line for one code, and `--only <module>` runs one module.

Errors are doctrine violations. Warnings are hygiene, or judgement the linter can only point at.

## core

| Code | Meaning | Fix |
|---|---|---|
| E001 | agent contract (or `core.living_plans`) points at a missing file | create it, fix the pointer, or declare a legitimate non-repo reference in `core.pointer_ignore` |
| E002 | register status outside `open in-progress done rejected blocked` | use the vocabulary; tooling reads it |
| E003 | terminal register row without `→ [YYYY-MM-DD] <evidence>` | `genome status <id> done --evidence <path>` |
| E004 | plan/audit file without a date stamp (subject to `core.dated_pattern`; a `README.md` / `INDEX.md` index is exempt) | rename to `YYYY-MM-DD-slug.md`, or declare it a living plan |
| E005 | agent contract points at a tombstone | point at the current owner |
| E006 | a generated zone was hand-edited (sha mismatch) | fix the source and re-emit (`genome rec emit`, `genome close`) |
| E009 | ledger cites a missing evidence file | restore the artefact or fix the citation |
| E010 | terminal register row cites a missing evidence file | same |
| E013 | ask with a bad status, or an applied-to path that is missing | fix the row |
| E014 | two worklog files share a number | rename one with a suffix (`0346b-…`) |
| E015 | the numbered worklog's index zone is stale or absent | `genome emit` (close does it) |
| E017 | `genome.toml` has a key or section genome does not read (a typo switches a check off silently) | fix the spelling; `references/*.md` list every key |
| E016 | an entry surface exceeds its byte budget | move history out (worklog/archive) or replace prose with a pointer |
| W000 | no agent contract | write AGENTS.md: identity, gate, routing table |
| W006 | two dated plans with overlapping titles | keep one owner, archive the other |
| W007 | archive file missing from its INDEX / generation manifest, or a generation without a manifest | add the manifest row (`genome archive` writes it) |
| W008 | README and a docs page answer the same question | the README links, it does not paraphrase |
| W009 | docs page reachable from neither README nor another page | link it or archive it |
| W010 | listed doc longer than `core.toc_lines` without a table of contents | add a contents line; readers still use `genome ask` |
| W011 | living plan keeps a section whose heading says superseded | `genome archive <plan> --section "<heading>" --reason …` |
| W012 | living plan has no "Resume here" section | write one: order of work, in-flight state, next entry points |
| W013 | ruling not applied to any owner | `genome q apply <id> --applied <owner path>` after amending the owner |
| W014 | operator question open longer than `core.ask_days` | re-ask or withdraw |

## records

| Code | Meaning | Fix |
|---|---|---|
| E101 | record without a title | fix frontmatter |
| E102 | record ID used twice | renumber the newer one; IDs are never reused |
| E103 | Superseded/Retired record still in an active dir | `genome rec supersede/retire` moves it |
| E104 | emitted records/idmap zone stale or absent | `genome rec emit` |
| W105 | record cites an unknown ID | the ID is wrong, or its record was never imported (see adoption: detaching) |
| E105 | record frontmatter: ID ≠ file name, required field missing (`records.required`, active records), bad Date / Severity | fix the frontmatter |
| E106 | `Supersedes` names an unknown or still-active record | import the retired record, or `genome rec supersede X --by Y` |
| E107 | an active record is named by no row of `records.governed_by` outside its zones | add its topic row to the doctrine |
| W106 | a live file (not append-only history) cites a record retired with no successor | drop the citation, or cite the record that now owns the topic |

## research

| Code | Meaning | Fix |
|---|---|---|
| W201 | a section on a research surface has a figure but no evidence class | tag it (`[IN-SAMPLE]` …) or cite the artefact instead of the number |
| E202 | a quarantined figure appears on a research surface | strike it; `genome figure <value>` lists every occurrence |
| E203 | a frozen pre-registration's spec part (above `## Results` / `## Verdict`) changed, or the spec vanished | revert it, or re-freeze with `--reason` (stays visible) |
| E204 | hypothesis status does not start with `open testing accepted rejected parked` (+ `research.hyp_statuses`) | use the vocabulary |
| E205 | accepted/rejected hypothesis without evidence (an existing backticked path or a resolving `worklog NNNN`), or citing one that is missing | `genome hyp verdict <id> <status> --evidence <path>` |
| E206 | rejected hypothesis without a re-open condition | add `--reopen "<what new evidence would re-open it>"` |

## ops

| Code | Meaning | Fix |
|---|---|---|
| E301 | file in an owner location not listed in the ownership map | list it with its status and question, or archive it |
| E303 | a link surface cites a path that does not exist | relink to the current owner or restore the file |
| E304 | code reachable from no live surface | archive it under `scripts/archive/<generation>/`, or cite it from its owner doc |
| E305 | regenerable bulk / oversized file tracked in git | `git rm --cached` + `.gitignore`, or `ops.bulk_allow` with a reason |
| E306 | layout: root file not in `ops.root_files`, a suffix not allowed by `ops.dir_suffixes`, a dir missing its `ops.dir_requires` file, a doc naming an `ops.stale_terms` path, a truncation-artefact name | move or rename the file, relink the doc |
| E307 | a tracked symlink points out of the repo (another machine's tree, an external organism) | vendor the file, remove the link, or list it in `ops.external_ok` |

## agents

| Code | Meaning | Fix |
|---|---|---|
| E008 | in-progress board row without a well-formed claim | `genome claim <item>` |

## doctor (informational)

| Finding | Meaning |
|---|---|
| stale state | the state doc names a commit that is not HEAD; regenerate or rewrite it |
| append-only violation | the last commit removed lines from the ledger, worklog or feed; restore them |
| missing role | an enabled module's role has no file; create it or remap it (`native:` / `overlay:`) |
| stale state/entry/runbook | untouched for 30 days |
| ruling not applied | an operator ruling has not reached its owner |
| running job edits | a modified file is being executed by a running process |
| `native:` / `overlay:` | not a finding; the role is owned elsewhere by design |
| live claim | who holds what right now |

## Kinds, drift (added with the kernel upgrade)

| Code | Meaning | Fix |
|---|---|---|
| E501–E511, W501–W502 | a declared kind or one of its entities breaks its schema (E510 an edge to a tainted target, E511 a required relation missing) | `references/kinds.md` lists each |
| W401 / E401 | a manual's covered paths changed after its `verified` sha | review the manual, then `genome verify <doc> --reviewed` |
| W402 | `covers` without `verified` | review, then `genome verify` |
| W403 | the `verified` sha is not in this repo's history | re-verify at a current commit |
| W404 | `covers` matches no tracked file | fix the glob, or the code moved |

