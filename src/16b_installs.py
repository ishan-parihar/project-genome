# ---------------------------------------------------------------- installation registry

# The fleet problem this module solves: `genome` is installed in several places
# per machine (skills roots, ~/.local/bin, sometimes /usr/local/bin, plus every
# repo that vendors scripts/genome), and an upgrade that touches only the
# known paths leaves the others silently stale — exactly what the machine this
# was first written on showed: two skills roots two commits behind origin and
# the PATH copy two VERSION stamps behind the skill, with nothing tracking it.
#
# The registry is one JSON manifest in the user's home, written by install.sh
# and by `genome installs register`, read by `genome installs list|verify`:
#   {"schema": 1, "installs": [{"kind": "skill|bin|vendored|kb", "path": "...",
#     "version": "...", "registered": "ISO8601", "note": "..."}]}
# `kind` drives the upgrade advice: skills roots are updatable by install.sh's
# update branch, bins are re-linked by it, vendored copies upgrade via
# `genome upgrade --apply` (or `git pull` where the repo tracks them).
# A vendored entry is informational — this CLI never writes outside the home
# manifest without a command that names the target.
#
# `kb` is the knowledge-base kind: a directory holding genome.toml (or the legacy
# kb.toml) that may or may not vendor a CLI copy. It exists because every activated
# genome is a KB whether or not it vendors the CLI, and the vendored rows alone left
# three live KBs off the registry (the meta-root, pioneer-qf, and a nested KB that
# defers to its parent). A kb row with no local CLI reads version 'none' — present
# and legitimate, nothing to compare — and is never reported as a broken install.

import json
import os
import re
import subprocess
from pathlib import Path

INSTALLS_SCHEMA = 1


def installs_manifest() -> Path:
    return Path(os.environ.get("GENOME_INSTALLS") or "~/.config/genome/installs.json").expanduser()


def load_installs() -> dict:
    p = installs_manifest()
    if not p.is_file():
        return {"schema": INSTALLS_SCHEMA, "installs": []}
    data = json.loads(p.read_text())
    if not isinstance(data, dict) or "installs" not in data:
        die(f"{p}: not an installs manifest (expected JSON with an 'installs' list)")
    data.setdefault("schema", INSTALLS_SCHEMA)
    return data


def save_installs(data: dict) -> None:
    p = installs_manifest()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(p)


def _version_key(v: str) -> tuple:
    """A VERSION stamp as a sortable key: YYYY.MM.DD-N tuples compare chronologically, so
    'the freshest registered copy' is a max(), not a string compare."""
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})-(\d+)$", v or "")
    return tuple(int(g) for g in m.groups()) if m else (0, 0, 0, 0)


