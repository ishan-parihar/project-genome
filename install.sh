#!/usr/bin/env bash
# project-genome installer — python-cli profile (uv → pipx → pip), plus the skill bundle.
#
#   curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash
#
# What it installs:
#   1. the `genome` CLI, as a Python package (pip/uv/pipx) — the tool on any machine
#   2. optionally (--skill) the project-genome SKILL bundle into the agent harnesses
#      you have — the methodology + references that accompany the CLI
#
# Flags:
#   --skill        also install the skill bundle into every detected harness
#   --dir <path>   extra skills root (repeatable) for --skill
#   --from-github  install the CLI from the Git repo instead of PyPI (unreleased builds)
#   --no-cta       skip the star/donate epilogue (also: SKIP_CTA=1)
#   --force-root   allow running as root (installs into $HOME of root)

set -euo pipefail
IFS=$'\n\t'

NAME="genome"
PKG="project-genome"
REPO="https://github.com/ishan-parihar/project-genome.git"
BRANCH="main"
TARGET_NAME="project-genome"
BIN_DIR="$HOME/.local/bin"
MIN_PY_MINOR=11

if [ -t 1 ]; then
  B=$(printf '\033[1m'); G=$(printf '\033[1;32m'); Y=$(printf '\033[1;33m'); R=$(printf '\033[1;31m'); N=$(printf '\033[0m')
else B=""; G=""; Y=""; R=""; N=""; fi
info() { printf '%s\n' "${G}==>${N} ${B}$*${N}"; }
warn() { printf '%s\n' "${Y}warn:${N} $*" >&2; }
err()  { printf '%s\n' "${R}error:${N} $*" >&2; }
die()  { err "$*"; printf '      fix it, then re-run this installer.\n' >&2; exit 1; }

# ── [SECTION: flags] ─────────────────────────────────────────────────────────
SKIP_SKILL=1
FROM_GITHUB=0
EXTRA_DIRS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --skill)       SKIP_SKILL=0; shift ;;
    --dir)         EXTRA_DIRS+=("$2"); shift 2 ;;
    --from-github) FROM_GITHUB=1; shift ;;
    --no-cta)      SKIP_CTA=1; shift ;;
    --force-root)  FORCE_ROOT=1; shift ;;
    --help|-h)     sed -n '2,16p' "$0"; exit 0 ;;
    *) die "Unknown option: $1 (supported: --skill, --dir <path>, --from-github, --no-cta, --force-root)" ;;
  esac
done

# ── [SECTION: root-guard] ───────────────────────────────────────────────────
# Root-owned ~/.local breaks every later step (the tool writes its registry and
# its cards under $HOME). Refuse by default rather than produce a broken install.
if [ "${EUID:-$(id -u)}" -eq 0 ] && [ "${FORCE_ROOT:-0}" != "1" ]; then
  die "Don't run as root — this installs into \$HOME and root-owned files break later upgrades. Re-run as your user (override: --force-root)."
fi

# ── [SECTION: os-arch] ──────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Linux*)  DISTRO="$(. /etc/os-release 2>/dev/null && echo "${ID:-unknown}")" ;;
  Darwin*) DISTRO="macos" ;;
  *) die "Unsupported OS: $OS — on Windows use install.ps1 (irm <url> | iex)" ;;
esac
ARCH="$(uname -m)"
if [ "$DISTRO" = "macos" ] && sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then
  ARCH="arm64"   # uname -m lies under Rosetta
fi
case "$ARCH" in x86_64|amd64) ARCH="x86_64" ;; aarch64|arm64) ARCH="arm64" ;; *) ARCH="unknown" ;; esac
info "platform: $OS/$DISTRO/$ARCH"

# ── [SECTION: prereqs] ──────────────────────────────────────────────────────
# The CLI is stdlib only, so the ONLY hard requirement is a Python >= 3.11
# interpreter. curl is needed only for the GitHub fallback path.
command -v python3 >/dev/null 2>&1 || die "python3 is not installed or not on PATH — project-genome needs Python >= $MIN_PY_MINOR (stdlib only, no packages to install)"
py_ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
py_ok="$(python3 -c 'import sys; print(1 if sys.version_info[:2] >= (3, 11) else 0)')"
if [ "$py_ok" != "1" ]; then
  die "python3 is $py_ver; project-genome needs >= 3.$MIN_PY_MINOR (it uses tomllib, added in 3.11). Upgrade Python, or point PATH at a newer interpreter."
