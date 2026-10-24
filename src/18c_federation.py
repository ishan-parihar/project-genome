# ---------------------------------------------------------------- federation, drift, upgrade

# Each repo keeps its own genome. A card is one small JSON summary of it, written to a cache outside the repo;
# the meta root reads cards instead of walking repos. Nothing here writes into a peer repo.

CARD_SCHEMA = 1
CARD_CLASSES = ("intent", "architecture", "operate", "decisions", "status", "offer")
CARD_BUDGET = 24_000  # bytes: a card must fit a session's context
SECRET_SHAPES = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}|\b(?:sk|pk|ghp|gho|glpat|xox[bap])[-_][A-Za-z0-9_-]{16,}|"
                           r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b")


def cards_dir(cfg: Cfg | None = None) -> Path:
    v = os.environ.get("GENOME_CARDS") or (cfg.get("federation", "cache") if cfg else None) or "~/.cache/genome/cards"
    return Path(v).expanduser()


ROLE_FORMS = ("overlay:", "native:")

CLASS_ROLES = {
    "intent": "readme",
    "operate": "runbook",
    "decisions": "records_index",
    "status": "state",
}
# a class with no role of its own falls back to the agent contract, which every repo has:
# the intent is what it says it is, the architecture is how it says it is built
CLASS_FALLBACK = {"intent": ("agents", ""), "architecture": ("agents", "Architecture")}


def role_form_path(cfg: Cfg, raw: str) -> str:
    """The file a role form names, when it names one this repo actually has.

    A role may be written as `overlay:<path>` or `native:<path>` to say the answer
    lives outside the distributed tree, or `native:<prose>` when the answer is a
    description rather than a file. Only the file form resolves to a doc; a prose
    form resolves to nothing, and the class stays empty because there is no
    document to point at.
    """
    for prefix in ROLE_FORMS:
        if not raw.startswith(prefix):
            continue
        tail = raw[len(prefix):].split(" ", 1)[0].strip()
        if tail and (cfg.root / tail).exists():
            return tail
        return ""
    return raw


def card_class_path(cfg: Cfg, cls: str) -> str:
    """Where a doc class lives: [card] override, else the role that answers it."""
    v = cfg.get("card", cls)
    if v:
        return v
    role = CLASS_ROLES.get(cls)
    if role and role in cfg.paths:
        raw = cfg.paths[role]
        if raw.startswith(ROLE_FORMS):        # a role form names a doc this repo may hold
            return role_form_path(cfg, raw)
        if (cfg.root / raw.split("#", 1)[0]).exists():
            return raw
    fb = CLASS_FALLBACK.get(cls)
    if fb and fb[0] in cfg.paths:
        raw = cfg.paths[fb[0]]
        if not raw.startswith(ROLE_FORMS) and (cfg.root / raw.split("#", 1)[0]).exists():
            return f"{raw}#{fb[1]}" if fb[1] else raw
    return ""


def head_sha(cfg: Cfg, short: bool = True) -> str:
    return sh(cfg.root, "git", "rev-parse", *(["--short"] if short else []), "HEAD").strip()


def purpose_of(cfg: Cfg) -> str:
    if cfg.get("card", "purpose"):
        return cfg.get("card", "purpose")
    for role, heading in (("agents", "What this project is"), ("readme", "")):
        if not cfg.has(role):
            continue
        text = read(cfg.path(role))
        if heading and heading.lower() in text.lower():
            text = text[text.lower().index(heading.lower()):].partition("\n")[2]
        for para in re.split(r"\n\s*\n", text):
            para = " ".join(para.split())
            if len(para) > 40 and not para.startswith(("#", "|", "```", "<", "---", "![", "[!")):
                return para[:300]
    return ""


def manual_docs(cfg: Cfg) -> list[tuple[Path, list[str], str]]:
    """(doc, covers, verified) for every doc that declares `covers` in its front-matter."""
    pats = cfg.get("drift", "paths", ["**/README.md", "**/AGENTS.md", "docs/**/*.md"])
    out = []
    for rel in sorted(x for x in tracked(cfg) if x.endswith(".md") and any(gmatch(x, g, cfg) for g in pats)):
        f = cfg.root / rel
        fm = frontmatter(read(f)[:4000])
        if fm.get("covers"):
            out.append((f, [c.strip().strip('"\'') for c in re.split(r"[,\[\]]", fm["covers"]) if c.strip().strip('"\'')], fm.get("verified", "")))
    return out


