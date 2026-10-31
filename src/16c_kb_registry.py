# ---------------------------------------------------------------- the KB registry view

# The install registry (16b) tracks WHERE the CLI is installed, so an upgrade reaches
# every copy. This module adds the other half: WHERE THE KNOWLEDGE BASES ARE, so a
# genome in any working directory can reach any KB on the machine.
#
# Two questions drove it:
#   1. "which KBs exist?" — the install registry only knew the repos that VENDOR the
#      CLI, and every activated genome is a KB whether or not it vendors a copy. A KB
#      with no local CLI (the meta-root, a nested KB that defers to its parent) was
#      invisible, and so was a repo that vendors at bin/genome instead of scripts/genome.
#   2. "can I reach them?" — genome resolves its config by walking UP from the cwd, so
#      from an unrelated directory there is no genome to run against another repo's KB.
#      A registry of KB paths turns "the KB you want" into an addressable target.
#
# The registry manifest is the single source of truth: `genome installs register kb
# <path>` writes a row, `genome kb list` reads them, `genome kb lint` walks them.
# Nothing here writes into a peer repo — it reads their configs and their lint.

import json
import os
import subprocess
import sys
from pathlib import Path


def kb_rows() -> list[dict]:
    """Every registry row that names an activated knowledge base.

    A row is a KB when its directory holds genome.toml or the legacy kb.toml. The 78
    vendored CLI copies are ALSO knowledge bases (each carries a .genome/ state dir),
    so they are included here — that is what makes 'lint every KB' reach the whole
    estate rather than only the repos that happen to lack a local CLI."""
    data = load_installs()
    out = []
    for r in data["installs"]:
        p = Path(r["path"])
        if not p.is_dir():
            continue
        if (p / "genome.toml").is_file() or (p / "kb.toml").is_file():
            out.append(r)
    return out


def _current_release() -> str:
    """The release a KB is measured against: max(running CLI, registered floor).

    The same rule `_dispatch_upgrade` uses, re-derived rather than imported so this
    module does not reach into the dispatcher's scope. It is the answer to "behind
    what?", and answering it with any single root would reintroduce the defect the
    dispatch already fixed: one lagging root pinning the whole fleet's definition of
    current. A registry with no skill/bin row falls back to the running CLI."""
    skill_bin = [r for r in load_installs()["installs"] if r.get("kind") in ("skill", "bin")]
    floor = max((_version_of(Path(r["path"])) for r in skill_bin), key=_version_key, default="-")
    me = _file_version(Path(__file__).read_text())
    return me if not floor or _version_key(me) >= _version_key(floor) else floor


def _kb_label(path: Path, root: Path | None = None) -> str:
    """A KB's short name, disambiguated when two KBs share a basename.

    Two 'holon' KBs exist on this machine (holon/ and holon-personal/holon/), and a
    name that silently picks one is the kind of ambiguity that makes an agent act on
    the wrong KB. A collision gets the path relative to the COMMON ROOT of the
    colliding KBs — relative to the parent of one of them, the nested KB would still
    read as plain 'holon'."""
    name = path.name
    same = [Path(r["path"]) for r in kb_rows() if Path(r["path"]).name == name]
    if len(same) <= 1:
        return name
    # the deepest common ancestor of the colliding KBs: the root both share
    common = Path(os.path.commonpath([str(p) for p in same]))
    try:
        return str(path.relative_to(common))
    except ValueError:
        return str(path)


def resolve_kb(target: str) -> Path:
    """Find the KB an operator means by name or path, from ANY working directory.

    A path that exists wins (it is unambiguous). Otherwise the name is matched against
    every registered KB: an exact path match, a path suffix match, then a basename
    match. An ambiguous basename is an error naming the candidates, never a guess."""
    t = Path(target).expanduser()
    if t.is_absolute() and t.is_dir():
        return t.resolve()
    rows = kb_rows()
    if not rows:
        die("no knowledge bases registered — `genome installs register kb <path>` "
            "for each activated genome (the dirs holding genome.toml / kb.toml)", ERR)
    # an exact path, as given or as a suffix of a registered path
    exact = [r for r in rows if str(r["path"]) == str(t)]
    if exact:
        return Path(exact[0]["path"]).resolve()
    suff = [r for r in rows if str(r["path"]).endswith(str(t))]
    if len(suff) == 1:
        return Path(suff[0]["path"]).resolve()
    if len(suff) > 1:
        die(f"'{target}' matches several knowledge bases: " +
            ", ".join(sorted(r["path"] for r in suff)) + " — name one by full path", ERR)
    base = [r for r in rows if Path(r["path"]).name == t.name]
    if len(base) == 1:
        return Path(base[0]["path"]).resolve()
    if len(base) > 1:
        die(f"'{target}' matches several knowledge bases: " +
            ", ".join(sorted(r["path"] for r in base)) + " — name one by full path", ERR)
    die(f"no knowledge base named '{target}' ({len(rows)} registered — `genome kb list`)", ERR)