fi
info "python3 $py_ver ok"

# ── [SECTION: install] the uv → pipx → pip chain ───────────────────────────
# Each rung degrades gracefully. uv is the best rung (a self-contained tool
# install, no venv juggling); pipx is the classic; pip --user is the floor.
# Nothing is installed into a system Python: PEP 668 makes that an error on
# Debian/Ubuntu, and it wrecks distro package management.
#
# The bin directory each rung lands in is RECORDED, because the verify step must
# check the binary this run installed — not whatever genome happens to sit at
# ~/.local/bin/genome already (observed: the installer verified a stale -20
# symlink while the freshly installed -21 sat in the uv tool dir).
installed_with=""
INSTALL_BIN_DIR=""
if [ "$FROM_GITHUB" = "1" ]; then
  command -v git >/dev/null 2>&1 || die "--from-github needs git — install git, or drop the flag to install from PyPI"
  info "installing from the Git repository (unreleased build)"
  if command -v uv >/dev/null 2>&1; then
    uv tool install --force --from "git+$REPO" "$PKG" && installed_with="uv (from git)"
    INSTALL_BIN_DIR="$(uv tool dir --bin 2>/dev/null || echo "$BIN_DIR")"
  elif command -v pipx >/dev/null 2>&1; then
    pipx install --force "git+$REPO" && installed_with="pipx (from git)"
    INSTALL_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$BIN_DIR")"
  else
    python3 -m pip install --user --force-reinstall "git+$REPO" && installed_with="pip (from git)"
    INSTALL_BIN_DIR="$("$HOME/.local/bin/python3" -c 'import sysconfig; print(sysconfig.get_path("scripts", scheme="posix_user"))' 2>/dev/null || echo "$BIN_DIR")"
  fi
elif command -v uv >/dev/null 2>&1; then
  info "installing with uv"
  if uv tool install --force "$PKG" 2>/dev/null; then installed_with="uv"; else
    warn "uv tool install failed — trying pipx"
    command -v pipx >/dev/null 2>&1 || die "uv could not install $PKG and pipx is not installed. Install pipx (pipx install pipx) or uv (curl -LsSf https://astral.sh/uv/install.sh | sh), then re-run."
    pipx install --force "$PKG" && installed_with="pipx"
  fi
  if [ "$installed_with" = "uv" ]; then
    INSTALL_BIN_DIR="$(uv tool dir --bin 2>/dev/null || echo "$BIN_DIR")"
  fi
elif command -v pipx >/dev/null 2>&1; then
  info "installing with pipx"
  pipx install --force "$PKG" && installed_with="pipx"
  INSTALL_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$BIN_DIR")"
else
  info "installing with pip --user"
  python3 -m pip install --user --upgrade "$PKG" && installed_with="pip --user"
  INSTALL_BIN_DIR="$(python3 -c 'import sysconfig; print(sysconfig.get_path("scripts", scheme="posix_user"))' 2>/dev/null || echo "$BIN_DIR")"
fi
[ -n "$installed_with" ] || die "the install did not report a successful method — see the errors above"
info "installed via $installed_with"

# ── [SECTION: path] idempotent PATH injection ───────────────────────────────
# uv and pipx both land in ~/.local/bin. PATH edits only prove themselves in a
# NEW shell, so the rc file is the real deliverable — and it must be written
# once: re-running this installer must not append a second copy.
ensure_path() {
  local dir="$1"
  mkdir -p "$dir" 2>/dev/null || return 1
  case ":$PATH:" in *":$dir:"*) return 0 ;; esac
  local rc="$HOME/.bashrc"
  [ -f "$HOME/.zshrc" ] && rc="$HOME/.zshrc"
  if ! grep -qs "export PATH=\"$dir:\$PATH\"" "$rc" 2>/dev/null; then
    printf '\n# added by project-genome installer: %s on PATH\nexport PATH="%s:$PATH"\n' "$dir" "$dir" >> "$rc"
    info "PATH line appended to $rc (takes effect in new shells)"
  fi
  export PATH="$dir:$PATH"
}
ensure_path "$BIN_DIR" || warn "could not create $BIN_DIR — use the export line below"