def stale_files(cfg: Cfg, covers: list[str], verified: str) -> list[str] | None:
    """Paths under `covers` changed between `verified` and HEAD; None when the sha is unknown to git."""
    if not sh(cfg.root, "git", "cat-file", "-t", verified).strip().startswith("commit"):
        return None
    return sh(cfg.root, "git", "diff", "--name-only", f"{verified}..HEAD", "--", *[f":(glob){c}" for c in covers]).split()


def lint_drift(cfg: Cfg) -> list[str]:
    """W401/E401 a manual's covered code changed since it was verified · W402 no verified sha · W403 sha unknown · W404 covers matches nothing."""
    if not is_git(cfg):
        return []
    sev = "E" if cfg.get("drift", "mode", "warn") == "error" else "W"
    until = cfg.get("drift", "warn_until", "")  # nested plan decision 4: after the window, a repo with a gate blocks close
    if sev == "W" and until and cfg.get("core", "gate") and dt.date.today().isoformat() > str(until):
        sev = "E"
    out, files = [], tracked(cfg)
    for f, covers, verified in manual_docs(cfg):
        rel = cfg.rel(f)
        if not any(gmatch(x, c, cfg) for c in covers for x in files):
            out.append(f"W404 {rel} covers {covers}, which match no tracked file (a typo, or the code moved)")
            continue
        if not verified:
            out.append(f"W402 {rel} declares covers but no `verified` sha — after reviewing it, run `genome verify {rel} --reviewed`")
            continue
        changed = stale_files(cfg, covers, verified)
        if changed is None:
            out.append(f"W403 {rel}: verified sha {verified} is not in this repository's history")
        elif changed:
            out.append(f"{sev}401 {rel} is stale: {len(changed)} covered path(s) changed since {verified} "
                       f"({', '.join(changed[:3])}{' …' if len(changed) > 3 else ''}) — review, then `genome verify {rel} --reviewed`")
    return out


def cmd_verify(args) -> None:
    """Record that a person or agent has compared this manual with the code it covers, at the current HEAD."""
    cfg = find_cfg()
    if not args.reviewed:
        die("verify records that you read the manual against its covered code: pass --reviewed once you have")
    p = (cfg.root / args.doc) if not Path(args.doc).is_absolute() else Path(args.doc)
    if not p.is_file():
        die(f"{args.doc} is not a file")
    fm = frontmatter(read(p))
    if not fm.get("covers") and not args.covers:
        die(f"{args.doc} has no `covers` front-matter: pass --covers 'glob, glob' to declare what it describes")
    sha = args.sha or head_sha(cfg)
    if not sha:
        die("verify records a commit: commit the manual and the code it covers first, then verify")
    fields = {"verified": sha}
    if args.covers:
        fields["covers"] = args.covers
    atomic_write(p, set_front(read(p), fields))
    print(f"{cfg.rel(p)}: verified {sha}")


def register_summary(cfg: Cfg) -> tuple[dict[str, int], list[dict]]:
    rs = register_rows(cfg) if cfg.has("register") else None
    counts: dict[str, int] = {}
    openr = []
    for r in rs or []:
        if len(r) > 2 and r[1] in STATUS_VOCAB:
            counts[r[1]] = counts.get(r[1], 0) + 1
            if r[1] in ("open", "in-progress", "blocked"):
                openr.append({"id": r[0], "status": r[1], "item": r[2][:100]})
    return counts, openr


