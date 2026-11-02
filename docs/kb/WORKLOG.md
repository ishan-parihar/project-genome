# Worklog

Append-only: `python3 scripts/genome log "<entry>"`, one per unit of work.

## 2026-10-31 — one verb instead of three commands joined by path (`5b9f0f9`, VERSION `2026.10.31-34`)

The ask, verbatim: *a unified surface area from where we can link all our kbs and upgrade
it effectively, rather than manual search and upgrade of each kb.* Measured first (nothing
was taken from the register): the `genome` on PATH was `~/.local/bin/genome`, a uv-tool
package whose real CLI sits inside the environment at
`lib/python3.13/site-packages/project_genome/_genome.py`; four skills roots at
`2026.10.30-22`; the kernel at `2026.10.30-29`; 77 vendored copies of which 74 were at
`2026.10.27-13`. **Five gaps, each an existing correct mechanism stopping at a boundary:**

1. The installed package **compared itself and printed "up to date"**, and `installs
   verify` read its bin row as `?`, because resolving the symlink lands on a
   console-script stub with no VERSION line.
2. An installed package's staleness had **no reference from outside itself** to compare
   against, and from a neutral cwd the command died in `find_cfg()` before checking
   anything.
3. `kb list` had **no version column**, so it could not answer "which are behind".
4. `kb lint --all` capped findings at three and **printed no remedy**, so 100 fleet
   warnings appeared as bare counts.
5. Three parts of one job lived in **three commands with three geometries**.

Fixes: `_script_of()` probes the package environment; `_package_reference()` +
`_package_upgrade()` measure an install against the skills roots and the kernel checkout;
`kb list` gains versions and `behind <ref>`; `kb_lint_one()` returns every finding and
`_remedies_for()` — now the single owner of the code→command table, shared with
`_post_upgrade_findings()` — prints the remedies and the KBs carrying each code; and
`genome fleet {list,upgrade,lint}` joins the three parts with no new machinery.

**Two defects in my own work, caught by measurement and by its tests:**

- The first remedy table knew only the **E** codes, and the estate carries 100 warnings in
  nine **W** codes, so the first `fleet lint` printed no remedies at all. Same failure
  shape as the cap: the answer withheld by the caller.
- A registry-row probe that asked for "AGENTS.md" matched `saas/lifeos-bot` (AGENTS.md, no
  `src/`), so the package was measured against a `-29` peer instead of the release it would
  converge on. **The kernel was not registered at all**, so no manifest reader could see
  the newest copy on the machine — the real root cause, fixed by registering it and by
  probing the kernel from the running file's own tree.

**Four ghost rows** (holon-personal and its nested holon, discord-cli, tg-cli — directories
that no longer exist) were inflating every count and appearing as "no local CLI"; the new
fleet surface made them visible and `installs unregister` removed them.

Suites at `-34`: test_genome 38/38 (kb_registry asserts the package layout, the version
column and the behind group, and fails on a scratch revert with `version: '?'`),
test_package 8/8, test_package_modes 5/5, check_ps1 412 lines; wheel bytes ==
`scripts/genome`; kernel lint clean, doctor healthy. A scoped `--roots` dry run reached
2 of 2 named repos on the `-34` source, and a scope matching nothing still dies rather
than print the all-clear. No fleet-wide `--apply`: that pass is the operator's call.

## 2026-10-30 — the kernel repo stops being the one repo without a genome (this)

The gap this closes: **the skill that enforces `genome init` on every adopting project had
never run `genome init` on itself.** Measured before the change, from the repo root: no
`genome.toml`, no `AGENTS.md`, no `README` records of its own handoff, no
`docs/handoff/`, no `docs/kb/`, no `docs/RECORDS.md`, no `docs/RUNBOOK.md`, no
`PAGE-INDEX`; `docs/plans/` (3 files), `docs/audit/` (1), `docs/PUBLISHING.md` present.
`genome init --profile software` created 12 files, kept 0 of them (nothing clobbered);
README.md, SKILL.md and references/ were not touched by the tool.

