# Publishing project-genome to PyPI

The package builds and installs. Publishing is the one step that needs a
credential, so it belongs to the operator. Everything before it is done and
verified.

## Current state

| Item | State |
|---|---|
| PyPI name | `project-genome` — verified **free** (`genome` and `genome-cli` are taken by other projects, and would have been wrong names for this tool) |
| Build | `uv build` produces `dist/project_genome-0.1.0.tar.gz` (sdist) and `dist/project_genome-0.1.0-py3-none-any.whl` (wheel) |
| Wheel contents | 8 files: `project_genome/{__init__,__main__,_genome}.py` + metadata. `_genome.py` is the same 392 KB `scripts/genome` the repos vendor |
| Entry points | `genome` console script and `python -m project_genome` |
| Runtime deps | none (stdlib only, Python ≥ 3.11) |
| Install verified | the wheel installs into a fresh venv; `genome --version`, `init`, `lint`, `doctor` and `upgrade` all run; the from-GitHub install path was exercised against the real repo |

## Publish

```console
# 1. Build (already done — dist/ holds both artifacts)
uv build

# 2. Publish. The token is a PyPI API token scoped to this project:
#    https://pypi.org/manage/project/project-genome/tokens/ (or pypi.org/manage/account/token/)
uv publish dist/*            # prompts for the token: pypi-…
```

`uv publish` reads `UV_PUBLISH_TOKEN` when set, which is the right form for a
non-interactive shell:

```console
export UV_PUBLISH_TOKEN='pypi-…'
uv publish dist/*
```

With `twine` instead of `uv`:

```console
python3 -m twine upload dist/*
```

PyPI requires a **first publication by any method** to be done with a token that
has the project pre-claimed — the one-time verification step PyPI shows on a new
project is what makes the name permanently yours. Do that before treating the
name as safe.

## After publishing

```bash
uv tool install project-genome     # from PyPI, no Git needed
genome --version
```

One-liners to put in the README once live:

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash

# Windows
irm https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.ps1 | iex
```

The installer's default path is already PyPI (`uv tool install project-genome`),
so publication flips it from "install from Git" to "install from the index"
with no script change. `install.sh --from-github` stays as the path for
unreleased builds.

## Versioning

`pyproject.toml`'s `version` is the **distribution** version (currently
`0.1.0`); the CLI prints its own VERSION stamp (`2026.10.29-21`, in
`src/01_constants.py`), which is what `genome upgrade` compares between a
vendored copy and a release. They are deliberately different: the CLI version
moves with every change, the distribution version moves on public releases.

Bump both together for a public release:

1. `src/01_constants.py` → the new VERSION stamp, then `python3 scripts/build.py`
   (the build refuses to rewrite a released checksum; the bump is the fix).
2. `pyproject.toml` → the new version.
3. Commit, push, `uv build`, `uv publish dist/*`.

PyPI rejects a re-upload of an existing version number, so a failed publish of
`0.1.0` needs `0.1.1` (or `--publish-url` to TestPyPI first, which is the safe
rehearsal: `uv publish --publish-url https://test.pypi.org/legacy/ dist/*`).

## What a user gets on each path

| Path | CLI | Methodology + references | Registry |
|---|---|---|---|
| `uv tool install` / `pipx` / `pip --user` | yes | no | registers the bin on install |
| `install.sh` | yes (same chain) | `--skill` adds it | registers the bin on install |
| `npx skills add` | yes (inside the skill) | yes | registers the skills root on install |
| a repo that vendors `scripts/genome` | yes, that repo's copy | via `references/` in that repo | `installs register vendored <path>` |
