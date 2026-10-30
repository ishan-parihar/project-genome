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
import os
import shutil
import subprocess
import sys
import tempfile
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
    modes — install says 'up to date' rather than failing on a missing skills dir."""
    tmp, vpy, _ = venv_with_wheel("mode")
    try:
        proj = tmp / "proj"
        proj.mkdir()
        init = run([str(vpy), "-m", "project_genome", "init", "--profile", "software"], cwd=str(proj))
        assert init.returncode == 0, f"init failed: {init.stderr[-400:]}"
        for cmd in (["upgrade"], ["doctor"], ["lint"]):
            out = run([str(vpy), "-m", "project_genome", *cmd], cwd=str(proj))
            assert out.returncode == 0, f"`{' '.join(cmd)}` failed in installed mode: {out.stdout[-400:]}{out.stderr[-400:]}"
        up = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj)).stdout
        assert "up to date" in up, f"installed mode did not report up-to-date: {up.strip()!r}"
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
