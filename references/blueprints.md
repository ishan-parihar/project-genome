# Blueprints: ready-made and custom knowledge bases

Contents: what a blueprint is · the four built in · applying · the daily loop · authoring a new one · the check ·
safety · ceilings.

A **blueprint** is one TOML file: a `[blueprint]` header (summary, modules, privacy, routes, playbook, seed) plus
`[kinds.*]` and `[views.*]`. `genome init --blueprint <name|file>` copies it to `genome/kinds/NNN-<name>.toml`,
writes its playbook to `docs/playbooks/<name>.md`, adds its routing rows to `AGENTS.md`, creates its view documents
and seed entities, and sets `[card] privacy` when it asks for one. Nothing is overwritten, and a second run adds
nothing. Blueprints are configuration, not code: all behaviour comes from the kinds the CLI already understands.

## Built in

| Blueprint | Use it to | Privacy |
|---|---|---|
| `mind-topology` | map one person's inner world with an agent: engrams, emotions, shadows, processes, complexes, insights, sessions. Loops (`graph cycles`) are the knots that feed themselves, hubs the leverage points, bridges the single links between clusters. The agent only proposes `insight`s; untangling, integration and owning a shadow are `human_only`. Not therapy: the playbook says to stop and point to human help on a crisis. | `local` |
| `intersubjective` (extends `mind-topology`) | several people's maps in one graph. Every entry has `of` (whose map) and `seen_by` (whose perception), both defaulting to the seeded self subject `SU-01`. Adds `subject` (attachment style and its source), `bond`, `transaction` (transactional analysis: ego states, complementary/crossed/ulterior) and `pattern`. `graph cycles\|bridges\|hubs\|gaps --across of` shows only what crosses between people. | `local` |
| `literature-research` | go from papers to novel, testable hypotheses (medical science or any field with citable sources). Verbatim claims with locators, GRADE-graded findings, a PRISMA-style search log, concept normalisation, Swanson ABC discovery by `graph gaps --kind concept`, and retraction cascades. `supported` is `human_only`. Not medical advice. | internal |
| `ontology` | build an ontology by derivation (shaped on HoloOS): axioms, theses on the ladder `ai-draft → canonical-hypothesis → canonical` (the last is `human_only`), derivations with HoloOS's patterns, witnesses that corroborate but can never be premises, open joints as the agenda, the five-phase catalyst protocol. | internal |

`genome blueprint list` shows these plus any in `genome/blueprints/`. `genome blueprint show <name>` is the compact
schema (kinds, states, who may move what, relations, views); `--playbook` is the loop; `--toml` the full file. The
profiles (`software`, `research`, `team`, `full`) are also accepted as blueprint names and mean modules only.

## Applying

```bash
genome init --blueprint mind-topology            # new genome, or add to an existing one
genome init --blueprint intersubjective          # extends mind-topology: its entries gain `of` / `seen_by`
genome init --blueprint literature-research --profile research   # modules can be added at the same time
```

- On an existing genome the needed **modules must already be on**: the command refuses before writing anything and
  names the module to add.
- Extending later is safe: entities made earlier get the new default relations (the backfill), and the seed is
  created once.
- If a blueprint kind has the same name as a kind already in `genome.toml`, the genome's own keys win (a note is
  printed). `genome.toml` always merges last.
- The copy in `genome/kinds/` is yours to edit; a later `init --blueprint` keeps it and says if it differs from the
  shipped one.

## The daily loop (every blueprint)

