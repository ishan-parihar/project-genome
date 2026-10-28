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
#   {"schema": 1, "installs": [{"kind": "skill|bin|vendored", "path": "...",
#     "version": "...", "registered": "ISO8601", "note": "..."}]}
# `kind` drives the upgrade advice: skills roots are updatable by install.sh's
# update branch, bins are re-linked by it, vendored copies upgrade via
# `genome upgrade --apply` (or `git pull` where the repo tracks them).
# A vendored entry is informational — this CLI never writes outside the home
# manifest without a command that names the target.

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
    freshest live version among the skill/bin rows — those are the copies install.sh
    manages, so by construction they are (or were just made) current. A row whose live
    version is older is BEHIND and listed with the delta; a row whose version is not
    comparable (a fork with a local stamp) is reported UNKNOWN rather than silently
    green. Exit 2 when anything is behind: 'all upgrades are seamless' has to start
    with knowing which copies are behind."""
    live = {r["path"]: _version_of(Path(r["path"])) for r in rows}
    refs = [live[r["path"]] for r in rows if r.get("kind") in ("skill", "bin") and _version_key(live[r["path"]]) > (0,) * 4]
    if not refs:
        die("no skill/bins copy registered to use as the shipped reference — run install.sh "
            "or `genome installs register skill <root>` first", ERR)
    ref = max(refs, key=_version_key)
    behind, unknown = [], []
    for r in rows:
        v = live[r["path"]]
        if v == "missing":
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
    scripts/genome), or the skills root's scripts/genome when the path is the root directory."""
    p = path
    if p.is_dir():
        p = p / "scripts" / "genome"
    return p


def _version_of(path: Path) -> str:
    """A registered install's VERSION stamp, or 'missing'/'?' — the same regex `upgrade` trusts."""
    p = _script_of(path)
    if not p.exists():
        return "missing"
    if p.is_symlink():
        try:
            p = p.resolve()
        except OSError:
            return "?"
    if not p.is_file():
        return "missing"
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


def cmd_installs(args) -> None:
    """installs: list | verify | register | scan — the machine's genome installs, one manifest."""
    if getattr(args, "installs_cmd", "list") == "list":
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
        if kind not in ("skill", "bin", "vendored"):
            die(f"kind must be skill | bin | vendored (got {kind})", ERR)
        data = load_installs()
        rows = [r for r in data["installs"] if r["path"] != path]
        rows.append({"kind": kind, "path": path,
                     "version": _version_of(Path(path)), "registered": today_iso(),
                     "note": args.note or ""})
        data["installs"] = rows
        save_installs(data)
        print(f"registered: {kind} {path} (version {_version_of(Path(path))})")
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
