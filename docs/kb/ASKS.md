# Operator questions and rulings

`genome q add "<question>"` · `genome q rule Q1 "<ruling>" --applied <owner path>`.
A ruling is done only when its owner doc or record carries it.

| id | asked | status | question | ruling | applied |
|---|---|---|---|---|---|
| Q1 | 2026-11-01 | open | The vendored-copy convention's cost, now measured rather than assumed: the estate's `2026.10.31-40` dispatch landed in **73 of 85 registered rows and none of them committed it** (` M scripts/genome`, disk at the shipped bytes, an older copy at HEAD), so every one of those working trees is one `git restore` / `checkout .` / `clean -fd` away from a nine-release rollback — and `installs verify --against-shipped` reported all of them healthy because it read the disk and never asked git. The revert class it was written for is **one repo** (`pioneer-qf`), not two: the 2026-11-01 census read the registry's `version` column, which is a recorded claim, and mislabelled `holon` while omitting `operant` entirely. Do we (1) keep vendoring and make `installs verify --against-shipped` — which now reports `UNCOMMITTED` — a scheduled check, (2) keep vendoring but record each repo's ownership intent in the manifest note so a writer knows before it touches a copy, or (3) migrate the vendored copies to PATH installs? Option 3 is the protocol's ratification item 5 and removes the revert class entirely, and **one owner has already consented to it in writing** (operant's 2026-10-28 worklog calls its own copy *fork-without-intent*, 485 diff lines, and asks for the PATH install, which already works). Either way, the 73 uncommitted rows are the more urgent question and this is not one ruling but 73: each owner decides whether their copy is tracked or generated. Evidence: `docs/audit/2026-11-02-UNCOMMITTED-COPY-AUDIT.md`. | — | — |

**Recorded 2026-10-30 — none logged by this seat, deliberately.** The one question this
session would naturally raise is *"should the 75-repo CLI upgrade run now?"*, and it is
not asked here: it is already PQ-1 in `TODO.md` with the measurement attached, and it is
the operator's pass to schedule. Asking it in this file as well would create a second
owner for a question `TODO.md` already owns (rule 1). W014 is the code for a record-only
entry, so this paragraph is the record, not an ask.