`wake` (the QUEUE shows each blueprint's work, 5 rows per view) → `place` / `ask --index` / `graph` to find where
something belongs → `new … --link rel=ID` (an entity and its edges in **one** call) → `move` (the lifecycle, with
evidence and human sign-off enforced) → `close`.

Call and token budget, by design:
- `show A,B,C` reads several entities in one call; `move A,B,C state` moves several, all checked before any moves.
- `new --batch FILE|-` takes JSON lines `{"kind","title","set","link","body"}`, where `@N` in a link names the entity
  made by line N. A whole paper's claims go in as one call; one bad line writes nothing and names the line.
- Fields are single-line. Prose goes in `--body`, and `show` prints it.
- `wake` is about 300 tokens for a blueprint genome. Read `playbook` once per task, not per session.

## Authoring a blueprint

```bash
genome blueprint new my-kb [--from mind-topology]    # writes genome/blueprints/my-kb.toml, a commented working skeleton
genome blueprint check genome/blueprints/my-kb.toml   # the eval
genome init --blueprint my-kb
```

Design it in this order. Each step maps to one schema feature, so the rule is enforced rather than written down.

1. **Kinds and lifecycles.** One kind per thing with its own lifecycle. `states`, `transitions` (a state not listed
   as a key is terminal), `evidence_on` for states that must cite something.
2. **Who decides.** `human_only = [...]` for every state where a judgement belongs to a person: confirming an
   interpretation, adopting an axiom, calling a hypothesis supported. Agents propose; people dispose.
3. **What must be cited.** `min = n` on a relation (a claim cites exactly one source), `required_in = [states]`
   (a canonical thesis must be derived). Enforced when you create, move or unlink, and again by lint (E511).
   `evidence_ref = { state = "kind?field=a|b" }` on a kind makes the evidence for that state an entity of that kind
   (`state` may be the field): a hypothesis is `screened` only on a `search?executed=yes`, a catalyst `corroborated`
   only on a `witness?state=verified|incorporated`. Without it, evidence is any path, entity id, commit or URL.
4. **What a retraction does.** `taint = [states]` on a relation, with the pointing kind's `quarantine = "<state>"`.
   When the target enters a tainted state, lint flags the pointer (E510) and `new`/`link`/`move` refuse to add or
   keep a dependence on it. Quarantining the pointer (evidence: the tainting id) clears the flag, and the next hop
   shows up on the next lint. Each hop is a reviewed step.
5. **Perspective.** For anything subjective, add a `of`/`seen_by`-style relation with `default = "<id>"` so every
   entry says whose view it is.
6. **Volume.** `store = "jsonl"` for logs and ledgers (append-only; an entity is the fold of its events). Use
   `new --batch` to ingest.
7. **Graph hygiene.** `graph = false` on membership and provenance relations (`of`, `from_session`, `found_by`) so
   they do not become fake hubs. `symmetric = true` for "correlates with", so a pair is not a cycle. Reify an edge as
   a kind when it needs attributes (`derivation`, `transaction`, `bond`): edges carry none.
8. **Views.** `where = ["state!=closed", "priority=high"]` (a list of `field op value`; `state` counts as a field) with
   optional `state`, `columns`, `sort`, `limit`. `wake = true` for the queue an agent should see on arrival (a view that lists states needing action),
   `into = "docs/X.md#zone"` for generated tables and counts. Never hand-write a count.
9. **Playbook and routes.** The playbook is the whole interface for the agent: the rules the schema enforces, then a
   numbered loop of exact commands. Routes are `[question, where the answer lives]` rows for `AGENTS.md`.

Before a state change you are unsure of, `genome impact <id> --to <state>` lists what it would flag, hop by hop.
Times: `date` is the only date type; for a timeline use one `int` or `text` field in a sortable form (`2026-03-02T14:12Z`)
and `sort` the view on it. In a batch a loop closes with forward references (`"link":{"triggers":"@2"}` on line 1 and
`"@1"` on line 2). `genome init --blueprint my-kb` works in an empty repo; `--profile` is only for extra modules.

Relation keys: `to` (`kind|kind` or `*`) · `inverse` (label) · `max` · `min` · `required_in` · `taint` · `graph` ·
`symmetric` · `default`. Kind keys: `path id store mutability fields states initial transitions evidence_on evidence_ref human_only quarantine relations`; anything else is E501. A blueprint can extend another's kind by redeclaring it in a
later file (`extends = ["base"]`, then `[kinds.engram.relations]` with only the new relation): files in
`genome/kinds/` deep-merge in name order and `genome.toml` merges last.

## The check

`genome blueprint check [name|file]` (no argument checks every built-in) validates the declaration and then drives
the real CLI in a scratch genome, a mechanical eval that costs nothing to write:

- the declaration: header keys, summary, playbook, modules, routes, kinds (E501), view kinds and paths, seed kinds;
- a freshly initialised genome lints clean (routes to log files do not dangle);
- one entity per kind (in dependency order), one edge per relation, lint clean;
- every state of every kind is reached through its transitions, with evidence and sign-off supplied;
- every `taint` edge: the target goes bad after the pointer exists, lint flags the pointer, a new pointer is refused,
  quarantining clears it;
- every view renders, `graph hubs`, `place`, `index`, `wake`, `close`.

It prints `PASS name: counts; N CLI calls; wake B bytes` or `FAIL name: <the first step that broke>` and keeps the
scratch genome for inspection. Exit 2 on failure. A defect you introduce on purpose (an unreachable state, a
`min` relation that nothing can satisfy, an unknown target kind) fails it; `scripts/test_genome.py p4_check_catches`
proves that.

## Safety

- `--human NAME` is a record, not authentication: any agent can type any name. "Only a human on the team closes an
  incident" holds when the process does (the agent is told not to, and `lint` warns when a human-only state has no
  sign-off in its history); it is not a lock. Give the sign-off commands to the operator, never run them yourself.
- `privacy = "local"`: no card, no federation, and `close` refuses while the repo has a git remote. Use it for
  subjective or third-party data. It is a guard against publishing by accident, not encryption.
- Another person's map is always "as perceived by someone". Write it as perception; keep it local; do not quote it
  back to them as fact. `consent` on a subject records whether they agreed to be modelled.
- `mind-topology` is reflective self-mapping. If the operator signals crisis, stop mapping and point to human help.
- `literature-research` output carries its certainty. A hypothesis stays a hypothesis until a recorded test says
  otherwise, and `supported` needs a person.

## Ceilings

- Edges carry no weight or attributes, and graph analytics are unweighted. Reify when it matters.
- `graph --kind K` is a one-hop projection through non-K nodes; `--across REL|FIELD` namespaces nodes by the first
  target of the relation (or a field value).
- Tracing a thesis back to its axioms is a query (`graph path`), not a lint rule; lint checks that a derivation exists.
- Taint moves one hop per lint pass, by design.
- The check proves the schema is coherent and drivable. It does not judge whether the playbook is any good; run an
  agent through the loop on a real case (a pilot) for that.