A parallel session was committing here live. Measured at 04:43: `install.ps1` modified at
08:03 the previous day; while this work ran it committed `b48c464` (modes suite, ps1 parity)
and `4733cfd` (the installed copy's "up to date" line). Every file of its work is its own
commit; this session touched only the paths its own writes created, and the scaffold's
write() semantics (creates missing, keeps existing) mean a shared file could not be
overwritten here.

Then the templates were filled from measurement rather than the register:
**AGENTS.md** carries the real architecture (one file built from 27 parts, six modules on
by configuration, the four-loci fix path), the real routing table, the real gate with the
`pytest`-collects-nothing trap, and ten rules including the two the fleet needs — a new
lint code takes the next free flat number (**E018**, not a gap), and never hand-edit the
built artifact. **STATE.md** is the 2026-10-30 snapshot. **TODO.md** is the register,
eight open rows, each with the measurement behind it. **docs/handoff/README.md** gets the
real commands and the real stop conditions. **docs/RUNBOOK.md** gets the build chain, the
three suites with their measured counts, and the traps — the two vendored copies in holon,
`pioneer-qf`'s `bin/genome`, the KB `genome/` directories, the stale-`dist/` trap, the
repo-root shadowing trap.

Two figures were derived from the shipped script rather than carried from the register,
and one was corrected in the process: the **live catalogue is 14 E-codes and 10 W-codes**
(`grep -rhoE` over `src/`, non-comment lines), not the audit's "44 and 21" — that audit
counts every code the module *can* emit, including runtime-assembled ones. The live max is
**E017** and **E018/E019/E020** are free, so the KB protocol's proposed gates still fit.
The fleet measurement was also re-derived: **77 vendored CLI files across 77 repos** — holon
carries two, `pioneer-qf` vendors at `bin/genome`, and `knowledge-bases/*/genome/` are
directories, all three measured rather than assumed.

Verified before claiming any of it: `python3 scripts/build.py --check` exits 0 (the artifact
is current with `src/`); the wheel's `project_genome/_genome.py` is byte-identical to
`scripts/genome` (393,117 bytes both); the sdist, measured (59 files), does **not** carry
`_genome.py`, which is why the packaged install runs through the `__init__.py` source-tree
fallback — recorded as PQ-3, not silently accepted.

## 2026-10-30 — E006 was fence-blind, and the manual that documents the marker failed the lint it describes

Running `python3 scripts/genome lint --all` over this repo's own new genome files produced exactly two errors, and
both were this repo's fault, not the tool's stdout:

**E006 `references/core.md`: zone `NAME` start marker without its end.** That marker sits inside a fenced code block —
the "Generated zones" section shows the marker format as an example. `ZONE_RE` requires `sha=` followed by lowercase
hex, so it never matched the `sha=XXXXXXXXXXXX` example, and `broken_zones()` used its own looser regex over the whole
file with no fence awareness. So the manual documenting the zone contract failed the check that enforces it. Fixed in
`src/04_zones.py`: `broken_zones()` now walks the file line by line and skips code fences, the same convention
`headings()` already uses two functions below it. `write_zone()` inherits the fix because it calls the same function.

**E001 `AGENTS.md:104 points at missing docs/audit/2026-10-22-SURFACE-AREA-AUTOPSY.md`.** The four-loci citation pointed
at a path that exists only in the *meta-root's* `docs/audit/`, not this repo's. Rewritten to name the audit and say
where it lives, rather than to carry a pointer that resolves nowhere.

The behaviour change bumped `VERSION` to **2026.10.30-23** and rebuilt: this is the `build.py` guard doing its job — a
released checksum must not change, so the bytes differ by a version, not by a silent rewrite.

**Verified, each suite re-run from a neutral cwd (`cwd=/`) after `uv build`:** `test_genome` 38/38,
`test_package` 8/8, `test_package_modes` 5/5, `check_ps1` parity ok at 258 lines, `build.py --check` exit 0,
`lint: clean [core, records]`, `doctor: healthy`. The wheel's `project_genome/_genome.py` is byte-identical to
`scripts/genome` after the rebuild (measured, not assumed). `genome wake` picks up all eight register rows and the
worklog tail. Two prep items recorded: PQ-4 and PQ-5 in `TODO.md` are the traps this run actually hit — the
`test_package_modes` cwd shadowing and the stale-`dist/` byte-parity failure that appeared between the 05:34 and
08:55 builds.

Also closed by this same pass: **README.md gained one line routing a contributor to `AGENTS.md` and
`docs/RUNBOOK.md`** (PQ-7), which is the whole of the README change — the PyPI front page keeps its content.
- **2026-10-30T17:09** — the execution outline, and the four measurements that re-ordered it
- **2026-10-31T02:19** — the installer rework: one command delivers the CLI and the skill, as one canonical copy with links

## 2026-10-31 — the install became one command that gives both halves

The cold-start product was neither default. `install.sh` gave you the CLI and skipped the skill;
`npx skills add` gave you the skill and skipped the CLI. On this machine that showed up as
**four byte-identical 4.8 MB clones of one skill at four distinct inodes**, because the installer
ran a separate `git clone` per harness root, and only the `~/.agents` one had a backup behind it.

**What shipped** (`0d34558`): `install.sh` and `install.ps1` both install the skill the way
`npx skills add -g` writes it, and one line (`.../install.sh | bash -s -- --skill`) delivers both.
One real copy at `~/.agents/skills/project-genome`, a relative symlink in every other harness root
that exists, and one entry in `~/.agents/.skill-lock.json` so `npx skills update` knows the copy's
source. `--copy-skill` keeps the old real-copy-per-root behaviour for a harness that does not
follow links.

**Three things the sandbox caught that reading the code did not:**
1. A fixed `../.agents/skills/..` link target resolves into `~/.claude/.agents/..` — a second broken
   link. Computed per root depth now, and verified against `os.path.relpath` on all six roots.
2. The lock file was first written *inside* `skills/`. Measured, the real one is
   `~/.agents/.skill-lock.json`, one level **above** the root — where the npx CLI and the
   skills-backup service both look.
3. An empty `EXTRA_DIRS` still yields one empty word through the `${VAR+...}` guard, so `--dir ""`
   pushed `""` into the roots list and `mkdir -p ""` failed on every run.

**The honest limit, in-code not in a footnote:** our `skillFolderHash` is not the npx algorithm
(a real entry re-derived: `86b6f36...`, ours `c3c8fba...`), so `npx skills update` re-fetches
instead of skipping — the safe direction, and the entry still teaches the CLI where our copy
lives, which it could not otherwise know.

**Verified:** the real skill section run twice in a sandbox (one copy, five links, one lock entry;
second run a no-op on all three, foreign lock entries preserved), the ps1 link algorithm against
ground truth, `bash -n`, `check_ps1` green at 412 lines with four new parity guards, and
`test_genome` 38/38, `test_package` 8/8, `test_package_modes` 5/5, `lint` clean.

**Stale references corrected from measurement:** `docs/PUBLISHING.md`'s path table (its
"CLI: yes (inside the skill)" claim was literally true and practically false — the skill ships a
runnable `scripts/genome`, but nothing put a `genome` on PATH), the README install section, the
RUNBOOK parity note, and the AGENTS loci table. The skills-root audit that ordered all of it is
`docs/audit/2026-10-30-SKILLS-ROOT-AUDIT.md`.
- **2026-10-31T02:53** — the skills-root audit re-measured: the zcode chain is 207 links, not 43 — the published count was broken
- **2026-10-31T03:50** — the skills-root audit re-measured a second time: three of its own figures corrected, one claim retracted outright

## 2026-10-31 — the upgrade mechanism had ten gaps, and the scoped test was impossible

The operator asked to bring every genome-managed KB under `~/Documents/github/my-projects` to the
latest kernel, under a standing ruling: **scoped runs only, `--apply` always after a dry run, never a
full fleet bootstrap on this machine.** The first question is whether that is one command. At
`ffc95f1` it was not.

**The fleet, measured:** **77 vendored CLI files across 77 repos** (the kernel's own
`scripts/genome` is the 78th on disk and one more sits inside `.genome-backups`; both excluded), of which
**75 sit at `2026.10.27-13`**, `operant` at `2026.10.21-2`, `artificial-route` at `2026.10.22-17`.
The four skills roots all sit at `2026.10.30-22`, **one release behind the kernel**. Ten releases
separate `-13` from `-23` (corrected from the eleven this session's summary carried — derived from
`releases.txt`, not remembered), and a `-13 → -25` swap is **807 lines added, 6 removed** per copy.

