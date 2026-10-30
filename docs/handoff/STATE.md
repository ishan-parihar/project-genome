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
- **The lint code catalogue, re-derived from the shipped script** (2026-10-30): the source
  literally names **14 E-codes and 10 W-codes** — E001-E006, E008-E010, E013-E017 and
  W000, W006-W014 — measured as non-comment `[EW]0\d\d` tokens in `src/`. The live flat
  maximum is **E017**, so **E018/E019/E020** are free and **E007/E011/E012** plus
  **W001-W005** are gaps deliberately not reused (older fleet copies may carry them with
  meanings a new code cannot derive). The 2026-10-28 audit's "44 E-codes and 21 W-codes"
  counts every code the module *can* emit, runtime-assembled ones included; this is the
  number a session choosing the next code should use.
- **The fleet this kernel governs, measured 2026-10-30:** **77 vendored CLI files across
  77 repos** (holon carries two — `scripts/genome` and `holon/holon/vendor/genome.py`;
  pioneer-qf vendors at `bin/genome`, not `scripts/genome`; and `knowledge-bases/*`'s
  `genome/` are directories, not the CLI). Versions: **75 at `2026.10.27-13`, 1 at
  `2026.10.22-17`, 1 at `2026.10.21-2`**. The current build is `2026.10.30-23` (it moved
  from `-22` today, when the fence fix below forced a version bump), so the fleet is three
  versions behind and that drift is the next real work item.
- **The installed skill and this repo were the same source, and now differ by one commit.**
  `diff -rq ~/.agents/skills/project-genome/src src/` returned nothing but `__pycache__` on
  2026-10-30 at VERSION `2026.10.30-22`. The fence fix bumped this repo to `2026.10.30-23`
  and `genome doctor` now reports "newer than the installed skill copy (2026.10.30-22)",
  which is PQ-9. So locus 2 was a deploy target, not a second source — and the
  meta-root's surface-area audit said as much, now re-measured rather than assumed.
- **All suites green, measured 2026-10-30:** `test_genome` 38/38, `test_package` 8/8,
  `test_package_modes` 5/5, `check_ps1` parity ok at 258 lines, `probe-outline-languages`
  9/9. Two measurement failures were diagnosed on the way and both were environment, not
  defect: a stale `dist/` (built 05:34 against a `scripts/genome` rebuilt at 08:48) failed
  the sdist byte-parity case until `uv build` was re-run; and
  `test_package_modes.py` read from the repo root resolves the local `project_genome/`
  ahead of site-packages, so the honest run is from a neutral cwd. Both are now PQ-5 and
  PQ-4 with the rule written down, and the final run of every suite was from `cwd=/`
  after a rebuild.
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
