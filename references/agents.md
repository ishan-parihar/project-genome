# agents.md — parallel agents: identity, claims, feed, boards

Contents: when · identity · the protocol · boards · feed grammar · register claims

## When

Two or more agents work in the same repo at once. Separate workflows get separate boards, so two agents never
edit one TODO list; within a board, the claim is the lock. The register stays the strategic spine; boards are the
operational surface beneath it.

## Identity

Each agent uses a stable id: `--agent <id>`, or `GENOME_AGENT_ID` (`KB_AGENT_ID` is still read). Every claim,
transition and feed post is signed with it.

## The protocol

1. **On wake:** run `genome wake`. With `GENOME_AGENT_ID` set, it shows your new mentions since your last wake;
   the read mark is in `.genome/seen-<id>`. To browse the feed itself: `genome feed --to <you> --since F####`.
2. **Before work:** claim it. For a board item, `genome claim <item>`. For a strategic row,
   `genome claim-register <row>`. Both are flock-guarded and refuse an item another agent holds (exit 2).
3. **Cross-talk:** use `genome post "<msg>" [--wf W] [--to @agent] [--reply F####]` for blockers, questions and
   handoffs.
4. **On finishing:** run `genome done <item> done --evidence <path>`, which posts automatically. The evidence
   pointer lets the next agent verify rather than trust.

## Boards (`paths.workflows/<wf>.md`)

```bash
genome wf new migration && genome wf add migration "move the orders table"   # migration-001
genome claim migration-001 --agent agent-a
genome done migration-001 done --evidence docs/audit/2026-10-17-migration.md

`done` refuses when another agent holds the claim (exit 2); the holder finishes it, or releases it first.
genome wf list
```

Each board row is `| id | status | item | claim | verdict |`. The claim cell reads
``claimed-by `<agent>` since <ts>``. That exact shape is what double-claim detection reads, so never hand-write a
claim. A malformed in-progress claim is E008.

## Feed grammar (`paths.feed`, append-only)

```
- **[F0042]** 2026-10-17T03:14 · `agent-a` · wf:migration · @agent-b · → F0039 — migration-001 lands today; refactor-002 unblocks after
```

The fields, in order:
1. the id;
2. the timestamp;
3. the author (backticked);
4. optional `wf:`;
5. optional `@addressee`;
6. optional `→ reply-to`;
7. ` — `, then the message.

The feed is a file in git, so it is reviewable, greppable, and survives the tooling that wrote it.

## Register claims

`genome claim-register R7` **appends** the claim to the row's notes cell, keeping the existing context.
`genome status` then refuses transitions on a row another agent holds unless `--agent` matches.
