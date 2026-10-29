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
    follows: an unproven thing is not a green thing."""
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
    findings = [f"{f.get('code','?')}: {f.get('text','')}" for f in j.get("findings", [])][:3]
    return (errs, warns, findings)


def cmd_kb(args) -> None:
    """kb: list | lint | show — the machine's knowledge bases, reachable from anywhere."""
    cmd = getattr(args, "kb_cmd", "list")
    if cmd == "list":
        rows = kb_rows()
        if not rows:
            print("no knowledge bases registered — `genome installs register kb <path>`")
            return
        for r in sorted(rows, key=lambda r: r["path"]):
            p = Path(r["path"])
            print(f"{_kb_label(p):34} {p}  [{r.get('kind','?')}]")
        print(f"\n{len(rows)} knowledge base(s) registered")
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
            for f in findings:
                print(f"        {f}")
            if errs:
                failures.append(label)
        print(f"\nkb lint: {len(targets)} KB(s), {total_e} error(s), {total_w} warning(s)"
              + (f", {len(no_cli)} with no CLI to lint with" if no_cli else ""))
        if failures:
            die(f"{len(failures)} KB(s) with errors: {', '.join(failures)}", ERR)
        return
    die(f"unknown kb subcommand {cmd}", ERR)
