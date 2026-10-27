# ---------------------------------------------------------------- lint checks

def lint_core(cfg: Cfg) -> list[str]:
    out: list[str] = [f"E017 genome.toml: unknown key {k} (a typo here switches a check off silently)"
                      for k in cfg.unknown]
    out += lint_layout(cfg)   # root placement is a core invariant, not an ops option
    out += [f"W507 [paths] {k} is retired (no role uses it); `genome migrate` removes it" for k in RETIRED_PATHS
            if k in cfg.declared]
    if cfg.schema_version < 2:  # the one-dialect change: say what `genome migrate` will rewrite
        out += [f"W506 [{s}] {k}: `{p}` matches at any depth on schema_version {cfg.schema_version}; "
                f"`genome migrate` writes `**/{p}`" for s, k, p in membership_problems(cfg.sec)]
    names = tracked(cfg)
    ign = cfg.ignore()
    # agent contract pointers
    if cfg.has("agents"):
        text = read(cfg.path("agents"))
        for n, t in pointers(text, ign):
            if not pointer_exists(cfg, t, names):
                out.append(f"E001 {cfg.paths['agents']}:{n} points at missing `{t}`")
            elif "/" in t and (cfg.root / t).is_file() and TOMBSTONE.search(read(cfg.root / t)):
                out.append(f"E005 {cfg.paths['agents']}:{n} points at a tombstone `{t}`")
    elif cfg.form("agents")[0] == "file":
        out.append("W000 no agent contract (AGENTS.md) — the entry point for every future agent")
    # register
    if cfg.has("register"):
        reg_rows = register_rows(cfg)
        if reg_rows is None:
            out.append(f"E001 register {cfg.paths['register']}: no heading `{cfg.paths['register'].partition('#')[2]}` in the file")
        for r in reg_rows or []:
            rid, st = r[0], (r[1] if len(r) > 1 else "")
            if st and st not in STATUS_VOCAB:
                out.append(f"E002 register {rid}: status `{st}` not in {STATUS_VOCAB}")
            if st in TERMINAL and (len(r) < 3 or "→ [" not in r[2]):
                out.append(f"E003 register {rid}: terminal without `→ [YYYY-MM-DD] <evidence>`")
            if st in TERMINAL and len(r) > 2:
                for tok in re.findall(r"`([^`]+)`", r[2]):
                    if "/" in tok and not PTR_BAD.search(tok) and not (cfg.root / tok).exists():
                        out.append(f"E010 register {rid}: evidence `{tok}` missing")
    # ledger evidence
    if cfg.has("ledger"):
        for n, t in pointers(read(cfg.path("ledger")), ign):
            if "/" in t and not pointer_exists(cfg, t, names):
                out.append(f"E009 ledger:{n} cites missing evidence `{t}`")
    # dated plans/audits
    pat = re.compile(cfg.get("core", "dated_pattern", "."))
    living = set(cfg.get("core", "living_plans", []))
    seen_dirs = set()
    for role in ("plans", "audits"):
        d = cfg.path(role)
        if cfg.form(role)[0] == "file" and d.is_dir() and d.resolve() not in seen_dirs:
            seen_dirs.add(d.resolve())
            for f in d.glob("*.md"):
                if f.name in ("README.md", "INDEX.md"):  # a directory's index is not a plan
                    continue
                if cfg.rel(f) not in living and pat.search(f.name) and not re.search(r"\d{4}-\d{2}-\d{2}", f.name):
                    out.append(f"E004 {role} file without a date stamp: {cfg.rel(f)}")
    # living plans
    resume = cfg.get("core", "resume_heading", "Resume here")
    for lp in living:
        p = cfg.root / lp
        if not p.is_file():
            out.append(f"E001 core.living_plans names missing `{lp}`")
            continue
        heads = [h for h, *_ in sections(p)]
        if section_by_heading(p, resume, 1) is None:
            out.append(f"W012 living plan {lp} has no '{resume}' section — a resuming agent reads only that")
        for h in heads:
            if re.search(r"\bsuperseded\b", h, re.I):
                out.append(f"W011 living plan {lp}: section '{h[:60]}' is superseded — `genome archive {lp} --section ...`")
    # generated zones: hand edits
    zfiles = {f.resolve(): f for f in corpus(cfg) + [cfg.root / t for t in record_zone_targets(cfg)]
              + ([worklog_index(cfg)] if worklog_numbered(cfg) else [])}
    for f in zfiles.values():
        out += [f"E006 {cfg.rel(f)}: zone `{n}` start marker without its end, or duplicated" for n in broken_zones(read(f))]
        for name, (sha, body) in zones(read(f)).items():
            if zone_sha(body) != sha:
                out.append(f"E006 {cfg.rel(f)}: generated zone `{name}` was hand-edited — fix the source, re-emit")
    # budgets
    for rel, limit in (cfg.get("core", "budgets", {}) or {}).items():
        p = cfg.root / rel
        if p.is_file() and p.stat().st_size > limit:
            out.append(f"E016 {rel} is {p.stat().st_size} bytes > budget {limit} — move history out, do not add prose")
    # TOC on long docs
    toc = cfg.get("core", "toc_lines", 300)
    for f in listed_docs(cfg):
        lines = read(f).splitlines()
        if len(lines) > toc and not re.search(r"^#+\s*(contents|table of contents|toc)\b|\]\(#", read(f), re.I | re.M):
            out.append(f"W010 {cfg.rel(f)} has {len(lines)} lines and no table of contents (`genome ask` still finds its sections)")
    # asks / rulings
    if cfg.has("asks"):
        days = cfg.get("core", "ask_days", 3)
        for r in rows(cfg.path("asks")):
            if len(r) < 6:
                continue
            rid, asked, st, _, _, applied = r[:6]
            if st not in ASK_VOCAB:
                out.append(f"E013 asks {rid}: status `{st}` not in {ASK_VOCAB}")
            if st == "ruled" and applied in ("", "—"):
                out.append(f"W013 asks {rid}: ruling not applied to any owner doc/record (feedback amends its owner the same session)")
            for t in re.findall(r"`([^`]+)`", applied):
                if not (cfg.root / t).exists():
                    out.append(f"E013 asks {rid}: applied-to `{t}` missing")
            try:
                age = (dt.date.today() - dt.date.fromisoformat(asked[:10])).days
            except ValueError:
                age = 0
            if st == "open" and age > days:
                out.append(f"W014 asks {rid}: open for {age} days — re-ask the operator or withdraw it")
    # numbered worklog
    if worklog_numbered(cfg):
        nums: dict[str, list[str]] = {}
        for f in worklog_files(cfg):
            nums.setdefault(re.match(r"\d+[a-z]?", f.name).group(0), []).append(f.name)
        out += [f"E014 worklog number {n} used by {len(v)} files: {', '.join(v)}" for n, v in nums.items() if len(v) > 1]
        z = zones(read(worklog_index(cfg))).get("worklog")
        if worklog_files(cfg) and (z is None or z[1] != render_worklog_index(cfg)):
            out.append(f"E015 {cfg.rel(worklog_index(cfg))}: worklog zone {'absent' if z is None else 'stale'} — `genome emit`")
    # archive manifests
    arch = cfg.path("archive")
    if cfg.form("archive")[0] == "file" and arch.is_dir():
        if cfg.get("core", "archive_form", "flat") == "generations":
            for gen in [d for d in arch.iterdir() if d.is_dir()]:
                man = read(gen / "README.md")
                if not man:
                    n = sum(1 for f in gen.rglob("*") if f.is_file())
                    out.append(f"W007 archive generation {gen.name}/ has no README manifest ({n} files)")
                    continue
                for f in gen.rglob("*"):
                    rel = f.relative_to(gen).as_posix()
                    parents = [p.as_posix() + "/" for p in Path(rel).parents if p.as_posix() != "."]
                    if f.is_file() and f.name != "README.md" and rel not in man and f.name not in man \
                            and not any(p in man for p in parents):
                        out.append(f"W007 archive {gen.name}/{f.relative_to(gen)} missing from its README manifest")
        else:
            idx = read(arch / "INDEX.md")
            out += [f"W007 archive file not in INDEX.md: {f.name}" for f in arch.glob("*.md")
                    if f.name != "INDEX.md" and f.name not in idx]
    # duplicate-question plans (dated form)
    plans = cfg.path("plans")
    if cfg.form("plans")[0] == "file" and plans.is_dir():
        titles = []
        for f in sorted(plans.glob("*.md")):
            body = read(f)
            if "kb: tombstone" in body:
                continue
            h = next((ln for ln in body.splitlines() if ln.startswith("#")), "")
            titles.append((f.name, set(re.findall(r"[a-z0-9]{4,}", h.lower()))))
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                a, b = titles[i][1], titles[j][1]
                if a and b and len(a & b) / len(a | b) >= 0.5:
                    out.append(f"W006 plans `{titles[i][0]}` and `{titles[j][0]}` answer the same question — keep one owner")
    out += lint_outward(cfg)
    return out


