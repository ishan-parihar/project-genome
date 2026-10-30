#!/usr/bin/env bash
# project-genome installer — python-cli profile (uv → pipx → pip), plus the skill bundle.
#
#   curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash
#
# What it installs:
#   1. the `genome` CLI, as a Python package (uv / pipx / pip) — the tool on any machine
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
# Where this install puts things that are not on a tool's own PATH: the isolated
# venv the pip rung falls back to on an externally-managed Python, and its bin.
# Defaults under XDG data so a read-only or unusual HOME cannot break the install.
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/project-genome"
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

# The bundle is a separate explicit step rather than a surprise side effect of
# the CLI install. Check the prerequisite HERE, at request time: a git-less host
# that only learns this after the CLI rungs have run is a host holding a partial
# install and a confusing tail (observed: '--skill needs git' printed after a
# bundle-less install, exit 1, with no advice in reach).
if [ "$SKIP_SKILL" = "0" ]; then
  command -v git >/dev/null 2>&1 || die "--skill needs git to fetch the bundle — install git, install the CLI without --skill, or run the CLI-only install and add the bundle later"
fi

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
#
# The last rung, and it must actually reach the floor. On Debian/Ubuntu the system
# Python is PEP 668 externally-managed, so `pip install --user` is REFUSED
# outright (verified on this host's /usr/bin/python3.14, whose
# /usr/lib/python3.14/EXTERNALLY-MANAGED makes even --user an error). A chain
# whose last rung cannot succeed on the most common Linux distros is not a chain,
# so the refusal falls back to an isolated venv — the one form of pip install that
# never needs to touch a managed Python.
#
# Every rung that can fail calls this: uv being present but unable to install
# (the package is not published yet) must reach the venv too, not stop at pipx.
# The `|| return 1` shape matters: under `set -e`, a bare `return 1` from a
# function called in a condition-less context aborts the script, which would
# kill the run before the CLI-unmet handler below (and before the --skill
# bundle) — observed with exactly that symptom.
try_pip_floor() {
  if python3 -m pip install --user --force-reinstall "$1" 2>/dev/null; then
    installed_with="pip --user${2:+ $2}"
    return 0
  fi
  if python3 -m venv "$PREFIX/tool" >/dev/null 2>&1 \
     && "$PREFIX/tool/bin/pip" install --quiet --force-reinstall "$1"; then
    installed_with="pip (isolated venv — system Python is externally-managed${2:+, $2})"
    INSTALL_BIN_DIR="$PREFIX/tool/bin"
    return 0
  fi
  return 1
}
# The caller's context decides what a failure means: `--skill` still owes the
# bundle, a CLI-only run dies with the remedy. Both are guarded call sites
# (`if ! try_pip_floor ...`) precisely so the `return 1` is NOT the last command
# of the script under `set -e` — a bare failing call here aborts the whole
# installer before the CLI-unmet handler, observed with exactly that symptom
# (the --skill bundle never ran and nothing said why).
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
    if ! try_pip_floor "git+$REPO" "from git"; then
      warn "the pip floor could not install it — see the errors above"
    fi
  fi
elif command -v uv >/dev/null 2>&1; then
  info "installing with uv"
  if uv tool install --force "$PKG" 2>/dev/null; then
    installed_with="uv"
    INSTALL_BIN_DIR="$(uv tool dir --bin 2>/dev/null || echo "$BIN_DIR")"
  else
    # The package may simply not be on PyPI yet (a first publish is the operator's
    # step). That is not a failure of the machine, so say what happened and fall
    # through to the next rung rather than dying — and with --skill on, the bundle
    # is an explicit request that must still be honoured.
    warn "uv could not install $PKG (not on PyPI yet? trying the next rung)"
    if command -v pipx >/dev/null 2>&1; then
      pipx install --force "$PKG" && { installed_with="pipx"; INSTALL_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$BIN_DIR")"; }
    fi
    # uv present but unable to install is the pre-publication case, and it must
    # still reach the floor: pipx absent (or also refusing) leaves the venv. Found
    # by running the installer: this chain stopped here and reported "the install
    # did not report a successful method" on a machine where uv existed.
    if [ -z "$installed_with" ]; then
      if ! try_pip_floor "$PKG"; then
        warn "the pip floor could not install it — see the errors above"
      fi
    fi
  fi