def build_card(cfg: Cfg) -> dict:
    """The card: built from the working tree, never from git history; read-only."""
    privacy = cfg.get("card", "privacy", "internal")
    classes = {}
    for c in CARD_CLASSES:
        v = card_class_path(cfg, c)
        classes[c] = {"path": v, "exists": bool(v) and (cfg.root / v.split("#")[0]).exists()}
    heads = {}
    for c, d in classes.items():
        f = cfg.root / d["path"].split("#")[0] if d["exists"] else None
        if f and f.is_file() and f.suffix == ".md":
            heads[c] = [(h[:70], a) for h, a, b, _ in sections(f) if h != f.name][:25]
    routing = [[r[0][:90], r[1][:90]] for r in rows(cfg.path("agents")) if len(r) > 1][:40] if cfg.has("agents") else []
    counts, openr = register_summary(cfg)
    lint = run_lint(cfg)
    errs = sum(1 for x in lint if x.startswith("E"))
    kinds = {}
    if cfg.kinds and privacy != "local":
        ents, _ = load_entities(cfg)
        for e in ents.values():
            kinds.setdefault(e["kind"], {}).setdefault(e["state"], 0)
            kinds[e["kind"]][e["state"]] += 1
    manuals = []
    for f, covers, verified in manual_docs(cfg):
        ch = stale_files(cfg, covers, verified) if verified and is_git(cfg) else None
        manuals.append({"path": cfg.rel(f), "covers": covers, "verified": verified, "stale": bool(ch)})
    comps = [{"name": Path(c).name, "path": c} for g in cfg.get("card", "components", []) for c in
             sorted(cfg.rel(p) for p in cfg.root.glob(g) if p.is_dir())][:60]
    card = {"schema": CARD_SCHEMA, "name": cfg.root.name, "root": str(cfg.root), "genome": VERSION, "head": head_sha(cfg),
            "built": now(), "privacy": privacy, "purpose": purpose_of(cfg), "modules": sorted(cfg.modules),
            "classes": classes, "headings": heads, "routing": routing, "components": comps,
            "register": {"counts": counts, "open": openr[:30]}, "kinds": kinds, "manuals": manuals,
            "records": [{"id": r["id"], "title": r["title"][:80]} for r in (records(cfg)[:50] if "records" in cfg.modules else [])],
            "health": {"errors": errs, "warnings": len(lint) - errs}}
    return card


def card_problems(card: dict, cfg: Cfg) -> list[str]:
    text = json.dumps(card, ensure_ascii=False)
    out = [f"secret-shaped string in the card ({m.group(0)[:12]}…)" for m in SECRET_SHAPES.finditer(text)][:3]
    out += [f"a configured secret value from {spec} appears in the card" for spec, v in secret_values(cfg) if v in text]
    if len(text.encode()) > CARD_BUDGET:
        out.append(f"card is {len(text.encode())} bytes, over the {CARD_BUDGET} budget — trim [card] components or the register")
    return out


def card_key(cfg: Cfg, taken: set[str] | None = None) -> str:
    """The cache filename's stem: the directory name, disambiguated by its path only when it collides.

    F6 was that two members with the same directory name (`work/alpha/logbook` and
    `work/beta/logbook`) slugified to one name and therefore one file, so the second silently replaced
    the first. That is not cosmetic: `ask` and `resolve` then answered for a repo that was not a member
    at all, and `prune_cards` could not see the overwrite because the surviving card's `root` existed.

    The cache is read by people too, so a plain hash or a full absolute path is the wrong key: the
    shipped test suite asserts `cache/alpha.json`, and `genome resolve` prints these names back. So
    the directory name stays the stem, and the parent path is appended only for the second and later
    members that collide with an earlier one. Unambiguous names are unchanged; ambiguous ones become
    `alpha-logbook`, `beta-logbook` and stay readable.

    `taken` is the set of stems already claimed this run, so the second colliding member sees the
    first one's claim and disambiguates. Without it every member would disambiguate against itself."""
    base = slugify(cfg.root.name, 80)
    if taken is None:
        return base
    if base not in taken:
        taken.add(base)
        return base
    # a collision: keep the name and add enough of the parent path to be unique, closest parent first
    parts = list(cfg.root.resolve().parts)
    for depth in range(2, min(len(parts), 6) + 1):
        cand = base + "-" + slugify("-".join(parts[-depth:-1]), 100 - len(base) - 1)
        if cand not in taken:
            taken.add(cand)
            return cand
    taken.add(base)
    return base


