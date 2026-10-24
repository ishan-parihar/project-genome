# records.md — decisions (AD) and regressions (RG)

Contents: what a record is · modes · lifecycle commands · file format · the ID map · consolidation · checks

## What a record is

- **An AD (decision)** says why X is the way it is. It is a law an agent can apply without asking.
- **An RG (regression)** is a bite plus the law that prevents it: symptom, root cause, law, detection.

Records are cited forever (in code, docs and worklogs), so an ID never changes meaning and is never reused.

Records are few and topical. A project with 90 RGs for 15 topics has a ledger, not a law. When topics converge,
records merge into one owner whose clauses carry their source IDs (below).

## Modes (`[records] mode`)

| Mode | A correction is | Use when |
|---|---|---|
| `immutable` (default) | a new record that supersedes the old one by name | decisions are rare and external readers cite them verbatim |
| `amendable` | a dated `## Amendment YYYY-MM-DD — title` section plus a Revisions line, via `rec amend` | the law evolves weekly under operator feedback and fragmentation is the bigger risk (R&D programs) |

Either way, the history is in the file (amendments, Revisions) and in git, never lost.

## Lifecycle

```bash
genome rec recon cache eviction ttl          # records + owner sections on the topic; prints a token
# → if an owner covers it: amend it (amendable) or write the lesson into it; stop.
genome rec new rg "TTL drift under clock skew" --recon R1017093011 \
    --orthogonal "no record covers clock-dependent expiry; AD-004 is about cache keys" \
    --description "Expiry uses monotonic time; wall-clock TTLs drift under skew" --severity High
genome rec amend PQF-AD-021 --title "growth-first ruling" --reason "operator 2026-10-15" \
    --body-file /tmp/amend.md --set Description="…"
genome rec supersede PQF-RG-091 --by PQF-RG-025 --reason "topic converged"
genome rec merge PQF-RG-036 PQF-RG-037 --into PQF-RG-061 --reason "one money-path owner"
genome rec retire PQF-AD-013 --reason "mechanism removed"
genome rec show PQF-RG-091                    # resolves a retired ID to its owner
genome rec list [--all] · genome rec emit
```

**Why recon gates `new`.** The common failure is a new record for a lesson an existing owner already covers.
That is how 20 ADs grow for 7 topics. The recon token (valid `records.recon_hours`, 6 h) proves the agent looked,
and `--orthogonal` writes the justification into the record's `## Orthogonality` section, where a reviewer can
check it.

Recon tokens are kept per topic, so parallel `rec recon` runs do not clobber each other. `rec new` numbers after
the highest ID ever cited, even one with no record file, and prints a note when it skips ahead (a typo'd citation spends a number).

## File format

```markdown
---
ID: "PQF-RG-040"
Title: "Knowledge-base integrity: …"
Status: "Active"            # Active | Superseded | Retired
Date: "2026-10-12"
Description: "One line; the emitted index shows it."
Severity: "High"            # RG only
SupersededBy: "PQF-RG-025"  # set by supersede/merge
---

# PQF-RG-040: Knowledge-base integrity: …
## Symptom · ## Root cause · ## Law · ## Detection      (AD: ## Context · ## Decision · ## Consequences)
## Orthogonality
## Amendment 2026-10-15 — …                              (amendable mode)
## Revisions
- 2026-10-15: <reason> [Updated: Field=Value]
```

IDs are `<prefix>-AD-NNN` / `<prefix>-RG-NNN` (`records.prefix`, `records.width`). The next number is computed
over active records, archived records and the ID map, so a number is never reused. Records without frontmatter
(an older `# AD-003: title` style) are read too. The first mutation adds frontmatter.

## The ID map and the emitted index

`supersede`, `merge` and `retire` do three things:
- move the record to the records archive (`records.archive`, default `<archive>/records/`), with
  `Status` / `SupersededBy` set and a Revisions line;
- append "absorbed X" to the owner's Revisions;
- re-emit the zones.

They also list the live files still citing the old ID. Those citations keep working, because:
- the `idmap` zone maps every retired ID to its owner;
- `rec show <old>` says where to read.

Relink citations when you next touch those files; there is no need to churn every file at once.

The zones go where `records.zones` says: a map `{file = [zone names]}`, by default the records index with
`records` and `idmap`. A repo that keeps the index in its agent contract can emit `records` there and `idmap` into
a doctrine doc. Zone names: `records` (both tables), `decisions`, `regressions` (with a Severity column when the
records carry one) and `idmap`. A placeholder line `<!-- genome:zone NAME -->` places a zone under its heading.

The ID map follows `SupersededBy` (or arch's `Superseded-By`) through retired records to the live owner, so an ID
retired twice reads `PQF-AD-024 (via PQF-AD-012)`. A successor may carry a clause (`PQF-AD-021 §11.1`).

**Governance map** (`records.governed_by = "<doctrine>.md"`): every active record must be named in that file outside
its generated zones, so a topic → governing-record row exists for it (E107). A generated table naming every record
proves nothing, which is why zones do not count.

**Frontmatter contract** (`records.required = { AD = [...], RG = [...] }`): required fields on active records;
on every record the `ID` matches the file name, `Date` is `YYYY-MM-DD` (or `unrecorded`), `Severity` is one of
Critical / High / Medium / Low (E105). A record's `Supersedes` names a retired record, never an active one (E106).

## Consolidation (when topics converge)

1. `rec recon <topic>` lists every record on the topic.
2. Pick the owner. Fold each source's surviving clauses into it, each carrying its source ID ("clause 6 (ex-RG-067):
   …"), through `rec amend`.
3. Run `rec merge <sources…> --into <owner> --reason "…"`.
4. Keep a short topic → governing-record table above the zones (hand-written; it is judgement). The generated
   tables stay generated.

## Checks

| Code | Meaning |
|---|---|
| E101 | a record has no title |
| E102 | an ID is used twice |
| E103 | a Superseded / Retired record is still in an active dir |
| E104 | an emitted zone is stale or absent (`rec emit`) |
| W105 | a record cites an ID that neither an active record nor the ID map knows |
| E105 | frontmatter: ID ≠ file name, a required field missing, a bad Date or Severity |
| E106 | `Supersedes` names an unknown record, or one that is still active |
| E107 | an active record is named by no row of `records.governed_by` (outside generated zones) |
