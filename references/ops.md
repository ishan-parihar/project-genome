# ops.md — housekeeping gates for repos big enough to rot quietly

Contents: why · ownership map · links · unreachable code · tracked bulk · secrets · running jobs · configuration

## Why

Every file in the working tree costs an agent context and can mislead it. A repo with 65 scripts that nothing
live calls, 1.3 GB of regenerable data in git, and docs that cite files that no longer exist pays that cost on
every session. These gates fail closed, so the tree holds only live truth. Superseded material is archived, not
deleted (core `archive`).

## Ownership map (`paths.ownership_map`, `ops.owner_globs`, `ops.owner_exempt`)

A table listing every active doc, with its status (`LIVE`, `EVIDENCE`, `PLAN-ACTIVE`), the question it owns, and
what it is not for.

**E301** fires when a tracked file under an owner glob is neither listed by path nor by backticked basename. This
is the machine half of "one owner per question". The other half, two docs answering one question, is judgement:
consolidate them and archive one.

Glob semantics everywhere in genome.toml:
- `*` stays inside one path segment;
- `**` crosses segments;
- a pattern without `/` matches the basename anywhere (`"*.parquet"`).

## Links (`ops.link_surfaces`, `ops.link_prefixes`)

**E303** checks backticked paths in the link surfaces (globs). A token counts as a pointer when it is file-shaped
(`dir/name.ext`), or when it starts with one of `link_prefixes` (then directories count too).

Placeholders (`<x>`, `{x}`, `*`, `…`, `NNNN`), URLs, absolute and home paths, flags and git refs are prose. A
pointer resolves if any of these exists:
- the file at the root;
- a tracked file ending with the pointer (package-relative paths such as `tools/x.rs`);
- the file on disk under a tracked directory that holds its first component (untracked artefacts such as
  `scratch/…/x.json`);
- `module.py`, for `pkg/module.func`.

Moving a file means relinking its readers in the same commit. `genome archive` prints them.

## Unreachable code (`ops.code_globs`, `ops.code_roots`)

**E304** fires for code under `code_globs` that no live surface reaches. Live surfaces are:
- the link surfaces;
- the docs the map and contract point at;
- active records;
- files matching `code_roots` (bin/, tests/, cron, skills…).

Reachability is by name and transitive: a file that a reachable file names is reachable. Unreachable code goes to
`scripts/archive/<generation>/` with its path preserved, or gets cited from its owner doc.

## Tracked bulk (`ops.bulk_globs`, `ops.max_bytes`, `ops.bulk_allow`)

**E305** fires for files tracked in git that match `bulk_globs`, or that exceed `max_bytes` and are not
allow-listed. The fix is `git rm --cached` plus `.gitignore`: the file stays on disk and in history.

## Secrets (`ops.secrets`)

`secrets = [".env:API_KEY", "~/.config/app/token"]`: a dotenv key, or a whole file. `genome secrets` (also run by
`close`):
- scans the staged and unstaged diff, plus every untracked (not ignored) file, for each value;
- prints only the source label and a hit count, never the value;
- exits 2 on a hit.

Values under 6 characters are ignored, since they would match by accident.

## Running jobs (`ops.jobs`)

- `wake` shows the output of `ops.jobs`, e.g. `bin/rdjob status`.
- `doctor` lists modified files that a running process executes, or that its Python script imports
  (transitively, through static `import` / `from` lines resolved from the root, the script's directory and
  `ops.py_paths`; `python -m pkg.mod` and the process's working directory are followed). A long job reading
  code you just edited produces results from neither version.

Imports done through `importlib` or computed `sys.path` entries are not followed; list such directories in
`ops.py_paths` (e.g. `["Shared/engines", "scripts/pipelines"]`).

## Layout (`ops.root_files`, `ops.dir_suffixes`, `ops.dir_requires`, `ops.stale_terms`, `ops.stale_exempt`, `ops.external_ok`)

**E306** keeps files where they belong (it replaces a hand-built structure linter):
- `root_files`: the only files allowed at the root (dot-files exempt);
- `dir_suffixes = { "scripts" = [".py", ".sh"], "Shared/data" = "*" }`: the longest matching dir decides; `"*"` allows
  anything;
- `dir_requires = { "sub-systems/*" = "AGENTS.md" }`: every matching dir holds that file;
- `external_ok`: tracked symlinks allowed to point out of the repo. Any other one is **E307**: it ties the repo to
  one machine and lets text outside it steer agents (a linked skill, a linked CLI).
- `stale_terms`: old paths that docs (`*.md`, `*.yaml`, `*.toml`, `*.txt`) must no longer name; append-only roles,
  archives and `stale_exempt` globs are exempt;
- a file named like a truncation artefact (`…truncated…`, `...x`) is always flagged.

Tracked and untracked (not ignored) files are checked.

## Commands in genome.toml run as code

`core.gate`, `core.emitters` and `ops.jobs` are shell commands. `close` runs the first two and `wake` runs the
third. Treat a foreign repo's `genome.toml` the way you would treat its Makefile: read it before running `wake`
there.

The records recon token is a nudge, not a lock: it proves an agent ran the prior-art search recently. It cannot
prove the agent read the results.

## Configuration sketch

```toml
[ops]
owner_globs = ["sub-systems/*/docs/**/*.md", "skills/*/references/*.md"]
owner_exempt = ["skills/x/references/generated.md"]
link_surfaces = ["AGENTS.md", "docs/STATE.md", "skills/**/*.md"]
link_prefixes = ["core/", "docs/", "scripts/", "skills/"]
code_globs = ["scripts/**/*.py", "scripts/**/*.sh", "bin/*"]
code_roots = ["bin/*", "tests/*.py", "skills/**", "cron-jobs/*"]
bulk_globs = ["*.parquet", "*.pkl", "*.npz", "models/scratch/ledgers/*"]
max_bytes = 5000000
secrets = [".env:MT5_PASSWORD", "~/.config/gogcli/.keyring_pass"]
jobs = "bin/rdjob status"
py_paths = ["scripts/pipelines", "Shared/engines"]
root_files = ["AGENTS.md", "README.md", "genome.toml", ".gitignore"]
dir_suffixes = { "scripts" = [".py", ".sh", ".md"], "docs" = [".md"] }
dir_requires = { "sub-systems/*" = "AGENTS.md", "skills/*" = "SKILL.md" }
stale_terms = ["Scripts/Python"]
```

TOML 1.0 inline tables are one line: a multi-line `{ … }` is a parse error (use one line, or a `[ops.dir_suffixes]`
table).

## Vendored copy

`doctor` says when the vendored CLI differs from the skill copy (`~/.agents/skills/project-genome/scripts/genome`, or
`$GENOME_SKILL`). It never updates itself: the repo pins its tool. Read the changes, then copy.