**Ten gaps, each verified against `HEAD:scripts/genome` by extraction and grep, not by recollection.**
The one that mattered most is not a reporting gap but a **mathematical one**: `--roots` was parsed
and then ignored (the dispatch body had zero references to it), so every "scoped" run was a fleet run
by another name — the operator's sanctioned test could not be performed at all. And even with scope
fixed, a dispatch from `-23` delegated to each repo's own old CLI, whose `skill_copy()` hardcoded one
of four skills roots at `-22`, so the fleet could only ever converge on **the last thing install.sh
published**, never on the tip. Reproduced in a sandbox both ways: `-13 → -22` with the environment
unset, `-13 → -23` with `GENOME_SKILL` pointed at the release. That is a bootstrap problem, and no
amount of per-repo fixing would have closed it, because the reference and the source were both wrong.

**Five fixes** (`src/16b_installs.py`, `src/18c_federation.py`, `src/19_main.py`, VERSION `-23 → -25`):
the dispatch takes `roots` and **dies rather than print an all-clear** when the scope matches nothing;
the reference becomes `max(running CLI, registered floor)`; the dispatch hands each child `GENOME_SKILL`,
an env var every shipped version already honours, so no repo needs the new code to receive the right
source; `skill_copy()` probes all four roots **plus the kernel working tree** and takes the newest; and
a new `installs unregister` verb lets the registry forget (2 ghost rows had been inflating every
target count). The operator's second ask — name what to fix inside each KB — is
`_post_upgrade_findings()`: after the swap, this CLI's own lint runs and prints a numbered list with the
command that clears each item, and it never fails the upgrade, because exiting non-zero afterwards
would tell the dispatcher the swap failed when it did not.

**One test assertion was wrong and was narrowed, not relaxed.** The `kb_registry` case forbade the
skill root appearing anywhere in the dispatch output — which the new honest swap-source line
legitimately does. It now checks the *target lines*, and asserts the swap-source line is present.

**Verified:** `test_genome` 38/38, `test_package` 8/8, `test_package_modes` 5/5, `check_ps1` parity ok
at 412 lines, `genome close` green, wheel bytes == `scripts/genome` bytes == the ledger's `2026.10.30-25`
checksum. Three packaging failures along the way were a **stale `dist/`** (both artefacts still carried
`-23`), not a code defect — recorded in the audit so the next run does not re-diagnose it.

**Deliberately NOT done:** no `--apply` on any repo, no publish, no fleet-wide run. The procedure is
written down in the audit; steps 1 and 4 are the operator's call. The audit is
`docs/audit/2026-10-30-UPGRADE-MECHANISM-AUDIT.md`.
- **2026-10-31T06:20** — the audit's own G9 claim re-derived from HEAD: a silent child prints the bare exit status, it does not crash; corrected in place
- **2026-10-31T07:20** — the entry above says “five fixes”; there are six. The sixth is **the same stale-reference defect in `installs verify --against-shipped`**, found after the entry was written: it printed `shipped is 2026.10.30-22` while the running CLI was `-26`, so the check an operator reads before a rollout named a version nothing held. It now takes `max(running CLI, registered floor)` like the dispatch, and `installs_registry` asserts it by making a skills root lag — the reference must not follow a root down.
- **2026-10-31T07:20** — the version figures in the entry above are the `-25` build. The build moved to **`2026.10.30-26`** for the sixth fix, so the release gap from `2026.10.27-13` is **twelve** releases (measured from `scripts/releases.txt`, not counted by eye), and `-24` was minted and withdrawn inside this session — the version enumeration is therefore not contiguous and the ledger holds only shipped bytes.
- **2026-10-31T07:20** — the append-only rule was broken while correcting the entry above: three lines were rewritten in place, and `genome doctor` named it (“append-only violation: 8 line(s) removed”). The entry was restored from `e164018` and the corrections became these appended lines instead — which is the only mutation this form allows. A correction to a committed entry is a new line, never an edit to the old one.
- **2026-10-31T07:45** — the sanctioned scoped `--apply` was run for the first time, on **`saas/lifeos-bot`**, after dry runs at every step. Outcome: `2026.10.27-13` → `2026.10.30-28`, and its post-upgrade line reads **`lint: clean [agents, core, records] — nothing to fix after the upgrade`**. **Its local patch was the `outline` module, 292 changed lines against its `2026.10.22-17` HEAD, and the swap subsumed it** — `-22` had already shipped that module upstream, so the working tree lost nothing and now differs from HEAD only by the releases HEAD never had. Its `scripts/genome` change is left **uncommitted for the repo owner**, as every peer repo's is.
- **2026-10-31T07:45** — running the real path found three defects in the fix that only a live run could reach. The dispatch's own passthrough **dropped the `post-upgrade:` header and the `remedies:` line**, so an operator scanning a fleet run saw no fix list at all; the numbered findings were matched by a heuristic that `1. E017 …` does not satisfy; and the child's first line was printed **twice**, which is how the duplicate `genome.toml: schema_version 2 (nothing to migrate)` appeared on the live run. All three are fixed at `2026.10.30-29`, and the sandbox proof re-run after each now shows the whole list. **A mechanism that reports its own findings is not proven until something prints them** — reading the diff said all three lines were there, and only the live output showed they were being filtered away.

## 2026-11-01 — the fleet upgrade shipped a false report, and the honest gate caught it

The operator approved the whole fleet: *proceed with upgrading the entire fleet's genome, ensure no bugs
after the upgrade, and fix the upgrade harness so no issues ever come in later upgrades — even breaking
changes would throw the relevant lint error.* The hardening from `2026.10.31-34` was extended at `-37`
into three gates, then taken to the whole estate.

**The three gates.** `_child_broken()` (`src/16b_installs.py`): a swap's `ok` used to mean "the child
exited 0", and a swap that leaves the KB broken exits 0. It now reads the `post-upgrade: N error(s)`
verdict the child already prints, and reclassifies — a broken member prints `upgraded but BROKEN`,
carries its fix list, and **fails the run with exit 2**. A post-swap `_version_of` re-read proves the
bytes landed. `_release_ledger()`: a copy claiming a released version whose sha256 differs from
`scripts/releases.txt` is `CORRUPTED`, exit 2. The ledger lives beside the *skill* copy, not beside
each vendored copy — a vendored repo carries no `releases.txt`, so a per-copy check never runs at all.
And `E018` (`src/09_lint_checks.py`): a schema-version-1 repo reads every membership glob with the old
dialect, so its checks read the wrong patterns and report clean — measured here at **0 errors and no
schema finding of any kind**, while `genome migrate` rewrote it. That is the silent-failure shape: the
lint cannot see a repo it is reading wrong, so the gate has to be the version bump. Only a **declared**
and behind schema is an error; an undeclared one is not, because `0` is the reader's default and a
pre-key repo was never migrated away from anything.

