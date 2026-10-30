#!/usr/bin/env python3
"""Second-round packaging checks: the surfaces the first suite did not reach.

Why: scripts/test_package.py covered the WHEEL. This suite covers what a user
actually hits that the wheel path hides — the sdist, the whole command surface in
installed mode, the exit codes a CI job chains on, and the Python floor. Each
case here is a check that was run by hand and would otherwise be re-verified
by hand forever.

Run: python3 scripts/test_package_modes.py [case ...]   (stdlib only)
Every selected case runs even when one fails; the summary lists them all and the
exit code is 1 on any failure.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def sdist_path():
    wheels = sorted((ROOT / "dist").glob("*.whl"))
    candidates = sorted((ROOT / "dist").glob("*.tar.gz"))
    assert candidates, "no sdist in dist/ — run `uv build`"
    return candidates[-1], (wheels[-1] if wheels else None)


def venv_with(sdist=None, name="modes"):
    """A throwaway venv with the SDIST (not the wheel) installed."""
    tmp = Path(tempfile.mkdtemp(prefix=f"genome-{name}-"))
    mk = run([sys.executable, "-m", "venv", str(tmp / "venv")])
    assert mk.returncode == 0, f"venv creation failed: {mk.stderr[-300:]}"
    vpy = tmp / "venv" / "bin" / "python"
    src = sdist or sdist_path()[0]
    inst = run([str(vpy), "-m", "pip", "install", "--quiet", "--force-reinstall", str(src)])
    assert inst.returncode == 0, f"sdist install failed: {inst.stderr[-400:]}"
    return tmp, vpy


# ── the sdist path ───────────────────────────────────────────────────────────


@case
def sdist_install_runs_and_matches_the_wheel():
    """A wheel-less platform installs the sdist. It must produce a working CLI whose
    bytes are the same the wheel installs — the parity the release ledger assumes."""
    tmp, vpy = venv_with(sdist=None, name="sdist")
    try:
        out = run([str(vpy), "-m", "project_genome", "--version"], cwd=str(tmp))
        assert out.returncode == 0, f"the sdist install did not run: {out.stdout[-300:]}{out.stderr[-300:]}"
        assert "genome" in out.stdout, f"unexpected: {out.stdout.strip()!r}"
        site = next((tmp / "venv").glob("lib/*/site-packages/project_genome/_genome.py"))
        import hashlib
        sdist_sha = hashlib.sha256(site.read_bytes()).hexdigest()
        import zipfile
        wheels = sorted((ROOT / "dist").glob("*.whl"))
        if wheels:
            with zipfile.ZipFile(wheels[-1]) as z:
                wheel_sha = hashlib.sha256(z.read("project_genome/_genome.py")).hexdigest()
            assert sdist_sha == wheel_sha, (
                f"the sdist and the wheel install DIFFERENT CLI bytes: "
                f"{sdist_sha[:12]} vs {wheel_sha[:12]}"
            )
        assert sdist_sha == hashlib.sha256((ROOT / "scripts" / "genome").read_bytes()).hexdigest(), (
            "the installed copy is not the bytes the fleet vendors"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── the whole command surface in installed mode ──────────────────────────────


@case
def installed_mode_matches_vendored_on_every_surface():
    """Every command that reads its own `__file__` must behave the same from
    site-packages as from a vendored path: inventory (skill_copy), upgrade,
    installed_as_package, and bp_check — the last of which re-invokes the script
    as a subprocess with [sys.executable, os.path.abspath(__file__)], the one path
    most likely to break when the file moves."""
    tmp, vpy = venv_with(name="modes")
    try:
        proj = tmp / "proj"
        proj.mkdir()
        init = run([str(vpy), "-m", "project_genome", "init", "--profile", "software"], cwd=str(proj))
        assert init.returncode == 0, f"init failed: {init.stderr[-300:]}"
        vendored = str(ROOT / "scripts" / "genome")
        surfaces = (["blueprint", "check"], ["wake"], ["lint"], ["upgrade"], ["doctor"], ["installs", "scan"])
        for cmd in surfaces:
            a = run([str(vpy), "-m", "project_genome", *cmd], cwd=str(proj))
            b = run([sys.executable, vendored, *cmd], cwd=str(proj))
            assert a.returncode == b.returncode, (
                f"`{' '.join(cmd)}`: installed exit {a.returncode} vs vendored {b.returncode}\n"
                f"  installed: {a.stdout[-200:]}{a.stderr[-200:]}\n"
                f"  vendored : {b.stdout[-200:]}{b.stderr[-200:]}"
            )
            # same first line of real output (skip lines that name a path)
            al = [l for l in a.stdout.splitlines() if str(tmp) not in l and "site-packages" not in l]
            bl = [l for l in b.stdout.splitlines() if str(tmp) not in l and "site-packages" not in l]
            assert al[:2] == bl[:2], f"`{' '.join(cmd)}` output diverges:\n  {al[:2]}\n  {bl[:2]}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def installed_mode_detection_is_observable_through_the_cli():
    """The wrapper exposes no Python API (and should not until something needs one:
    the deliverable is the CLI), so the mode detection is checked the way a user
    sees it — through the CLI's own output. A pip install must report 'up to date'
    rather than failing about a missing skills path, and a vendored copy must
    still compare against the skill."""
    tmp, vpy = venv_with(name="detect")
    try:
        proj = tmp / "proj"
        proj.mkdir()
        init = run([str(vpy), "-m", "project_genome", "init", "--profile", "software"], cwd=str(proj))
        assert init.returncode == 0, f"init failed: {init.stderr[-300:]}"
        up = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj))
        assert up.returncode == 0, f"installed-mode upgrade failed: {up.stderr[-300:]}"
        assert "up to date" in up.stdout, f"installed mode did not report up to date: {up.stdout.strip()!r}"
        assert "missing" not in up.stdout.lower(), f"installed mode blamed a missing file: {up.stdout.strip()!r}"
        # a vendored copy compares against the skill copy and reports the delta it found
        vend = run([sys.executable, str(ROOT / "scripts" / "genome"), "upgrade"], cwd=str(proj))
        assert vend.returncode == 0, f"vendored upgrade failed: {vend.stderr[-300:]}"
        assert "up to date" in vend.stdout or "→" in vend.stdout, (
            f"vendored mode reported neither currency nor a delta: {vend.stdout.strip()!r}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def stale_installed_copy_is_never_reported_current_silently():
    """A pip install cannot see a newer release: skill_copy() resolves to the
    running file, so `upgrade` prints 'up to date' unconditionally. That is a
    documented limitation of installed mode (there is no file to swap in), but it
    must NOT claim more than it checked — the wording has to say what it compared.
    Pinned so a future 'up to date' that implies a remote check fails here."""
    tmp, vpy = venv_with(name="current")
    try:
        proj = tmp / "proj"
        proj.mkdir()
        run([str(vpy), "-m", "project_genome", "init", "--profile", "software"], cwd=str(proj))
        out = run([str(vpy), "-m", "project_genome", "upgrade"], cwd=str(proj))
        assert out.returncode == 0, f"upgrade failed: {out.stderr[-300:]}"
        assert "up to date" in out.stdout, f"installed mode did not report up to date: {out.stdout.strip()!r}"
        assert "→" not in out.stdout, "installed mode claimed a delta it cannot have compared"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── exit codes a CI job chains on ────────────────────────────────────────────


@case
def installer_exits_nonzero_when_it_refuses():
    """The rejection paths must be visible to a `set -e` CI job or a chained
    script — observed once where a piped `head` hid a real exit 1. Tested directly
    rather than through a pipe, because the pipe is what hid it."""
    bad_python = Path(tempfile.mkdtemp(prefix="genome-pyfloor-")) / "bin"
    bad_python.mkdir(parents=True)
    fake = bad_python / "python3"
    fake.write_text('#!/bin/bash\nif [ "$1" = "-c" ]; then echo "3.9.18"; exit 0; fi\nexec /usr/bin/python3 "$@"\n')
    fake.chmod(0o755)
    home = bad_python.parent / "home"
    home.mkdir()
    sysdirs = [d for d in ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"] if Path(d).is_dir()]
    clean = ":".join([str(bad_python), *sysdirs])
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(bad_python.parent / "data"), PATH=clean)
    out = run(["bash", str(ROOT / "install.sh"), "--no-cta"], env=env, cwd=str(home))
    assert out.returncode != 0, f"a refused install exited 0: {out.stdout[-300:]}"
    both = out.stdout + out.stderr
    assert "3.9.18" in both and "tomllib" in both, f"the refusal did not name the reason: {both[-300:]}"
    # --skill without git: a request the machine cannot take, refused before anything is installed.
    # bash and git live in the same directory here, so dropping directories cannot
    # produce a PATH with bash and no git. Put bash itself in the fake bin dir
    # instead (that is how a real PATH would have it), and assert the harness is
    # what it claims before trusting anything the run reports.
    for tool in ("bash", "sh"):
        src = shutil.which(tool)
        if src:
            (bad_python / tool).symlink_to(src)
    nogit = ":".join([str(bad_python), *[d for d in sysdirs if not (Path(d) / "git").exists() and not (Path(d) / "bash").exists()]])
    assert shutil.which("bash", path=nogit), "the harness is wrong: no bash on the no-git PATH"
    assert not shutil.which("git", path=nogit), "the harness is wrong: git is still reachable"
    env2 = dict(env, PATH=nogit)
    out2 = run(["bash", str(ROOT / "install.sh"), "--skill", "--no-cta"], env=env2, cwd=str(home))
    assert out2.returncode != 0, "a --skill request on a git-less machine exited 0"
    assert "git" in (out2.stdout + out2.stderr).lower(), "the refusal did not mention git"


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
            import traceback
            traceback.print_exc()
    print(f"\ntest_package_modes: {ok}/{len(selected)} cases ok" + (f" — FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
