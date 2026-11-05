#!/usr/bin/env python3
"""The MUTATIONS for the push rung — the check that reports a committed but unpushed
vendored CLI, and the `--refresh` flag that buys certainty about the remote.

WHY THIS FILE EXISTS. The push rung's guard lived only in a scratch harness
(`/home/ishanp/.jcode/scratch/...`). The scratch directory is not the repo, so
the next person who edits `_unpushed_cli` had NO shipped guard — the d10 lesson
(a guard that is not in the repo is not a guard) applied to my own work. These
mutations move that guard into `scripts/mutation_check.py`, where the repo's own
gate runs it.

WHY A SEPARATE MODULE, like scripts/mutation_install_sh.py and friends. The
repo's MUTATIONS list expresses a mutation as a git revert to a commit holding
the pre-fix file. The push rung's guard and the guarded logic arrived TOGETHER
(the case and the fix were written in the same change), so there is no pre-fix
commit to revert to that would revert only the push rung. The equivalent is a
small edit that removes the guard while leaving the file parseable, which is
what this module does.

THE MUTATIONS, aimed at the ways this check can be a lie:
  unpushed-needs-the-network    the check consults the live remote again — the
                                d12 defect: 58.75s of network across the fleet,
                                and 49 MINUTES with the remotes unreachable.
  unpushed-remote-probe         the remote RESOLUTION probes the network.
  unpushed-unknown-reads-clean  a repo with no tracking ref reads as clean.
  unpushed-count-dropped        the detail drops how many commits are unpushed.
  unpushed-no-remote-reported   a repo with no remote at all is reported.
  unpushed-wrong-branch         the count is taken against the remote's DEFAULT
                                branch instead of the branch's own upstream —
                                which misattributes the remote's own commits to
                                the local repo. Measured on the fleet: it said 48
                                and 41 unpushed commits where the truth was 1.
  unpushed-zero-count-reported  a count of zero is reported as unpushed.
  refresh-never-runs            the --refresh flag does nothing at all.
  refresh-failure-silent        a failed refresh is silent, so a stale verdict
                                reads as a fresh one.
  refresh-failure-invents       a failed refresh invents an UNPUSHED row.
  refresh-creates-tracking-ref  the refresh creates a tracking ref for a remote
                                the checkout has NEVER contacted, converting the
                                "cannot be decided" unknown into a false
                                certainty.
  refresh-unbounded             the refresh has no timeout — the bound that
                                keeps it from becoming the d12 defect again.
  refresh-on-by-default         the refresh runs by default, so the default path
                                touches the network.

EVERY MUTATION MUST LAND. Each one edits a named string in the source, and the
edit is ASSERTED: if the string is not found, the mutation raises rather than
silently doing nothing. A mutation that changes nothing is an equivalent
mutation, and an equivalent mutation proves nothing.
"""
from pathlib import Path

INSTALLS = "src/16b_installs.py"


