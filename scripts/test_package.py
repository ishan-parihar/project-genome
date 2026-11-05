#!/usr/bin/env python3
"""Self-check for the PACKAGE: build the wheel, install it in a throwaway venv, and
assert the contracts the packaging makes.

Why this exists: the packaging defects found on 2026-10-29 (a site-packages copy
whose `python -m` path was never exercised, a verify step that reported success
for a binary the run had not installed, a last pip rung that is refused on an
externally-managed Python, and a venv re-run that silently no-ops) were all
found by RUNNING the installer, not by reading it, because nothing here tested
the package. Each of them is now pinned by a case below.

Run: python3 scripts/test_package.py [case ...]   (stdlib only; needs `python3 -m venv`)
Every selected case runs even when one fails; the summary lists them all and the
exit code is 1 on any failure.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "genome"
WHEEL_GLOBS = ["dist/project_genome-*.whl", "dist/*.whl"]

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# Which shipped suites can be judged from an extracted sdist, and how to tell.
#
# Measured 2026-11-05 from the extracted sdist, after making it a complete
# environment (git init + commit, then build.py, then uv build):
#
#   build.py              exit 0
#   check_docs_lint.py    exit 0   11/11
#   check_ps1.py          exit 0
#   test_genome.py        exit 0   51/51
#   mutation_check.py     exit 1   reverts fixes by `git checkout <sha>`; an
#                                    sdist has no history, so every mutation
#                                    is reported ESCAPED because the REF does
#                                    not exist
#   test_package_modes.py exit 1   installs the artefacts and compares them
#   test_package.py       exit 1   same
#
# The last three are STRUCTURAL limits of an sdist, not packaging defects:
# a source distribution is not a checkout and does not carry build output.
#
# The skip is decided by BEHAVIOUR — what the suite printed — not by reading
# the source for the word "git". An earlier version of this rule grepped the
# text, and `check_docs_lint.py` matched: it runs `git init` on fixtures it
# creates itself, so it does NOT need a checkout. Skipping it hid the very
# defect the case exists for, and a mutation that changed only the quote
# style of `DOCS = HERE / "docs"` escaped every check.
#
# So the question is asked of the OUTPUT: did the suite fail because a
# HISTORICAL REF is missing, or because it needs the artefacts it installs?
# Those are the two structural limits, and each has its own signature.


def runnable_in_an_sdist(rel: str, result, output: str) -> bool:
    """True when this suite's failure is NOT a packaging defect.

    A suite that fails in the extracted sdist because it needs git HISTORY or
    the built artefacts is judging something an sdist cannot provide. One that
    fails because a file it ships is missing IS the defect this case is for.

    A USAGE ERROR is also not a packaging defect: `score_readme.py` takes a
    required `readme` positional, so running it with no arguments is asking it
    the wrong question. It works in the sdist when given a README:

        score_readme.py README.md  ->  exit 0, "Score: 4/8 [generic]"

    The signature is argparse's, not the exit code: argparse exits 2 on a usage
    error, and `docs_lint.py` ALSO exits 2 on a hard finding. The two are
    told apart by the output — argparse prints "usage:" and "error:", the
    gate prints "docs_lint: FAIL" and a count of hard failures.
    """
    if result.returncode == 0:
        return True
    low = output.lower()
    # argparse usage error: the wrong question was asked, not a broken artefact
    if "usage:" in low and "error:" in low:
        return False
    # mutation_check.py: `git checkout <sha>` against a ref that does not exist
    if "invalid reference" in low or ("does not exist" in low and "checkout" in low):
        return False
    if "unknown revision" in low:
        return False
    # the packaging suites: they install dist/ and need it to be current
    if "run `uv build` first" in low or "stale dist/" in low:
        return False
    return True


def suite_path_bindings(path: Path):
    """The repo-relative paths a suite declares as module-level Path bindings.

    Read by IMPORTING the suite and inspecting its namespace, so how the path
    was spelled does not matter — `DOCS = HERE / "docs"` and
    `DOCS = HERE / 'docs'` are the same declaration. A regex over the source
    missed the second form, and a mutation using it escaped the check.

    `build.py` is excluded: it writes `scripts/genome` and the release
    ledger at import time, so importing it would mutate the working tree
    while the test is running.
    """
    import importlib.util

    if path.name == "build.py":
        return []
    spec = importlib.util.spec_from_file_location("pkgprobe_" + path.stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        # a suite that cannot even be imported cannot be judged here
        return []
    out = []
    for value in vars(mod).values():
        if isinstance(value, Path):
            try:
                out.append(value.resolve())
            except OSError:
                continue
    return out


def git_tracked_paths():
    """Every path git tracks in this repo, as repo-relative posix strings.

    This is the fact the "suite needs a subject" rule is built on. A path
    that git tracks is part of the repo's SOURCE; a path git does not track
    is build output or scratch (`dist/`, `__pycache__/`), and an sdist is
    not supposed to carry it. Measured 2026-11-05: `dist/` is not tracked,
    which is why `test_package.py`'s `DIST = ROOT / "dist"` is not a
    packaging defect and `scripts/docs/` is.
    """
    r = run(["git", "-C", str(ROOT), "ls-files", "-z"])
    assert r.returncode == 0, f"git ls-files failed: {r.stderr[-300:]}"
    return {p for p in r.stdout.split("\0") if p}


def venv_with_wheel(name="vpkg"):
    """A throwaway venv with THIS wheel installed. Raises with the real output on failure."""
    tmp = Path(tempfile.mkdtemp(prefix=f"genome-{name}-"))
    venv = run([sys.executable, "-m", "venv", str(tmp / "venv")])
    if venv.returncode != 0:
        raise RuntimeError(f"venv creation failed: {venv.stderr[-400:]}")
    vpy = tmp / "venv" / "bin" / "python"
    wheels = sorted((ROOT / "dist").glob("*.whl"))
    if not wheels:
        raise RuntimeError("no wheel in dist/ — build it first (scripts/build.py already ran; run `uv build`)")
    inst = run([str(vpy), "-m", "pip", "install", "--quiet", "--force-reinstall", str(wheels[-1])])
    if inst.returncode != 0:
        raise RuntimeError(f"wheel install failed: {inst.stderr[-600:]}")
    return tmp, vpy, wheels[-1]


def isolated_env(tmp: Path, name: str = "home") -> tuple:
    """An environment in which the installed CLI sees NOTHING of the live machine.

    A packaging suite must depend on the wheel it built, and on nothing else.
    `genome upgrade` for an INSTALLED package compares the package against what
    it would converge on, and `_package_reference()` probes four home-directory
    skills roots plus every vendored row in the fleet-wide installs manifest.
    So an un-isolated run of the installed-mode cases reads the OPERATOR'S
    machine: measured 2026-11-05, all four roots here were at 2026.11.05-14
    while the wheel built from this checkout was at -13, so the package
    honestly printed "BEHIND" and the case failed.

    That failure was the TEST's defect, not the product's. The product was right:
    the package really was behind. The case asserted "up to date" — an outcome
    that depends on the machine, not on the artefact. It was green by machine
    state, which is the same silent-green class this suite exists to catch, one
    level down.

    BOTH inputs are isolated, and each isolation is load-bearing:

      HOME            -> the four skills roots are probed through it.
      GENOME_INSTALLS -> the fleet-wide vendored rows are read from it.
                        `installs_manifest()` reads this variable and NOT
                        `XDG_CONFIG_HOME`, so overriding HOME alone would still
                        let the whole fleet's rows in.

    `GENOME_SKILL` is cleared because it names a reference outright and would
    win over everything else.

    Each branch gets its OWN home, so one branch's fixture cannot be seen by
    the next one: the reference probe takes the NEWEST candidate, and a
    leftover fixture would silently change what a later branch compares
    against.

    Returns (env, home) so a caller can write fixtures into that home.
    """
    home = tmp / name
    home.mkdir(parents=True, exist_ok=True)
    manifest = home / "installs.json"
    manifest.write_text(json.dumps({"schema": 1, "installs": []}))
    env = dict(os.environ, HOME=str(home), GENOME_INSTALLS=str(manifest))
    env.pop("GENOME_SKILL", None)
    return env, home


def fake_skill_root(home: Path, version: str) -> Path:
    """A skills root under `home` carrying a given VERSION, for the comparison tests."""
    d = home / ".agents" / "skills" / "project-genome" / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "genome"
    f.write_text(f'#!/usr/bin/env python3\nVERSION = "{version}"\n')
    return f


def fake_vendored_row(manifest: Path, root: Path, version: str) -> Path:
    """A vendored row in an installs manifest, pointing at a fixture copy.

    This is the manifest half of the reference: `_package_reference()` reads
    every vendored row and takes the newest. A manifest row is the ONLY way to
    reach a reference that is not under HOME, so it is what makes the
    GENOME_INSTALLS isolation OBSERVABLE — without such a case, a suite that
    forgot to override the manifest would still pass whenever the live fleet
    happened to agree with the wheel.

    Measured 2026-11-05: the live fleet's vendored copies are all at or behind
    the wheel, so reading the live manifest changed nothing on this machine.
    That is luck, not isolation, and it is why the manifest needs its own case.
    """
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    f = scripts / "genome"
    f.write_text(f'#!/usr/bin/env python3\nVERSION = "{version}"\n')
    manifest.write_text(json.dumps({
        "schema": 1,
        "installs": [{"kind": "vendored", "path": str(root), "version": version}],
    }))
    return f


def wheel_cli_version(wheel) -> str:
    """The VERSION stamp the PACKAGED CLI carries, read from the wheel itself.

    Read from the artefact rather than from `scripts/genome`, because those two
    can disagree: the wheel in dist/ is built from whatever the tree carried at
    build time, and the tree is rebuilt independently. Measured 2026-11-05: the
    wheel carried -13 while the tree already carried -14.
    """
    import zipfile

    with zipfile.ZipFile(wheel) as z:
        names = [n for n in z.namelist() if n.endswith("/_genome.py") or n == "project_genome/_genome.py"]
        if not names:
            raise RuntimeError(f"the wheel does not contain project_genome/_genome.py: {z.namelist()[:8]}")
        text = z.read(names[0]).decode(errors="replace")
    m = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    return m.group(1) if m else ""


def wheel_cli_bytes(wheel):
    """The packaged CLI bytes as they land in site-packages (the shipped copy)."""
    with zipfile.ZipFile(wheel) as z:
        names = [n for n in z.namelist() if n.endswith("/_genome.py") or n == "project_genome/_genome.py"]
        if not names:
            raise RuntimeError(f"the wheel does not contain project_genome/_genome.py: {z.namelist()[:8]}")
        return z.read(names[0])


# ── the contracts the packaging makes ────────────────────────────────────────


@case
def wheel_ships_the_same_bytes_the_repos_vendor():
    """A pip-installed genome and a vendored genome are the same bytes — that is the
    only thing that makes `genome upgrade`'s release-checksum comparison meaningful
    for an installed copy."""
    tmp, vpy, wheel = venv_with_wheel("bytes")
    try:
        vendored = hashlib.sha256(CLI.read_bytes()).hexdigest()
        packaged = hashlib.sha256(wheel_cli_bytes(wheel)).hexdigest()
        assert vendored == packaged, (
            f"bytes differ: vendored {vendored[:12]} vs packaged {packaged[:12]}. "
            "The wheel must ship scripts/genome itself, not a copy of it."
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def console_script_runs():
    """The entry point resolves and reports the version the source tree carries."""
    tmp, vpy, _ = venv_with_wheel("entrypoint")
    try:
        binpath = tmp / "venv" / "bin" / "genome"
        assert binpath.is_file(), f"no console script at {binpath}"
        out = run([str(binpath), "--version"])
        assert out.returncode == 0, f"--version failed: {out.stderr[-300:]}"
        want = next(
            (l.split('"')[1] for l in CLI.read_text().splitlines() if l.startswith("VERSION = ")),
            None,
        )
        assert want and want in out.stdout, f"expected {want!r} in {out.stdout.strip()!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def python_dash_m_runs():
    """`python -m project_genome` runs the CLI — the form a CI job reaches for when
    there is no console script on PATH."""
    tmp, vpy, _ = venv_with_wheel("modrun")
    try:
        out = run([str(vpy), "-m", "project_genome", "--version"], cwd=str(tmp))
        assert out.returncode == 0, f"python -m failed: {out.stderr[-300:]}"
        assert "genome" in out.stdout, f"unexpected output: {out.stdout.strip()!r}"
        # the __main__ wrapper must not swallow the CLI's exit codes
        code = run([str(vpy), "-m", "project_genome", "definitely-not-a-command"], cwd=str(tmp))
        assert code.returncode != 0, "an unknown command exited 0 through the wrapper"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def installed_copy_behaves_like_the_vendored_copy():
    """The site-packages copy decides what it is from its own __file__, so the
    commands that compare it to a skills copy must behave identically in both
    modes — install says 'up to date' rather than failing on a missing skills dir.

    HERMETIC BY CONSTRUCTION. Measured 2026-11-05: this case used to read the
    OPERATOR'S machine. For an installed package, `genome upgrade` compares the
    package against what it would converge on, and that reference is probed
    outside the package: four home-directory skills roots plus every vendored
    row in the fleet-wide installs manifest. On this machine all four roots
    were at 2026.11.05-14 while the wheel built from this checkout was at -13,
    so the package honestly printed "BEHIND — this machine is at
    2026.11.05-14" and the case failed.

    The PRODUCT was right: the package really was behind. The CASE was wrong:
    it asserted "up to date", an outcome that depends on the machine rather
    than on the artefact. A packaging suite may depend on the wheel it built
    and on nothing else, or it is green by machine state — which is the
    silent-green class this whole suite exists to catch, one level down.

    So the comparison is made CONTROLLABLE instead of assumed. The environment
    is isolated (no live skills root, an empty installs manifest), and then
    three branches are each exercised on purpose:

      no reference      -> "up to date — ... no skills root on this machine
                           to compare against"
      reference SAME    -> "up to date (<path> is <version>)"
      reference NEWER   -> "BEHIND — this machine is at <version>"

    The third is the one that matters: it is the branch the operator saw, and
    it must still be reachable once the live machine is out of the way. A fix
    that made the comparison always print "up to date" would pass the old
    assertion and be a lie, so the NEWER case is asserted here, not just the
    comfortable one.
    """
    tmp, vpy, wheel = venv_with_wheel("mode")
    try:
        env, home = isolated_env(tmp)
        proj = tmp / "proj"
        proj.mkdir()
        init = run([str(vpy), "-m", "project_genome", "init", "--profile", "software"], cwd=str(proj), env=env)
        assert init.returncode == 0, f"init failed: {init.stderr[-400:]}"
        for cmd in (["upgrade"], ["doctor"], ["lint"]):
            out = run([str(vpy), "-m", "project_genome", *cmd], cwd=str(proj), env=env)
            assert out.returncode == 0, f"`{' '.join(cmd)}` failed in installed mode: {out.stdout[-400:]}{out.stderr[-400:]}"

        # BRANCH 1 — no reference anywhere. The installed copy has nothing to
        # converge on, and must say so rather than claim to be current.
        up = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj), env=env).stdout
        assert "up to date" in up, f"installed mode did not report up-to-date: {up.strip()!r}"
        assert "no skills root" in up, (
            f"installed mode claimed to be current without naming what it compared "
            f"against: {up.strip()!r}"
        )

        # BRANCH 2 — a reference at the SAME version is up to date, and says WHICH.
        mine = wheel_cli_version(wheel)
        assert mine, "the wheel carries no VERSION stamp"
        ref = fake_skill_root(home, mine)
        same = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj), env=env).stdout
        assert "up to date" in same, f"a same-version reference was reported as stale: {same.strip()!r}"
        assert str(ref) in same, f"the comparison did not name the reference it used: {same.strip()!r}"

        # BRANCH 3 — a reference NEWER means BEHIND. This is the branch the
        # operator saw, and it must survive the isolation. `upgrade` never
        # exits non-zero for an installed package: the package is a working
        # tool, and a gate failure here would say the machine is broken when
        # it is simply one release behind.
        fake_skill_root(home, "9999.01.01-1")
        behind = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj), env=env)
        assert behind.returncode == 0, (
            f"`upgrade` exited {behind.returncode} for a stale installed package: "
            f"{behind.stdout[-300:]}{behind.stderr[-300:]}"
        )
        assert "BEHIND" in behind.stdout, (
            f"a newer reference did not produce the BEHIND verdict: {behind.stdout.strip()!r}"
        )
        assert "9999.01.01-1" in behind.stdout, (
            f"the BEHIND verdict did not name the version to converge on: {behind.stdout.strip()!r}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def installed_reference_is_not_read_from_the_fleet_manifest():
    """A manifest row is the OTHER half of the installed copy's reference, and it
    is the half that is easiest to leave un-isolated.

    `_package_reference()` reads every vendored row of the installs manifest
    and takes the newest. `installs_manifest()` reads the `GENOME_INSTALLS`
    variable and NOT `XDG_CONFIG_HOME`, so isolating HOME alone is not enough:
    the whole fleet's rows would still be read. Measured 2026-11-05, the live
    fleet was at or behind the wheel, so the un-isolated run passed — luck, not
    isolation, and exactly the kind of green-by-machine-state this suite exists
    to catch. On any machine whose fleet leads the package, this becomes the
    operator's BEHIND again.

    So the manifest is isolated AND the isolation is exercised from BOTH sides:
    an isolated manifest row is honoured (the manifest half of the reference
    works), and the live manifest is not read (isolation holds).
    """
    tmp, vpy, wheel = venv_with_wheel("manifest")
    try:
        mine = wheel_cli_version(wheel)
        assert mine, "the wheel carries no VERSION stamp"

        # the manifest half of the reference works when it is OUR manifest
        env, home = isolated_env(tmp, "own")
        proj = tmp / "proj"
        proj.mkdir()
        init = run([str(vpy), "-m", "project_genome", "init", "--profile", "software"], cwd=str(proj), env=env)
        assert init.returncode == 0, f"init failed: {init.stderr[-300:]}"
        row = fake_vendored_row(home / "installs.json", tmp / "fleetrepo", mine)
        same = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj), env=env)
        assert same.returncode == 0, f"upgrade failed: {same.stdout[-300:]}{same.stderr[-300:]}"
        assert "up to date" in same.stdout, (
            f"a manifest row at the same version was not read: {same.stdout.strip()!r}"
        )
        assert str(row) in same.stdout, (
            f"the reference was read from somewhere other than the manifest row: {same.stdout.strip()!r}"
        )

        # and the LIVE manifest must not be read: a row that leads the package
        # is written into the isolated manifest, and the live fleet — which on
        # this machine sits behind the wheel — cannot supply it.
        led = fake_vendored_row(home / "installs.json", tmp / "fleetlead", "9999.01.01-1")
        behind = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj), env=env)
        assert behind.returncode == 0, (
            f"`upgrade` exited {behind.returncode} for a stale installed package: "
            f"{behind.stdout[-300:]}{behind.stderr[-300:]}"
        )
        assert "BEHIND" in behind.stdout, (
            f"a manifest row at a newer version produced no BEHIND verdict: {behind.stdout.strip()!r}"
        )
        assert str(led) in behind.stdout, (
            f"the BEHIND reference was not the manifest row: {behind.stdout.strip()!r}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def force_reinstall_restores_bytes_while_plain_install_does_not():
    """A re-run must not silently no-op: the PyPI version does not move when the CLI's
    VERSION stamp does, so `pip install` reports 'already satisfied' and leaves the
    old bytes. --force-reinstall restores them. This is the installer's venv rung."""
    tmp, vpy, wheel = venv_with_wheel("force")
    try:
        site = next((tmp / "venv").glob("lib/*/site-packages/project_genome/_genome.py"))
        good = site.read_bytes()

        # corrupt the installed copy, then reinstall WITHOUT --force-reinstall
        site.write_bytes(good + b"\n# tampered\n")
        plain = run([str(vpy), "-m", "pip", "install", "--quiet", str(wheel)])
        assert plain.returncode == 0, plain.stderr[-300:]
        assert site.read_bytes() != good, (
            "a plain `pip install` rewrote a corrupted file — if this ever fails the "
            "installer's forced installs are unnecessary, not that the corruption was kept"
        )

        site.write_bytes(good + b"\n# tampered\n")
        forced = run([str(vpy), "-m", "pip", "install", "--quiet", "--force-reinstall", str(wheel)])
        assert forced.returncode == 0, forced.stderr[-300:]
        assert site.read_bytes() == good, "--force-reinstall did not restore the exact bytes"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def missing_cli_file_fails_loudly():
    """If the wheel somehow shipped without the CLI file, the error must name the
    path and the fix, not traceback. (The guard in project_genome/__init__.py.)"""
    tmp, vpy, _ = venv_with_wheel("missing")
    try:
        site = next((tmp / "venv").glob("lib/*/site-packages/project_genome/_genome.py"))
        keep = site.with_name("_genome.py.keepme")
        site.rename(keep)
        try:
            # cwd is the throwaway dir, NOT the repo root: from the repo root the
            # wrapper legitimately falls back to the source build, which would make
            # this case pass for the wrong reason (it did).
            out = run([str(vpy), "-m", "project_genome", "--version"], cwd=str(tmp))
            assert out.returncode != 0, "a package with no CLI file exited 0"
            both = out.stdout + out.stderr
            assert "missing" in both.lower(), f"the error does not say what is wrong: {both.strip()[:200]!r}"
            assert "force-reinstall" in both, f"the error gives no remedy: {both.strip()[:200]!r}"
            assert "Traceback" not in both, "the guard leaked a traceback"
        finally:
            if keep.exists() and not site.exists():
                keep.rename(site)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def installer_chain_reaches_the_pip_floor():
    """On an externally-managed Python the last rung must not die: the installer
    simulates a host where `pip install --user` always fails, and the venv fallback
    must carry the install. Runs the real install.sh in an isolated HOME."""
    tmp = Path(tempfile.mkdtemp(prefix="genome-install-"))
    try:
        fake_bin = tmp / "bin"
        fake_bin.mkdir()
        py = fake_bin / "python3"
        py.write_text(
            "#!/bin/bash\n"
            'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
            '  echo "error: externally-managed-environment" >&2\n'
            "  exit 1\n"
            "fi\n"
            "exec /usr/bin/python3 \"$@\"\n"
        )
        py.chmod(0o755)
        for tool in ("bash", "sh", "env", "mkdir", "cat", "printf", "sed", "ls", "grep", "dirname",
                     "basename", "chmod", "touch", "head", "tail", "uname", "id", "git"):
            src = shutil.which(tool)
            if src:
                (fake_bin / tool).symlink_to(src)
        home = tmp / "home"
        (home / ".agents" / "skills").mkdir(parents=True)
        # the whole point is the pip rung, so build a PATH from this fake bin
        # plus the system dirs the installer needs — but note that a real host may
        # well have uv in /usr/sbin (this one does), and if it does, that is a
        # LEGITIMATE rung-1 install, not a defect. So do not assert which tool was
        # used: assert that the install SUCCEEDED and that the result is a genome
        # that runs. Where pip --user is refused (the fake python3 below), either
        # uv/pipx carries it, or the venv rung does; all three are acceptable.
        system_dirs = ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"]
        clean_path = ":".join([str(fake_bin), *[d for d in system_dirs if Path(d).is_dir()]])
        env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(tmp / "data"), PATH=clean_path)
        # uv is present on this host (in /usr/sbin) but cannot install, because
        # the package is NOT on PyPI yet — the pre-publication state, where no
        # PyPI rung can ever succeed. So the contract this pins is the SHAPE of
        # the chain: after uv fails, the installer must CONTINUE to the pip floor
        # (the venv), not stop at pipx or die at uv. The evidence it kept going
        # is the venv's own pip notice in the output, which only appears once
        # `python3 -m venv $PREFIX/tool` has run.
        out = run(["bash", str(ROOT / "install.sh"), "--no-cta"], env=env, cwd=str(tmp))
        text = out.stdout + out.stderr
        venv_marker = str(tmp / "data" / "project-genome" / "tool")
        assert venv_marker in text, (
            f"the chain never reached the pip floor (no venv was created): {text[-600:]}"
        )
        # with --skill the CLI install is unmet-but-reported and the run exits 0,
        # because the bundle is an explicit request that must still be honoured.
        out2 = run(["bash", str(ROOT / "install.sh"), "--skill", "--no-cta"], env=env, cwd=str(tmp))
        text2 = out2.stdout + out2.stderr
        assert out2.returncode == 0, f"the --skill run did not honour the bundle: {text2[-600:]}"
        assert "The skill bundle is installed" in text2, (
            f"the bundle was not delivered: {text2[-600:]}"
        )
        # the venv rung produces a genome that runs: it can only be exercised
        # against a source that exists, so drive the same fallback directly.
        venv = tmp / "direct"
        mk = run([str(fake_bin / "python3"), "-m", "venv", str(venv)], env=env)
        if mk.returncode == 0:
            inst = run([str(venv / "bin" / "pip"), "install", "--quiet", "--force-reinstall", str(sorted((ROOT / "dist").glob("*.whl"))[-1])], env=env)
            assert inst.returncode == 0, f"the venv pip install failed: {inst.stderr[-400:]}"
            ver = run([str(venv / "bin" / "genome"), "--version"], env=env)
            assert ver.returncode == 0 and "genome" in ver.stdout, f"the venv genome did not run: {ver.stdout!r}{ver.stderr!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def repo_local_invocation_runs_the_source_build():
    """From the repo root, `python -m project_genome` imports THIS directory's
    project_genome/ (the cwd precedes site-packages), and that package has no
    _genome.py — the file is force-included by the build and never committed. It
    must resolve to the source build rather than telling the operator to reinstall
    a package that is fine."""
    out = run([sys.executable, "-m", "project_genome", "--version"], cwd=str(ROOT))
    assert out.returncode == 0, f"the repo-local invocation failed: {out.stdout[-300:]}{out.stderr[-300:]}"
    assert "genome" in out.stdout, f"unexpected output: {out.stdout.strip()!r}"
    assert "missing" not in out.stdout.lower(), f"it blamed the install instead of running: {out.stdout.strip()!r}"