def lint_outward(cfg: Cfg) -> list[str]:
    """W008 README and a docs page answer the same question; W009 unreachable docs page."""
    out = []
    readme, docs = cfg.path("readme"), cfg.path("docs")
    text = read(readme) if readme.is_file() else ""
    pages = sorted(docs.rglob("*.md")) if docs.is_dir() else []
    if not (text and pages):
        return out

    def heads(t, levels=("## ", "### ")):
        return {re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", "", ln.lstrip("# ").lower())).strip()
                for ln in t.splitlines() if ln.startswith(levels)} - {""}

    internal = set()
    for role in DEFAULT_PATHS:
        if role not in ("readme", "docs") and cfg.form(role)[0] == "file":
            internal.add(cfg.path(role).resolve())
    internal |= {(cfg.root / str(v["into"]).partition("#")[0]).resolve() for v in cfg.views.values() if v.get("into")}  # generated view docs
    internal.add((docs / "playbooks").resolve())  # a blueprint's playbooks: reached through the AGENTS.md routing table
    outward = [f for f in pages if not any(f.resolve() == d or d in f.resolve().parents for d in internal)]
    rh = {h for h in heads(text) if len(h) >= 4}
    for f in outward:
        for h in sorted(rh & heads(read(f), ("# ", "## ", "### "))):
            out.append(f"W008 README and {cfg.rel(f)} both answer '{h}' — the README links, it does not paraphrase")
    linked = set(re.findall(r"\]\(([^)#\s]+\.md)", text))
    linked |= {l.split("/", 1)[1] for l in linked if l.startswith(docs.name + "/")}
    for f in outward:
        rel = f.relative_to(docs).as_posix()
        if rel in linked or f.name in linked or rel.lower() in ("readme.md", "index.md"):  # the docs landing page
            continue
        if not any(rel in read(p) or f.name in read(p) for p in outward if p != f):
            out.append(f"W009 docs page not linked from README or any docs page: {rel}")
    return out


