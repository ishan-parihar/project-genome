# ---------------------------------------------------------------- sections / ask

def sections(path: Path) -> list[tuple[str, int, int, str]]:
    """(heading, start, end, body) per markdown section; code fences respected, generated zone bodies blanked."""
    return md_sections(blank_zones(read(path)), path.name)


def stem(t: str) -> str:
    """Crude suffix folding so quote/quoted/quotes and figure/figures meet."""
    for suf in ("ations", "ation", "ances", "ance", "ences", "ence", "ings", "ing", "ies", "ied", "ed", "es", "s"):
        if len(t) >= len(suf) + 3 and t.endswith(suf):  # adding → add, quoted → quot
            t = t[:-len(suf)] + ("y" if suf in ("ies", "ied") else "")
            break
    return t[:-1] if len(t) > 4 and t.endswith("e") else t


def toks(s: str) -> set[str]:
    # short ids with a digit (V1, H1, A28, C0) are the handles of research docs: keep them
    # two-letter upper-case acronyms (AI, ML, DB) are terms too
    return {stem(t.lower().strip(".-_")) for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]*", s)
            if len(t) >= 3 or re.search(r"\d", t) and re.search(r"[A-Za-z]", t) or len(t) == 2 and t.isalpha() and t.isupper()} - STOP


def chunks(path: Path) -> list[tuple[str, int, int, str]]:
    """Sections, with long ones split at bold lead lines (or every 25 lines), so
    `ask` can point at a narrow line range instead of a 200-line section."""
    out = []
    for h, a, b, body in sections(path):
        lines = body.splitlines()
        if len(lines) <= 30:
            out.append((h, a, b, body))
            continue
        cand = [i for i, ln in enumerate(lines) if i and re.match(r"\s*(?:[-*]\s+)?\*\*[^*]{3,}\*\*", ln)]
        cand = sorted(set(cand + list(range(25, len(lines), 25))))
        cuts = [0]
        for c in cand:  # a lead line with its first sub-points: never a one-line hit
            if c - cuts[-1] >= MIN_CHUNK:
                cuts.append(c)
        bold = set(cand) - set(range(25, len(lines), 25))
        for i, c in enumerate(cuts):
            e = cuts[i + 1] if i + 1 < len(cuts) else len(lines)
            if not "".join(lines[c:e]).strip():
                continue  # a blanked zone
            # every lead merged into this chunk keeps its lead weight, not only the first
            leads = [lines[j].strip().strip("-* ")[:60] for j in range(c, e) if j in bold or (j == c and c)]
            lead = " · ".join(leads)
            out.append((f"{h} › {lead}" if lead else h, a + c, a + e - 1, "\n".join(lines[c:e])))
    return out


def listed_docs(cfg: Cfg) -> list[Path]:
    """Docs the ownership map (or the agent contract) points at."""
    out: dict[Path, Path] = {}
    for role in ("ownership_map", "agents", "entry"):
        if cfg.has(role):
            for _, t in pointers(read(cfg.path(role)), set()):
                p = cfg.root / t
                if p.is_file() and p.suffix == ".md":
                    out.setdefault(p.resolve(), p)
    return list(out.values())


def corpus(cfg: Cfg) -> list[Path]:
    files = [cfg.path(r) for r in DEFAULT_PATHS if cfg.form(r)[0] == "file" and cfg.path(r).is_file()
             and cfg.path(r).suffix == ".md"]
    files += listed_docs(cfg) + [cfg.root / p for p in cfg.get("core", "living_plans", [])]
    files += cfg.globs(cfg.get("core", "ask_globs", []))
    if "records" in cfg.modules:
        files += [r["path"] for r in records(cfg)]
    seen, out = set(), []
    for f in files:
        k = f.resolve()
        if k not in seen and f.is_file() and f.stat().st_size < 1_500_000 and not is_archived(cfg, cfg.rel(f)):
            seen.add(k)
            out.append(f)
    return out


