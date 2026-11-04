#!/usr/bin/env python3
"""A self-check for scripts/docs/docs_lint.py and scripts/docs/docs-check.sh.

These two files are the docs gate, and until 2026-11-04 they had NO test coverage
at all: nothing in scripts/test_genome.py, scripts/test_package.py or
scripts/test_package_modes.py mentioned docs_lint, D001 or D003. Three defects
shipped through that gap in one afternoon, and each of them was the kind that
looks like it works:

  1. `docs-check.sh` printed "FAIL: outward boundary" and then printed
     "docs-check: clean" and exited 0. Only the README rubric ended in
     `|| rc=2`; every other check's failure never reached the exit code.
  2. `--staged` was announced in the script's own usage text, parsed into
     SCOPE, and then never read. `docs_lint.py` had no `--staged` argument
     at all. A repo with one old orphan page therefore failed EVERY commit
     forever, which is how a gate trains people to ignore it.
  3. D003 fired on `docs/RECORDS.md` — the genome's `records_index` role, the
     generated index over docs/decisions and docs/regressions, both of which
     are already exempt as internal dirs. It sits at the top of docs/ rather
     than inside a directory of its own, so the directory rule missed it.

Run: python3 scripts/check_docs_lint.py   (stdlib only; every case builds its
own throwaway repo)
Every selected case runs even when one fails; the summary lists them all and
the exit code is 1 on any failure.
"""
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"
LINT = DOCS / "docs_lint.py"
CHECK = DOCS / "docs-check.sh"
CASES: dict = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def run(cwd, *args, ok=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if ok and r.returncode != 0:
        raise AssertionError(f"{' '.join(args)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def findings(root: Path, *args) -> list:
    """The findings as (code, file) pairs, via the machine-readable output.

    docs_lint exits 2 when it has hard findings, so the exit code is NOT the
    signal here — the JSON document is. `ok=False` keeps the harness from
    raising on a finding it is about to assert on.
    """
    r = run(root, sys.executable, str(LINT), "--root", ".", "--json", *args, ok=False)
    doc = json.loads(r.stdout)
    return [(f["code"], f.get("file")) for f in doc.get("findings", [])]


def new_repo(root: Path) -> None:
    run(root, "git", "init", "-q")
    run(root, "git", "config", "user.email", "t@t")
    run(root, "git", "config", "user.name", "t")


def make(root: Path, files: dict) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


@case
def d003_reports_a_real_orphan(root: Path) -> None:
    """A doc page that nothing links to IS an orphan, and the check says so.

    D003 is the check that catches a page a reader can never find. It has to
    fire on the ordinary case, or the exemption added below would silence it.
    """
    r = root / "orphan"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n\nSee [guide](docs/GUIDE.md).\n",
             "docs/GUIDE.md": "# Guide\n"})
    (r / "docs" / "ORPHAN.md").write_text("# Orphan\n")
    got = findings(r)
    assert ("D003", "docs/ORPHAN.md") in got, got


@case
def d003_exempts_the_generated_records_index(root: Path) -> None:
    """The genome's `records_index` role is not an orphan page.

    Measured 2026-11-04: D003 fired on this repo's own docs/RECORDS.md and
    failed the docs-check gate. The file is the generated index over
    docs/decisions and docs/regressions — BOTH of which are already exempt as
    internal dirs — and it sits at the top of docs/ rather than inside a
    directory of its own, so the directory rule missed it.

    The reference that DOES exist is in AGENTS.md's routing table as a CODE
    SPAN, not a markdown link, so no linker scan would have helped. And the
    page is not a reader page at all: `genome rec emit` writes it and tooling
    reads it. Every reader-facing page in docs/ IS linked from README —
    ARCHITECTURE.md, RUNBOOK.md and PUBLISHING.md all are.

    The exemption must be NARROW. A differently-named page in the same
    directory is still an orphan, and a differently-named directory's RECORDS
    page is still exempt only by name.
    """
    r = root / "records"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n", "docs/RECORDS.md": "# Records\n"})
    got = findings(r)
    assert not any(c == "D003" for c, _ in got), f"the records index was reported as an orphan: {got}"

    # and the exemption is narrow: a sibling with another name is still caught
    (r / "docs" / "OTHER.md").write_text("# Other\n")
    got = findings(r)
    assert ("D003", "docs/OTHER.md") in got, f"the exemption swallowed a real orphan: {got}"


