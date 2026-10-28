# PRE-UPGRADE IMPLEMENTATION AUDIT — genome 2026.10.28-16

**Status:** dated-frozen audit, 2026-10-28. Read this BEFORE deploying the KB
protocol upgrade (`docs/plans/2026-10-28-KB-MANAGEMENT-PROTOCOL.md` +
`KB-GATE-NUMBERING-ADDENDUM.md`) to any fleet install.
**Scope:** the shipped CLI at this commit, its measurement surface, the gaps
between the operator's KB-management directive and today's code, the bugs found
by live probes, and the installation-registry design that removes the one
recurring fleet failure.
**Method:** source reads + the suite run at tip (37/37) + live scratch-repo
probes + fleet measurements on this machine. Every number below was derived, not
remembered.

## 1. What ships today (measured at this commit)

- **One script, 6,343 lines** built by `scripts/build.py` from 26 `src/NN*.py` modules (`wc -l scripts/genome` at this commit), embedded blueprints included. VERSION `2026.10.28-16`.
- **44 lint/doctor codes in live use** (derived: every `ENNN` token the script
  emits): flats `E001-E006, E008-E010, E013-E017` (E007/E011/E012 unemitted —
  gaps, not free), families `E101-E107, E202-E206, E301-E307, E401, E501-E511`.
  E018/E019/E020 are the first free codes — the addendum's M017/E018/E019
  numbering is consistent with this set.
- **37 self-check cases** (`scripts/test_genome.py`): 36 pre-existing + the
  `installs_registry` case added by this iteration. Suite green 37/37, 0 fail.
- **6 modules**: core, records, research, ops, agents, outline. Claims,
  workflows, register rows, feed, handoff/emit, records, index/graph,
  federation, blueprints, kinds — all real, all covered by cases.
- **install.sh**: clone-or-update into each detected skills root, three install
  states (git checkout / rsync-migrate / fresh clone), PATH wiring to
  `~/.local/bin` and best-effort `/usr/local/bin`, self-check gate, CTA.

## 2. The directive's four requirements vs today's code

The operator's ask has four separable parts. Measured gap for each:

| Requirement | State today | Verdict |
|---|---|---|
| WORKLOG/BUGS/TODO/WORKFLOW manageable via CLI + sqlite with a standardized schema | All four are markdown-file surfaces with CLI management (`genome log`, `status`, `claim`, `done`, `wf new/add/list`, `q`). The `sqlite` store exists ONLY as the `ask --index` BM25 cache (`.genome/index.db`, `18b_index.py`), not as a write-model. | **Gap — the protocol defines `.genome/kb.sqlite` as the write-model; this audit confirms it does not exist.** No sqlite write path, no migration tool, no rendered views. |
| plan/audit mint fails when a new dated file exists without approved disposition of open transients | `genome plan`/`genome audit` mint unconditionally; a hand-written dated plan/audit is INVISIBLE to lint (probe: lint clean on `docs/plans/2026-10-28-*.md` and `docs/audit/*.md` written outside the CLI); the TRANSIENTS register does not exist. | **Gap — this is the protocol's M017/E018 pair; both absent by design (they are the upgrade).** |
| One active WORKFLOW/TODO row per agent | `genome claim` guards PER-ITEM ("claimed by X") but a single agent can hold items in MULTIPLE boards simultaneously — proven by probe: `claim probe-wf-001` and `claim probe-wf2-001` both succeed for the same agent id. | **Gap — E019 absent.** The protocol's `one-active-per-agent` partial-unique index is new machinery. |
| genome CLI first-class + registry so upgrades reach every install | install.sh already installs to PATH (hardened at `0151979` + `82c7211`), but **nothing records WHERE the installs are**: this machine carried two skills roots two commits behind origin and the PATH copy two VERSION stamps behind, silently. | **FIXED by this iteration** — §4. |

## 3. Utilization audit — what is effectively used in the active loop

Utilization measured by corpus citation (the repos that USE genome), not by
unit tests — a command with cases but zero call sites is still under-used.

**Zero citations in the active corpus** (AGENTS.md/README/docs of the adopting
projects — re-derived here, not copied from the earlier audit, whose corpus was
contaminated by `scripts/genome` self-references):

```
set, secrets, resolve, outline, outline-check, modules, index, figure
```

- `resolve` — federated-pointer resolution: real capability, exercised only by
  the suite; no adopting repo invokes it by hand.
- `outline`/`outline-check` — emitted stack-outline zones; cited by the skill's
  own machinery, not by project workflows.
- `set/modules/index/figure/secrets` — capability complete, needs-zero (no
  caller depends on them). Candidates for a "why this exists" README section or
  doc-level discoverability, NOT deletion (they are the integration seams the
  upgrade and federation ride).
- The `figure`+`quarantine` pair is effectively used inside the research
  workflow (W201/E202 fire) but the CLI verbs themselves are uninvoked.