def _verify_against_shipped(rows: list) -> None:
    """The check the registry clause actually needs: every registered install against the
    SHIPPED reference, not against its own registration record. The reference is the
    freshest live version among the skill/bin rows — the copies install.sh manages —
    RAISED to the running CLI's own VERSION, because those rows are only as current as
    the last publish while the repo under development is by definition newer. A row whose
    live version is older is BEHIND and listed with the delta; a row whose version is not
    comparable (a fork with a local stamp) is reported UNKNOWN rather than silently
    green. Exit 2 when anything is behind: 'all upgrades are seamless' has to start
    with knowing which copies are behind."""
    live = {r["path"]: _version_of(Path(r["path"])) for r in rows}
    refs = [live[r["path"]] for r in rows if r.get("kind") in ("skill", "bin") and _version_key(live[r["path"]]) > (0,) * 4]
    if not refs:
        die("no skill/bins copy registered to use as the shipped reference — run install.sh "
            "or `genome installs register skill <root>` first", ERR)
    ref = max(refs, key=_version_key)
    # Same correction the dispatch needed (2026-10-31, commit for `2026.10.30-25`): the
    # registered floor is a PUBLISH-TIME snapshot, so on a development day it is one
    # release behind the CLI actually running, and this check then calls every copy "at
    # the shipped version" for a shipped version that no longer exists. Measured: the
    # four skill roots are at `2026.10.30-22`, the running CLI at `-25`, and this command
    # printed "shipped is 2026.10.30-22" — so an operator reading it learned the wrong
    # target. The running CLI wins for the same reason it wins in `_dispatch_upgrade`: it
    # is the newest thing the operator can name, and the floor still prevents dragging a
    # repo backwards from an older checkout.
    me = _file_version(Path(__file__).read_text())
    if _version_key(me) > _version_key(ref):
        ref = me
    behind, unknown, tampered = [], [], []
    for r in rows:
        v = live[r["path"]]
        if v in ("missing", "none"):
            continue
        if _version_key(v) < _version_key(ref):
            behind.append((r, v))
        elif _version_key(v) == (0,) * 4:
            unknown.append((r, v))
        elif not _matches_ledger(Path(r["path"]), v):
            # A copy that claims a released version but does not carry that release's
            # bytes. This is the integrity question the install-time check exists for:
            # a hand-edit, a bad merge, a file restored from the wrong backup, or a
            # partial write all look like a valid release from the version line alone.
            # The fleet's whole premise is that a vendored copy is the released file,
            # so a copy that is not reported CORRUPTED is a copy the operator cannot
            # trust — and it would otherwise pass this check as clean.
            tampered.append((r, v))
    for r, v in behind:
        print(f"BEHIND  {r['kind']:8} {r['path']} — {v}, shipped is {ref}")
    for r, v in unknown:
        print(f"UNKNOWN {r['kind']:8} {r['path']} — version {v!r} does not compare (a local stamp?)")
    for r, v in tampered:
        print(f"CORRUPTED {r['kind']:6} {r['path']} — claims {v} but its bytes differ from the release "
              f"(a hand-edit, a partial write, or the wrong restore)")
    # The fourth question, added 2026-11-02 after the census measured 68 of 85 rows at
    # the shipped bytes on disk and older bytes at HEAD: a copy can be CURRENT and still
    # be one `git restore` from a regression. Behind/tampered are about what the bytes
    # ARE; this is about what git will let them STAY. It does not gate the exit code,
    # because a repo that intentionally gitignores its generated copy is healthy — this
    # prints the fact and lets the operator decide, which is the one judgement here that
    # 68 owners hold and this seat does not.
    uncommitted = []
    for r in rows:
        if r.get("kind") not in ("vendored", "bin"):
            continue    # a skills root is a checkout of the publisher, not a vendored copy
        p = Path(r["path"])
        found = _uncommitted_cli(p)
        if found:
            uncommitted.append((r, found))
    for r, (cli, st) in uncommitted:
        try:
            shown = cli.relative_to(Path(r["path"]))
        except ValueError:
            shown = cli
        print(f"UNCOMMITTED {r['kind']:6} {r['path']} — {shown} is modified in the working tree "
              f"({st}); git can discard it on the next restore/checkout")
    if uncommitted:
        print(f"note: {len(uncommitted)} row(s) hold the shipped bytes but have not committed them — "
              f"verify reads the disk, git holds the history, and only the owner knows which one is "
              f"authoritative")
    if not behind and not unknown and not tampered:
        print(f"verify: all {len(rows)} registered install(s) at the shipped version {ref}")
        return
    die(f"{len(behind)} behind, {len(unknown)} unknown, {len(tampered)} corrupted (shipped {ref})", ERR)


def _release_ledger() -> dict[str, str]:
    """VERSION -> sha256 from the release ledger, or {} when no ledger is on the machine.

    The ledger lives beside the SKILL copy (`scripts/releases.txt`), which is the
    published source of truth, not beside each vendored copy. Measured 2026-10-31: a
    vendored repo holds `scripts/genome` and no `releases.txt` at all — so a check that
    looked beside every copy would find nothing on the entire fleet and report the
    estate clean. That is the defect this whole function exists to catch, reproduced
    inside the fix: reading the ledger from the copy instead of from the publisher.

    The kernel checkout counts too, since on a development day its ledger is ahead of
    the last publish and the operator is iterating against it."""
    for c in (Path("~/.agents/skills/project-genome/scripts/releases.txt").expanduser(),
              Path("~/.claude/skills/project-genome/scripts/releases.txt").expanduser(),
              Path("~/.codex/skills/project-genome/scripts/releases.txt").expanduser(),
              Path("~/.zcode/skills/project-genome/scripts/releases.txt").expanduser(),
              Path(__file__).resolve().parent.parent / "scripts" / "releases.txt"):
        if c.is_file():
            out = {}
            for ln in c.read_text(errors="replace").splitlines():
                parts = ln.split()
                if len(parts) >= 2 and not ln.startswith("#"):
                    out[parts[0]] = parts[1]
            if out:
                return out
    return {}


