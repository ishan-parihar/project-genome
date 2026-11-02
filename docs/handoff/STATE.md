# State

Current snapshot only (no history: that is the worklog). The first `## ` block is
what `genome wake` shows.

## State — 2026-11-02, after the census was corrected by running the check (`2026.10.31-40`)

- **The estate census was wrong by one repo, and the missing row is nine releases behind.**
  Tier 0.1's step 1 — `genome installs verify --against-shipped` — was never executed;
  running it now names **`agentic-harness/operant` BEHIND at `2026.10.21-2`** (sha
  `ee03491721ed`, clean tree, so it was *never upgraded*, not reverted) alongside
  `pioneer-qf`. Verbatim: `2 behind, 0 unknown, 0 corrupted`. It carries 2026-11-01
  rollback artefacts (`.genome/genome.pre-upgrade` at `-39`, `genome.pre-2-full`) showing an
  upgrade that reached `-39` and was rolled back, 5 `fleet-hold-*` WIP branches and 3 stashes.
  **And its own 2026-10-28 worklog already ruled on its copy**: *fork-without-intent — should be
  deleted in favor of the PATH install + `genome upgrade`*. So the true figure is **73/76
  vendored rows current**, not 75/76.
- **Two structural facts the census hid.** `pioneer-qf` is a **`kb` row** (an activated genome
  with no `scripts/` copy at all), a fourth kind beside vendored/skill/bin — so "the estate's
  copies" is not one population. And `holon/scripts/genome` is a **symlink** into
  `holon/holon/vendor/genome.py`, a target `installs verify` does not resolve, so holon is
  invisible to the fleet-wide check rather than measured by it. Q1's options now carry that.
- **The gate builds before it measures, and a stale `dist/` fails by name.**
  `[core] gate` starts with `uv build --wheel --sdist`; `test_package_modes.py` refuses aged
  or absent artefacts with `stale dist/: … uv build first` instead of two unexplained hashes.
  Measured both directions. **PQ-5 closed in code, PQ-4 closed as a non-issue.** E018 has its
  row in `references/lint-rules.md`, and the lint-code catalogue is current (15 E / 10 W flat,
  free **E019/E020/E021**). Full gate green: `uv build` → 39/39 → 8/8 → 5/5 → `--check` →
  `check_ps1`, exit 0.
- **Tier 1 is a missing module, not a renumbering.** `modules = ["core", "records"]`, the
  protocol says *"Status: upgrade proposal. Nothing here is implemented yet"*, and
  `grep -rl transients src/` is 0 files, so `tadopt` + the transients register must land
  before `M017`/`E019`/`E020`. Landing `E019` unaided turns 9 dated files red.
- **Both remaining rows are the operator's**: **Q1** (the vendored-copy convention, where
  operant's own record is evidence for option 3) and Tier 1's ratification of the `kb`
  protocol. No working tree has been written to: operant's crate WIP, pioneer-qf's checkout,
  and holon's symlink target are all left alone.

## State — 2026-11-02, after the stale-`dist/` trap closed in the gate (`2026.10.31-40`)

- **The gate now builds before it measures, so it cannot report the build system's state as the
  code's.** `[core] gate` starts with `uv build --wheel --sdist`, and
  `test_package_modes.py` refuses a stale `dist/` by name
  (`stale dist/: … uv build first`) instead of comparing two stale hashes. Measured
  both directions: aged artefacts → exit 1 with the refusal; fresh → 5/5. This
  closes **PQ-5 in code** and **PQ-4 as a non-issue** — with a fresh `dist/` the
  suite passes from `cwd=/` (exit 0, 5/5), so the repo-root-shadowing claim was
  never the cause. Full gate green as the new string: `uv build` → `test_genome`
  39/39 → `test_package` 8/8 → `test_package_modes` 5/5 → `build --check` →
  `check_ps1`.
- **Two facts measured here that the plan did not know.** `python3 -m uv` does not
  exist on this machine — `uv` is only `/usr/bin/uv` (`0.13.4`) — so the plan's
  fix, spelled `python3 -m uv build`, would have failed the gate at its first
  step on every run; the string is bare `uv build`. And `uv build` **does not
  clear `dist/`**: it rewrites the two names it knows and leaves a stray file
  alone (a `zz_junk.whl` survived a full build), so the guard ages the whole glob.
- **E018 shipped with no documentation row; it has one now, and the catalogue is
  current.** `references/lint-rules.md` carries the E018 row with the distinction
  a reader needs (an *undeclared* `schema_version` is deliberately not this
  error). `AGENTS.md` rule 8's catalogue was three days stale — said max E017,
  free E018/E019/E020, "14 E-codes"; re-measured against `src/` it is **15 E and
  10 W** flat, free **E019/E020/E021**, and the row now explains why the `grep`
  count of 46/21 is not the catalogue. The same three stale figures plus a
  "38/38" sat in `docs/RUNBOOK.md`; re-measured to 39/39.
