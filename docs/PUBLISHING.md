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

### Before publishing, verify it is really installable

Run the whole chain, in this order, every time. The "already done, dist/ holds both
artifacts" note above is about the FIRST build only: once `src/` moves — a peer
commit, a VERSION bump — the artifacts in `dist/` are stale even though they
install fine, and a stale wheel is exactly what `test_package.py`'s byte-parity
assertion exists to catch.

```console
python3 scripts/build.py             # builds scripts/genome AND records its release checksum
uv build                             # re-packages: sdist + wheel (never skip when src/ moved)
python3 scripts/test_package.py      # 8/8 — installs THAT wheel in a throwaway venv
python3 scripts/test_genome.py       # 38/38 — the CLI itself
python3 scripts/test_package_modes.py # 5/5 — the sdist path, every command in installed mode
python3 scripts/check_ps1.py         # structural + cross-installer parity for install.ps1
```

Confirm the wheel you are about to publish is the one just built: compare the
`scripts/genome` checksum inside it against `scripts/releases.txt`, and the file
mtime against your last commit. If either disagrees with the current tip, rebuild.

`test_package.py` is the one that matters for a release: it installs the wheel
(not the source tree), runs the console script and `python -m`, and asserts the
byte parity between the packaged CLI and the `scripts/genome` the fleet vendors
— which is what `genome upgrade`'s release-checksum comparison is built on. A
release that ships without it could publish a package whose CLI is a stale copy.

## After publishing

```bash
uv tool install project-genome     # from PyPI, no Git needed
genome --version
```

One-liners to put in the README once live:

```bash
# Linux / macOS — the CLI
curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash

# Linux / macOS — the CLI AND the agent skill, one command (cold-start safe)
curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash -s -- --skill

# Windows
irm https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.ps1 | iex
```

The installer's default path is already PyPI (`uv tool install project-genome`),
so publication flips it from "install from Git" to "install from the index"
with no script change. `install.sh --from-github` stays as the path for
unreleased builds.

**What `--skill` writes** (measured 2026-10-30, in a sandbox, against the real
section): one real copy at `~/.agents/skills/project-genome`, a relative symlink
in each other harness root that exists, and one entry in
`~/.agents/.skill-lock.json`. A second run is a no-op on all three; a real copy
left by an older installer run in another root is replaced only after `diff -rq`
proves it identical. The lock file sits at `~/.agents/.skill-lock.json` — one
level **above** the skills root, which is where the npx CLI and this machine's
skills-backup service both look (the first draft wrote it inside `skills/`, where
nothing reads it).

## Versioning

`pyproject.toml`'s `version` is the **distribution** version (currently
`0.1.0`); the CLI prints its own VERSION stamp (`2026.10.30-23`, in
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

**Measured 2026-10-30, corrected the same day.** The row below said `npx skills add`
gives a "CLI: yes (inside the skill)". The first half is literally true and
practically false: the skill directory *does* ship `scripts/genome`, and that file
does run (`./scripts/genome --version` works from inside the skill root), but
**nothing puts a `genome` command on PATH** and nothing registers it in
`~/.config/genome/installs.json`. So every documented command inside
`references/` — `genome lint`, `genome close`, `genome wake` — fails on a machine
that installed the npx way, until the operator edits PATH or runs an installer for
the CLI. The table records what the paths *actually* deliver.

| Path | CLI on PATH | Methodology + references | Registry |
|---|---|---|---|
| `uv tool install` / `pipx` / `pip --user` | yes | no | registers the bin on install |
| `install.sh` | yes (same chain) | `--skill` adds it | registers the bin on install |
| `install.sh --skill` | yes (same chain) | yes, as one canonical copy with one link per harness root | registers the bin, the skill root, and the `.skill-lock.json` entry |
| `npx skills add` | no — a runnable `scripts/genome` lives inside the skill dir, but no PATH entry and no registry row | yes | registers the skills root on install |
| a repo that vendors `scripts/genome` | yes, that repo's copy | via `references/` in that repo | `installs register vendored <path>` |

**The cold-start asymmetry, stated plainly.** `install.sh` installed the CLI and
skipped the skill by default; `npx skills add` installed the skill and skipped the
CLI by default. Neither default was the product. `install.sh --skill` is now both,
in one command (`curl -fsSL …/install.sh | bash -s -- --skill`), and its skill
step writes the same on-disk shape `npx skills add -g` writes — one real copy at
`~/.agents/skills/<name>`, a relative symlink per other harness root, one
`.skill-lock.json` entry — so a machine that has used both paths converges instead
of accumulating a clone per harness.
