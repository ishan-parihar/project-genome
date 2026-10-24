# ---------------------------------------------------------------- core commands

def cmd_status(args) -> None:
    cfg = find_cfg()
    reg = cfg.require("register", "genome status")
    if args.status not in STATUS_VOCAB:
        die(f"status must be one of {STATUS_VOCAB}")
    if args.status in TERMINAL and not args.evidence:
        die(f"`{args.id} -> {args.status}` is terminal: --evidence <existing path>")
    if args.evidence and not (cfg.root / args.evidence).exists():
        die(f"evidence path does not exist: {args.evidence}")
    with Guarded(reg):
        row = register_find(cfg, args.id) or die(f"no register row `{args.id}`")
        row = list(row) + [""] * (4 - len(row))
        held = claim_holder(row[3])
        if held and args.agent and held != args.agent:
            die(f"`{args.id}` is claimed by {held}", ERR)
        row[1] = args.status
        if args.status in TERMINAL:
            row[2] = f"{row[2]} → [{today()}] `{args.evidence}`" + (f" — verdict: {args.note}" if args.note else "")
        register_replace(cfg, args.id, row)
    print(f"register: {args.id} → {args.status}")


def cmd_plan(args, role: str = "plans") -> None:
    cfg = find_cfg()
    d = cfg.require(role, f"genome {role[:-1]}")
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{today()}-{slugify(args.title)}.md"
    if p.exists():
        die(f"{cfg.rel(p)} exists — pick another title")
    p.write_text((PLAN_TPL if role == "plans" else AUDIT_TPL).replace("{{TITLE}}", args.title).replace("{{DATE}}", today()))
    print(cfg.rel(p))


def readers(cfg: Cfg, needle: str) -> list[str]:
    out = sh(cfg.root, "git", "grep", "-l", "-w", "-F", "-e", needle, "--").splitlines()
    gen = {t for t in record_zone_targets(cfg)} | {cfg.paths["records_index"]}
    return [f for f in out if not is_archived(cfg, f) and f not in gen]


