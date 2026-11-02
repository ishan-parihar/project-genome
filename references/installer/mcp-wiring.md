<!-- DEAD PATH (2026-10-20): the `~/.hermes/...` reference(s) in this file point at subsystems deleted with the hermes runtime; the live equivalents, if any, are under `~/organism/`. -->
# MCP server wiring — per-harness registration snippets

An MCP server is inert until a harness registers it. The installer should: detect
harnesses (harness-matrix.md §4), offer registration for each, and always write the
portable `.mcp.json` as a fallback artifact. Absolute paths only — a stdio command
registered relative breaks the moment the harness's cwd differs.

## Portable: `.mcp.json` (project root)

The de-facto portable convention (Claude Code and several others read it natively).
Ship it in the repo; the installer prints it for manual paste:

```json
{
  "mcpServers": {
    "<name>": {
      "command": "/absolute/path/to/<server>",
      "args": ["--stdio"],
      "env": { "<KEY>": "..." }
    }
  }
}
```

## Claude Code

```bash
# user scope (machine-wide), project scope with -s project
claude mcp add <name> -s user -- /absolute/path/to/<server> --stdio
claude mcp list                                   # verify
claude mcp add <name> -s user -e KEY=value -- <cmd> <args>   # with env passthrough
```

## Codex CLI

`~/.codex/config.toml`:

```toml
[mcp_servers.<name>]
command = "/absolute/path/to/<server>"
args = ["--stdio"]
```

Verify: run `codex` and check the tools appear; `codex mcp list` on newer builds.

## OpenCode

`~/.config/opencode/opencode.json` (user) or `opencode.json` (project):

```json
{
  "mcp": {
    "<name>": {
      "type": "local",
      "command": ["/absolute/path/to/<server>", "--stdio"],
      "enabled": true
    }
  }
}
```

Verify: `opencode` → tools list.

## Gemini CLI

```bash
gemini mcp add <name> -- /absolute/path/to/<server> --stdio
gemini mcp list        # verify
```
(Lands in `~/.gemini/settings.json` `mcpServers`.)

## Claude Desktop (local app, not Code)

Config at (macOS) `~/Library/Application Support/Claude/claude_desktop_config.json`,
(Windows) `%APPDATA%\Claude\claude_desktop_config.json` — same `mcpServers` JSON as
`.mcp.json`. Merge, never overwrite; requires app restart.

## zeroclaw

`~/.zeroclaw/config.toml` — add an `[mcp]` server entry following the schema of the
user's existing config (zeroclaw's MCP section format; keep the tool surface deferred
— `deferred_loading = true` — for servers exposing dozens of tools, so the model
discovers them via tool search instead of paying for always-on schema). Probe
`zeroclaw --help` and mirror an existing entry's shape. Verify by starting a session
and listing tools.

## hermes-agent

`~/.hermes/` — hermes has its own MCP/config surface (`hermes --help`, existing
`~/.hermes/config*`); mirror the installed config's format. Skills, at least, are
registry-covered (`npx skills add <repo> --agent hermes-agent -y` → `~/organism/skills`).

## omp (oh-my-pi)

`~/.omp/agent/mcp.json` (JSON, verified format from the oh-my-pi schema):

```json
{
  "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
  "enabledServers": ["<name>"],
  "mcpServers": {
    "<name>": { "type": "stdio", "command": "/absolute/path/to/<server>", "args": ["--stdio"], "enabled": true }
  }
}
```

Rules: add your server under `mcpServers` AND list its name in `enabledServers` (that
array is what turns it on); merge, never overwrite; `type` is `"stdio"` or `"http"`
(with `url`). Verify by starting omp and confirming the tools load. Permissions on
the live file are `600` — preserve that when writing.

## omo

No verified user-editable MCP file — skills placement (`~/.omo/agent/skills/`) is the
reliable integration path. State that plainly in installer output rather than guessing
config keys.

## Everything else (the honest default)

For a harness not covered above: print the `.mcp.json` snippet and the harness's
own docs command (`<bin> mcp --help` is increasingly a convention). Never write to
a config file whose schema you haven't confirmed — a corrupt harness config is worse
than no registration.

## Rules recap

1. Absolute paths in every registration.
2. Secrets via `env` passthrough keys — never baked values.
3. Offer per-harness; skip non-interactive (CI) by default.
4. Verify with the harness's own list command before claiming success.
5. Merge existing config files; never clobber.
6. Print the `.mcp.json` snippet at the end regardless — it's the manual fallback.
