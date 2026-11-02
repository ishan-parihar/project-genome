# Installers — the first run a stranger has

Absorbed from the standalone `install-script-creator` skill. Depth lives in
`references/installer/` and `assets/installer/`; this file carries the
decisions.

The bar: `curl -fsSL <url> | bash` (or `irm <url> | iex`) either installs a
working tool or prints a precise, actionable error. Nothing in between.

## Six steps, in order

1. **Profile the project** — language/runtime, shape (CLI, MCP server, skill
   bundle, server, docker stack, library), distribution (PyPI/npm/crates,
   GitHub release binaries, source-only), config surface (env, files, keys),
   update owner, and what the README already promises. The installer must
   deliver exactly that promise.
2. **Match an install profile** — `references/installer/project-profiles.md`
   (python-cli, node-cli, rust-binary, mcp-server, skill-bundle, local-server,
   docker-selfhost, library; hybrids compose). A CLI that is also an MCP
   server installs the CLI first and offers the extras — never force a user
   who wanted the binary to configure three harnesses.
3. **Generate from the template, delete what doesn't apply** —
   `assets/installer/install.sh.tmpl`, `install.ps1.tmpl`, and
   `setup.bat.tmpl` only for cmd-only audiences. A lean correct script beats a
   full-featured one with dead sections. `references/installer/cross-platform.md`
   has the OS/arch/libc detection, prerequisite matrix and idempotent PATH
   snippets.
4. **Harness integration** — `references/installer/harness-matrix.md` (the 79-
   harness `npx skills` registry plus zeroclaw/omp/omo) and
   `references/installer/mcp-wiring.md`. Detect don't assume; version-gate;
   offer don't force (interactive in a TTY, flags and `SKIP_HARNESS=1` to
   override, skip in CI); validate generated TOML/JSON before writing; verify
   with the harness's own list command after.
5. **Star + donate epilogue** — `references/installer/cta-star-donate.md`:
   repo star prompt plus donation links, skippable via `--no-cta` /
   `SKIP_CTA=1`, never blocking, never requiring network. The same file
   defines the `<cli> donate` subcommand and the repo's `FUNDING.yml` — which
   is the sponsorship half of `references/surface.md`, so a new repo gets it
   from the installer rather than as a later chore.
6. **Verify before delivering** — `bash scripts/docs/verify_install.sh <path>`
   (syntax, shellcheck, required sections, idempotency guards), then really run
   it: one fresh container per OS family (`debian:stable`, `fedora`,
   `archlinux`, `alpine` for musl), twice, back to back. Then `command -v
   <cli>` in a *new* shell — PATH edits only prove themselves there.

## Non-negotiable rules

- `set -euo pipefail` (bash); `$ErrorActionPreference = 'Stop'` (PowerShell).
- Never `curl | sudo bash`. Download, verify, then run with least privilege.
- Every write to a user file (shell rc, config) is idempotent — grep before
  append. Non-idempotent PATH injection is the top "ran it twice, now my rc
  has six copies" bug.
- Files containing secrets get `chmod 600`.
- One failure mode per check: print what failed, why, and the exact fix.
- The installer bootstraps the CLI; **the installed CLI owns updates**. A saved
  shell script or a mutable `main` URL must never be the only update path. For
  direct-release binaries embed the app's own updater
  (`references/installer/updater-architecture.md`); for package-managed
  installs delegate to the manager and never overwrite files owned by pipx,
  npm, Cargo, Homebrew, winget or a distro package.

## Why these rules exist

Each maps to a failure that has actually bitten these projects or every
installer author: `curl | sudo bash` is the yearly-demoed credential-theft
vector; musl silently breaks glibc release binaries; Rosetta makes `uname -m`
lie on macOS; `PROCESSOR_ARCHITECTURE` lies under Windows emulation (read the
registry); pip-installing into system Python wrecks Debian's package
management. Understand the failure before bending the rule knowingly.

## Reporting

Which OSes were smoke-tested, which were not, and the exact one-liners for the
README. An untested platform is a disclosed gap, not an implied pass.