**Redundancies confirmed (ponytail class):** the vendored `scripts/genome`
fork-per-repo convention itself is the largest one — every repo carries a 14k
line copy; drifts measured coparatively: operant's copy now equals shipped
`2026.10.27-13` (0 diff lines after the peer closed it), but the machine's
skills roots sat at `7635877` and PATH at `2026.10.27-11` — three independent
delivery surfaces, zero shared knowledge of each other. The install registry is
the first fix; the protocol's rendered-read-view + migration is the second.

**Not re-verified:** the wider (non-operant) fleet's per-repo drift. Only this
machine was measured; the registry's `installs scan` is designed to make the
next such measurement one command instead of a manual sweep.

## 4. The installation registry (landed in this iteration)

The recurring failure: `genome` lives in N places per machine, upgrades touch
the known ones, stragglers go stale silently — agents run a stale CLI and never
learn why.

- **One manifest**: `~/.config/genome/installs.json` (`GENOME_INSTALLS`
  override), schema 1: `{"schema": 1, "installs": [{"kind":
  "skill|bin|vendored", "path", "version", "registered", "note"}]}`.
- **`genome installs list|verify|register|scan`** (src/16b_installs.py, 175
  lines): `list` prints each install's live VERSION; `verify` reports MISSING
  (path gone) and STALE (on-disk VERSION ≠ recorded) and exits 2; `register`
  idempotently records/replaces by path — recording the path AS GIVEN (a bin
  symlink keeps its link path; `_version_of` reads through dir → `scripts/
  genome` and through symlinks); `scan` probes the conventional skills roots
  and PATH for unregistered installs (HOME-isolated, exits 2 with the list).
- **install.sh registers every install it creates** — skills roots, both PATH
  bins — bootstrap-safe (calls the source clone's `scripts/genome`, no PATH
  dependency) and non-fatal if it cannot.
- **Test**: `installs_registry` — register-dedupe, as-given symlink paths,
  verify-clean, drift detection (bump-under → STALE), missing detection, bad
  kind refused, clean rescan. Green in the 37/37 suite.
- **Upgrade procedure now**: re-run install.sh (updates + re-registers), then
  `genome installs verify`; anything `scan` finds that install.sh does not touch
  (vendored copies in adopting repos) is upgraded with `genome upgrade --apply`.

## 5. Bugs found by live probe (each with repro)

1. **E202 quarantine sweep is opt-in-by-default-off.** `[research]
   quarantine_surfaces` UNWIDENED (the default) protects only
   `research_surfaces` — an AUDIT that re-quotes a quarantined figure passes
   lint. Repro: scratch repo, `[research] surfaces=[…], quarantine="…"`, audit
   quotes the struck figure → clean; adding `quarantine_surfaces=["docs/audit/*"]`
   → `E202 … quotes quarantined figure`. The 64cb8f2 commit widened the sweep
   mechanism; the DEFAULT keeps the RG-040 hole open until each repo sets the
   key. **Pre-upgrade decision for the operator:** flip the default to the wide
   list (every `docs/**` with figures) in the next release, or document
   `quarantine_surfaces` as required in the research blueprint. Recorded here —
   not changed in this iteration (the operator's file for that call).
2. **Registry bugs found and fixed during this iteration by its own live test**
   (recorded as implementation history): version-of registered a skills ROOT as
   `missing` (roots are directories); register RESOLVED a bin symlink into the
   skills root's script, making the manifest describe the wrong install; scan
   reported a link-registered bin as unregistered. All three fixed in
   16b_installs.py and pinned by the case above.
3. **The scan resolution-symmetry bug, found by mutating the shipped fix** — the
   deepest one, and the reason the suite is trustworthy only after mutation
   testing: with three bugs pinned green in the case, reverting the scan
   comparison to the pre-fix form STILL passed. Probing the real scenario
   showed why: a bin LINK whose resolution is a REGISTERED skills root's script
   was re-reported as unregistered (my first `resolved_known` compared the LINK
   path against resolution strings, so it never matched). The comparison must
   resolve `b` too — `b.resolve() not in resolved_known`. The case now carries
   the scenario (root registered, bin unregistered → scan quiet) and the
   mutation fails it. **Lesson for the upgrade implementers: a case that passes
   both before and after a fix is not a case; mutation-test every lint/gate fix.**

## 6. Pre-upgrade blockers for the deployment

1. **Ratify the protocol first** (thresholds, vocabulary, back-fill triage, the
   E017 `--force` escape, vendored-copy deletion) — the addendum's open items.
2. **E202 default decision** (finding 1) — one-line change, operator's call.
3. **The upgrade ordering is fragile on this machine right now** because the peer
   agent's iter-A session work is mid-flight in the shared operant tree — land
   the registry + protocol first, adopt second (per the protocol's own
   sequencing: skill-side, then adoption, then compaction).

## 7. Not covered by this audit

- Non-operant fleet repos' per-repo drift (one machine measured).
- Runtime performance, concurrency, network paths (stdlib single-file CLI).
- The KB sqlite write-model's implementation effort estimate (the protocol
  defines the schema; sizing it is the same iteration as coding it).
- Any file under `docs/plans/` beyond the two proposal docs named above.
