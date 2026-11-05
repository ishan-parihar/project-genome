#!/usr/bin/env python3
"""scripts/check_suite_counts.py — AGENTS.md's count claims must match the code.

This exists because of a MEASURED defect, not a hypothetical one.

The AGENTS.md suite table said "52/52 cases" for scripts/test_genome.py.
Measured on 2026-11-05, the file held 54. The count had been corrected once
already (44/44 -> 52/52), and then went stale again a few days later,
because correcting a table by hand is not a fix — it is a repair with no
guard. It went stale a THIRD time (52 -> 54 -> 55) while this file was
being written, and the mutation count went stale too (7/7 claimed, 10 then
11 in the code). A document that reads green while its numbers are wrong is
the same failure mode this whole project is about, one level down: the
summary that is supposed to be the honest one is the one no check read.

So this check reads AGENTS.md's OWN claims and compares each to the file it
describes:

  | `scripts/test_genome.py` | 55/55 cases ... |   -> the file's @case count
  python3 scripts/mutation_check.py    # 11/11    -> len(MUTATIONS)

Every count in AGENTS.md must be DERIVED from the files it describes, or it
is a claim with no evidence behind it. This script derives it.

THE SUITES ARE DISCOVERED, NOT HARDCODED: every `scripts/*.py` row in the
table is checked, so a suite added to the table is covered the moment it is
listed — the failure mode where a new suite's count is never checked cannot
happen here.

BOTH NUMBERS ARE CHECKED. A row claiming `9/10` is claiming a suite that
does not pass every case. That claim is the one a reader is most likely to
trust, and it must never be false.

Run:  python3 scripts/check_suite_counts.py     (stdlib only; exit 1 on drift)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
AGENTS = REPO / "AGENTS.md"

# A table row that names a script and carries a count claim:
#   | `scripts/test_genome.py` | 55/55 cases: ... | 2026-11-05 |
ROW_RE = re.compile(r"^\|\s*`(scripts/[^`]+\.py)`\s*\|([^|]*)\|")
# The two code blocks that repeat a count outside the table.
HEADLINE_RE = re.compile(r"python3\s+(scripts/test_genome\.py)\s*#\s*(\d+)/(\d+)")
MUTATION_RE = re.compile(r"python3\s+(scripts/mutation_check\.py)\s*#\s*(\d+)/(\d+)")

# Every suite the table is EXPECTED to name. The table is the source of
# truth for what to check, but it must not be the source of truth for
# WHICH suites exist: a row deleted from the table would otherwise take
# its own check with it, and the deletion would be silent. So the expected
# set is asserted here, and the table must still name every one of them.
EXPECTED_SUITES = {
    "scripts/test_genome.py",
    "scripts/test_package.py",
    "scripts/test_package_modes.py",
    "scripts/check_docs_lint.py",
}


def case_count(rel: str) -> int:
    """How many cases a suite holds, or None if it has no case decorator.

    A suite is a file whose cases are decorated with @case. A script with
    no @case decorators is NOT a suite with a countable set of cases — it is
    a check that either passes or fails — so it has no `n/n` claim to
    verify, and AGENTS.md's row for it correctly carries no count.
    """
    text = (REPO / rel).read_text()
    n = len(re.findall(r"^@case", text, re.M))
    return n if n else None


def mutation_count() -> int:
    """How many mutations mutation_check.py declares, from its own list."""
    text = (REPO / "scripts" / "mutation_check.py").read_text()
    i = text.index("MUTATIONS = [")
    body = text[i:text.index("\n]\n", i)]
    # each entry is a 4-space-indented parenthesized tuple whose first item
    # is the mutation's name
    return len(re.findall(r"^\s{4}\(\"", body, re.M))


def check_claim(rel: str, numerator: int, denominator: int, where: str,
                actual: int, drift: list) -> None:
    """Check one `n/n` claim against the count the code actually has."""
    if numerator != denominator:
        drift.append(
            f"{where}: claims {numerator}/{denominator} — a suite that does not "
            f"pass every case is not green")
    if denominator != actual:
        drift.append(f"{where}: says {denominator}, the code has {actual}")


def main() -> int:
    if not AGENTS.is_file():
        print(f"no AGENTS.md at {AGENTS}", file=sys.stderr)
        return 1
    agents = AGENTS.read_text()

    drift = []
    checked = 0

    # 1. every suite row in the table
    named = set()
    for line in agents.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        rel, cell = m.group(1), m.group(2)
        named.add(rel)
        path = REPO / rel
        if not path.is_file():
            drift.append(f"{rel}: the table names it, but the file does not exist")
            continue
        cm = re.search(r"(\d+)\s*/\s*(\d+)", cell)
        actual = case_count(rel)
        if not cm:
            # A row with no count is only correct if the file has no
            # countable cases. If it DOES have cases and the row is silent,
            # the table is hiding a count that could be wrong.
            if actual is not None:
                drift.append(
                    f"{rel}: the table row carries no `n/n` count, but the file "
                    f"has {actual} cases")
            continue
        if actual is None:
            drift.append(
                f"{rel}: the table row claims {cm.group(0)}, but the file has no "
                f"@case cases to count")
            continue
        checked += 1
        check_claim(rel, int(cm.group(1)), int(cm.group(2)),
                    f"{rel} (the table row)", actual, drift)

    # 2. every suite the table is expected to name, but does not
    for rel in sorted(EXPECTED_SUITES - named):
        drift.append(f"{rel}: no table row in AGENTS.md names it at all")

    # 3. the headline count in the Gate code block
    h = HEADLINE_RE.search(agents)
    if h:
        checked += 1
        check_claim(h.group(1), int(h.group(2)), int(h.group(3)),
                    "the Gate code block", case_count(h.group(1)), drift)

    # 4. the mutation count in the run-it-on-demand block
    mm = MUTATION_RE.search(agents)
    if mm:
        checked += 1
        check_claim(mm.group(1), int(mm.group(2)), int(mm.group(3)),
                    "the mutation block", mutation_count(), drift)

    if drift:
        print("AGENTS.md count claims have drifted from the code:")
        for d in drift:
            print("  " + d)
        print(f"\n{len(drift)} drifted claim(s). Correct AGENTS.md, or add the")
        print("missing cases, and re-run. A stale count is a summary that lies.")
        return 1
    print(f"check_suite_counts: {checked} count claims in AGENTS.md all match the code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
