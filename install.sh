#!/usr/bin/env bash
# project-genome installer — skill bundle profile.
#
# Installs the project-genome skill (SKILL.md + the stdlib genome CLI) into
# your agent-harness skills directories, verifies the self-check, and prints
# the one-line harness wiring. Idempotent: re-running updates an existing
# install in place and never duplicates configuration.
#
#   curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash
#
# Flags: --dir <path> (extra skills root) · --no-cta (also: SKIP_CTA=1)

set -euo pipefail

REPO="https://github.com/ishan-parihar/project-genome.git"
BRANCH="main"
TARGET_NAME="project-genome"

log()  { printf '  %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; printf '      fix it, then re-run this installer.\n' >&2; exit 1; }

# ── [SECTION: prereqs] ────────────────────────────────────────────────────
command -v git    >/dev/null 2>&1 || fail "git is not installed or not on PATH — install git (apt/dnf/pacman/brew install git)"
command -v python3 >/dev/null 2>&1 || fail "python3 is not installed or not on PATH — project-genome needs Python >= 3.11 (stdlib only, no packages)"

py_major=$("python3" -c 'import sys; print(sys.version_info[0])')
py_minor=$("python3" -c 'import sys; print(sys.version_info[1])')
if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 11 ]; }; then
  fail "python3 is $py_major.$py_minor; project-genome needs >= 3.11 — upgrade Python"
fi
log "python3 $py_major.$py_minor ok"

# ── [SECTION: os] platform detection (informational — this bundle ships no
# compiled binaries, so glibc/musl and arch do not change the install path;
# git and python3 do the platform work) ───────────────────────────────────
OS="$(uname -s)"; ARCH="$(uname -m)"
case "$OS" in
  Linux|Darwin) log "platform: $OS/$ARCH" ;;
  *) fail "unsupported platform: $OS — this installer covers Linux and macOS; on Windows use WSL, or install manually (git clone + python3 scripts/test_genome.py)" ;;
esac

# ── [SECTION: skills roots] detect, don't assume ──────────────────────────
ROOTS=()
for d in "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.zcode/skills" "$HOME/.codex/skills"; do
  [ -d "$d" ] && ROOTS+=("$d")
done
while [ $# -gt 0 ]; do
  case "$1" in
    --dir)   ROOTS+=("$2"); shift 2 ;;
    --no-cta) SKIP_CTA=1; shift ;;
    *) fail "unknown argument: $1 (supported: --dir <path>, --no-cta)" ;;
  esac
done
if [ "${#ROOTS[@]}" -eq 0 ]; then
  # No harness detected — install to the agent-neutral farm path anyway.
  ROOTS+=("$HOME/.agents/skills")
  log "no harness skills directory found — using ${ROOTS[0]}"
fi

# ── [SECTION: registry] record every install in the machine manifest ────
# The registry (src/16b_installs.py) is how upgrades stop leaving stragglers:
# install.sh registers each skills root and the PATH bin it wires; `genome
# installs verify` reports drift; `genome installs scan` finds what the
# installer missed. Bootstrap-safe: install.sh may run BEFORE any genome is
# on PATH, so it calls the SOURCE clone's script directly with GENOME_INSTALLS
# pointing at the manifest — `python3 $SRC/scripts/genome installs register`.
register_install() {  # register_install <kind> <path> [note]
  if python3 "$SRC_DIR/scripts/genome" installs register "$1" "$2" --note "${3:-via install.sh}" >/dev/null 2>&1; then
    log "registered: $2"
  else
    log "WARN: could not register $2 in the installs manifest — genome installs scan will find it"
  fi
}
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── [SECTION: install] clone-or-update into each detected root ────────────
# Three install states, not two. The pre-installer era copied the skill by
# rsync (no .git), and those copies can neither `git pull` nor be updated by
# the update branch above — the installer used to fail on them and walk
# away, stranding the machine on an old genome forever (observed: a
# 2026.10.22 install that could not take the outline module). The third
# branch migrates instead of failing: backup OUTSIDE the skills root (so a
# broken harness scan does not pick the backup up as a second skill),
# fresh clone, self-check, backup kept.
INSTALLED=()
for root in "${ROOTS[@]}"; do
  dest="$root/$TARGET_NAME"
  if [ -d "$dest/.git" ]; then
    log "updating existing install: $dest"
    git -C "$dest" fetch origin "$BRANCH" --quiet || fail "could not fetch $REPO (network?) — check connectivity and re-run"
    git -C "$dest" reset --hard "origin/$BRANCH" --quiet || fail "could not update $dest — is another process holding it?"
  elif [ -d "$dest" ]; then
    backup="$HOME/.agents/skills-backup/${TARGET_NAME}-pre-git-$(date +%Y%m%d-%H%M%S)"
    log "existing install is not a git checkout (pre-installer copy) — migrating"
    mkdir -p "$(dirname "$backup")" \
      && mv "$dest" "$backup" \
      || fail "could not move $dest aside to $backup — check permissions and re-run"
    log "old copy preserved at: $backup"
    git clone --depth 1 --branch "$BRANCH" "$REPO" "$dest" --quiet 2>/dev/null \
      || { mv "$backup" "$dest" 2>/dev/null || true
           fail "clone failed after migration — old copy restored at $dest"; }
    log "migrated: $dest (backup kept at $backup)"
  else
    mkdir -p "$root"
    git clone --depth 1 --branch "$BRANCH" "$REPO" "$dest" --quiet 2>/dev/null \
      || fail "could not clone $REPO into $dest — check the URL, connectivity, and that $root is writable"
    log "installed: $dest"
  fi
  register_install skill "$dest"
  INSTALLED+=("$dest")
