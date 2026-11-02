# per-package-contract.md — Per-package README contract (archetype E)

> Covers the monorepo-root-as-package-index pattern: the assembled root README is a thin index, never a duplicate of package content; per-package READMEs own depth; `indexion doc readme --per-package` scaffolds non-overwriting; drift is verified via `plan drift` with a `--vocab-threshold=0.05` CI guard; and the `packages` root section type currently emits a link table, not rich per-entry prose. Plan §3 row E (line 177), §4.1a lines 255–257, 291.

## When to use / When NOT to use

**Use when** the repo is a monorepo with ≥2 packages that ship independent functionality (archetype E — plan §1.2 line 49: "Monorepo / multi-package | an assembled package index | 70–330 root | opencode, deepseek-harness, n8n").

**Do NOT use** when the repo is single-package, or a curated list (C) where the README *is* the data. Do not apply the contract to package directories that are private internals with no public API. Do not hand-write root-README prose about individual packages — point to the per-package README instead.

> This axis is orthogonal to `oss-project-types.md`, which classifies by technology shape (cli-go, library-python, operator, helm). A doorway-typed operator chart is normal (plan §4.1a lines 303–307); a 70-line curated list is not. The contract applies when the *documentation role* is E.

## The mechanism

### Root README is an assembled index, not a duplicate

plan §3 row E (line 177) requires these root sections:

| Required section | Plan citation |
|---|---|
| Hook (1-sentence problem) | plan §3 line 177 |
| Package table (name · what · status · link) | plan §3 line 177 |
| Quick-start for the flagship package only | plan §3 line 177 |
| Per-package contract | plan §3 line 177 |
| `## Documentation` (TOC-to-site table) | plan §1.3 mechanism #1 line 55; plan §3 line 177 |
| Contributing | plan §3 line 177 |

**Forbidden:** duplicating any per-package README content (plan §1.3 mechanism #1 line 55: "`## Documentation` as a TOC-to-site table ... keeps the README thin"; plan §3 line 178: "A and E compose; the root of a monorepo is an A-type doorway with a package table").

### Non-overwriting generation

`indexion doc readme --per-package <paths>` creates README.md in each package that does not already have one — it never overwrites (indexion-readme SKILL.md Step 3). To regenerate, delete first.

### Additive / drift discipline

After regeneration or any hand-edit of the root README, verify the change is purely additive:

```bash
# Snapshot the previous version
git show HEAD:README.md > /tmp/README.before.md

# Compare against the new version
indexion plan drift --top=20 /tmp/README.before.md README.md
```

What to look for:
- `Drift terms in /tmp/README.before.md (missing on the other side): (none)` — nothing was removed
- `Drift terms in README.md (missing on the other side): …` — exactly the new vocabulary you intended

CI guard (indexion-readme SKILL.md Step 7):

```bash
indexion plan drift --vocab-threshold=0.05 /tmp/README.before.md README.md
# exits 1 if cosine_distance > 0.05
```

Cross-lingual drift detection uses the same mechanism on README pairs (`README.md` ↔ `README-ja.md`) (indexion-readme SKILL.md Step 7).

### doc.json config shape

The root section types and package fields (indexion-readme SKILL.md Step 2):

| Root section type | Behavior |
|---|---|
| `static` | Include a markdown file verbatim |
| `toc` | Insert a table-of-contents heading |
| `packages` | Pull in entries from the `packages` array, filtered by glob |

| Package field | Purpose |
|---|---|
| `include_in_root` | Whether to include in the assembled root README |
| `sections` | README headings to extract; honored by per-package extraction flows |

### Known limitation: `packages` root section emits a table, not rich expansion

`{ "type": "packages" }` in the root currently emits a markdown table of package links with empty descriptions — it does NOT expand per-entry `overview` / `usage` sections inline (indexion-readme SKILL.md "Known limitation"). Two consequences:

1. Rich per-command prose in the checked-in root README is **hand-maintained**, not generated.
2. To see how much of your README is hand-curated, diff `doc readme --config -o=/tmp/regen.md` against the checked-in README — large diffs mean mostly hand-curated content.

Always run `plan drift` after hand-edits to the root README (indexion-readme SKILL.md "Common pitfalls").

### Template-mode side effect

`doc readme --template=<t> <paths...>` walks the given paths and **auto-creates** per-package READMEs for any package that lacks one — even without `--per-package` (indexion-readme SKILL.md Step 3). On broad paths (`cmd/`, `src/`), expect new files in unrelated packages.

**Mitigation:** pass a narrow path, or run `git status` afterward to review and clean up unintended creations.

## Worked example — opencode

opencode is archetype A+E: a 129-line root landing page that is an A-type doorway with a package table (plan §1.1 line 22: `anomalyco/opencode | **A+E** | 129 | 7 | 3 | 2 | 1 | astro starlight | ~560 | yes (~35)`). The root README links out to ~35 per-package READMEs. It never duplicates package internals — it indexes them. The per-package contract (purpose, configuration, extension points, limitations, Model Experience) lives in each package README, not the root.

n8n is also A+E but slimmer: 73 lines, `yes` for per-package READMEs (plan §1.1 line 24). deepseek-harness is A+E at 77 lines with `yes` per-package READMEs and the script-enforced contract (plan §1.1 line 23; plan §1.3 mechanism #5).

## Executable contract checklist

`verify_per_package_readme.py` (plan §4.1a line 291) enforces this checklist on every `packages/*/`:

| Section | Must be present | Plan citation |
|---|---|---|
| Purpose | Yes — one-sentence what-this-package-does | plan §4.1a lines 255–257 |
| Configuration | Yes — env vars, flags, config files | plan §4.1a lines 255–257 |
| Extension points | Yes — hooks, plugins, interfaces | plan §4.1a lines 255–257 |
| Limitations | Yes — known constraints, not-yet-implemented | plan §4.1a lines 255–257 |
| Model Experience | Yes — how the package affects agent model behavior | plan §1.3 mechanism #5 line 67–69 (deepseek `verify-package-readme-model-experience.ts`) |

deepseek enforces its contract via two TypeScript scripts declared in `packages/README.md` (plan §1.3 mechanism #5, lines 67–69). The plan extends this to `verify_per_package_readme.py` (plan §4.1a line 291). 7/11 audited repos ship per-package READMEs; 2 of them (deepseek, hermes) have script-enforced contracts (plan §1.4 aggregate line 33).

## What to check before shipping

- [ ] Root README has exactly the 6 required sections — no per-package content inlined.
- [ ] Package table has columns: name, what, status, link (plan §3 line 177).
- [ ] Quick-start covers only the flagship package.
- [ ] Each `packages/*/` README passes the 5-section contract checklist above.
- [ ] `indexion doc readme --per-package` was run with a narrow path — check `git status` for stray creations.
- [ ] `doc readme --config -o=/tmp/regen.md` diffs against the checked-in README are reviewed for hand-curated drift.
- [ ] `indexion plan drift --vocab-threshold=0.05` passes in CI.
- [ ] The `indexion` binary is available — `plan drift` requires it (plan §4.1a line 313).
- [ ] `verify_per_package_readme.py` exits 0 on all `packages/*/` directories.
