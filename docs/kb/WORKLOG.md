# Worklog

Append-only: `python3 scripts/genome log "<entry>"`, one per unit of work.

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