@case
def d003_exempts_the_internal_dirs(root: Path) -> None:
    """The internal directories stay exempt — the convention the records index joins."""
    r = root / "internal"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n",
             "docs/kb/CLOSED.md": "# Closed\n",
             "docs/decisions/AD-001.md": "# Decision\n",
             "docs/regressions/RG-001.md": "# Regression\n",
             "docs/handoff/STATE.md": "# State\n"})
    got = findings(r)
    assert not any(c == "D003" for c, _ in got), f"an internal page was reported as an orphan: {got}"


@case
def d001_reports_a_dead_link(root: Path) -> None:
    """A link to a file that does not exist is dead, and the check says so."""
    r = root / "dead"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n\nSee [gone](docs/GONE.md).\n"})
    got = findings(r)
    assert any(c == "D001" for c, _ in got), f"a dead link was not reported: {got}"


@case
def staged_scope_reports_only_staged_files(root: Path) -> None:
    """--staged reports the findings in the files git has staged.

    The flag was announced in docs-check.sh's usage text, parsed into SCOPE,
    and then never read; docs_lint.py had no --staged argument at all. The
    consequence was that a repo with one old orphan failed EVERY commit
    forever — and a gate that always fails is a gate nobody reads.

    The scope must be exactly the staged set: an old finding in an untouched
    file is not reported, and a finding in a staged file IS.
    """
    r = root / "staged"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n", "docs/OLD.md": "# Old\n"})
    run(r, "git", "add", "-A")
    run(r, "git", "commit", "-qm", "init")
    # an old orphan, committed: it is in the tree but in no staged file
    got = findings(r, "--staged")
    assert not any(c == "D003" for c, _ in got), f"an untouched page was reported on this commit: {got}"

    # now stage a genuinely new orphan: it MUST be reported
    (r / "docs" / "NEW.md").write_text("# New\n")
    run(r, "git", "add", "docs/NEW.md")
    got = findings(r, "--staged")
    assert ("D003", "docs/NEW.md") in got, f"a staged orphan was not reported: {got}"


@case
def staged_scope_fails_closed(root: Path) -> None:
    """When git cannot be asked, EVERY finding is kept.

    The scope is an optimisation, and an optimisation that cannot tell what is
    staged must not turn into a silent pass. If the staged set is unknown, the
    safe direction is to report everything.
    """
    r = root / "nogit"
    r.mkdir()
    make(r, {"README.md": "# Title\n", "docs/ORPHAN.md": "# Orphan\n"})
    # NOT a git repo: `git diff --cached` cannot be run
    got = findings(r, "--staged")
    assert ("D003", "docs/ORPHAN.md") in got, f"an unknown scope silently dropped a finding: {got}"


@case
def docs_check_propagates_a_failing_check(root: Path) -> None:
    """A check that FAILS must make the script exit non-zero.

    Measured 2026-11-04: `run` printed the FAIL line and returned non-zero,
    but only the README rubric ended in `|| rc=2`. The outward boundary and
    the genome boundary printed their FAIL line and then the script went on
    to print "docs-check: clean" and exit 0. A dead link, an orphan page and
    a W008/W009 warning ALL failed the gate in appearance only.

    The fix is inside `run`, not at the call sites, so this test pins the
    BEHAVIOUR (the exit code) rather than the implementation.
    """
    r = root / "gate"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n\nSee [gone](docs/GONE.md).\n"})
    res = run(r, "bash", str(CHECK), "--all", ok=False)
    assert res.returncode != 0, f"a failing check did not fail the gate:\n{res.stdout}"
    assert "FAIL:" in res.stdout, res.stdout
    assert "docs-check: FAILED" in res.stdout, res.stdout
    assert "docs-check: clean" not in res.stdout, f"the gate said clean and failed:\n{res.stdout}"