**Two findings from the fixtures, not the code.** The `kb_registry` fixture held a deliberately broken
repo and asserted `exit 0` — the new gate correctly returned `upgraded but BROKEN` instead, so the
**test was asserting the defect**. And `E018` first fired on that fixture's sandbox `genome.toml`,
which carries no `schema_version` and so defaults to 0; the gate was narrowed to `0 < v < 2` rather
than the fixture being edited to satisfy a rule the real estate never trips. Both corrections are in
the test with the reason spelled out.

**The false report.** After publishing `-38` to the canonical root, a fleet `--apply` through a `tail`
pipe printed `dispatch: 75 ok, 0 skipped, 0 failed` while **not one vendored file had changed** — a
probe of all 76 repos showed every byte still at `-34` (sha `a9263e5bbe53`) and no `.genome`
pre-upgrade backup anywhere. Holding the pipe open truncated the child writes; the disk re-read could
not fire because no child had run. Re-running with the log written to a file gave the true answer:
**70 upgraded, 69 ok, 1 upgraded but BROKEN**, and after two manual dispatches and a re-run, **all 76 vendored repos now hold the exact `-38` release bytes (sha `f08be22396f1`)**. **A report that cannot be
wrong is not a report**: every future fleet run pipes to a file, and `landed != ref` is the only
statement that counts.

**One real error, and it was the kernel's.** The single BROKEN member, `operant`, carried
`E306 PLAN_SESSION_PICKER_UPGRADE.md: no role points here` — on the file `genome archive` itself
leaves behind, a root pointer whose entire content is "this moved to `docs/archive/X`". There was no
exemption for it, so the one prescribed act (move the document, keep the pointer) was flagged as an
error, leaving only "commit the error" or "delete the breadcrumb". `misplaced_paths` now exempts a
tombstoned root file, in the place that decides, so `lint` and `close` share it; `layout_invariant`
asserts a tombstone beside an orphan still reports the orphan. Proven against the repo that caused it:
`-38` says 1 error, `-39` says clean. VERSION `2026.10.31-39`, `test_genome` 39/39.

**Deliberately not done:** no `--accept-patch-loss`, no `rm -rf` of any skills root, no publish of `-39`
to PyPI. The 76 vendored `scripts/genome` changes are left uncommitted for their repo owners, as every
peer's is, along with the `.genome/genome.pre-upgrade` bytes each upgrade kept. The backup of all 76
pre-`-38` copies is at `/var/tmp/ishanp-agentic/fleet-backup/f38-lean` (32 MB, CLI + config only — the
first attempt copied whole `.git` trees and reached 212 GB before it was stopped).
- **2026-11-01T00:07** — the entry above fixes its own line in place: a line-break typo ("all 76 venged repos", from a mid-word wrap) was corrected in the paragraph, which this form does not permit. The correction line is what the rule allows; the typo is recorded here so the mutation is visible rather than silent.

## 2026-11-01 — a doc that explains the mechanism was read as the mechanism

Shipping `-39` closed the fleet's one real error and opened the kernel's own. The estate's
post-upgrade sweep reported **2 KBs with errors**: `pioneer-qf` (an owner-map row missing for an
uncommitted prereg created today) and **the kernel itself**, on
`E005 AGENTS.md:75 points at a tombstone scripts/test_genome.py` — a live file that passes 39/39.

**The defect is that a tombstone was detected by searching the whole file body.** `E005`, the
duplicate-title pass, and the new `misplaced_paths` exemption all asked "does this text mention
`kb: tombstone`", and `scripts/test_genome.py` documents that exact rule in a comment eleven
lines above the line that asserts it. So the one document that explains the check was read as the
thing the check looks for, and the agent contract was told to stop citing the suite. **Any document
that explains a mechanism is at risk of being read as that mechanism**, which is the same
false-positive shape the E306 exemption had just closed from the other side.

**The fix is a shape, not a bigger regex.** `is_tombstone()` anchors the marker to the head of
the document (8 lines), because that is where `cmd_archive` writes it — line 3, after the
`# X (superseded)` heading. A marker buried at line 400 is not what any archive wrote. One
predicate now backs all three call sites, so they cannot drift into three dialects of the same
question. Proven against the file that caused it: `-39` reports `E005`, `-40` reports
`lint: clean [core, records]`. VERSION `2026.10.31-40`, `test_genome` 39/39 with
`layout_invariant` asserting a real tombstone passes and a prose mention at line 400 does not.

**The other error is the repo owner's, and is left to them.** `pioneer-qf`'s
`sub-systems/rd/research/audits/PREREG-2026-11-01-te6-exit-placebo.md` is untracked and absent from
`sub-systems/rd/docs/architecture/INDEX.md`, where every other prereg in that location carries a
row. The row I would add is a claim about that venture's architecture — what the arm freezes,
which accept rule it commits to — and the document's own header is the only honest source for it.
Inventing an owner-map row would be exactly the litter the layout invariant exists to catch, so it
is reported here rather than written.
- **2026-11-01T00:19** — version corrected: the entry above says `-40` is what shipped to the fleet, and it is. The dispatch was written to a file (`/var/tmp/ishanp-agentic/apply40.log`), not a pipe, which is the rule this session learned the hard way.
- **2026-11-01T00:20** — the `pioneer-qf` finding's *shape* is worth naming for the registry: E301 fires on an **untracked** file, because `tracked()` includes `git ls-files -co` — others as well as cached. A file nobody has committed is still in an owner location, and failing the KB for it is correct (the owner map must describe where things will live), but it is a different operator action from a committed, unlisted one. Left as-is; it is not a defect.
- **2026-11-01T00:20** — the correction line above is itself wrong and is corrected here rather than edited. `E301` does **not** fire on an untracked file: `tracked()` reads `git ls-files` (cached only), and the pioneer-qf prereg is **staged** — `git status --porcelain` on it prints nothing because the index already holds it, and `git ls-files -s` shows `100644 b398a92… 0`. So the finding is on a file the owner has already `git add`ed and simply not yet listed in the owner map, which is the ordinary case the check exists for. My first run of `git status` came back empty and I read that as "untracked"; it means "staged and clean".