- **Register corrected: `PQ-2`'s gate list named `E018` as unfired.** E018 shipped
  2026-11-01, so the frontier is `M017` plus `E019/E020/E021`, and no M-code
  exists in the source yet (measured 2026-11-02).
- **Still the largest gap, and still the operator's: 75/76 vendored copies sit at
  `2026.10.31-40`, and `pioneer-qf` and `holon` sit at `2026.10.27-13` again.**
  Both were reverted after the swaps landed, by external git operations. **Q1 in
  `docs/kb/ASKS.md` is still open** — the vendored-copy convention is Tier 0 of
  the 2026-11-01 outline, and until it is ruled, every dispatch into this fleet
  can be silently undone by a `git checkout`. Neither copy has been re-applied to:
  overwriting an owner's checkout is what the vendored-copy guard exists to prevent.

## State — 2026-11-01, after the remaining gaps were re-measured (`2026.10.31-40`)

- **The fleet is current in bytes and two copies are not, and both were reverted from
  outside the dispatch.** Measured per registered row against
  `~/.agents/skills/project-genome/scripts/genome`: **75 of 76 vendored copies hold
  `2026.10.31-40`** (sha `11bf845430e0`). `pioneer-qf/bin/genome` and
  `holon/holon/vendor/genome.py` (+ its `scripts/genome` symlink) sit at
  `2026.10.27-13` again — pioneer-qf's reflog shows `reset: moving to HEAD` at 07:06
  local after a 06:01 commit, holon's copy was rewritten at 07:40 local with no commit
  above a 22:56-UTC HEAD. `installs verify --against-shipped` names exactly those two
  BEHIND. **An upgrade undone by the next `git checkout` is not an upgrade that
  succeeded** — Q1 asks the operator which of three conventions replaces vendoring.
- **The live plan is `docs/plans/2026-11-01-remaining-implementation-gaps-outline.md`.**
  It supersedes the 2026-10-30 one (archived, tombstone left, W006 cleared). Its Tier 1
  numbering is **M017 / E019 / E020**, not the old M017/E018/E019, because this repo
  minted **E018** on 2026-11-01 for the `schema_version` gate — re-derived from the
  shipped script, live flat max E018, E019/E020 free, no M-code exists. Tier 0 is the
  convention decision (Q1); Tier 2 is the stale-`dist/` trap closed in the gate.
- **Five register/plan claims were wrong and are now re-measured:** the evals figure
  (16 evals, **86 assertions**, no fixture count — `fixtures` is a build glob); PQ-3's
  mechanism (pip builds a wheel from the sdist, so the install *does* carry
  `_genome.py` at the right sha); PQ-4/PQ-5 (one trap — a stale `dist/`, proven by an
  identical failure from `/` and from the repo root, cleared by one `uv build`); PQ-1
  (two externally-reverted copies); PQ-9 (closed in fact, all roots at `-40`).
- **The estate lints 82 KB(s), 1 error, 102 warnings, 1 with no CLI** — the error is
  pioneer-qf's `E301`, an owner-map row only that venture's owner can write. The kernel
  itself: `lint: 0 error(s), 1 warning(s)` (W010 on the append-only worklog),
  `doctor: healthy`. `test_genome` 39/39 and the gate green at `2026.10.31-40`.
- **A shipped code with no documentation row: E018 is absent from
  `references/lint-rules.md`** (14 flat E rows, none for it). Recorded in the plan's
  Tier 2 to be added with E019, so frontier and rows land in the same commit.

## State — 2026-11-01, after the fleet upgrade shipped (`2026.10.31-40`)

- **Every vendored copy in the estate holds the same release.** Measured against the
  canonical skills root, all **76 vendored repos** sit at `2026.10.31-39` (sha `f08be22396f1`
  from `-38`, re-verified after the `-39` dispatch), the kernel and the four skills roots
  are at `-39`, and the installed uv tool reports `genome 2026.10.31-39`. The three
  non-canonical roots are still symlinks into `~/.agents`, not copies.
- **One fleet run reported a lie and the harness now guards against it.** A `--apply`
  piped through `tail` printed `dispatch: 75 ok, 0 skipped, 0 failed` while **no vendored
  file had changed** (76 repos probed: every byte still `-34`, sha `a9263e5bbe53`, zero
  pre-upgrade backups). The pipe held the children open and truncated their writes; the
  post-swap disk re-read could not fire because no child had run. The same dispatch written
  to a file gave **70 upgraded, 69 ok, 1 upgraded but BROKEN**. Every fleet run now writes
  its log to a file, and `_version_of` after the swap is the only claim that counts.
