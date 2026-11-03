# workspace-lint → the `ops` module

**Status:** absorbed into `project-genome` on 2026-11-02, by the meta-skill
discipline: one skill per class of work, and this class already had an
implementation with a lint catalogue behind it.

`workspace-lint` was a standalone skill carrying a 441-line `workspace_lint.py`
plus a per-project `workspace-lint.yaml`. It answered a real question — *is this
working tree still shaped the way I declared it?* — and it answered it with a
second linter beside the one genome already runs.

Nothing was lost. The second linter is not needed on its own terms, because
the same rules are kernel checks with codes and configuration keys: **the two
overlapped on almost everything, which is the reason to merge rather than to vendor
side by side.** The three rules the kernel could not already answer were written as
E308 and E309 below, not left behind.

## What maps to what

| `workspace_lint.py` does | genome's own equivalent |
|---|---|
| `structure.canonical` — dirs that must exist, with a purpose | **E306** `ops.dir_requires` (a dir missing its required file) + **E301** the ownership map |
| `rules.root` — files allowed at the root | **E306** `ops.root_files` |
| suffix / extension placement rules | **E306** `ops.dir_suffixes` |
| `rules.forbid` — patterns that must not appear | **E305** tracked bulk, **E303** dead link citations, **E308** a forbidden directory NAME (`ops.dir_name_patterns`) |
| orphaned files at the root | **E301** (a tracked file with no owner row) |
| duplicate directories (two names that normalize to one) | **E308**, added 2026-11-02 — the validator's duplicate scan had no genome equivalent |
| tracked files that also match `.gitignore` | **E309**, added 2026-11-02 — `git ls-files -i -c`, which no genome check passed |
| stray `__pycache__` / `.pyc` / `.log` | **E305** regenerable bulk + `.gitignore`, which genome never fights |
| git hygiene | `git status` / `close`'s staleness checks; **E307** an escaping symlink |
| the validator script itself | `genome lint` — one stdlib file, no PyYAML |

That last row is the load-bearing difference. `workspace_lint.py` imports PyYAML
and therefore needs an installed dependency; the kernel's standing rule is that
the CLI stays **one stdlib-only file** so `copy-one-file` installability holds.
A second linter that needs a dependency breaks the property the whole design
rests on, for a job the stdlib one already does.

## What to do instead

1. `genome lint` — it reports every structural violation above, by code.
2. Configure the shape you want in `genome.toml`, not in a second config file:

```toml
[ops]
root_files = "README.md AGENTS.md LICENSE"
dir_suffixes = { docs = "md", scripts = "py|sh" }
dir_requires = { docs = "INDEX.md" }
dir_name_patterns = ['^\\s|\\s$']
dir_name_exempt = ['vendor/**']
bulk_allow = []      # regenerable bulk may be tracked, with a reason
owner_globs = ["docs/**/*.md"]
```

3. The per-project half stays per-project, exactly as before. The config moved;
   it did not become global. `workspace-lint.yaml`'s content belongs in
   `[ops]`, one repo at a time.
4. `genome ask "<question>"` finds which section owns an answer without reading
   the whole reference tree.

## The two codes that were added, not mapped

Three of the old validator's checks had no genome equivalent and were **written**, on
2026-11-02, as **E308** and **E309** rather than being folded into an existing check:

- a forbidden directory **name** (`ops.dir_name_patterns` / `ops.dir_name_exempt`) and
  two siblings that normalize to one name — E308;
- a file git **tracks and ignores** at once (`git ls-files -i -c`) — E309.

E309 is the one that found real defects the day it was written: operant tracks
`Cargo.lock` and `kernel-sidecar/uv.lock` while `*.lock` ignores them, and holon
tracks `.genome/overrides/RECORDS_TPL.md` while `.genome/` ignores it. Both are now
green after the remedy, which is the point of the check.

## The three integrity axes the consolidation actually closed

The port above is complete and byte-verified. What the port exposed is bigger: all three
skills validated a *surface* — prose, an installer, a tree — and none of them could ask
**does this application still build**. The `integrity` module (`E651`–`E658`, `W651`–`W655`,
`I651`) closes that, and it is the same three-axis discipline in each case:

- **app** — `[app] toolchain` names the language or genome infers it from the manifest, and
  `[app] build` / `test` / `typecheck` / `lint` run it. A failed phase is `E651`.
- **docs** — `[docs] required` names the documents a project owes its readers, and
  `sections` the headings one must carry. An absent or heading-only required doc is
  `E653`.
- **dirs** — `ops.dir_globs` names directories that must exist (`E655`) and must not be
  empty (`E656`, unless the dir is a genome role's home).

Three severities now, and only one fails a build — `I651` states a fact an operator should
see (a toolchain genome found but could not run here) without turning it into a gate
failure. The config is per-project and per-lifecycle: a CLI declares its Rust build, a
knowledge base declares nothing and is asked nothing.

## The one thing to actually port

If a repo already has a `workspace-lint.yaml`, do not hand-transcribe it blindly.
The two schemas differ in one way that matters: `workspace-lint` declares a
**canonical directory list** and asks "is anything missing or extra", while
`ops.dir_requires` declares **per-directory obligations** and asks "is each
directory satisfying its own contract". A canonical list can express "docs/
must exist"; `dir_requires` can express "docs/ must exist *and* must contain
INDEX.md", which is the rule that was silently unenforceable before.

Read `references/ops.md` for the full gate set and the configuration keys.

## What was not ported, and why

`workspace_lint.py --fix` auto-remedies violations by moving files. Genome has
no equivalent, deliberately: every housekeeping gate here **fails closed and
tells you the command** (E306 names `move or rename the file`) rather than
mutating the tree. An agent that silently relocates files breaks paths other
agents mid-run are holding. The fix is a suggestion the operator applies.