def lint_records(cfg: Cfg) -> list[str]:
    out = []
    active, gone = records(cfg), records(cfg, True)
    seen: dict[str, str] = {}
    for r in active:
        if r["id"] in seen:
            out.append(f"E102 record id {r['id']} used twice: {seen[r['id']]} and {cfg.rel(r['path'])}")
        seen[r["id"]] = cfg.rel(r["path"])
        if r["status"] in ("Superseded", "Retired"):
            out.append(f"E103 {cfg.rel(r['path'])} is {r['status']} but still active — `genome rec supersede/retire` moves it")
        if not r["title"]:
            out.append(f"E101 {cfg.rel(r['path'])}: no title")
    known = {r["id"] for r in active + gone}
    pat = re.compile(rf"\b{re.escape(rec_prefix(cfg))}(?:AD|RG)-\d+\b")
    for r in active:
        for cited in set(pat.findall(r["text"])) - known:
            out.append(f"W105 {r['id']} cites unknown record {cited}")
    # a retired record has no successor: a live doc citing it cites law that no longer exists
    hist = tuple(cfg.paths[r].rstrip("/") for r in APPEND_ONLY if cfg.form(r)[0] == "file")
    for r in gone:
        if r["status"] == "Retired" and not r["by"]:
            for f in readers(cfg, r["id"]):
                if not f.startswith(hist) and f != cfg.rel(r["path"]):
                    out.append(f"W106 {f} cites retired record {r['id']} (no successor) — drop the citation or cite the owner")
    # frontmatter contract: the id in the file matches its name; required fields; vocabularies
    req = cfg.get("records", "required", {})
    for r in active + gone:
        rel, fm = cfg.rel(r["path"]), r["fm"]
        if fm.get("ID") and fm["ID"] != r["file_id"]:
            out.append(f"E105 {rel}: ID `{fm['ID']}` does not match the file name")
        if r in active:  # archived records are frozen history: required fields bind live law only
            out += [f"E105 {rel}: frontmatter `{k}` missing" for k in req.get(r["kind"], []) if not fm.get(k)]
        if fm.get("Date") and fm["Date"] != "unrecorded" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fm["Date"]):
            out.append(f"E105 {rel}: Date `{fm['Date']}` is not YYYY-MM-DD")
        if r["sev"] and r["sev"] not in SEVERITIES:
            out.append(f"E105 {rel}: Severity `{r['sev']}` not in {SEVERITIES}")
    # supersession is two-sided: a record that supersedes X names a retired X
    by_id = {r["id"]: r for r in active + gone}
    for r in active:
        for t in re.findall(rf"{re.escape(rec_prefix(cfg))}(?:AD|RG)-\d+", r["fm"].get("Supersedes", "")):
            if t not in by_id:
                out.append(f"E106 {r['id']} supersedes {t}, which no record or archive holds")
            elif by_id[t] in active:
                out.append(f"E106 {r['id']} supersedes {t}, which is still active — `genome rec supersede {t} --by {r['id']}`")
    # governance map: every active record is named by the doctrine outside its generated zones
    gov = cfg.get("records", "governed_by")
    if gov:
        text = read(cfg.root / gov)
        for _, (_, body) in zones(text).items():
            text = text.replace(body, "")
        for r in active:
            if not re.search(rf"\b{re.escape(r['id'])}\b", text):
                out.append(f"E107 {r['id']} is governed by no row of {gov} — name it where its topic lives")
    for target, names in record_zone_targets(cfg).items():
        z = zones(read(cfg.root / target))
        for n in names:
            want = RENDER[n](cfg) if n in RENDER else ""
            if n not in RENDER:
                out.append(f"E104 {target}: unknown zone `{n}` (known: {', '.join(RENDER)})")
            elif n in z and z[n][1] != want + ("" if want.endswith("\n") else "\n"):
                out.append(f"E104 {target}: zone `{n}` is stale — `genome rec emit`")
            elif n not in z and (active or gone) and (not cfg.legacy or cfg.zones_declared):
                out.append(f"E104 {target}: zone `{n}` absent — `genome rec emit`")
    return out


