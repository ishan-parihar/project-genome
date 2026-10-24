# ---------------------------------------------------------------- research commands

def figure_hits(cfg: Cfg, value: str) -> list[str]:
    out = sh(cfg.root, "git", "grep", "-n", "-F", "-e", value, "--").splitlines()
    if not out and not sh(cfg.root, "git", "rev-parse", "HEAD").strip():
        out = [f"{cfg.rel(p)}:{n}:{ln}" for p in cfg.root.rglob("*.md")
               for n, ln in enumerate(read(p).splitlines(), 1) if value in ln]
    ev = cfg.paths["evidence"].rstrip("/") + "/"
    return [h for h in out if not is_archived(cfg, h.split(":", 1)[0]) and not h.startswith(ev)]


def cmd_figure(args) -> None:
    cfg = find_cfg()
    cfg.need("research")
    hits = figure_hits(cfg, args.value)
    for h in hits:
        print(h[:200])
    print(f"figure `{args.value}`: {len(hits)} live occurrence(s) (archive and evidence store excluded)")


def cmd_quarantine(args) -> None:
    cfg = find_cfg()
    cfg.need("research")
    p = cfg.require("quarantine", "genome quarantine")
    with Guarded(p):
        append_row(p, [" ".join(f"`{f}`" for f in args.figures), args.where or "—", args.why, args.by or "—", today()],
                   QUAR_TPL)
    hist = [cfg.paths[r].rstrip("/") + ("/" if cfg.path(r).is_dir() else "") for r in APPEND_ONLY
            if cfg.form(r)[0] == "file"]
    live, past = {}, set()
    for f in args.figures:
        for h in figure_hits(cfg, f):
            loc = h.split(":", 2)
            if loc[0] == cfg.paths["quarantine"]:
                continue
            if any(loc[0] == x or (x.endswith("/") and loc[0].startswith(x)) for x in hist):
                past.add(loc[0])  # append-only history keeps what it said; the quarantine row is the correction
            else:
                live.setdefault(":".join(loc[:2]), h)
    print(f"quarantined {len(args.figures)} figure(s); strike {len(live)} live occurrence(s) now:")
    for h in live.values():
        print(f"  {h[:180]}")
    if past:
        print(f"  ({len(past)} append-only history file(s) also quote them; leave those as written)")


def cmd_hyp(args) -> None:
    cfg = find_cfg()
    cfg.need("research")
    p = cfg.require("hypotheses", "genome hyp")
    prefix = cfg.get("research", "hyp_prefix", "H")
    if not p.exists():
        atomic_write(p, HYP_TPL)
    if args.hyp_cmd == "add":
        text = " ".join([args.id or ""] + args.text).strip() or die("hyp add needs the hypothesis text")
        with Guarded(p):
            reg = Register(cfg, "hypotheses")
            hid, row = reg.next_id(prefix), ["—"] * len(reg.header)
            row[0] = hid
            for name, val in (("status", "open"), ("text", text)):
                k = reg.col(name)
                if k is None:
                    die(f"the hypotheses register has no `{name}` column ({' | '.join(reg.header)})")
                row[k] = val
            reg.write(None, row)
        print(f"{hid} open")
    elif args.hyp_cmd == "verdict":
        vocab = hyp_vocab(cfg)
        if args.status is None and args.text and args.text[0] in vocab:  # `hyp verdict H3 rejected …`
            args.status = args.text[0]
        if args.status not in vocab:
            die(f"status must be one of {vocab}")
        if args.status in HYP_TERMINAL and not (args.evidence and (cfg.root / args.evidence).exists()):
            die(f"{args.status} needs --evidence <existing path>: a verdict without its measurement is unfalsifiable")
        if args.status == "rejected" and not args.reopen and Register(cfg, "hypotheses").col("reopen") is not None:
            die("rejected needs --reopen \"<the new evidence that would re-open it>\"")
        with Guarded(p):
            reg = Register(cfg, "hypotheses")
            i, r = reg.find(args.id) or die(f"no hypothesis `{args.id}`")
            r += ["—"] * (len(reg.header) - len(r))
            r[reg.col("status")] = args.status
            k = reg.col("evidence")
            if args.evidence and k is not None:  # appended: an earlier verdict's evidence stays readable
                stamp = f"[{today()}] `{args.evidence}`" + (f" — {args.note}" if args.note else "")
                r[k] = stamp if r[k] in ("", "—") else f"{r[k]} · {stamp}"
            k = reg.col("reopen")
            if args.reopen:
                if k is None:
                    die("the hypotheses register has no re-open column; put the condition in --note")
                r[k] = args.reopen
            reg.write(i, r)
        print(f"{args.id} → {args.status}")
    else:
        reg = Register(cfg, "hypotheses")
        for r in reg.rows:
            if not args.open or status_word(reg.get(r, "status")) in ("open", "testing"):
                print(" | ".join(r))


RESULTS_RE = re.compile(rb"^#{1,6}[ \t]*(results|verdict)\b", re.I | re.M)


def spec_hashes(data: bytes) -> tuple[str, str]:
    """(spec part, whole file). The spec part ends at the first `## Results` / `## Verdict` heading, so the run's
    results can be appended to the frozen spec; the whole-file hash keeps earlier freezes valid."""
    m = RESULTS_RE.search(data)
    part = (data[:m.start()] if m else data).rstrip()  # the blank line before an appended heading is not the spec
    return hashlib.sha256(part).hexdigest()[:16], hashlib.sha256(data).hexdigest()[:16]


def cmd_prereg(args) -> None:
    cfg = find_cfg()
    cfg.need("research")
    p = cfg.require("prereg", "genome prereg")
    if args.pr_cmd == "freeze":
        spec = cfg.root / args.spec
        if not spec.is_file():
            die(f"no spec file {args.spec}")
        prior = [r for r in rows(p) if len(r) > 1 and r[1].strip("`") == cfg.rel(spec)]
        if prior and not args.reason:
            die("this spec is already frozen; re-freezing a pre-registration needs --reason (it is visible forever)")
        if args.at:  # backfill: freeze the spec as it was committed, then lint proves it has not moved since
            data = subprocess.run(["git", "show", f"{args.at}:{cfg.rel(spec)}"], cwd=cfg.root,
                                  capture_output=True).stdout or die(f"{cfg.rel(spec)} is not in commit {args.at}")
            head = sh(cfg.root, "git", "rev-parse", "--short", args.at).strip()
        else:
            data, head = spec.read_bytes(), sh(cfg.root, "git", "rev-parse", "--short", "HEAD").strip() or "—"
        sha = spec_hashes(data)[0]
        if sha != spec_hashes(spec.read_bytes())[0]:
            die(f"the spec part of {cfg.rel(spec)} changed after {args.at}: freeze it at the commit that holds its "
                "current text, or record the change with --reason")
        with Guarded(p):
            append_row(p, [today(), f"`{cfg.rel(spec)}`", f"`{sha}`", head, args.reason or args.note or "—"], PREREG_TPL)
        print(f"frozen {cfg.rel(spec)} sha {sha} at {head} — run the confirmatory test only after this commit")
    else:
        bad = [e for e in lint_research(cfg) if e.startswith("E203")]
        print("\n".join(bad) or "prereg: every frozen spec is unchanged")
        raise SystemExit(ERR if bad else 0)