- **The one BROKEN member was right, and the kernel was wrong.** `operant` carried
  `E306 PLAN_SESSION_PICKER_UPGRADE.md: no role points here` on the tombstone the archive
  workflow itself writes. `misplaced_paths()` now exempts a tombstoned root file, in the
  place that decides, so `lint` and `close` share the same set. Proven on the repo that
  caused it: `-38` lints 1 error, `-39` lints clean.
- **The hardening at `-39`:** `_child_broken()` reads the child's `post-upgrade: N error(s)`
  verdict so a broken swap is `upgraded but BROKEN` and fails the run (exit 2);
  `_release_ledger()` calls a copy whose sha256 differs from `scripts/releases.txt`
  `CORRUPTED`, and the ledger lives beside the *skill* copy because a vendored repo carries
  no `releases.txt` at all; and `E018` makes a **declared-but-behind** `schema_version` an
  error, because an unmigrated repo reads every glob with the old dialect and reports clean.
- **A second round of the same class, closed by one shape.** `-39` fixed the kernel's own
  `E005` false positive (a live test file that *documents* the tombstone rule read as one),
  but `holon`'s vendored copy of the CLI carried the same whole-body search and fired
  `E005` twice on `holon/vendor/genome.py`. `is_tombstone()` now anchors the marker to the
  head of the document — where `cmd_archive` writes it, line 3 — and all three call sites
  (E005, the duplicate-title pass, the placement exemption) share that one predicate.
- **All suites green at `2026.10.31-40`:** `test_genome` **39/39**. `layout_invariant`
  asserts a real tombstone passes and a prose mention at line 400 does not;
  `kb_registry` asserts the new `upgraded but BROKEN` exit-2 behaviour instead of the old
  exit-0 one — **the fixture had been asserting the defect.**
- **The estate is measured clean but for one owner's file.** `genome fleet lint` reads
  **82 KB(s), 1 error, 102 warnings, 1 with no CLI**. The one error is `pioneer-qf`'s
  staged, unlisted prereg (`PREREG-2026-11-01-te6-exit-placebo.md`), which needs an
  owner-map row only that venture's owner can write. The kernel, holon and operant all
  lint clean. All 76 vendored repos hold the identical release (sha `11bf845430e0`).

## State — 2026-10-31, after `genome fleet` unified the three upgrade surfaces (`2026.10.31-34`)

- **The estate is now one verb away: `genome fleet`.** It answers what is behind, takes it
  current, and prints the fix list per KB. `fleet` alone is `list` - grouped by what the
  operator does about it (sources / behind / current / no-local-CLI) - and the current run
  on this machine reads **83 registered installs, current release `2026.10.31-34`, 5
  sources, 76 behind, 1 current (the kernel), 1 with no local CLI (the meta-root).**
  `fleet upgrade [--roots --apply]` and `fleet lint [names...]` reuse the existing
  dispatch and lint printer, so there is no second registry and no second copy of any
  answer.
- **The installed package is no longer invisible or self-comparing.** `~/.local/bin/genome`
  is a uv tool whose real CLI sits at `lib/python3.13/site-packages/project_genome/_genome.py`
  (`2026.10.30-23`, seven releases behind). The bin symlink resolved to a console-script
  stub with no VERSION line, so the registry read the row as `?`; `_script_of()` now probes
  the environment beside the stub, and `installs verify --against-shipped` went from
  "81 behind, **1 unknown**" to "81 behind, **0 unknown**". `genome upgrade` from a neutral
  cwd now prints `BEHIND — this machine is at 2026.10.31-34` with the reinstall command,
  where it used to die in `find_cfg()` before checking anything, or print "up to date".
- **76 installs are behind the current release `2026.10.31-34`:** 73 at
  `2026.10.27-13` (including `pioneer-qf`, which vendors at `bin/genome`, not
  `scripts/genome`), `operant` at `2026.10.21-2`, `artificial-route` at
  `2026.10.22-17`, `saas/lifeos-bot` at `2026.10.30-29`. The kernel (`2026.10.31-34`) is
  the one current copy; `my-projects` is the one registered KB with no local CLI at all.
  The four skills roots sit at `2026.10.30-22`. These are measured against `fleet`, which
  probes both `scripts/genome` and `bin/genome` — a probe looking only in `scripts/`
  undercounts by one (pioneer-qf).
- **The registry is now complete and clean.** It previously missed the kernel itself (the
  one genomic project no manifest reader could see) and carried four ghost rows whose
  directories no longer exist (holon-personal and its nested holon, discord-cli, tg-cli).
  The kernel is registered as `vendored` with a note; the ghosts are unregistered. 83 rows
  resolve, and `installs scan` finds nothing unregistered.
