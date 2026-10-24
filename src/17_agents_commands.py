# ---------------------------------------------------------------- agents commands

def agent_id(args) -> str:
    return getattr(args, "agent", None) or os.environ.get("GENOME_AGENT_ID") or os.environ.get("KB_AGENT_ID") \
        or f"agent-{platform.node()}"


def _post(cfg: Cfg, aid: str, msg: str, wf=None, to=None, reply=None) -> str | None:
    if cfg.form("feed")[0] != "file" or "agents" not in cfg.modules:
        return None
    feed = cfg.path("feed")
    feed.parent.mkdir(parents=True, exist_ok=True)
    with Guarded(feed):
        ids = [int(x) for x in re.findall(r"\*\*\[F(\d{4,})\]", read(feed))]
        fid = f"F{max(ids, default=0) + 1:04d}"
        head = f"- **[{fid}]** {now()} · `{aid}`" + (f" · wf:{wf}" if wf else "") + (f" · @{to}" if to else "") \
            + (f" · → {reply}" if reply else "")
        with open(feed, "a") as f:
            f.write(f"{head} — {msg}\n")
    return fid


def _wf_path(cfg: Cfg, wf: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", wf or ""):
        die(f"workflow name `{wf}` must be kebab-case")
    return cfg.require("workflows", "genome wf") / f"{wf}.md"


def _board_of(cfg: Cfg, item: str) -> Path:
    d = cfg.path("workflows")
    for f in sorted(d.glob("*.md")) if d.is_dir() else []:
        if find_row(f, item):
            return f
    die(f"no workflow board holds `{item}` — `genome wf list`")


def cmd_wf(args) -> None:
    cfg = find_cfg()
    cfg.need("agents")
    if args.wf_cmd == "new":
        p = _wf_path(cfg, args.name)
        if p.exists():
            die(f"board exists: {cfg.rel(p)}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(WF_TPL.replace("{{WF}}", args.name))
        print(f"workflow: {cfg.rel(p)} created")
    elif args.wf_cmd == "add":
        p = _wf_path(cfg, args.name)
        if not p.exists():
            die(f"no board `{args.name}` — `genome wf new {args.name}` first")
        with Guarded(p):
            n = max([int(m.group(1)) for r in rows(p) if (m := re.fullmatch(re.escape(args.name) + r"-(\d+)", r[0]))],
                    default=0) + 1
            append_row(p, [f"{args.name}-{n:03d}", "open", args.item, "—", "—"], "")
        print(f"{args.name}-{n:03d} added (open)")
    else:
        d = cfg.path("workflows")
        for f in sorted(d.glob("*.md")) if d.is_dir() else []:
            rs = rows(f)
            print(f"{f.stem:24} {len(rs):3} rows, {sum(r[1] == 'open' for r in rs if len(r) > 1)} open")


def cmd_claim(args) -> None:
    cfg = find_cfg()
    cfg.need("agents")
    p = _board_of(cfg, args.item)
    aid = agent_id(args)
    with Guarded(p):
        r = list(find_row(p, args.item))
        held = claim_holder(r[3] if len(r) > 3 else "")
        if held and held != aid:
            die(f"`{args.item}` is claimed by {held} — post to the feed or take another item", ERR)
        r[1], r[3] = "in-progress", claim_text(aid)
        replace_row(p, args.item, r)
    _post(cfg, aid, f"claiming `{args.item}` on board `{p.stem}`", p.stem)
    print(f"{args.item}: claimed by {aid}")


def cmd_done(args) -> None:
    cfg = find_cfg()
    cfg.need("agents")
    p = _board_of(cfg, args.item)
    if args.new_status in TERMINAL and not args.evidence:
        die("terminal: --evidence names where the verdict lives")
    with Guarded(p):
        row = find_row(p, args.item)
        r = list(row) + ["—"] * (5 - len(row))
        held = claim_holder(r[3])
        if held and held != agent_id(args):
            die(f"`{args.item}` is claimed by {held} — only the holder finishes it", ERR)
        r[1] = args.new_status
        if args.new_status in TERMINAL:
            r[4] = f"[{today()}] {args.evidence}" + (f" — {args.note}" if args.note else "")
        replace_row(p, args.item, r)
    _post(cfg, agent_id(args), f"`{args.item}` → {args.new_status}", p.stem)
    print(f"{args.item} → {args.new_status}")


def cmd_claim_register(args) -> None:
    cfg = find_cfg()
    cfg.need("agents")
    reg = cfg.require("register", "genome claim-register")
    aid = agent_id(args)
    with Guarded(reg):
        row = register_find(cfg, args.id) or die(f"no register row `{args.id}`")
        r = list(row) + [""] * (4 - len(row))
        held = claim_holder(r[3])
        if held and held != aid:
            die(f"`{args.id}` is claimed by {held}", ERR)
        claim = claim_text(aid)
        r[3] = f"{r[3]} · {claim}".strip(" ·") if r[3] and r[3] != "—" else claim
        register_replace(cfg, args.id, r)
    _post(cfg, aid, f"claiming register row `{args.id}`")
    print(f"register: {args.id} claimed by {aid}")


def cmd_post(args) -> None:
    cfg = find_cfg()
    cfg.need("agents")
    cfg.require("feed", "genome post")
    fid = _post(cfg, agent_id(args), args.message, args.workflow, args.to.lstrip("@") if args.to else None, args.reply)
    print(f"feed: [{fid}] by {agent_id(args)}")


def cmd_feed(args) -> None:
    cfg = find_cfg()
    cfg.need("agents")
    feed = cfg.require("feed", "genome feed")
    lines = read(feed).splitlines()
    if args.since:
        idx = next((i for i, l in enumerate(lines) if f"[{args.since}]" in l), None)
        if idx is None:
            die(f"--since {args.since}: no such feed id")
        lines = lines[idx + 1:]
    to = args.to.lstrip("@") if args.to else None
    for ln in lines:
        if (not args.workflow or f"wf:{args.workflow}" in ln) and (not to or f"@{to}" in ln or f"`{to}`" in ln):
            print(ln)