@case
def sdist_ships_the_files_its_own_suites_need():
    """A shipped suite must RUN from the sdist it ships in.

    Measured 2026-11-05: `scripts/check_docs_lint.py` was in the sdist's
    include list, and the two files it exists to test — `scripts/docs/docs_lint.py`
    and `scripts/docs/docs-check.sh` — were NOT. So the sdist carried a test
    suite whose subjects were absent, and running it there died with a
    traceback on its first case (exit 120).

    That is the silent-green direction again, one level up: the suite passed
    11/11 in the repo, so nothing was red, and the artefact it produced was
    broken for anyone who extracted it. A green run in the repo says nothing
    about the artefact.

    The property asserted here is general, not specific to the docs gate, and
    it is asserted TWICE, by two independent means, because the first version
    of this case had four separate holes in it (each recorded below).

    RULE 1 — the subject rule. A suite's subject is a path that is BOTH
      (a) TRACKED by git — it is part of the repo's SOURCE, so the sdist
          ought to carry it; and
      (b) bound by a module-level `Path` in a suite the sdist ships.

    (a) is the fact that separates a real subject from build output.
    `dist/` is bound by `test_package.py` and `test_package_modes.py`, but it
    is NOT tracked: it is build output, and an sdist does not carry it.
    `scripts/docs/` IS tracked, IS bound by `check_docs_lint.py`, and was
    missing — that was the defect.

    The bindings are read by IMPORTING each suite, so how the path was
    spelled does not matter. A regex over the source was tried first and had
    two holes: it matched a bare literal in a docstring, and it missed
    `DOCS = HERE / 'docs'` — a mutation that changed only the quote style
    ESCAPED every check in the case.

    RULE 2 — the run rule. The sdist is extracted and every shipped suite is
    RUN there. A suite that cannot pass there is a broken artefact, and the
    exit code is the verdict.

    The environment is made COMPLETE before the suites run, because an sdist
    is not a checkout and does not carry build output. Measured 2026-11-05
    from the extracted sdist, in this order:

      git init + commit   -> a checkout to work from
      scripts/build.py    -> rebuilds scripts/genome (exit 0)
      uv build            -> produces dist/ (exit 0)

    `build.py` runs BEFORE `uv build` because the order matters: `build.py`
    rewrites `scripts/genome`, and `test_package_modes.py` refuses to run
    when `dist/` is OLDER than `scripts/genome`. With that order, every
    shipped suite passes in the extracted sdist except two, and both are
    STRUCTURAL limits of an sdist rather than packaging defects:

      mutation_check.py     reverts fixes by `git checkout <historical-sha>`,
                            and an sdist has no history. Every mutation is
                            reported as ESCAPED because the REF does not
                            exist, not because the test passed.
      test_package_modes.py refuses to run against a dist/ that is not newer
                            than scripts/genome; uv build above satisfies
                            that, but the suite installs the artefacts and
                            compares them, which needs the wheel the sdist
                            was built from.

    Neither is a missing subject, so neither is what this case is about. The
    two rules are independent: RULE 1 catches a missing subject even when
    the suite cannot run at all, and RULE 2 catches a suite that runs but
    fails, even when no path binding names what it needed.
    """
    import tarfile

    # RECURSION GUARD. This case runs every shipped suite from the extracted
    # sdist — including `test_package.py`, which ships in that sdist and
    # contains THIS case. Without a guard the extracted copy would extract
    # its own sdist and run its own suites again, forever.
    #
    # The guard is an environment variable, so it travels with the child
    # process rather than depending on how the suite was invoked. The outer
    # run sets it; the extracted copy sees it and skips this one case, having
    # already been judged by the outer run.
    if os.environ.get("GENOME_SDIST_CHECK"):
        return

    sdists = sorted(ROOT.glob("dist/project_genome-*.tar.gz"), key=lambda p: p.stat().st_mtime)
    assert sdists, "no sdist in dist/ — run `uv build` first"
    sd = sdists[-1]
    with tarfile.open(sd) as tf:
        names = {n.split("/", 1)[1] for n in tf.getnames() if "/" in n}
    shipped = sorted(n for n in names if n.startswith("scripts/") and n.endswith(".py"))
    assert shipped, f"the sdist ships no scripts: {sd}"

    # RULE 1 — the subject rule.
    #
    # `scripts/docs/` is a DIRECTORY in the include list, so the check is
    # "some file under this prefix is shipped", not "this exact path is
    # shipped". A directory is a subject too: the suite opens files INSIDE it.
    def shipped_path(rel: str) -> bool:
        return rel in names or any(n.startswith(rel.rstrip("/") + "/") for n in names)

    tracked = git_tracked_paths()

    missing = []
    for rel in shipped:
        for target in suite_path_bindings(ROOT / rel):
            # only paths INSIDE the repo are subjects of the sdist. A suite may
            # bind a path outside it — `mutation_check.py` binds its scratch
            # worktree under $JCODE_SCRATCH_DIR — and that is not something the
            # sdist ships or must ship.
            try:
                r = target.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            # the repo ROOT itself is the tree, not a subject of it
            if r in (".", ""):
                continue
            # not tracked: build output or scratch, not source
            if r not in tracked and not any(t.startswith(r.rstrip("/") + "/") for t in tracked):
                continue
            if not shipped_path(r):
                missing.append((rel, r))
    assert not missing, (
        "the sdist ships a suite whose subjects it does not ship: "
        + "; ".join(f"{a} needs {b}" for a, b in missing)
    )

    # RULE 2 — the run rule.
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(sd) as tf:
            tf.extractall(td)
        roots = [p for p in Path(td).iterdir() if p.is_dir()]
        assert roots, "the sdist extracted to nothing"
        extracted = roots[0]

        # make it a checkout
        assert run(["git", "init", "-q", "."], cwd=str(extracted)).returncode == 0
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            run(["git", "config", k, v], cwd=str(extracted))
        assert run(["git", "add", "-A"], cwd=str(extracted)).returncode == 0
        assert run(["git", "commit", "-q", "-m", "sdist"], cwd=str(extracted)).returncode == 0

        # rebuild the CLI, then the artefacts. The ORDER matters: build.py
        # rewrites scripts/genome, and the packaging suites refuse to run
        # against a dist/ older than scripts/genome.
        b = run([sys.executable, "scripts/build.py"], cwd=str(extracted))
        assert b.returncode == 0, f"build.py fails in the sdist:\n{b.stdout[-400:]}{b.stderr[-400:]}"
        u = run(["uv", "build"], cwd=str(extracted))
        assert u.returncode == 0, f"uv build fails in the sdist:\n{u.stdout[-400:]}{u.stderr[-400:]}"

        for rel in shipped:
            env = dict(os.environ)
            env["GENOME_SDIST_CHECK"] = "1"
            r = run([sys.executable, rel], cwd=str(extracted), env=env)
            out = r.stdout + r.stderr
            if not runnable_in_an_sdist(rel, r, out):
                continue
            # the exit code is the verdict. A suite that prints a failure and
            # exits 0 is the defect class this whole session is about, so the
            # exit code is asserted, not the printed line.
            assert r.returncode == 0, (
                f"{rel} fails when run from the sdist it ships in (exit {r.returncode}):\n{out[-600:]}"
            )
            # and it must not have died on a missing subject
            assert "Traceback (most recent call last)" not in out, (
                f"{rel} crashes when run from the sdist it ships in:\n{out[-600:]}"
            )


def main():
    only = sys.argv[1:]
    selected = [c for c in CASES if not only or c.__name__ in only or c.__name__.startswith(tuple(only))]
    failed, ok = [], 0
    for c in selected:
        try:
            c()
            ok += 1
        except Exception:
            failed.append(c.__name__)
            print(f"FAIL {c.__name__}")
            traceback.print_exc()
    print(f"\ntest_package: {ok}/{len(selected)} cases ok" + (f" — FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    import traceback

    sys.exit(main())
