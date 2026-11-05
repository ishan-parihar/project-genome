#!/usr/bin/env python3
"""The mutation for the init-scaffold guard, for mutation_check.py.

The repo's mutation harness reverts a file to a commit holding the PRE-FIX
version. The init-scaffold guard does not fit that shape: the fix (writing the
README the scaffold declares) landed in 500d87d, but the guard that tests it
arrived later, and the harness's worktree is built from the CURRENT commit.
Reverting `src/13_init.py` to `500d87d^` would revert a lot more than the
README write, so the equivalent pre-fix state is a small edit that drops the
`write("README.md", readme)` call while leaving init parseable.

One mutation, which must be caught:

  init-no-readme  `genome init` stops writing the README.md its own
                  genome.toml declares and its own AGENTS.md cites, so the
                  scaffold ships a pointer to a file it did not create.  This
                  is the pre-500d87d defect, reproduced on purpose: measured on
                  that build, `genome init --profile software` produced a tree
                  whose genome.toml said `readme = "README.md"`, no README
                  existed, and the AGENTS.md routing table cited it.

Usage (from mutation_check.py):
    mutate_init(root, "init-no-readme")
"""
from __future__ import annotations

import pathlib

_WITH_README = '    write("README.md", readme)\n'

_WITHOUT_README = '    pass  # MUTATED: the README the scaffold declares is not written\n'


def mutate_init(root: pathlib.Path, name: str) -> None:
    if name != "init-no-readme":
        raise SystemExit(f"unknown init mutation: {name}")
    p = root / "src" / "13_init.py"
    text = p.read_text()
    if text.count(_WITH_README) != 1:
        raise SystemExit("the init README write is not in the shape this mutation expects; "
                         "update scripts/mutation_init.py")
    p.write_text(text.replace(_WITH_README, _WITHOUT_README))