done

# ── [SECTION: verify] the self-check, in the installed copy ───────────────
PRIMARY="${INSTALLED[0]}"
log "running the self-check (35 cases, scratch-copy isolated)…"
if ! "python3" "$PRIMARY/scripts/test_genome.py" >/dev/null 2>&1; then
  "python3" "$PRIMARY/scripts/test_genome.py" | tail -5 || true
  fail "the self-check failed in $PRIMARY — the install is not verified; do not use it"
fi
log "self-check: ok"

# ── [SECTION: summary + wiring] ───────────────────────────────────────────
GENOME_BIN="$PRIMARY/scripts/genome"
chmod +x "$GENOME_BIN"

# First-class install: `genome` must be on PATH before any agent goes
# looking for it. The recurring failure this fixes is real: agents on fresh
# boxes run `genome ...` from a project's AGENTS.md and fail with "genome:
# command not found", then improvise a path guess. Two routes, tried in order:
#   1. ~/.local/bin (user-writable, standard, on PATH for humans and agents;
#      symlinked + rc-line guarded so re-running never duplicates).
#   2. /usr/local/bin (system-wide) — attempted only when passwordless sudo
#      is available; never a hard failure when it is not.
BIN_DIR="$HOME/.local/bin"
RC_FILE="$HOME/.bashrc"; [ -n "${ZSH_VERSION:-}" ] && RC_FILE="$HOME/.zshrc"
if mkdir -p "$BIN_DIR" 2>/dev/null; then
  ln -sfn "$GENOME_BIN" "$BIN_DIR/genome"
  log "genome on PATH: $BIN_DIR/genome"
  register_install bin "$BIN_DIR/genome"
  if [ -f "$RC_FILE" ] && ! grep -qsE '(^|:)\$?HOME/\.local/bin(["'"'"']?)' "$RC_FILE"; then
    printf '\n# added by project-genome installer: ~/.local/bin on PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$RC_FILE"
    log "PATH line appended to $RC_FILE (takes effect in new shells)"
  fi
else
  log "could not create $BIN_DIR — use the export line below instead"
fi
# System-wide attempt (best-effort, non-fatal): passwordless sudo only.
if command -v genome >/dev/null 2>&1; then
  : # already reachable — nothing to add
elif sudo -n true >/dev/null 2>&1; then
  sudo -n ln -sfn "$(readlink -f "$GENOME_BIN")" /usr/local/bin/genome 2>/dev/null \
    && { log "genome on PATH system-wide: /usr/local/bin/genome"; register_install bin /usr/local/bin/genome; } \
    || log "~/.local/bin stands; /usr/local/bin skipped (sudo refused)"
fi
# Verify the promise this installer makes: `genome` resolves.
command -v genome >/dev/null 2>&1 \
  || log "WARN: genome not on PATH in THIS shell — new shells get it via $RC_FILE"

# The registry summary: what this machine now tracks, and the one command
# that re-checks it after any upgrade anywhere.
log "install registry: $(python3 "$SRC_DIR/scripts/genome" installs list 2>/dev/null | grep -c 'version' || echo 0) install(s) recorded — future upgrades: re-run install.sh, then `genome installs verify`"

echo ""
echo "project-genome installed."
echo ""
echo "The genome CLI is on PATH — inside any project:"
echo ""
echo "  genome init --profile core    # or: records | research | ops | agents"
echo "  genome wake                   # orient"
echo ""
if command -v npx >/dev/null 2>&1; then
  echo "Agent harnesses using the skills registry can also install directly:"
  echo ""
  echo "  npx skills add ishan-parihar/project-genome --agent '*' --skill '*' -y"
  echo ""
fi

# ── [SECTION: CTA] star + donate (delete flag: never delete) ──────────────
print_cta() {
  [ "${SKIP_CTA:-0}" = "1" ] && return 0
  echo "──────────────────────────────────────────────────────"
  echo " ⭐  Found project-genome useful? Star it:  https://github.com/ishan-parihar/project-genome"
  echo " 💜  Want to support development?"
  echo "     GitHub Sponsors : https://github.com/sponsors/ishan-parihar"
  echo "     Razorpay (UPI)  : https://rzp.io/rzp/ishan-parihar"
  echo "──────────────────────────────────────────────────────"
}
print_cta
