# Curated List — Archetype C (README-as-data)

> Documentation archetype C: the README IS the data — a curated, browseable index of third-party resources. README length band 400–2700 lines. Exemplars: public-apis/public-apis (2655 L), codecrafters-io/build-your-own-x (505 L).
>
> This classifies the *documentation role* the README plays — the *technology shape* is classified separately by `oss-project-types.md`; the two axes are orthogonal. Gold-standard README patterns live in `readme-craft.md`; this file is an additional reference, not a replacement. See `archetypes.md` for the full 5-archetype routing table.

## When to use / When NOT to use

**Use C when** the repo has no installable product of its own — its value is the curated list. The README is the data, the index, and the contribution contract all at once. Target reader: someone browsing entries.

**Do NOT use C when:**
- The repo ships executable code or agent configs → use A (doorway), B ([`skills-pack.md`](skills-pack.md)), or E (`per-package-contract.md`).
- The content teaches a structured learning path → use D ([`learning-resource.md`](learning-resource.md)).
- You need per-entry interactivity beyond what GFM tables support → use `--mode=docs-site` with a real framework.
- The list is small (<400 lines) and fits in a section → fold it into an A-type README's Resources section.

## Detection signals

| Signal | Evidence |
|---|---|
| README is pure markdown, no docs site | build-your-own-x `none`; public-apis `none` (§1.1) |
| `.gitattributes` with `*.md linguist-documentation=false` | build-your-own-x (§1.3 #14) — keeps language graph from drowning in markdown |
| 0–2 badges, no badges preferred | build-your-own-x 2 badges; public-apis 0 badges (§1.1) |
| `## Index` or `## Contents` as sole ToC | build-your-own-x 30 in-page anchor links; public-apis `## Index` (§1.1: 35 headings for build-your-own-x) |
| Categories use `###` headers with tables or bullets | public-apis 53 tables across 51 categories (§1.1: 53 tables); build-your-own-x 35 headings (§1.1) |
| `## Contribute` is 1–3 bullets; real contract is elsewhere | build-your-own-x `## Contribute` = 2 bullets (assignment brief); rejection rule lives in `.github/ISSUE_TEMPLATE/` |
| Entry micro-template `[**Lang**: _Title_](url)` | build-your-own-x 391 bullet lines, 0 code fences, 0 tables (assignment brief) |

**Rejection rule (build-your-own-x, assignment brief):** the ISSUE_TEMPLATE explicitly rejects "no frameworks, libraries, guides for frameworks/libraries or tutorials that glue just other libraries together." Every new entry must pass this gate before review.

## Section order (§3, line 175)

Ordered — do not shuffle:

1. **sponsor banner** — optional, non-intrusive
2. **one-line hook** — what the list is for
3. `## Index` — anchor table of contents linking to each category
4. **category `###` sections** — one per category; each entry follows the micro-template
5. **entry micro-template** — `[**Lang**: _Title_](url)` with a single-line description
6. `## Contribute` — 2 bullets max; points to `ISSUE_TEMPLATE.md`
7. **license / rights** — bottom-loaded badge + paragraph, not a LICENSE file

## Forbidden sections

- Install instructions (there is nothing to install)
- Usage examples or tutorials (you are indexing, not teaching)
- Architecture or deep-dive sections
- More than 2–3 badges (public-apis uses 0; build-your-own-x uses 2 — §1.1)
- Code blocks (build-your-own-x: 0 code fences across 505 lines — assignment brief)
- Inline LICENSE text (rights are a bottom-loaded badge + paragraph — see below)

## The mechanism that makes it work

| §1.3 # | Mechanism | Source repo | How C uses it |
|---|---|---|---|
| 6 | CI-enforced doc validation: `scripts/validate/format.py` | public-apis (2655 L) | Alphabetical order; ≥3 entries per category; ≥5 columns per row; description ≤100 chars; closed Auth/HTTPS/CORS vocabularies; every cell padded exactly 1 space (§1.3 #6) |
| 6 | CI link validation: `scripts/links.py` + daily `cron` sweep | public-apis | Duplicate-link checker + daily dead-link sweep on every push/PR (§1.3 #6) |
| 14 | `.gitattributes` `*.md linguist-documentation=false` | build-your-own-x (505 L) | Keeps the GitHub language graph from drowning in markdown (§1.3 #14) |

**CI validation is the critical mechanism.** A 2655-line README (public-apis, §1.1) is only maintainable because every entry is schema-checked at push time.

| Validator | Checks |
|---|---|
| `format.py` | Alphabetical order within category; ≥3 entries per category; ≥5 columns per row; description ≤100 chars; first letter capitalized; no trailing punctuation; `Auth`/`HTTPS`/`CORS` vocabularies closed; every cell padded exactly 1 space |
| `links.py` | Duplicate-link detection across the whole README |
| `cron` (daily) | Dead-link sweep on all entries |

**README.md is hand-authored, not generated.** A common assumption is that a 2655-line list is generated from a JSON data file. It is not — `README.md` is the canonical source, and CI validates it directly. The maintainers edit markdown and let `format.py` enforce structure. Do NOT generate from data; the README IS the data.

**Rights declaration (bottom-loaded):** build-your-own-x declares CC0 via a paragraph at the bottom of `README.md` plus a license badge — there is no `LICENSE` file (assignment brief). Flag: this weakens machine-readability — license-scanning tools that look for `LICENSE` will miss it. If machine-readability matters, ship a real `LICENSE` file alongside the paragraph.

## Verification

```bash
python3 ~/.agents/skills/project-genome/scripts/docs/score_readme.py --archetype awesome-list README.md
```

- `--archetype awesome-list` is the §5 Phase-1 flag for archetype C (§5 line 401: "public-apis must not be penalised for 2655 lines under `--archetype awesome-list`").
- Expect: `length_400_2700` passes; `badges_0_to_7` passes (C exemplars use 0–2); `code_examples_2plus` is absent/ignored (C has 0 code blocks by design — §1.4 G9); `entry_microformat` (new check) verifies `[**Lang**: _Title_](url)`.
- Regression: a 46-line archetype-C-correct README currently scores **−4/8** under the un-scoped rubric (§1.4 line 158), penalised for `length_100_170`, `code_examples_2plus`, `visual_proof_3plus`, `badges_3_to_8`. Under `--archetype awesome-list` it must score ≥8/8.
- Structural: verify `## Index` anchors resolve to `###` category headers; verify every `###` header has ≥3 entries (enforced by `format.py`).