def write_card(cfg: Cfg, to: Path | None = None, taken: set[str] | None = None) -> tuple[Path | None, list[str]]:
    if cfg.get("card", "privacy") == "local":
        return None, ["privacy = local: this genome publishes no card"]
    card = build_card(cfg)
    probs = card_problems(card, cfg)
    if probs:
        return None, probs
    # `to` is already absolute when `federate` passes its cache, so this branch is `genome card`
    # run by hand with a relative --out, or a relative [federation] cache used outside federate. It is
    # resolved against the CWD, never against cfg.root: federate chdirs into each member before
    # building its card, so rooting it at cfg.root would write the cache inside whichever member ran
    # last. mkdir the parent too - `.genome/cards` needs `.genome` first, and mkdir on the leaf alone
    # raises a bare FileNotFoundError traceback instead of a message.
    d = to or cards_dir(cfg)
    if not d.is_absolute():
        d = Path.cwd().resolve() / d
    d.parent.mkdir(parents=True, exist_ok=True)
    d.mkdir(parents=True, exist_ok=True)
    key = card_key(cfg, taken)
    out = d / f"{key}.json"
    atomic_write(out, json.dumps(card, ensure_ascii=False, indent=1) + "\n")
    return out, []


def cmd_card(args) -> None:
    cfg = find_cfg()
    if args.stdout:
        jprint(build_card(cfg))
        return
    out, probs = write_card(cfg, Path(args.out).expanduser() if args.out else None)
    if probs:
        die("card not written: " + "; ".join(probs), ERR)
    print(f"card: {out} ({out.stat().st_size} bytes)")


def federation_repos(cfg: Cfg) -> list[Path]:
    """The federation's members: every directory the globs reach that holds a genome,
    minus the ones the operator excludes by name.

    Membership would otherwise be an accident of how deep a directory sits: a glob
    that reaches one level too deep also reaches a fixture. `[federation] exclude`
    names the directories to skip, so membership is a decision.
    """
    seen = []
    skip = set(cfg.get("federation", "exclude", []))
    for g in cfg.get("federation", "repos", ["*", "*/*"]):
        for d in sorted(cfg.root.glob(g)):
            if d.is_dir() and d != cfg.root and (d / "genome.toml").is_file() and d not in seen \
                    and not any(x in d.relative_to(cfg.root).parts for x in HEAVY_DIRS | skip):
                seen.append(d)
    return seen


def prune_cards(cache: Path) -> list[str]:
    """Delete the cards whose repo is gone: a card for a directory that no longer exists keeps
    answering questions and outranks the live repos it was meant to point at.

    Only a card whose recorded `root` is missing is removed; a card whose root exists is left
    alone even if the repo is no longer a member (it may be excluded, or a peer may still hold it).
    """
    gone = []
    for p in sorted(cache.glob("*.json")):
        try:
            card = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        root = card.get("root")
        if root and not Path(root).is_dir():
            p.unlink()
            gone.append(card.get("name") or p.stem)
    return gone


def cmd_federate(args) -> None:
    """Build every member's card into the cache (reading each tree, writing none) and refresh the portfolio zone."""
    cfg = find_cfg()
    cache = cards_dir(cfg).expanduser().resolve()  # absolute: federate chdirs into each member below
    rows_, skipped = [], []
    taken: set[str] = set()  # stems claimed this run, so a same-named member disambiguates
    here = Path.cwd()
    for d in federation_repos(cfg):
        try:
            os.chdir(d)
            sub = find_cfg(d)
            out, probs = write_card(sub, cache, taken)
        except SystemExit:
            skipped.append(f"{d.name}: unreadable genome")
            continue
        finally:
            os.chdir(here)
        if probs:
            skipped.append(f"{d.name}: {'; '.join(probs)}")
            continue
        c = json.loads(out.read_text())
        rows_.append(c)
    gone = prune_cards(cache)
    # A card left under an older keying: its stem is one this run claimed but did not write
    # (the first member of a colliding pair took the plain name under the old keying, and the second
    # now writes `beta-logbook`, leaving `logbook` behind). Reported, never deleted: the cache is
    # global and another meta root's cards are not ours to judge. Scoped to stems we ourselves claim,
    # so a stranger's card is never misreported as our leftover.
    written = {p.stem for p in cache.glob("*.json")}
    stale_keys = sorted(s for s in taken if s not in written)
    into = cfg.get("federation", "status_into")
    if into and rows_:
        body = "| repo | genome | lint | open items | purpose |\n|---|---|---|---|---|\n"
        for c in sorted((c for c in rows_ if c["privacy"] != "private"), key=lambda c: c["name"]):  # private repos stay in the cache
            h = c["health"]
            body += (f"| {c['name']} | {c['genome']} | {h['errors']}E {h['warnings']}W | {len(c['register']['open'])} | "
                     f"{c['purpose'][:90].replace('|', '/')} |\n")
        path, _, zone = into.partition("#")
        write_zone(cfg.root / path, zone or "portfolio", body)
    print(f"federate: {len(rows_)} card(s) in {cache}" + (f"; skipped {len(skipped)}" if skipped else "")
          + (f"; pruned {len(gone)} stale card(s): {', '.join(gone)}" if gone else "")
          + (f"; left from an earlier keying: {', '.join(stale_keys)} — `genome federate` no longer writes those names, "
             f"remove them if they are not wanted" if stale_keys else ""))
    for s in skipped:
        print(f"  skipped {s}")