# ── [SECTION: verify] the promise this installer makes ──────────────────────
# `genome` must resolve and run. THE BINARY THIS RUN INSTALLED is what gets
# checked: on a machine that already had a genome on PATH (the skills-root
# symlink), verifying that one would report success for a stale build while the
# freshly installed copy sat unverified beside it.
GENOME_BIN=""
if [ -n "$INSTALL_BIN_DIR" ] && [ -x "$INSTALL_BIN_DIR/$NAME" ]; then
  GENOME_BIN="$INSTALL_BIN_DIR/$NAME"
fi
if [ -z "$GENOME_BIN" ]; then
  for cand in "$BIN_DIR/$NAME" "$HOME/.local/bin/$NAME"; do
    [ -x "$cand" ] && { GENOME_BIN="$cand"; break; }
  done
fi
if [ -n "$GENOME_BIN" ]; then
  export PATH="$(dirname "$GENOME_BIN"):$PATH"
  VERSION_OUT="$("$GENOME_BIN" --version 2>&1 || true)"
  case "$VERSION_OUT" in
    genome*) info "verified: $VERSION_OUT ($GENOME_BIN)" ;;
    *) die "the installed CLI did not run: $VERSION_OUT" ;;
  esac
elif command -v "$NAME" >/dev/null 2>&1; then
  info "verified: $(command -v "$NAME")"
else
  die "$NAME is not on PATH — add this to your shell profile and re-run: export PATH=\"$BIN_DIR:\$PATH\""
fi

# ── [SECTION: registry] record this install in the machine manifest ─────────
# The registry is what stops an upgrade from leaving stragglers behind: it
# names every copy, `genome installs verify` reports drift, and `genome installs
# scan` finds what the installer missed. A pip/uv install is exactly the kind
# of copy that otherwise goes untracked.
register_install() {  # register_install <kind> <path> [note]
  if "$GENOME_BIN" installs register "$1" "$2" --note "${3:-via install.sh}" >/dev/null 2>&1; then
    info "registered: $2"
  else
    warn "could not register $2 in the installs manifest — `genome installs scan` will find it"
  fi
}
[ -n "$GENOME_BIN" ] && register_install bin "$GENOME_BIN" "via install.sh ($installed_with)"

# ── [SECTION: skill] the methodology bundle (optional, off by default) ──────
# The package installs the CLI. The SKILL carries the methodology, the lint
# rule reference and the adoption guide — an agent needs that too, so it is a
# separate, explicit step rather than a surprise side effect of the CLI install.
if [ "$SKIP_SKILL" = "0" ]; then
  command -v git >/dev/null 2>&1 || die "--skill needs git to fetch the bundle (install git, or drop --skill)"
  ROOTS=()
  for d in "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.zcode/skills" "$HOME/.codex/skills"; do
    [ -d "$d" ] && ROOTS+=("$d")
  done
  for d in ${EXTRA_DIRS+"${EXTRA_DIRS[@]}"}; do ROOTS+=("$d"); done
  if [ "${#ROOTS[@]}" -eq 0 ]; then
    ROOTS+=("$HOME/.agents/skills")
    info "no harness skills directory found — using ${ROOTS[0]}"
  fi
  for root in "${ROOTS[@]}"; do
    dest="$root/$TARGET_NAME"
    mkdir -p "$root"
    if [ -d "$dest/.git" ]; then
      if git -C "$dest" fetch origin "$BRANCH" --quiet && git -C "$dest" reset --hard "origin/$BRANCH" --quiet; then
        info "updated skill: $dest"
      else
        warn "could not update $dest — is another process holding it?"
      fi
    else
      if git clone --depth 1 --branch "$BRANCH" "$REPO" "$dest" --quiet 2>/dev/null; then
        info "installed skill: $dest"
      else
        warn "could not clone the skill into $dest"
      fi
    fi
    [ -n "$GENOME_BIN" ] && register_install skill "$dest" "via install.sh --skill"
  done
fi

# ── [SECTION: summary] ──────────────────────────────────────────────────────
echo ""
echo "project-genome installed."
echo ""
echo "  genome init --profile software   # scaffold a knowledge genome"
echo "  genome wake                      # orient a fresh agent"
echo "  genome lint                      # check the roles and their mutability"
echo ""
if [ "$SKIP_SKILL" = "0" ]; then
  echo "The skill bundle is installed too — agents pick up the methodology and references."
else
  echo "The CLI is installed. For the agent methodology + references, add --skill"
  echo "(or: npx skills add ishan-parihar/project-genome --agent '*' --skill '*' -y)."
fi
echo ""

# ── [SECTION: CTA] star + donate ────────────────────────────────────────────
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
