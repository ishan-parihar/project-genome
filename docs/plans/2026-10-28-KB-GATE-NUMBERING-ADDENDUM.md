# KB PROTOCOL GATE NUMBERING — ADDENDUM TO THE 2026-10-28 PROPOSAL

**Status:** correction-of-record addendum. The proposal above
(`2026-10-28-KB-MANAGEMENT-PROTOCOL.md`) is dated-frozen and stays as
written; this file is the numbering correction an implementer MUST read
before coding the gates. The correction of record in the operant repo is
feed entry **F0119** (2026-10-28T05:03, `docs/kb/feed.md`), restated here
because THIS repo has no feed surface, and its second-pass record is
operant feed **F0124** (2026-10-28T06:50).

**Author:** the operant KB-management session, 2026-10-28.
**Applies to:** the same scope as the proposal — every project under
genome management that opts into the `kb` module.

## The two defects this addendum corrects

The proposal, as frozen, names its three new checks **M017** (mint-time
admission gate), **E017** (lint-time detection of an unregistered dated
plan/audit), and **E018** (one-active-per-agent at lint). Two problems:

1. **E017 is a live code.** In the shipped script, E017 is the unknown
   `genome.toml` key check (the typo guard), E016 is the size-budget
   check, E015 is the worklog-index zone check. Reusing E017 for a new
   lint would make one number mean two different failures depending on
   script version.
2. **Cross-repo collision.** The operant-side v2 plan
   (`docs/plans/2026-10-28-kb-management-protocol-v2-sqlite-state-gates-one-active-per-.md`
   in the operant repo) names its admission gate E017 as well — same
   number, different gate, depending on which document an implementer
   reads.

## Authoritative numbering (derived, not picked)

Derived from the shipped script's live code set at local commit
`64cb8f2` (maximum live flat code E017; E1xx/E2xx/E3xx/E401/E5xx
families in live use; no M-codes exist anywhere):

| Gate | Authoritative number | Meaning |
|---|---|---|
| Mint-time admission gate | **M017** | `genome plan` / `genome audit` refuse to mint when an open transient row lacks an approved disposition, or when the minting agent already holds an active workflow/todo row |
| Lint-time detection lint | **E018** | an unregistered dated plan/audit on disk fails lint until it has a `kind='transient'` row (or is approved) |
| One-active-per-agent | **E019** | more than one active workflow/todo row per agent fails lint |

**M017 is safe** because m-codes are a brand-new namespace — no M-code
exists in the shipped script, so the mint gate takes the proposal's number
unchanged. **E018/E019 are safe** because they sit above the live maximum
flat code (E017). Note the live set has three gaps below the maximum —
E007, E011, E012 are not emitted by the current script — but the gaps are
NOT taken: they may carry retired meanings in older fleet copies, and a
new gate never reuses a number with history it did not derive.

The frontier is cheap to re-derive before coding: list every E-code the
shipped script emits (`grep -oE 'E[0-9]{3}' scripts/genome | sort -u`),
and the first flat code above the live maximum is free.

## What the implementer does with this

- Read F0119 (operant `docs/kb/feed.md`) and this addendum BEFORE coding
  the gates; the frozen proposal's M017/E017/E018 labels are superseded
  by M017/E018/E019.
- The skill-level proposal's OWN body otherwise stands: SQLite
  write-model, rendered markdown read-view, the partial UNIQUE index for
  one-active-per-agent, `compact kb`, the detection lint's semantics.
- If a future genome version consumes E018/E019 before this protocol
  lands, shift to the next free flat codes and record the shift here the
  same way.
