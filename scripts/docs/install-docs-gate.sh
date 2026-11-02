#!/usr/bin/env bash
# install-docs-gate.sh — install the docs-check pre-commit hook across the fleet.
#
# Usage:
#   install-docs-gate.sh [--dry-run] [--enforce] [ROOT]
#     ROOT     default: ~/Documents/github/my-projects
#     --dry-run  print what would change, write nothing
#     --enforce  findings block the commit (default: warn, never blocks)
#
# Walks every git repo under ROOT (skips node_modules, target, third_party).
# Writes <hooks>/pre-commit that runs docs-check.sh --staged. Repos with a
# foreign hook, core.hooksPath, .husky/ or .pre-commit-config.yaml are skipped
# and listed, never overwritten. Re-running is safe: managed hooks are
# rewritten in place when the gate path or mode changes.
set -u
MARK="# managed-by: install-docs-gate"
GATE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/docs-check.sh"
DRY=0; ENFORCE=0; ROOT="$HOME/Documents/github/my-projects"
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --enforce) ENFORCE=1 ;;
    -h|--help) grep '^#' "$0" | cut -c3-; exit 0 ;;
    *) ROOT="$a" ;;
  esac
done
[ -x "$GATE" ] || { echo "gate missing: $GATE" >&2; exit 1; }

MODE_ARG=" --mode=warn"; [ "$ENFORCE" -eq 1 ] && MODE_ARG=""
body() {
  printf '#!/usr/bin/env bash\n%s\n# Source: %s\nexec "%s" --staged%s\n' "$MARK" "$GATE" "$GATE" "$MODE_ARG"
}

counts_installed=0; counts_updated=0; counts_unchanged=0
skipped=()

while IFS= read -r gitentry; do
  repo="$(dirname "$gitentry")"
  name="${repo#"$ROOT"/}"
  if [ -n "$(git -C "$repo" config --get core.hooksPath 2>/dev/null)" ]; then
    skipped+=("$name: core.hooksPath set"); continue
  fi
  if [ -d "$repo/.husky" ] || [ -f "$repo/.pre-commit-config.yaml" ]; then
    skipped+=("$name: other hook manager present"); continue
  fi
  hooks="$(git -C "$repo" rev-parse --git-path hooks 2>/dev/null)" || continue
  case "$hooks" in /*) ;; *) hooks="$repo/$hooks" ;; esac
  hook="$hooks/pre-commit"
  if [ -e "$hook" ] && ! grep -qF "$MARK" "$hook"; then
    skipped+=("$name: foreign pre-commit hook"); continue
  fi
  want="$(body)"
  if [ -e "$hook" ] && [ "$(cat "$hook")" = "$want" ]; then
    counts_unchanged=$((counts_unchanged+1)); continue
  fi
  if [ -e "$hook" ]; then action=update; counts_updated=$((counts_updated+1))
  else action=install; counts_installed=$((counts_installed+1)); fi
  if [ "$DRY" -eq 1 ]; then
    echo "would $action: $name"
  else
    mkdir -p "$hooks" && printf '%s\n' "$want" > "$hook" && chmod +x "$hook"
  fi
done < <(find "$ROOT" \( -name node_modules -o -name target -o -name third_party \) -prune -o -name .git -print 2>/dev/null)

verb=$([ "$DRY" -eq 1 ] && echo "would be " || echo "")
echo "mode: $([ "$ENFORCE" -eq 1 ] && echo enforce || echo warn)  root: $ROOT"
echo "installed ${verb}: $counts_installed   updated ${verb}: $counts_updated   unchanged: $counts_unchanged"
if [ "${#skipped[@]}" -gt 0 ]; then
  echo "skipped ${#skipped[@]}:"
  printf '  %s\n' "${skipped[@]}"
fi