def _matches_ledger(path: Path, version: str) -> bool:
    """True when a copy's bytes are the released bytes for its own VERSION.

    A copy whose sha matches the ledger is the release; one that does not is local, and
    the caller says so rather than trusting a version line a local edit left in place.
    This is the integrity question: without it, a hand-edit, a partial write, a bad
    merge, and a restore-from-the-wrong-backup are all indistinguishable from a genuine
    release, because each of them left the version line alone.

    Three states are deliberately NOT failures. A version with no ledger entry (an
    unreleased build the operator is iterating on, or a fork's own stamp), a path that is
    not a file (a register mistake, which `missing` already reports), and an unreadable
    file all return True: calling them corrupted would fail every machine
    mid-development. A False is reserved for bytes that provably differ from a release
    that IS recorded — the state where the operator has to look."""
    script = _script_of(path)
    if not script.is_file():
        return True
    ledger = _release_ledger()
    known = ledger.get(version, "")
    if not known:
        return True
    try:
        actual = hashlib.sha256(script.read_bytes()).hexdigest()
    except OSError:
        return True
    return actual.startswith(known)


def _script_of(path: Path) -> Path:
    """A registered path's genome script: the path itself when it is one (bin symlink or vendored
    scripts/genome), or the skills root's scripts/genome when the path is the root directory.

    A repo can vendor the CLI somewhere other than scripts/genome — pioneer-qf ships
    bin/genome — so both are probed. A path that has neither is a KB with no local CLI
    (the meta-root, a nested KB that defers to its parent): that is not 'missing', it is
    'no CLI here', and the caller must not report it as a broken install.

    A PACKAGE install is a third shape, and it was invisible here. `~/.local/bin/genome`
    is a console-script stub that uv/pip generates — a few lines of `import sys; from
    project_genome import main` — so it carries no VERSION line, and resolving the symlink
    lands on that stub instead of the CLI. Measured 2026-10-31: the registry reported the
    bin row as `?` while the real file beside it inside the uv environment was
    `2026.10.30-23`, one release ahead of every skills root on the machine. A registry
    that reads its own install as unknown cannot tell the operator what is behind, and
    that line was the only aggregate a fleet view could have been built on.

    The real CLI sits beside the stub inside the same environment:
    `<env>/lib/python*/site-packages/project_genome/_genome.py`. Probing it is what makes
    the registry, `installs list`, `installs verify` and every aggregate see an installed
    package as a versioned install rather than an unknown."""
    p = path
    if p.is_dir():
        for cand in (p / "scripts" / "genome", p / "bin" / "genome"):
            if cand.exists():
                return _package_cli(cand)
        return p / "scripts" / "genome"  # the canonical location, absent — reported as such
    return _package_cli(p)


def _package_cli(p: Path) -> Path:
    """A console-script stub's real CLI inside its environment, or the path unchanged.

    A real CLI carries a VERSION line in its head — a vendored `scripts/genome`, a skills
    root's copy, and the packaged `_genome.py` module itself all do — and is returned
    untouched. pioneer-qf's `bin/genome` is a vendored copy that carries VERSION, so this
    leaves it alone too.

    A bin with no VERSION line is read two ways, which is the whole of the honest answer:
    the path itself, and the path its symlink points at. Each is a `bin/` directory inside
    an environment, so each environment root is probed for
    `lib/python*/site-packages/*/_genome.py` — the uv-tool and plain-venv layouts
    respectively. When nothing is there the path is returned as given, so a genuinely
    unversioned path stays unversioned rather than being dressed up as an install."""
    try:
        if not p.is_file():
            return p
        if "VERSION" in p.read_text(errors="replace")[:512]:
            return p
    except OSError:
        return p
    bases = [p.parent]
    try:
        if p.resolve() != p:
            bases.append(p.resolve().parent)
    except OSError:
        pass
    for base in dict.fromkeys(bases):
        for cand in sorted((base.parent / "lib").glob("python*/site-packages/*/_genome.py")):
            if cand.is_file():
                return cand
    return p


def _is_kb(path: Path) -> bool:
    """A directory is an activated knowledge base when it holds genome.toml (or the
    legacy kb.toml). A KB may vendor no CLI at all — the meta-root and a nested KB
    that defers to its parent are both legitimate — so 'no local CLI' is a fact about
    the KB, not a broken install."""
    return (path / "genome.toml").is_file() or (path / "kb.toml").is_file()