def ask_rank(cfg: Cfg, question: str, k: int = 6) -> list[tuple[float, Path, str, int, int, str]]:
    q = toks(question)
    secs = [(f, *s) for f in corpus(cfg) for s in chunks(f)]
    df: dict[str, int] = {}
    stoks = []
    for f, h, a, b, body in secs:
        head, _, lead = h.partition(" › ")  # a chunk's lead line is body text, not a heading
        ht, lt, bt, pt = toks(head), toks(lead), toks(body), toks(cfg.rel(f).replace("/", " "))
        stoks.append((ht, lt, bt, pt))
        for t in q & (ht | bt):
            df[t] = df.get(t, 0) + 1
    n = max(len(secs), 1)
    scored = []
    for (f, h, a, b, body), (ht, lt, bt, pt) in zip(secs, stoks):
        s = sum(math.log(n / (1 + df.get(t, 0))) * (3 * (t in ht) + 1.5 * (t in lt) + (t in bt) + (t in pt)) for t in q)
        if re.search(r"\b[A-Z]+-(AD|RG)-\d+\b|\b(AD|RG)-\d+\b", question):
            s += 50 * any(i in body or i in h for i in re.findall(r"\b(?:[A-Z]+-)?(?:AD|RG)-\d+\b", question))
        if s > 0:
            scored.append((s, f, h, a, b, body))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]


def cmd_ask(args) -> None:
    cfg = find_cfg()
    q = " ".join(args.question)
    route = [(r[0], r[1]) for r in rows(cfg.path("agents")) if len(r) > 1 and len(toks(q) & toks(r[0])) >= 2] if cfg.has("agents") else []
    if args.all:  # across every repo that has published a card
        hits_ = cards_ask(q, args.k, cfg)
        if args.json:
            jprint({"question": q, "hits": hits_})
            return
        for h in hits_:
            print(f"{h['score']:5.1f}  {h['pointer']}  {h['where']}  § {h['match']}")
        if not hits_:
            print(f"ask --all: no card matches in {cards_dir(cfg)} — `genome federate` at the meta root builds them")
        return
    ents: list[dict] = []
    if args.index or cfg.get("core", "ask_index", False):  # BM25 from the rebuildable index; also finds entities
        hits, ents = index_ask(cfg, q, args.k)
    else:
        hits = ask_rank(cfg, q, args.k)
    if args.json:
        jprint({"question": q, "routing": [{"question": a, "answer": b} for a, b in route], "entities": ents,
                "hits": [{"score": round(s, 1), "path": cfg.rel(f), "start": a, "end": b, "heading": h}
                         for s, f, h, a, b, _ in hits]})
        return
    for a, b in route:  # routing-table rows whose question cell matches
        print(f"routing  {a[:70]} → {b[:90]}")
    for e in ents:
        print(f"entity  {e['id']}  [{e['kind']}] {e['title'][:80]}  ({e['score']})  → `genome show {e['id']}`")
    if not hits and not ents:
        print("ask: no section matches — try other words, or `genome ask --k 12`")
        return
    qt = toks(q)
    for s, f, h, a, b, _ in hits:
        head, _, leads = h.partition(" › ")
        if leads:  # show the merged lead the question matched, not merely the first
            h = f"{head[:50]} › " + max(leads.split(" · "), key=lambda ld: len(qt & toks(ld)))
        print(f"{s:6.1f}  {cfg.rel(f)}:{a}-{b}  § {h[:100]}  ({b - a + 1} lines)")
    if args.show:
        _, f, h, a, b, body = hits[0]
        lines = body.splitlines()
        print(f"\n--- {cfg.rel(f)}:{a}-{b} ---")
        print("\n".join(lines[:args.show]))
        if len(lines) > args.show:
            print(f"... {len(lines) - args.show} more lines (Read {cfg.rel(f)} offset {a + args.show})")


