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
                    if not re.search(r"\(|\b(if|else|elseif|function|try|catch|finally|foreach|switch|param)\b", opener):
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
        # needle, the file it must appear in, the human-readable name
        guards = [
            ("externally-managed", "both", "externally-managed venv fallback"),
            ("--force-reinstall", "both", "force-reinstall on the venv rung"),
            ("not resetting it", "both", "vendored-copy reset guard"),
            ("needs git to fetch the bundle", "both", "--skill prerequisite at request time"),
            ("installs register", "both", "registry record of this install"),
            ("VenvBinDir", "both", "verify checks the binary this run installed"),
        ]
        for needle, where, label in guards:
            if where == "both" and needle not in text:
                problems.append(f"parity gap — {label}: present in install.sh but missing from install.ps1")
            elif needle not in text:
                problems.append(f"missing guard — {label}")

    if problems:
        print(f"FAIL {path.name}:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"ok  {path.name}: structure balances, parities hold ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(check(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT))