def _version_of(path: Path) -> str:
    """A registered install's VERSION stamp, or 'missing'/'?' — the same regex `upgrade` trusts.

    A kb row with no local CLI reads 'none', not 'missing': the KB is present and
    working, it simply has no copy of the CLI to compare against. Reporting it as
    MISSING would put a healthy KB on the broken list."""
    p = _script_of(path)
    if not p.exists():
        return "none" if _is_kb(path) else "missing"
    if p.is_symlink():
        try:
            p = p.resolve()
        except OSError:
            return "?"
    if not p.is_file():
        return "none" if _is_kb(path) else "missing"
    m = re.search(r'^VERSION = "([^"]+)"', p.read_text(errors="replace"), re.M)
    return m.group(1) if m else "?"


def _git_sha(path: Path) -> str:
    """For skills roots: the checked-out commit, or '-' when the copy has no .git (rsync copies)."""
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "-"
    except (OSError, subprocess.TimeoutExpired):
        return "-"


def _uncommitted_cli(repo: Path) -> tuple[Path, str] | None:
    """(cli file, `git status` line) when a repo's vendored CLI is modified but not
    committed, else None.

    Why this exists: measured 2026-11-02, the fleet's `2026.10.31-40` dispatch landed
    correctly in **68 of 85** registered rows and none of them committed it — `M
    scripts/genome` in `git status`, disk at the shipped bytes, HEAD one release train
    behind. `installs verify --against-shipped` read the disk and reported all 68
    healthy, so the estate's own check could not see that every one of them is one
    `git restore` / `checkout .` / `clean -fd` away from a nine-release rollback.
    **A guard that checks a write landed, and nothing that checks it stayed landed, is
    a guard that certifies a regression-in-waiting as healthy.** This is that missing
    rung, and it is deliberately a *report*, not a fix: 68 owners decide whether their
    vendored copy is tracked (committed) or generated (gitignored), and neither answer
    is this seat's to give.

    A repo with no .git is not uncommitted, it is unversioned, and a CLI that is
    committed-and-clean is exactly the state we want to leave alone."""
    if not (repo / ".git").exists():
        return None
    cli = _repo_cli(repo)
    if not cli:
        return None
    # A vendored copy reached through a symlink lives somewhere else in the same repo:
    # holon/scripts/genome -> holon/vendor/genome.py. `git status` on the LINK path
    # reports the link, which is clean and unchanged, while the TARGET it points at is
    # the modified file (measured 2026-11-02: ` M holon/vendor/genome.py`). Ask git
    # about the resolved path, so a symlinked copy is not reported clean when the bytes
    # it resolves to are the ones one `git restore` away from disappearing.
    try:
        rel = cli.resolve().relative_to(repo.resolve())
    except (OSError, ValueError):
        try:
            rel = cli.relative_to(repo)
        except ValueError:
            return None
    try:
        r = subprocess.run(["git", "-C", str(repo), "status", "--short", "--", rel],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # An empty pathspec is a git error (exit 128), not an empty result: a copy git does
    # not know about at all reads exactly like a clean one if the failure is mistaken for
    # silence. Assert the call itself succeeded before believing what it does not say.
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    return (cli, out) if out else None


def _repo_cli(path: Path) -> Path | None:
    """The CLI a repo vendors, or None when it vendors none. bin/genome counts:
    pioneer-qf ships its copy there, and looking only in scripts/ made it invisible."""
    for cand in (path / "scripts" / "genome", path / "bin" / "genome"):
        if cand.is_file():
            return cand
    return None


def _dispatch_upgrade(rows: list, apply: bool, roots: list | None = None) -> None:
    """Dispatch an upgrade to every registered copy that is behind the shipped one.

    Each repo is upgraded by ITS OWN vendored CLI, run inside that repo — the
    vendored copy knows the repo's layout, and `upgrade` already refuses to swap a
    copy that carries a local patch (it keeps the diff and asks first), so a patched
    copy is never silently overwritten.

    A DRY RUN is the default: this writes into other people's repositories, and a
    fleet-wide rewrite is the operator's call. --apply performs it; every repo's
    result is reported, and one failure does not stop the rest.

    `--roots` scopes the dispatch. Measured 2026-10-30, the flag was parsed and then
    ignored — every byte of scope logic lived in `cmd_upgrade`, and the dispatcher
    ran the whole fleet regardless — so the sanctioned scoped test could not be
    performed at all. A scope that matches nothing now dies: an all-clear printed
    to a `--roots no-such-repo` request is the one output that must never appear,
    because the operator reading it concludes the fleet is current.

    THE REFERENCE IS MAX(RUNNING CLI, REGISTERED FLOOR). The registered floor came
    from the skills roots, which install.sh refreshes only at publish time: on a
    development day the roots sit one release behind the CLI actually running, and
    the dispatch reported that lagging copy as the target. `GENOME_SKILL` is handed
    to each vendored CLI, which already reads it, so a fleet dispatched from -23
    converges on -23 rather than stopping at the roots' -22 — the bootstrap
    failure proven in a sandbox, where a -23 dispatch delegated to each repo's own
    old CLI and the whole fleet pinned at -22."""
    skill_bin = [r for r in rows if r.get("kind") in ("skill", "bin")]
    if not skill_bin:
        die("no skill/bin copy registered to use as the shipped reference — "
            "run install.sh first", ERR)
    # The running CLI is the newest thing the operator can name, and it beats a
    # registered floor that a publish has not yet caught up with. A hand-edited
    # working tree still wins, which is intended: it is what the fleet is converging
    # toward, and operator hands are on the wheel.
    floor = max((_version_of(Path(r["path"])) for r in skill_bin), key=_version_key)
    me = _file_version(Path(__file__).read_text())
    ref = me if _version_key(me) >= _version_key(floor) else floor
    if roots:
        wanted = {r.strip().rstrip("/") for r in roots if r.strip()}
        before = len(rows)
        rows = [r for r in rows
                if str(Path(r["path"]).resolve().name) in wanted
                or r["path"].rstrip("/") in wanted
                or os.path.basename(r["path"].rstrip("/")) in wanted]
        if not rows:
            # 2026-10-30, `--roots no-such-repo` printed the all-clear line, which is the
            # one output that must never be produced by a scoped request that matched
            # nothing — an operator reading it would conclude the fleet is current.
            names = sorted({Path(r["path"]).resolve().name for r in load_installs()["installs"]})
            die("no registered install matches " + ", ".join(sorted(wanted))
                + f" ({before} registered; `genome installs list` names them)", ERR)
    targets = []
    for r in rows:
        if r.get("kind") not in ("vendored", "kb"):
            continue
        p = Path(r["path"])
        cli = _repo_cli(p)
        if cli is None:
            continue
        v = _version_of(p)
        if v and _version_key(v) < _version_key(ref):
            targets.append((r, cli, v))
    if not targets:
        print(f"dispatch: nothing to upgrade (every registered copy is at {ref})")
        return
    print(f"dispatch: {len(targets)} cop(y/ies) behind {ref}"
          + ("" if apply else " — DRY RUN (--apply performs the upgrade)"))
    # The swap source each repo's own CLI reads. `skill_copy()` probes the four
    # skills roots and picks the newest, so it resolves the release even when one
    # root lags — but a repo whose vendored CLI is OLDER than this dispatch still
    # hardcodes a single root inside ITSELF. Handing it the right source through the
    # env it already reads closes the bootstrap problem for every version at once,
    # which is the only way a fleet dispatched from -23 can reach -23.
    swap_source = skill_copy()
    env = dict(os.environ)
    if swap_source.is_file():
        env["GENOME_SKILL"] = str(swap_source)
        sv = _file_version(swap_source.read_text())
        if _version_key(sv) < _version_key(ref):
            # Say it out loud rather than letting a slow skills root pin the fleet:
            # the dispatch would report the target while every repo lands on the
            # source's version. The drill is to publish first (or point
            # GENOME_SKILL at the release), and this line names both.
            print(f"note: the swap source is {sv}, the dispatch target is {ref}")
            print(f"      each repo swaps in the source, so publish first, or "
                  f"GENOME_SKILL=<the {ref} copy> genome installs upgrade --apply")
        else:
            print(f"swap source: {swap_source} ({sv})")
    ok = skipped = failed = 0
    broken_out: list[tuple] = []  # (row, old_version, reason, child_output): upgraded, but left broken
    for r, cli, v in targets:
        cmd = [sys.executable, str(cli), "upgrade"] + (["--apply"] if apply else [])
        try:
            res = subprocess.run(cmd, cwd=str(Path(r["path"])), capture_output=True,
                                 text=True, timeout=300, env=env)
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"ERROR  {r['path']} — {e}")
            failed += 1
            continue
        out = (res.stdout + res.stderr).strip()
        # THE VERDICT IS THE CHILD'S, NOT THE DISPATCH'S. `upgrade` exit 0 means the
        # swap happened, and a swap that leaves the KB broken still returns 0 — the
        # post-upgrade finding list only ever goes to stdout. Measured 2026-10-31 on
        # the live estate: the fleet run reported `dispatch: 74 ok` while one repo had
        # been left with a stale records zone the new CLI correctly caught, and the
        # fleet's own summary said nothing was wrong. So the dispatcher reads the
        # verdict the child already printed and reclassifies: a child whose post-upgrade
        # list names errors is NOT ok, whatever its exit status.
        broken = _child_broken(out)
        # THE SWAP IS ALSO VERIFIED ON DISK. A child that printed `upgraded ... to
        # <ref>` and exited 0 has still only CLAIMED it moved: the file could be
        # unchanged (a permissions hiccup in atomic_write's rename), land on the wrong
        # bytes (a stale GENOME_SKILL), or be half-written. Re-reading the copy after
        # the child exits is the one check that cannot be fooled by a report. This is
        # the integrity gate the operator asked for, and it runs whether the child
        # succeeds or fails: a repo claiming a successful swap that did not happen is
        # the state that must never read as green.
        if apply and res.returncode == 0:
            landed = _version_of(Path(r["path"]))
            if landed != ref:
                broken = broken or f"the copy is {landed} on disk, not {ref}"
        if res.returncode == 0:
            if not broken:
                ok += 1
                print(f"{'upgraded' if apply else 'would upgrade':14} {r['path']}  {v} → {ref}")
            else:
                # The swap succeeded, so the file moved — the KB needs a fix, not a
                # retry, and the line must say so. Reporting `ok` here is the whole
                # defect: it is the line an operator scans, and a `dispatch: 74 ok`
                # summary over a fleet with a broken member reads as a green fleet.
                broken_out.append((r, v, broken, out))
                print(f"{'upgraded but BROKEN':22} {r['path']}  {v} → {ref}  ({broken})")
            # The new lint output is part of the result, not noise: a fleet run that
            # prints only the version line leaves every post-upgrade fix list unread.
            # The header is the line an operator scans for, so it is named explicitly
            # rather than left to a numbered-line heuristic that would miss it.
            # Skip the first line: it is the child's own `path: a -> b` header, which the
            # dispatch already prints on its own target line above. Printing it twice is
            # how the duplicate `genome.toml: schema_version ...` line appeared.
            for line in out.splitlines()[1:]:
                s = line.strip()
                if not s:
                    continue
                if (s.startswith("lint:") or s.startswith("genome.toml:")
                        or s.startswith("post-upgrade:") or s.startswith("remedies:")
                        or s.startswith("after fixing:")):
                    print(f"        {s}")
            # The numbered findings themselves: `  1. E017 genome.toml: ...` — strip the
            # leading spaces and the `N. ` prefix is the marker. Capped at 5 because
            # lint output is read by agents and every line costs.
            shown = 0
            for line in out.splitlines():
                s = line.strip()
                if re.match(r"^\d+\. ", s) and shown < 5:
                    print(f"        {s}")
                    shown += 1
        elif "local edits" in out or "patch" in out.lower():
            # the copy carries a local patch: `upgrade` refused, which is the right
            # answer — it is reported, never forced through with --accept-patch-loss
            skipped += 1
            print(f"skipped (local patch)  {r['path']}  {v}")
        else:
            failed += 1
            # A child that produced no output still owes a REASON, not an exit status:
            # a crash and a clean refusal both surface as bare 1 otherwise, and the
            # whole point of a per-repo line is that it is actionable.
            why = (out.splitlines()[0] if out else
                   "exit " + str(res.returncode) + " (no output — run it directly: " + " ".join(cmd) + ")")
            print(f"ERROR  {r['path']} — {why}")
    # A copy that upgraded but was left broken is its OWN category: it is not ok (the
    # KB needs a fix), not failed (the swap worked, a retry would not help), and not
    # skipped (nothing refused). Folding it into `ok` is what made a broken fleet report
    # itself green, so it is counted separately, printed with its fix list, and it fails
    # the run: a fleet that finished with a broken member has NOT finished.
    if broken_out:
        for r, v, why, out in broken_out:
            print(f"\nBROKEN {r['path']} — {why}")
            for line in out.splitlines():
                s = line.strip()
                if s.startswith("post-upgrade:") or s.startswith("remedies:") \
                        or s.startswith("after fixing:") or re.match(r"^\d+\. ", s):
                    print(f"        {s}")
        print(f"\ndispatch: {ok} ok, {len(broken_out)} upgraded but BROKEN, "
              f"{skipped} skipped (local patch), {failed} failed")
        die(f"{len(broken_out)} copy/copies upgraded but left broken — "
            f"`genome fleet lint` shows them, fix each then re-run", ERR)
    print(f"\ndispatch: {ok} ok, {skipped} skipped (local patch), {failed} failed")
    if failed:
        die(f"{failed} copy/copies failed to upgrade", ERR)