def _edit(root: Path, name: str) -> None:
    """Apply one named mutation to the worktree's src/16b_installs.py.

    Raises if the target text is not found: a mutation that cannot be applied is
    not a mutation, and a harness that cannot tell the difference reports
    false results in BOTH directions — a real mutation looks escaped, and an
    escape looks caught."""
    p = root / INSTALLS
    t = p.read_text()
    before = t

    if name == "unpushed-needs-the-network":
        # The comparison goes back to the REMOTE NAME instead of the local
        # tracking ref, so git has to ask the remote — which is the d12 defect.
        old = '                             f"{ref}..HEAD"],'
        new = '                             f"{remote}..HEAD"],'
    elif name == "unpushed-remote-probe":
        # The remote RESOLUTION probes the network to find a remote that answers.
        old = ("    for name in order:\n"
               "        return (name, _tracking_ref(repo, name, spec))")
        new = ("    for name in order:\n"
               "        probe = subprocess.run([\"git\", \"-C\", str(repo), \"ls-remote\", name, \"HEAD\"],\n"
               "                               capture_output=True, text=True, timeout=60)\n"
               "        if probe.returncode == 0 and probe.stdout.strip():\n"
               "            return (name, _tracking_ref(repo, name, spec))")
    elif name == "unpushed-unknown-reads-clean":
        old = ('        return (cli, f"remote {remote} has never been fetched or pushed to, so whether "\n'
               '                     f"the local commit is pushed cannot be decided")\n')
        new = "        return None\n"
    elif name == "unpushed-count-dropped":
        old = 'f"{n} commit(s) on HEAD are not on {remote}"'
        new = 'f"a commit is not on {remote}"'
    elif name == "unpushed-no-remote-reported":
        old = ("        # No remote at all: unversioned, not unpushed.\n"
               "        return None\n")
        new = '        return (cli, "no remote at all")\n'
    elif name == "unpushed-wrong-branch":
        # The branch's own upstream is no longer preferred, so the comparison
        # falls back to the remote's default branch.
        old = ('    if spec and spec.startswith(remote + "/"):\n'
               '        cand = f"refs/remotes/{spec}"\n'
               '        if _ref_exists(repo, cand):\n'
               '            return cand\n')
        new = ""
    elif name == "unpushed-zero-count-reported":
        old = ('    if n == "0":\n'
               '        # Every local commit is already on the remote\'s last known state, so\n'
               '        # there is nothing to push.\n'
               '        return None\n')
        new = ""
    elif name == "refresh-never-runs":
        old = ("                if ref:\n"
               "                    ok, note = _refresh_tracking_refs(p, remote)\n"
               "                    if not ok:\n"
               "                        refresh_failures.append((r, note))\n")
        new = "                if False:\n                    pass\n"
    elif name == "refresh-failure-silent":
        old = ("                    if not ok:\n"
               "                        refresh_failures.append((r, note))\n")
        new = "                    if False:\n                        pass\n"
    elif name == "refresh-failure-invents":
        old = ("                    if not ok:\n"
               "                        refresh_failures.append((r, note))\n")
        new = ("                    if not ok:\n"
               "                        unpushed.append((r, (p, f\"the fetch from {remote} failed: {note}\")))\n")
    elif name == "refresh-creates-tracking-ref":
        old = ("                if ref:\n"
               "                    ok, note = _refresh_tracking_refs(p, remote)\n")
        new = ("                if True:\n"
               "                    ok, note = _refresh_tracking_refs(p, remote)\n")
    elif name == "refresh-unbounded":
        old = '        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)'
        new = '        r = subprocess.run(cmd, capture_output=True, text=True, env=env)'
    elif name == "refresh-on-by-default":
        old = ("        if refresh:\n"
               "            resolved = _push_remote(p)\n")
        new = ("        if True:\n"
               "            resolved = _push_remote(p)\n")
    else:
        raise ValueError(f"unknown push-rung mutation: {name}")

    if old not in t:
        raise AssertionError(
            f"the mutation {name!r} could not be applied: the target text is not in "
            f"{INSTALLS}. Either the source changed or the mutation is now "
            f"equivalent to the original. An unapplicable mutation proves nothing.")
    t = t.replace(old, new, 1)
    if t == before:
        raise AssertionError(f"the mutation {name!r} changed nothing")
    p.write_text(t)


def mutate_push_rung(root: Path, name: str) -> None:
    """Apply one push-rung mutation to the worktree at `root`."""
    _edit(root, name)


# The names this module knows how to apply. mutation_check.py asserts that every
# entry it lists is in here, so a typo cannot silently become a no-op mutation.
NAMES = (
    "unpushed-needs-the-network",
    "unpushed-remote-probe",
    "unpushed-unknown-reads-clean",
    "unpushed-count-dropped",
    "unpushed-no-remote-reported",
    "unpushed-wrong-branch",
    "unpushed-zero-count-reported",
    "refresh-never-runs",
    "refresh-failure-silent",
    "refresh-failure-invents",
    "refresh-creates-tracking-ref",
    "refresh-unbounded",
    "refresh-on-by-default",
)
