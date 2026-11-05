#!/usr/bin/env python3
"""Mutations for the two append-only guards, for mutation_check.py.

The repo's mutation harness reverts a file to a commit that holds the PRE-FIX
version. The first append-only fix fits that shape (revert src/10_doctor.py to
the net-diff-over-a-window check), but the MERGE fix does not: the flag that
makes a merge's diff visible arrived with the guard that catches it, so there is
no commit where the merge-resolution removal is possible and the check does not
see it. So that mutation is expressed as a small edit that drops the flag while
keeping the check parseable — the honest equivalent of the pre-fix state.

One mutation, which must be caught:

  merge-diff-blind  `--diff-merges=first-parent` dropped, so `git log -p`
                    omits a merge's diff again and a published line removed
                    only by a merge's conflict resolution reads as healthy.

Measured before being written here 2026-11-05: with the flag the case passes,
with the flag removed it FAILS with "doctor: healthy" while a published line is
gone from the worklog.

Usage (from mutation_check.py):
    mutate_append_only(root, "merge-diff-blind")
"""
from __future__ import annotations

import pathlib

_WITH_FLAG = (
    '    probe = subprocess.run(args + ["--diff-merges=first-parent", "--", rel],\n'
    '                           cwd=root, capture_output=True, text=True, timeout=60)\n'
    '    if probe.returncode == 0:\n'
    '        out = probe\n'
    '    else:\n'
    '        out = subprocess.run(args + ["--", rel],\n'
    '                             cwd=root, capture_output=True, text=True, timeout=60)\n'
    '        if out.returncode != 0:\n'
    '            return []\n'
)

_WITHOUT_FLAG = (
    '    out = subprocess.run(args + ["--", rel],\n'
    '                         cwd=root, capture_output=True, text=True, timeout=60)\n'
    '    if out.returncode != 0:\n'
    '        return []\n'
)


def mutate_append_only(root: pathlib.Path, name: str) -> None:
    if name != "merge-diff-blind":
        raise SystemExit(f"unknown append-only mutation: {name}")
    p = root / "src" / "10_doctor.py"
    text = p.read_text()
    if text.count(_WITH_FLAG) != 1:
        raise SystemExit("the merge-diff guard is not in the shape this mutation expects; "
                         "update scripts/mutation_append_only.py")
    p.write_text(text.replace(_WITH_FLAG, _WITHOUT_FLAG))
