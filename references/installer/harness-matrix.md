# Harness compatibility matrix

How to make a tool/skill/MCP server land in every agentic harness the user runs.
Three worlds: (1) the `npx skills` registry — 79 harnesses, one command; (2) the
family harnesses (zeroclaw, omp, omo) — manual placement; (3) unknown harnesses —
the holon 5-step adapter contract.

## 1. The `npx skills` registry (vercel-labs `skills` CLI)

Install skills into specific harnesses:

```bash
npx skills add <owner>/<repo>                  # interactive picker (lists detected agents)
npx skills add <owner>/<repo> --agent '*' --skill '*' -y   # every installed harness
npx skills add <owner>/<repo> --agent claude-code,codex -y # specific harnesses
npx skills add <owner>/<repo> --copy           # copy files instead of symlinks
npx skills ls                                   # verify what's installed
```

Project-level vs global: default is project-scope when run inside a project,
global (user) otherwise; `-g` forces global. Skills land in each harness's skills
directory — table below. **Global dir rule**: harnesses whose project dir is
`.agents/skills` use global `~/.agents/skills`; the rest use `~/.<dirname>/skills`
(exceptions: claude-code → `~/.claude/skills`; windsurf → `~/.codeium/windsurf/skills`;
tabnine-cli → `~/.tabnine/agent/skills`).

### Registry (skills CLI v1.7.2, 79 harnesses) — project-level skills dir per harness

| Agent ID | Display name | Skills dir |
|---|---|---|
| adal | AdaL | `.adal/skills` |
| aider-desk | AiderDesk | `.aider-desk/skills` |
| amp | Amp | `.agents/skills` |
| antigravity | Antigravity | `.agents/skills` |
| antigravity-cli | Antigravity CLI | `.agents/skills` |
| astrbot | AstrBot | `data/skills` |
| augment | Augment | `.augment/skills` |
| autohand-code | Autohand Code CLI | `.autohand/skills` |
| bob | IBM Bob | `.bob/skills` |
| claude-code | Claude Code | `.claude/skills` |
| cline | Cline | `.agents/skills` |
| codearts-agent | CodeArts Agent | `.codeartsdoer/skills` |
| codebuddy | CodeBuddy | `.codebuddy/skills` |
| codemaker | Codemaker | `.codemaker/skills` |
| codestudio | Code Studio | `.codestudio/skills` |
| codex | Codex | `.agents/skills` |
| command-code | Command Code | `.commandcode/skills` |
| continue | Continue | `.continue/skills` |
| cortex | Cortex Code | `.cortex/skills` |
| crush | Crush | `.crush/skills` |
| cursor | Cursor | `.agents/skills` |
| deepagents | Deep Agents | `.agents/skills` |
| devin | Devin for Terminal | `.devin/skills` |
| dexto | Dexto | `.agents/skills` |
| droid | Droid | `.agents/skills` |
| eve | Eve | `agent/skills` |
| firebender | Firebender | `.agents/skills` |
| forgecode | ForgeCode | `.forge/skills` |
| fx | fx | `.fx/skills` |
| gemini-cli | Gemini CLI | `.agents/skills` |
| github-copilot | GitHub Copilot | `.agents/skills` |
| goose | Goose | `.goose/skills` |
| grok | Grok Build | `.grok/skills` |
| hermes-agent | Hermes Agent | `.hermes/skills` |
| iflow-cli | iFlow CLI | `.iflow/skills` |
| inference-sh | inference.sh | `.inferencesh/skills` |
| jazz | Jazz | `.jazz/skills` |
| junie | Junie | `.junie/skills` |
| kilo | Kilo Code | `.agents/skills` |
| kimchi | Kimchi | `.kimchi/skills` |
| kimi-code-cli | Kimi Code CLI | `.agents/skills` |
| kiro-cli | Kiro CLI | `.kiro/skills` |
| kode | Kode | `.kode/skills` |
| lingma | Lingma | `.lingma/skills` |
| loaf | Loaf | `.agents/skills` |
| mcpjam | MCPJam | `.mcpjam/skills` |
| minimax-code | MiniMax Code | `.minimax/skills` |
| mistral-vibe | Mistral Vibe | `.vibe/skills` |
| moxby | Moxby | `.moxby/skills` |
| mux | Mux | `.mux/skills` |
| neovate | Neovate | `.neovate/skills` |
| ona | Ona | `.ona/skills` |
| openclaw | OpenClaw | `skills` |
| opencode | OpenCode | `.agents/skills` |
| openhands | OpenHands | `.openhands/skills` |
| pi | Pi | `.agents/skills` |
| pochi | Pochi | `.pochi/skills` |
| posit-assistant | Posit Assistant | `.posit/assistant/skills` |
| promptscript | PromptScript | `.agents/skills` |
| qoder | Qoder | `.qoder/skills` |
| qoder-cn | Qoder CN | `.qoder/skills` |
| qwen-code | Qwen Code | `.qwen/skills` |
| reasonix | Reasonix | `.reasonix/skills` |
| replit | Replit | `.agents/skills` |
| roo | Roo Code | `.roo/skills` |
| rovodev | Rovo Dev | `.rovodev/skills` |
| sarvam-code | Sarvam Code | `.agents/skills` |
| tabnine-cli | Tabnine CLI | `.tabnine/agent/skills` |
| terramind | Terramind | `.terramind/skills` |
| tinycloud | Tinycloud | `.tinycloud/skills` |
| trae | Trae | `.trae/skills` |
| trae-cn | Trae CN | `.trae/skills` |
| universal | Universal | `.agents/skills` |
| warp | Warp | `.agents/skills` |
| windsurf | Windsurf | `.windsurf/skills` |
| zcode | ZCode | `.zcode/skills` |
| zed | Zed | `.agents/skills` |
| zencoder | Zencoder | `.zencoder/skills` |
| zenflow | Zenflow | `.zencoder/skills` |

