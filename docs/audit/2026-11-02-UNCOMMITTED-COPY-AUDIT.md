# 2026-11-02 — THE UNCOMMITTED COPY: the rung below "what is stale"

**Status:** written 2026-11-02 at VERSION `2026.11.02-43`.
**Scope:** the question the upgrade surface does not ask. `2026-10-31-UNIFIED-UPGRADE-SURFACE-AUDIT.md`
owns "what is stale, take it to current, and what must I fix inside each KB
afterwards". This owns the rung beneath it: **whether the write that landed is one git
will keep.** It does not re-audit the dispatch, the registry's linking surface, or the
post-upgrade validation.
**Method:** measured on this machine at the time written. `genome installs verify
--against-shipped`, `sha256sum <repo>/scripts/genome` per registered row against the
shipped reference with symlinks resolved, `git show HEAD:<path>`, and `git status --short
-- <path>`. Nothing is remembered, and nothing was written into any repo that is not this
one.

## F1 — the estate's own check could not see a regression-in-waiting as a risk

Measured 2026-11-02, before the change, per registered row in
`~/.config/genome/installs.json` (85 rows):

| class | rows | disk | HEAD | `git status` | what `installs verify` said |
|---|---|---|---|---|---|
| current | 11 | shipped | agrees | clean | (current) |
| **uncommitted** | **68** | **shipped** | **older** | **` M`** | **healthy** |
| behind | 3 | older | agrees | clean | BEHIND |
| nofile | 3 | — | — | — | n/a |

**The 68 uncommitted rows are the finding.** The `2026.10.31-40` dispatch to those repos
landed correctly and completely, and nothing committed it. In
`webdev/webdev-portfolio` the uncommitted diff is
`1 file changed, 1639 insertions(+), 16 deletions(-)`, disk `2026.10.31-40`, and
` M scripts/genome`. The copies are **not** gitignored. Every one of those working trees
is one `git restore`, `checkout .`, rebase or `clean -fd` away from a nine-release
rollback, while the estate's own check reported them healthy — because it read the disk
and never asked git.

**A guard that checks a write landed, and nothing that checks it stayed landed, is a
guard that certifies a regression-in-waiting as clean.**

## F2 — and the census that preceded it was wrong twice, from one cause

The 2026-11-01 census recorded "2 reverts" and "75/76 current". Both figures came from
reading the registry's `version` column, which is a **recorded claim, not a
measurement**. Measured against disk:

| row | the claim | the bytes |
|---|---|---|
| `holon` | "reverted to `2026.10.27-13` by external git operations" | **current at `2026.10.31-40`**, uncommitted. Its vendor file was rewritten 2026-11-01 08:49 and never reverted |
| `operant` | absent from the census | genuinely behind at `2026.10.21-2`, committed and clean — the never-upgraded class |
| `pioneer-qf` | a revert | genuinely behind, and a **`kb` row**, not a vendored copy at all — a fourth kind beside vendored/skill/bin |
| 68 rows | "current, green" | current on disk and uncommitted |

So the revert class the tier existed to instrument was **one repo**, not two. Both errors
are the same error: a table written from the registry instead of from `sha256sum` against
the shipped reference.

## F3 — the check that fixes F1, and the rule that keeps it honest

`_uncommitted_cli(repo)` in `src/16b_installs.py`, called for every `vendored` and `bin`
row by `_verify_against_shipped`:

```
UNCOMMITTED vendored <path> — scripts/genome is modified in the working tree
             (M scripts/genome); git can discard it on the next restore/checkout
```

**The exit code is not gated on it, and that is the whole design.** `BEHIND`/`UNKNOWN`/
`CORRUPTED` answer *what the bytes are*; `UNCOMMITTED` answers *what git will let them
stay*. Only the owner knows whether a vendored copy is tracked (commit it) or generated
(gitignore it), and a repo that intentionally gitignores its copy is healthy. Red on this
would punish exactly the right answer. Measured after the change: exit 2 for the estate's
BEHIND rows, exit 0 with none, and **73 rows UNCOMMITTED** printed either way.

## F4 — two blind spots in the first implementation, both caught by running it

1. **An empty pathspec is a git error, not an empty result.** The first
   `git status --short -- "" scripts/genome` exits 128 (`fatal: empty string is not a
   valid pathspec`) and prints nothing, which the code read as "clean". Every repo
   reported clean. The call now asserts its own success before believing its silence.
2. **A symlinked copy is a second blind spot, and `holon` lives in it.**
   `holon/scripts/genome` is a symlink to `holon/vendor/genome.py`. `git status` on the
   **link** is clean while the **target** is the modified file (` M holon/vendor/genome.py`).
   Asking about the link reported holon's uncommitted copy as clean. The path is now
   resolved before asking git, so the row names `vendor/genome.py` — the file git will
   actually discard.

Both are pinned by `p7_uncommitted_copy_is_reported_not_swallowed` in
`scripts/test_genome.py`, along with the one thing that must *not* happen: a
committed-and-clean copy is not reported.

## F5 — what this does not decide, and who does

- **Whether any of the 73 uncommitted rows should be committed or gitignored.** That is
  73 owners' call, and each tree carries its own WIP — holon's +1639 is real work, not
  noise. No tree was touched in producing this audit.
- **Where the check runs.** It exists as a command a person or a job can run. Making it
  scheduled is the vendored-copy convention question (Q1 in `docs/kb/ASKS.md`), not a
  property of the check.
- **Whether "uncommitted" is itself the right shape.** A repo could commit its vendored
  copy, gitignore it, or vendor nothing and use a PATH install. The check reports the
  fact; the convention is a ruling.

## The reproducible measurement

`census.py` under `/var/tmp/ishanp-agentic/` — three questions per registered row
(disk, HEAD, registry claim), symlinks resolved, runs in about a second, **writes
nothing**. It is not in this repo because it is a diagnostic, not part of the CLI: the
CLI's answer is `genome installs verify --against-shipped`, which now asks the git
question the census needed a script to ask.
