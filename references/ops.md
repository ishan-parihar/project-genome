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

## Layout (`ops.root_files`, `ops.dir_suffixes`, `ops.dir_requires`, `ops.stale_terms`, `ops.stale_exempt`, `ops.external_ok`, `ops.dir_name_patterns`, `ops.dir_name_exempt`)

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

## Names (`ops.dir_name_patterns`, `ops.dir_name_exempt`)

**E308** asks whether a directory's NAME is legal — a different question from where it sits, which E306 already
asks. Two directories under one parent that normalize to one name are the half that needs no configuration at
all: `PHANTOM` and `phantom`, or `Docs` and `docs`, are one directory to a reader and two to git, so they never
merge and every agent that opens one wonders which is live. The siblings are grouped and judged once, so three
such directories produce one line naming all three, and the answer does not turn on which one the filesystem
listed first.

- `dir_name_patterns = ['^\\s|\\s$', '^[0-9]+\\.[ ]?']`: a regex matched against the directory name.
  Silence is the default — a name is illegal because a project said so, not because a linter has an opinion.
  `^\\s|\\s$` is the usual one (leading or trailing whitespace from a copy).
- `dir_name_exempt = ['kb/PHANTOM', 'vendor/**']`: root-relative globs that name a directory the project does
  want, whatever its shape. It is **per name**: exempting one member leaves the others reported, and exempting
  the whole group (or its parent) silences it.

```toml
dir_name_patterns = ['^\\s|\\s$']
dir_name_exempt = ['vendor/**', 'docs/legacy*']
```

## A file git tracks AND ignores (**E309**)

`git ls-files -i -c --exclude-standard` names files that are tracked and match an ignore pattern at the same
time. Both facts are true, which is the defect: tracking wins on `git status`, so the file is committed and
diffed as normal, while the ignore rule that supposedly excludes it applies to nothing. Every generator that
writes that path produces an untracked sibling beside a tracked one. The remedy is `git rm --cached <file>`,
which keeps the file and ends the contradiction.

This is not E305 (regenerable bulk in git) and not E306 (a misplaced file): both of those run `ls-files -co`
and answer what is tracked. Only `-i` names the contradiction.

## Directories you declare (`ops.dir_globs`)

**E655** asks that a declared directory exists, and **E656** that a declared one is not empty. The inverse of
`dir_requires`, which asks what a directory that exists must hold.

```toml
dir_globs = ["docs/plans", "docs/audit", "docs/regressions"]
```

A genome ROLE's home is exempt from E656, because `genome init` creates those empty and they fill as the work
happens — `docs/plans/` holding nothing on a new repo is a lifecycle, not a defect.

## Application integrity (`[app]`, `[docs]`)

A new module, added 2026-11-03 with the codes **E651–E658 / W651–W655 / I651**, documented in
`references/lint-rules.md` and carried in the `integrity` module. The short version:

```toml
[app]
toolchain = "python"          # or rust, node, typescript, go, java, shell — inferred from the manifest
build = "python3 -m compileall -q ."
test = "python3 -m pytest -q"
install_script = "scripts/setup.sh"

[docs]
required = ["README.md", "AGENTS.md", "docs/ARCHITECTURE.md"]
sections = { "docs/ARCHITECTURE.md" = ["Components", "Decisions"] }
max_lines = 400
min_lines = 40                   # unset = no thin-doc warning; a hard band flagged every fresh init stub
```

An `I651` is a fact, not a defect: a repo with no build (a KB, a notes repo) is not broken, and a toolchain
that cannot run on this machine is a fact about the machine. Only `E` fails a gate.

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
