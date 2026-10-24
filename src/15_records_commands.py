# ---------------------------------------------------------------- records commands

def recon_file(cfg: Cfg) -> Path:
    return cfg.root / ".genome" / "recon.json"


def recon_tokens(cfg: Cfg) -> dict[str, dict]:
    """Live recon tokens (token -> {ts, kw}); a token older than records.recon_hours is dropped."""
    try:
        raw = json.loads(read(recon_file(cfg)) or "{}")
    except json.JSONDecodeError:
        raw = {}
    toks_ = raw.get("tokens", {})
    if "token" in raw:  # the single-token form written by earlier versions
        toks_[raw["token"]] = {"ts": raw.get("ts", 0), "kw": raw.get("kw", "")}
    cutoff = dt.datetime.now().timestamp() - cfg.get("records", "recon_hours", 6) * 3600
    return {t: v for t, v in toks_.items() if v.get("ts", 0) >= cutoff}


def cmd_rec(args) -> None:
    cfg = find_cfg()
    cfg.need("records")
    a = args.rec_cmd
    if a == "recon":
        kw = " ".join(args.keywords)
        q = toks(kw)
        hits = []
        for r in records(cfg) + records(cfg, True):
            s = len(q & toks(r["title"] + " " + r["desc"])) * 3 + len(q & toks(r["text"][:4000]))
            if s:
                hits.append((s, r))
        hits.sort(key=lambda x: -x[0])
        print(f"records matching '{kw}':")
        for s, r in hits[:10]:
            where = "archived" if is_archived(cfg, cfg.rel(r["path"])) else r["status"]
            print(f"  {r['id']:16} {where:10} {r['title'][:90]}")
        print("owner sections matching:")
        for s, f, h, lo, hi, _ in ask_rank(cfg, kw, 6):
            print(f"  {cfg.rel(f)}:{lo}-{hi} § {h[:70]}")
        token = "R" + dt.datetime.now().strftime("%m%d%H%M%S") + hashlib.sha1(f"{os.getpid()}{time.time_ns()}".encode()).hexdigest()[:3]
        recon_file(cfg).parent.mkdir(exist_ok=True)
        with Guarded(recon_file(cfg)):  # parallel agents each keep their own token
            tokens = recon_tokens(cfg)
            tokens[token] = {"ts": dt.datetime.now().timestamp(), "kw": kw}
            atomic_write(recon_file(cfg), json.dumps({"tokens": tokens}))
        print(f"\nrecon token {token} — amend an owner above if it covers the topic; otherwise "
              f"`genome rec new ad|rg \"<title>\" --recon {token} --orthogonal \"<why no owner covers it>\"`")
        return
    if a == "new":
        hours = cfg.get("records", "recon_hours", 6)
        rc = recon_tokens(cfg).get(args.recon)
        if rc is None:
            die(f"--recon must be the token of a `genome rec recon` run in the last {hours} h (prior art first)")
        kind = args.kind.upper()
        d = cfg.require("decisions" if kind == "AD" else "regressions", "genome rec new")
        d.mkdir(parents=True, exist_ok=True)
        lock = Guarded(d / ".genome-rec")  # released at exit: two agents never mint one ID
        lock.__enter__()
        known = records(cfg) + records(cfg, True)
        nums = [r["num"] for r in known if r["kind"] == kind]
        # an ID anyone ever cited is spent, even when its file is gone (a retired record not yet imported)
        cited = re.compile(rf"\b{re.escape(rec_prefix(cfg))}{kind}-(\d+)\b")
        nums += [int(x) for r in known for x in cited.findall(r["text"])]
        if cfg.has("records_index"):
            nums += [int(x) for x in cited.findall(read(cfg.path("records_index")))]
        width = cfg.get("records", "width", 3)
        top = max((r["num"] for r in known if r["kind"] == kind), default=0)
        if max(nums, default=0) > top + 1:  # a typo'd citation spends a number for good; say so
            print(f"note: {kind}-{max(nums):0{width}d} is cited but has no record, so numbering continues after it "
                  f"(a typo? `genome lint` lists unknown citations as W105)", file=sys.stderr)
        rid = f"{rec_prefix(cfg)}{kind}-{max(nums, default=0) + 1:0{width}d}"
        p = d / f"{rid}-{slugify(args.title)}.md"
        fm = {"ID": rid, "Title": args.title, "Status": "Active", "Date": today(),
              "Description": args.description or args.title}
        if kind == "RG":
            fm["Severity"] = args.severity
        body = (AD_BODY if kind == "AD" else RG_BODY).replace("{{ID}}", rid).replace("{{TITLE}}", args.title)
        mode = cfg.get("records", "mode", "immutable")
        body = body.replace("{{MODE}}", "Amended only by dated `## Amendment` sections (`genome rec amend`)."
                            if mode == "amendable" else "Immutable once numbered: a correction is a new record that supersedes this one.")
        body += f"\n## Orthogonality\n\n{args.orthogonal} (recon {args.recon}: {rc.get('kw', '')})\n\n## Revisions\n\n- {today()}: created\n"
        with open(p, "x") as f:
            f.write("---\n" + "\n".join(f'{k}: "{yq(v)}"' for k, v in fm.items()) + "\n---\n\n" + body)
        emit_records(cfg)
        print(cfg.rel(p))
        return
    if a == "amend":
        if cfg.get("records", "mode", "immutable") != "amendable":
            die("records.mode is immutable — correct a record with `genome rec supersede`, or set mode = \"amendable\"")
        r = find_record(cfg, args.id)
        body = (sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text()) if args.body_file else (args.body or "")
        if not body.strip():
            die("an amendment needs its text: --body \"...\" or --body-file <path>")
        text = r["text"]
        bad = [kv for kv in args.set or [] if not re.fullmatch(r"[A-Za-z][\w-]*=.*", kv)]
        if bad:
            die(f"--set takes Field=value, got {bad}")
        fields = dict(kv.split("=", 1) for kv in args.set or [])
        if {"ID", "Status"} & set(fields):
            die("--set cannot change ID or Status — use `genome rec supersede/merge/retire`")
        if fields:
            text = set_front(text, fields)
        # amendments are chronological at the end; the revision line goes into ## Revisions
        text = text.rstrip("\n") + f"\n\n## Amendment {today()} — {args.title}\n\n{body.strip()}\n"
        rev = f"- {today()}: {args.reason}" + (f" [Updated: {', '.join(f'{k}={v}' for k, v in fields.items())}]" if fields else "")
        atomic_write(r["path"], add_revision(text, rev))
        emit_records(cfg)
        print(f"{r['id']}: amended ({args.title})")
        return
    if a in ("supersede", "merge", "retire"):
        ids = args.ids
        target = None if a == "retire" else find_record(cfg, args.by)
        plan = [find_record(cfg, rid) for rid in ids]  # all exist, or nothing moves
        for r in plan:
            if target and r["id"] == target["id"]:
                die(f"{r['id']} cannot be merged into itself — nothing was changed")
            if (rec_archive(cfg) / r["path"].name).exists():
                die(f"the records archive already holds {r['path'].name} — nothing was changed")
        for r in plan:
            st = "Retired" if a == "retire" else "Superseded"
            fields = {"Status": st}
            if target:
                fields["SupersededBy"] = target["id"]
            text = add_revision(set_front(r["text"], fields), f"- {today()}: {st.lower()}"
                                + (f" by {target['id']}" if target else "") + f" — {args.reason}")
            dst = rec_archive(cfg) / r["path"].name
            atomic_write(dst, text)
            r["path"].unlink()
            if target:
                atomic_write(target["path"], add_revision(read(target["path"]),
                                                          f"- {today()}: absorbed {r['id']} — {args.reason}"))
            print(f"{r['id']} → {st}{' by ' + target['id'] if target else ''}; moved to {cfg.rel(dst)}")
            cites = [f for f in readers(cfg, r["id"]) if f != cfg.rel(dst)]
            if cites:
                print(f"  {len(cites)} live file(s) cite {r['id']} — they resolve through the ID map; relink when you touch them")
        emit_records(cfg)
        return
    if a == "list":
        recs = records(cfg) + (records(cfg, True) if args.all else [])
        if args.json:
            jprint([{"id": r["id"], "status": r["status"], "title": r["title"], "path": cfg.rel(r["path"])} for r in recs])
            return
        for r in recs:
            print(f"{r['id']:16} {r['status']:10} {r['title'][:100]}")
        return
    if a == "show":
        r = find_record(cfg, args.id, archived_ok=True)
        if r["status"] in ("Superseded", "Retired"):
            print(f"{r['id']} is {r['status']}" + (f" → read {r['by']}" if r["by"] else ""))
        print(cfg.rel(r["path"]))
        print("\n".join(r["text"].splitlines()[:args.lines]))
        return
    if a == "emit":
        ch = emit_records(cfg)
        print(f"emitted: {', '.join(ch) if ch else 'unchanged'}")


