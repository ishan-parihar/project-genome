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
# The skill takes ONE real copy at the canonical root (~/.agents/skills, the only
# root a skills-backup push covers) and symlinks every other detected root at it —
# the same shape `npx skills add -g` writes, so a machine that has both paths holds
# one copy and N links rather than N copies. It also writes the project-genome entry
# into ~/.agents/.skill-lock.json, so `npx skills update` refreshes THIS copy instead
# of installing a second one beside it.
#
# Flags:
#   --skill        also install the skill bundle into every detected harness
#   --dir <path>   extra skills root (repeatable) for --skill
#   --from-github  install the CLI from the Git repo instead of PyPI (unreleased builds)
#   --no-cta       skip the star/donate epilogue (also: SKIP_CTA=1)
#   --force-root   allow running as root (installs into $HOME of root)
#   --copy-skill   copy the skill into every root instead of linking one canonical copy

set -euo pipefail
IFS=$'\n\t'

NAME="genome"
PKG="project-genome"
REPO="https://github.com/ishan-parihar/project-genome.git"
BRANCH="main"
TARGET_NAME="project-genome"
BIN_DIR="$HOME/.local/bin"
# The canonical skills root. ONE real copy of the skill lives here, because this is
# the root a skills backup covers: ~/.agents is the only skills root on this machine's
# class that is a git repo pushing to a remote (~/.claude, ~/.zcode, ~/.codex,
# ~/.codegpt and opencode's ~/.config/opencode/skills are not), so a skill that lives
# only under them has no second copy anywhere. This is also the root `npx skills add
# -g` writes, which is why linking from it is interoperable rather than merely tidy.
SKILL_CANON_ROOT="$HOME/.agents/skills"
# The lock file, MEASURED 2026-10-30 rather than assumed: it sits at ~/.agents/
# .skill-lock.json — one level ABOVE the skills root — and that is the file the
# skills-backup service stages. Writing it inside skills/ (which an earlier draft
# of this change did) puts the entry where no CLI ever looks.
SKILL_LOCK="$HOME/.agents/.skill-lock.json"
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
COPY_SKILL=0
EXTRA_DIRS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --skill)       SKIP_SKILL=0; shift ;;
    --dir)         EXTRA_DIRS+=("$2"); shift 2 ;;
    --copy-skill)  COPY_SKILL=1; shift ;;
    --from-github) FROM_GITHUB=1; shift ;;
    --no-cta)      SKIP_CTA=1; shift ;;
    --force-root)  FORCE_ROOT=1; shift ;;
    --help|-h)     sed -n '2,30p' "$0"; exit 0 ;;
    *) die "Unknown option: $1 (supported: --skill, --dir <path>, --copy-skill, --from-github, --no-cta, --force-root)" ;;
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
    # Every PyPI rung refused, which on this machine means the package is not
    # published yet. When git is available, --from-github IS the working path on
    # this very host, so take it instead of reporting a dead end and telling the
    # operator to re-run with a flag (observed: the README one-liner exited 1 on a
    # machine where the from-git install succeeds in one step - the advice
    # repeated the failure instead of resolving it).
    if command -v git >/dev/null 2>&1; then
      warn "the package is not on PyPI yet — retrying from the Git repository"
      if command -v uv >/dev/null 2>&1; then
        uv tool install --force --from "git+$REPO" "$PKG" && installed_with="uv (from git)"
        INSTALL_BIN_DIR="$(uv tool dir --bin 2>/dev/null || echo "$BIN_DIR")"
      elif command -v pipx >/dev/null 2>&1; then
        pipx install --force "git+$REPO" && installed_with="pipx (from git)"
        INSTALL_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$BIN_DIR")"
      elif try_pip_floor "git+$REPO" "from git"; then
        installed_with="pip (from git)"
      fi
    fi
  fi
fi
# Re-check after the retry: only a genuinely failed install is terminal now.
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

