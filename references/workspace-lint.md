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

## The two scripts that are better, not merely moved

Re-verified 2026-11-03 with `cmp` against the originals at
`~/.cache/jcode-scratch/baseline/`. Of `doc`'s seven scripts, five arrive byte-identical
into `scripts/docs/`. Two do not, and the difference is worth stating precisely rather
than calling the port a straight copy:

- **`verify_install.sh`** — a `printf | grep -q` pipeline under `pipefail` is replaced by a
  temp file, closing a SIGPIPE race; the hardening check becomes shebang-aware, so a
  `/bin/sh` installer is asked for `set -eu` rather than a bashism it cannot carry; and
  the arch-truth check is scoped to installers that actually download an arch-specific
  artefact, instead of demanding `PROCESSOR_ARCHITECTURE` of an `npx` wrapper that has
  no arch-sensitive step.
- **`score_readme.py`** — `curated-list` is no longer classified by linked-entry count
  alone. A 133-line doorway carrying an 11-item docs index was being read as a list, and
  then judged against a 400-line floor for a list it was not. Entry count now has to be
  joined by the absence of an install section and of code fences.

Both are the same shape: the check was firing on trees that were fine. That is the class
of defect this whole reference is about, so the two scripts that carry it are the two
worth reading before anyone touches the checks they own.

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

## What the fleet run changed about the module

Enabling the module on three real repos measured the part the unit tests could not: the
**phase budget**. Holon is a Python distribution whose `test` tier is 48 modules (six past
120s, discovery over ten minutes, `tests/test_adapters.py` holding a real
`time.sleep(120)`) and whose `lint` phase is its own `holon lint --strict`, which runs
past 300s. Declaring either produced `E651 ... timed out after 300 seconds` on a repo
that was not broken.

Two conclusions, both now written into the repo's own `genome.toml` where the next person
will look:

1. **A phase that cannot finish must not be declared.** A check that reports an error for
   a suite that is merely slow teaches the reader to ignore the error. Holon declares
   `build` (a compile check, seconds) and leaves `test`/`lint` to CI, and the `I651` info
   line names what was checked so silence is not mistaken for a green suite.
2. **A phase that calls the linter which calls the phase is a cycle.** `holon
   lint --pack genome` shells out to `scripts/genome lint`, which read `[app] lint` and
   shelled back to holon. The recursion is gone, but the lesson generalises: `[app] lint`
   must never name a tool whose own lint runs `genome lint`.

The other two firmed up the silence rule. paperclip-zeroclaw-adapter declares
`toolchain = "node"` and no phases, because its `package.json` has no `scripts` block, and
naming a `test` that does not exist would be a declaration pointing at nothing.
ishan-parihar declares no `[app]` at all: a metric portfolio has no build, and an app
check that invented a toolchain for it would be noise rather than integrity.

And the module earned its keep in the first week: E309 found
`.genome/overrides/RECORDS_TPL.md` tracked while `.genome/` ignored it, a contradiction
git tolerates and no previous gate could see.

## The two defects this round of validation found in genome itself

Worth writing down, because both are the shape the module exists to catch and neither was
visible until the checks were pointed at the tool's own output.

**`genome init` mapped a role it never filled.** Every `genome.toml` this tool emits
declares `readme = "README.md"`, and until 2026-11-03 no scaffold wrote that file. A fresh
`init` therefore produced a tree that asserted a document which did not exist, and the
moment an operator added `[docs] required = ["README.md"]` — the first thing the integrity
module invites — the lint answered `E653` against a file the tool had been supposed to
create. The scaffold writes it now, short and honest about being a stub, and `redteam6`
asserts it against the path the config maps rather than a hardcoded name.

**The stub then exposed a real pre-existing W009.** Writing a README activates
`lint_outward_pages`, which had been dormant on every fresh tree precisely because no
README existed to link from. It immediately reported `docs/OUTLINE.md` unreachable — and
the same finding against this repo's own `docs/ARCHITECTURE.md`, which had been failing
all along without anything to notice. So the scaffold's docs pointer names the entry page
`core` always writes, the module-scaffolded pages are linked by `cmd_init` only when their
module is on, and this repo's README finally links its architecture.

The generalisation, which is the one worth keeping: **a check that cannot run on the tool's
own scaffolding is a check nobody has seen pass.** Both defects were hidden by a tree that
was too empty to be judged.

## What the estate-wide upgrade found: E309 is the code that earns its keep

`genome installs upgrade --apply` brought 73 vendored copies from `2026.11.02-43` to
`-71`, and `installs verify` now reports the whole estate on one version. Two repos came
back upgraded-but-broken, which the tool names itself; the estate sweep then found that
most of the remaining errors are **E309**, the check added in this consolidation, firing
at scale for the first time:

- **quant-signals — 607 findings.** 597 are `audit/**/*.png|jpg`, which this repo's own
  `.gitignore` (line 45, written when the screenshots were excluded for size) still
  tracks; 10 are `.agents/` files matching `~/.gitignore_global:9`.
- **openscript — 62 findings**, `third_party/`, vendored code the repo also ignores.
- Ten more repos carry one to six each.

The lesson worth writing down: **E309's findings were almost all invisible until the module
was installed across the estate.** The defects predate this work by months; what was
missing was the check, and the check was missing because it lived in a skill that was never
a gate. That is the entire argument for consolidating the three skills into a module every
repo can enable, and it is the strongest evidence from this session that the port was the
right shape.

One caveat on the class, because it cuts the other way: `agentic-harness/external-repos/
deepseek-harness` tracks 3651 files under `.agents/` and they are **upstream's**, from a
public clone — not this operator's confidential artifacts. A global ignore written for the
operator's own machines is simply over-broad against a third-party repo, so those rows are
not defects. The distinction is authorship, which is why `E309` reports the contradiction
and leaves the remedy (`git rm --cached`, or an allowance) to the operator.
