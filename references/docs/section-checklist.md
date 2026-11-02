# Section Checklist by Documentation Archetype

Which sections to include, by archetype. Cited by scoping/ when emitting section plans.

**Two axes apply, not one.** `oss-project-types.md` classifies the *technology
shape* (which files a repo kind needs). This file classifies the *documentation
role* (what job the README does, hence its length and section set). A
curated-list-typed operator chart is normal; a 70-line learning resource is not.
`archetypes.md` holds the routing rule and the detection signals.

## The archetypes and their bands

| Archetype | README is… | Band | Exemplars (measured) |
|---|---|---|---|
| A · Doorway | a thin storefront that links out | 70–340 | n8n 73, opencode 129, hermes 243, openclaw 331 |
| B · Skills-pack | methodology + catalog | 150–400 | superpowers 400, mattpocock 258, karpathy 171 |
| C · Curated list | the data itself | 400–2700 | public-apis 2655, build-your-own-x 505 |
| D · Learning resource | the course | 800–2000 | system-design-primer 1839 |
| E · Monorepo | an assembled package index | 70–340 root + per-pkg | opencode, deepseek-harness, n8n |

## Sections by archetype

`Link` = a link to the dedicated file, never inlined content. `—` = forbidden.

| Section | A Doorway | B Skills-pack | C Curated | D Learning | E Monorepo |
|---|---|---|---|---|---|
| Logo / banner | Yes | Optional | Sponsor banner | Optional | Yes |
| One-sentence hook | Yes | Yes | Yes | Motivation blockquote | Yes |
| Badges | ≤7 | ≤7 | — | — | ≤7 |
| Trust / security blurb | Near install | — | — | — | — |
| Install | One fenced block, `#` per platform | `<details>` per harness (≥5) or one block (≤3) | — | — | Flagship only |
| One working example | Yes | Yes | — | — | Flagship only |
| Proof (image/transcript) | ≥1 | Concrete artifact | Entry density (≥10 links) | ≥1 inline at point of use | Concrete artifact |
| Catalog / index | Link to docs | One-line bullets per item | `## Index` anchor ToC | Topic index | Package table |
| Methodology / principles | — | Yes | — | — | — |
| Study-guide / progression | — | — | — | Timeline matrix | — |
| Co-located per-item READMEs | — | Per-skill `SKILL.md` | Entry micro-template | Per-solution READMEs | Per-package |
| `## Documentation` TOC-to-site table | **Required** | Optional | — | — | **Required** |
| Architecture | Link | Link | — | — | Link |
| Contributing | Link | AGENTS.md gate | `## Contribute` → ISSUE_TEMPLATE | Link | Link |
| License | Link | Link | Link or rights note | Link | Link |
| Deployment / ops | Link | — | — | — | Link |
| Troubleshooting | Link | — | — | — | Link |
| Community / governance | Optional | Optional | — | — | Optional |
| Last reviewed | — | — | — | — | — |

## Forbidden sections (the archetype's negative set)

| Archetype | Never in the README |
|---|---|
| A · Doorway | deep usage, config tables, architecture detail, roadmap, troubleshooting — all belong to the docs site |
| B · Skills-pack | skill internals inlined; per-skill docs; a second copy of any harness install |
| C · Curated list | install, usage, architecture, badges, code fences, a `Last reviewed` date |
| D · Learning resource | install, quickstart, badges, a build-from-source path |
| E · Monorepo | any per-package content duplicated from that package's own README |

## Minimum for every archetype

Name, one-sentence description (what + why), and a path to value — which is a
usage example for A/B/E, the entry micro-template for C, and the study guide for D.

## Length discipline

A README outside its band is a signal to re-check the archetype, not
automatically a defect — but the fix is a docs site or a split
(`--mode=docs-site`), never a longer README.
