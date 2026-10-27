# KB OUTLINE — the standard kickstart outline for a knowledge base

**Status:** **implemented.** `src/04a_outline.py` ships the `outline` module: `genome
outline` emits the zone, `genome outline-check` gates it, and `genome close` refreshes
it. This document is the proposal it was built from; its three open questions are now
settled by the implementation — `outline` is the sixth module (not six more files in
`core`), the zone lives in `AGENTS.md`, and the check gates from the start. Committed in
`854f847`; `meme-lyr` is the first KB running it (`105d430`).
**Author:** the docs-library session, 2026-10-27.
**Applies to:** every venture under the meta-directory that carries a `genome.toml`.

---

## The problem this solves

A knowledge base under `genome` starts as a complete skeleton: `genome init` writes
`AGENTS.md`, the routing table, the register, the handoff, the ledger, the worklog,
the asks, the runbook and the archive index. It is a *records* skeleton, not a
*description* skeleton. Nothing in it answers the four questions an arriving agent
needs before it can act:

1. **What is this, structurally?** Not the marketing one-liner in `README.md` — the
   language, the layout, the entry point, the dependency set.
2. **How big is it?** Which number, out of which command, at which commit.
3. **How does it work?** The component map and the one rule that shapes the rest.
4. **What do I read next, in order?** The reading order into `docs/`.

Verified instance of the gap, this session: `agentic-utility/content-creation/meme-lyr`
is a fully genome-managed repository — `genome.toml` with schema_version 2, modules
`core` + `agents` + `records`, the whole document set present and linted — and a grep
across its entire `docs/` tree and its README for `architecture`, `stack` or `wiring`
returns **nothing**. It has an entry contract and no description. `src` is one file,
`src/index.ts`, so its architecture is small but real, and still unwritten.

The same shape holds across the KBs. This is not a documentation-drive problem, it is
a missing *artefact* problem: the answer to those four questions is derivable from the
repository, so it should be generated and then kept honest, rather than written by
hand once and left to drift.

---

## The principle, stated before the schema

**Generated, then owned.** The outline is produced by a script from what is already
true — the file tree, the manifests, the git state — and it lands inside a generated
zone so that re-running the script refreshes the facts and cannot touch the prose
around them.

This is the same contract `genome rec emit` already keeps for the records index and
`genome emit` keeps for the worklog, and it is deliberately not a new mechanism:
`write_zone` in `src/04_zones.py` replaces the body between
`<!-- genome:zone <name> sha=… -->` and `<!-- genome:end <name> -->`, and the lint rule
E006 fails a zone that was hand-edited. So a stale outline fails the gate rather than
quietly lying, which is the property every other zone on this system already has.

**Two files, one of each kind.** Facts go in the zone, inside `AGENTS.md`.
Interpretation goes in a hand-owned document it links to. The split matters because a
generated file cannot make a judgement and a hand-written file cannot be refreshed, and
the failure mode of merging them is a document nobody trusts.

---

## The schema

Two artefact kinds. Neither is optional, and the KB does not ship a partial outline.

### 1. `AGENTS.md`, gaining one generated zone: `stack`

Placed immediately after the `## Gate` section, because that is where an agent has just
learned how to check the thing and has not yet been told what the thing is. Registered
in `genome.toml` like the records zones are, so it is a declared part of the contract
rather than a side effect:

```toml
[outline]
zones = { "AGENTS.md" = ["stack"] }
```

The zone renders five tables. **Every row is derived; nothing is asserted.**

| Table | Rows | Source |
|---|---|---|
| `Language and layout` | language, source dir(s), entry point, test dir, manifest | file probes |
| `Size` | files by type, LOC by language | `cloc`-equivalent over the source tree |
| `Gate` | the command that must pass, as `genome` already records it | `genome.toml` `[genome]` or the `gate` probe |
| `Dependencies` | direct dependencies, split first-party / third-party | the manifest, resolved against the monorepo |
| `Wiring` | which component calls which, one row per edge | import graph over the source tree |

The `Wiring` table is the one that earns the schema. It is what a reader cannot get by
looking, and it is derivable, so it belongs in the generated half.

### 2. `docs/OUTLINE.md`, hand-written, linked from the zone

The zone's last line is always:

```
Read `docs/OUTLINE.md` for how these parts fit together, and the order to read them in.
```