elif command -v pipx >/dev/null 2>&1; then
  info "installing with pipx"
  pipx install --force "$PKG" && installed_with="pipx"
  INSTALL_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$BIN_DIR")"
  # pipx present but refusing (it delegates to the same PEP 668 refusal): fall to
  # the floor rather than leaving the operator with no CLI.
  if [ -z "$installed_with" ]; then
    if ! try_pip_floor "$PKG"; then
      warn "the pip floor could not install it — see the errors above"
    fi
  fi
else
  info "installing with pip"
  if ! try_pip_floor "$PKG"; then
    warn "the pip floor could not install it — see the errors above"
  fi
fi
# The CLI is the point of the script, but a --skill run has a second explicit
# request. When the package cannot be installed (typically: not published yet) and
# --skill is on, the bundle still gets installed and the CLI install is reported as
# unmet rather than aborting the run.
CLI_UNMET=0
if [ -z "$installed_with" ]; then
  if [ "$SKIP_SKILL" = "0" ]; then
    warn "the CLI package could not be installed — installing the skill bundle anyway"
    CLI_UNMET=1
  else
    die "the install did not report a successful method — see the errors above (the package may not be published yet: try --from-github)"
  fi
else
  info "installed via $installed_with"
fi

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
  # assign separately from the export: SC2155 — a failed substitution inside an
  # export's command substitution is masked, and here it would hide a broken bin dir
  BIN_DIR_FOUND="$(dirname "$GENOME_BIN")"
  export PATH="$BIN_DIR_FOUND:$PATH"
  VERSION_OUT="$("$GENOME_BIN" --version 2>&1 || true)"
  case "$VERSION_OUT" in
    genome*) info "verified: $VERSION_OUT ($GENOME_BIN)" ;;
    *) die "the installed CLI did not run: $VERSION_OUT" ;;
  esac
elif [ "$CLI_UNMET" = "1" ]; then
  # nothing was installed to verify, and an existing genome on PATH is not this
  # run's artifact: say so rather than printing a success it did not earn
  warn "no installed CLI to verify — the bundle install stands on its own"
elif command -v "$NAME" >/dev/null 2>&1; then
  # a copy exists, but this run never installed it: not this installer's success
  warn "the newly installed CLI was not found; a different copy is at $(command -v "$NAME") — re-run install.sh"
else
  die "$NAME is not on PATH — add this to your shell profile and re-run: export PATH=\"$BIN_DIR:\$PATH\""
fi

# Only the verified binary registers. register_install calls $GENOME_BIN, so an
# empty one would otherwise silently fall back to whatever genome is on PATH —
# registering a copy this run did not install, and recording it as this run's.

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
      # A checkout of this REPO. The update is a fetch+reset against origin/main, which
      # is safe for the skill (its only local files are genome-owned) but DESTRUCTIVE
      # inside a repo that vendors scripts/genome and has its own uncommitted work
      # there — observed: a reset --hard silently discarded a working-tree change in
      # operant's vendored copy. So refuse the reset when the repo carries a DIFFERENT
      # skill checkout inside its own tree, and say what to run instead.
      if [ -e "$dest/scripts/genome" ] && ! git -C "$dest" diff --quiet -- scripts/genome 2>/dev/null; then
        warn "$dest has its own uncommitted scripts/genome — not resetting it"
        warn "  inspect it with: git -C $dest diff -- scripts/genome"
        warn "  upgrade that copy with: genome installs upgrade --apply (from inside $dest)"
        continue
      fi
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
if [ "$CLI_UNMET" = "1" ]; then
  echo "The skill bundle is installed. The CLI package could NOT be installed."
  echo ""
  echo "  Usually this means $PKG is not on PyPI yet. Install the CLI with:"
  echo "    curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash -s -- --from-github"
  echo ""
  if [ "$installed_with" != "" ]; then
    echo "  (it installed via $installed_with, so only the verification fell short"
    echo "   — the binary did not resolve; check the PATH line above)"
  fi
  # The remedy above is only actionable if the machine can take it: --from-github
  # needs git and needs the network. Say so instead of sending the operator back
  # down a path this same machine just refused (observed on a host where both
  # git and the PyPI rung were unavailable, and the advice repeated the failure).
  if ! command -v git >/dev/null 2>&1; then
    echo ""
    echo "  This machine has no git, and --from-github needs it. Install git first,"
    echo "  or install the CLI by hand:  python3 -m pip install --user $PKG"
    echo "  (if pip refuses with 'externally-managed-environment', your Python is"
    echo "   PEP 668 managed — use a venv:  python3 -m venv ~/.local/share/$PKG/tool &&"
    echo "   ~/.local/share/$PKG/tool/bin/pip install $PKG)"
  fi
  echo ""
else
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
