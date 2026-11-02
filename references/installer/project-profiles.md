# Project Profiles — pick, then follow the recipe

Decision table first, then one recipe per profile. Hybrids compose: install the
user-facing artifact, then wire extras as offers (see SKILL.md step 4).

## Decision table

| If the project is… | Profile | Install core | Extras to offer |
|---|---|---|---|
| Python CLI on PyPI or GitHub | `python-cli` | uv tool → pipx → pip chain | manager-owned updates; MCP wiring if it exposes one |
| Node/TS CLI on npm or GitHub | `node-cli` | npm i -g (bun fallback) | manager-owned updates; npx-run mode if stateless |
| Rust/Go prebuilt binaries on GitHub releases | `rust-binary` | verified release download | embedded updater; cargo install fallback |
| MCP server (any language) | `mcp-server` | underlying runtime profile | per-harness registration (mcp-wiring.md) |
| Repo of SKILL.md bundles | `skill-bundle` | `npx skills add` | manual dirs for family harnesses |
| Long-running daemon/service | `local-server` | runtime + systemd unit | user-level unit first |
| docker compose stack | `docker-selfhost` | compose + .env from example | update/uninstall path |
| Importable library | `library` | version check + examples | none — say so in output |

---

## python-cli

The uv → pipx → pip chain, proven across the `*-lyr` family. Each rung degrades
gracefully: try uv, on failure warn and try pipx, on failure warn and try pip, on
failure die with the manual command.

**Prereqs:** Python ≥ the project's minimum (scan interpreters `python3.13 … python3.10`
like tg-cli does), curl, git. Install missing curl/git via the package-manager matrix
(see cross-platform.md).

**Install:**
```bash
if command -v uv >/dev/null; then
  uv tool install --from "git+https://github.com/<owner>/<repo>" <cli>   # or: uv tool install <pypi-name>
elif command -v pipx >/dev/null; then
  pipx install "git+https://github.com/<owner>/<repo>" || pipx install <pypi-name>
else
  pip install --user <pypi-name>
fi
```
Offer to auto-install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`) when absent
— it's the best rung; don't force it.

**Verify:** `command -v <cli> && <cli> --version` — and if the tool is AXI-compliant,
`<cli>` with no args should print its home view (AXI §8), which doubles as the verify.

**Pitfalls:**
- Debian/Ubuntu: never bare `pip install` into system Python — `--user` or venv only,
  or you fight distro packaging (PEP 668 externally-managed error).
- uv/pipx land in `~/.local/bin` — PATH injection is mandatory, not optional.
- Pin the minimum Python version with an explicit check that names the interpreter it
  found and the one it needs.
- Root guard: refuse to run as root (`EUID -eq 0`) unless `--force-root`; root-owned
  `~/.local` breaks everything downstream.

**Updates:** pipx/uv/pip own their installed files. The CLI's `update` command
delegates to that manager or prints the precise upgrade command. Do not make the
Python process overwrite its own package files.

## node-cli

**Prereqs:** node ≥ engines field, npm. Install npm itself via nodesource/nvm when absent.

**Install:** `npm install -g <name>@<repo-url>` (or plain `npm i -g <name>` if published).
If the audience uses bun: `bun install -g <name>` as an alternative rung.

**Verify:** `command -v <cli> && <cli> --version`.

**Pitfalls:**
- Global npm needs `sudo` on some setups — prefer the user's nvm/configured prefix;
  detect a user-writable prefix and only then suggest sudo, or offer `npx <name>` as
  the zero-install mode for occasional use.
- Binary shim name may differ from package name (package.json `bin` field) — install
  the package but *verify* the shim.

**Updates:** npm/bun own global installs. The CLI delegates to its recorded manager
or prints the exact command; only a separately distributed standalone bundle can
use a self-replacing binary updater.

## rust-binary

GitHub Releases carry prebuilt assets per (arch, libc); the installer picks and
verifies. The installed standalone binary also embeds an updater from
`references/updater-architecture.md`; the installer is a bootstrap path, not the
only way to update.

**Preflight:** arch (`uname -m`, cross-platform.md), libc (glibc vs musl), then
resolve the release asset: `<name>-<version>-<arch>-<libc>.tar.gz` naming convention
(whatever the project actually publishes — read its release page once).

**Install:**
```bash
curl -fsSL -o "$tmp/<asset>" "https://github.com/<owner>/<repo>/releases/download/v<ver>/<asset>"
echo "<sha256>  $tmp/<asset>" | sha256sum -c -   # digest fetched from a second source: releases/<ver>/SHA256SUMS
tar -xzf "$tmp/<asset>" -C "$tmp"
install -m 0755 "$tmp/<name>" "$HOME/.local/bin/<name>"
```
For compatibility updaters, fetch a digest from a separately trusted source; a
checksum from the same origin as the payload detects corruption, not publisher
compromise. The suite standard is TUF metadata and a maintained client, as defined
in `references/updater-architecture.md`.

**Fallback:** `cargo install --git https://github.com/<owner>/<repo> --locked` when no
prebuilt matches (slow — warn first).