def figure_re(cfg: Cfg) -> re.Pattern:
    return re.compile(cfg.get("research", "figure_pattern", r"(?<![\w.])[+\-−]?\d+(?:\.\d+)?\s?%"))


def class_re(cfg: Cfg) -> re.Pattern:
    cl = cfg.get("research", "classes", list(CLASSES))
    return re.compile(r"\[(" + "|".join(map(re.escape, cl)) + r")\]")


def research_surfaces(cfg: Cfg) -> list[Path]:
    s = cfg.get("research", "surfaces")
    return cfg.globs(s) if s else [cfg.path(r) for r in ("state", "agents") if cfg.has(r)]


def quarantine_surfaces(cfg: Cfg) -> list[Path]:
    """Where a quarantined figure may not appear: the research surfaces plus every skill reference and audit that
    quotes measurements (RG-040). The narrow `surfaces` key left the skill references unguarded, so a struck figure
    could be re-quoted there with no check."""
    s = cfg.get("research", "quarantine_surfaces")
    return cfg.globs(s) if s else research_surfaces(cfg)


def quarantined(cfg: Cfg) -> list[tuple[str, str]]:
    if not cfg.has("quarantine"):
        return []
    # only the figures table: a quarantine file may carry other tables, whose first column is not figures
    return [(t, r[0]) for h, rs in tables(cfg.path("quarantine")) if not h or re.search(r"figure", h[0], re.I)
            for r in rs for t in re.findall(r"`([^`]+)`", r[0])]


