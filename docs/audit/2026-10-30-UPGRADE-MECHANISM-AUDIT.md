# UPGRADE-MECHANISM AUDIT — why a scoped fleet update was not one command

**Status:** written 2026-10-30 at VERSION `2026.10.30-25` (6,970 lines, 27 `src/` modules,
`python3 scripts/build.py --check` exit 0 at this commit).
**Scope:** the upgrade mechanism only — `genome installs upgrade`, the dispatch it
performs, the skill copy it swaps in, and the registry that names the targets. It does
not re-audit the installer (that is
`2026-10-30-SKILLS-ROOT-AUDIT.md`) or the KB protocol gates (that is
`../plans/2026-10-28-KB-MANAGEMENT-PROTOCOL.md` + its addendum).
**Method:** source reads against `HEAD` (`ffc95f1`, extracted and grepped, not
remembered), live dry runs against one repo, registry measurements on this machine, and
a sandbox reproduction of the bootstrap failure. Every number below was derived here.
**Outcome:** ten gaps found, five fixed in this repo at `2026.10.30-25` (§5), and the
scoped update is now one command (§6). Nothing was applied to the fleet.

## 1. The measured state this audit began from

| fact | measurement |
|---|---|
| the fleet | **77 vendored CLI files across 77 repos** (the kernel's own `scripts/genome` is the 78th `scripts/genome` on disk and one more sits inside `.genome-backups`; both excluded), of which **75 sit at `2026.10.27-13`**, `operant` at `2026.10.21-2`, `artificial-route` at `2026.10.22-17` |
| the shipping reference | the four skills roots (`~/.agents`, `~/.claude`, `~/.zcode`, `~/.codex`) all at **`2026.10.30-22`** — one release behind the kernel |
| the registry | **86 rows, 82 distinct paths** (78 vendored, 3 kb, 4 skill, 1 bin): `holon` and the four `project-genome` skill rows each resolve to a name shared by several rows |
| the registry's ghosts | **2 rows point at nothing** — `holon-personal` and `holon-personal/holon` — yet every dry run counted them as targets |
| registry vs disk | **of 81 registered vendored/kb rows, 79 resolve to a real directory and 77 of those hold `scripts/genome`** — exactly the 77 vendored files on disk, so the registry is complete. The 2 rows with a directory but no CLI are the meta-root itself (a KB with no CLI, correct) and `pioneer-qf` (vendors at `bin/genome`) |
| the release gap | **10 releases** separate `2026.10.27-13` from `2026.10.30-23` (`-14 … -23`, measured in `scripts/releases.txt`); 11 to `-25` |
| the per-copy delta | a `-13 → -25` swap is **807 lines added, 6 removed** (measured by difflib on `saas/lifeos-bot`) |
| suites before this audit | `test_genome` 38/38, `test_package` 8/8, `test_package_modes` 5/5, `check_ps1` parity ok at 412 lines |

The operator's directive was to bring every genome-managed KB under
`~/Documents/github/my-projects` to the latest kernel version — **scoped runs only,
`--apply` always preceded by a dry run**. This audit is the "is that actually one
command" check, and the answer at `ffc95f1` was **no**: the mechanism had ten gaps, and
one of them made the sanctioned scoped test impossible.

## 2. The ten gaps, each with the evidence that it was real

All ten were verified against `HEAD:scripts/genome` (extracted to a scratch file), so
none is a recollection.

**G1 — `--roots` was parsed and then ignored by the dispatch.** At HEAD the parser
accepts `--roots` (it is the scan verb's flag) and `_dispatch_upgrade` takes
`(rows, apply)` with **zero references to `roots` in its body** (grep count 0). So
`genome installs upgrade --roots lifeos-bot` ran the whole fleet. This is the gap that
made the operator's sanctioned scoped test impossible to perform: every "scoped" run was
a fleet run by another name.

**G2 — a scope that matched nothing printed the all-clear.** At HEAD, `--roots
no-such-repo` produced `dispatch: nothing to upgrade (every registered copy is at …)`
and exit 0. That is the single most dangerous output the mechanism can produce: an
operator reading it concludes the fleet is current.

**G3 — no `unregister` verb.** The registry can add and verify but never forget
(`unregister` appears at HEAD only inside the `scan` output's phrasing). Two ghost rows
persisted and inflated every target count, which is the same class of lie as an empty
registry reporting green.

**G4 — `cmd_upgrade` ran `migrate` but never linted.** Grep of `cmd_upgrade` at HEAD:
`lint`/`run_lint` count 0. An eleven-releases-behind KB was upgraded and the run ended on
`upgraded X (backup: .genome/genome.pre-upgrade)` — with the errors that the new schema
introduced never printed. The operator's ask was the opposite: name the concrete
errors/warnings to fix inside each KB.

**G5 — `skill_copy()` hardcoded one of four roots.** At HEAD the function's candidate
list had exactly **one** `skills/project-genome` path (`~/.agents`). The machine has four
roots at four distinct inodes, and a hardcoded answer means a fleet whose `.agents` root
lagged upgrades to the lagging copy.

**G6 — the dispatch handed the child no source override.** At HEAD, the subprocess call
passed **no `env` at all**, so each repo's own vendored CLI resolved its own swap source
through its own (old) `skill_copy()`.

**G7 — G5 + G6 together are the bootstrap failure, proven in a sandbox.** A dispatch
from `-23` delegates to each repo's old CLI; that CLI's `skill_copy()` points at
`-22`; so the fleet converges on `-22` and stops. Reproduced with the environment unset
(`-13 → -22`) and with `GENOME_SKILL` pointed at the release (`-13 → -23`). Without the
env hand-off, **a fleet dispatched from the tip could never reach the tip** — it could
only ever reach the last thing install.sh published.

**G8 — the reference was the registered floor, not the running CLI.** At HEAD,
`ref = max(registered skill/bin versions)` = `-22`. On a development day the running CLI
is `-23`/`-24` and the roots are one release behind, so the dispatch reported a target
older than itself.

**G9 — a child that printed no reason was reported as `ERROR  <path> — 1`** (the bare
return code). At HEAD the line is `{out.splitlines()[0] if out else res.returncode}`:
when the child produced no output, the repo was named and the *exit status* was
printed, which is not a reason. (`out` empty takes the `res.returncode` branch, so this
is not a crash — verified — but it is still uninformative: `genome: not a genome repo`
and `genome: disk full` both surface as `1`.)

**G10 — the `--roots` help text mentions only `scan`.** The flag is now the dispatch's
scope too; a help string that names one verb teaches the operator that the other does
not exist.

## 3. Why the gaps compound, and which ones are the same defect

Three of the ten are one defect seen from three angles: **G5, G6 and G7/8 are all "what
copy does the fleet converge on"**. Fixing any one of them alone still leaves the fleet
one release short, which is why the earlier pass could not close this with a single
change: the reference (`-22`) fed the dispatch, the dispatch did not correct the source,
and the source each child read was itself hardcoded.

Two more are the same defect from two sides: **G1 and G2 are "scope is not honoured"**.
Honouring the scope but not failing on an empty match would let a typo'd root name look
like success.

G3 and G4 are the reporting pair the operator actually asked for: a registry that
over-reports its targets, and an upgrade that under-reports its findings.

## 4. The design decision, and why it is the smallest one that holds

A dispatch has exactly one job: **make every stale copy the same bytes as the newest
genome on this machine, and say what each repo must fix afterwards.** That is two
numbers and one source, so the fix resolves all three from the running CLI rather than
from any registration:

- the **target** is `max(the running CLI's own VERSION, the highest registered
  skill/bin version)`. The floor still matters: a repo whose CLI is newer than the roots
  but which is being run from an older checkout should not be dragged backwards, and the
  floor prevents exactly that. An operator mid-development wins on both counts, which is
  intended — the developing kernel is what the fleet is converging toward.
- the **source** each repo's CLI reads is `GENOME_SKILL`, an environment variable every
  version already honours, so no repo needs the new code to receive the right source.
- `skill_copy()` now probes all four roots **and the kernel's working tree**, taking the
  newest file that exists. The kernel is scored on merit, not privilege: it wins on a
  development day and loses when it is checked out older than the roots.

A scope that matches nothing dies with exit 2 and names the registered count. A registry
row can now be forgotten. An upgrade now ends with a numbered fix list and the command
that clears each finding.

## 5. What was changed (all in this repo, nothing applied to the fleet)

`src/16b_installs.py`, `src/18c_federation.py`, `src/19_main.py`,
`src/01_constants.py` (VERSION `2026.10.30-23 → -25`), and
`scripts/test_genome.py` (the `kb_registry` case's dispatch assertion was over-broad: it
forbade the skill root appearing anywhere in the output, which the new honest
swap-source line legitimately does; it is now scoped to the target lines, and the
swap-source line is asserted instead).

| gap | fix |
|---|---|
| G1 | `_dispatch_upgrade(rows, apply, roots)`; `--roots` scopes by name or path |
| G2 | an empty scope dies with exit 2 and the registered count (86, not the deduped 82 — see §7) |
| G3 | `genome installs unregister <path>` — exact path first, then an UNAMBIGUOUS name match |
| G4 | `_post_upgrade_findings()`: lint after the swap, numbered, with remedies; never fails the upgrade |
| G5 | `skill_copy()` probes all four roots plus the kernel working tree, newest wins |
| G6 | the dispatch hands `GENOME_SKILL` to every child |
| G7 | both together: a `-25` dispatch now swaps `-25` into a `-13` repo |
| G8 | the reference is `max(running CLI, registered floor)` |
| G9 | the child's first output line is now printed for every failure, including the bare-return-code path |
| G10 | `--roots` help names both verbs |

**Verification, all at `2026.10.30-25`:** `test_genome` 38/38, `test_package` 8/8,
`test_package_modes` 5/5, `check_ps1` parity ok at 412 lines. The dist artifacts were
**stale** (`dist/*.whl` and `*.tar.gz` carried `-23`) and that alone produced three
failures in the packaging suites until `uv build` refreshed them — a stale artefact, not
a code defect, recorded here so the next run does not re-diagnose it.

Live checks against one repo (`saas/lifeos-bot`, at `2026.10.27-13`):

```
$ genome installs upgrade --roots lifeos-bot          # DRY RUN — writes nothing
dispatch: 1 cop(y/ies) behind 2026.10.30-25 — DRY RUN (--apply performs the upgrade)
swap source: …/project-genome/scripts/genome (2026.10.30-25)
would upgrade  …/saas/lifeos-bot  2026.10.27-13 → 2026.10.30-25

$ genome installs upgrade --roots no-such-repo
genome: no registered install matches no-such-repo (86 registered; …)     # exit 2

$ genome installs unregister project-genome
genome: 'project-genome' matches 4 registered installs — pass one in full: … # exit 2
```

The dispatch did not touch any other repo: the dry run's target list contains exactly
one path, and the manifest still holds 86 rows after the three probe commands above.

## 6. The procedure this now makes possible (not yet performed)

```
# 1. publish, so the four roots and the wheel carry the same bytes as the kernel
install.sh --skill && uv build && python3 scripts/genome installs register skill <root>

# 2. per repo, or per group, always the dry run first
genome installs upgrade --roots <name>              # reads the fix list, writes nothing
genome installs upgrade --roots <name> --apply      # swaps, migrates, prints the fix list

# 3. inside the repo, clear what the list named
genome emit && genome lint --code E --all && genome close

# 4. the fleet-wide run, only once the scoped ones have all gone through step 3
genome installs upgrade --apply
```

Steps 1 and 4 are the operator's call. **No `--apply` has been run on any repo.**

## 7. Two honesty notes

- The "86 registered" in the empty-scope message counts rows, and the "82" figure that
  appears in this audit's state table counts **distinct resolved path names**. Both are
  true and they are not the same number: four `project-genome` rows (the four skill
  roots) and two `holon` rows (the repo and its deleted `holon-personal/holon` twin)
  collapse by name. The dispatch message was deliberately changed from names to rows so
  that it matches `genome installs list`.
- The earlier session summary recorded "11 releases separate `-13` from `-23`". The
  correct count measured from `releases.txt` is **10** (`-14` through `-23`); 11 reaches
  `-24`. Corrected here rather than carried forward.

## Re-measured 2026-10-31, 07:20 — a sixth fix, a new build, and one rule broken on the way

The audit was published inside the same session that wrote it, so the tables above are
the `2026.10.30-25` snapshot. Two moves happened after it, and they are recorded here
rather than by editing the body — a dated-frozen audit that changes under the reader is
worse than one that is stale with the date attached.

| figure | published 2026-10-30 (`-25`) | re-measured 2026-10-31 (`-26`) | what moved |
|---|---|---|---|
| the build | `2026.10.30-25`, 6,970 lines | **`2026.10.30-26`, 6,983 lines** | the sixth fix below, and the ERROR-line remedy from G9 |
| release gap from `-13` | 11 to `-25` | **12 to `-26`** | one more release; and `-24` was minted then withdrawn, so the version enumeration is not contiguous |
| per-copy delta | 802 added / 6 removed | **820 added / 6 removed** | the same `saas/lifeos-bot` copy re-measured against the new build (13 of the extra lines are the G9 remedy) |
| fixes | five | **six** | `installs verify --against-shipped` had the same stale-reference defect as the dispatch |
| suites | `test_genome` 38/38 | **38/38** with one new assertion inside `installs_registry` | the reference-floor property is now asserted, not just claimed |

**The sixth fix is the fifth gap in a second location.** `genome installs verify
--against-shipped` computed `shipped is …` from the registered skill/bin floor and
printed `shipped is 2026.10.30-22` while the running CLI was at `-26` — so the check an
operator reads *before* a rollout named a version nothing on the machine held. It is the
same defect as G8 in the dispatch, which is the useful part of the finding: a reference
resolved from a publish-time snapshot is wrong everywhere it appears, so the fix belongs
to one place (`max(running CLI, registered floor)`) and was applied in both. The
`installs_registry` case now asserts it by making a skills root lag and checking the
reported reference does not follow it down.

**G9's remedy also tightened.** The published fix printed the child's first output line,
which is empty when the child dies silently. It now prints `exit N (no output — run it
directly: <command>)` in that case, because a bare `1` is not a reason.

**One rule was broken while correcting the previous session's entry and the repair is
part of the record.** `docs/kb/WORKLOG.md` is append-only; three lines of the committed
entry were rewritten in place to update the version figures, and `genome doctor` named
it — "append-only violation: 8 line(s) removed from docs/kb/WORKLOG.md in the working
tree". The entry was restored from `e164018` and the corrections were appended as new
dated lines instead. That is the only mutation the form allows, and it is why this
section exists in a dated-frozen audit rather than as edits above: a correction is a new
line with its own timestamp, never a rewrite of the one already published.