`docs/OUTLINE.md` is a normal document with a normal mutability class: no zone, nothing
generated, written once by whoever knows the system and amended after `genome close`
when a decision changes it. Its required headings are the four questions:

```markdown
# Outline — <name>

One paragraph: what this is, who it is for, and the one thing it must never do.

## The shape            a Mermaid diagram and a component table
## The one rule         the single constraint that shapes everything else
## How the parts wire   the import graph in prose, with the rule each edge encodes
## How to check it      the gate command and what green means
## Reading order        the documents to read next, in order
```

`How to check it` and `Reading order` are required because they are what makes the
outline evidence rather than claim, and what makes a document the entry point of a
library rather than a page in it. This is the template `holon/docs/ARCHITECTURE.md`
already exemplifies.

### What the generator must never emit

- **A number it cannot attribute.** Every figure names the command and the commit it
  came from, in the row. A figure with no source is deleted from the row rather than
  rounded.
- **A language claim.** Language is read per row from the manifests. "All Python" is
  exactly the class of statement this schema exists to prevent: a family summary
  asserted in prose that one member silently falsifies. The same sentence written in
  the corpus this session audited named twelve connectors all Python, and the largest
  of them is Rust.
- **Anything about this machine.** No `~/.` paths, no scratch directories. The
  publication guard already enforces this downstream; writing it clean is faster.
- **A test count.** A test count changes with every commit and the outline would state
  a stale number the day after. `How to check it` names the gate; the gate prints the
  count.

---

## The command

```
genome outline            emit the zone from the current tree, in place
genome outline --check    exit non-zero if the zone is stale, and say what changed
```

`--check` is the important half, because it is what a gate attaches to:

```
npm test && genome outline --check
```

so that a change which alters the shape of the tree without regenerating the outline
fails the build, which is the whole point.

Integration points, all existing:

| File | Change |
|---|---|
| `src/01_constants.py` | add `"outline"` to `MODULES`; register its zones |
| `src/04_zones.py` | no change — the zone writer is reused as-is |
| `src/12_close.py` | include the outline in `emit_all` so `genome close` refreshes it |
| `src/09_lint_checks.py` | add the stale-zone check to the existing E-rule family |
| `src/13_init.py` | `core` gains `docs/OUTLINE.md`; the outline module gains the zone |

`outline` becomes a sixth module rather than a sixth file in `core`, so a KB that
wants only the records skeleton is not forced to carry a generated stack table it will
never refresh. `profiles` keeps working: `--profile full` adds it.

---

## The kickstart path

This is the part that answers "so that all our KBs can be kickstarted":

```
genome init --blueprint stack        # the outline module, the zone, docs/OUTLINE.md
genome outline                       # the first emit
```

A fresh KB is then complete: the entry contract says what this is and how to check it,
the zone says what it is made of, and `docs/OUTLINE.md` is the one file a human reads
first. For the KBs that already exist and already carry a genome, the adoption path is
the one `genome init` already has for the case where `genome.toml` is present — add the
missing pieces and leave the hand-written alone — which means no existing KB loses its
prose.

---

## What this is not

- **Not a documentation linter.** It does not judge writing. It emits facts and fails
  when they go stale.
- **Not a replacement for `AGENTS.md`'s routing table.** The zone sits beside it. One
  owner per question: the table owns which document answers what, the zone owns what
  the code is made of.
- **Not a second records module.** There is no ledger here. An outline is a view of the
  tree, refreshed by a script, and it holds no state.
- **Not automatic prose.** `docs/OUTLINE.md` is deliberately hand-written. A generated
  document cannot state the one rule that shapes a system, because a rule is a judgement
  and this system's rule 4 is that terminal states name their evidence.

---

## Open questions for the operator

1. **Sixth module, or part of `core`?** I propose a sixth module so a records-only KB
   is not carrying a table it will not refresh. The cost is one more entry in
   `--profile` decisions.
2. **Where does the zone live: `AGENTS.md` or `docs/`?** I propose `AGENTS.md`, after
   `## Gate`, because that is where the arriving agent is. The alternative is a
   `docs/STACK.md` of its own, which is one more file to route to.
3. **Does `--check` gate every KB, or advisory at first?** I propose from the start,
   because a check that is not a gate is a check nobody runs.