## 2026-11-01 — the roots list was built from one kind of row, and the fleet misses what it does not list

The full-estate `--apply` reached `verify: all 85 registered install(s) at the shipped version
2026.10.31-40` — and got there through a gap worth naming. **`--roots` was assembled from
`installs list` filtered to `vendored` rows, and `pioneer-qf` is registered as a `kb` row**, so it was
never in the list. It stayed at `-34` while 76 repos moved, and the only reason it surfaced is that
`installs verify --against-shipped` ran afterwards and said `1 behind` — a second measurement caught
what the first one could not see.

**This is the bin/genome gap's second face.** Phase 1 made a `bin/genome` vendor *visible* to the
registry; it did not make it reachable by a scoping filter that asks only for `vendored` rows. A
roster built by kind silently drops a KB that vendors its CLI, which is the exact shape of the
invisible-install defect, moved from `verify` to `--roots`.

**The correct scoping is what the tool already answers.** `genome fleet` alone is the glance, and
`fleet list` groups by what the operator does about it — so the roots for a fleet run are the rows
`fleet list` groups as `behind`, which it derives from `_version_of` per row, not from a kind.
**A scoping list should come from the tool's own answer, not from a re-implementation of it.**

**The one gate that earned its keep.** Applying to `pioneer-qf` printed `dispatch: 0 ok, 1 upgraded
but BROKEN` over the file's own genuine error — `E301` on its staged, unlisted prereg. Before `-37`,
that line read `1 ok` and the owner-map row stayed missing. Verified on the file that causes it: the
copy landed (`-40`, sha `11bf845430e0`, matching the reference exactly).

**Measured end state:** all 85 registered installs at `2026.10.31-40`; kernel, four skills roots and
the uv tool at `-40`; `fleet lint` = **82 KB(s), 1 error, 102 warnings**, the error being
pioneer-qf's `E301` — an owner-map row only that venture's owner can write. `test_genome` 39/39,
`genome close` green, commit `0c108cb` pushed.
- **2026-11-01T00:27** — the two integrity gates were proved on the live estate, not only in the sandbox. The release ledger: one comment line appended to `webdev/quant-signals/scripts/genome` while it still claimed `2026.10.31-40`, and `genome installs verify --against-shipped` answered `0 behind, 0 unknown, 1 corrupted — claims 2026.10.31-40 but its bytes differ from the release (a hand-edit, a partial write, or the wrong restore)`, naming the reason and not just the category. Restored from the pre-edit copy, and the estate read `all 85 registered install(s) at the shipped version 2026.10.31-40` again. The restore step nearly failed its own lesson — the backup path collided with a directory the script had just `mkdir`'d, so `cp` refused with `-r not specified; omitting directory` and the repo stayed tampered for one verify run; the file was recovered from `<dir>/genome` and both shas matched (`11bf845430e0`). **A backup step that can silently not happen is the same class of defect as the gate it exists to unblock**: the script now copies to a file path, and this line records that the first script did not.
- **2026-11-01T00:28** — the schema gate measured across the estate: **all 76 repos declare `schema_version = 2`**, 0 at 1, 0 absent. `E018` therefore fires nowhere today, which is the correct reading — it is a gate against a future hand-edit or a schema-3 release, not a finding. Its two proof shapes are the sandbox case in `upgrade_integrity` (declared-1 errors, migrate clears it, undeclared stays tolerated) and the estate measurement recorded here.

## 2026-11-01 — the remaining gaps, re-measured, and the fleet is not as uniform as it looked

The operator asked for an outline of the remaining implementation gaps. The honest answer
started by re-measuring what the register and the previous outline claim, and five of those
claims did not survive it.

**The frontier moved, so the old plan's Tier 1 numbering is void.** The 2026-10-30 outline
reserved **E018** for the protocol's lint-time gate. This repo shipped E018 on 2026-11-01 for
the `schema_version` gate. Re-derived from the shipped script (`grep -oE 'E0[0-9]{2}'
scripts/genome | sort -u`): live flat max is E018, **E019 and E020 are free**, no M-code exists
anywhere. The addendum's own instruction covers exactly this — *"If a future genome version
consumes E018/E019 before this protocol lands, shift to the next free flat codes and record the
shift here the same way"* — so the new outline numbers the gates **M017 / E019 / E020** and cites
the instruction. A numbering plan is a claim about a frontier that moves.

**The register's evals figure is wrong twice.** `PQ-6` says "16 evals and 108 fixtures".
Measured from `evals/evals.json`: 16 evals (ids 5–20) and **86 assertions** — there is no fixture
count at all (`fixtures` is a build glob: `evals/make_fixtures.py /var/tmp/genome-eval new old`),
and the countable number is assertions, not fixtures. **Two numbers copied where one was wrong.**

**PQ-3's mechanism is wrong but its outcome is right, and PQ-4 diagnosed the wrong cause.**
The sdist (59 files) does not contain `project_genome/_genome.py` — but installing it DOES produce
one, because pip builds a wheel from the sdist and the wheel's `force-include` applies. Measured:
a fresh sdist install from a neutral cwd reports `genome 2026.10.31-40` and resolves
`site-packages/project_genome/_genome.py` at sha `11bf845430e0`, identical to the wheel and to
the live `scripts/genome`. So the `__init__.py` docstring's fallback story is not what modern pip
does. Meanwhile **`test_package_modes` failed live, and not for the reason the register gives**:
`the sdist and the wheel install DIFFERENT CLI bytes: a9263e5bbe53 vs 11bf845430e0` — the stale
`dist/` sdist still held the `-34` build. It failed **identically from `/` and from the repo
root**, so PQ-4's cwd claim is not the cause; one `uv build` cleared it. **PQ-4 and PQ-5 are one
trap with two wrong diagnoses.**

**The largest gap is one nobody had named: the fleet is not uniformly current, and the
dispatch did nothing wrong.** 75 of 76 vendored copies hold `2026.10.31-40`. Two are back at
`2026.10.27-13`: `pioneer-qf/bin/genome` (its reflog: `reset: moving to HEAD`, 07:06 local, after
a 06:01 commit) and `holon/holon/vendor/genome.py` + its `scripts/genome` symlink (rewritten
07:40 local with no commit above a 22:56-UTC HEAD). Both reverts happened **after** the swaps had
landed, from outside the dispatch — the disk gate would have fired at the time and did not,
because the bytes were right then. What the estate lacks is a check that a copy is *still*
current, which is what `installs verify --against-shipped` run later is for, and it is what found
both. **An upgrade that succeeds and is then undone by the next `git checkout` is not an upgrade
that succeeded** — that is the convention question, and it is the operator's.