def kb_lint_one(path: Path) -> tuple[int, int, list[str]]:
    """Lint one KB by running ITS OWN vendored CLI, so the check is the KB's own rules.

    A KB that vendors no CLI cannot lint itself; that is reported as 'no CLI here'
    rather than silently counted as clean — the same rule the empty-registry fix
    follows: an unproven thing is not a green thing.

    Every finding is returned, not the first three. Measured 2026-10-31, the estate
    carries 100 warnings across 79 KBs and the cap turned that into 11 rows of bare
    counts with no code and no remedy — the aggregation that hides both the finding
    and its fix, which is the same defect the per-repo post-upgrade list was built to
    stop. The caller counts; the codes are the point."""
    script = _script_of(path)
    if not script.is_file():
        return (0, 0, ["no CLI in this KB — nothing to lint with"])
    try:
        r = subprocess.run([sys.executable, str(script), "lint", "--json"],
                           cwd=str(path), capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as e:
        return (0, 0, [f"lint failed to run: {e}"])
    out = r.stdout.strip()
    if not out:
        return (0, 0, [(r.stderr.strip().splitlines() or ["lint produced no output"])[-1]])
    try:
        j = json.loads(out)
    except ValueError:
        return (0, 0, [f"lint output was not JSON: {out[:120]}"])
    errs = int(j.get("errors", 0))
    warns = int(j.get("warnings", 0))
    findings = [f"{f.get('code','?')} {f.get('text','')}" for f in j.get("findings", [])]
    return (errs, warns, findings)


def _remedies_for(codes) -> str:
    """The commands that clear each finding CODE, as one line.

    The remedy is the point of a findings list: `E117` and `genome emit` are the same
    sentence to a reader who already knows them, and an unknowing one has to go and
    find out. This table is shared with `_post_upgrade_findings`, so a single KB's
    post-upgrade list and the estate's aggregate name the same fix for the same code
    instead of drifting into two vocabularies.

    The W codes are here because they are what the estate actually carries. Measured
    2026-10-31 across 77 KBs: 0 errors and 100 warnings in nine codes, every one of
    them a W. A table that knew only the E codes therefore printed no remedies at all
    on the first real fleet run, which is the same defect as printing no findings —
    the answer withheld by the gap in the table rather than by a cap in the caller.
    Each entry is the remedy the code's own lint text already names."""
    seen = {c for c in codes if c and c[0] in "EW"}
    fixes = []
    if "E117" in seen:
        fixes.append("`genome emit` (worklog zone is stale)")
    if "E006" in seen:
        fixes.append("`genome emit` (a generated zone was hand-edited or has broken markers)")
    if "E104" in seen:
        fixes.append("`genome outline` (outline zone is stale)")
    if "E016" in seen:
        fixes.append("move history out of the over-budget file (`genome archive`)")
    if "W006" in seen:
        fixes.append("two plans answer one question — keep one owner, retire the other")
    if "W008" in seen:
        fixes.append("delete the duplicated prose: the README links a page, it does not paraphrase it")
    if "W009" in seen:
        fixes.append("link the unreachable docs page from its README or a sibling page")
    if "W010" in seen:
        fixes.append("add a table of contents to the long file (or split it)")
    if "W011" in seen:
        fixes.append("`genome archive <plan> --section ...` for the superseded section")
    if "W014" in seen:
        fixes.append("re-ask the operator on the aged ask, or withdraw it")
    if "W105" in seen:
        fixes.append("point the citation at a live record, or retire the doc's claim")
    if "W201" in seen:
        fixes.append("class the figure in that section (measured | stated | estimated)")
    if "W401" in seen:
        fixes.append("`genome emit` refreshes the manual's covered code, or re-verify it")
    if any(c.startswith("E") for c in seen):
        fixes.append("`genome lint --code E --all` lists every error; `genome doctor` explains each code")
    return "; ".join(fixes)


def cmd_kb(args) -> None:
    """kb: list | lint | show — the machine's knowledge bases, reachable from anywhere."""
    cmd = getattr(args, "kb_cmd", "list")
    if cmd == "list":
        rows = kb_rows()
        if not rows:
            print("no knowledge bases registered — `genome installs register kb <path>`")
            return
        # THE VERSION IS THE POINT OF THIS LIST. A list of 79 names and paths answers
        # "where are they" and cannot answer "which are behind", which is the question
        # that starts every upgrade — measured 2026-10-31, that is exactly what it did,
        # so the staleness had to be assembled by hand from another command. `-` is a
        # KB with no local CLI: present and legitimate, nothing to compare against,
        # and never printed as a broken install.
        behind = 0
        for r in sorted(rows, key=lambda r: r["path"]):
            p = Path(r["path"])
            v = _version_of(p)
            if v not in ("none", "missing"):
                ref = _current_release()
                if _version_key(v) < _version_key(ref):
                    print(f"{_kb_label(p):34} {r['path']:56} {v:14} behind {ref}")
                    behind += 1
                    continue
            print(f"{_kb_label(p):34} {r['path']:56} {v:14} [{r.get('kind','?')}]")
        print(f"\n{len(rows)} knowledge base(s) registered, {behind} behind the current release")
        return
    if cmd == "show":
        p = resolve_kb(args.target)
        cfg = find_cfg(p)
        print(f"root: {cfg.root}")
        print(f"modules: {', '.join(sorted(cfg.modules))}")
        print(f"legacy kb.toml: {cfg.legacy}")
        for role in sorted(cfg.paths):
            print(f"  {role:10} {cfg.paths[role]}")
        return
    if cmd == "lint":
        # --all: every registered KB. Without it: the named one (or the cwd's).
        targets = []
        if getattr(args, "all", False):
            targets = [Path(r["path"]) for r in sorted(kb_rows(), key=lambda r: r["path"])]
            if not targets:
                die("no knowledge bases registered — nothing to lint", ERR)
        elif getattr(args, "target", None):
            targets = [resolve_kb(args.target)]
        else:
            targets = [find_cfg().root]
        total_e = total_w = 0
        failures = []
        no_cli = []
        codes: dict[str, list[str]] = {}  # code -> the KBs carrying it, for the remedy summary
        for t in targets:
            errs, warns, findings = kb_lint_one(t)
            total_e += errs
            total_w += warns
            label = _kb_label(t)
            if findings and findings[0].startswith("no CLI"):
                # a KB with no local CLI is UNLINTED, not clean: saying 'ok' here
                # would read as a passing check that never ran
                no_cli.append(label)
                print(f"skip  {label:34} no CLI in this KB — nothing to lint with")
                continue
            status = "ok" if not errs and not findings else ("FAIL" if errs else "warn")
            print(f"{status:5} {label:34} {errs} error(s), {warns} warning(s)")
            # EVERY finding, not the first three. Measured 2026-10-31, the cap hid the
            # 4th and later ones and the codes with them, so a per-KB line was a count
            # with no way to act on it — the same defect `_post_upgrade_findings` was
            # written to stop, arriving through the aggregate. The remedy line per KB
            # is what makes each row actionable instead of merely informative.
            for f in findings:
                print(f"        {f}")
                codes.setdefault(f[:4], [])
                if label not in codes[f[:4]]:
                    codes[f[:4]].append(label)
            if errs:
                failures.append(label)
        print(f"\nkb lint: {len(targets)} KB(s), {total_e} error(s), {total_w} warning(s)"
              + (f", {len(no_cli)} with no CLI to lint with" if no_cli else ""))
        # THE REMEDY IS THE POINT. A numbered list of codes without the command that
        # clears each one turns a lint into another thing to research, so the
        # aggregate answer names the fix and the KBs it applies to. `remedies:` is the
        # exact prefix `_post_upgrade_findings` prints, so a per-repo run and the estate
        # run name the same command for the same code.
        rem = _remedies_for(codes.keys())
        if rem:
            print(f"remedies: {rem}")
            for code, kbs in sorted(codes.items()):
                print(f"        {code} in {len(kbs)} KB(s): {', '.join(kbs[:12])}"
                      + (f" (+{len(kbs) - 12} more)" if len(kbs) > 12 else ""))
        if failures:
            die(f"{len(failures)} KB(s) with errors: {', '.join(failures)}", ERR)
        return
    die(f"unknown kb subcommand {cmd}", ERR)


def cmd_fleet(args) -> None:
    """fleet: one surface for the whole job — what is behind, take it current, what to fix after.

    The operator's ask, measured 2026-10-31: three commands answered three parts of
    one job in three geometries, and joining them by path was the manual search this
    replaces. "What is stale" was `installs verify --against-shipped` (a flat list with
    no KB label), "take it current" was `installs upgrade` (the same list, a different
    verb), "what must I fix" was `kb lint --all` (rows keyed by label, capped at three
    findings with no remedy). The label came from `_kb_label()`, which only `kb` used,
    so no single output could name a KB, its version, and its fixes together.

    Nothing new is invented here: `list` reads the registry, `upgrade` calls the
    dispatcher that already scopes and already dry-runs, `lint` reuses the per-KB
    printer. The rule this obeys is the genome's own — one owner per question, so the
    verb is a joining surface and not a second registry.

    `genome fleet` alone is `list`: the glance that answers "which are behind", which
    is the question every upgrade starts from."""
    sub = getattr(args, "fleet_cmd", None) or "list"
    if sub == "upgrade":
        _dispatch_upgrade(load_installs()["installs"], getattr(args, "apply", False),
                          getattr(args, "target", None) or getattr(args, "roots", None))
        return
    if sub == "lint":
        # `fleet lint [names...]` is `kb lint --all` with an optional scope, so the
        # printer, the counting, and the empty-registry gate have one owner. `target`
        # names the scope and `all` asks for every KB; when both arrive the scope wins.
        args.kb_cmd = "lint"
        args.all = not bool(getattr(args, "target", None))
        cmd_kb(args)
        return
    _fleet_list()


def _fleet_list() -> None:
    """Every registered install by label, version and status — one line per thing to act on.

    A line is grouped by what the operator does about it: behind (upgradable), current,
    a skills root or package install (the thing the fleet converges toward), and a KB
    with no local CLI (present, legitimate, nothing to compare). The groups are the
    answer to "what must I do", so the list ends with the counts rather than leaving
    them to be summed by eye."""
    rows = load_installs()["installs"]
    if not rows:
        die("no installs registered — this machine has proven nothing: run install.sh "
            "(it registers everything it creates), or `genome installs scan`", ERR)
    ref = _current_release()
    behind, current, sources, no_cli = [], [], [], []
    for r in sorted(rows, key=lambda r: (r.get("kind", ""), r["path"])):
        p = Path(r["path"])
        kind = r.get("kind", "?")
        if kind in ("skill", "bin"):
            sources.append((p, kind, _version_of(p)))
            continue
        v = _version_of(p)
        if v in ("none", "missing"):
            no_cli.append((p, _kb_label(p), v))
        elif _version_key(v) < _version_key(ref):
            behind.append((p, _kb_label(p), v))
        else:
            current.append((p, _kb_label(p), v))
    print(f"fleet: {len(rows)} registered install(s) · current release {ref}")
    if sources:
        print(f"\n  sources ({len(sources)}) — what the fleet converges on")
        for p, kind, v in sources:
            print(f"    {kind:9} {v:14} {p}")
    if behind:
        print(f"\n  behind ({len(behind)}) — `genome fleet upgrade --roots <name>` takes one current")
        for p, label, v in behind:
            print(f"    {label:34} {v:14} {p}")
    if current:
        print(f"\n  current ({len(current)})")
        for p, label, v in current:
            print(f"    {label:34} {v:14} {p}")
    if no_cli:
        print(f"\n  no local CLI ({len(no_cli)}) — registered, nothing to compare")
        for p, label, v in no_cli:
            print(f"    {label:34} {v:14} {p}")
