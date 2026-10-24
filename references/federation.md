# Federation, drift and upgrade

Contents: the card · `federate` · `ask --all` and `repo:` pointers · covers / verified drift · the status zone ·
privacy · upgrading a vendored CLI.

Each repo keeps its own genome. The meta root points and never copies, and nothing here writes into a peer repo.

## The card

`genome card` writes `<cache>/<repo>.json`: name, purpose, genome version and HEAD, the doc classes
(`intent architecture operate decisions status`) with paths and headings, the routing table, open register items
(id and status), record titles, kind counts, manuals with their `covers` / `verified` state, and lint counts. Built
from the working tree, never from git history. Over 24 KB, or holding a secret-shaped string or a configured
secret value, it is refused (exit 2). `--stdout` prints it instead.

Cache: `$GENOME_CARDS`, else `[federation] cache`, else `~/.cache/genome/cards`.

Map the classes in `genome.toml` where the defaults (README, runbook, records index, state doc) are wrong:

```toml
[card]
architecture = "docs/ARCHITECTURE.md"
purpose = "One line; otherwise taken from AGENTS.md 'What this project is'."
components = ["crates/*", "packages/*"]    # directories listed in the card
privacy = "internal"                       # "private" = card in the cache but not in the portfolio zone; "local" = no card at all
status_into = "README.md#status"           # a generated zone of register counts and open items
```

## At the meta root

```toml
[federation]
repos = ["*", "*/*"]                       # directory globs; a member has its own genome.toml
status_into = "docs/PORTFOLIO.md#portfolio"
```

`genome federate` builds every member's card in-process (reading each tree, writing none), skips privacy-local
repos and refused cards with the reason, prunes the cards of repos whose directory is gone, and refreshes the
portfolio zone.
`genome ask --all "<question>"` scores the cards and answers with pointers
`repo:<name>#<class>` plus the path and line. `genome resolve repo:<name>#<class>` prints the file.

**A question that names a doc class is answered with that class's document.** "how is it built" and "architecture"
answer with `#architecture`, "why was it decided" with `#decisions`, "where does it stand" with `#status`,
"how do I run it" with `#operate`, "what is this" with `#intent`. The reason is that a routing row's own question
text ("where does the project stand right now") matches a natural-language question better than a class heading
does, so term coverage alone answered with the routing table instead of the document the card points at. A
question that names no class is scored exactly as before, and the repo's own name still outranks a mention of it
in another repo's purpose.

## Drift: is the manual still true of the code?

A manual declares what it describes and when someone last checked:

```yaml
---
covers: "src/engine/**, crates/pump/**"
verified: 3fa91c2
---
```

Lint reports `W401` when `git diff --name-only <verified>..HEAD -- <covers>` is non-empty; `W402` covers without a
`verified`; `W403` the sha is not in history; `W404` covers matches no tracked file. `[drift] mode = "error"` turns
W401 into E401 (do that after the first 30 days). `[drift] paths` limits which docs are scanned (default README,
AGENTS and docs/**).

`genome verify <doc> --reviewed [--covers '…'] [--sha X]` records the current HEAD as `verified`. It is the
reviewer's act: run it after reading the manual against the covered code. `--reviewed` is required so it cannot be
run by reflex. Never auto-edit manual prose; draft a diff and let the owner accept it.

## Privacy

`privacy = "local"` keeps a genome out of cards, `federate` and `ask --all`. Use it for subjective or personal
knowledge bases, and keep such a repo without a remote.

## Upgrading a vendored copy

- The first move off a copy that has no `genome upgrade` is the `cp` that `genome doctor` prints, then
  `genome migrate`.
- After that, `genome upgrade` shows the version change and line counts; `--apply` swaps the file in, keeps
  `.genome/genome.pre-upgrade`, and runs `migrate` (it stamps `[genome] schema_version`).
- `scripts/releases.txt` holds each release's checksum. A copy whose checksum does not match its version carries a
  local patch: `upgrade --apply` refuses until you pass `--accept-patch-loss`, which saves the difference to
  `.genome/local-patch.diff`. Put template changes in `.genome/overrides/` and other fixes in the skill.
- `GENOME_SKILL` points at a different skill copy.
