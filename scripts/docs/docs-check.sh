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
  return $rc
}

skip() { echo "skip: $1"; }

echo "docs-check: $ROOT"
rc=0

# 1. README archetype score — always, if a README exists
if [ -f "$ROOT/README.md" ]; then
  # --archetype auto: the generic bar mis-scores non-visual repos (see score_readme.py).
  # The redirect that used to sit here swallowed the FAIL line, so the failure was silent.
  run "README rubric" python3 "$SCORER" "$ROOT/README.md" --archetype auto || rc=2
else
  skip "no README.md"
fi

# 2. Outward boundary (dead links, orphans, anchors)
if [ -f "$ROOT/README.md" ]; then
  run "outward boundary (D001-D005)" python3 "$DOCSLINT" --root "$ROOT" --quiet
fi

# 3. Per-package contract — only if packages/ or crates/ exists
PKG_DIR=""
for d in packages crates; do
  [ -d "$ROOT/$d" ] && PKG_DIR="$ROOT/$d" && break
done
if [ -n "$PKG_DIR" ]; then
  run "per-package README contract" python3 "$PPR" --packages-dir "$PKG_DIR"
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
[ "$rc" -ne 0 ] && echo "docs-check: FAILED ($rc)" || echo "docs-check: clean"
exit $rc
