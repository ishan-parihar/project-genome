#!/usr/bin/env python3
"""A structural check for install.ps1, for hosts with no PowerShell.

There is no pwsh here and no .NET SDK to get one (only the dotnet RUNTIME), so
the Windows installer cannot be executed or parsed on this machine. That is a
real limit and this file does not pretend to remove it: it only catches the class
of error that a missing `pwsh` otherwise hides — the unbalanced braces and orphaned
closers that a hand edit introduces, which is what happened while adding the
registry section (an orphan `}` and a duplicated line made the file unparseable,
and nothing on this host could have caught it).

Run: python3 scripts/check_ps1.py [path]   (stdlib only)
Exit 0 when the structure balances, 1 when it does not.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = HERE.parent / "install.ps1"


def strip_comment(line: str) -> str:
    """Remove a trailing # comment. Does not understand PowerShell heredocs or
    '# inside a string' precisely, but avoids the two common traps."""
    out, in_s = [], None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_s:
            if ch == in_s:
                in_s = None
            out.append(ch)
        elif ch in "'\"":
            in_s = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def check(path: Path) -> int:
    text = path.read_text()
    lines = text.splitlines()
    problems = []
    # Track openers with their line and column, and pair each closer with the
    # opener it actually closes. A heuristic that inspects only the previous line
    # flags every legitimate `}` in the file (it did), so the pairing is real.
    stack: list[tuple[int, str]] = []
    for n, raw in enumerate(lines, 1):
        code = strip_comment(raw)
        for col, ch in enumerate(code, 1):
            if ch == "{":
                stack.append((n, code.strip()))
            elif ch == "}":
                if not stack:
                    problems.append(f"line {n}: a closing brace with no opener")
                else:
                    opener_line, opener = stack.pop()
                    # the opener statement must contain a block keyword
                    # `[ordered]@{` is the ordered-hashtable literal (install.ps1 writes
                    # the skills-lock JSON through it). It opens no block, but it does
                    # open a brace — without this alternative the checker reports every
                    # hashtable literal as a mis-nested block and, worse, the real
                    # brace counts go unverifiable again. The test is the shape of the
                    # opener (`<something> = [ordered]@{`), not its key names, because
                    # the JSON it builds is not fixed.
                    if not re.search(r"\(|\b(if|else|elseif|function|try|catch|finally|foreach|switch|param)\b", opener) \
                            and not re.search(r"=\s*\[ordered\]@\{", opener):
                        problems.append(
                            f"line {n}: closes a block opened at line {opener_line} by a statement "
                            f"that does not open one: {opener[:60]!r}"
                        )
    if stack:
        problems.append(f"unbalanced braces: {len(stack)} unclosed opener(s) at lines {[s[0] for s in stack[:5]]}")
    parens = strip_comment(text)
    if (parens.count("(") - parens.count(")")) != 0:
        problems.append(f"unbalanced parens: {parens.count('(') - parens.count(')')}")

    # the cross-installer parity this repo actually depends on: every guard present
    # in install.sh must also exist in install.ps1, or the Windows installer is not
    # the same installer.
    pair = path.parent / "install.sh"
    if pair.is_file():
        sh = pair.read_text()
        # needle, the file it must appear in, the human-readable name.
        # 'both' means the guard must appear in BOTH installers, and the loop below
        # checks both directions - a pair that lives on only one platform is a real
        # asymmetry and must be named as one-sided explicitly, not left as a 'both'
        # that silently fails.
        guards = [
            ("externally-managed", "both", "externally-managed venv fallback"),
            ("--force-reinstall", "both", "force-reinstall on the venv rung"),
            ("not resetting it", "both", "vendored-copy reset guard"),
            ("needs git to fetch the bundle", "both", "--skill prerequisite at request time"),
            ("installs register", "both", "registry record of this install"),
            # Platform-native, so one-sided by construction: bash names the resolved
            # bin's directory with $BIN_DIR_FOUND, PowerShell with $script:VenvBinDir.
            # Comparing these across files would report a permanent parity gap, so
            # each is checked only in the file that owns the construct.
            ("BIN_DIR_FOUND", "sh", "verify checks the binary this run installed (bash)"),
            ("VenvBinDir", "ps1", "verify checks the binary this run installed (PowerShell)"),
            # The parity pairs added by the red-team round: each one closes a gap
            # that a mutation exposed. The skill-registration pair exists because
            # removing `reg_install 'skill'` from install.ps1 passed this checker
            # silently - the Windows installer recorded the bin but not the bundle,
            # so `genome installs verify` accused a knowingly-installed copy of drift.
            ("register_install skill", "sh", "skill bundle registered (bash)"),
            ("reg_install 'skill'", "ps1", "skill bundle registered (PowerShell)"),
            # The canonical-root convention: one real copy at ~/.agents/skills (the
            # only root a skills backup covers), a link in every other root. Adding
            # this pair because the four-clone loop it replaces was the measured
            # defect — four 4.8 MB copies of one skill, none of them the backup's.
            # The needle in each file is the constant, so a rename on one platform
            # alone is reported rather than silently diverging.
            ("SKILL_CANON_ROOT", "sh", "canonical skills root (bash)"),
            ("$script:SkillCanonRoot", "ps1", "canonical skills root (PowerShell)"),
            # The relative link target is computed per root depth (a fixed
            # `../.agents/skills/..` resolves to `~/.claude/.agents/skills/..`), and
            # that computation must exist on both platforms for the same reason.
            ("os.path.relpath", "sh", "computed relative link target (bash)"),
            ("GetRelativePath", "ps1", "computed relative link target (PowerShell)"),
            # The .skill-lock.json entry: without it `npx skills add` installs a second
            # copy beside ours and `npx skills update` never refreshes ours.
            (".skill-lock.json", "sh", "skills-lock entry written (bash)"),
            (".skill-lock.json", "ps1", "skills-lock entry written (PowerShell)"),
            # The pre-publication retry. Without this pair, one installer degrades to
            # the from-git path while the other reports a dead end, which is exactly
            # the defect that made the README one-liner exit 1 on a working machine.
            ("not on PyPI yet", "both", "pre-publication from-git retry"),
            # Update guidance: an installed user's next question has an answer on
            # both platforms or the installer has a platform-dependent hole.
            ("To update later", "both", "update guidance in the success summary"),
        ]
        for needle, where, label in guards:
            if where == "both":
                if needle not in text:
                    problems.append(f"parity gap — {label}: present in install.sh but missing from install.ps1")
                if needle not in sh:
                    problems.append(f"parity gap — {label}: present in install.ps1 but missing from install.sh")
            elif where == "sh":
                if needle not in sh:
                    problems.append(f"missing guard — {label} in install.sh")
            else:
                if needle not in text:
                    problems.append(f"missing guard — {label} in install.ps1")

    if problems:
        print(f"FAIL {path.name}:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"ok  {path.name}: structure balances, parities hold ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(check(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT))
