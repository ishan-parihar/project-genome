#!/usr/bin/env python3
"""The mutation for the scaffold's docs-index guard, for mutation_check.py.

The scaffolding of `readme = "README.md"` and the README write landed in
500d87d; the guard that tests it arrived later; and the docs-index half (the
README linking every page init creates) landed in the same change as this
guard. So there is no pre-fix commit to revert to, and the equivalent pre-fix
state is a small edit: restore the README's original single-link body, which is
exactly the shape that produced orphan pages on every profile.

Two mutations, which must be caught:

  init-no-readme  `genome init` stops writing the README.md its own
                  genome.toml declares and its own AGENTS.md cites, so the
                  scaffold ships a pointer to a file it did not create.  This
                  is the pre-500d87d defect, reproduced on purpose: measured on
                  that build, `genome init --profile software` produced a tree
                  whose genome.toml said `readme = "README.md"`, no README
                  existed, and the AGENTS.md routing table cited it.

  init-readme-no-docs-links  init's README stops linking the docs pages it
                             creates (docs/RUNBOOK.md on every profile,
                             docs/INDEX.md on the ops module), so the scaffold
                             ships pages the docs gate's D003 calls orphans.
                             Measured 2026-11-05: with the links the case
                             passes; with them removed it FAILS naming the
                             unlinked page.

Usage (from mutation_check.py):
    mutate_init(root, "init-no-readme")
    mutate_init_docs(root, "init-readme-no-docs-links")
"""
from __future__ import annotations

import pathlib

_WITH_README = '    write("README.md", readme)\n'

_WITHOUT_README = '    pass  # MUTATED: the README the scaffold declares is not written\n'

_WITH_LINKS = (
    '    readme = README_TPL.replace("{{NAME}}", root.name)\n'
    '    if "core" in mods:  # the core profile always creates the runbook\n'
    '        readme += "\\n- [docs/RUNBOOK.md](docs/RUNBOOK.md) — the exact commands and the environment traps\\n"\n'
    '    if "ops" in mods:\n'
    '        readme += "\\n- [docs/INDEX.md](docs/INDEX.md) — the map of this knowledge base\\n"\n'
    '    if "outline" in mods:\n'
)

_WITHOUT_LINKS = (
    '    readme = README_TPL.replace("{{NAME}}", root.name)\n'
    '    if "outline" in mods:\n'
)


def mutate_init(root: pathlib.Path, name: str) -> None:
    if name != "init-no-readme":
        raise SystemExit(f"unknown init mutation: {name}")
    p = root / "src" / "13_init.py"
    text = p.read_text()
    if text.count(_WITH_README) != 1:
        raise SystemExit("the init README write is not in the shape this mutation expects; "
                         "update scripts/mutation_init.py")
    p.write_text(text.replace(_WITH_README, _WITHOUT_README))


def mutate_init_docs(root: pathlib.Path, name: str) -> None:
    if name != "init-readme-no-docs-links":
        raise SystemExit(f"unknown init docs mutation: {name}")
    p = root / "src" / "13_init.py"
    text = p.read_text()
    if text.count(_WITH_LINKS) != 1:
        raise SystemExit("the init docs links are not in the shape this mutation expects; "
                         "update scripts/mutation_init.py")
    p.write_text(text.replace(_WITH_LINKS, _WITHOUT_LINKS))