def load_cards(cfg: Cfg | None = None, members: bool = False) -> list[dict]:
    """Every card in the cache, sorted by filename.

    `members=True` drops the cards that are not reachable from THIS cfg: cards whose root is another
    meta root's member, or a directory that moved on. Without it the cache is global, so a card left
    behind by an earlier glob, or by another root entirely, still answers questions and outranks the
    live repos it was meant to point at.

    It deliberately does NOT mean "federate wrote it this run". A meta root's own card is written by
    `genome card` in that root and is not a member of its own federation - it answers from its own
    repo - and the offer class only resolves there. So the roots kept are the federation's members
    PLUS the federating root itself.

    When two files describe the same repo - the path-keyed one and a name-keyed one an older
    `federate` wrote before collisions were disambiguated - the newer wins and the older is dropped
    here rather than ranked alongside it. Both pass the membership test, so only the `built` stamp
    tells them apart, and showing both would answer twice for one repo."""
    d = cards_dir(cfg)
    if not d.is_dir():
        return []
    cards = []
    for p in sorted(d.glob("*.json")):
        try:
            cards.append(json.loads(p.read_text()))
        except (OSError, ValueError):
            continue
    if members and cfg is not None:
        roots = {str(p.resolve()) for p in federation_repos(cfg)} | {str(Path(cfg.root).resolve())}
        cards = [c for c in cards if str(Path(c["root"]).resolve()) in roots]
    by_root: dict[str, dict] = {}
    for c in sorted(cards, key=lambda c: (c.get("built", ""), c.get("name", ""))):
        by_root[str(Path(c["root"]).resolve())] = c
    return sorted(by_root.values(), key=lambda c: c.get("name", ""))


# A question that names a doc class is answered with that class's document.
#
# Why this is needed: a routing row's own question text ("where does the project stand right now")
# matches a natural-language question far better than a class heading does, and the routing row
# scores 2.5 against the class headings' 1.5. So the federation answered "how is it built" with a
# routing row instead of the architecture document the card already points at. The class map was
# right and the ranking was answering something else. Routing is not weakened here; the class
# question reaches the class.
CLASS_INTENT_WORDS = {
    "intent": {"purpose", "overview"},
    "architecture": {"architectur", "built", "structur", "design", "component", "layout", "blueprint"},
    "operate": {"run", "operat", "deploy", "install", "build", "test", "usag", "command", "setup", "configur"},
    "decisions": {"decid", "ration", "reason", "choic", "chosen"},
    "status": {"stand", "status", "stat", "progress", "today", "current"},
    # the offer class is opt-in: no role, no fallback, so it resolves only where [card] offer points at a doc.
    # Ventures carry no offers; the meta root points the class at its proof/evidence documents.
    "offer": {"offer", "price", "pricing", "fee", "rate"},
}
# the question words that are stop words in the tokenizer ("how", "why", "where") are matched as phrases
CLASS_INTENT_PHRASES = {
    "intent": ("what is", "what does", "what are"),
    "architecture": ("how is", "how does", "how it works"),
    "operate": ("how do i", "how to"),
    "decisions": ("why was", "why is", "why did", "why were"),
    "status": ("where does", "where is"),
    "offer": ("what should we offer", "what should i offer", "what can we sell"),
}
# the order a tie is broken in: the more specific class wins, intent last
CLASS_PRIORITY = ("offer", "architecture", "decisions", "status", "operate", "intent")


