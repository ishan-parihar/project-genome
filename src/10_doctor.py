# ---------------------------------------------------------------- doctor

def py_imports(cfg: Cfg, script: Path) -> set[Path]:
    """Repo files a Python script imports, transitively (resolved from the root and the script's dir).
    ponytail: static `import`/`from` lines only; importlib and sys.path tricks are not followed."""
    seen: set[Path] = set()
    todo = [script]
    root = cfg.root.resolve()
    extra = [root / p for p in cfg.get("ops", "py_paths", [])]  # dirs the code puts on sys.path
    while todo:
        f = todo.pop()
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        for m in re.finditer(r"^\s*(?:from\s+(\.*[\w.]*)\s+import\s+([\w, ]+)|import\s+([\w., ]+))", read(f), re.M):
            mods = [m.group(1)] if m.group(1) is not None else [x.split(" as ")[0].strip() for x in m.group(3).split(",")]
            subs = [s.strip() for s in (m.group(2) or "").split(",") if s.strip()]
            for mod in mods:
                dots = len(mod) - len(mod.lstrip("."))
                bases = [f.parent.joinpath(*[".."] * (dots - 1)).resolve()] if dots else [root, f.parent, *extra]
                parts = [p for p in mod.lstrip(".").split(".") if p]
                for b in bases:
                    for cand in [parts] + [parts + [s] for s in subs]:
                        if not cand:
                            continue
                        p = b.joinpath(*cand)
                        for hit in (p.with_suffix(".py"), p / "__init__.py"):
                            if hit.is_file() and root in hit.resolve().parents:
                                todo.append(hit.resolve())
    return seen


