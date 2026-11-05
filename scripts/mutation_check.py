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
sys.path.insert(0, str(HERE))
import mutation_install_sh  # noqa: E402  (needs HERE on the path first)
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
    # The git-restore dance below keeps the ledger honest, but the belt to its braces:
    # a mutation rebuild is a TRANSIENT build, so the ledger must not learn its checksum
    # at all (GENOME_NO_LEDGER is the build's own opt-out for exactly this).
    os.environ["GENOME_NO_LEDGER"] = "1"
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
        os.environ.pop("GENOME_NO_LEDGER", None)


def kernel_suite(*cases):
    """Run named cases of the kernel self-check. Returns (exit_code, output)."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_genome.py"), *cases],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def docs_suite(*cases):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_docs_lint.py"), *cases],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def modes_suite(*cases):
    """Run named cases of the package-modes suite (the installer cases).

    The modes suite installs the BUILT artefacts, and it refuses to run when
    `dist/` is missing or older than `scripts/genome` ("stale dist/: ... Run
    `uv build` first"). In a FRESH WORKTREE `dist/` is gitignored and absent,
    so the suite exits on that guard BEFORE it runs any case. A mutation
    harness that reads only the exit code then sees "the test failed" and
    reports the mutation CAUGHT — for a reason that has nothing to do with the
    mutation. Measured 2026-11-05: two install.sh mutations were reported
    "caught" with the symptom `Run `uv build` first.`, while the unmutated
    control failed the SAME way. A harness that cannot distinguish "failed
    because of the mutation" from "failed because the fixture was missing"
    measures nothing.

    So the wheel is built here, and the suite's own verdict is checked for the
    case's name: the failure must name the case that was expected to fail.
    """
    ensure_dist_built()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_package_modes.py"), *cases],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def ensure_dist_built():
    """Build the package artefacts if `dist/` is missing or stale.

    `scripts/build.py` builds the KERNEL (scripts/genome); the WHEEL the
    installer cases install comes from `uv build`. Both are needed, and in this
    order: the suite refuses artefacts older than the kernel they were built
    from.
    """
    dist = ROOT / "dist"
    arts = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    built = ROOT / "scripts" / "genome"
    if arts and built.exists() and all(a.stat().st_mtime >= built.stat().st_mtime for a in arts):
        return
    # The kernel first (it is what the artefacts are built from), then the package.
    try:
        sh(sys.executable, str(ROOT / "scripts" / "build.py"))
    except AssertionError:
        pass
    sh("uv", "build")


def install_sh_mutation(name):
    """The MUTATION for one of the two V-111 install.sh guards.

    The repo's MUTATIONS list expresses a mutation as a git revert to a commit
    holding the pre-fix file. The two V-111 install.sh guards were ADDED, so no
    such commit exists: the guarded logic and the guard arrived together. For
    those, the equivalent is a small edit that removes the guard while leaving
    the script parseable, which is what scripts/mutation_install_sh.py does.

    This returns the MUTATION ITSELF, not a runner that applies it and then
    runs the suite. That separation is load-bearing: the control phase calls
    the plain runner, so a bundled mutate-and-run would make the "control" a
    second mutation — which is exactly the bug measured on 2026-11-05, when
    the control for both install.sh mutations FAILED and the harness correctly
    refused to claim a catch.

    The mutation is applied to the THROWAWAY worktree (ROOT), never to the live
    checkout, and the caller's finally-block restores the file byte for byte.
    """
    def apply():
        mutation_install_sh.mutate(ROOT, name)
    return apply


# (name, file to revert, ref holding the PRE-FIX version, needs rebuild, runner, cases)
#
# Each entry may carry a 7th element: an EXTRA mutation to apply on top of the
# git revert. It is a callable, not a runner, so the control phase can run the
# plain suite and the mutation phase can apply it.
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
    # The two V-111 install.sh guards. They were ADDED, so there is no pre-fix
    # commit to revert to; the ref is the CURRENT commit (a no-op restore) and
    # the mutation is applied by the runner. See scripts/mutation_install_sh.py.
    ("install-sh-no-build-py-refusal",
     "install.sh", "HEAD", False, modes_suite,
     ("installer_local_source_never_breaks_a_working_install",),
     install_sh_mutation("no-build-py-refusal")),
    ("install-sh-prebuild-unreachable",
     "install.sh", "HEAD", False, modes_suite,
     ("installer_local_source_never_breaks_a_working_install",),
     install_sh_mutation("prebuild-unreachable")),
    # The append-only rule.  aa4b44b holds the net-diff-over-a-window check, which
    # reported a COMPLIANT REPAIR as a violation (the window's base could itself be
    # the violating commit) and could not see an in-place edit inside a file added
    # after that base.  The publication-aware rule fixes both.
    ("append-only-publication-rule",
     "src/10_doctor.py", "aa4b44b", True, kernel_suite,
     ("append_only_publication_rule", "append_only_repair_in_working_tree")),
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

    # The live checkout's state is captured BEFORE the run and compared after.
    # Comparing only AFTER would blame the harness for edits that were already
    # there: measured 2026-11-05, an uncommitted change of my own was reported
    # as "FATAL: the live checkout was modified by this run". The harness's
    # claim is that IT changed nothing, so the evidence must be a DIFF of the
    # before/after state, not the presence of any dirt.
    live_before = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                                  capture_output=True, text=True).stdout
    live_before_staged = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--name-only"],
                                        capture_output=True, text=True).stdout

    # THE CONTROL MUST BE MEASURED, NOT ASSUMED. A mutation is only evidence
    # that a FAILING test failed because of the mutation. If the unmutated test
    # also fails — a missing fixture, a build the worktree does not have, a
    # suite that exits on a precondition — then every "caught" below is a
    # coincidence and the whole run is noise. Measured 2026-11-05: the two
    # install.sh mutations were reported "caught" with the symptom
    # `Run `uv build` first.`, because `dist/` is gitignored and absent in a
    # fresh worktree. The unmutated control failed the SAME way. So the control
    # is run first, and if it does not pass, the run stops: there is nothing to
    # measure.
    print("control: running each mutation's own test UNMUTATED, in this worktree")
    bad_control = []
    for name, path, ref, needs_build, runner, cases, *extra in MUTATIONS:
        original = (ROOT / path).read_bytes()
        try:
            rc, out = runner(*cases)
        except Exception as e:
            rc, out = 1, f"runner raised: {e}"
        finally:
            # the runner may have mutated (install_sh_mutation); put it back
            (ROOT / path).write_bytes(original)
            if needs_build:
                rebuild()
        if rc == 0:
            print(f"control  {name}: PASSES unmutated  (so a FAIL below means the mutation)")
        else:
            bad_control.append(name)
            first = next((ln for ln in out.splitlines()
                          if ln.startswith("FAIL") or "stale" in ln or "Error" in ln), out.splitlines()[-1:][0] if out else "")
            print(f"control  {name}: FAILS unmutated — this run cannot prove anything  [{first.strip()[:90]}]")
    if bad_control:
        print(f"\nFATAL: {len(bad_control)} mutation(s) have a control that does not pass: "
              f"{', '.join(bad_control)}.\n"
              "A test that already fails proves nothing about the mutation. Fix the fixture "
              "(for installer cases: `uv build` in the worktree) and re-run.")
        print(f"(the worktree is left at {wt} for inspection)")
        return 2

    escaped, caught = [], []
    for name, path, ref, needs_build, runner, cases, *extra in MUTATIONS:
        # the fixed state, captured so the restore is exact
        original = (ROOT / path).read_bytes()
        try:
            restore(ref, path)
            if needs_build:
                rebuild()
            for apply in extra:
                apply()
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
                                 capture_output=True, text=True).stdout
    live_staged = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--name-only"],
                                  capture_output=True, text=True).stdout
    if live_dirty != live_before or live_staged != live_before_staged:
        print(f"FATAL: the live checkout at {REPO} was modified by this run:\n"
              f"before: {live_before!r}\nafter:  {live_dirty!r}\n"
              f"staged before: {live_before_staged!r}\nstaged after:  {live_staged!r}")
        escaped.append("live-checkout-mutated")
    else:
        print(f"live checkout untouched by this run (state identical before and after): {REPO}")
    if args.keep:
        print(f"(--keep: the worktree is left at {wt})")
    else:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)],
                       capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    return 1 if escaped else 0


if __name__ == "__main__":
    sys.exit(main())
