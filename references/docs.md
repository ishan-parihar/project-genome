# Docs — the outward pair (`README.md` + `docs/`)

The genome's roles describe what the project knows internally (state, register,
records, evidence). This file covers the **outward** surface: the README a
stranger reads first and the `docs/` tree behind it. They are the same
discipline — one owner per question, mutability declared, claims traceable —
pointed at a reader instead of an agent.

Absorbed from the standalone `doc` skill. Depth lives in
`references/docs/`; this file carries the decisions.

## Pick the mode first

| Mode | Artifact | Read |
|---|---|---|
| *(default)* | API docs, code-maps, coverage + validation | `docs/default-mode.md` |
| `readme` | Gold-standard README (interview → generate → de-slop → checks) | `docs/readme-craft.md` |
| `oss` | OSS doc pack (CONTRIBUTING / CHANGELOG / AGENTS.md): audit + scaffold | `docs/oss-pack.md` |
| `docs-site` | README ↔ docs-site split: framework choice, tree, delegation contract | `docs/docs-site.md` |

Trigger routing: "rewrite the README" → `readme`; "scaffold contributing" /
"audit OSS docs" → `oss`; "split my docs" / "which docs framework" / "README
is getting too long" → `docs-site`.

Every README generate or rewrite runs `docs/de-slopify.md` **before** the
deterministic checks. A README that passes the checker and reads like a
brochure has failed.

## The four rules that make a doc trustworthy

1. **Ground every claim in the current repository.** Plausible, stale prose is
   the defect; a gap you disclose is not.
2. **Research in bounded chunks against a coverage ledger.** List the chunks
   (modules, commands, config surfaces), mark each `read` / `skimmed` /
   `skipped` with a reason, and claim only on `read`. An unledgered wander
   makes coverage "whatever the walk touched", and nobody can say what the
   document silently omits.
3. **Hold to the conceptual-surprise floor.** Name at least one thing a reader
   who already skimmed the code would not have known — an invariant, an
   ordering constraint, a why, a trap. If nothing qualifies, report the doc as
   reference-only coverage. Prose that renarrates signatures is the *mirror
   doc* failure: accurate, complete, useless.
4. **Never overwrite operator-owned docs unasked.** In `oss` mode create
   missing files only; `refresh` is a separate, explicitly confirmed path.

## Where docs meet the genome

`docs/project-genome-seam.md` is the boundary: which documents are genome
roles (state, worklog, records, evidence) and which are outward docs, plus the
W008/W009 lint codes that fire when the two disagree. Read it before adding a
document whose role is ambiguous — a doc that answers a question the genome
already owns is a second owner, which rule 1 forbids.

## Validation, by mode

```bash
bash scripts/docs/validate.sh                  # skill contract
python3 scripts/docs/score_readme.py README.md --archetype <archetype>   # readme
python3 scripts/docs/docs_lint.py --root <repo>                          # docs-site
python3 scripts/docs/verify_per_package_readme.py                        # monorepo
bash scripts/docs/docs-check.sh --staged       # pre-commit gate
```

Report the validators you ran and the gaps you did not close. Never imply full
coverage from a passing script.

## Reference map

`references/docs/` carries the full set: the four mode workflows, the five
README archetypes (`archetypes.md` — doorway, skills-pack, curated list,
learning resource, monorepo) with their length bands, the 16 transferable
mechanisms, style and prose rules, admonition syntax, i18n patterns,
per-package contracts, CI validation, the audit rubric, and the executable
`.feature` specs. Read the one the mode names; do not read them all.

`references/docs/project-genome-seam.md` is required before touching a document
whose role is unclear.
