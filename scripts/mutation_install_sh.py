#!/usr/bin/env python3
"""Mutations for the two V-111 install.sh guards, for mutation_check.py.

The repo's mutation harness reverts a file to a commit that holds the PRE-FIX
version. That shape does not fit these two guards, because they were ADDED: there
is no commit where the guarded logic exists and the guard does not. So these
mutations are expressed as small edits that REMOVE a guard while keeping the
script parseable, which is the honest equivalent of the pre-fix state.

Two mutations, both of which must be caught:

  no-build-py-refusal   the checkout check `[ -f "$FROM_LOCAL/scripts/build.py" ] || die ...`
  prebuild-unreachable  the pre-build wheel check made unreachable with `&& false`
                        (the script still parses, so the mutation is about the
                        CHECK, not about the shell syntax)

Each mutation was measured before being written here. See the notes: the first
naive version of this file registered a THIRD mutation that the surviving
case could not catch, and the assertion had to be tightened first.

Usage (from mutation_check.py):
    mutate_install_sh("no-build-py-refusal")
"""
from __future__ import annotations

import pathlib
import re

# The two guard lines, quoted exactly as they appear in project-genome/install.sh.
_REFUSAL = (
    '  [ -f "$FROM_LOCAL/scripts/build.py" ] || die "--from-local needs '
    '$FROM_LOCAL/scripts/build.py to build the checkout\'s kernel '
    '(a checkout without it would install whatever scripts/genome happens to hold, '
    'and a failed build would take the existing install down with it)"\n'
)

_PREBUILD_IF = (
    '  if [ "$FROM_LOCAL" != "" ] && command -v uv >/dev/null 2>&1; then\n'
)


def _install_sh(root: pathlib.Path) -> pathlib.Path:
    return root / "install.sh"


def no_build_py_refusal(root: pathlib.Path) -> None:
    """Delete the no-build.py checkout refusal, leaving the build call in place.

    The build call still fails on a missing file, so the install is still refused
    and the working install is still safe — which is exactly why a test that only
    checks the exit code cannot catch this mutation. The case that covers it
    asserts the refusal's own wording (`--from-local needs`), which only this
    guard produces.
    """
    p = _install_sh(root)
    t = p.read_text()
    if t.count(_REFUSAL) != 1:
        raise SystemExit(f"anchor not found exactly once: {t.count(_REFUSAL)}")
    p.write_text(t.replace(_REFUSAL, ""))


def prebuild_unreachable(root: pathlib.Path) -> None:
    """Make the pre-build wheel check unreachable while the script still parses.

    `&& false` keeps the block syntactically valid, so the mutation is about the
    CHECK rather than about the shell. The case covering it fails with "the
    refusal did not say the install was left alone", because the install then
    proceeds, uv removes the old copy, and the case reports the removal.
    """
    p = _install_sh(root)
    t = p.read_text()
    if t.count(_PREBUILD_IF) != 1:
        raise SystemExit(f"anchor not found exactly once: {t.count(_PREBUILD_IF)}")
    p.write_text(t.replace(_PREBUILD_IF, _PREBUILD_IF.replace("; then", " && false; then")))


MUTATIONS = {
    "no-build-py-refusal": no_build_py_refusal,
    "prebuild-unreachable": prebuild_unreachable,
}


def mutate(root: pathlib.Path, name: str) -> None:
    if name not in MUTATIONS:
        raise SystemExit(f"unknown install.sh mutation: {name}")
    MUTATIONS[name](root)


# The case in scripts/test_package_modes.py that covers these guards.
CASES = ("installer_local_source_never_breaks_a_working_install",)