def lint_research(cfg: Cfg) -> list[str]:
    out = []
    fig, cls = figure_re(cfg), class_re(cfg)
    q = quarantined(cfg)
    qpath = cfg.path("quarantine").resolve()
    for f in quarantine_surfaces(cfg):
        text = read(f)
        text = blank_zones(text)
        for h, a, b, body in md_sections(text, "(top)"):
            if f in set(research_surfaces(cfg)) and fig.search(body) and not cls.search(body) and not cls.search(h):
                n = a + next(i for i, ln in enumerate(body.splitlines()) if fig.search(ln))
                out.append(f"W201 {cfg.rel(f)}:{n} figure without an evidence class in section '{h[:50]}'")
        if f.resolve() != qpath:
            pats = [(t, re.compile(r"(?<![\w.])" + re.escape(t) + r"(?![\w])")) for t, _ in q]
            for n, ln in enumerate(text.splitlines(), 1):
                for t, rx in pats:
                    if rx.search(ln):
                        out.append(f"E202 {cfg.rel(f)}:{n} quotes quarantined figure `{t}` — strike it")
    if cfg.has("prereg"):
        latest: dict[str, list[str]] = {}
        for r in rows(cfg.path("prereg")):
            if len(r) >= 3:
                latest[r[1].strip("`")] = r
        for spec, r in latest.items():
            p = cfg.root / spec
            if not p.is_file():
                out.append(f"E203 pre-registration `{spec}` is missing")
            elif r[2].strip("`") not in spec_hashes(p.read_bytes()):
                out.append(f"E203 pre-registration `{spec}` changed after freezing — revert it, or re-freeze with a reason")
    if cfg.has("hypotheses"):
        reg, vocab = Register(cfg, "hypotheses"), hyp_vocab(cfg)
        for r in reg.rows:
            if reg.col("status") is None or len(r) < 2:
                break
            hid, st = r[0], status_word(reg.get(r, "status"))
            if st not in vocab:
                out.append(f"E204 hypothesis {hid}: status `{reg.get(r, 'status')[:40]}` does not start with one of "
                           f"{vocab} (research.hyp_statuses adds words)")
            if st in HYP_TERMINAL and reg.col("evidence") is not None:
                ok, bad = evidence_refs(cfg, reg.get(r, "evidence") + " " + reg.get(r, "status"))
                if not ok:
                    out.append(f"E205 hypothesis {hid}: {st} without evidence (a backticked path or `worklog NNNN`)")
                out += [f"E205 hypothesis {hid}: evidence {e} missing" for e in bad]
            if st == "rejected" and reg.col("reopen") is not None and reg.get(r, "reopen") in ("", "—"):
                out.append(f"E206 hypothesis {hid}: rejected without a re-open condition")
    return out


def hyp_vocab(cfg: Cfg) -> tuple[str, ...]:
    return HYP_VOCAB + tuple(cfg.get("research", "hyp_statuses", []))