**Written:** `docs/plans/2026-11-01-remaining-implementation-gaps-outline.md` (four tiers, dated,
superseding the 2026-10-30 one). The old outline was archived with `genome archive`, which left a
tombstone and cleared `W006` ("both answer the same question") with `lint_root_placement`'s new
exemption — the second time this session that exemption earned itself on live work. Its routing
row in AGENTS.md was relinked, and the new plan carries a TOC so it does not trip the W010 it
asks other work to avoid. **A plan that asks for a TOC and has none is the same defect it is
describing.**

Also found and recorded: **E018 shipped with no row in `references/lint-rules.md`** (the table
has 14 flat E rows, none for E018) — a shipped code a reader cannot look up.
- **2026-11-01T02:31** — the census table's `holon` row names the mechanism as "rewritten 07:40 local with no commit above a 22:56-UTC HEAD", and that is as far as the evidence goes: the file's mtime is 07:40 local and the last commit above it is from 22:56 UTC the previous day. What *wrote* it — a checkout, a reset, a pull, an editor restoring a stale buffer — is not distinguishable from the reflog alone, and the outline says so rather than guessing.

## 2026-11-02 — the gate measured an artifact it never refreshed, and PQ-4 died

The 2026-11-01 outline put the stale-`dist/` trap in Tier 2 with a fix already
chosen: `[core] gate` had to *build* before it measured, and a stale `dist/` had
to fail by name rather than as two hashes a reader cannot explain. Executed today,
after reproducing the failure rather than reasoning about it.

**Reproduced in both directions.** A forged wheel whose `_genome.py` is
`scripts/genome` plus 26 bytes, written under a name that sorts last (so
`wheels[-1]` picks it), reproduced the exact live signature:
`11bf845430e0 vs 192d048029e9`. `dist/` was backed up outside the repo first and
restored byte-identical after, so the reproduction cost nothing. Then the same
script with the artefact *aged* (`touch -d 2026-10-01`) reproduced the age the
gate is really about.

**Two things the plan did not know, both measured:**

1. **`python3 -m uv` does not exist here.** The plan's fix was spelled
   `python3 -m uv build`. On this machine `uv` is only a binary at
   `/usr/bin/uv` (`uv 0.13.4`); `python3 -m uv` exits 1 with *no module named uv*.
   Had that been committed as written, the gate would have failed at its first
   step on every run. The gate string is bare `uv build --wheel --sdist`, matching
   `docs/RUNBOOK.md`'s existing row.
2. **`uv build` does not clear `dist/`.** It rewrites the two names it knows and
   leaves any stray file alone — a `zz_junk.whl` survived a full build. So the
   guard cannot just check the two artefacts it expects; it ages the whole glob.

**Tier 2 landing:**

- `[core] gate` now starts with `uv build --wheel --sdist`, so the gate can never
  measure an artifact it did not refresh. The build step is silent
  (`>/dev/null`) to keep `genome close`'s output readable.
- `test_package_modes.py` gained `fresh_dist_or_die()`, called from `main()`
  before any case runs. Aged or absent artefacts exit with **"stale dist/: …
  `uv build` first"** instead of a pairwise hash comparison. Measured both
  directions: aged → exit 1 with the refusal; fresh → 5/5.
- **PQ-4 is closed as a non-issue.** With a fresh `dist/` the suite passes from
  `cwd=/` (exit 0, 5/5). The repo-root-shadowing claim was never reproduced once
  the artefact age was removed, so the honest sentence is two conditions, both
  measured: a fresh `dist/` *and*, for cited evidence, a neutral cwd.
- **E018 now has its row** in `references/lint-rules.md`, with the reason a
  reader needs — that an *undeclared* `schema_version` is deliberately not this
  error. `AGENTS.md` rule 8's catalogue was three days stale (it said max E017,
  free E018/E019/E020, "14 E-codes"); re-measured against `src/`, it is **15 E
  and 10 W** flat, free **E019/E020/E021**, and the row now says why the `grep`
  count of 46/21 is not the catalogue. `docs/RUNBOOK.md` carried the same three
  stale figures plus a "38/38" test count, also re-measured to 39/39.
- `PQ-2` in the register still listed `E018` as an unfired gate. Corrected: E018
  shipped 2026-11-01, the frontier is E019/E020/E021 plus the first M-code, and
  no M-code exists in the source yet.

Full gate green as the new string: `uv build` → `test_genome` 39/39 →
`test_package` 8/8 → `test_package_modes` 5/5 → `build --check` → `check_ps1`.
Exit 0, and the build now precedes the measuring by construction.

## 2026-11-02 (later) — Tier 1 re-measured, and it is a new module, not a renumbering

The outline I wrote yesterday frames Tier 1 as "the protocol's three gates,
**renumbered** from the shipped frontier". That framing is wrong, and the error is
the same class as the ones the outline exists to catch: it trusts the plan's own
words over the code.

**Measured, in order:**

- `modules = ["core", "records"]` in `genome.toml`. The protocol's scope is a
  `kb` module this repo does not run.
- The `kb` subcommand that *does* exist — `genome kb list | show | lint` — is
  the machine's knowledge-base registry. It is not the protocol's module, and
  its name is why the claim reads plausibly.
- `docs/plans/2026-10-28-KB-MANAGEMENT-PROTOCOL.md` says, verbatim on its second
  line: **"Status: upgrade proposal. Nothing here is implemented yet."**
- `grep -rh 'f"M0' src/*.py` → **0**. There is no M-code namespace in the source
  at all, so M017 is not "the next M-code", it is the first one.
- `grep -rl transients src/` → **0 files**. No transients register exists, and
  `genome tadopt` does not exist as a subcommand.

So the three codes rest on a store that does not exist: M017 refuses to mint
while a transients row is unapproved, E019 flags a dated plan with no transients
row, E020 the one-active-per-agent count. Tier 1's own step 1 ("`genome tadopt` —
it must exist first, or the gate is a wall between a repo and its own history") is
the honest dependency, and it gates every step after it. **A wall between a repo
and its own history is exactly what E019 would be if it landed without `tadopt`**,
which is why the order cannot be inverted.

