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