# The .skill-lock.json the npx `skills` CLI reads and writes. Without this entry the
# two installers do not know about each other: `npx skills add` installs a SECOND copy
# beside ours, and `npx skills update` never refreshes this one. (Measured 2026-10-30:
# a machine holding 153 skills has 23 in its lock file, and project-genome is one of the
# 130 the lock does not name — so every one of them is invisible to update.)
# The lock file lives at ~/.agents/.skill-lock.json — one level ABOVE the skills
# root — which is where the skills-backup service stages it, so an entry written
# here survives a disk failure.
skills_lock_entry() {  # skills_lock_entry <canonical skill path>
  local canon="$1"
  # MEASURED 2026-10-30, not assumed: the real lock file is
  # ~/.agents/.skill-lock.json — one directory ABOVE the skills root, and it is
  # that file the backup tracks (~/.local/state/skills/.skill-lock.json is a
  # second, older copy with the same schema). Writing it inside skills/ put the
  # entry where no CLI ever looks, which is the same defect it fixes.
  local lock="$SKILL_LOCK"
  [ -f "$canon/SKILL.md" ] || return 0
  command -v python3 >/dev/null 2>&1 || { warn "no python3 — skipped the .skill-lock.json entry"; return 0; }
  python3 - "$canon" "$lock" "$REPO" <<'PY' || warn "could not write the .skill-lock.json entry"
import hashlib, json, os, sys
from datetime import datetime, timezone
canon, lock, repo = sys.argv[1], sys.argv[2], sys.argv[3]
name = os.path.basename(canon)
# A deterministic fingerprint over the skill's own files, EXCLUDING .git and
# .variable paths. HONEST LIMIT, stated rather than papered over: this is NOT the
# npx CLI's own `skillFolderHash` algorithm. Measured 2026-10-30 by re-deriving a
# real entry's hash over its installed folder (recorded 86b6f36…, this scheme
# c3c8fba…) — it does not match. So `npx skills update` will see this entry as
# carrying a foreign hash and will re-fetch on its first pass, which is the safe
# direction: it refreshes our canonical copy from origin/main rather than
# concluding the copy is current and skipping it. The entry exists so the CLI
# KNOWS this copy and its source, which is the part it cannot otherwise learn.
# The alternative (writing no entry) leaves the copy invisible to update forever.
h = hashlib.sha1()
for root, dirs, files in os.walk(canon):
    dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__"))
    for f in sorted(files):
        if f.endswith((".pyc", ".genome-tmp")) or ".genome-tmp." in f:
            continue
        p = os.path.join(root, f)
        h.update(os.path.relpath(p, canon).encode())
        with open(p, "rb") as fh:
            h.update(fh.read())
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
entry = {"source": "ishan-parihar/project-genome", "sourceType": "github",
         "sourceUrl": repo, "skillPath": "SKILL.md",
         "skillFolderHash": h.hexdigest(), "installedAt": now, "updatedAt": now}
try:
    data = json.load(open(lock)) if os.path.exists(lock) else {}
except ValueError:
    data = {}
data.setdefault("version", 3)
data.setdefault("skills", {})
prior = data["skills"].get(name)
data["skills"][name] = entry if prior is None else {**prior, **entry}
os.makedirs(os.path.dirname(lock), exist_ok=True)
with open(lock, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print("skill-lock: %s %s" % (name, "added" if prior is None else "refreshed"))
PY
}

# ── [SECTION: skill] the methodology bundle (optional, off by default) ──────
# The package installs the CLI. The SKILL carries the methodology, the lint
# rule reference and the adoption guide — an agent needs that too, so it is a
# separate, explicit step rather than a surprise side effect of the CLI install.
if [ "$SKIP_SKILL" = "0" ]; then
  ROOTS=()
  # Every harness root that exists. The list is wider than the four roots this
  # installer used to probe (measured 2026-10-30: .codegpt and opencode also hold
  # real skills on this machine, and .claude/skills/browser-automation is already a
  # symlink into ~/.codegpt, which proves a harness reads it). A root that does not
  # exist yet is created only for the canonical one; for the others a link at a
  # path a harness has not created is harmless, so they are all offered.
  for d in "$SKILL_CANON_ROOT" "$HOME/.claude/skills" "$HOME/.zcode/skills" \
           "$HOME/.codex/skills" "$HOME/.codegpt/skills" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills"; do
    if [ -d "$d" ] || [ "$d" = "$SKILL_CANON_ROOT" ]; then ROOTS+=("$d"); fi
  done
  # Skip an empty element: `--dir` with a missing value, or an empty --dir="",
  # otherwise pushes "" into ROOTS and the loop below tries `mkdir -p ""`, which
  # fails with "could not create" on every run. Measured in the sandbox test on
  # 2026-10-30 (an empty array with the `${VAR+...}` guard still yields one empty
  # word, so the guard itself is not enough).
  for d in ${EXTRA_DIRS+"${EXTRA_DIRS[@]}"}; do [ -n "$d" ] && ROOTS+=("$d"); done
  if [ "${#ROOTS[@]}" -eq 0 ]; then
    ROOTS+=("$SKILL_CANON_ROOT")
    info "no harness skills directory found — using ${ROOTS[0]}"
  fi
  # The canonical root holds the ONE real copy; every other root gets a link at it.
  # This is the shape `npx skills add -g` writes, so a machine that has used both
  # installers converges on one copy instead of accumulating four.
  CANON_DEST="$SKILL_CANON_ROOT/$TARGET_NAME"
  mkdir -p "$SKILL_CANON_ROOT"
  if [ -d "$CANON_DEST/.git" ]; then
    if [ -e "$CANON_DEST/scripts/genome" ] && ! git -C "$CANON_DEST" diff --quiet -- scripts/genome 2>/dev/null; then
      warn "$CANON_DEST has its own uncommitted scripts/genome — not resetting it"
      warn "  inspect it with: git -C $CANON_DEST diff -- scripts/genome"
      warn "  upgrade that copy with: genome installs upgrade --apply (from inside $CANON_DEST)"
    elif git -C "$CANON_DEST" fetch origin "$BRANCH" --quiet && git -C "$CANON_DEST" reset --hard "origin/$BRANCH" --quiet; then
      info "updated skill: $CANON_DEST"
    else
      warn "could not update $CANON_DEST — is another process holding it?"
    fi
  elif [ -L "$CANON_DEST" ]; then
    warn "$CANON_DEST is a symlink, not a clone — replacing it with a real copy"
    rm -f "$CANON_DEST"
    if git clone --depth 1 --branch "$BRANCH" "$REPO" "$CANON_DEST" --quiet 2>/dev/null; then
      info "installed skill: $CANON_DEST"
    else
      warn "could not clone the skill into $CANON_DEST"
    fi
  elif git clone --depth 1 --branch "$BRANCH" "$REPO" "$CANON_DEST" --quiet 2>/dev/null; then
    info "installed skill: $CANON_DEST"
  else
    warn "could not clone the skill into $CANON_DEST"
  fi
  [ -n "$GENOME_BIN" ] && register_install skill "$CANON_DEST" "via install.sh --skill"

  # The link target is computed, not hardcoded: relative depth differs by root
  # (`.claude/skills` needs `../../`, `.config/opencode/skills` needs `../../../`),
  # and the fixed `../.agents/skills/…` that a first draft wrote resolves to
  # `~/.claude/.agents/skills/…` — a second broken link, caught by the sandbox test
  # rather than by reading the code. Relative, not absolute, so a moved $HOME keeps
  # the links working and so it matches what the npx convention writes.
  link_target() {
    python3 - "$1" "$SKILL_CANON_ROOT/$TARGET_NAME" <<'PYL'
import os, sys
print(os.path.relpath(sys.argv[2], os.path.dirname(sys.argv[1])))
PYL
  }
  for root in "${ROOTS[@]}"; do
    dest="$root/$TARGET_NAME"
    [ "$root" = "$SKILL_CANON_ROOT" ] && continue
    if [ "$COPY_SKILL" = "1" ]; then
      # The escape hatch for a harness that does not follow symlinks: a real copy
      # in each root, which is what this installer used to do unconditionally.
      mkdir -p "$root"
      rm -rf "$dest"
      if cp -R "$CANON_DEST" "$dest" 2>/dev/null; then
        info "copied skill: $dest"
        [ -n "$GENOME_BIN" ] && register_install skill "$dest" "via install.sh --skill --copy-skill"
      else
        warn "could not copy the skill into $dest"
      fi
      continue
    fi
    want="$(link_target "$dest")"
    # Replace a previous clone (or a stale link) with a relative link at the
    # canonical copy.
    if [ -L "$dest" ]; then
      tgt="$(readlink "$dest" || true)"
      if [ "$tgt" = "$want" ]; then
        info "skill already linked: $dest"
        continue
      fi
      rm -f "$dest"
    elif [ -d "$dest" ]; then
      # A real copy from an earlier installer run. Verified identical before it is
      # replaced, so a root that holds local work never loses it silently.
      if diff -rq "$CANON_DEST" "$dest" >/dev/null 2>&1; then
        rm -rf "$dest"
        info "replaced identical skill copy with a link: $dest"
      else
        warn "$dest differs from the canonical copy — keeping it (compare: diff -rq $CANON_DEST $dest)"
        [ -n "$GENOME_BIN" ] && register_install skill "$dest" "via install.sh --skill (kept: differs from canonical)"
        continue
      fi
    else
      if ! mkdir -p "$root" 2>/dev/null; then
        warn "could not create $root — skipping the link for this harness"
        continue
      fi
    fi
    if ln -s "$want" "$dest" 2>/dev/null; then
      info "linked skill: $dest -> $want"
      register_install skill "$root" "via install.sh --skill (root links the canonical copy)"
    else
      warn "could not link the skill into $root"
    fi
  done
  skills_lock_entry "$CANON_DEST"
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
  # An installed user's next question is 'how do I get the next version?' A uv/pipx
  # tool cannot be upgraded by the CLI itself -- `genome upgrade` compares a
  # VENDORED copy against the release ledger and says so explicitly -- so the
  # answer is this installer, and the installer must be the one to say it.
  echo "To update later, re-run this installer (it is idempotent):"
  echo "  curl -fsSL https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.sh | bash"
  echo "On Windows:  irm https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.ps1 | iex"
  echo ""
  echo "A repo that VENDORS scripts/genome updates that copy with: genome installs upgrade --apply"
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
