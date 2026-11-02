# Mechanisms — the 16 techniques that actually work

> Transferable patterns extracted from 11 high-profile repos, each attributed to
> where it was observed. Use as a palette while polishing; the archetype files
> say *which* sections, this says *how* to render them.

Evidence rule: every entry names the repo and the line- or count-level evidence
it was read from. Nothing here is invented. Repos not named were not measured.

## 1. `## Documentation` as a TOC-to-site table

A GFM table mapping each doc topic to its URL with one line of description.
The README stays thin *and* the reader jumps straight to the page they need.

Observed in: hermes-agent (16-row table, README lines 165–185), opencode, n8n,
openclaw (a goal-directed table, not a repo TOC), deepseek-harness.

This is the single highest-leverage doorway mechanism — it is what lets a
243-line README serve a 455-page docs site.

## 2. Parallel-platform install in one fenced block

All install paths in one fenced block with an inline `#` comment per line.
Kills the tabbed-installer UI and the per-platform page split.

Observed in: opencode (curl / npm / brew tap + pacman / paru / mise / nix in one
block, README lines 48–62), hermes-agent (`### Linux, macOS, WSL2` and
`### Windows (native, PowerShell)` as adjacent one-liners), openclaw (`curl … |
bash` and `iwr … | iex` with inline `# platform` comments).

Use for 2–3 platforms. For 5+ use mechanism #3.

## 3. Collapsible `<details>` install matrix

One `<details>`/`<summary>` per reader tool; zero static height until the reader
picks theirs. Self-selecting.

Observed in: mattpocock/skills (5 blocks — Claude Code, Codex, GitHub Copilot,
Gemini CLI, generic npx — the whole 5-agent matrix collapses to nothing).

## 4. A canonical install-block source file

One file holding the install wording plus a route/update matrix; README,
changesets, and docs pages all pull it verbatim via placeholder tags. Eliminates
install drift across surfaces.

Observed in: mattpocock/skills — `.agents/install-block.md` with
`<canonical-block>` tags.

Worth it the moment install instructions exist in more than one surface.

## 5. Per-package README contract enforced by a script

A declared contract (purpose, configuration, extension points, limitations,
Model Experience) plus scripts that verify it, so package READMEs cannot rot
independently.

Observed in: deepseek-harness — `packages/README.md` declares the contract;
`scripts/verify-package-readme-model-experience.ts` and
`verify-package-readme-limitations.ts` enforce it.

Executable locally via `verify_per_package_readme.py`.

## 6. CI-enforced documentation validation

Validate the doc as data, on every push and PR — not by human review.

Observed in: public-apis — `scripts/validate/format.py` (alphabetical order,
min 3 entries per category, ≥5 columns per row, description ≤100 chars, closed
Auth/HTTPS/CORS vocabularies, every cell padded exactly one space) +
`scripts/validate/links.py` (URL + duplicate-link) on push/PR, plus a full link
sweep on a daily cron.

Decision rule: a curated table is worth a validator when it has >100 rows, >1
contributor, or a closed vocabulary. See `ci-validation.md`.

## 7. Locale sync keyed off English source paths

A workflow that treats translations as mechanically derived from the English
source path, so locales track changes instead of drifting.

Observed in: opencode — `.github/workflows/docs-locale-sync.yml`, 20 translated
root READMEs + 17 docs locales (~560 pages) keyed off
`packages/web/src/content/docs/*.mdx`.

## 8. One manifest projecting one source to many locales

A single `docsPages`/`pairedPages`/`localeCollections` manifest so en+zh never
drift by copy-paste.

Observed in: deepseek-harness — `website/docs.ts` (~96 canonical pages, ~190
routes incl. Chinese mirrors).

## 9. API reference footnoted to the source line

Each generated/translated reference member ends with a link to the exact
implementation line, making it traceable rather than a floating description.

Observed in: deepseek-harness — `docs/cordis-api/registry.md` ends each `###`
member with `[Source](../../vendor/cordis/src/registry.ts#L176)`.

## 10. Feature→mechanism map table

When the architecture claim is "everything is a plugin", document it as a table
mapping each product feature to the concrete extension point that implements it.
The claim becomes checkable instead of asserted.

Observed in: deepseek-harness — `docs/cookbook/extension-cookbook.md` (hook
system, /goal, /loop, MCP, skills, plan mode, sub-agent delegation → plugin
extension points, with source links).

## 11. Auto-generated contributor grid via markers

Bot-managed markers let a contributor wall refresh without anyone editing the
README by hand.

Observed in: openclaw — `<!-- clawtributors:start -->` …
`<!-- clawtributors:hidden:end -->`, 60+ avatars.

## 12. HTML `<table>` for short-label / long-description grids

GFM pipe tables stretch every column to the longest cell. For a grid of bold
one-word labels against multi-sentence answers, raw HTML renders correctly where
GFM does not.

Observed in: hermes-agent — 7-row feature comparison, README lines 23–31.

Keep it the exception. GFM is diffable and lintable; HTML is not.

## 13. Language-selector badges → translated READMEs

shields.io `style=for-the-badge` badges with native language names, each linking
a translated root README. Discoverable in GitHub's rendered view, and an open
invitation to translate.

Observed in: hermes-agent (中文 / اردو / Español → `README.zh-CN.md`,
`README.ur-pk.md`, `README.es.md`, plus translated CONTRIBUTING/SECURITY).

## 14. `.gitattributes` telling Linguist markdown is the code

For a pure-markdown repo, `*.md linguist-documentation=false` stops the language
graph collapsing to "100% Markdown".

Observed in: build-your-own-x — first two lines of `.gitattributes`.

## 15. RELEASE-NOTES.md as architectural memory

A large per-release changelog that doubles as project history: feature
breakdowns with issue numbers and contributor attribution.

Observed in: obra/superpowers — 109 KB, per-release notes referencing issues
(#2463, #2479, #2393) with named contributors.

## 16. Declarative success criteria

Tell the reader how to know it worked — a behavioural checklist, not a claim.

Observed in: andrej-karpathy-skills — `## How to Know It's Working`
(README lines 140–148), plus a `1. [Step] → verify: [check]` plan block.

## Anti-patterns observed in the same 11 repos

These are not hypothetical. Each was found in a repo this palette was read from.

| Anti-pattern | Where | Why it matters |
|---|---|---|
| LICENSE asserted in prose + manifest, no LICENSE file | andrej-karpathy-skills (220k stars) | real compliance exposure; also a `verify`-able gap |
| Install commands hardcoding a previous owner after a repo move | andrej-karpathy-skills (`forrestchang/…` in 3 places, now `multica-ai`) | breaks copy-paste for every new reader; hides in translation/localisation edits |
| Badges beyond the useful ceiling | not an exemplar failure, but the rubric's ceiling is 7 and no audited repo exceeds it | past ~7 they are noise, and our own repos run 8–14 |
| Topic roots treated as deletable messages | not a doc pattern, but the same class of error: mechanical bulk edits to forum-topic service messages destroyed fresh-message topic binding | bulk-mechanical edits to a system whose invariants you have not read will destroy state silently |