def class_intent(question: str) -> str | None:
    """The doc class a question names, or None when it names none.

    "how is it built" names architecture, "why was it decided" names decisions, "where does it
    stand" names status, "how do I run it" names operate, "what is this" names intent. A word
    match counts double against a phrase match, so one specific word ("status") beats a generic
    phrase ("what is"); a tie goes to the more specific class.
    """
    q = question.lower()
    words = toks(question)
    best, best_score = None, 0
    for cls in CLASS_PRIORITY:
        w = len(CLASS_INTENT_WORDS.get(cls, set()) & words)
        p = sum(1 for ph in CLASS_INTENT_PHRASES.get(cls, ()) if re.search(r"\b" + re.escape(ph) + r"\b", q))
        s = 2 * w + p
        if s > best_score:
            best, best_score = cls, s
    return best


def class_pointer(card: dict, cls: str) -> tuple[str, str]:
    """Where a class's document is and what to call it: the path, plus the heading that anchors it."""
    raw = card["classes"][cls]["path"]
    path, _, anchor = raw.partition("#")
    heads = card.get("headings", {}).get(cls) or []
    if anchor:
        for h, ln in heads:
            if h.strip().lower() == anchor.strip().lower():
                return f"{path}:{ln}", h
    if heads:
        return f"{path}:{heads[0][1]}", heads[0][0]
    return path, path


def cards_ask(question: str, k: int, cfg: Cfg | None = None) -> list[dict]:
    """Repos ranked by how many question terms their card covers (idf across repos, field-weighted), each with the
    best-matching item as the pointer. Coverage beats repetition: a term found ten times counts once.

    A question that names a doc class is answered with that class's document, whatever the term
    coverage says: the class map is what the portfolio indexed, so it is what the answer points at."""
    q = toks(question)
    cards = [c for c in load_cards(cfg, members=True) if c.get("privacy") != "local"]
    # Keyed on the card's root, not its name: two members may share a directory name
    # (`work/alpha/logbook` and `work/beta/logbook`), and keying on the name silently merged them into
    # one ranking row while still emitting a hit per card - the same collision the file keying had, one
    # layer down. The path is unique per repo; `repo` in a pointer stays the name, because that is what
    # a person types.
    items: dict[str, list[tuple[float, set[str], str, str, str]]] = {}
    for c in cards:
        it = [(3.0, toks(c["purpose"]), "purpose", "", c["purpose"]), (4.0, toks(c["name"].replace("-", " ")), "name", "", c["name"])]  # own name outranks a mention in another purpose
        it += [(2.5, toks(f"{a} {b}"), "operate" if "run" in b.lower() else "routing", b, a) for a, b in c["routing"]]
        for cls, hs in c["headings"].items():
            it += [(1.5, toks(h), cls, f"{c['classes'][cls]['path'].split('#')[0]}:{ln}", h) for h, ln in hs]
        it += [(1.0, toks(r["item"]), "register", r["id"], r["item"]) for r in c["register"]["open"]]
        it += [(1.0, toks(r["title"]), "decisions", r["id"], r["title"]) for r in c["records"]]
        items[str(Path(c["root"]).resolve())] = it
    df = {t: sum(any(t in x[1] for x in it) for it in items.values()) for t in q}
    n = max(len(cards), 1)
    named = class_intent(question)
    hits = []
    for c in cards:
        it = items[str(Path(c["root"]).resolve())]
        score = sum(math.log(1 + n / (1 + df[t])) * max((w for w, ts, *_ in it if t in ts), default=0) for t in q)
        if score <= 0:
            continue
        if named and c["classes"].get(named, {}).get("exists"):
            cls = named
            where, text = class_pointer(c, cls)
        else:
            w, ts, cls, where, text = max(it, key=lambda x: (len(q & x[1]), x[0]))
            if cls == "name":
                cls = "intent"
        hits.append({"score": round(score, 1), "repo": c["name"], "root": c["root"], "pointer": f"repo:{c['name']}#{cls}",
                     "where": where, "match": text[:100], "head": c["head"], "built": c["built"]})
    return sorted(hits, key=lambda h: (-h["score"], h["repo"], h["root"]))[:k]


