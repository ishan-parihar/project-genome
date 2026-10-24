# ---------------------------------------------------------------- close

def secret_values(cfg: Cfg) -> list[tuple[str, str]]:
    out = []
    for spec in cfg.get("ops", "secrets", []):
        path, _, key = spec.partition(":")
        p = Path(os.path.expanduser(path))
        p = p if p.is_absolute() else cfg.root / p
        if not p.is_file():
            continue
        if key:
            for ln in read(p).splitlines():
                m = re.match(rf"\s*(?:export\s+)?{re.escape(key)}\s*=\s*(.*)$", ln)
                if m:
                    v = m.group(1).strip()
                    if v[:1] in "'\"" and v.find(v[0], 1) > 0:  # quoted: up to the closing quote
                        v = v[1:v.find(v[0], 1)]
                    else:  # unquoted: an inline ` # comment` is not part of the value
                        v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
                    out.append((spec, v))
        else:
            text = read(p).strip()
            out.append((spec, text))
            out += [(spec, ln.strip()) for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    seen, uniq = set(), []
    for s_, v in out:
        if len(v) >= 6 and v not in seen:
            seen.add(v)
            uniq.append((s_, v))
    return uniq


def secret_hits(cfg: Cfg) -> tuple[int, list[str]]:
    """Staged + unstaged diff, plus every untracked file `close` would name for commit."""
    vals = secret_values(cfg)
    if not vals:
        return 0, []
    if not is_git(cfg):  # no diff to read: scan every file the walk finds
        blob = "".join(read(cfg.root / f) for f in tracked(cfg)
                       if (cfg.root / f).is_file() and (cfg.root / f).stat().st_size < 2_000_000
                       and not any(f == v[0].partition(":")[0] for v in vals))
        return len(vals), [f"{spec}: {blob.count(v)} hit(s)" for spec, v in vals if v in blob]
    diff = sh(cfg.root, "git", "diff", "--cached", timeout=120) + sh(cfg.root, "git", "diff", timeout=120)
    for st, p in changed_paths(cfg):
        f = cfg.root / p
        if st == "??" and f.is_file() and f.stat().st_size < 20_000_000:
            diff += read(f)
    return len(vals), [f"{spec}: {diff.count(v)} hit(s)" for spec, v in vals if v in diff]


def cmd_secrets(args) -> None:
    cfg = find_cfg()
    cfg.need("ops")
    n, hits = secret_hits(cfg)
    if not n:
        print("secrets: no ops.secrets sources configured or readable")
        return
    for h in hits:
        print(f"SECRET IN DIFF — {h}")
    print(f"secrets: {n} source(s), {'HITS — do not commit' if hits else '0 hits'}")
    raise SystemExit(ERR if hits else 0)


def emit_all(cfg: Cfg) -> list[str]:
    changed = emit_records(cfg) if "records" in cfg.modules else []
    if worklog_numbered(cfg) and emit_worklog_index(cfg):
        changed.append(cfg.rel(worklog_index(cfg)))
    return changed + (emit_views(cfg) if cfg.views else []) + emit_status(cfg)


def cmd_emit(args) -> None:
    ch = emit_all(find_cfg())
    print(f"emitted: {', '.join(ch)}" if ch else "zones already current")


def collapse_paths(files: list[str], excluded: list[str], prefix: str = "") -> list[str]:
    """A directory stands for its files when three or more changed under it and none of them is left out."""
    by: dict[str | None, list[str]] = {}
    for f in files:
        head, sep, _ = f[len(prefix):].partition("/")
        by.setdefault(head if sep else None, []).append(f)
    out: list[str] = []
    for head, fs in by.items():
        d = f"{prefix}{head}/"
        if head is None or len(fs) < 3:
            out += fs
        elif not any(e.startswith(d) for e in excluded):
            out.append(d)
        else:
            out += collapse_paths(fs, excluded, d)
    return out


def cmd_close(args) -> None:
    """Mechanical iteration close: emit, lint, secrets, gate; print the judgement left."""
    cfg = find_cfg()
    red = False
    if cfg.get("card", "privacy") == "local" and is_git(cfg) and sh(cfg.root, "git", "remote").strip():
        die("privacy = \"local\" and this repo has a git remote: subjective data never leaves the machine. "
            "Remove the remote (`git remote remove <name>`) or change [card] privacy deliberately.", ERR)
    changed = emit_all(cfg)
    for cmd in cfg.get("core", "emitters", []):
        r = subprocess.run(cmd, shell=True, cwd=cfg.root, capture_output=True, text=True)
        print(f"emit   {cmd}: {'ok' if r.returncode == 0 else 'FAILED'}")
        red |= r.returncode != 0
    if changed:
        print(f"emit   genome zones refreshed: {', '.join(changed)}")
    lint = run_lint(cfg)
    errs = [f for f in lint if f.startswith("E")]
    print(f"lint   {len(errs)} error(s), {len(lint) - len(errs)} warning(s)")
    for f in errs[:20]:
        print(f"       {f}")
    red |= bool(errs)
    manuals = list(manual_docs(cfg))  # the judgement the drift check cannot make: did this change alter a manual?
    if manuals:
        print(f"judge  {len(manuals)} manual(s) declare covers: did this change alter one? If so, review it, then `genome verify <manual> --reviewed`")
    if not is_git(cfg):
        print("git    not a git repo — the secret scan reads every file, and no commit list can be named")
    if "ops" in cfg.modules:
        n, hits = secret_hits(cfg)
        print(f"secret {n} source(s), {len(hits)} hit(s)" + (" — " + "; ".join(hits) if hits else ""))
        red |= bool(hits)
    gate = cfg.get("core", "gate")
    if gate and not args.no_gate:
        r = subprocess.run(gate, shell=True, cwd=cfg.root, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
        print(f"gate   `{gate}`: {'ok' if r.returncode == 0 else 'FAILED'}" + ("".join(f"\n       {t}" for t in tail)))
        red |= r.returncode != 0
    if cfg.get("card", "privacy") == "local":
        print("privacy local: no card or federation; the paths below hold private data, so commit them only to a repo that stays private")
    paths = [p for _, p in changed_paths(cfg)]
    never = cfg.get("core", "never_commit", [])
    never = list(never) + ["**/*.genome-lock", ".genome/**", "**/*.genome-tmp"]
    staged_gone = {p for st, p in changed_paths(cfg) if st == "D "}  # `git add` on it fails the whole line
    named = [p for p in paths if not any(gmatch(p, g, cfg) for g in never) and not p.startswith(".genome/")
             and p not in staged_gone]
    # a path the layout check rejects is never named for commit: the tooling
    # must not produce the litter it is reporting
    misplaced = set(misplaced_paths(cfg))
    named = [p for p in named if p not in misplaced]
    print("\njudgement ([x] checked here, [?] yours to confirm):")
    checks = []
    if cfg.has("state"):
        sp = cfg.root / cfg.paths["state"]
        checks.append(("state updated", cfg.paths["state"] in paths and "— (date)" not in (read(sp) if sp.is_file() else "")))  # the empty template is not an update
    wl = cfg.paths["worklog"].rstrip("/")
    wl_index = cfg.rel(worklog_index(cfg)) if worklog_numbered(cfg) else None  # a re-emitted index is not an entry
    status = dict((p, st) for st, p in changed_paths(cfg))
    entries = [p for p in paths if p.startswith(wl) and p != wl_index and not status.get(p, " ").startswith("R")]
    checks.append(("worklog entry written", bool(entries)))  # a renamed old entry is not this session's entry
    rec_dirs = [cfg.paths[r].rstrip("/") for r in ("decisions", "regressions")] if "records" in cfg.modules else []
    touched = [p for p in paths if any(p.startswith(d) for d in rec_dirs)]
    if touched:
        ids = [r["id"] for p in touched if (cfg.root / p).is_file() and (r := parse_record(cfg, cfg.root / p))]
        text = "\n".join(read(cfg.root / e) for e in entries)
        missing = [i for i in ids if not re.search(rf"\b{re.escape(i)}\b", text)]
        checks.append((f"records changed ({len(touched)}) are cited in the worklog"
                       + (f" — not cited: {', '.join(missing)}" if missing else ""), bool(entries) and not missing))
    for item in cfg.get("core", "checklist", []):
        checks.append((item, None))
    for text, ok in checks:
        print(f"  [{'x' if ok else ' ' if ok is False else '?'}] {text}")
    if misplaced:
        print("\nnot committed — these are in no role's location:")
        for p in sorted(misplaced):
            print(f"  {p}")
        print("  move it, or give it a role, then run close again")
    if named:
        shown = collapse_paths(named, [p for p in paths if p not in named]) if len(named) > 12 else named
        print("\ncommit named paths:\n  git add -- " + " ".join(shlex.quote(p) for p in shown))
    skipped = len(paths) - len(named)
    if skipped:
        print(f"  ({skipped} path(s) left out by core.never_commit)")
    print(f"\nclose: {'RED — fix before commit' if red else 'green'}")
    raise SystemExit(ERR if red else 0)