def live_surfaces(cfg: Cfg, files: list[str]) -> list[str]:
    s = {cfg.rel(p) for p in cfg.globs(cfg.get("ops", "link_surfaces", []))}
    s |= {cfg.rel(p) for p in listed_docs(cfg)}
    s |= {cfg.paths[r] for r in ("agents", "state", "entry", "ownership_map", "runbook") if cfg.has(r)}
    roots = cfg.get("ops", "code_roots", [])
    s |= {f for f in files if any(gmatch(f, g, cfg) for g in roots) and not is_archived(cfg, f)}
    if "records" in cfg.modules:
        s |= {cfg.rel(r["path"]) for r in records(cfg)}
    return sorted(s)


def lint_ops(cfg: Cfg) -> list[str]:
    out = []
    files = tracked(cfg)
    names = files
    ign = cfg.ignore()
    # ownership map: every owner-location doc is listed
    if cfg.has("ownership_map"):
        mp = read(cfg.path("ownership_map"))
        exempt = set(cfg.get("ops", "owner_exempt", []))
        for g in cfg.get("ops", "owner_globs", []):
            for f in files:
                if gmatch(f, g, cfg) and f not in exempt and not is_archived(cfg, f) \
                        and f not in mp and f"`{Path(f).name}`" not in mp:
                    out.append(f"E301 {f} is in an owner location but not listed in {cfg.paths['ownership_map']}")
    # links across surfaces
    for rel in sorted(set(cfg.rel(p) for p in cfg.globs(cfg.get("ops", "link_surfaces", []))) |
                      ({cfg.paths["ownership_map"]} if cfg.has("ownership_map") else set())):
        for n, t in pointers(read(cfg.root / rel), ign, tuple(cfg.get("ops", "link_prefixes", []))):
            if "/" in t and not pointer_exists(cfg, t, names) and not list(cfg.root.glob(t)):
                out.append(f"E303 {rel}:{n} cites `{t}`, which does not exist")
    # unreachable code
    globs = cfg.get("ops", "code_globs", [])
    if globs:
        code = [f for f in files if any(gmatch(f, g, cfg) for g in globs) and not is_archived(cfg, f)]
        by_stem: dict[str, list[str]] = {}
        for f in code:
            by_stem.setdefault(Path(f).stem, []).append(f)
        tok = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

        def refs(p: str) -> set[str]:
            return {c for t in set(tok.findall(read(cfg.root / p))) for c in by_stem.get(t, ())}

        live = live_surfaces(cfg, files)
        seen: set[str] = set()
        todo: set[str] = set(live) & set(code)
        todo |= set().union(*(refs(r) for r in live)) if live else set()
        while todo:
            f = todo.pop()
            if f not in seen:
                seen.add(f)
                todo |= refs(f) - seen
        out += [f"E304 {f} is reachable from no live surface — archive it or cite it from its owner" for f in
                sorted(set(code) - seen)]
    out += lint_external(cfg)
    # tracked bulk
    bulk, big = cfg.get("ops", "bulk_globs", []), cfg.get("ops", "max_bytes", 0)
    allow = set(cfg.get("ops", "bulk_allow", []))
    for f in files:
        if f in allow:
            continue
        if any(gmatch(f, g, cfg) for g in bulk):
            out.append(f"E305 {f} is regenerable bulk tracked in git — `git rm --cached` + .gitignore")
        elif big:
            try:
                sz = (cfg.root / f).stat().st_size
            except OSError:
                continue
            if sz > big:
                out.append(f"E305 {f} is {sz / 1e6:.1f} MB > {big / 1e6:.0f} MB and not in ops.bulk_allow")
    return out