def cmd_resolve(args) -> None:
    """repo:<name>#<class> → the file in that repo (from its card)."""
    m = re.fullmatch(r"repo:([\w.-]+)#(\w+)", args.pointer)
    if not m:
        die("a repo pointer looks like repo:<name>#<class>, e.g. repo:operant#architecture")
    name, cls = m.groups()
    try:
        cfg = find_cfg()
    except SystemExit:  # outside any genome: the default cache still answers
        cfg = None
    cards = [c for c in load_cards(cfg, members=True) if c["name"] == name]
    if not cards:
        die(f"no card for `{name}` in {cards_dir(cfg)} — run `genome federate` at the meta root (or `genome card` in that repo)")
    # Several members may share a directory name, and `resolve` prints one path, so it says which one
    # it picked rather than choosing silently. `--root` pins one exactly.
    if args.root:
        want = str(Path(args.root).expanduser().resolve())
        picked = [c for c in cards if str(Path(c["root"]).resolve()) == want]
        if not picked:
            die(f"`{name}` is a member at {', '.join(c['root'] for c in cards)}, not {args.root}")
        cards = picked
    c = cards[0]
    if len(cards) > 1:
        print("note: " + f"`{name}` is a member at {len(cards)} roots; showing {c['root']}. "
              + "; ".join(f"{x['root']} → `genome resolve repo:{name}#{cls} --root {x['root']}`" for x in cards[1:]))
    if cls not in c["classes"] or not c["classes"][cls]["path"]:
        die(f"{name} declares no `{cls}` document (classes: {', '.join(k for k, v in c['classes'].items() if v['path'])})")
    path = c["classes"][cls]["path"].split("#")[0]
    print(f"{Path(c['root']) / path}" + ("" if c["classes"][cls]["exists"] else "  (missing)") + f"  [card {c['built']} @ {c['head']}]")


def emit_status(cfg: Cfg) -> list[str]:
    """Generated status zone (counts from the register, never hand-kept) in the doc named by [card] status_into."""
    into = cfg.get("card", "status_into")
    if not into or not cfg.has("register"):
        return []
    counts, openr = register_summary(cfg)
    body = "| status | items |\n|---|---|\n" + "".join(f"| {s} | {counts[s]} |\n" for s in STATUS_VOCAB if s in counts)
    body += "\n" + "".join(f"- `{r['id']}` [{r['status']}] {r['item']}\n" for r in openr[:10]) if openr else ""
    path, _, zone = into.partition("#")
    return [path] if write_zone(cfg.root / path, zone or "status", body) else []


# ---- upgrade

SCHEMA_VERSION = 2
MIGRATIONS: dict[int, object] = {}  # target schema_version → fn(text) that rewrites genome.toml in place


def migrate_v2(text: str) -> str:
    """Schema 2 has one glob dialect. A slashless membership pattern matched at any depth under schema 1, so it
    gets the `**/` prefix that keeps that meaning; every other line is left as written."""
    for k in RETIRED_PATHS:
        text = re.sub(rf'^{k}\s*=[^\n]*\n', "", text, count=1, flags=re.M)
    for s, k, p in membership_problems(tomllib.loads(text)):
        text = re.sub(rf'^({re.escape(k)}\s*=\s*\[[^\]]*?)"{re.escape(p)}"',
                      lambda m: m.group(1) + f'"**/{p}"', text, count=1, flags=re.M)
    tomllib.loads(text)  # the result must still be valid TOML
    return text


MIGRATIONS[2] = migrate_v2


def apply_overrides(start: Path) -> None:
    """`.genome/overrides/<NAME>.md` replaces the built-in template text NAME (RECORDS_TPL, AGENTS_TPL, …): local
    template edits live beside the repo's config instead of in a hand-patched copy of this file."""
    for d in [start, *start.parents]:
        o = d / ".genome" / "overrides"
        if o.is_dir():
            for f in o.glob("*.md"):
                if f.stem in globals() and f.stem.endswith("_TPL") and isinstance(globals()[f.stem], str):
                    globals()[f.stem] = f.read_text()
            return
        if (d / "genome.toml").exists() or (d / "kb.toml").exists():
            return


def skill_copy() -> Path:
    return Path(os.environ.get("GENOME_SKILL", "~/.agents/skills/project-genome/scripts/genome")).expanduser()


