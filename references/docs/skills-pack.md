# Skills-Pack — Archetype B (methodology + catalog)

> Documentation archetype B: the README teaches a methodology first, then catalogs available agent-config/skill units as one-line bullets linking to per-skill `SKILL.md` files. README length band 150–400 lines. Exemplars: obra/superpowers (400 L), mattpocock/skills (258 L), multica-ai/andrej-karpathy-skills (171 L).
>
> This classifies the *documentation role* the README plays — the *technology shape* of the repo (CLI-go, library-python, operator, helm) is classified separately by `oss-project-types.md`; the two axes are orthogonal and never conflict. Gold-standard README patterns live in `readme-craft.md`; this file is an additional reference, not a replacement. See `archetypes.md` for the full 5-archetype routing table.

## When to use / When NOT to use

**Use B when** the repo's product IS a collection of agent/skill config units (each a `SKILL.md`), and the README's job is to teach the methodology before installation, then provide a browseable catalog. Target reader: an engineer configuring an agent.

**Do NOT use B when:**
- The repo ships executable code as its primary product → use A (doorway) via `readme-craft.md` patterns, or E (`per-package-contract.md`).
- The README is a thin storefront linking to a docs site → use A.
- The content is a curated index of third-party resources → use C ([`curated-list.md`](curated-list.md)).
- The content is a structured learning curriculum → use D ([`learning-resource.md`](learning-resource.md)).
- The repo has a docs site as its primary face → use A + `--mode=docs-site`; B ships **no docs site** (§1.1: 0 of 3 B exemplars have one — only 6/11 audited repos total have a site).

## Detection signals

| Signal | Evidence |
|---|---|
| Product is `SKILL.md` files, not installable code | superpowers 48 doc pages + 15 pkg READMEs; mattpocock 29 doc pages; karpathy 5 doc pages (§1.1) |
| Zero or near-zero badges; zero images | superpowers 0 badges / 0 images; karpathy 0 badges / 0 images (§1.1) |
| Catalog section = pure bullets, zero code fences in catalog | mattpocock Reference ~50 lines of pure bullets for 27 promoted skills, 0 code fences (assignment brief) |
| Install appears AFTER methodology, not first | superpowers: 7-step SDLC precedes install (assignment brief) |
| Before→after problem/principle tables in README | karpathy 2 tables (§1.1: karpathy 2 tables, 0 badges) |
| `## How to Know It's Working` or equivalent declarative criteria | karpathy section title (§1.3 #16) |
| No docs site; README is the product | 0 of 3 B exemplars have a docs site (§1.1) |

**Anti-patterns to check:**
- **Missing LICENSE** — karpathy asserts MIT twice in prose but ships **no LICENSE file** (§1.1 p.11 line 39). Assert license only via a real `LICENSE`, never inline-only.
- **Stale owner references** — karpathy install commands carry owner references that diverge from the current repo owner (assignment brief). Verify every `git clone`/`pip install` owner matches the repo's actual owner.
- **Catalog depth** — do NOT inline per-skill internals in the README; point each bullet to its `SKILL.md`.
- **Install-first** — this violates B's methodology-before-installation ordering. README must teach *why* before *how to install*.

## Section order (§3, line 174)

Ordered — do not shuffle:

1. **hook** — one-sentence problem statement
2. **the problem** — before→after 2-column table (problem → principle)
3. **methodology / principle list** — the how-to, ordered as steps
4. **install matrix** — `<details>`/`<summary>` per harness for 5+ platforms (§1.3 #3); one fenced block with inline `#` comments for 2–3 platforms (§1.3 #2)
5. **catalog** — one-line bullets, each linking to a per-skill `SKILL.md`; never inline internals (§3)
6. **philosophy / How to Know It's Working** — declarative success criteria (§1.3 #16)
7. **AGENTS.md gate** — the acceptance test
8. **license** — link-out only (never inlined)

## Forbidden sections

- Inlining skill internals or per-skill deep docs in the README (point to `SKILL.md` instead)
- Per-skill tutorials or walkthroughs in the README
- Inline LICENSE text
- Install as the first content block (violates methodology-before-installation)

**Note on `readme-craft.md` divergence:** Pattern 8 there (Problem → Install → See It Work → …) is install-first; B inverts this deliberately (methodology first, install second). Pattern 6 (collapse depth, don't delete) is the rationale for the `<details>` install matrix.

## The mechanism that makes it work

| §1.3 # | Mechanism | Source repo | How B uses it |
|---|---|---|---|
| 16 | Declarative success criteria (`## How to Know It's Working`) | karpathy (171 L) | Reader self-verifies completion without asking |
| 3 | Collapsible `<details>` install matrix, zero static height | mattpocock (258 L) | 5 harness `<details>` blocks; reader self-selects; complements #2 (§1.3 #3) |
| 4 | Canonical install-block source file + `<canonical-block>` tags | mattpocock | `.agents/install-block.md` pulled verbatim by README, changesets, and docs — eliminates install drift (§1.3 #4) |
| 2 | Parallel-platform install in one fenced block, inline `#` comments | opencode, hermes, openclaw | Used when 2–3 platforms; #3 handles 5+ (§1.3 #2) |

**Companion (not a §1.3 mechanism):** superpowers ships `RELEASE-NOTES.md` as architectural memory — 109 KB, per-release feature breakdowns with issue numbers and contributor attribution (§1.3 #15). The README links to it, never inlines it.

**Triple-mount source of truth (karpathy technique, assignment brief):** one canonical skill definition is mounted to `CLAUDE.md` + `.cursor/rules/` + `SKILL.md` so the agent's context layers stay in sync from a single source. Not a mechanism in §1.3 but a B-specific discipline to prevent drift.

## Verification

```bash
python3 ~/.agents/skills/project-genome/scripts/docs/score_readme.py --archetype skills-pack README.md
```

- `--archetype skills-pack` switches the length band to 150–400 and relaxes `code_examples_2plus`, `visual_proof_3plus`, `badges_3_to_8` (B exemplars use 0–1 badges, 0 images) (§5 G8, G9).
- Expect: `length_150_400` passes; `catalog_bullets_link_skm` (new check) verifies each catalog entry links to a `SKILL.md`.
- Regression: like the archetype-C-correct README (−4/8) and the curriculum README (−2/8) measured in §1.4 line 158, a B-shaped README scores negatively under the un-scoped rubric; under `--archetype skills-pack` it must score ≥8/8 (§5 line 399–405).

**Acceptance test (superpowers AGENTS.md gate, assignment brief):** send "Let's make a react todo list" and verify brainstorming auto-triggers; PRs failing the 6-point pre-PR checklist reject at an estimated ~94% rate. The README must link to `AGENTS.md` and assert the same gate.