def _child_broken(out: str) -> str:
    """A child upgrade's own post-upgrade verdict, or '' when the child reported none.

    The child prints `post-upgrade: <N> error(s), <M> warning(s) to fix in this KB` after
    it swaps. Errors there are the new CLI saying this KB is now wrong, which is the one
    signal a dispatcher cannot see in the exit code: the swap succeeded and the operator
    still has work to do.

    Only ERRORS count. Warnings are advice about prose this release found, and an estate
    of 77 KBs carries 100 of them by design — treating them as breakage would fail every
    run for the normal state of the world, which is how a gate gets disabled.

    Returns the reason as a phrase for the line, so the dispatcher's report names what
    is wrong instead of just counting it."""
    for ln in out.splitlines():
        s = ln.strip()
        if not s.startswith("post-upgrade:"):
            continue
        m = re.search(r"(\d+)\s+error", s)
        if m and int(m.group(1)) > 0:
            return s.replace("post-upgrade:", "").strip()
    return ""


def cmd_installs(args) -> None:
    """installs: list | verify | register | scan — the machine's genome installs, one manifest."""
    if args.installs_cmd == "upgrade":
        _dispatch_upgrade(load_installs()["installs"], getattr(args, "apply", False),
                         getattr(args, "roots", None))
        return
    if args.installs_cmd == "list":
        data = load_installs()
        rows = data["installs"]
        if not rows:
            print(f"no installs registered — install.sh registers them, or `genome installs register <kind> <path>`")
            return
        for r in rows:
            print(f"{r['kind']:8} {r['path']}")
            print(f"         version {_version_of(Path(r['path']))} · registered {r.get('registered', '?')}"
                  + (f" · {r['note']}" if r.get("note") else ""))
        return
    if args.installs_cmd == "register":
        kind = args.kind
        raw = Path(args.path).expanduser()
        # Record the path AS GIVEN (not resolved): a bin entry is the symlink the
        # operator manages, and resolving it would point the registry inside a skills
        # root that install.sh updates separately. _version_of reads through the link.
        path = str(raw) if raw.is_absolute() else str(raw.resolve())
        if kind not in ("skill", "bin", "vendored", "kb"):
            die(f"kind must be skill | bin | vendored | kb (got {kind})", ERR)
        data = load_installs()
        rows = [r for r in data["installs"] if r["path"] != path]
        rows.append({"kind": kind, "path": path,
                     "version": _version_of(Path(path)), "registered": today_iso(),
                     "note": args.note or ""})
        data["installs"] = rows
        save_installs(data)
        print(f"registered: {kind} {path} (version {_version_of(Path(path))})")
        return
    if args.installs_cmd == "unregister":
        # The registry had no way to forget, so a path that no longer exists stayed
        # listed forever: measured 2026-10-30, `holon-personal` (and its nested
        # `holon-personal/holon`) were still registered as kb rows although the
        # directory is gone, and every upgrade dry run counted them as targets. A
        # registry that cannot forget reports a fleet size that is too high, which is
        # the same class of lie as an empty registry reporting green.
        cand = getattr(args, "kind", None)
        # The path is the FIRST positional, but `installs` shares its positionals
        # with `register` (kind, then path), so `unregister <path>` puts the path in
        # `kind` and leaves `path` None. Accept either: the four real kinds are
        # refused so a typo like `unregister kb` says so instead of hunting for a
        # repo called "kb".
        if not args.path and cand and cand not in ("skill", "bin", "vendored", "kb"):
            args.path, cand = cand, None
        if not args.path:
            die("unregister needs the path: `genome installs unregister <path>` "
                "(or `installs list` to see them)", ERR)
        raw = Path(args.path).expanduser()
        data = load_installs()
        rows = data["installs"]
        # Exact path first. A NAME match is offered only when it is unambiguous:
        # `holon` and `project-genome` each resolve to several rows (the four skill
        # roots), and a name match there would drop rows the operator never named.
        hit = [r for r in rows if r["path"] == str(raw)
               or r["path"] == str(raw.resolve())]
        if not hit:
            by_name = [r for r in rows if Path(r["path"]).name == raw.name]
            if len(by_name) > 1:
                die(f"'{raw.name}' matches {len(by_name)} registered installs — "
                    "pass one in full: " + ", ".join(r["path"] for r in by_name), ERR)
            hit = by_name
        if not hit:
            print(f"no registered install matches {raw} — nothing to unregister")
            return
        gone = [r["path"] for r in hit]
        data["installs"] = [r for r in rows if r not in hit]
        save_installs(data)
        for p in gone:
            print(f"unregistered: {p}")
        print(f"{len(gone)} row(s) removed")
        return
    if args.installs_cmd == "verify":
        data = load_installs()
        rows = data["installs"]
        # An EMPTY registry is not a pass: on a fresh machine nothing has proven
        # itself yet, and a green line here is exactly the silent failure this
        # registry exists to catch. Say nothing-tested and exit 2, so a new
        # agent or a post-install gate cannot read "0 installs" as healthy.
        if not rows:
            die("no installs registered — this machine has proven nothing: run install.sh "
                "(it registers everything it creates), or `genome installs scan`", ERR)
        if getattr(args, "against_shipped", False):
            _verify_against_shipped(rows)
            return
        stale, broken = [], []
        for r in rows:
            p = Path(r["path"])
            v = _version_of(p)
            if v == "missing":
                broken.append((r, v))
            elif v == "none":
                # a KB with no local CLI: present and legitimate, nothing to compare
                continue
            elif r.get("version") and r["version"] != "?" and v != r["version"]:
                stale.append((r, v))
        for r, v in broken:
            print(f"MISSING {r['kind']} {r['path']} (was version {r.get('version', '?')})")
        for r, v in stale:
            print(f"STALE   {r['kind']} {r['path']} — manifest says {r['version']}, on disk {v}")
        if not broken and not stale:
            print(f"verify: all {len(rows)} registered install(s) present, versions unchanged")
            return
        die(f"{len(broken)} missing, {len(stale)} changed since registration", ERR)
    if args.installs_cmd == "scan":
        # Find installs the manifest does not know about. Skills roots come from the
        # harness conventions install.sh probes; bins from PATH; vendored copies by
        # walking parents is out of scope — a machine's repos are too many to sweep.
        known = {r["path"] for r in load_installs()["installs"]}
        # every registered path's resolution too: a bin LINK and the script it points at
        # are the same install recorded two ways
        resolved_known = {k for r in load_installs()["installs"]
                          for k in (r["path"], str(_script_of(Path(r["path"])).resolve()))}
        found = []
        # An ACTIVATED GENOME sweep: a directory holding genome.toml (or the legacy
        # kb.toml) is a knowledge base, whether or not it vendors a CLI copy. Walking
        # a root for those is how a repo that has no scripts/genome — a meta-root, a
        # nested KB that defers to its parent — still reaches the registry, and it is
        # the sweep that finds KBs nobody registered by hand.
        for root in (getattr(args, "roots", None) or []):
            rp = Path(root).expanduser().resolve()
            if not rp.is_dir():
                die(f"scan root is not a directory: {rp}", ERR)
            for cand in sorted(rp.rglob("genome.toml")) + sorted(rp.rglob("kb.toml")):
                d = cand.parent
                if not any(x in d.parts for x in (".git", "node_modules", "target", ".venv", "venv", "__pycache__")):
                    if str(d) not in known:
                        found.append(("kb", str(d)))
        for root in ("~/.agents/skills/project-genome", "~/.claude/skills/project-genome",
                     "~/.operant/skills/project-genome", "~/.local/share/agents/skills/project-genome",
                     "~/Library/Application Support/agents/skills/project-genome"):
            p = Path(root).expanduser()
            if p.is_dir() and str(p.resolve()) not in known:
                found.append(("skill", str(p.resolve())))
        for d in os.environ.get("PATH", "").split(os.pathsep):
            b = Path(d).expanduser() / "genome"
            # Three ways this bin can be accounted for, any one of which silences scan:
            # (1) its own path was registered (a bin entry records the link as given);
            # (2) its RESOLUTION is a registered path or a registered root's script
            #     (a link into an already-tracked skills root is the same install);
            # (3) nothing above — then it is a real unregistered install.
            try:
                bres = str(b.resolve())
            except OSError:
                bres = ""
            if b.exists() and str(b) not in resolved_known and bres not in resolved_known:
                found.append(("bin", str(b)))
        if not found:
            print("scan: no unregistered installs found")
            return
        for kind, p in found:
            print(f"unregistered {kind} {p} — `genome installs register {kind} {p}`")
        die(f"{len(found)} unregistered install(s) — register them so upgrades reach them", ERR)


def today_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M")