If the binary was installed with `cargo install`, leave updates to Cargo. The
embedded self-updater is for the standalone release binary only.

**Pitfalls:** musl builds run everywhere but are slower; when both exist, prefer glibc
on glibc systems. macOS aarch64: `uname -m` under Rosetta reports the *emulated* arch —
use `sysctl -n hw.optional.arm64` truth (cross-platform.md).

## mcp-server

The project ships an MCP server (stdio or HTTP). Two install layers:

1. **Transport-agnostic core** — install the server binary/package per its language
   profile (python-cli/node-cli/rust-binary above).
2. **Registration** — MCP servers do nothing until a harness registers them. This is
   the harness-integration step (SKILL.md step 4): offer registration into every
   detected harness, using `references/mcp-wiring.md` snippets. Always also write a
   standalone `.mcp.json` in the project root — the portable convention multiple
   harnesses read — and print it so users of unlisted harnesses can paste manually.

**Verify:** run the server's own health path — for stdio servers, a
`timeout 5 <command>` that exits without "connection refused"; for HTTP, curl the
health endpoint. Then verify registration in one harness (`claude mcp list` /
`codex mcp list` / `opencode mcp`) before claiming success.

**Pitfalls:** stdio servers registered with a relative command break when the harness's
cwd differs — always write absolute paths into registrations. Env-var-shaped secrets:
support `env` passthrough in the registration rather than baking values.

## skill-bundle

The repo's product is one or more SKILL.md directories.

**Install:** canonical command is the vercel-labs skills CLI —
`npx skills add <owner>/<repo> --agent <agents> --skill <skills> -y`
(`--agent '*'` for all installed harnesses; the full 79-name registry and per-agent
skill directories are in `references/harness-matrix.md`). The installer's job:
detect which of the 79 are installed, show them, run the add for the selected ones.

**Family harnesses not in the registry** (zeroclaw, omp, omo) get manual placement —
see harness-matrix.md §3 for their directory conventions and the holon 5-step adapter
contract for any harness not covered.

**Verify:** `npx skills ls` after install; for manual placements, test the directory
exists and SKILL.md frontmatter parses (name + description keys present).

**Pitfalls:** symlinking (the skills CLI default) breaks for harnesses that can't
follow symlinks or for synced-home setups — `--copy` is the escape hatch. Keep
canonical skill files in the repo and point bundles at them (zeroclaw's
`skill_bundles` pattern) rather than duplicating content.

## local-server

The daemon/systemd pattern from c-suite-agents and lifeos-bot.

**Order of operations:** prereqs → install runtime + app (language profile) →
`.env` from `.env.example` (chmod 600, never overwrite existing) → **user-level
systemd first** (`systemctl --user`, `~/.config/systemd/user/`), fall back to a
system unit only with consent → `systemctl --user daemon-reload && enable --now` →
health check.

An automatic update timer calls the CLI's update-only mode. Restart only a service
that was active before the update; verify health and restore the prior binary if
startup fails. Do not fetch and run a mutable installer URL from a timer.

**System-unit fallback hardening** (only when user-level can't work, e.g. needs
system resources): `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=read-only`
+ explicit `ReadWritePaths=`, `MemoryMax`, `SystemCallFilter=@system-service`,
`EnvironmentFile=` for secrets. Ship a logrotate drop-in for file logs.

**Pitfalls:** two sources of the same secret (`.env` AND config.json) is the lifeos/
c-suite bug class — pick one source of truth, document it. User-level units need
`loginctl enable-linger <user>` to survive logout — mention it. Health-check before
printing "installed": `systemctl --user is-active` + the app's own endpoint.

## docker-selfhost

The lifeos-saas bootstrap pattern.

**Prereqs:** docker + compose plugin (install via get.docker.com convenience script
*with a warning*, or point at the distro package; never silently curl|sudo a script —
print what it does first). git for pulling dependent repos.

**Install:**
1. `git clone` (or pull) the repo
2. `cp .env.example .env` if absent (chmod 600); prompt only for secrets the compose
   file actually requires, print the rest as "review later"
3. `docker compose build` (or `pull` if images are published) → `docker compose up -d`
4. Health check: the compose healthcheck / a known endpoint with retry loop
   (e.g. `until curl -sf http://localhost:<port>/health; do sleep 2; done` — capped)

**Also ship:** an `update.sh` that selects a digest-pinned image, waits for its
health check, restores the prior digest on failure, and an `uninstall.sh` or
documented `down -v` command. Self-hosters judge projects by the exit path.

**Pitfalls:** never generate secrets silently — print generated passwords once and
say where they were written. Port collisions: detect listener in use and suggest an
override (`<port>:` env substitution) instead of failing opaque.

## library

If the project is only ever consumed as a dependency (pip/npm/cargo), do not generate
a standalone installer — say that in your answer. What helps instead: a `pip install -e .`
/ `npm link` dev-setup snippet in the README, and version-guard at import time
(`requires-python`, `engines`, `rust-version`) so the *package manager* does the
checking. Generating an installer for a library is the classic over-delivery mistake.