def lint_external(cfg: Cfg) -> list[str]:
    """A tracked symlink out of the repo makes it depend on one machine and lets outside text steer it."""
    ok, out = cfg.get("ops", "external_ok", []), []
    for ln in sh(cfg.root, "git", "ls-files", "-s").splitlines():
        if not ln.startswith("120000"):
            continue
        f = ln.split("\t", 1)[1]
        try:
            (cfg.root / f).resolve().relative_to(cfg.root.resolve())
        except ValueError:
            if not any(gmatch(f, g, cfg) for g in ok):
                out.append(f"E307 {f} is a symlink out of the repo (-> {os.readlink(cfg.root / f)}): vendor it, "
                           "remove it, or list it in ops.external_ok")
    return out


def misplaced_paths(cfg) -> list[str]:
    """Root files that no role points at.

    With an explicit ops.root_files the rule is the strict allow-list it has
    always been. With the derived default the rule is scoped to documents,
    because a Cargo.toml, a LICENSE and a genome.toml are the repo's own
    machinery and flagging them would train the agent to ignore the check.
    """
    legal = legal_root_files(cfg)
    derived = cfg.get("ops", "root_files") is None
    out = []
    for f in sh(cfg.root, "git", "ls-files", "-co", "--exclude-standard", "-z").split("\0"):
        if not f or "/" in f:
            continue
        if not (cfg.root / f).is_file():
            continue    # a staged deletion is not a file in the wrong place
        name = f.rsplit("/", 1)[-1]
        if name.startswith(".") or name in legal:
            continue
        if derived and not name.lower().endswith((".md", ".markdown")):
            continue
        out.append(f)
    return sorted(out)


def legal_root_files(cfg) -> set[str]:
    """The root-level files this repo may have.

    Derived when the repo has not said otherwise: the conventional root docs
    plus every role this repo has moved to the root. ops.root_files, when set,
    REPLACES the derived set, so an existing config keeps exactly the behaviour
    it was written for.
    """
    explicit = cfg.get("ops", "root_files")
    if explicit is not None:
        return set(explicit)
    out = set(CONVENTIONAL_ROOT_DOCS)
    for role in cfg.paths:
        if cfg.form(role)[0] != "file":
            continue
        p = cfg.paths[role].split("#", 1)[0]
        if "/" not in p:
            out.add(p)
    return out


def lint_root_placement(cfg: Cfg) -> list[str]:
    """A file may only live where a role points at.

    One source of truth: `misplaced_paths` decides, this reports. The lint and
    `close` must agree — a file the lint calls misplaced and a file `close`
    refuses to name for commit are the same set, or the lint is advisory.
    """
    return [f"E306 {f}: no role points here — move it under docs/, or give it a role"
            for f in misplaced_paths(cfg)]


def lint_layout(cfg: Cfg) -> list[str]:
    """Where files may live: root allow-list, per-directory suffixes, required per-directory files, stale terms."""
    out = []
    roots, suf = cfg.get("ops", "root_files"), cfg.get("ops", "dir_suffixes", {})
    req, stale = cfg.get("ops", "dir_requires", {}), cfg.get("ops", "stale_terms", [])
    # the root-placement check needs no config: the legal set is derived, so it
    # runs on every repo. the ops-only checks stay gated on their keys.
    if not (suf or req or stale):
        return lint_root_placement(cfg)
    # and it runs even when the ops-only checks do: the placement findings
    # come from the same function `close` uses, so the two can never disagree
    out += lint_root_placement(cfg)
    files = [f for f in sh(cfg.root, "git", "ls-files", "-co", "--exclude-standard", "-z").split("\0") if f]
    files = [f for f in files if (cfg.root / f).is_file()]
    for f in files:
        name = f.rsplit("/", 1)[-1]
        if "truncated" in name or name.startswith("..."):
            out.append(f"E306 {f}: named like a truncation artefact")
        key = max((d for d in suf if f.startswith(d.rstrip("/") + "/")), key=len, default=None)
        if key is not None and suf[key] != "*" and not f.endswith(tuple(suf[key])):
            out.append(f"E306 {f}: suffix not allowed under {key} ({', '.join(suf[key])})")
    for pat, need in req.items():
        for d in sorted(p for p in cfg.root.glob(pat.rstrip("/")) if p.is_dir() and not p.name.startswith((".", "__"))):
            if not (d / need).exists():
                out.append(f"E306 {cfg.rel(d)}/ has no {need}")
    exempt = cfg.get("ops", "stale_exempt", [])
    for term in stale:
        rx = re.compile(r"(?<![\w/.-])" + re.escape(term))  # not inside a longer path (its archived copy)
        for f in sh(cfg.root, "git", "grep", "-l", "-F", "-e", term, "--", *STALE_DOCS).split():
            if f in ("genome.toml", "kb.toml") or is_archived(cfg, f) or any(gmatch(f, g, cfg) for g in exempt) \
                    or any(f.startswith(cfg.paths[r].rstrip("/") + "/") or f == cfg.paths[r]
                           for r in APPEND_ONLY if cfg.form(r)[0] == "file"):
                continue
            text = read(cfg.root / f)
            text = re.sub(r"(?ms)^##\s+Revisions\b.*?(?=^##\s|\Z)", "", text)  # revision lines are history
            if rx.search(text):
                out.append(f"E306 {f} names the stale path `{term}`")
    return out


