# UNIFIED UPGRADE SURFACE — the measured gaps, and the one verb that closes them

**Status:** written 2026-10-31 at VERSION `2026.10.30-29` (6,983 lines, 27 `src/` modules).
**Scope:** the three surfaces that answer "what is stale, take it to current, and what must
I fix inside each KB afterwards" — the installed package, the registry as a linking
surface, and the post-upgrade validation. It does not re-audit the dispatch itself (that
is `2026-10-30-UPGRADE-MECHANISM-AUDIT.md`).
**Method:** every claim below was measured on this machine at the time written: the
installed uv-tool package read directly, `installs verify/list/scan/upgrade`, `kb
list`/`kb lint --all`, and a disk sweep reconciled against the registry. Nothing is
remembered.
**The operator's ask, verbatim:** *a unified surface area from where we can link all our
kbs and upgrade it effectively, rather than manual search and upgrade of each kb*.

## 1. What the machine looks like today (measured)

| fact | measurement |
|---|---|
| the installed package on PATH | `~/.local/bin/genome` → uv tool `project-genome`, `site-packages/project_genome/_genome.py` at **`2026.10.30-23`** — six releases behind the kernel |
| every harness skills root | `~/.agents`, `~/.claude`, `~/.zcode`, `~/.codex` all at **`2026.10.30-22`** |
| the kernel repo | `2026.10.31-34`, and it is the only checkout that is current |
| the fleet | 76 vendored copies across 76 repos; 74 at `2026.10.27-13`, `operant` `2026.10.21-2`, `artificial-route` `2026.10.22-17`, `saas/lifeos-bot` `2026.10.30-29` |
| registry coverage | **complete** after this session: a disk sweep finds 78 `scripts/genome` repos and 80 `genome.toml` KBs. **The kernel was the one exception — it was not registered, so no manifest reader could see the newest copy on the machine. It is registered now, and 4 ghost rows (holon-personal and its nested holon, discord-cli, tg-cli — directories that no longer exist) are gone.** |
| registry reach | `installs upgrade` dry run names **76 targets** and can reach `bin/genome` repos (`pioneer-qf`) as well as `scripts/genome` ones |
| `kb list` | 77 KBs, **name + path + kind only — no version, so it cannot answer "what is stale"** |
| `kb lint --all` | 77 KBs, 0 errors, 100 warnings, 1 with no CLI — and it printed **at most 3 findings per KB with no remedy** |

## 2. The gaps, in the order an operator hits them

**G-A — the installed package reports itself as current while six releases behind.**
`genome --version` from a neutral cwd prints `genome 2026.10.30-23`; `genome upgrade`
inside any KB prints *"up to date — installed as a package, so there is nothing to compare
against; reinstall to move versions"* and exits 0. The sentence is honest about the
mechanism and false as a status: the operator cannot learn a release exists. `doctor`
reports nothing either. This is the same lie the empty-registry gate and the
`skill_copy()` probe were built to stop, arriving through the install mode that a plain
`pip install`/`uv tool install` produces.

**G-B — the installed package is `?` to the registry, so no aggregate sees it.**
`installs verify --against-shipped` prints `BEHIND bin ~/.local/bin/genome — ?, shipped is
2026.10.30-29`: the count is right, the version is not, because `_script_of()` resolves the
bin symlink to `<env>/bin/genome`, a console-script stub with no `VERSION` line. The real
CLI is at `<env>/lib/python*/site-packages/project_genome/_genome.py`. `_repo_cli()` knows
about `bin/genome` inside a repo, but `_script_of()` does not know about a *package* bin.

**G-C — `kb list` cannot be the linking surface because it carries no version.**
The operator wants one place that links every KB and shows what needs work. A list of 79
names and paths answers "where are they" and cannot answer "which are behind", which is
the question that starts every upgrade.

**G-D — the post-upgrade findings are still capped and remedy-less across the fleet.**
`kb lint --all` shows ≤3 findings per KB and no `remedies:` line, so 100 fleet warnings
appear as 11 rows of counts. Inside one KB the new `_post_upgrade_findings()` prints a
numbered list with remedies; across the estate that machinery is bypassed — `kb_lint_one()`
takes `findings[:3]` and prints them raw.

**G-E — the three pieces of one job live in three commands with three geometries.**
"What is stale" is `installs verify --against-shipped` (a flat name/version/delta list, no
label). "Take it current" is `installs upgrade [--roots] [--apply]` (same list, a different
verb). "What must I fix" is `kb lint --all` (rows keyed by label, no versions). The label
KBs answer to (`kali-mahabali`) is produced by `_kb_label()` and used by `kb` only, so an
operator must mentally join three outputs by path to act on one KB.

