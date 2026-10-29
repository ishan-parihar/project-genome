"""`python -m project_genome` — run the genome CLI.

Kept separate from `__init__.py` so the module can be executed directly, which is
the form a reader reaches for when they want the CLI without a console script on
PATH (a CI job, a container, a `python -m` in a Makefile).
"""

from __future__ import annotations

from . import main

if __name__ == "__main__":
    raise SystemExit(main())