def lint_agents(cfg: Cfg) -> list[str]:
    out = []
    d = cfg.path("workflows")
    if cfg.form("workflows")[0] == "file" and d.is_dir():
        for f in sorted(d.glob("*.md")):
            for r in rows(f):
                if len(r) > 3 and r[1] == "in-progress" and not re.search(r"claimed-by `[A-Za-z0-9_.-]+`", r[3]):
                    out.append(f"E008 {f.name} {r[0]}: in-progress without a well-formed claim (`genome claim`)")
    return out


def lint_outline(cfg: Cfg) -> list[str]:
    """The same E-rule the records zones use, so a stale outline fails `genome lint` and
    `genome close` by the code a reader already knows, not a new one."""
    return [f"E104 {s.rsplit(' (', 1)[0]}: zone `{OUTLINE_ZONE}` is stale — `genome outline`"
            for s in outline_stale(cfg)]


CHECKS = {"core": lint_core, "records": lint_records, "research": lint_research, "ops": lint_ops,
          "agents": lint_agents, "outline": lint_outline}


def run_lint(cfg: Cfg, only: str | None = None) -> list[str]:
    out = []
    for mod in MODULES:
        if mod in cfg.modules and (only is None or only == mod):
            out += CHECKS[mod](cfg)
    if only is None:
        out += lint_kinds(cfg) if cfg.kinds else []
        out += lint_drift(cfg)
    return out


def cmd_lint(args) -> None:
    cfg = find_cfg()
    if args.only:
        cfg.need(args.only)
    found = run_lint(cfg, args.only)
    if args.code:
        found = [f for f in found if f.startswith(tuple(args.code))]
    errs = [f for f in found if f.startswith("E")]
    if args.json:
        jprint({"errors": len(errs), "warnings": len(found) - len(errs), "modules": sorted(cfg.modules),
                "findings": [{"code": f[:4], "severity": "error" if f[0] == "E" else "warning", "text": f[5:]} for f in sorted(found)]})
        raise SystemExit(ERR if errs and not args.advisory else 0)
    by: dict[str, list[str]] = {}
    for f in sorted(found, key=lambda s: (s[0] == "E", s)):
        by.setdefault(f[:4], []).append(f)
    for code, items in by.items():  # capped per code: lint output is read by agents, every line costs
        for f in items if args.all else items[:5]:
            print(f)
        if not args.all and len(items) > 5:
            print(f"{code} ... {len(items) - 5} more (`genome lint --code {code} --all`)")
    print(f"lint: {len(errs)} error(s), {len(found) - len(errs)} warning(s) [{', '.join(sorted(cfg.modules))}]"
          if found else f"lint: clean [{', '.join(sorted(cfg.modules))}]")
    raise SystemExit(ERR if errs and not args.advisory else 0)