def file_version(text: str) -> str:
    m = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    return m.group(1) if m else "?"


def cmd_upgrade(args) -> None:
    """Compare this repo's vendored CLI with the skill's copy; --apply swaps it in, keeping a backup and any local patch as a diff."""
    import difflib
    cfg = find_cfg()
    new = skill_copy()
    me = Path(__file__).resolve()
    if not new.is_file():
        die(f"no skill copy at {new} (set GENOME_SKILL)")
    mine_t, new_t = me.read_text(), new.read_text()
    if mine_t == new_t:
        print(f"genome {VERSION}: up to date")
        return
    rel = cfg.rel(me)
    print(f"{rel}: {file_version(mine_t)} → {file_version(new_t)}")
    releases = {}
    rf = new.with_name("releases.txt")
    if rf.is_file():
        releases = {ln.split()[0]: ln.split()[1] for ln in rf.read_text().splitlines() if len(ln.split()) >= 2 and not ln.startswith("#")}
    known = releases.get(VERSION)
    sha = hashlib.sha256(me.read_bytes()).hexdigest()
    patched = known is not None and not sha.startswith(known)
    if known is None:
        print(f"note: no recorded checksum for {VERSION}; cannot tell whether this copy was hand-patched")
    if patched:
        print("this copy differs from the released one: it carries a local patch. Moving a template change into "
              "`.genome/overrides/<TEMPLATE>.md` keeps it across upgrades; other edits belong in the skill.")
    if not args.apply:
        diff = list(difflib.unified_diff(mine_t.splitlines(), new_t.splitlines(), lineterm="", n=0))
        print(f"{sum(1 for d in diff if d.startswith('+') and not d.startswith('+++'))} lines added, "
              f"{sum(1 for d in diff if d.startswith('-') and not d.startswith('---'))} removed. `genome upgrade --apply` swaps it in.")
        return
    if patched and not args.accept_patch_loss:
        die("refusing: this copy has local edits that the swap would drop. Re-run with --accept-patch-loss to keep the diff "
            "at .genome/local-patch.diff and continue", ERR)
    bak = cfg.root / ".genome"
    bak.mkdir(exist_ok=True)
    (bak / "genome.pre-upgrade").write_text(mine_t)
    if patched:
        (bak / "local-patch.diff").write_text("\n".join(difflib.unified_diff(mine_t.splitlines(), new_t.splitlines(), "vendored", "skill", lineterm="")))
    atomic_write(me, new_t)
    me.chmod(0o755)
    print(f"upgraded {rel} to {file_version(new_t)} (backup: .genome/genome.pre-upgrade)")
    subprocess.run([sys.executable, str(me), "migrate"], cwd=cfg.root)  # the new code runs its own config migrations


def cmd_migrate(args) -> None:
    """Bring genome.toml to this CLI's schema_version (each migration is a function of the config text)."""
    cfg = find_cfg()
    f = cfg.root / ("kb.toml" if cfg.legacy else "genome.toml")
    text = f.read_text()
    cur = cfg.schema_version
    if cur > SCHEMA_VERSION:
        die(f"genome.toml is schema_version {cur}; this CLI knows up to {SCHEMA_VERSION} — upgrade the CLI", ERR)
    for v in range(cur + 1, SCHEMA_VERSION + 1):
        if v in MIGRATIONS:
            text = MIGRATIONS[v](text)
    if re.search(r"^schema_version\s*=", text, re.M):
        text = re.sub(r"^schema_version\s*=.*$", f"schema_version = {SCHEMA_VERSION}", text, count=1, flags=re.M)
    elif re.search(r"^\[genome\]\s*$", text, re.M):
        text = re.sub(r"^(\[genome\][^\n]*\n)", rf"\1schema_version = {SCHEMA_VERSION}\n", text, count=1, flags=re.M)
    else:
        text = f"[genome]\nschema_version = {SCHEMA_VERSION}\n\n" + text
    if text != f.read_text():
        atomic_write(f, text)
        print(f"{f.name}: schema_version {cur} → {SCHEMA_VERSION}")
    else:
        print(f"{f.name}: schema_version {SCHEMA_VERSION} (nothing to migrate)")
