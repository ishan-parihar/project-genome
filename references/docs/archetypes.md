# Documentation Archetypes — what job does the README do?

> Five documentation *roles*, orthogonally to `oss-project-types.md`'s technology
> shapes. Cite from `readme-craft.md` (how to write a README) and
> `--mode=docs-site` (how the README relates to a docs site). When a task is
> unclear, descend here first.

## The one routing question

> **Is the README the product, or the doorway to the product?**

- **The product** → the README *contains* the value (C, D). Length is set by the
  content; a 2655-line list can be correct.
- **The doorway** → the README *describes* the value and links to it (A, B, E).
  Length is a budget to stay under; 73 lines can be correct.

Get this wrong and every downstream check is wrong. A curated list judged
against doorway rules loses points for having no install section; a doorway
judged against curated-list rules loses points for being too short.

## The archetypes

| Archetype | README is… | Band | Section authority | Exemplars (measured) |
|---|---|---|---|---|
| **A · Doorway** | a thin storefront that links out | 70–330 | this file | n8n 73, opencode 129, hermes 243, openclaw 331 |
| **B · Skills-pack** | methodology + catalog | 150–400 | `skills-pack.md` | superpowers 400, mattpocock 258, karpathy 171 |
| **C · Curated list** | the data itself | 400–2700 | `curated-list.md` | public-apis 2655, build-your-own-x 505 |
| **D · Learning resource** | the course | 800–2000 | `learning-resource.md` | system-design-primer 1839 |
| **E · Monorepo** | an assembled package index | 70–330 root | `per-package-contract.md` | opencode, deepseek-harness, n8n |

Bands are evidence-derived, not aspirational: across the 11 audited repos the
archetype predicts length within ±2×. A README outside its band is a signal to
re-check the archetype, not automatically a defect.

**A and E compose.** A monorepo's root README is a doorway with a package table;
each package's own README is scoped to that package's audience.

## Detection signals

Detect from repo shape *before* reading the README — then confirm.

| Signal | Archetype |
|---|---|
| Product is a directory of `SKILL.md` / prompt files; language breakdown dominated by markdown | **B** |
| `.gitattributes` carries `*.md linguist-documentation=false` | **C** |
| Sole substantive content is the README; `docs/` absent or token | **C** or **D** |
| One very long README (1500+ lines) with a study-guide/index spine | **D** |
| Multiple package manifests (`packages/*/package.json`, `cmd/*`, `src/bin/*`) | **E** |
| A `## Documentation` section that is a table of links to an external site | **A** |
| README under ~150 lines, install near the top, deep usage links out | **A** |

Confirm by reading the first screen: what does the README do in its opening
3 lines — advertise, catalogue, teach, or index?

## Section plans

The authoritative per-archetype section sets live in the files named above. The
cross-cutting rules:

**Every archetype, minimum:** name, one-sentence description (what + why), and a
usage path with an example. `section-checklist.md` holds the full matrix.

**A · Doorway** — logo/banner, hook, badges ≤7, install as ONE fenced block with
inline `#` comments per platform, one working example, a `## Documentation`
table mapping each topic to its docs URL, then Contributing/License/Security as
links. **Forbidden:** deep usage, config tables, architecture, roadmaps,
troubleshooting. All of those are the docs site's job.

**B · Skills-pack** — the problem (before→after 2-column tables), methodology,
install matrix (`<details>` per harness when ≥5, one fenced block when ≤3),
catalog as one-line bullets linking each per-skill file, philosophy,
AGENTS.md gate, license. **Forbidden:** inlining skill internals.

**C · Curated list** — sponsor banner, `## Index` anchor ToC, category `###`
sections, entry micro-template, `## Contribute` pointing at the issue template,
license. **Forbidden:** install, usage, architecture, badges, code blocks.

**D · Learning resource** — motivation blockquote, study-guide timeline matrix,
topic index, co-located per-solution READMEs, multi-format export, translation
bar, license. **Forbidden:** install, quickstart, badges.

**E · Monorepo root** — hook, package table (name · what · status · link),
quick-start for the flagship package only, the per-package contract,
`## Documentation`, contributing. **Forbidden:** duplicating any package's
content.

## What changes about the checks

`score_readme.py --archetype <name>` makes the rubric archetype-relative:

| Check | README-shaped assumption | Archetype-relative |
|---|---|---|
| length | 100–170 | the archetype's band (A/E 70–330, B 150–400, C 400–2700, D 800–2000) |
| `visual_proof_3plus` | always required | required for A/E; a curated list's proof is its entry density |
| `code_examples_2plus` | always required | required for A/B/E; C and D legitimately ship none |
| `badges_3_to_8` | always required | A/B only; C/D/E exemplars often use zero |
| `install_before_arch` | always required | A/B/E only; C/D have nothing to install |

Without this flag the rubric scores a correct curated list −4/8 and a correct
curriculum −2/8 (measured during the audit). Run it with the flag.

## Boundaries

- **Not a technology taxonomy.** `oss-project-types.md` answers *which files does
  this repo kind need* (cli-go → `docs/CLI_REFERENCE.md`). This file answers
  *what job does the README do*. Both apply; neither overrides the other.
- **Not a doc-site choice.** That is `docs-site.md`.
- **Not a per-file style guide.** That is `style-guide.md` + `de-slopify.md`.
- **Not a length target for editing.** If a README needs to grow past its band,
  the fix is usually a docs-site or a split, not a longer README.