## 3. What the fix is, and why it is these five things

The jobs are already in the codebase and already correct for one repo; the gaps are that
each of them stops at a boundary — the package boundary, the estate boundary, the
aggregation boundary. So the fix is to stop the boundary, not to write new machinery:

1. **`_script_of()` learns the package layout** (`bin` stub → sibling `lib/python*/
   site-packages/*/_genome.py`). That single change makes the registry, `installs list`,
   `installs verify` and every aggregate read the installed package's real version, and it
   needs no new command.
2. **`doctor` reports the installed package when it is behind the running CLI.** The
   kernel repo compares against its own working tree (correct: the kernel is the source);
   every other repo compares against the newest skill root. The gap is the *package*, which
   is neither. One condition, one finding.
3. **`kb list` gains a version column** from the same `_version_of()` the registry uses, so
   the linking surface answers "which are behind" in the same glance it answers "where are
   they".
4. **`kb lint --all` prints every finding with its remedy, grouped by code**, and keeps the
   per-KB total: `kb_lint_one()` already receives the JSON, so this is a presentation
   change plus the shared remedy table `_post_upgrade_findings()` already uses.
5. **One verb that joins them: `genome fleet`** — `list` (every KB, version, behind-or-not),
   `upgrade [--roots] [--apply]` (the dispatch, already scoped and already dry-run-first),
   `lint [--all]` (every KB's findings with remedies). `genome kb list` keeps working; the
   new verb is the surface a human or agent starts from, and it reuses every mechanism
   above rather than growing a second owner for any question.

## 4. What shipped (VERSION `2026.10.31-34`, this session)

Five changes, all in the existing mechanisms, no new machinery:

| gap | fix | proof |
|---|---|---|
| G-B | `_script_of()` probes the environment beside a VERSION-less bin: `<env>/lib/python*/site-packages/*/_genome.py`. A bin that already carries VERSION (pioneer-qf's vendored copy) is returned untouched | the registry's bin row read `?` on the host and reads `2026.10.30-23` now; `installs verify --against-shipped` went from "81 behind, **1 unknown**" to "81 behind, **0 unknown**"; a scratch revert makes the new assertion fail with `version: '?'` |
| G-A | `genome upgrade` measures an installed package against what it would converge on (the skills roots AND the kernel checkout), **before** `find_cfg()`, and names the reinstall command | the `-23` package, run from a neutral cwd, prints `BEHIND — this machine is at 2026.10.31-34` where it previously printed "up to date"; the ordering fix matters because from a neutral cwd the old code died in `find_cfg` before any staleness check ran |
| G-C | `kb list` carries a version column and marks each row `behind <ref>` | `kb list` on the host ends `77 knowledge base(s) registered, 76 behind the current release` |
| G-D | `kb_lint_one()` returns every finding (was `[:3]`), the printer emits each code, and `_remedies_for()` — now the ONE owner of the code→command table, shared with `_post_upgrade_findings()` — prints the remedies and which KBs carry each code | `fleet lint` on the host: 100 warnings in 9 codes, all printed, then a `remedies:` line naming 9 fixes and a `W0xx in N KB(s)` line per code |
| G-E | `genome fleet` — `list` (behind / current / sources / no-local-CLI, grouped by what the operator does), `upgrade [--roots] [--apply]` (the existing dispatcher, already dry-run-first), `lint [names...]` (the existing per-KB printer) | `genome fleet` alone answers "which are behind" with a label, a version, and a count |

**Two things found while doing it, both recorded in place:** the kernel was the
one genomic project the manifest did not know, so no reader could see the
newest copy on the machine — it is registered now, as `vendored` with a note
saying it is the source; and four **ghost rows** (holon-personal and its nested
holon, discord-cli, tg-cli — all directories that no longer exist) inflated
every count and appeared in `fleet` as "no local CLI" until unregistered.

**A defect in the fix itself, caught by its own test:** the first remedy table
knew only the E codes, and the estate carries 100 warnings in nine W codes, so
the first `fleet lint` printed no remedies at all. That is the same failure
shape as the finding cap — the answer withheld by the caller — and the table now
covers the codes the machine actually produces, each entry taken from the remedy
its own lint text already names.

## 5. Deliberately not done

- **No fleet-wide `--apply`.** The registry and dispatch are proven; the pass is the
  operator's call under the standing ruling.
- **No second registry.** Coverage is already complete; a second index would violate rule 1.
- **No change to how a repo's own `upgrade` compares itself.** That logic is settled in
  `2026-10-30-UPGRADE-MECHANISM-AUDIT.md` and is not reopened here.