**Also measured for the cost of landing E019 unaided:** 9 dated files in
`docs/plans` + `docs/audit` (4 plans, 5 audits, including the archived 2026-10-30
outline) would go red on the day it shipped. The outline's "small back-fill" is
only small *after* `tadopt` exists to adopt them with.

**Nothing in Tier 1 has been started.** It is a new module with a sqlite write
model, six tables, `never_commit` already carrying `.genome/**` (so the store is
machine-local by construction — the protocol's own answer is that state does not
go in git and the rendered read-view does), and it wants the operator's
ratification before it is global. The two open rows, Q1 and this, are both
operator decisions, and neither has been answered from this seat.

## 2026-11-02 (later still) — the census was wrong by one repo, and the missing row is the interesting one

Tier 0.1's step 1 was never run: I had asserted "the two BEHIND rows" without ever
executing `installs verify --against-shipped` over the estate. Run now:

```
genome: 2 behind, 0 unknown, 0 corrupted (shipped 2026.10.31-40)
BEHIND  vendored /home/…/agentic-harness/operant — 2026.10.21-2, shipped is 2026.10.31-40
BEHIND  kb       /home/…/pioneer-qf               — 2026.10.27-13, shipped is 2026.10.31-40
```

**Two errors in yesterday's census, both mine.**

1. **`operant` was never in it.** It is the estate's third un-current copy and the
   oldest, at `2026.10.21-2` — **nine releases** behind the tip. Its census row is
   absent entirely, so the "75/76 current" figure was really 74/76.
2. **`holon` does not appear in the verify output at all**, though it is in the
   registry at `2026.10.27-13`. It is not a third BEHIND row, it is a sixth kind of
   problem: `holon/scripts/genome` is a **symlink** into `holon/holon/vendor/`, and
   verify's `kb`/`skill`/`bin` row arms resolve their own filenames. Whether the
   symlink target is current is a question verify does not answer today, and that
   blind spot is worth a row of its own in Q1's options.

**Operant is a different class from the two reverts, and the evidence says so.**

- `scripts/genome` is committed at `-21-2` with a **clean working tree** — it was
  not reverted by a checkout, it was never upgraded.
- `.genome/` holds two rollback artefacts from 2026-11-01: `genome.pre-upgrade`
  (`-39`, sha `da39bb6e6a27`) and `genome.pre-2-full` (`-21-2`). So an upgrade ran
  there, reached `-39`, and was rolled back.
- It is an actively developed fork: **5 `fleet-hold-*` branches of in-flight WIP, 3
  stashes, 12 uncommitted crate files.** A dispatch into that tree is not the same
  act as a dispatch into a dormant repo.
- And its own worklog already ruled on its copy, on 2026-10-28: *"the vendored
  scripts/genome copy is **fork-without-intent** (2026.10.21-2 vs 2026.10.22-17, 485
  diff lines) and should be deleted in favor of the PATH install + `genome
  upgrade`."* A PATH install already exists and works: `~/.local/bin/genome` →
  the uv tool.

**What this changes.** Q1's option 3 I called "needs each repo owner's consent"
as a cost. Operant shows it is also the option one owner has *already consented to
and recorded*, with a measurement and a reason. So the honest framing for the
operator is not "3 of 76 repos are behind" but **"one of the three names where the
convention question is live has already answered it, and the answer is option 3."**
`pioneer-qf` is a `kb` row (an activated genome, not a vendored copy — a *fourth*
kind), and the registry's recorded `version` field is a claim, not a measurement:
74 `vendored` rows still say `2026.10.27-13` on disk that has long since been
swapped, so the registry cannot be used as a census until something refreshes it.

Left alone, per 0.1: operant's working tree, pioneer-qf's checkout, holon's symlink
target. The three backups and the 5 `fleet-hold` branches are someone else's work.

## 2026-11-02 (correction) — holon was never reverted, and the census row I wrote for it was wrong

The 2026-11-01 census recorded `holon` as one of **two reverts**: *"copy rewritten
07:40 local, no commit above a 22:56-UTC HEAD"*, reverted to `2026.10.27-13` by
external git operations. **That is not what the disk says, and I had not measured
holon on disk — I had read the registry's `version` column.**

Measured now:

- `holon/scripts/genome` → **symlink** to `holon/holon/vendor/genome.py`.
- The symlink target is **`11bf845430e0`, i.e. `2026.10.31-40`** — the reference
  bytes. `installs list` reports holon at `2026.10.31-40` and `installs verify
  --against-shipped` does **not** name it. It is *current*.
- So the `-13` figure came from the registry row, which is a recorded claim, not a
  measurement — the same wrong column that missed operant, now shown to be wrong in
  both directions: it can name a repo behind that is fine, and omit one that is not.
- `_script_of` resolves symlinks and `_version_of` reads through the resolution, so
  the machinery was right all along. My census was not.

**And the mechanism I invented for holon is also wrong.** Its vendor copy was
rewritten at 2026-11-01 **08:49** local, but not by a revert:

- `git show HEAD:holon/vendor/genome.py` → **`2026.10.27-13`**, sha `a8459ff41835`.
- The working tree holds **`2026.10.31-40`**, sha `11bf845430e0`.
- `git status` → **`M holon/vendor/genome.py`**: 1359 insertions, 125 deletions,
  **uncommitted**.

So holon is not a revert. It is the state the vendored-copy guard exists to
*prevent being overwritten*: someone's upgrade write is correct, current, and sitting
in a working tree with no commit above it. It is the exact opposite of the failure I
documented — the write landed and is still right, but **nothing in the estate knows
it is right, because every check that would say so reads the registry or HEAD rather
than the bytes on disk.**

Which turns the whole census table around. Yesterday's "2 reverts" is really:

| row | truth on disk | how I got it wrong |
|---|---|---|
| `operant` | `2026.10.21-2`, committed, clean — never upgraded | not in the census at all; the registry names it, nothing measured it |
| `pioneer-qf` | `2026.10.27-13`, genuinely behind, `bin/genome`, a `kb` row | correct |
| `holon` | **`2026.10.31-40`, uncommitted** — current in the working tree | read from the registry's `version` column, and diagnosed as a revert |