def cmd_archive(args) -> None:
    cfg = find_cfg()
    arch = cfg.require("archive", "genome archive")
    src = Path(args.path).resolve()
    if not (src.is_file() or (src.is_dir() and not args.section)) or cfg.root.resolve() not in src.parents:
        die(f"{args.path} is not a file (or, without --section, a directory) inside this project")
    rel = cfg.rel(src)
    gens = cfg.get("core", "archive_form", "flat") == "generations"
    gen = slugify(args.generation, 60) if args.generation else (f"{today()}-{slugify(args.reason, 30)}" if gens else "")
    if args.section:
        text = read(src)
        lines = text.splitlines()
        hs = headings(lines)
        want = args.section.lower().strip()
        exact = [(k, lv) for k, lv in hs if lines[k].lstrip("# ").strip().lower() == want]
        some = exact or [(k, lv) for k, lv in hs if want in lines[k].lower()]
        if not some:
            die(f"no heading containing '{args.section}' in {rel}")
        if len(some) > 1:  # moving the wrong section out of a living plan is silent damage
            die(f"'{args.section}' matches {len(some)} headings in {rel}: "
                + "; ".join(f"{k + 1}: {lines[k][:60]}" for k, _ in some[:5]) + " — give the exact heading text")
        i, lvl = some[0]
        j = heading_end(hs, i, lvl, len(lines))
        res_path, _, res_head = (cfg.get("core", "resume") or "").partition("#")
        res_head = res_head or cfg.get("core", "resume_heading", "Resume here")
        if res_path == rel and any(res_head.lower() in ln.lower() for ln in lines[i:j]):
            die(f"§ {lines[i].lstrip('# ')[:60]} holds the '{res_head}' block `genome wake` resumes from "
                "(sub-sections move with their parent) — move that block out first")
        name = f"{Path(rel).stem}--{slugify(lines[i], 40)}.md"
        dst = (arch / gen / Path(rel).parent / name) if gens else arch / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            die(f"{cfg.rel(dst)} exists")
        dst.write_text(f"<!-- archived {today()} from {rel} (lines {i + 1}-{j}): {args.reason} -->\n\n"
                       + "\n".join(lines[i:j]) + "\n")
        stub = f"> Archived {today()}: § {lines[i].lstrip('# ')[:80]} → `{cfg.rel(dst)}` ({args.reason})."
        atomic_write(src, "\n".join(lines[:i] + [stub, ""] + lines[j:]) + "\n")
        moved = f"{rel} § {lines[i].lstrip('# ')[:60]}"
    else:
        dst = (arch / gen / rel) if gens else arch / src.name
        if dst.exists():
            die(f"archive already holds {cfg.rel(dst)}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        moved = rel
        if not gens and dst.is_file():  # flat archive: tombstone keeps the old path findable
            src.write_text(f"# {src.stem} (superseded)\n\n<!-- kb: tombstone target=\"{cfg.rel(dst)}\" -->\n\n"
                           f"Moved to `{cfg.rel(dst)}` on {today()}.\n\n**Reason:** {args.reason}\n")
    if gens:
        append_row(arch / gen / "README.md", [f"`{cfg.rel(dst)[len(cfg.rel(arch / gen)) + 1:]}{'/' if dst.is_dir() else ''}`",
                                              args.by or "—",
                                              args.reason, today()],
                   f"# Archive generation {gen}\n\n| file | superseded by | reason | date |\n|---|---|---|---|\n")
    else:
        append_row(arch / "INDEX.md", [today(), moved, args.reason], "| date | original | reason |\n|---|---|---|\n")
    print(f"archived {moved} → {cfg.rel(dst)}" + (f" (no --generation given: `{gen}`)" if gens and not args.generation else ""))
    if not args.section:
        for r in readers(cfg, rel):
            print(f"relink: {r} still cites `{rel}`")


def cmd_log(args) -> None:
    cfg = find_cfg()
    wl = cfg.require("worklog", "genome log")
    sig = f" · `{args.agent}`" if args.agent else ""
    if args.body_file:  # a session entry is a page of markdown, not an argv string
        args.body = sys.stdin.read() if args.body_file == "-" else (read(Path(args.body_file)) or die(f"empty or missing {args.body_file}"))
    if worklog_numbered(cfg):
        if not args.entry:
            die("numbered worklog: `genome log \"<title>\"` creates the next file")
        with Guarded(wl / ".genome-log"):  # two sessions logging at once must not share a number
            nums = [int(re.match(r"\d+", f.name).group(0)) for f in worklog_files(cfg)]
            width = cfg.get("core", "worklog_width", 4)
            n = f"{max(nums, default=0) + 1:0{width}d}"
            p = wl / f"{n}-{today()}-{slugify(args.entry, 50)}.md"
            with open(p, "x") as f:
                f.write(f"# {n} — {today()} — {args.entry}{sig}\n\n" + (args.body + "\n" if args.body else ""))
            emit_worklog_index(cfg)
        print(cfg.rel(p))
        return
    with Guarded(wl):
        wl.parent.mkdir(parents=True, exist_ok=True)
        with open(wl, "a") as f:
            f.write(f"- **{now()}**{sig} — {args.entry}\n")
    print(f"worklog: appended ({cfg.rel(wl)})")


def cmd_handoff(args) -> None:
    cfg = find_cfg()
    head = sh(cfg.root, "git", "rev-parse", "HEAD").strip() or "(not a git repo)"
    br = sh(cfg.root, "git", "rev-parse", "--abbrev-ref", "HEAD").strip()
    dirty = sh(cfg.root, "git", "status", "--short").strip()
    open_rows = [f"  - [{r[1]}] {r[0]}: {r[2][:80]}" for r in (register_rows(cfg) or [] if cfg.has("register") else [])
                 if len(r) > 2 and r[1] in ("open", "in-progress", "blocked")]
    tail = read(cfg.path("worklog")).splitlines()[-5:] if cfg.has("worklog") and cfg.path("worklog").is_file() else []
    out = [f"## Handoff — {today()}", "", f"Repo branch `{br}`, HEAD `{head}`."
           + (f" Working tree dirty ({len(dirty.splitlines())} paths)." if dirty else " Tree clean."),
           "", "## Open register rows", *(open_rows or ["  (none)"]), "", "## Recent worklog",
           *(tail or ["  (see the worklog directory)"]), "", "Regenerate with `genome handoff --write`."]
    if args.write:  # only the generated zone: curated prose in the state doc is never overwritten
        state = cfg.require("state", "genome handoff --write")
        write_zone(state, "handoff", "\n".join(out))
        print(f"wrote zone `handoff` in {cfg.paths['state']}")
    else:
        print("\n".join(out))


def cmd_q(args) -> None:
    """Operator questions and rulings: asked → ruled → applied to the owner."""
    cfg = find_cfg()
    p = cfg.require("asks", "genome q")
    if args.q_cmd == "add":
        text = " ".join([args.id or ""] + args.text).strip() or die("q add needs the question text")
        with Guarded(p):
            qid = next_id(p, "Q")
            append_row(p, [qid, today(), "open", text, "—", "—"], ASKS_TPL)
        print(f"{qid} open — ask the operator; `genome q rule {qid} \"<ruling>\" --applied <path>` records the answer")
    elif args.q_cmd in ("rule", "apply", "withdraw"):
        with Guarded(p):
            r = list(find_row(p, args.id) or die(f"no ask `{args.id}`"))
            r += ["—"] * (6 - len(r))
            if args.q_cmd == "rule":
                r[2], r[4] = "ruled", " ".join(args.text)
            if args.q_cmd == "withdraw":
                r[2] = "withdrawn"
            for a in args.applied or []:
                if not (cfg.root / a).exists():
                    die(f"applied-to path does not exist: {a}")
                r[5] = (r[5].strip("— ") + f" `{a}`").strip()
            replace_row(p, args.id, r)
        print(f"{args.id}: {r[2]}" + ("" if r[5] not in ("", "—") else " — not yet applied to an owner (genome q apply)"))
    else:
        for r in rows(p):
            if not args.open or r[2] == "open" or (r[2] == "ruled" and r[5] in ("", "—")):
                print(" | ".join(r))


