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


def _append_only_hunks(root: Path, rel: str) -> list[tuple[str, str, list[list[tuple[str, str]]]]]:
    """The history of one append-only file as (commit, subject, hunks), oldest first.

    A hunk is a list of (kind, line) pairs with kind "+" or "-"; context lines are
    dropped.  Renames are followed, so a renamed entry keeps its history.

    MERGES ARE INCLUDED.  `git log -p` omits a merge's diff by default, so a
    removal introduced ONLY by a merge's conflict resolution was invisible —
    measured 2026-11-05: a published line dropped by the merge and by no branch
    commit yielded 0 violations, and `--diff-merges=first-parent` yields 1.
    The flag is added only if this git understands it (it landed in git 2.31),
    so an older git still gets a working check rather than an error.
    """
    args = ["git", "log", "--reverse", "--format=@@@COMMIT %H %s", "-p", "--no-color",
            "--find-renames", "--follow"]
    probe = subprocess.run(args + ["--diff-merges=first-parent", "--", rel],
                           cwd=root, capture_output=True, text=True, timeout=60)
    if probe.returncode == 0:
        out = probe
    else:
        out = subprocess.run(args + ["--", rel],
                             cwd=root, capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return []
    commits: list[tuple[str, str, list[list[tuple[str, str]]]]] = []
    sha = subj = None
    hunks: list[list[tuple[str, str]]] = []
    hunk: list[tuple[str, str]] | None = None
    for line in out.stdout.splitlines():
        if line.startswith("@@@COMMIT "):
            if sha:
                commits.append((sha, subj, hunks))
            _, sha, subj = line.split(" ", 2)
            hunks, hunk = [], None
        elif line.startswith("@@"):
            hunk = []
            hunks.append(hunk)
        elif line.startswith(("--- ", "+++ ", "diff --git", "index ", "similarity ", "rename ",
                              "old mode", "new mode", "deleted file", "new file", "Binary",
                              "\\ No newline")):
            continue
        elif hunk is not None and line.startswith("+"):
            hunk.append(("+", line[1:]))
        elif hunk is not None and line.startswith("-"):
            hunk.append(("-", line[1:]))
    if sha:
        commits.append((sha, subj, hunks))
    return commits


def _published_and_removed(hunks_per_commit) -> tuple[set[str], list[tuple[str, str, str, bool]]]:
    """Split a file's history into what was PUBLISHED and what was removed.

    A line added in a hunk that ALSO removed lines is REPLACEMENT TEXT: it was
    never a legitimate publication, because that hunk was an in-place rewrite.
    Removing replacement text later is the REPAIR of an illegal rewrite, not a
    second violation — so only lines added in PURE-APPEND hunks count as
    published, and only their removal can be a violation.

    Attribution is CHRONOLOGICAL: a removal is judged against what had been
    published UP TO THAT COMMIT.  A line first published at commit 9 cannot
    make its own removal at commit 5 a violation.

    Returns (published_lines, [(commit, subject, removed_line, was_published_then), ...]).
    """
    published: set[str] = set()
    removed: list[tuple[str, str, str, bool]] = []
    for sha, subj, hunks in hunks_per_commit:
        for h in hunks:
            mixed = any(k == "-" for k, _ in h)
            for k, line in h:
                if k == "+" and not mixed:
                    published.add(line)
        for h in hunks:
            for k, line in h:
                if k == "-":
                    removed.append((sha, subj, line, line in published))
    return published, removed


def _append_only_paths(cfg: Cfg, role: str) -> list[str]:
    """The repo-relative paths an append-only role covers, or [] when it is not a
    plain path in this repo (a native/overlay role is owned elsewhere and the
    append-only law does not apply to it here)."""
    form, target = cfg.form(role)
    if form != "file":
        return []
    rel = target.split("#", 1)[0].rstrip("/")
    if not rel:
        return []
    if (cfg.root / rel).is_dir():
        return [rel]
    return [rel]


def _append_only_violations(cfg: Cfg, window: int, head: str) -> list[str]:
    """Append-only violations, attributed to the commit that made them.

    The rule, validated on 2026-11-05 against a repo whose doctor was red on a
    fully compliant repair:

      - A line was legitimately PUBLISHED iff it was added in a pure-append hunk.
      - A VIOLATION is a PUBLISHED line, removed inside the window, that is
        absent from the current content.
      - A compliant REPAIR (restore the original, append the correction as an
        AMENDED block) is silent: the original is published AND present now.
      - Removing REPLACEMENT TEXT — a line added by an earlier in-place
        rewrite — is silent: that is the repair of the earlier violation, not
        a second one.

    Two defects of the net-diff-over-a-window rule this replaces, both measured:

      1. FALSE POSITIVE.  The window's base was `rev-list --max-count=11 |
         tail -1`, which could itself BE the violating commit; the compliant
         repair then read as a removal against it (base a7265eea was the
         violation commit, so its repair raised "3 line(s) removed").
      2. FALSE NEGATIVE.  A net diff cannot see an in-place edit inside a file
         ADDED after the base.  11fbbedc removed a published line from 0542
         (born 5f0637e0, inside the window) and the check never reported it.

    Per-commit attribution fixes both: each removed line is judged against what
    was published and what is present now, never against an arbitrary base.
    Only files the window touched can violate, so only those are read — the
    publication reference still spans each one's WHOLE history (a line may be
    removed in the window long after it was published).
    """
    findings: list[str] = []
    if not head:
        return findings
    window_commits = set(sh(cfg.root, "git", "rev-list", f"--max-count={window}", "HEAD").split())
    if not window_commits:
        return findings
    # The append-only roles that live as plain paths in this repo.  A native or
    # overlay role is owned by another organ, so the law does not apply here.
    roles = {r: p for r in APPEND_ONLY for p in _append_only_paths(cfg, r)}
    if not roles:
        return findings
    # Every append-only path the window touched.  A numbered worklog entry may
    # be RENAMED freely (R4), so the window's file names are followed, not compared.
    touched = sh(cfg.root, "git", "log", f"--max-count={window}", "--name-only", "--format=", "--",
                 *sorted(set(roles.values())))
    for path in sorted({ln for ln in touched.splitlines() if ln}):
        role = next((r for r, p in roles.items() if path == p or path.startswith(p + "/")), None)
        if role is None:
            continue
        p = cfg.root / path
        if not p.is_file():
            continue
        if role == "worklog" and path == cfg.rel(worklog_index(cfg)):
            continue          # the index is generated
        now = set(read(p).splitlines())
        published, removed = _published_and_removed(_append_only_hunks(cfg.root, path))
        lost = [(sha, subj) for sha, subj, line, was_pub in removed
                if sha in window_commits and was_pub and line not in now]
        if lost:
            findings.append(f"append-only violation: {len(lost)} line(s) removed from {path} "
                            f"in the last {window} commits")
            for sha, subj in lost:
                findings.append(f"    committed {sha[:8]}: {subj[:70]}")
    return findings


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
    # append-only roles: no PUBLISHED line removed over the last core.append_window commits.
    # A numbered worklog is a directory: its entries are append-only (renames allowed), its index is generated.
    # The rule is per-commit and publication-aware (see _append_only_violations): a compliant
    # repair is silent and an in-place rewrite is still caught.
    window = int(cfg.get("core", "append_window", 10))
    finds += _append_only_violations(cfg, window, head)
    # The working tree: a published line removed but not yet committed.  Judged
    # against the same publication reference, so restoring a published line in
    # the working tree (the compliant repair, staged or not) is silent.
    for role in APPEND_ONLY:
        for path in _append_only_paths(cfg, role):
            if (cfg.root / path).is_dir():
                paths = [ln for ln in sh(cfg.root, "git", "ls-files", path).splitlines() if ln]
            else:
                paths = [path]
            for f in paths:
                if role == "worklog" and f == cfg.rel(worklog_index(cfg)):
                    continue
                p = cfg.root / f
                if not p.is_file():
                    continue
                diff = sh(cfg.root, "git", "diff", "-M", "--diff-filter=DM", "HEAD", "--", f)
                removed = [ln[1:] for ln in diff.splitlines()
                           if ln.startswith("-") and not ln.startswith("---")]
                if not removed:
                    continue
                published, _ = _published_and_removed(_append_only_hunks(cfg.root, f))
                now = set(read(p).splitlines())
                lost = [ln for ln in removed if ln in published and ln not in now]
                if lost:
                    finds.append(f"append-only violation: {len(lost)} line(s) removed from {f} "
                                 f"in the working tree")
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
    # A kind declaration that cannot work makes `graph`, `show`, `card`, `impact` and
    # `place` unable to run at all. Measured 2026-11-05: `doctor` reported
    # `healthy: true` on exactly such a repo while `lint` reported E501 — a health
    # check that does not check the thing that is broken. Doctor already reports
    # what lint reports for the other roles, so it reports this too.
    finds += [p.replace("E501 ", "", 1) for p in kind_problems(cfg)]
    # A numbered worklog must live in a DIRECTORY. Measured 2026-11-05: a repo
    # that flipped `worklog_form` to "numbered" while `worklog` still pointed
    # at the template's single file made `genome log` die with a raw
    # FileExistsError traceback — and `doctor` reported "healthy" on that
    # tree. The same shape as the kind check above: a health report that says
    # healthy next to a crashing command is a report that contradicts the
    # tool's own behaviour. The worklog is the surface a later session resumes
    # from, so it crashing is not a cosmetic problem.
    if cfg.has("worklog") and worklog_numbered(cfg):
        wl = cfg.path("worklog")
        if wl.exists() and not wl.is_dir():
            finds.append(f"numbered worklog needs `worklog` to be a DIRECTORY, but {cfg.rel(wl)} is a file "
                         f"— `genome log` crashes on it; point the role at a directory or use "
                         f"`worklog_form = \"file\"`")
    d = cfg.coord(cfg.path("workflows"))
    if "agents" in cfg.modules and cfg.form("workflows")[0] == "file" and d.is_dir():
        for f in sorted(d.glob("*.md")):
            info += [f"live claim {f.stem}: {r[0]} {r[3]}" for r in rows(f) if len(r) > 3 and r[1] == "in-progress"]
    if "agents" in cfg.modules and shutil.which("wt") is None and shutil.which("git-wt") is None:
        mgr = ("brew install worktrunk" if sys.platform == "darwin"
               else "sudo pacman -S worktrunk" if Path("/etc/arch-release").exists()
               else "winget install max-sixty.worktrunk" if sys.platform == "win32"
               else "cargo install worktrunk --locked")
        info.append(f"worktrunk not installed (parallel-agent worktrees): {mgr}")
    if "agents" in cfg.modules and (cfg.root / ".git").is_file() and cfg.coord_root() == cfg.root:
        # a linked worktree whose coordination fell back to LOCAL: the main checkout does not carry
        # this genome's config (pruned main, bare repo, submodule) — every guarantee the coordination
        # home makes is silently gone, so say so instead of letting agents trust flock that isn't there
        info.append("linked worktree resolved to LOCAL coordination — the main checkout carries no "
                    "genome.toml/kb.toml; claims and the feed are per-worktree until it is restored")
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


