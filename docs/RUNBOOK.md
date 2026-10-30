# Runbook — exact commands, environment traps

This repo has no vendored CLI of its own — it IS the kernel. Run the CLI as
`python3 scripts/genome ...` (or `python3 -m project_genome ...` from an installed copy).
Everything below is stdlib-only unless it says otherwise.

| task | command | traps |
|---|---|---|
| build the CLI from source | `python3 scripts/build.py` | writes `scripts/genome` AND records its sha in `scripts/releases.txt`; it **refuses** to rewrite a released checksum — bump `VERSION` in `src/01_constants.py` first |
| check the artifact is current | `python3 scripts/build.py --check` | exits 1 when `scripts/genome` differs from the build. Run it before any commit that touched `src/` |
| the CLI suite | `python3 scripts/test_genome.py` | 38/38 measured 2026-10-30. Runs against a **scratch copy**; it never writes your project |
| the packaging suite | `python3 scripts/test_package.py` | needs `dist/` to hold the built artifacts; 8/8. Installs the wheel in a throwaway venv and asserts byte parity with `scripts/genome` |
| the packaging-modes suite | `python3 scripts/test_package_modes.py` | 5/5 measured 2026-10-30. Covers the sdist path, the whole command surface in installed mode, the exit codes a CI job chains on, and the Python floor. **Run it from a neutral cwd** (`cwd=/`) — from the repo root the local `project_genome/` shadows site-packages |
| installer parity | `python3 scripts/check_ps1.py` | structure + cross-installer parity for `install.ps1`; 258 lines measured 2026-10-30 |
| outline-language probe | `python3 scripts/probe-outline-languages.py` | 9/9 measured 2026-10-30 |
| build both artifacts | `uv build` | produces the sdist and the wheel in `dist/`; the packaging suites install those, not the source tree |
| lint this repo | `python3 scripts/genome lint --all` | plain `lint` truncates; `--all` prints every finding |
| doctor | `python3 scripts/genome doctor` | staleness and append-only violations |
| the CLI, from this repo | `python3 scripts/genome wake` | also `python3 -m project_genome` from an installed copy |
| the CLI, this repo's own version | `python3 scripts/genome --version` | prints the `src/01_constants.py` VERSION stamp, not the distribution version |
| mint a new lint code | (no command — a rule) | the next free flat code. Measured 2026-10-30: live max **E017**, free **E018/E019/E020**, gaps **E007/E011/E012 are NOT reused** |
| the eval suite | `python3 evals/grade.py <id> <repo>` | 16 evals in `evals/evals.json`; `python3 evals/make_fixtures.py` builds the fixtures first |
| release | `docs/PUBLISHING.md` | the operator's credential, the operator's step. Nothing in this repo publishes by itself |

## Environment traps

- **`pytest` has nothing to collect.** The gate is `python3 scripts/test_genome.py`. The
  suites are plain scripts on purpose: that is what keeps the built artifact
  dependency-free.
- **Never hand-edit `scripts/genome`, `dist/`, or a generated zone.** They are built.
  Running the build is the edit.
  The SYMPTOM to recognise: the edit is gone and nothing says so. `git status` is clean,
  `git diff` is empty, the checksum guard never fires (it only refuses a same-VERSION build
  that CHANGES bytes, and the rebuild reproduces the bytes `src/` describes), and
  `build.py --check` passes because the artifact really was rebuilt. An edit applied to
  `scripts/genome` is therefore indistinguishable from a change that was never made — the
  only signal is the behaviour being absent when you look for it. Observed 2026-10-30: an
  installed-mode `upgrade` message was edited into `scripts/genome` and reverted by the next
  build, and was believed shipped until a manual read found the wording gone. Edit
  `src/NN_*.py`, bump `VERSION`, rebuild.
- **`test_package_modes.py` from the repo root reads the wrong `project_genome`.** The
  repo's own `project_genome/` package shadows site-packages when cwd is the repo root,
  so an installed copy resolves to the source tree. The suite computes its own paths from
  `__file__` and passes either way, but the honest reading is from a neutral cwd.
- **Two vendored copies in `holon`.** `holon/scripts/genome` and
  `holon/holon/vendor/genome.py` are both live. Both are at `2026.10.27-13`. A fleet
  sweep that counts files instead of repos will over-count by one.
- **`pioneer-qf` vendors at `bin/genome`, not `scripts/genome`.** Same reason: count
  repos, not the `scripts/` convention.
- **The knowledge-bases have a `genome/` directory, not the CLI.** Under
  `knowledge-bases/`, `genome/` is that KB's own layout (its `kinds/` subdir). A
  filesystem sweep for `-name genome` returns 11 directories that are not the CLI.
- **`install.sh` and `install.ps1` must stay at parity.** `check_ps1.py` is the check.
  A flag added to one is added to the other in the same change — the behaviours now on
  both are `--skill`, `--dir`, the git prerequisite check at request time, the registry
  registration, the vendored-copy guard that refuses to reset a working-tree copy,
  `--copy-skill`, the canonical-root link loop (`SKILL_CANON_ROOT` /
  `$script:SkillCanonRoot`), the computed relative link target, and the
  `.skill-lock.json` entry. `check_ps1.py` also teaches its brace matcher that
  `[ordered]@{` opens a literal, not a block — install.ps1 builds the lock entry
  through it, and without that the checker reports a mis-nested block on a file whose
  real brace counts are fine.
- **The build refuses a silent checksum rewrite.** If the bytes change and VERSION does
  not, `scripts/build.py` fails, because the fleet's 75 vendored copies are compared
  against that sha and a silent rewrite makes every one look hand-patched.
- **`genome close` does not commit.** It prints the `git add -- <paths>` line. Stage only
  those paths; a parallel session may be committing in this repo (there was one, live,
  2026-10-30).
