# PQ-9 closure — kernel and the four skill roots at 2026.11.02-43

Measured 2026-11-02, at the close of this session's fleet pass. PQ-9's premise was
*kernel ahead of the copies every harness reads*; that premise is now false.

## The measurement

```text
$ python3 scripts/genome --version                  # the kernel repo's own copy
genome 2026.11.02-43

$ python3 ~/.agents/skills/project-genome/scripts/genome --version
genome 2026.11.02-43

$ python3 scripts/genome installs verify --against-shipped
verify: all 89 registered install(s) at the shipped version 2026.11.02-43
(exit 0; 0 BEHIND rows)
```

## Why the roots converged when they did

The installer's shape was already right and did not need building: `~/.agents/skills/project-genome`
holds the **one real copy**, and `.claude`, `.zcode`, `.codex` each hold a *relative* link at it,
computed from the root's depth rather than hardcoded. A hardcoded `../.agents/…` resolves to
`~/.claude/.agents/…`, which is the second broken link the installer's sandbox test caught; that
fix is why a single write at the canonical copy reaches every root.

What was actually stale was the canonical copy itself, at `2026.10.31-40`, plus the global uv
binary at `~/.local/bin/genome` (also `-40`, and the copy this session's earlier outline was
mistakenly read through). Both were brought to `-43`, so all four roots now serve the shipped
bytes.

## The one caveat worth keeping

`installs verify` reads the **disk**, and 72 rows hold the shipped bytes on disk while HEAD holds
an older `scripts/genome`. The roots are among a class that may yet be reverted by a
`git restore`. That is Q1 and the 72 owners' question, not PQ-9's — this file records only that
the *version drift* PQ-9 described is gone.