- **`kb lint --all` prints every finding with its remedy, and the remedy table has one
  owner.** `kb_lint_one()` used to cap findings at three; it now returns all of them, and
  `_remedies_for()` - shared with `_post_upgrade_findings()` so the two cannot drift into
  two vocabularies - prints `remedies:` plus a `W0xx in N KB(s)` line per code. Measured on
  this machine: 77 KBs, **0 errors, 100 warnings in 9 codes** (W006 x2, W008, W009, W010 x5,
  W011 x3, W014 x6, W105, W201, W401 x2).
- **A defect in the fix was caught by its own test and is recorded in-code.** The first
  remedy table knew only the E codes, and the estate carries only W codes, so the first
  `fleet lint` printed no remedies at all - the same failure shape as the finding cap. The
  table now covers the codes the machine produces.
- **All suites green at `2026.10.31-34`:** test_genome 38/38, test_package 8/8,
  test_package_modes 5/5, check_ps1 412 lines, kernel lint clean and doctor healthy, wheel
  bytes == `scripts/genome` bytes == the ledger's `-34` checksum. `kb_registry` asserts the
  package layout, the version column and the behind group, and fails on a scratch revert
  with `version: '?'`.
- **No fleet-wide `--apply` was run.** A scoped `--roots` dry run reached 2 of 2 named
  repos on the `-34` source, and a scope matching nothing still dies (exit 2) rather than
  printing the all-clear. The full pass remains the operator's call.

## State — 2026-10-31, after the upgrade mechanism was proved by a real scoped `--apply` (`2026.10.30-29`)

- **The fleet is 77 vendored CLI files across 77 repos, and 76 of them sit at
  `2026.10.27-13`** — twelve releases behind the tip; `saas/lifeos-bot` is the one that
  moved. The four skills roots sit at `2026.10.30-22`, one release behind the kernel
  (`2026.10.30-29`). A `-13 → -29` swap is **820 lines added, 6 removed** per copy. The
  registry knows every vendored repo: 79 of its 81 vendored/kb rows resolve to a real
  directory and 77 hold `scripts/genome`, exactly the on-disk set. Two rows point at
  nothing (`holon-personal` and its nested twin).
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
- **The same stale-floor defect was in a sibling command, and is fixed there too.**
  `genome installs verify --against-shipped` printed `shipped is 2026.10.30-22` while the
  running CLI was `-26` — the check an operator reads before a rollout named a version
  nothing held. It now takes `max(running CLI, registered floor)`, and `installs_registry`
  asserts it by making a skills root lag: the reference must not follow a root down.
- **The registry can now forget.** `genome installs unregister <path>` is new: exact path
  first, then an unambiguous name match. `project-genome` is refused (it matches 4 rows)
  rather than dropping rows the operator never named.
- **All suites green at `2026.10.30-29`:** `test_genome` 38/38 (one new assertion
  in `kb_registry`), `test_package` 8/8, `test_package_modes` 5/5, `check_ps1` parity ok
  at 412 lines, `genome close` green, and the wheel bytes equal `scripts/genome` bytes
  equal the ledger's `-29` checksum.
- **Three packaging failures were a stale `dist/`, not a code defect.** Both artefacts
  still carried `-23` mid-session and the byte-parity cases failed until `uv build` was
  re-run. A `build.py` guard also refused to rewrite a released checksum, which forced
  the VERSION bump that uncovered the stale-artefact path — two independent guards
  working. The unshipped `-24` ledger line was removed: no file on disk ever held those
  bytes.
- **One scoped `--apply` WAS run, on `saas/lifeos-bot`, twice, each after its dry
  run.** `2026.10.27-13` → `-28` → `-29`; its post-upgrade line reads `lint: clean
  [agents, core, records] — nothing to fix after the upgrade` and `genome doctor` there
  is healthy. Its 292-line local patch was the `outline` module, which `-22` had already
  shipped upstream, so the swap subsumed it and lost nothing. Its `scripts/genome`
  working-tree change is left uncommitted for the repo owner.
- **The live run found three defects in the fix, all fixed at `-29`.** The dispatch's own
  line filter dropped the `post-upgrade:` header and the `remedies:` line — a fleet run
  would have shown NO fix list; the numbered findings were matched by a heuristic
  `1. E017 …` cannot satisfy; and the child's first line printed twice. All three are
  asserted in `kb_registry`, and the assertion was proved to catch the defect by
  reverting the passthrough in a scratch copy and watching it fail.
- **Nothing else was applied.** No publish, no fleet-wide run: the remaining 74 vendored
  copies still sit at `2026.10.27-13`, and the procedure that would take them is in
  `docs/audit/2026-10-30-UPGRADE-MECHANISM-AUDIT.md` §6.

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
