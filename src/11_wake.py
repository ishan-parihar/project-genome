# ---------------------------------------------------------------- wake

def section_by_heading(path: Path, needle: str, cap: int) -> tuple[int, list[str]] | None:
    lines = read(path).splitlines()
    hs = headings(lines)
    hit = next(((k, lv) for k, lv in hs if needle.lower() in lines[k].lower()), None)
    bold = next((k for k, ln in enumerate(lines) if ln.startswith("**") and needle.lower() in ln.lower()), None)
    if hit is None and bold is None:
        return None
    i, lvl = hit if hit is not None and (bold is None or hit[0] < bold) else (bold, 7)
    j = heading_end(hs, i, lvl, len(lines))
    body = lines[i:j]
    return i + 1, body[:cap] + ([f"... ({len(body) - cap} more lines)"] if len(body) > cap else [])


def cmd_wake(args) -> None:
    """One call, a few kB: everything a resuming agent needs, and where to read next."""
    if getattr(args, "write", False):  # the handoff zone lives here now; `handoff` is its alias
        return cmd_handoff(args)
    cfg = find_cfg()
    br = sh(cfg.root, "git", "rev-parse", "--abbrev-ref", "HEAD").strip()
    head = sh(cfg.root, "git", "rev-parse", "--short", "HEAD").strip()
    dirty = len(sh(cfg.root, "git", "status", "--porcelain").splitlines())
    print(f"# genome wake — {cfg.root.name} @ {br or '-'} {head or '-'} ({dirty} dirty) "
          f"[{', '.join(sorted(cfg.modules))}]")
    cap = cfg.get("core", "wake_lines", 18)
    if cfg.has("state"):
        lines = read(cfg.path("state")).splitlines()
        start = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), 0)
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        print(f"\n## STATE  {cfg.paths['state']}:{start + 1}-{end}")
        print("\n".join(lines[start:min(end, start + cap)]))
        if end - start > cap:
            print(f"... ({end - start - cap} more lines in the top block)")
    res = cfg.get("core", "resume")
    if res:
        path, _, needle = res.partition("#")
        got = section_by_heading(cfg.root / path, needle or cfg.get("core", "resume_heading", "Resume here"),
                                 cfg.get("core", "resume_lines", 30))
        if got:
            print(f"\n## RESUME  {path}:{got[0]}")
            print("\n".join(got[1]))
        else:
            print(f"\n## RESUME  (no '{needle}' heading in {path})")
    elif cfg.has("register"):
        open_rows = [r for r in register_rows(cfg) or [] if len(r) > 2 and r[1] in ("open", "in-progress", "blocked")]
        print(f"\n## REGISTER  {len(open_rows)} open")
        for r in open_rows[:8]:
            print(f"- [{r[1]}] {r[0]}: {r[2][:90]}")
    if cfg.has("asks"):
        pend = [r for r in rows(cfg.path("asks")) if len(r) > 5 and (r[2] == "open" or (r[2] == "ruled" and r[5] in ("", "—")))]
        if pend:
            print("\n## OPERATOR")
            for r in pend:
                print(f"- {r[0]} [{r[2]}{', unapplied' if r[2] == 'ruled' else ''}] {r[1]}: {r[3][:110]}")
    if "research" in cfg.modules and cfg.has("hypotheses"):
        reg = Register(cfg, "hypotheses")
        live = [r for r in reg.rows if status_word(reg.get(r, "status")) in ("open", "testing")]
        if live:
            print(f"\n## HYPOTHESES  {len(live)} open/testing  ({cfg.paths['hypotheses']})")
            for r in live[:8]:
                print(f"- {r[0]} [{status_word(reg.get(r, 'status'))}] {reg.get(r, 'text')[:110]}")
    jobs = cfg.get("ops", "jobs") if "ops" in cfg.modules else None
    if jobs:
        try:
            out = subprocess.run(jobs, shell=True, cwd=cfg.root, capture_output=True, text=True, timeout=30).stdout
        except subprocess.TimeoutExpired:
            out = "(jobs command timed out)"
        print(f"\n## JOBS  `{jobs}`")
        print("\n".join(out.strip().splitlines()[:12]) or "(none)")
    if worklog_numbered(cfg):
        wf = worklog_files(cfg)
        if wf:
            print(f"\n## LAST WORKLOG  {cfg.rel(wf[-1])}")
    elif cfg.has("worklog"):
        print("\n## LAST WORKLOG")
        print("\n".join(read(cfg.path("worklog")).splitlines()[-3:]))
    if "agents" in cfg.modules and cfg.has("feed"):
        aid = os.environ.get("GENOME_AGENT_ID") or os.environ.get("KB_AGENT_ID")
        if aid:
            seen_f = cfg.root / ".genome" / f"seen-{aid}"
            seen = read(seen_f).strip()
            lines = read(cfg.path("feed")).splitlines()
            if seen:
                idx = next((i for i, l in enumerate(lines) if f"[{seen}]" in l), -1)
                lines = lines[idx + 1:]
            mine = [l for l in lines if f"@{aid}" in l]
            print(f"\n## INBOX  @{aid}: {len(mine)} new")
            print("\n".join(mine[-8:]))
            ids = re.findall(r"\*\*\[(F\d{4,})\]", read(cfg.path("feed")))
            if ids:
                seen_f.parent.mkdir(exist_ok=True)
                seen_f.write_text(ids[-1])
    if cfg.kinds:  # one line per kind: counts per state, generated and never hand-kept
        ents, _ = load_entities(cfg)
        print("\n## KINDS")
        none = []
        for name, k in kind_specs(cfg).items():
            by: dict[str, int] = {}
            for e in ents.values():
                if e["kind"] == name:
                    by[e["state"]] = by.get(e["state"], 0) + 1
            if by:
                parts = ", ".join(f"{s} {n}" for s, n in by.items() if s)  # a kind without states has only a count
                print(f"- {name}: {sum(by.values())}" + (f" ({parts})" if parts else ""))
            else:
                none.append(name)
        if none:
            print("- none yet: " + ", ".join(none))
        queue = wake_views(cfg)
        if queue:
            print("\n## QUEUE")
            print("\n".join(queue))
        pbs = sorted((cfg.root / "docs" / "playbooks").glob("*.md"))
        if pbs:
            print("playbook (read once per task): " + ", ".join(cfg_rel(cfg.root, p) for p in pbs))
    finds, _ = doctor_findings(cfg)
    lint = run_lint(cfg)
    errs = sum(1 for f in lint if f.startswith("E"))
    print(f"\n## HEALTH  doctor {len(finds)} finding(s) · lint {errs} error(s), {len(lint) - errs} warning(s)")
    for f in finds[:5]:
        print(f"- {f}")
    print("\nNext: `genome ask \"<question>\"` → the owning section; read only that range.")


