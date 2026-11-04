#!/usr/bin/env python3
"""Mutation test: revert each fix and prove the test that covers it FAILS.

A test that cannot fail proves nothing. Every fix in this session rests on a
test, and the honest question is not "does the test pass now" but "would it
have caught the bug it was written for".

For each mutation:
  1. restore the PRE-FIX version of the source file (git checkout <parent> -- <file>)
  2. rebuild the artifact, if the file is kernel source
  3. run the ONE test that covers the fix
  4. assert the test FAILS
  5. restore the fixed version

A mutation that leaves the test PASSING is a hole: either the fix does not do
what it claims, or the test does not cover it. Both are worth knowing.

IT RUNS IN ITS OWN THROWAWAY WORKTREE. The live checkout is never mutated:
`git worktree add --detach` under the scratch directory, mutated there, and
removed at the end. A mutation harness that edits the repo it ships from is a
harness that can leave that repo broken.

Run: python3 scripts/mutation_check.py [--keep]
Exit 0 when every mutation was caught, 1 when any escaped.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SCRATCH = Path(os.environ.get("JCODE_SCRATCH_DIR") or tempfile.gettempdir()) / "genome-mutation"
ROOT = REPO          # rebound to the worktree by main()


def _version_at_head() -> str:
    import re
    text = (REPO / "src" / "01_constants.py").read_text()
    return re.search(r'^VERSION = "([^"]+)"', text, re.M).group(1)


VERSION_AT_HEAD = _version_at_head()


def sh(*args, cwd=None, check=True):
    # `cwd=ROOT` as a DEFAULT ARGUMENT is evaluated when the function is
    # DEFINED, so rebinding the global ROOT later (to point at the throwaway
    # worktree) would not change it — and the mutation would run against the
    # LIVE checkout. It is read at CALL time here, deliberately.
    r = subprocess.run(args, cwd=cwd or ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"{' '.join(args)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def restore(ref: str, path: str) -> None:
    """Put `path` back to the state at `ref` (a commit)."""
    # `--` pathspec and an explicit cwd: this must never touch the live
    # checkout, and `git checkout <ref> -- <path>` STAGES the change, so the
    # index is reset afterwards too.
    sh("git", "checkout", ref, "--", path)
    sh("git", "reset", "--quiet", "HEAD", "--", path)


def rebuild() -> None:
    """Rebuild scripts/genome from src/, if src/ changed.

    The build REFUSES to rewrite a released version's checksum — correct
    behaviour, and it blocks mutation testing: reverting a fix changes the
    bytes while the version stays the same. So the ledger line is restored
    from git around the rebuild, and the build's own guard is left intact
    for real builds.
    """
    rel = ROOT / "scripts" / "releases.txt"
    original = rel.read_bytes()
    try:
        sh(sys.executable, str(ROOT / "scripts" / "build.py"))
    except AssertionError:
        # the guard fired: drop the stale line for this version, rebuild, put it back
        text = original.decode()
        kept = [ln for ln in text.splitlines()
                if not ln.startswith(f"{VERSION_AT_HEAD} ")]
        rel.write_text("\n".join(kept) + "\n")
        sh(sys.executable, str(ROOT / "scripts" / "build.py"))
    finally:
        rel.write_bytes(original)


def kernel_suite(*cases):
    """Run named cases of the kernel self-check. Returns (exit_code, output)."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_genome.py"), *cases],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def docs_suite(*cases):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_docs_lint.py"), *cases],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