## 2. Family harnesses (not in the registry) — manual placement

| Harness | Skills location | Convention |
|---|---|---|
| zeroclaw | `~/.zeroclaw/config.toml` → `[skill_bundles.<name>]` pointing at canonical skill dirs | keep canonical SKILL.md dirs where they live (e.g. an organism/ repo); register bundles by path — never duplicate content. MCP tools: `[mcp]` section, keep `deferred_loading = true` for large tool surfaces |
| omp | `~/.omp/agent/skills/` (+ `~/.omp/agent/managed-skills/` for agent-managed), project-level `.omp/skills/` | plain SKILL.md directories; MCP wiring is harness-internal — skills placement is the reliable integration path |
| omo | `~/.omo/agent/skills/` | plain SKILL.md directories |
| hermes-agent | `~/organism/skills/` (also in the npx registry as `hermes-agent`) | registry install works; manual = copy/symlink SKILL.md dirs into `~/organism/skills/` |

## 3. Unknown harness — the holon 5-step adapter contract

Proven across zeroclaw/hermes/jcode/operant/claude-code adapters (holon). Follow it
in order for any harness not in the tables above:

1. **Detect**: `shutil.which(<bin>)` + a capability probe — the binary exists AND
   answers a support question (e.g. `<bin> agent --help` must show the flag you rely
   on). Version-gate: if the capability is missing, refuse with a distinct exit
   code and a one-line upgrade hint (holon uses exit 2; regression-test it by
   probing a fake old binary).
2. **Export skills** into the harness's skills directory (registry dir if known,
   else `<bin> --help`/docs; when the harness has no skills concept, skip — never
   dump files into an invented directory).
3. **Write harness-native config** (driver/driver.toml or equivalent) with
   placeholders filled from detected paths.
4. **Validate before write**: parse every generated TOML/JSON (`tomllib.loads`,
   `json.loads`) — never write config that fails to parse.
5. **Verify after write**: run the harness's own list/version command to confirm
   registration actually took.

## 4. Detection loop for installers

Detect-then-offer (never force). In install.sh:

```bash
detect_harnesses() {
  FOUND=""
  for h in claude codex opencode gemini qwen grok goose hermes zeroclaw omp omo pi droid; do
    command -v "$h" >/dev/null 2>&1 && FOUND="$FOUND $h"
  done
  echo "$FOUND" | xargs -n1 echo  # space-separated list, print one per line
}
```

Offer registration for each found harness; default yes in TTY, `--all-harnesses`/
`--no-harness`/`SKIP_HARNESS=1` to override, skip silently in CI (no TTY). For
registry harnesses delegate to `npx skills add`; for family harnesses use the table
in §2; for anything else the §3 contract.

MCP server registration (a different table) is in `mcp-wiring.md`.
