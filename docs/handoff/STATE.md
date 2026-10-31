# State

Current snapshot only (no history: that is the worklog). The first `## ` block is
what `genome wake` shows.

## State — 2026-10-31, after the upgrade mechanism was made honest and the scoped test became possible

- **The fleet is 77 vendored CLI files across 77 repos, and 75 of them sit at
  `2026.10.27-13`** — ten releases behind the tip. The four skills roots sit at
  `2026.10.30-22`, one release behind the kernel (`2026.10.30-25`). A `-13 → -25` swap
  is **807 lines added, 6 removed** per copy. The registry knows every vendored repo:
  79 of its 81 vendored/kb rows resolve to a real directory and 77 hold `scripts/genome`,
  exactly the on-disk set. Two rows point at nothing (`holon-personal` and its nested twin).
- **The upgrade mechanism had ten gaps, and the operator's sanctioned scoped test was
  impossible to perform.** `--roots` was parsed and then ignored (the dispatch body had
  zero references to it), so every "scoped" run was a fleet run by another name. Verified
  against `HEAD` by extraction and grep, not by recollection.
- **The bootstrap failure was mathematical, not cosmetic, and is now closed.** A dispatch
  from `-23` delegated to each repo's own old CLI, whose `skill_copy()` hardcoded one of
  four skills roots at `-22` — so the fleet could only ever converge on the last thing
  install.sh published, never on the tip. Reproduced in a sandbox both ways (`-13 → -22`
  unset, `-13 → -23` with `GENOME_SKILL` at the release). Fixed by three changes that only
  work together: the reference is `max(running CLI, registered floor)`, the dispatch hands
  each child `GENOME_SKILL` (an env var every shipped version already honours), and
  `skill_copy()` probes all four roots plus the kernel working tree and takes the newest.
- **An upgrade now ends with a numbered fix list, not with "upgraded X".**
  `_post_upgrade_findings()` runs this CLI's own lint after the swap and prints each
  finding with the command that clears it. It never fails the upgrade: exiting non-zero
  afterwards would tell the dispatcher the swap failed when it did not.
- **A scope that matches nothing now dies (exit 2) instead of printing the all-clear.**
  `--roots no-such-repo` used to print `dispatch: nothing to upgrade (every registered
  copy is at …)` — the single most dangerous line the mechanism can produce, because the
  operator reading it concludes the fleet is current.
- **The registry can now forget.** `genome installs unregister <path>` is new: exact path
  first, then an unambiguous name match. `project-genome` is refused (it matches 4 rows)
  rather than dropping rows the operator never named.
- **All suites green at `2026.10.30-25`:** `test_genome` 38/38, `test_package` 8/8,
  `test_package_modes` 5/5, `check_ps1` parity ok at 412 lines, `genome close` green,
  and the wheel bytes equal `scripts/genome` bytes equal the ledger's `-25` checksum.
- **Three packaging failures were a stale `dist/`, not a code defect.** Both artefacts
  still carried `-23` mid-session and the byte-parity cases failed until `uv build` was
  re-run. A `build.py` guard also refused to rewrite a released checksum, which forced
  the VERSION bump that uncovered the stale-artefact path — two independent guards
  working. The unshipped `-24` ledger line was removed: no file on disk ever held those
  bytes.
- **Nothing was applied to the fleet.** No `--apply` on any repo, no publish, no
  fleet-wide run. The procedure is written down in
  `docs/audit/2026-10-30-UPGRADE-MECHANISM-AUDIT.md`; its steps 1 and 4 are the
  operator's call. That audit also records a corrected figure: the release gap is **10**
  releases, not the eleven the previous session summary carried.

## State — 2026-10-30, after the installer rework made one command deliver both

- **The cold-start install now delivers the CLI *and* the skill from one line.**
  Measured before: `install.sh` installed the CLI and skipped the skill by default;
  `npx skills add` installed the skill and skipped the CLI. Neither default was the
  product. `curl -fsSL .../install.sh | bash -s -- --skill` is now both, and its
  skill step writes the same shape `npx skills add -g` writes — verified in a
  sandbox on 2026-10-30: **one real copy** at `~/.agents/skills/project-genome`, **five
  relative links** (`.claude`, `.zcode`, `.codex`, `.codegpt`, opencode), **one
  `.skill-lock.json` entry**, and the second run a no-op on all three.
- **The four-clone defect is gone.** Measured on this machine 2026-10-30:
  `project-genome` was **four byte-identical 4.8 MB clones at four distinct inodes**,
  because the installer ran a separate `git clone` per harness root. Only
  `~/.agents/skills/project-genome` was the copy the skills backup covers; the other
  three had no second copy anywhere. The probe also missed two roots that exist
  (`.codegpt`, `~/.config/opencode/skills`). Both are fixed, and the old behaviour is
  still reachable with `--copy-skill`.
- **Two installer defects were caught by running it, not by reading it.** The link
  target was first written as a fixed `../.agents/skills/..`, which resolves to
  `~/.claude/.agents/skills/..` — a second broken link. It is now computed per root
  depth (`.claude` needs `../../`, opencode needs `../../../`), verified against
  `os.path.relpath` on all six roots. And the lock file was first written inside
  `skills/`; measured, the real one is `~/.agents/.skill-lock.json`, **one level
  above** the root, which is where the npx CLI and the skills-backup service look.
- **An honest limit is recorded in-code rather than papered over.** Our
  `skillFolderHash` is not the npx algorithm (a real entry's hash re-derived against
  ours: `86b6f36...` vs `c3c8fba...`), so `npx skills update` re-fetches rather than
  skips. That is the safe direction, and the entry still tells the CLI this copy's
  source — which is the part it could not otherwise learn.
- **The lock file named 23 of 153 skills; ours was one of the 130 invisible.** The
  installer now writes its entry, so `npx skills update` can refresh ours. The other
  129 need the same one-line fix and are not this repo's to make.
- **The skills-root audit is committed** (`docs/audit/2026-10-30-SKILLS-ROOT-AUDIT.md`):
  six roots measured, the four-clone and lock-file gaps in prose, and the cleanup
  ordered by what it unblocks. `~/.agents` is the canonical root because it is the
  only gitsync-backed one; the others' 125/284 symlink chains already prove the
  harnesses follow links, so the direction of travel is already right.
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
  `test_package_modes` 5/5, `check_ps1` parity ok at 412 lines, `probe-outline-languages`
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
