#!/usr/bin/env bash
# docs-check.sh — documentation gate for doc-touching commits.
#
# Philosophy: only run the checks whose inputs exist in this repo. A repo with
# no docs/, no packages, and no kb.toml gets the README lint only; a monster
# monorepo gets everything. No false failures on repos that don't have the
# thing being checked.
#
# Usage:
#   docs-check.sh                 # check the working tree
#   docs-check.sh --staged        # check only what a pre-commit hook staged
#   docs-check.sh --mode=warn     # never exit non-zero (pre-push advisory)
#   docs-check.sh --verbose       # full finding list for failing checks
#
# Exit codes: 0 clean, 2 findings, 1 usage error. Skipped checks print 'skip:'.

set -u
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DOC=""
case "${1:-}" in -*|"") ;; *) DOC="$1" ;; esac
[ -n "$DOC" ] && ROOT="$DOC"
SCOPE="--staged"
MODE="gate"
for a in "$@"; do
  case "$a" in
    --staged) SCOPE="--staged" ;;
    --all|--worktree) SCOPE="--worktree" ;;
    --mode=warn) MODE="warn" ;;
    -h|--help) grep '^#' "$0" | cut -c3- ; exit 0 ;;
  esac
done

# The scope flags are honoured by the checks that can honour them. Until
# 2026-11-04 SCOPE was assigned here and then NEVER READ: the header
# promised '--staged  # check only what a pre-commit hook staged' and the
# script checked the whole worktree anyway. Measured consequence: a repo
# with one old orphan page failed EVERY commit forever, which is how a gate
# trains people to ignore it.
#
# What each check can do with a scope:
#   docs_lint.py    --staged: report only findings in staged files
#   score_readme.py no scope: it grades ONE file (README.md), so it runs
#                   only when README.md itself is staged
#   verify_per_package_readme.py  no scope: it grades every package README,
#                   so it runs only when a package README is staged
# A check with no scope capability is SKIPPED under --staged rather than
# run over the whole tree, because running it unscoped is exactly the bug
# this replaces.
SCOPE_ARG=""
STAGED_README=0
STAGED_PACKAGE_README=0
if [ "$SCOPE" = "--staged" ]; then
  SCOPE_ARG="--staged"
  STAGED_FILES="$(git -C "$ROOT" diff --cached --name-only --diff-filter=d 2>/dev/null || true)"
  case "$STAGED_FILES" in
    *README.md*) STAGED_README=1 ;;
  esac
  case "$STAGED_FILES" in
    *packages/*/README.md*|*crates/*/README.md*) STAGED_PACKAGE_README=1 ;;
  esac
fi

DOC_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCORER="$DOC_SCRIPT_DIR/score_readme.py"
DOCSLINT="$DOC_SCRIPT_DIR/docs_lint.py"
PPR="$DOC_SCRIPT_DIR/verify_per_package_readme.py"

VERBOSE=0
for a in "$@"; do [ "$a" = "--verbose" ] && VERBOSE=1; done

run() { # run <label> <command...>
  local label="$1"; shift
  local out rc summary
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    # warnings exit 0; say so, so a reader does not take the line for a clean run
    if echo "$out" | grep -qE '^W[0-9]{3}|warning\(s\)|[1-9][0-9]* advisory'; then
      echo "ok (warnings): $label"
    else
      echo "ok:   $label"
    fi
  else
    # one summary line per failing check; the full list only with --verbose
    summary="$(echo "$out" | grep -E 'hard failure|FAIL=|failure|Issues \(' | tail -1)"
    echo "FAIL: $label (rc=$rc)${summary:+ — $summary}"
    if [ "$VERBOSE" = 1 ]; then echo "$out" | sed 's/^/      /' | head -40; fi
  fi
  # THE FAILURE MUST REACH THE EXIT CODE, AND `run` IS THE ONLY PLACE THAT KNOWS IT.
  #
  # Measured 2026-11-04: only the README rubric ended in `|| rc=2`. The outward
  # boundary and the genome boundary printed their FAIL line and then the script
  # went on to print "docs-check: clean" and exit 0 — a dead link, an orphan page
  # and a W008/W009 warning ALL failed the gate in appearance only. The gate
  # reported the failure and swallowed it in the same breath.
  #
  # It was left to each call site to remember `|| rc=2`, and three of the four
  # did not. The fix is here rather than at the call sites: a check that FAILS
  # now sets the script's verdict itself, so a new check cannot be added without
  # inheriting the bug.
  if [ "$rc" -ne 0 ] && [ "$rc" -ne "$RC" ]; then RC=2; fi
  return $rc
}

skip() { echo "skip: $1"; }

echo "docs-check: $ROOT"
# The script's verdict. `run` sets it itself (see below), so a check cannot be
# added without inheriting the failure-propagation.
RC=0
rc=0

# 1. README archetype score — always, if a README exists
if [ -f "$ROOT/README.md" ]; then
  # --archetype auto: the generic bar mis-scores non-visual repos (see score_readme.py).
  # The redirect that used to sit here swallowed the FAIL line, so the failure was silent.
  # Under --staged this runs ONLY when README.md is staged: the scorer grades
  # one file and cannot be narrowed, so running it unscoped would report a
  # README problem on every commit that never touched the README.
  if [ "$STAGED_README" -eq 1 ] || [ "$SCOPE" != "--staged" ]; then
    run "README rubric" python3 "$SCORER" "$ROOT/README.md" --archetype auto
  else
    skip "README rubric (README.md not staged)"
  fi
else
  skip "no README.md"
fi

# 2. Outward boundary (dead links, orphans, anchors)
if [ -f "$ROOT/README.md" ]; then
  run "outward boundary (D001-D005)" python3 "$DOCSLINT" --root "$ROOT" --quiet $SCOPE_ARG
fi

# 3. Per-package contract — only if packages/ or crates/ exists
PKG_DIR=""
for d in packages crates; do
  [ -d "$ROOT/$d" ] && PKG_DIR="$ROOT/$d" && break
done
if [ -n "$PKG_DIR" ]; then
  if [ "$STAGED_PACKAGE_README" -eq 1 ] || [ "$SCOPE" != "--staged" ]; then
    run "per-package README contract" python3 "$PPR" --packages-dir "$PKG_DIR"
  else
    skip "per-package README contract (no package README staged)"
  fi
else
  skip "no packages/ or crates/"
fi

# 4. genome boundary (W008/W009) — repos with genome.toml or a legacy kb.toml
GENOME="$ROOT/scripts/genome"
[ -x "$GENOME" ] || GENOME="$HOME/.agents/skills/project-genome/scripts/genome"
if [ -f "$ROOT/genome.toml" ] || [ -f "$ROOT/kb.toml" ]; then
  if [ -x "$GENOME" ]; then
    run "genome boundary (W008/W009)" \
      bash -c "cd '$ROOT' && '$GENOME' lint --code W008 W009"
  else
    skip "genome config present but genome CLI not found"
  fi
else
  skip "no genome.toml or kb.toml"
fi

if [ "$MODE" = "warn" ]; then
  echo "docs-check: warn mode — findings reported, not gating"
  exit 0
fi
[ "$RC" -ne 0 ] && echo "docs-check: FAILED ($RC)" || echo "docs-check: clean"
exit $RC