@case
def json_stdout_is_one_document(root: Path) -> None:
    """`--json` is a contract: stdout is ONE document, and json.loads(stdout) must work.

    Measured 2026-11-04: `--json --staged` printed the scope note to stdout
    AHEAD of the document, so stdout held two things and every consumer's
    json.loads() raised on the first line. This is the same defect the
    kernel's own `lint --json` had, and the same fix: the note goes to stderr
    in JSON mode, and the counts travel inside the document.

    The note stays on stdout in TEXT mode, because a human reading the text
    output needs it and there is no document to carry it there.
    """
    r = root / "json"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n", "docs/OLD.md": "# Old\n"})
    run(r, "git", "add", "-A")
    run(r, "git", "commit", "-qm", "init")

    # JSON mode: stdout parses as ONE document, and the note is on stderr
    res = run(r, sys.executable, str(LINT), "--root", ".", "--json", "--staged", ok=False)
    doc = json.loads(res.stdout)          # raises if stdout is not exactly one document
    assert "findings" in doc, doc
    assert "staged" in doc, f"the scope counts must travel inside the document: {doc}"
    assert doc["staged"]["before"] >= 1, doc
    assert "staged scope" in res.stderr, f"the note belongs on stderr in JSON mode: {res.stderr}"
    assert "staged scope" not in res.stdout, f"the note polluted the JSON stream: {res.stdout}"

    # TEXT mode: the note stays on stdout, where a reader sees it
    res = run(r, sys.executable, str(LINT), "--root", ".", "--staged", ok=False)
    assert "staged scope" in res.stdout, res.stdout


@case
def docs_check_passes_a_clean_repo(root: Path) -> None:
    """A clean repo still passes, and says so. A gate that always fails is a gate nobody reads.

    The README rubric is a SEPARATE check with its own bar (a one-line README
    does not satisfy it), so this case exercises the boundary check alone and
    asserts on THAT check's verdict rather than on the script's overall exit
    code. The rubric's own gate is exercised by the other cases.
    """
    r = root / "clean"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n\nSee [guide](docs/GUIDE.md).\n",
             "docs/GUIDE.md": "# Guide\n"})
    res = run(r, "bash", str(CHECK), "--all", ok=False)
    assert "FAIL: outward boundary" not in res.stdout, res.stdout
    assert "ok:   outward boundary" in res.stdout, res.stdout


@case
def docs_check_warn_mode_never_gates(root: Path) -> None:
    """--mode=warn reports findings and never fails.

    Every managed hook uses `--staged --mode=warn`, so this is the path 45
    repos' hooks actually take. It must stay advisory.
    """
    r = root / "warn"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n\nSee [gone](docs/GONE.md).\n"})
    res = run(r, "bash", str(CHECK), "--all", "--mode=warn")
    assert res.returncode == 0, f"warn mode gated:\n{res.stdout}"
    assert "warn mode" in res.stdout, res.stdout


@case
def docs_check_staged_scope_ignores_untouched_files(root: Path) -> None:
    """The gate under --staged reports on the commit, not on the repo's history.

    This is the end-to-end shape of the defect: a repo with one old orphan
    page failed every commit that had nothing to do with it.
    """
    r = root / "scope"
    r.mkdir()
    new_repo(r)
    make(r, {"README.md": "# Title\n", "docs/OLD.md": "# Old\n"})
    run(r, "git", "add", "-A")
    run(r, "git", "commit", "-qm", "init")
    (r / "unrelated.txt").write_text("x\n")
    run(r, "git", "add", "unrelated.txt")
    res = run(r, "bash", str(CHECK), "--staged")
    assert res.returncode == 0, f"an untouched old orphan failed this commit:\n{res.stdout}"

    # and staging the orphan itself must fail
    (r / "docs" / "NEW.md").write_text("# New\n")
    run(r, "git", "add", "docs/NEW.md")
    res = run(r, "bash", str(CHECK), "--staged", ok=False)
    assert res.returncode != 0, f"a staged orphan did not fail the gate:\n{res.stdout}"
    assert "docs-check: FAILED" in res.stdout, res.stdout


def main() -> int:
    only = sys.argv[1:]
    selected = [c for n, c in CASES.items() if not only or n in only]
    failed, ok = [], 0
    with tempfile.TemporaryDirectory(prefix="docs-lint-check-") as td:
        base = Path(td)
        for c in selected:
            try:
                c(base)
                ok += 1
                print(f"ok    {c.__name__}")
            except Exception:
                failed.append(c.__name__)
                print(f"FAIL  {c.__name__}")
                traceback.print_exc()
    print(f"\ncheck_docs_lint: {ok}/{len(selected)} cases ok"
          + (f" — FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
