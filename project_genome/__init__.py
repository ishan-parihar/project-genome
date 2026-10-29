"""project-genome — the packaged entry point.

The CLI itself is one file (`scripts/genome`, built from `src/`). This module is
the thin wrapper that makes it installable:

  * `python -m project_genome` runs the CLI
  * the `genome` console script (declared in pyproject.toml) calls `main()`

Why a wrapper instead of shipping the file as a module directly: the file is
executed, not imported, and it reads its own `__file__` to decide what it is
(cmd_upgrade compares the running script against a skill copy; doctor's drift
check does the same; the blueprint self-check re-invokes the script). Running it
through `runpy` keeps `__file__` pointing at the real installed file, so those
behaviours stay identical to the vendored copy — a pip-installed genome and a
vendored genome are the same bytes with the same behaviour.

The CLI is stdlib only, so this module is too.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_CLI = Path(__file__).with_name("_genome.py")


def _cli_path() -> Path:
    if not _CLI.is_file():
        raise SystemExit(
            "project-genome: the CLI file is missing from the installed package "
            f"(expected {_CLI}). Reinstall: pip install --force-reinstall project-genome"
        )
    return _CLI


def main(argv: list[str] | None = None) -> int:
    """Run the CLI with the given arguments (defaults to sys.argv[1:])."""
    cli = _cli_path()
    if argv is None:
        argv = sys.argv[1:]
    # runpy with run_name="__main__" executes the file exactly as `python genome`
    # would, so __file__, __name__ and the `if __name__ == "__main__"` guard all
    # behave the way they do for a vendored copy.
    sys.argv = [str(cli), *argv]
    try:
        runpy.run_path(str(cli), run_name="__main__")
    except SystemExit as e:
        # The CLI exits with its own codes (0 ok, 1 usage, 2 lint/gate failure).
        # Let them through unchanged; argparse's own exits land here too.
        code = e.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