# (name, file to revert, ref holding the PRE-FIX version, needs rebuild, runner, cases)
#
# Each ref was verified by reading the code at that commit, not by a grep count:
#   85e3ec6  pre-72: prints `lint: clean [...]` with no `(filtered)`, and the
#             note went to stdout even under --json
#   01c4b38  the -72 honesty fix landed (note to stderr, `hidden` in the doc);
#             still pre-74
#   bda1775  the -74 JSON contract landed
#   4e925d4  pre-D003-exemption (no `internal_files`)
#   282af29  pre---staged and pre-exit-propagation (no `staged_paths`, no `RC=0`)
MUTATIONS = [
    ("code-filter-note",
     "src/09_lint_checks.py", "85e3ec6", True, kernel_suite, ("redteam7",)),
    ("json-stdout-contract",
     "src/09_lint_checks.py", "01c4b38", True, kernel_suite, ("redteam7",)),
    ("declared-patch-split",
     "src/16b_installs.py", "bda1775", True, kernel_suite, ("declared_local_patch",)),
    ("docs-gate-exit-code",
     "scripts/docs/docs-check.sh", "282af29", False, docs_suite, ("docs_check_propagates_a_failing_check",)),
    ("docs-staged-scope",
     "scripts/docs/docs_lint.py", "282af29", False, docs_suite, ("staged_scope_reports_only_staged_files",)),
    ("d003-records-exemption",
     "scripts/docs/docs_lint.py", "4e925d4", False, docs_suite, ("d003_exempts_the_generated_records_index",)),
    ("docs-json-stdout-contract",
     "scripts/docs/docs_lint.py", "7ad2461", False, docs_suite, ("json_stdout_is_one_document",)),
]


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true",
                    help="leave the worktree in place (for debugging)")
    args = ap.parse_args()

    # A THROWAWAY WORKTREE, so the live checkout is never mutated.
    SCRATCH.mkdir(parents=True, exist_ok=True)
    wt = SCRATCH / "tree"
    if wt.exists():
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)],
                       capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach", str(wt), "HEAD"],
                   check=True, capture_output=True)
    ROOT = wt

    # THE ISOLATION MUST HOLD, and it is asserted rather than assumed. The
    # first version of this harness had `def sh(*args, cwd=ROOT)`: a default
    # argument is evaluated when the function is DEFINED, so rebinding the
    # global ROOT later changed nothing — and the first mutation ran against
    # the LIVE checkout, reverting four files there. The live tree was
    # restored from HEAD, but the lesson stands: a harness that edits the repo
    # it ships from can break it, and the only defence is to CHECK.
    live = REPO.resolve()
    if live == wt.resolve() or live in wt.resolve().parents:
        print("FATAL: the mutation worktree resolves inside the live checkout — refusing to mutate anything")
        return 2
    if not (wt / "scripts" / "genome").is_file():
        print("FATAL: the mutation worktree is not a usable checkout")
        return 2
    print(f"mutating in {wt} (the live checkout at {REPO} is not touched)")

    escaped, caught = [], []
    for name, path, ref, needs_build, runner, cases in MUTATIONS:
        # the fixed state, captured so the restore is exact
        original = (ROOT / path).read_bytes()
        try:
            restore(ref, path)
            if needs_build:
                rebuild()
            rc, out = runner(*cases)
            if rc == 0:
                escaped.append(name)
                print(f"ESCAPED  {name}: the test still PASSED with the fix reverted")
                print(f"         (file={path} ref={ref} cases={','.join(cases)})")
            else:
                caught.append(name)
                first = next((ln for ln in out.splitlines()
                              if ln.startswith("FAIL") or "AssertionError" in ln), out.splitlines()[-1:][0] if out else "")
                print(f"caught   {name}: the test FAILED as it must  [{first.strip()[:90]}]")
        except Exception as e:
            escaped.append(name)
            print(f"ERROR    {name}: {e}")
        finally:
            # restore the fixed file byte for byte
            (ROOT / path).write_bytes(original)
            if needs_build:
                rebuild()

    print(f"\nmutation_check: {len(caught)}/{len(MUTATIONS)} mutations caught"
          + (f" — ESCAPED: {', '.join(escaped)}" if escaped else ""))
    # PROVE THE LIVE CHECKOUT WAS NOT TOUCHED, rather than asserting it. The
    # harness reverts files with `git checkout <ref> -- <path>`, which STAGES;
    # a bug in the cwd binding once reverted four files in the live checkout.
    # So the live tree's own state is captured and compared after the run.
    live_dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                                 capture_output=True, text=True).stdout.strip()
    live_staged = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--name-only"],
                                  capture_output=True, text=True).stdout.strip()
    if live_dirty or live_staged:
        print(f"FATAL: the live checkout at {REPO} was modified by this run:\n{live_dirty}\n{live_staged}")
        escaped.append("live-checkout-mutated")
    else:
        print(f"live checkout untouched (clean status, clean index): {REPO}")
    if args.keep:
        print(f"(--keep: the worktree is left at {wt})")
    else:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)],
                       capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    return 1 if escaped else 0


if __name__ == "__main__":
    sys.exit(main())
