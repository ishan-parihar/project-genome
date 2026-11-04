<!-- living plan: phase rows move; see "Resume here" -->

# Worktrunk integration — parallel agents across git worktrees

Plan: 2026-11-05. Status: **implemented and shipped 2026-11-05 as 2026.11.05-3** (combined with the
source repo's concurrent 2026.11.05-2 line — worklog-body fix, docs-gate gating — after the first
dispatch left the fleet at -1 while the kernel source moved to -2; both loci now hold byte-identical
-3 artifacts, 47/47 cases). Fleet dispatched twice: #1 shipped -1 (60 ok, 18 BROKEN incl. the source
repo's src-vs-build mismatch, 1 guarded skip), #2 shipped -3 (60 ok, 17 BROKEN — all pre-existing
content drift the dispatch's verdict-reading surfaces, none from this delta: e.g. E309
tracked-and-ignored, E001 dead links, E003 register hygiene — 1 guarded skip, holon's uncommitted
local work). PyPI publish is the operator's step per docs/PUBLISHING.md. Two deviations from the
rows below, both smaller than planned: doctor reports a missing `wt` as an info line (only when the
agents module is on) rather than adding a W code; the winget id was pinned to `max-sixty.worktrunk`
and the Windows binary to `git-wt` (verified against upstream README — `wt` is Windows Terminal's
own command).
Upstream: https://github.com/max-sixty/worktrunk (`wt`) — git worktree management for parallel AI
agent workflows: `wt switch -c <branch>`, `wt merge main`, `wt remove`, `.config/wt.toml` hooks,
`.worktreeinclude`, package-managed binary (brew / pacman / winget / cargo).

## Problem

The `agents` module's coordination is correct only while every agent works in one checkout. Worktrunk
gives each parallel agent its own worktree — and that silently breaks every guarantee the module makes:

| failure | where | what happens across worktrees |
|---|---|---|
| claim exclusivity | `Guarded(p)` flock on the board file | each worktree has its own copy of `docs/kb/workflows/<wf>.md` — a different inode, so two agents both claim `x-001` and both exit 0 |
| feed id uniqueness | `max(ids)+1` over the feed | each worktree mints the same `F0007`; after merge the ids collide |
| mention tracking | `.genome/seen-<id>` under `cfg.root` | per-worktree marks: every wake in a new worktree re-shows the whole inbox |

## Design: the main worktree is the coordination home

One rule fixes all three failures — **inside a linked worktree, the agents module's mutable state
(boards, feed, seen marks) resolves to the main worktree's paths.** flock then guards one real inode,
feed ids are minted once, the seen mark is one file. Boards and the feed stay git-tracked (the law:
"the feed is a file in git") — they are committed from the main worktree at `close`, exactly the way
the register already is. Code flows through `wt merge`; record flow flows through `genome close` in main.

Detection: `.git` is a file and `git rev-parse --git-common-dir` names a dir other than this checkout's
`.git` → main root = first entry of `git worktree list --porcelain`. ~15 lines, one helper, used by
`_wf_path` / `_board_of` / `_post` / `cmd_feed` and wake's inbox block. A linked worktree carries a
tracked `genome.toml`, so every other genome command already works there unchanged.

## Phases

