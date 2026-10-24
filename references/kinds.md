# Kinds, the index and the graph

Contents: declaring a kind · field types · states and transitions · relations · stores · commands · views · lint codes ·
the index · graph queries · `place` · what is not here.

A **kind** is a declared entity type. Use one when a knowledge base needs a lifecycle the built-in registers do not
give it: engrams, leads, claims, concepts. Kinds live in `genome.toml` as `[kinds.<name>]`, or in
`genome/kinds/*.toml` (same tables; handy for a blueprint to drop in). No kind is declared by default, so a repo
without them behaves exactly as before.

```toml
[kinds.engram]
path = "map/engrams"                 # dir store: one markdown file per entity; jsonl store: one file
id = "EN-{n:04}"                     # Python format; the counter is n
fields = { statement = "text!", valence = "enum:-2..2", intensity = "int:0..10" }
states = ["captured", "mapped", "integrated", "canonical"]    # initial = the first, unless `initial` is set
transitions = { captured = ["mapped"], mapped = ["integrated", "captured"], integrated = ["canonical"] }
evidence_on = ["integrated"]         # entering this state needs --evidence <existing path | commit:<sha> | URL>
evidence_ref = { integrated = "note?state=reviewed" }   # optional: that evidence must be an entity of this kind (and field/state)
human_only = ["canonical"]           # needs --human <name>; lint warns if history lacks the sign-off
mutability = "current"               # current | amendable | append-only | immutable
[kinds.engram.relations]
triggers = { to = "engram|emotion", inverse = "triggered-by" }
belongs_to = { to = "emotion", max = 1 }
```

- **Field types:** `text`, `int`, `int:lo..hi`, `enum:a|b|c`, `enum:lo..hi`, `date`, `bool`. A trailing `!` marks it
  required. Names `id kind state title` are reserved.
- **Transitions:** omit them and any state may follow any other. With them, a state not listed as a key is terminal.
- **Relations** are stored once, forward. The inverse name is only a label for reading (`show`, `graph`). `to` is a
  `|` list of kinds or `*`. Keys:
  - `max` / `min` cap or floor the number of targets (`min` is enforced on create and unlink, and by lint E511);
  - `required_in = [states]`: at least one target from those states on (enforced by `move`, `unlink` and lint E511);
  - `taint = [states]`: the pointing kind must declare `quarantine = "<state>"`. A target in a tainted state flags the
    pointer (E510); `new`, `link` and `move` refuse to create or keep such a dependence unless the pointer is in its
    quarantine state, which is reachable from any state with evidence;
  - `default = "<id>"`: filled by `new` when the edge is not given;
  - `symmetric = true`: reads the same both ways, so a pair is not a cycle;
  - `graph = false`: stored and linted, but left out of graph analytics (membership, provenance).
- **Fields are single-line**; long prose goes in `--body` (stored under the title, printed by `show`, indexed by `ask --index`).
- **Stores.** `dir`: `<path>/<ID>-<slug>.md`, front-matter holds the fields and relations (comma-separated ids), the
  body is yours, `## History` is maintained by the tool. `jsonl`: an append-only event log (`new`, `move`, `set`,
  `link`, `unlink`); an entity is the fold of its events, which suits outcome ledgers and high-volume logs.
- **Mutability** is checked: `append-only` jsonl fails lint (E508) if any commit removed a line; `immutable` dir
  entities fail if a second commit touched the file.

## Commands

