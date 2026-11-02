#!/usr/bin/env bash
# verify_install.sh — lint + structural checks for a generated installer.
# Usage: scripts/verify_install.sh <path/to/install.sh> [path/to/install.ps1]
# Exit 0 = all checks pass. Heuristic checks run on live (non-comment) lines.
set -uo pipefail
SH="${1:-}"; PSP="${2:-}"
[ -n "$SH" ] || { echo "usage: $0 <install.sh> [install.ps1]"; exit 2; }
FAIL=0
check() { # check <ok:0|1> <message>
  if [ "$1" = 0 ]; then echo "  ok  : $2"; else echo "  FAIL: $2"; FAIL=1; fi
}
LIVE_FILE=$(mktemp)
trap 'rm -f "$LIVE_FILE"' EXIT
grep -vE '^[[:space:]]*#' "$SH" > "$LIVE_FILE"   # file, not a var: avoids the printf|grep -q SIGPIPE race under pipefail
live_grep() { grep "$@" "$LIVE_FILE"; }

echo "== $SH =="
[ -f "$SH" ] || { echo "FAIL: not a file: $SH"; exit 2; }

# 1. syntax
bash -n "$SH" 2>/tmp/vi_syntax.err
check $? "bash -n syntax valid" || cat /tmp/vi_syntax.err

# 2. hardening
case "$(head -1 "$SH")" in
  *'sh')  # POSIX sh (dash/ash): pipefail is a bashism there; set -eu is the correct ceiling
    grep -qE 'set -[eu]+' "$SH"; check $? "POSIX sh hardening (set -eu; pipefail is a bashism under /bin/sh)" ;;
  *)
    grep -q 'set -euo pipefail' "$SH"; check $? "set -euo pipefail" ;;
esac

# 3. idempotency guards (the #1 real-world installer bug)
live_grep -q 'case ":\$PATH:"' && ok=0 || ok=1
if [ $ok != 0 ]; then live_grep -q 'grep -qs' && ok=0 || ok=1; fi
check $ok "PATH injection is guarded (grep-before-append)"
if live_grep -q '\.env'; then
  live_grep -qE '\[ (! -f|-f) [^]]*\.env|\[ -f "\.env" \]' && ok=0 || ok=1
  check $ok ".env seeded only when absent"
fi

# 4. CTA epilogue present and gated (live lines)
live_grep -q 'SKIP_CTA'; check $? "CTA is skip-gated (SKIP_CTA/--no-cta)"
live_grep -qi 'star'; check $? "star prompt present"

# 5. OS detection
live_grep -q 'uname -s'; check $? "OS detection"
# 6. shellcheck (missing = note only; findings = fail on errors)
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck -S error "$SH" && check 0 "shellcheck: no errors" || check 1 "shellcheck errors"
  n_warn=$(shellcheck "$SH" 2>/dev/null | grep -c '^In .* line' || true)
  echo "  note: shellcheck total findings: ${n_warn:-0}"
else
  echo "  note: shellcheck not installed — skipped"
fi

# 7. actionable errors: no bare "failed" die messages (live lines)
n_bare=$(grep -cE 'die "(Yes|No|Error|Failed|Oops|Something)' "$LIVE_FILE" || true)
[ "${n_bare:-0}" = 0 ]; check $? "die messages are specific (no bare 'failed')"

# PowerShell (optional arg)
if [ -n "$PSP" ] && [ -f "$PSP" ]; then
  echo "== $PSP =="
  grep -q "ErrorActionPreference = 'Stop'" "$PSP"; check $? "ErrorActionPreference Stop"
  grep -q 'NoCta' "$PSP"; check $? "CTA is skip-gated"
  # arch truth is only required when the ps1 selects arch-specific artifacts
  # (npx wrappers that delegate to npm have no arch-sensitive download)
  if grep -qE '\.zip|\.exe|\.msi|win-(x64|arm|ia32)|-windows-|node-v|Get-Platform|\[System.Runtime' "$PSP"; then
    grep -qE 'SESSION Manager..Environment|PROCESSOR_ARCHITECTURE' "$PSP"; check $? "arch truth source"
  else
    echo "  ok  : arch truth source (n/a — no arch-specific artifact selection)"
  fi
  if command -v pwsh >/dev/null 2>&1; then
    if pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('$PSP',[ref]\$null,[ref]\$null)|Out-Null" 2>/dev/null; then
      check 0 "PowerShell parses"
    else
      check 1 "PowerShell parse errors"
    fi
  else
    echo "  note: pwsh not installed — parse check skipped"
  fi
fi

echo ""
[ $FAIL = 0 ] && echo "RESULT: PASS" || echo "RESULT: FAIL (fix the FAIL lines above)"
exit $FAIL
