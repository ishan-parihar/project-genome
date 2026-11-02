# Cross-platform mechanics

Everything install.sh/install.ps1 need for OS, arch, package managers, PATH, and the
one-liner install commands. These are the battle-tested snippets from the zeroclaw
(sh+bat) and hermes (sh+ps1) installers — steal them verbatim.

## Bash: universal header

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

`#!/usr/bin/env bash` not `#!/bin/bash` (NixOS, macOS with newer bash). `IFS` hardening
prevents word-splitting surprises. If you need pure-POSIX reach (Alpine busybox is
fine with bash missing), drop to `#!/bin/sh` and forgo pipefail/arrays — the zeroclaw
choice; only do it when bash truly can't be assumed.

## OS detection

```bash
OS="$(uname -s)"
case "$OS" in
  Linux*)     DISTRO="$(. /etc/os-release 2>/dev/null && echo "$ID")" ;;  # debian, ubuntu, fedora, arch, alpine…
  Darwin*)    DISTRO="macos" ;;
  MINGW*|MSYS*|CYGWIN*) DISTRO="windows-gitbash" ;;   # recommend the .ps1 path instead
  *) die "Unsupported OS: $OS (this installer covers Linux and macOS; on Windows use install.ps1)"
esac
```

Distro family → package manager (the c-suite-agents 3-way branch, extended):

| Distro (from `$ID` / `$ID_LIKE`) | PM | Install prereqs |
|---|---|---|
| ubuntu, debian, mint, pop | `apt-get` | `sudo apt-get update && sudo apt-get install -y <pkgs>` |
| fedora, rhel, centos, rocky, alma | `dnf` | `sudo dnf install -y <pkgs>` |
| arch, manjaro, cachyos, endeavouros | `pacman` | `sudo pacman -Sy --needed --noconfirm <pkgs>` |
| opensuse* | `zypper` | `sudo zypper -n install <pkgs>` |
| alpine | `apk` | `sudo apk add <pkgs>` |
| macOS | `brew` | `brew install <pkgs>` (auto-install brew itself only with consent) |

Never hardcode one PM for "Linux". Check `$ID_LIKE` for derivatives (`"$(. /etc/os-release; echo "$ID_LIKE")"`).

## Arch detection (the two famous lies)

- **macOS Rosetta**: `uname -m` reports the emulated arch in an xterm session. Truth:
  ```bash
  if [ "$DISTRO" = "macos" ] && sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then ARCH="arm64"; else ARCH="$(uname -m)"; fi
  ```
- **Windows emulation**: `$env:PROCESSOR_ARCHITECTURE` lies under x86-on-ARM emulation.
  Truth from the registry (PowerShell):
  ```powershell
  $Arch = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').PROCESSOR_ARCHITECTURE
  ```

Normalize `x86_64`/`amd64` and `aarch64`/`arm64` to one canonical pair in your script.

## Libc detection (Linux, for prebuilt binaries)

```bash
detect_libc() {
  if ldd --version 2>&1 | grep -qi musl; then echo musl
  elif [ -e /lib/ld-musl-* ] 2>/dev/null; then echo musl
  else echo glibc; fi
}
```
Prefer a musl asset when present for Alpine; a glibc asset built on an old distro
(centos7-era sysroot) runs everywhere glibc. When only one exists, name the limitation
in the error, don't SEGfault for the user.

## PATH injection (idempotent or bust)

```bash
ensure_path() {  # ~/.local/bin — the standard user-bin dir on Linux AND macOS
  local dir="$1"; mkdir -p "$dir"
  case ":$PATH:" in *":$dir:"*) return 0 ;; esac
  local rc="$HOME/.zshrc"; [ -n "${ZSH_VERSION:-}" ] || rc="$HOME/.bashrc"
  [ -f "$HOME/.zshrc" ] && rc="$HOME/.zshrc"
  # .profile fallback for sh-only users
  if ! grep -qs "export PATH=\"$dir:\$PATH\"" "$rc" 2>/dev/null; then
    printf '\n# added by <name> installer\nexport PATH="%s:$PATH"\n' "$dir" >> "$rc"
  fi
  export PATH="$dir:$PATH"   # current session too
}
```

Rules: grep before append (re-runs must not duplicate); respect zsh vs bash;
print which rc file was touched. Windows (PowerShell): user-scope PATH via
`[Environment]::SetEnvironmentVariable('Path', $new, 'User')` — merge, don't overwrite,
and skip if the entry already exists.

## One-liner install commands (the README contract)

Linux/macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | bash
```
Windows (PowerShell 3+):
```powershell
irm https://raw.githubusercontent.com/<owner>/<repo>/main/install.ps1 | iex
```
CMD (thin wrapper only if the audience needs it):
```bat
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.ps1 -o "%TEMP%\install.ps1" && powershell -ExecutionPolicy Bypass -File "%TEMP%\install.ps1"
```

Rules:
- `-fsSL`, not `-sL`: fail on HTTP errors *and* show them.
- Scripts must work when piped: no `read` prompts unless a TTY is confirmed
  (`[ -t 0 ]` / `[ -t 1 ]`) — offer flags/env as the non-interactive path (`-y`, `SKIP_*`).
- **Never** `curl | sudo bash` (or `iex` an elevated script). If root is genuinely
  needed, download first, show the path, run the privileged part separately and
  narrowly (a `sudo install -m755 bin /usr/local/bin` inside the script — after the
  unprivileged download — is acceptable and auditable).
- Pin `main` (or a tag) — not `master` unless that's the default branch.
- On Windows, `irm | iex` runs in a fresh scope per pipeline: scripts must not rely on
  `$profile` state and must define functions before use.

## PowerShell: universal header

```powershell
#Requires -Version 5.1
[CmdletBinding()]
param(
  [switch]$NoCta,
  [switch]$AllHarnesses,
  [switch]$SkipHarness
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 5) { throw "PowerShell 5.1+ required" }
```
Target Windows PowerShell 5.1 *and* pwsh 7 — no C#-only syntax, no `&&` (PS5 doesn't
support it; use `;` with checks or `if ($LASTEXITCODE -ne 0) { throw }`).

Windows package managers, in preference order: `winget` (ships with modern Win10/11),
`scoop` (user-scope, no admin), `choco` (admin, most packages). Probe all three;
install prereqs through whichever exists; if none, print manual links and continue
if possible.

## Colors & output (keep it boring)

`\033[1;32m` info, `\033[1;33m` warn, `\033[1;31m` error — but only when stderr is a
TTY (`[ -t 2 ]`), else plain text (CI logs choke on codes). In PowerShell,
`Write-Host -ForegroundColor Green`. Print `>>> generated: <path> <<<` markers for
every file the installer writes (the zeroclaw convention) — users grep for these in
issue reports. End with a next-steps block (AXI §9): numbered, copy-pasteable, each
line a command that works.