| # | phase | loci | done when |
|---|---|---|---|
| P1 | ✅ 2026-11-05 coordination-home helper + agents commands | `src/02_config.py` (`Cfg.coord_root`/`Cfg.coord`), `src/17_agents_commands.py`, `src/10_doctor.py` (live-claims read the coordination home) | `worktree_coordination` case: second claim of one item exits 2 from another worktree, feed ids continue the home's sequence |
| P2 | ✅ 2026-11-05 wake worktree awareness | `src/11_wake.py` | wake in a worktree prints the `coordination:` line; seen marks resolve to main; the inbox reads the home's feed even before its first commit |
| P3 | ✅ 2026-11-05 AGENTS.md worktrunk block + wt hooks | `src/13_init.py` (`wt_hooks`), `src/18_templates.py`, `src/00_head.py` (+shutil) | init writes the block whenever the agents module scaffolds AGENTS.md (new repos and adoption), and `.config/wt.toml` only when `wt` is on PATH and the file is absent; `worktrunk_init` case proves both |
| P4 | ✅ 2026-11-05 protocol reference | `references/agents.md` | the worktrunk section owns the rules: the loop, identity, commit-from-main, hooks, lifecycle |
| P5 | ✅ 2026-11-05 lifecycle: installer + doctor | `install.sh` (`--with-worktrunk`), `install.ps1` (`-Worktrunk`), `scripts/check_ps1.py` (3 parity guards), `src/10_doctor.py` | opt-in on both platforms, package-manager delegation only, cargo fallback one-liner identical; doctor names the manager's one-liner when wt is missing |
| P6 | ✅ 2026-11-05 release + fleet | VERSION → 2026.11.05-1, then reconciled to **2026.11.05-3** in both loci; `scripts/build.py`, `scripts/releases.txt`, two `installs upgrade --apply` dispatches | gate green (47/47, 8/8 package, 5/5 modes, 11/11 docs, ps1 parity), byte-identical artifacts, fleet at -3; the 17 BROKEN members carry pre-existing content drift, listed in the header above |

Resume here: nothing — implemented; the open items are the operator's (PyPI publish, fleet dispatch).

## The AGENTS.md block (P3 content)

```bash
export GENOME_AGENT_ID=<agent id>   # identity for claims/feed — one agent = one worktree
wt switch -c <branch>               # your isolated checkout
genome wake                         # orientation + inbox — works inside a worktree
genome claim <item>                 # flock-guarded across ALL worktrees of this repo
# … work …
genome done <item> done --evidence <path>
wt merge main                       # squash, rebase, merge, cleanup
```

## wt hooks written by init (P3 content)

```toml
# .config/wt.toml — run by wt on worktree start / before merge
[pre-start]
genome = "genome wake"

[pre-merge]
genome = "genome lint"
```

The hook assumes `genome` is on PATH (the installers put it there); a vendored-only repo edits one
line to `python3 scripts/genome …`. Project-level wt commands need approval on first run — expected.

## Lifecycle ownership (P5)

worktrunk is a package-managed binary; `references/installer.md`'s rule decides the shape —
"for package-managed installs delegate to the manager and never overwrite files owned by pipx, npm,
Cargo, Homebrew, winget or a distro package":

| stage | owner | how |
|---|---|---|
| install | `install.sh --with-worktrunk` / `.ps1` | brew (macOS) / pacman (Arch) / winget (Windows) / cargo fallback; never `curl \| sudo bash`; off by default, `SKIP_WORKTRUNK=1` skips |
| check | `genome doctor` | `wt --version`; missing → W-level line + the one-liner for the detected manager |
| update | the package manager | doctor prints the manager name; project-genome never ships a wt updater |
| configure | `genome init` | the `.config/wt.toml` hooks above; shell integration (`wt config shell install`) stays the agent's own choice, documented in the reference |
| remove | the package manager | nothing project-genome writes depends on wt — hooks were written only when it was present |

## Not doing (deliberate)

- No `genome wt` wrapper subcommand — agents run `wt` directly; genome coordinates, it does not orchestrate.
- No new lint codes; the claim-cell grammar is unchanged (`claimed-by \`agent\` since ts`; agent id ↔ worktree is a convention, not a field).
- No generated AGENTS.md zone / outline-check gating for the block — `references/agents.md` owns the protocol; AGENTS.md routes to it.
- No `.worktreeinclude` template, no `-x` agent-spawning integration, no `wt list --full` coupling — the harness spawns agents, not genome.
- No wt auto-update mechanism — the installer rule already forbids competing with package managers.

## Risks

- Arch `pacman -S worktrunk` needs root: the installer attempts sudo in a TTY or prints the exact command; `SKIP_WORKTRUNK=1` skips.
- Boards/feed edits land uncommitted in the main worktree; until someone commits from main, a fresh worktree reads a stale feed. The commit-from-main convention is in P4; `wt merge` never touches those files.
- `.config/wt.toml` hook keys verified against worktrunk.dev/hook on 2026-11-05 (`pre-start` / `pre-merge`; project commands need first-run approval) — re-verify at implementation; wt moves fast.