| Command | Does |
|---|---|
| `genome new <kind> --title T --set k=v … --link rel=ID … [--body B] [--json]` | creates an entity and its edges in one call; fields, enums, ranges, target kinds, cardinality and defaults are enforced on write |
| `genome new --batch FILE\|-` | JSON lines, e.g. `{"kind":"claim","title":"t","set":{"quote":"…"},"link":{"cites":"@2","subject":"CO-3,CO-9"},"body":"…"}`. `@N` is line N of the input (1-based), forward or back, so a loop can close inside one batch; a link value is an id, `"A,B"`, or a list. Validated whole, all or nothing; an error names the line |
| `genome impact <id> [--to STATE] [--json]` | previews, without writing, what entering a taint state would flag (E510), hop by hop, with the `move` command that clears each hop |
| `genome move <id>[,<id>…] <state> [--evidence P] [--human NAME]` | transitions, evidence (a path, an **entity id**, `commit:`, a URL), human-only, required relations and taint enforced; several ids are all checked before any moves |
| `genome set <id> --set k=v …` | typed field updates (refused on an immutable kind) |
| `genome link <a> <relation> <b>[,<b>…]` / `unlink` | typed edge(s); target kind, `max`, `min`, `required_in` and taint enforced. In `new --link`, repeat the flag per relation (`--link a=X --link b=Y`); commas separate targets of one relation only |
| `genome show <id>[,<id>…] [--json]` | fields, body, edges in both directions, the last History lines |
| `genome find <kind> [--state S] [--where 'field op value' …] [--limit N] [--json]` | ops `= != < > <= >= ~` |
| `genome view <name>` | a saved query as a table: `[views.<name>] kind, where, columns, sort, limit, group_count, into = "doc.md#zone", wake = true` |

A view with `wake = true` is listed in `wake` under QUEUE (5 rows each; empty ones collapse into one line).
`emit` and `close` refresh every view that has `into`. A `group_count` view is a generated count per state: never
write counts by hand.

## Lint codes

E501 kind declaration unusable (including an unknown key, so a typo is an error, not a silent no-op) · E502 field
missing or ill-typed, including an undeclared front-matter key on a dir-kind row (the report names the key; the CLI
write paths validate against the kind, so an undeclared key in a file is a hand edit, never adopted by a rewrite) ·
E503 state not declared · E504 duplicate or
malformed id · E505 dangling edge · E506 unknown relation or wrong target kind · E507 cardinality exceeded · E508
frozen kind edited · E509 evidence-state without evidence in History · E510 an edge to a target in a taint state from
an entity that is not in its quarantine state · E511 a required relation missing (`min`, or `required_in` the current
state) · W501 file in a kind directory without
entity front-matter · W502 human-only state without human sign-off.

## The index (a cache) and retrieval

`.genome/index.db` (gitignored; stdlib sqlite3 with FTS5) holds sections, entities and edges, rebuilt per changed
file from content hashes. Delete it and the next command rebuilds the same thing. Markdown and jsonl stay the
source of truth.

- `genome index [--rebuild]` refreshes it and prints the counts. Other commands refresh it themselves.
- `genome ask --index "<q>"` ranks with BM25 (headings weigh 3×) and also returns matching entities. Set
  `[core] ask_index = true` to make it the default. The plain `ask` ranker stays for small repos: it already
  answers in about 0.3 s on the biggest genome here.
- Every read command that has `--json` returns ids and line ranges, never whole files.

## Graph queries (`genome graph <query> [a] [b] [--depth N] [--top N] [--json]`)

| Query | Answers |
|---|---|
| `neighbors <id> --depth 2` | the entities around one, layer by layer (edges read both ways) |
| `path <a> <b>` | shortest chain of edges between two |
| `hubs` | degree and betweenness: the leverage points |
| `cycles` | strongly connected groups: loops that feed themselves |
| `bridges` | edges whose removal splits a cluster |
| `gaps` | open triads: A and C share neighbours but have no edge (the Swanson ABC pattern: unseen connections worth testing) |

Two filters apply to every query. `--kind K` projects the graph onto one kind (two K nodes are adjacent when linked
directly or through one non-K node), so `gaps --kind concept` finds concept pairs that share a mechanism but were never
linked by any claim. `--across REL|FIELD` namespaces every node by the first target of that relation (or a field's
value) and keeps only what crosses namespaces: hubs ranked by cross-namespace degree, loops that span several
namespaces, bridges and gaps between them. `hubs` skips nodes with no edges.

`genome place "<text>"` answers where a new item lands: candidate kinds, the nearest entities and sections, and, per
nearby entity, the relations that could connect the new item to it (`edge: new engram → EN-12 (…) via triggers | …`). It writes nothing; confirm with `new` and `link`.

## Not here

- Built-in registers (AD/RG, asks, hypotheses) are still the existing commands; re-expressing them as kinds is
  planned, with the old verbs kept as aliases.
- No embeddings, no query language beyond `field op value`. Anything bigger is an `emitter` or a blueprint.
