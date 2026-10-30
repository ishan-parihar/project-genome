# State

Current snapshot only (no history: that is the worklog). The first `## ` block is
what `genome wake` shows.

## State — 2026-10-30, after the kernel repo was initialized as a genome project

- **This repo is now a genome-managed project.** Until today it was the one repo in the
  portfolio with **no `genome.toml` and no `AGENTS.md`** — a kernel that enforced
  `genome init` on every adopter without having run it on itself. Measured before the
  change: no `genome.toml`, no `AGENTS.md`, no `docs/handoff/`, no `docs/kb/`, no
  `docs/RECORDS.md`, no `docs/RUNBOOK.md`, no `PAGE-INDEX`. It did carry
  `docs/plans/` (3 files), `docs/audit/` (1) and `docs/PUBLISHING.md`. Now scaffolded
  with `genome init --profile software` (12 created, 0 kept — nothing was clobbered) and
  filled in with this repo's measured facts.
- **A parallel session was working here live, and its work was left untouched.** Measured:
  `install.ps1` was modified 1 minute before I checked. It committed twice while this
  work ran (`b48c464` the modes suite and ps1 parity, `4733cfd` the installed-copy
  "up to date" line). Every one of its files is committed as its own work; none of it is
  in this repo's genome commits.
- **The figure that matters, re-derived from the shipped script** (2026-10-30): **44
  E-codes and 21 W-codes in live use** (E-codes on non-comment lines, matching the
  2026-10-28 audit's "44 in live use" exactly). The live flat maximum is **E017**;
  **E018/E019/E020 are free**; **E007/E011/E012 and W001-W005 are gaps that are
  deliberately not reused** because older fleet copies may carry them with meanings a new
  code cannot derive.
- **The fleet this kernel governs, measured 2026-10-30:** **77 vendored CLI files across
  77 repos** (holon carries two — `scripts/genome` and `holon/holon/vendor/genome.py`;
  pioneer-qf vendors at `bin/genome`, not `scripts/genome`; and `knowledge-bases/*`'s
  `genome/` are directories, not the CLI). Versions: **75 at `2026.10.27-13`, 1 at
  `2026.10.22-17`, 1 at `2026.10.21-2`**. The current build is `2026.10.30-22`, so the
  fleet is three versions behind and that drift is the next real work item.
- **The installed skill and this repo are the same source.** `diff -rq
  ~/.agents/skills/project-genome/src src/` returns nothing but `__pycache__` on
  2026-10-30, at identical VERSION `2026.10.30-22`. That makes locus 2 a deploy target,
  not a second source of truth — the meta-root's surface-area audit said as much and it is
  now re-measured rather than assumed.
- **All suites green, measured 2026-10-30:** `test_genome` 38/38, `test_package` 8/8,
  `test_package_modes` 5/5, `check_ps1` parity ok at 258 lines, `probe-outline-languages`
  9/9. One measurement failure was diagnosed along the way and turned out to be a
  **stale `dist/`**, not a defect: the sdist byte-parity case failed against a
  `dist/` built at 05:34 while `scripts/genome` had been rebuilt at 08:48; after the
  parallel session rebuilt at 08:55 the same case passed 5/5.
- **The shape of this repo's knowledge:** it is a **software** project, so it runs
  `core` + `records` (2 of 6 modules). `research`/`ops`/`agents`/`outline` are modules
  this kernel *ships* to other repos, not modules this repo adopts — a distinction the
  architecture section makes explicit so a future session does not turn them on here to
  look consistent.

## What is deliberately NOT done here

- **The 75 fleet-wide CLI upgrades are not run.** That is a fleet-wide dispatch with its
  own blast radius and its own guard (the vendored-copy reset guard), and it belongs to an
  operator-approved pass, not to a documentation change.
- **The KB-management protocol is not implemented.** It is still a proposal
  (`docs/plans/2026-10-28-KB-MANAGEMENT-PROTOCOL.md` + its numbering addendum), its
  three gates still unfired: M017, E018, E019. The addendum's numbering was re-derived
  from this repo's own script today and still holds.
- **Nothing was published.** `docs/PUBLISHING.md` is the release path and it needs a
  credential this seat cannot mint.
- **`README.md` was not rewritten.** It is the PyPI-facing front page; it was read, not
  touched. `SKILL.md` likewise.