def running_edits(cfg: Cfg) -> list[str]:
    """Modified files that a running process executes, or that its Python script imports."""
    dirty = {p for st, p in changed_paths(cfg) if st != "??"}
    if not dirty or not Path("/proc").is_dir():  # without /proc a process's cwd is unknown: say nothing, not something wrong
        return []
    hits: dict[str, tuple[str, set[str]]] = {}  # file → (how, pids): wrappers (shell, timeout) repeat one job
    root = cfg.root.resolve()
    for ln in sh(cfg.root, "ps", "-eo", "pid=,args=").splitlines():
        pid, _, cmd = ln.strip().partition(" ")
        try:
            cwd = Path(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            cwd = root
        argv = cmd.split()
        for i, tok in enumerate(argv):
            if i and argv[i - 1] == "-m":
                p = cwd.joinpath(*tok.split("."))
                p = p.with_suffix(".py") if p.with_suffix(".py").is_file() else p / "__main__.py"
            elif tok.endswith((".py", ".sh")):
                p = cwd / tok
            else:
                continue
            if not p.is_file() or root not in p.resolve().parents:
                continue
            files = py_imports(cfg, p.resolve()) if p.suffix == ".py" else {p.resolve()}
            for f in sorted(files):
                rel = cfg.rel(f)
                if rel in dirty:
                    how = "executes" if f == p.resolve() else f"imports (via {cfg.rel(p)})"
                    hits.setdefault(rel, (how, set()))[1].add(pid)
    return [f"running job edits: {rel} is modified while pid {', '.join(sorted(pids)[:3])} {how} it — "
            "do not change a running job's code" for rel, (how, pids) in sorted(hits.items())]


def _changed_since(root: Path, named: str, head: str) -> list[str] | None:
    """The paths changed between `named` and `head`, or None when the range
    cannot be read (a rewritten history, a shallow clone)."""
    try:
        r = subprocess.run(["git", "diff", "--name-only", f"{named}..{head}"],
                           cwd=root, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return [ln for ln in r.stdout.splitlines() if ln]


def doctor_findings(cfg: Cfg) -> tuple[list[str], list[str]]:
    finds, info = [], []
    head = sh(cfg.root, "git", "rev-parse", "HEAD").strip()
    if not head:
        finds.append("not a git repo — append-only and staleness checks need history")
    if cfg.has("state") and head:
        heads = re.findall(r"\b[0-9a-f]{40}\b", read(cfg.path("state")))
        if heads and heads[0] != head:
            named = heads[0]
            # A snapshot names the commit it was generated at, so it names
            # the commit BEFORE the one that carried it — the literal
            # comparison could never converge, and the close-out pattern
            # ("write the snapshot, commit it with the worklog") always
            # left the check red. A snapshot still describes the tree when
            # every commit SINCE it touched only documentation (or a
            # configured role path): a code commit invalidates it, a
            # docs-only close-out does not.
            touched = _changed_since(cfg.root, named, head)
            if touched is None:
                finds.append(f"stale state: {cfg.paths['state']} names {named[:8]}, HEAD is {head[:8]} "
                             f"(the named commit is not in this history — the snapshot cannot be compared)")
            else:
                role_paths = {cfg.rel(cfg.path(r)) for r in cfg.paths if cfg.has(r)}
                code_touched = [f for f in touched
                                if not f.startswith("docs/")
                                and not any(f == rp or f.startswith(rp.rstrip("/") + "/") for rp in role_paths)]
                if code_touched:
                    finds.append(f"stale state: {cfg.paths['state']} names {named[:8]}, HEAD is {head[:8]} "
                                 f"({len(code_touched)} non-documentation path(s) changed since)")
                else:
                    info.append(f"state snapshot {named[:8]} is current: only documentation changed since it")
    # append-only roles: no line removed over the last core.append_window commits, nor in the working tree.
    # A numbered worklog is a directory: its entries are append-only (renames allowed), its index is generated.
    window = int(cfg.get("core", "append_window", 10))
    base = (sh(cfg.root, "git", "rev-list", f"--max-count={window + 1}", "HEAD").split() or [""])[-1]
    for role in APPEND_ONLY:
        if not (cfg.has(role) and head):
            continue
        rel = cfg.paths[role].rstrip("/")
        spec = [rel] + ([f":(exclude){cfg.rel(worklog_index(cfg))}"] if cfg.path(role).is_dir() else [])
        ranges = [(f"the last {window} commits", [base, "HEAD"])] if base and base != head else []
        for label, rng in ranges + [("the working tree", ["HEAD"])]:
            diff = sh(cfg.root, "git", "diff", "-M", "--diff-filter=DM", *rng, "--", *spec)
            removed = sum(1 for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---"))
            if removed:
                finds.append(f"append-only violation: {removed} line(s) removed from {rel} in {label}")
    for mod in sorted(cfg.modules):
        for role in MODULE_ROLES[mod]:
            form, target = cfg.form(role)
            if form != "file":
                info.append(f"{form}: {role} → {target}")
            elif role not in ("readme", "docs", "evidence") and not cfg.path(role).exists() \
                    and (not cfg.legacy or role in cfg.declared):
                finds.append(f"missing role: {role} ({cfg.paths[role]})")
    for role in ("state", "entry", "runbook"):
        if cfg.has(role):
            age = (dt.datetime.now().timestamp() - cfg.path(role).stat().st_mtime) / 86400
            if age > 30:
                finds.append(f"stale {role}: untouched for {age:.0f} days")
    if cfg.has("asks"):
        for r in rows(cfg.path("asks")):
            if len(r) > 5 and r[2] == "ruled" and r[5] in ("", "—"):
                finds.append(f"ruling {r[0]} not applied to its owner (genome q apply {r[0]} --applied <path>)")
    finds += running_edits(cfg)
    d = cfg.path("workflows")
    if "agents" in cfg.modules and cfg.form("workflows")[0] == "file" and d.is_dir():
        for f in sorted(d.glob("*.md")):
            info += [f"live claim {f.stem}: {r[0]} {r[3]}" for r in rows(f) if len(r) > 3 and r[1] == "in-progress"]
    return finds, info


def inventory(cfg: Cfg) -> list[str]:
    """What an agent needs to decide what to archive next: sizes against budgets, record and history counts."""
    out = []
    files = tracked(cfg)
    size = sum((cfg.root / f).stat().st_size for f in files if (cfg.root / f).is_file())
    out.append(f"inventory: {len(files)} tracked files, {size / 1e6:.0f} MB")
    for rel, limit in (cfg.get("core", "budgets", {}) or {}).items():
        p = cfg.root / rel
        if p.is_file():
            out.append(f"budget: {rel} {p.stat().st_size}/{limit} bytes ({100 * p.stat().st_size // limit} %)")
    if "records" in cfg.modules:
        act = records(cfg)
        out.append(f"records: {sum(r['kind'] == 'AD' for r in act)} AD + {sum(r['kind'] == 'RG' for r in act)} RG active, "
                   f"{len(records(cfg, True))} retired in {cfg.rel(rec_archive(cfg))}")
    if worklog_numbered(cfg) and (wf := worklog_files(cfg)):
        out.append(f"worklog: {len(wf)} entries, latest {wf[-1].name}")
    # a vendored copy drifts from the skill it came from; say so (never auto-update: the repo pins its tool).
    # An installed package has no separate skill copy: it IS the shipped one, so there
    # is nothing to drift from and nothing to report.
    skill = skill_copy()
    me = Path(__file__).resolve()
    if skill.is_file() and skill.resolve() != me and skill.read_bytes() != me.read_bytes():
        v = re.search(r'^VERSION = "([^"]+)"', read(skill), re.M)
        vk = lambda s: tuple(int(x) for x in re.findall(r"\d+", s))
        if v and vk(v.group(1)) < vk(VERSION):  # the repo is ahead of the installed skill: nothing to pull in
            out.append(f"upgrade: this genome is {VERSION}, newer than the installed skill copy ({v.group(1)}); nothing to upgrade")
            return out
        out.append(f"upgrade: this genome is {VERSION}, the skill copy is {v.group(1) if v else '?'} — "
                   + (f"`genome upgrade` shows the changes, `genome upgrade --apply` swaps it in" if "def cmd_upgrade" in me.read_text()
                    else f"`cp {skill} {cfg.rel(me)}` once, then `genome migrate` (later upgrades use `genome upgrade`)"))
    return out


def cmd_doctor(args) -> None:
    cfg = find_cfg()
    finds, info = doctor_findings(cfg)
    if args.json:
        jprint({"healthy": not finds, "findings": finds, "info": info + inventory(cfg)})
        return
    for i in info + inventory(cfg):
        print(i)
    print(f"doctor: {len(finds)} finding(s)" if finds else "doctor: healthy")
    for f in finds:
        print(f"  - {f}")


