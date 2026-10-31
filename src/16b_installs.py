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
    behind, unknown = [], []
    for r in rows:
        v = live[r["path"]]
        if v in ("missing", "none"):
            continue
        if _version_key(v) < _version_key(ref):
            behind.append((r, v))
        elif _version_key(v) == (0,) * 4:
            unknown.append((r, v))
    for r, v in behind:
        print(f"BEHIND  {r['kind']:8} {r['path']} — {v}, shipped is {ref}")
    for r, v in unknown:
        print(f"UNKNOWN {r['kind']:8} {r['path']} — version {v!r} does not compare (a local stamp?)")
    if not behind and not unknown:
        print(f"verify: all {len(rows)} registered install(s) at the shipped version {ref}")
        return
    die(f"{len(behind)} behind, {len(unknown)} unknown (shipped {ref})", ERR)


def _script_of(path: Path) -> Path:
    """A registered path's genome script: the path itself when it is one (bin symlink or vendored
    scripts/genome), or the skills root's scripts/genome when the path is the root directory.

    A repo can vendor the CLI somewhere other than scripts/genome — pioneer-qf ships
    bin/genome — so both are probed. A path that has neither is a KB with no local CLI
    (the meta-root, a nested KB that defers to its parent): that is not 'missing', it is
    'no CLI here', and the caller must not report it as a broken install."""
    p = path
    if p.is_dir():
        for cand in (p / "scripts" / "genome", p / "bin" / "genome"):
            if cand.exists():
                return cand
        return p / "scripts" / "genome"  # the canonical location, absent — reported as such
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
        if res.returncode == 0:
            ok += 1
            print(f"{'upgraded' if apply else 'would upgrade':14} {r['path']}  {v} → {ref}")
            # The new lint output is part of the result, not noise: a fleet run that
            # prints only the version line leaves every post-upgrade fix list unread.
            for line in out.splitlines()[:1]:
                print(f"        {line}")
            for line in out.splitlines():
                s = line.strip()
                if s.startswith("lint:") or s.startswith("genome.toml:"):
                    print(f"        {s}")
            shown = 0
            for line in out.splitlines():
                s = line.strip()
                if s[:1].isdigit() and ". [" in s[:8] and shown < 5:
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
    print(f"\ndispatch: {ok} ok, {skipped} skipped (local patch), {failed} failed")
    if failed:
        die(f"{failed} copy/copies failed to upgrade", ERR)


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
