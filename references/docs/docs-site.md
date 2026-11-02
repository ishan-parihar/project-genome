# Docs-Site Mode — when the README stops being enough

> `--mode=docs-site`. Decide whether a repo needs a docs site, pick the shape,
> and write the delegation contract that keeps the README thin. Cited from
> `readme-craft.md` (how to write the README) and `archetypes.md` (what job it
> does).

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## When to use / when NOT to use

| Use when | Do NOT use when |
|---|---|
| The README has grown past its archetype band and the overflow is real depth, not padding (A, E) | The README is merely long — split sections, don't build a site (B, C, D) |
| Users arrive from search and need one page answering one question (A) | The audience is future-you in one repo (config/personal archetypes) |
| Configuration surface exceeds ~10 options or has cross-cutting modes | A single `docs/` markdown tree renders fine on GitHub |
| There are per-package READMEs needing an index (E) | The repo's product *is* the README (C) or a single curriculum (D) |
| Multiple locales are planned or already drifting | No translation demand — add `i18n.md` mechanics later |

6 of the 11 audited repos run a docs site. The 5 that do not — superpowers,
build-your-own-x, public-apis, system-design-primer, andrej-karpathy-skills —
are exactly the 5 where the README is not a doorway. That correlation is the
decision rule.

## Step 1: Classify, then pick the shape

`archetypes.md` gives the archetype; `oss-project-types.md` gives the technology
shape. Both apply. Then:

| Repo shape | Docs tree |
|---|---|
| A (platform/app) | `docs/guide/` + `docs/reference/` + `docs/adr/` |
| B (skills-pack) | per-skill docs page mirroring the catalog + a canonical install block |
| C (curated list) | **no docs site** — CONTRIBUTING + validators are the contract (`ci-validation.md`) |
| D (learning resource) | README as spine + co-located per-solution READMEs + an export script |
| E (monorepo) | root as package index + a per-package contract (`per-package-contract.md`) |

## Step 2: Choose the framework

Decision table from the audited repos. "None" is a legitimate answer and the
most common one.

| Framework | Pick when | Observed cost | Evidence |
|---|---|---|---|
| **none** (repo markdown) | ≤ ~30 pages, no search/i18n need, GitHub render suffices | zero | superpowers (48 pages, repo-only), system-design-primer (single 1839-line file) |
| **Docusaurus** | versioned docs, many pages, docs live beside code | ~455 pages, 56 CI workflows | hermes-agent — `website/docs/` |
| **VitePress** | bilingual from one markdown source, manifest-driven sidebar | ~96 canonical pages → ~190 routes | deepseek-harness — `website/docs.ts` |
| **Astro Starlight** | docs belong to a site you already ship, per-package docs | ~560 pages, 17 locales | opencode — content in `packages/web/src/content/docs` |
| **GitBook** | the docs are the marketing site, low Git overhead | ~100 pages, only 3 hand-written in repo | n8n |
| **custom** | you need redirect control and bespoke components | ~1370 pages, 330 redirects in one config | openclaw — `docs.json` |

Rules that fell out of the audit:

- **Docs belong in the repo unless they clearly don't.** n8n put everything
  user-facing off-repo and kept only 3 hand-written pages plus ~97 generated
  schema docs in `docs/`. opencode and hermes kept theirs in-repo and projected
  them to a site. Both work; do not mix the two in one repo.
- **Keep the content source and the render site separate.** deepseek's manifest,
  opencode's locale-sync workflow, and hermes's table all exist so one markdown
  source projects to many routes without copy-paste.
- **Version the docs with the code.** A docs site whose content is not in the
  same repo rots invisibly.

## Step 3: Write the delegation contract

This is the output of the mode — a short, explicit statement of what the README
keeps and what it hands off. It is the thing that prevents the failure
`project-genome` law #1 ("one owner per question") exists to catch.

```markdown
## Delegation contract — <repo>

The README owns: what this is (1 sentence), how to install it (one fenced
block), one example that proves it works, and the index below.

Everything else lives in docs/:
| question | owner |
|---|---|
| how do I configure X | docs/guide/configuration.md |
| what are the CLI flags | docs/reference/cli.md |
| why is it built this way | docs/decisions/AD-NNN-*.md |
| what bit us and what law it produced | docs/regressions/RG-NNN-*.md |

The README MUST NOT paraphrase any page above — it links. A README section and
a docs page answering the same question is a defect (docs_lint D002).
```

## Step 4: Verify

```bash
doc/scripts/docs_lint.py --root <repo>          # dead links, overlap, orphans, anchors
doc/scripts/score_readme.py <repo>/README.md --archetype doorway
```

`docs_lint.py` reports `D001` dead outward links, `D002` README/docs
paraphrasing (advisory), `D003` orphan doc pages, and `D004` dead ToC anchors.
`D002` is the boundary check: it fires when the README and the docs both claim a
question.

## What this mode does not decide

- Hosting, CI for the site build, or DNS — operational, out of scope.
- The prose quality of any page — that is `readme-craft.md` + `de-slopify.md`.
- Translation content — `i18n.md` covers the mechanism only.
