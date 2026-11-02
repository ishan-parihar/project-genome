# Learning Resource — Archetype D (README-as-course)

> Documentation archetype D: the README IS the course — a single-file spine + index that carries a structured learning path, a study-guide timeline matrix, co-located worked solutions, and multi-format export. README length band 800–2000 lines. Exemplar: donnemartin/system-design-primer (1839 L).
>
> This classifies the *documentation role* the README plays — the *technology shape* is classified separately by `oss-project-types.md`; the two axes are orthogonal. Gold-standard README patterns live in `readme-craft.md`; this file is an additional reference, not a replacement. See `references/docs/archetypes.md` for the routing table.

## When to use / When NOT to use

**Use D when** the repo teaches a curriculum. The README is a single-file spine with an in-page anchor index — there is **no docs site** to host it. The learner follows a timeline-driven study guide, checks answers in co-located solution READMEs, and optionally exports to epub/Anki. Target reader: someone learning the subject end-to-end.

**Do NOT use D when:**
- The repo ships installable code or configs → use A (doorway), B ([`skills-pack.md`](skills-pack.md)), or E (`per-package-contract.md`).
- The content is a reference catalog of third-party links → use C ([`curated-list.md`](curated-list.md)).
- You need multi-page site navigation or search → use `--mode=docs-site`.
- The material is reference-only (API docs, CLI reference) without a progression → use A + default mode.

## Detection signals

| Signal | Evidence |
|---|---|
| Single README file, no docs site | system-design-primer 1839 L, `none` docs site (§1.1) |
| Study-guide matrix with Short/Medium/Long columns | system-design-primer matrix mapping interview timelines to breadth-vs-depth actions (§3, assignment brief) |
| 0 badges deliberately; language link bar at top | system-design-primer 0 badges (§1.1) + 28-language link bar (assignment brief) |
| Motivation blockquote as onboarding, not "How to use" | system-design-primer onboarding via blockquote (§3, assignment brief) |
| 8 co-located solution READMEs, same h2 structure | system-design-primer 8 pkg READMEs (§1.1: yes (8)) |
| Multi-format export files present | `generate-epub.sh` + `epub-metadata.yaml` + `resources/flash_cards/*.apkg` (3 Anki decks) (assignment brief) |
| Images embedded inline at point of discussion | system-design-primer 39 images (§1.1), 29 HTML `<img>` + 10 markdown (assignment brief) — not a proof gallery |

## Section order (§3, line 176)

Ordered — do not shuffle:

1. **language link bar** — 28-language bar at top, replaces badges (§1.1: 0 badges)
2. **motivation blockquote** — the onboarding hook (§3)
3. **study-guide timeline matrix** — `| Short | Medium | Long |` mapping interview timelines to breadth-vs-depth actions (§3, §1.2)
4. **topic index** — in-page anchor table linking to each `##` section
5. **spine sections** — the main `##` backbone (29 h2, system-design-primer) covering each topic
6. **per-topic worked-solution READMEs** — 8 co-located child READMEs, each reusing the same h2 structure (§1.1: yes (8))
7. **multi-format export** — `generate-epub.sh` + `epub-metadata.yaml` + `resources/flash_cards/` (§3)
8. **CONTRIBUTING** — covers the translation-maintainer workflow (§1.1: system-design-primer has CONTRIBUTING)
9. **license** — link-out only

## Forbidden sections

- Install instructions (nothing to install — this is a learning resource)
- Quickstart or "How to use this repo" section (onboarding is via the motivation blockquote)
- Badges (system-design-primer uses 0 deliberately — §1.1 p.11 line 34; assignment brief)
- Proof gallery at the bottom (images embed inline at point of discussion — assignment brief)

**Note on `readme-craft.md` divergence:** Pattern 8 (Problem → Install → See It Work) is install-first; D has no install and leads with a motivation blockquote + study-guide matrix. Pattern 3 ("show, don't claim") manifests as 8 worked-solution READMEs — one `##` per question with the answer co-located.

## The mechanism that makes it work

| §1.3 # | Mechanism | Source repo | How D uses it |
|---|---|---|---|
| 7 | i18n locale-sync workflow keyed off English source paths | opencode `.github/workflows/docs-locale-sync.yml` | Keeps the 28-language link bar disciplined — source paths are the canonical anchor (§1.3 #7) |
| 13 | Language-selector badges → translated READMEs | hermes, shields `style=for-the-badge` | system-design-primer uses a 28-language *link bar* instead — same principle, link to `README.xx.md`, no badges (§1.3 #13) |
| 8 | Single manifest projecting one markdown source to many locales | deepseek `website/docs.ts` (`docsPages`, `pairedPages`, `localeCollections`) | `epub-metadata.yaml` projects the single README spine + solution READMEs to epub + Anki (§1.3 #8, assignment brief) |

**The single-file spine is the critical mechanism.** system-design-primer (1839 L, 172 headings, §1.1) ships 0 doc pages — the README backbone (29 `##` sections), the in-page anchor index, and the study-guide matrix are the entire course. Multi-format export (`generate-epub.sh` + pandoc, `epub-metadata.yaml`, 3 `.apkg` Anki decks) is generated from that one source. No docs site, no separate hosting.

**Image policy:** 39 images total (29 HTML `<img>` + 10 markdown, assignment brief). Each embeds inline at the point of discussion — never a proof gallery at the bottom. HTML `<img>` for sizing control; markdown `![alt](url)` for the rest.

## Verification

```bash
python3 ~/.agents/skills/project-genome/scripts/docs/score_readme.py --archetype learning-resource README.md
```

- `--archetype learning-resource` is the §5 Phase-1 flag for archetype D (§5 line 399: "system-design-primer must not score 0/8 under `--archetype learning-resource`").
- Expect: `length_800_2000` passes; `badges_0` passes (D uses 0 — §1.1); `code_examples_2plus` is absent/ignored; `visual_proof_3plus` counts 39 images (§1.1).
- Regression: system-design-primer's 1839-line README currently scores **0/8** under the un-scoped rubric (§1.4 G3, line 152); under `--archetype learning-resource` it must score ≥8/8 (§5 line 399–405).
- Structural: verify the study-guide matrix `| Short | Medium | Long |` resolves every `##` topic index anchor; verify each of the 8 solution READMEs reuses the same h2 structure as the spine.