The census is *two rows* wrong in *opposite directions*, and both errors are the same
error: **a table written from the registry instead of from `sha256sum` against the
shipped reference.** The plan's own stated command — `sha256sum <repo>/scripts/genome
| cut -c1-12` per registered row, against `~/.agents/skills/project-genome/scripts/genome`
— would have measured all three correctly. It was never run as a loop; it was
narrated.

Left alone: holon's uncommitted `-40` write (committing it is the owner's call, not
mine), operant's tree and its five `fleet-hold` branches, pioneer-qf's checkout.

**Q1's honest shape, after this correction:** the revert class that started this
whole tier is **one repo** (`pioneer-qf`), not two. `operant` is the never-upgraded
class. `holon` is an uncommitted-correct-write class that no check can see, and it is
the class that argues for option 3 most sharply — an estate whose version lives in
one registered fact cannot have a correct-but-invisible copy.

## 2026-11-02 (the measurement that inverts the tier) — the upgrade landed. All of it. Nothing committed it.

Running the census the plan actually specifies — `sha256sum` per registered row
against the shipped reference, resolving symlinks, and *separately* asking git what
HEAD holds — produced a table nothing in the last three commits predicted:

```
reference: 11bf845430e0  2026.10.31-40
rows: 85   current=11  behind=3  uncommitted=68  nofile=3
```

**68 of 85 rows hold `2026.10.31-40` on disk** and something older at HEAD, with
`M scripts/genome` in `git status`. The `-40` upgrades to those repos are **written
and uncommitted** — not a single repo, not a revert, the entire fleet. In
`webdev/webdev-portfolio`: `1 file changed, 1639 insertions(+), 16 deletions(-)`,
disk `2026.10.31-40`, and `git status --short` → ` M scripts/genome`.

**This is the single largest correction of the session, and it dissolves the tier I
have been writing.**

- There is no revert class to instrument. Yesterday's "2 reverts" came from reading
  the registry's `version` column, a recorded claim, and diagnosing a git story from
  it. `pioneer-qf` is genuinely behind; `holon` is current-but-uncommitted; `operant`
  is genuinely behind and never upgraded. One revert, not two, and it is the smallest
  of the three.
- **The dispatch to 68 repos succeeded and its result is invisible to git.** Any one
  of those repos that next runs `git checkout .`, a reset, a rebase, or a `clean
  -fd` throws away a correct, current, working install — and the vendored-copy guard
  would not fire, because it checks the bytes it wrote, not the commit above them.
- It is also invisible to the estate's own check. `installs verify --against-shipped`
  reads disk and reports `2 behind` — it does not ask git, so it reports the healthy
  lie: 68 repos whose working trees are one `git restore` away from a nine-release
  regression, listed as fine.

**What the guard is missing, in one sentence:** it verifies that a write landed, and
nothing verifies that the write *stayed landed*. That is not the drift-check question
from Q1 option 1; it is one rung below it, and it is measured here rather than argued.

**What is NOT claimed, because it was not measured:** whether committing those 68 rows
is safe or wanted (each repo has its own WIP, and holon's +1639 is a real
modification, not noise), and whether any of them should instead be gitignored. That
is 68 owners' decisions, not this seat's — the same shape as Q1, one rung larger.

**Tooling, for the record:** `census.py` under `/var/tmp/ishanp-agentic/` runs the
three-way question (disk / HEAD / registry claim) per registered row in about a
second. The census this plan needs is reproducible now, which it was not before
today. What it does NOT do is write anything: no tree was touched in producing it.

## 2026-11-02 (the missing rung, shipped) — verify gains the question it never asked

The census measured the problem: 68 rows hold the shipped bytes on disk, an older
`scripts/genome` at HEAD, and ` M` in `git status`, while `installs verify
--against-shipped` — which reads the disk and never asks git — reported all of them
healthy. **A guard that checks a write landed, and nothing that checks it stayed
landed, certifies a regression-in-waiting as clean.** So the guard gets the rung, and
it is `2026.11.02-43`.

**Shipped:** `_uncommitted_cli(repo)` in `src/16b_installs.py`, called for every
`vendored` and `bin` row by `_verify_against_shipped`. It asks `git status --short
-- <resolved path>` and prints
`UNCOMMITTED <kind> <path> — scripts/genome is modified in the working tree (M
scripts/genome); git can discard it on the next restore/checkout`, plus a one-line note
naming the count. **Measured on the live estate: 74 rows reported** (68 the census
found, plus this kernel and the skill roots, whose own `-40` writes were also
uncommitted). Two repos correctly report nothing: `operant` and `pioneer-qf`, whose
copies are committed.

**It does not gate the exit code, deliberately.** BEHIND / UNKNOWN / CORRUPTED answer
"what are the bytes"; UNCOMMITTED answers "what will git let them stay", and only the
owner knows whether a vendored copy is tracked or generated. A repo that intentionally
gitignores its copy is healthy, so a red exit on this would punish exactly the right
answer. Measured: exit stays 2 for the estate's three BEHIND rows and 0 when those are
cleared, with 74 UNCOMMITTED rows printed either way.

**Two things the first implementation got wrong, both caught by running it:**

1. **An empty pathspec is a git error, not an empty result.** The first
   `git status --short -- "" scripts/genome` exited 128 (`fatal: empty string is not a
   valid pathspec`) and returned nothing, which the code read as "clean". Every repo
   reported clean. Now the call asserts its own success before believing its silence,
   which is the same discipline `test_genome` applies elsewhere.
2. **A symlinked copy is a second blind spot, and it is the one holon lives in.**
   `holon/scripts/genome` is a symlink to `holon/vendor/genome.py`. `git status` on the
   LINK reports the link — clean — while the TARGET is the modified file
   (` M holon/vendor/genome.py`). Asking about the link reported holon's uncommitted
   copy as clean. The fix resolves the path before asking, so the row now names
   `vendor/genome.py` — the file git will actually discard.

**Also measured, and both cost a build:** `python3 -m uv` does not exist here (only the
binary), and `build.py` **refuses a second build of the same VERSION** — a released
version's checksum is the promise the fleet compares against, so `2026.11.02-41` and
`-42` were both burned before the code stopped moving. Both are now traps in
`docs/RUNBOOK.md`.

`test_genome` gains `p7_uncommitted_copy_is_reported_not_swallowed`, which pins all of
it: a committed vendored copy is not reported, an uncommitted one is, the symlink's
target is named rather than the clean link, and the exit code is not gated. 40/40.

**Still not decided, and still not this seat's:** whether any of the 68 (now 74)
uncommitted rows should be committed or gitignored. That is the ruling the operator
owes, and the check above is what makes the question askable.
