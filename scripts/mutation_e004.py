#!/usr/bin/env python3
"""The mutation for the E004 tombstone exemption, for mutation_check.py.

The repo's mutation harness reverts a file to a commit holding the PRE-FIX
version. The E004 fix does not fit that shape: the exemption arrived WITH the
guard that tests it, so there is no commit where the kernel is red on its own
`genome archive` tombstone. The equivalent pre-fix state is a small edit that
drops the `is_tombstone` skip while leaving the check parseable.

One mutation, which must be caught:

  e004-tombstone-blind  the `is_tombstone(read(f))` skip removed from E004, so
                        the kernel's OWN archive stub (an undated plans/audits
                        file carrying a `kb: tombstone` marker) is reported as a
                        violation again.  E004 was the only reader of
                        plans/audits without that skip, unlike its siblings at
                        09_lint_checks.py:43/189/507.  The same mutation also
                        removes E019's dangling-target check, because the two
                        live in one hunk.

Measured before being written here 2026-11-05, on a purpose-built repo: with
the skip the case passes; with the skip removed it FAILS with "the kernel is
red on its OWN archive stub" while the plans/audit file it names is the
tombstone `genome archive` just wrote.

Usage (from mutation_check.py):
    mutate_e004(root, "e004-tombstone-blind")
"""
from __future__ import annotations

import pathlib

_WITH_SKIP = (
    '                body = read(f)\n'
    '                if is_tombstone(body):\n'
    '                    # A tombstone is the ARCHIVE\'s record of a file, not a plan (see\n'
    '                    # cmd_archive), so the date rule does not apply to it.  The\n'
    '                    # exemption must not be a blind spot: the tombstone\'s TARGET is\n'
    '                    # checked instead, so a stub whose archived file is gone is named.\n'
    '                    m = TOMBSTONE.search(body)\n'
    '                    if m and not (cfg.root / m.group(1)).exists():\n'
    '                        out.append(f"E019 {role} tombstone points at missing `{m.group(1)}`: {cfg.rel(f)}")\n'
    '                    continue\n'
)

_WITHOUT_SKIP = ""


def mutate_e004(root: pathlib.Path, name: str) -> None:
    if name != "e004-tombstone-blind":
        raise SystemExit(f"unknown E004 mutation: {name}")
    p = root / "src" / "09_lint_checks.py"
    text = p.read_text()
    if text.count(_WITH_SKIP) != 1:
        raise SystemExit("the E004 tombstone skip is not in the shape this mutation expects; "
                         "update scripts/mutation_e004.py")
    p.write_text(text.replace(_WITH_SKIP, _WITHOUT_SKIP))
