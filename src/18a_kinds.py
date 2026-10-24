# ---------------------------------------------------------------- kinds

# A kind is a declared entity type: fields, states, transitions, typed relations. It lives in genome.toml
# ([kinds.<name>]) or genome/kinds/*.toml. Text is the source of truth: `dir` kinds keep one markdown file per
# entity, `jsonl` kinds one append-only event log. Any index is a cache (see the index module).

RESERVED_FIELDS = {"id", "kind", "state", "title"}
STRUCTURAL_KEYS = {"id", "kind", "state", "title"}  # front-matter keys every entity may carry: not fields, not errors
STORES = ("dir", "jsonl")
MUTABILITY = ("current", "amendable", "append-only", "immutable")
KIND_KEYS = {"path", "id", "store", "mutability", "fields", "states", "initial", "transitions", "evidence_on", "evidence_ref",
             "human_only", "quarantine", "relations", "description"}
REL_KEYS = {"to", "inverse", "max", "min", "required_in", "taint", "graph", "symmetric", "default"}
WHERE_RE = re.compile(r"^\s*([A-Za-z_][\w.-]*)\s*(<=|>=|!=|=|<|>|~)\s*(.*?)\s*$")


def kind_specs(cfg: Cfg) -> dict[str, dict]:
    out = {}
    for name, k in cfg.kinds.items():
        s = dict(k)
        s.setdefault("store", "dir")
        s.setdefault("mutability", "append-only" if s["store"] == "jsonl" else "current")
        s.setdefault("fields", {})
        s.setdefault("relations", {})
        s["states"] = list(s.get("states", []))
        s.setdefault("initial", s["states"][0] if s["states"] else "")
        s["name"] = name
        out[name] = s
    return out


def kind_problems(cfg: Cfg) -> list[str]:
    """E501: a kind declaration that cannot work (checked before any entity is read)."""
    out, specs = [], kind_specs(cfg)
    for n, k in specs.items():
        def bad(msg):
            out.append(f"E501 kind `{n}`: {msg}")
        if set(k) - KIND_KEYS - {"name"}:
            bad(f"unknown key(s) {sorted(set(k) - KIND_KEYS - {'name'})} (known: {', '.join(sorted(KIND_KEYS))})")
        if not isinstance(k.get("path"), str) or not k["path"]:
            bad("`path` is required")
        elif not inside(k["path"]):
            bad("`path` must be a path inside the repo (no `..`, not absolute)")
        if "{n" not in str(k.get("id", "")):
            bad("`id` needs a counter, e.g. \"EN-{n:04}\"")
        if k["store"] not in STORES:
            bad(f"store must be one of {STORES}")
        if k["mutability"] not in MUTABILITY:
            bad(f"mutability must be one of {MUTABILITY}")
        st = set(k["states"])
        if k["states"] and k["initial"] not in st:
            bad(f"initial `{k['initial']}` is not one of its states")
        for key in ("evidence_on", "human_only"):
            if set(k.get(key, [])) - st:
                bad(f"{key} names states that do not exist: {sorted(set(k[key]) - st)}")
        for a, ts in k.get("transitions", {}).items():
            if a not in st or set(ts) - st:
                bad(f"transitions mention unknown states ({a} → {ts})")
        for f, spec in k["fields"].items():
            if f in RESERVED_FIELDS or f in k["relations"]:
                bad(f"field `{f}` clashes with a reserved name or a relation")
            elif field_error(str(spec), None, ignore_missing=True) == "spec":
                bad(f"field `{f}` has an unreadable type `{spec}`")
        for s_, spec in k.get("evidence_ref", {}).items():
            rk, _, cond = str(spec).partition("?")
            f_, _, vals = cond.partition("=")
            if s_ not in k.get("evidence_on", []) and s_ != k.get("quarantine"):
                bad(f"evidence_ref names `{s_}`, which does not take evidence (list it in evidence_on)")
            elif rk not in specs:
                bad(f"evidence_ref `{s_}` names unknown kind `{rk}`")
            elif cond and (not f_ or not vals or (f_ != "state" and f_ not in specs[rk]["fields"] and not (vals == "@self" and f_ in specs[rk]["relations"]))):
                bad(f"evidence_ref `{s_}`: `{spec}` should read kind, kind?field=a|b (field may be `state`) or kind?relation=@self")
        if k.get("quarantine") and k["quarantine"] not in st:
            bad(f"quarantine state `{k['quarantine']}` is not one of its states")
        for r, rs in k["relations"].items():
            if not isinstance(rs, dict):
                bad(f"relation `{r}` must be a table, e.g. {{ to = \"kind\" }}")
                continue
            if set(rs) - REL_KEYS:
                bad(f"relation `{r}` has unknown keys {sorted(set(rs) - REL_KEYS)} (known: {', '.join(sorted(REL_KEYS))})")
            targets = [t for t in str(rs.get("to", "")).split("|") if t]
            for t in targets:
                if t != "*" and t not in specs:
                    bad(f"relation `{r}` points at unknown kind `{t}`")
            for key in ("min", "max"):
                if key in rs and not (isinstance(rs[key], int) and rs[key] >= 0):
                    bad(f"relation `{r}`: {key} must be a whole number")
            if set(rs.get("required_in", [])) - st:
                bad(f"relation `{r}`: required_in names states that do not exist: {sorted(set(rs['required_in']) - st)}")
            if rs.get("taint"):
                if not k.get("quarantine"):
                    bad(f"relation `{r}` has `taint` but the kind declares no `quarantine` state to move into")
                known = {s for t in targets for s in (specs[t]["states"] if t in specs else [])}
                if "*" not in targets and set(rs["taint"]) - known:
                    bad(f"relation `{r}`: taint names states its targets do not have: {sorted(set(rs['taint']) - known)}")
    return out


def field_error(spec: str, value, ignore_missing: bool = False) -> str | None:
    """None when the value fits the field spec; 'spec' when the spec itself is unreadable; else a message.
    Specs: text · int[:lo..hi] · enum:a|b|c · enum:lo..hi · date · bool; a trailing `!` makes the field required."""
    req = spec.endswith("!")
    base = spec.rstrip("!")
    typ, _, arg = base.partition(":")
    if typ not in ("text", "int", "enum", "date", "bool") or (typ == "enum" and not arg):
        return "spec"
    if value in (None, ""):
        return None if ignore_missing or not req else "is required"
    v = str(value)
    if typ == "int" or (typ == "enum" and re.fullmatch(r"-?\d+\.\.-?\d+", arg)):
        if not re.fullmatch(r"-?\d+", v):
            return f"`{v}` is not an integer"
        m = re.fullmatch(r"(-?\d+)\.\.(-?\d+)", arg)
        if m and not int(m.group(1)) <= int(v) <= int(m.group(2)):
            return f"{v} is outside {arg}"
    elif typ == "enum" and v not in arg.split("|"):
        return f"`{v}` is not one of {arg}"
    elif typ == "date" and not re.fullmatch(r"\d{4}-\d\d-\d\d", v):
        return f"`{v}` is not a date (YYYY-MM-DD)"
    elif typ == "bool" and v not in ("true", "false"):
        return f"`{v}` is not true/false"
    return None


def id_regex(k: dict) -> re.Pattern:
    pre, post = re.split(r"\{n[^}]*\}", k["id"], maxsplit=1)
    return re.compile(re.escape(pre) + r"(\d+)" + re.escape(post))


def kind_dir(cfg: Cfg, k: dict) -> Path:
    return cfg.root / k["path"]


def _entity(k: dict, id_: str, state: str, title: str, fields: dict, rels: dict, history: list, path: Path, line: int = 0, body: str = "", extra: list | None = None) -> dict:
    return {"id": id_, "kind": k["name"], "state": state, "title": title, "fields": fields, "rels": rels,
            "history": history, "path": path, "line": line, "body": body, "extra": extra or []}


def inside(rel: str) -> bool:
    """A repo-relative path that stays in the repo: not absolute, no `..`."""
    return bool(rel) and not Path(rel).is_absolute() and ".." not in Path(rel).parts


def parse_dir_entity(k: dict, p: Path) -> dict | None:
    text = read(p)
    fm = frontmatter(text)
    if "id" not in fm or fm.get("kind") != k["name"]:
        return None
    rels = {r: [x.strip() for x in fm[r].split(",") if x.strip()] for r in k["relations"] if fm.get(r)}
    fields = {f: fm[f] for f in k["fields"] if f in fm}
    # An undeclared key is a typo the write paths validated against the kind, so it is an error, not data:
    # it must reach lint (E502) yet must never enter `fields`, or a re-write would re-quote and adopt it.
    extra = sorted(set(fm) - set(k["fields"]) - set(k["relations"]) - STRUCTURAL_KEYS)
    hist = [ln[2:] for ln in text.partition("\n## History")[2].splitlines() if ln.startswith("- ")]
    pre = text.partition("\n## History")[0]
    m = re.match(r"---\n.*?\n---\n", pre, re.S)
    body = re.sub(r"^\s*# .*\n", "", pre[m.end():] if m else pre, count=1).strip()
    return _entity(k, fm["id"], fm.get("state", ""), fm.get("title", ""), fields, rels, hist, p, 0, body, extra)


def fold_jsonl(k: dict, p: Path) -> tuple[dict[str, dict], list[str]]:
    ents: dict[str, dict] = {}
    bad: list[str] = []
    for n, ln in enumerate(read(p).splitlines() if p.is_file() else [], 1):
        if not ln.strip():
            continue
        try:
            ev = json.loads(ln)
            id_, op = ev["id"], ev["op"]
        except (ValueError, KeyError, TypeError):
            bad.append(f"E504 {p.name}:{n} not a JSON event with `id` and `op`")
            continue
        e = ents.get(id_)
        if op == "new":
            if e:
                bad.append(f"E504 {p.name}:{n} duplicate id {id_}")
                continue
            ents[id_] = _entity(k, id_, ev.get("state", k["initial"]), ev.get("title", ""), dict(ev.get("fields", {})),
                                {r: list(v) for r, v in ev.get("rels", {}).items()}, [f"{ev.get('ts', '')} created"], p, n, ev.get("body", ""))
        elif not e:
            bad.append(f"E505 {p.name}:{n} event `{op}` for unknown id {id_}")
        elif op == "move":
            e["history"].append(f"{ev.get('ts', '')} {e['state']} → {ev['state']}" + (f" · evidence: {ev['evidence']}" if ev.get("evidence") else "")
                                + (f" · by {ev['by']}" if ev.get("by") else ""))
            e["state"] = ev["state"]
        elif op == "set":
            e["fields"].update(ev.get("fields", {}))
        elif op in ("link", "unlink"):
            lst = e["rels"].setdefault(ev["rel"], [])
            if op == "link" and ev["to"] not in lst:
                lst.append(ev["to"])
            elif op == "unlink" and ev["to"] in lst:
                lst.remove(ev["to"])
    return ents, bad


def load_entities(cfg: Cfg) -> tuple[dict[str, dict], list[str]]:
    """Every entity of every kind, by id; plus read problems (E504 duplicate or unreadable)."""
    ents: dict[str, dict] = {}
    bad: list[str] = []
    for k in kind_specs(cfg).values():
        found: list[dict] = []
        if k["store"] == "jsonl":
            es, b = fold_jsonl(k, kind_dir(cfg, k))
            found, bad = found + list(es.values()), bad + b
        elif kind_dir(cfg, k).is_dir():
            for f in sorted(kind_dir(cfg, k).glob("*.md")):
                e = parse_dir_entity(k, f)
                if e:
                    found.append(e)
                elif f.name not in ("README.md", "INDEX.md"):
                    bad.append(f"W501 {cfg.rel(f)} is in kind `{k['name']}`'s directory but has no `id` and `kind: {k['name']}` front-matter")
        for e in found:
            if e["id"] in ents:
                bad.append(f"E504 duplicate id {e['id']} ({cfg.rel(ents[e['id']]['path'])}, {cfg.rel(e['path'])})")
            else:
                ents[e["id"]] = e
    return ents, bad


def inverse_edges(cfg: Cfg, ents: dict[str, dict]) -> dict[str, list[tuple[str, str]]]:
    """id → [(inverse relation name, source id)]: edges are stored once, forward, and read both ways."""
    specs, out = kind_specs(cfg), {}
    for e in ents.values():
        for r, tos in e["rels"].items():
            rs = specs[e["kind"]]["relations"].get(r, {})
            inv = rs.get("inverse") or (r if rs.get("symmetric") else f"~{r}")
            for t in tos:
                out.setdefault(t, []).append((inv, e["id"]))
    return out


def relation_problems(k: dict, e: dict, ents: dict[str, dict], state: str, rels: dict | None = None) -> list[tuple[str, str]]:
    """(code, message) for E511 (a required relation missing) and E510 (an edge to a target in a taint state from an
    entity not in quarantine), judging entity `e` as if it were in `state`. Lint and `move` share this, so a step
    that lint would refuse is refused on write."""
    out, rels = [], e["rels"] if rels is None else rels
    for r, rs in k["relations"].items():
        need = int(rs.get("min", 0)) or (1 if state in rs.get("required_in", []) else 0)
        if len(rels.get(r, [])) < need:
            when = f" in state `{state}`" if not rs.get("min") else ""
            out.append(("E511", f"{e['id']}.{r} needs at least {need} target(s){when}: `genome link {e['id']} {r} <id>`"))
        if rs.get("taint") and state != k.get("quarantine"):
            for t in rels.get(r, []):
                if t in ents and ents[t]["state"] in rs["taint"]:
                    out.append(("E510", f"{e['id']}.{r} → {t} which is `{ents[t]['state']}`: "
                                        f"`genome move {e['id']} {k['quarantine']} --evidence {t}`, or unlink it"))
    return out


def lint_kinds(cfg: Cfg) -> list[str]:
    """E501-E510 / W501-W502: schema-derived checks over every declared kind."""
    out = kind_problems(cfg)
    if out:
        return out
    specs = kind_specs(cfg)
    ents, bad = load_entities(cfg)
    out += bad
    for v, vs in cfg.views.items():
        if vs.get("into") and not inside(str(vs["into"]).partition("#")[0]):
            out.append(f"E501 view `{v}`: `into` must be a path inside the repo")
    for e in ents.values():
        k, where = specs[e["kind"]], f"{cfg.rel(e['path'])}" + (f":{e['line']}" if e["line"] else "")
        if not id_regex(k).fullmatch(e["id"]):
            out.append(f"E504 {where} id {e['id']} does not match `{k['id']}`")
        if k["store"] == "dir" and not e["title"]:
            out.append(f"E502 {where} {e['id']}: title is required")
        for f, spec in k["fields"].items():
            err = field_error(str(spec), e["fields"].get(f))
            if err:
                out.append(f"E502 {where} {e['id']}.{f} {err}")
        for f in e.get("extra") or []:
            out.append(f"E502 {where} {e['id']}.{f} is not a field of kind `{k['name']}`")
        for f in set(e["fields"]) - set(k["fields"]):
            out.append(f"E502 {where} {e['id']}.{f} is not a field of kind `{k['name']}`")
        if k["states"] and e["state"] not in k["states"]:
            out.append(f"E503 {where} {e['id']}: state `{e['state']}` is not one of {k['states']}")
        out += [f"{code} {where} {msg}" for code, msg in relation_problems(k, e, ents, e["state"])]
        for r, tos in e["rels"].items():
            rs = k["relations"].get(r)
            if rs is None:
                out.append(f"E506 {where} {e['id']}: unknown relation `{r}`")
                continue
            if rs.get("max") and len(tos) > int(rs["max"]):
                out.append(f"E507 {where} {e['id']}.{r} has {len(tos)} targets, the limit is {rs['max']}")
            allowed = [t for t in str(rs.get("to", "*")).split("|") if t]
            for t in tos:
                if t not in ents:
                    out.append(f"E505 {where} {e['id']}.{r} → {t}: no such entity")
                elif "*" not in allowed and ents[t]["kind"] not in allowed:
                    out.append(f"E506 {where} {e['id']}.{r} → {t}: `{ents[t]['kind']}` is not one of {allowed}")
        for st in k.get("evidence_on", []):
            if e["state"] == st and not any(f"→ {st}" in h and "evidence:" in h for h in e["history"]):
                out.append(f"E509 {where} {e['id']} is `{st}` but its history names no evidence")
        for st in k.get("human_only", []):
            if e["state"] == st and not any(f"→ {st}" in h and "by human:" in h for h in e["history"]):
                out.append(f"W502 {where} {e['id']} is `{st}`, a human-only state, with no human sign-off in its history")
    for k in specs.values():  # frozen kinds: the laws a table of contents only asserts
        path = kind_dir(cfg, k)
        if not path.exists() or not is_git(cfg):
            continue
        if k["mutability"] == "append-only" and k["store"] == "jsonl":
            log = sh(cfg.root, "git", "log", "--numstat", "--format=%h", "--", k["path"])
            commit = None
            for ln in log.splitlines():
                m = re.fullmatch(r"(\d+)\t(\d+)\t.*", ln)
                if not m:
                    commit = ln
                elif int(m.group(2)):
                    out.append(f"E508 {k['path']}: commit {commit} removed lines from an append-only log")
        elif k["mutability"] == "immutable" and k["store"] == "dir":
            for f in sorted(path.glob("*.md")):
                n = len(sh(cfg.root, "git", "log", "--format=%h", "--", cfg.rel(f)).split())
                if n > 1:
                    out.append(f"E508 {cfg.rel(f)} is immutable but was changed in {n} commits")
    return out


# ---- commands

def next_entity_id(k: dict, ents: dict[str, dict], counters: dict | None = None) -> str:
    """The next free id. A batch passes `counters` so the scan over every id happens once per kind, not once per entity."""
    if counters is not None and k["name"] in counters:
        n = counters[k["name"]] + 1
    else:
        rx = id_regex(k)
        n = max([int(m.group(1)) for i in ents for m in [rx.fullmatch(i)] if m], default=0) + 1
    if counters is not None:
        counters[k["name"]] = n
    return k["id"].format(n=n)


def parse_sets(pairs: list[str] | None) -> dict[str, str]:
    out = {}
    for p in pairs or []:
        k, sep, v = p.partition("=")
        if not sep:
            die(f"--set expects key=value, got `{p}`")
        out[k.strip()] = v.strip()
    return out


def entity_text(k: dict, e: dict, body: str = "") -> str:
    fm = {"id": e["id"], "kind": k["name"], "state": e["state"], "title": e["title"], **e["fields"],
          **{r: ", ".join(v) for r, v in e["rels"].items() if v}}
    head = "".join(f'{key}: "{yq(v)}"\n' for key, v in fm.items())
    hist = "".join(f"- {h}\n" for h in e["history"])
    return f"---\n{head}---\n\n# {e['title']}\n\n" + (body + "\n\n" if body else "") + f"## History\n\n{hist}"


def write_entity(cfg: Cfg, k: dict, e: dict) -> None:
    """Persist one entity: a dir kind rewrites its file (front-matter + history); a jsonl kind never calls this."""
    p = e["path"]
    old = read(p) if p.exists() else ""
    if old:
        fields = {"state": e["state"], **e["fields"], **{r: ", ".join(v) for r, v in e["rels"].items()}}
        text = set_front(old, {key: val for key, val in fields.items()})
        text = text.rstrip("\n") + "\n"
        marker = "## History"
        head = text.split(marker)[0].rstrip("\n") + "\n\n" if marker in text else text.rstrip("\n") + "\n\n"
        text = head + marker + "\n\n" + "".join(f"- {h}\n" for h in e["history"])
        atomic_write(p, text)
    else:
        atomic_write(p, entity_text(k, e))


def append_event(path: Path, ev: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"ts": now(), **ev}, ensure_ascii=False) + "\n")


def kind_of(cfg: Cfg, name: str) -> dict:
    specs = kind_specs(cfg)
    if name not in specs:
        die(f"no kind `{name}` — declared kinds: {', '.join(specs) or '(none)'}; declare one under [kinds.{name}] in genome.toml")
    probs = [p for p in kind_problems(cfg)]
    if probs:
        die("\n".join(probs))
    return specs[name]


def entity_of(cfg: Cfg, id_: str) -> tuple[dict, dict, dict[str, dict]]:
    ents, _ = load_entities(cfg)
    if id_ not in ents:
        die(f"no entity `{id_}`")
    return ents[id_], kind_specs(cfg)[ents[id_]["kind"]], ents


def human_check(k: dict, state: str, args) -> str:
    who = f"human:{args.human}" if args.human else args.agent or os.environ.get("GENOME_AGENT_ID", "agent")
    if state in k.get("human_only", []) and not args.human:
        die(f"`{state}` is human-only for kind `{k['name']}`: the operator runs `genome move <id> {state} --human <name>`", ERR)
    return who


def parse_links(pairs) -> dict[str, list[str]]:
    """`rel=ID` pairs (repeatable; `rel=A,B` for several), or a JSON object {rel: id | [ids]}."""
    out: dict[str, list[str]] = {}
    items = pairs.items() if isinstance(pairs, dict) else [p.partition("=")[::2] for p in pairs or []]
    for r, v in items:
        r = r.strip()
        if not r or not v:
            die(f"--link expects relation=ID, got `{r}={v}`")
        for t in (v if isinstance(v, list) else str(v).split(",")):
            if "=" in str(t):
                die(f"--link {r}={v}: `=` inside a value. Repeat the flag for each relation: --link {r}=A --link {str(t).partition('=')[0]}=B")
            if str(t).strip() and str(t).strip() not in out.setdefault(r, []):
                out[r].append(str(t).strip())
    return out


def draft_entity(cfg: Cfg, k: dict, ents: dict[str, dict], title: str, sets: dict, links: dict[str, list[str]], who: str, counters: dict | None = None, id_: str | None = None) -> dict:
    """Validate one new entity against its kind (fields, relation targets, cardinality, defaults) and give it an id.
    Raises SystemExit with the reason; writes nothing."""
    for f in sets:
        if f not in k["fields"]:
            die(f"`{f}` is not a field of `{k['name']}` (fields: {', '.join(k['fields']) or 'none'})")
    for f, spec in k["fields"].items():
        err = field_error(str(spec), sets.get(f))
        if err:
            die(f"{k['name']}.{f} {err}")
    if k["store"] == "dir" and not title:
        die(f"a title is required for `{k['name']}` (a directory kind)")
    for r, rs in k["relations"].items():
        if r not in links and rs.get("default"):
            links[r] = [rs["default"]]
    for r, tos in links.items():
        rs = k["relations"].get(r)
        if rs is None:
            die(f"`{k['name']}` has no relation `{r}` (relations: {', '.join(k['relations']) or 'none'})")
        allowed = [t for t in str(rs.get("to", "*")).split("|") if t]
        for t in tos:
            if t not in ents:
                die(f"{k['name']}.{r} → {t}: no such entity")
            if "*" not in allowed and ents[t]["kind"] not in allowed:
                die(f"{r} points at {allowed}, but {t} is `{ents[t]['kind']}`", ERR)
        if rs.get("max") and len(tos) > int(rs["max"]):
            die(f"{r} allows at most {rs['max']} target(s), got {len(tos)}", ERR)
    missing = [r for r, rs in k["relations"].items() if int(rs.get("min", 0)) > len(links.get(r, []))
               or (k["initial"] in rs.get("required_in", []) and not links.get(r))]
    if missing:
        die(f"`{k['name']}` needs " + ", ".join(f"--link {r}=<id>" + (f"×{k['relations'][r]['min']}" if int(k['relations'][r].get('min', 0)) > 1 else "")
                                              for r in missing), ERR)
    tainted = [m.split(": `genome")[0] for c, m in relation_problems(k, {"id": f"new {k['name']}"}, ents, k["initial"], links) if c == "E510"]
    if tainted:
        die("a new entity must not depend on a tainted target (quarantine state): " + "; ".join(tainted), ERR)
    id_ = id_ or next_entity_id(k, ents, counters)
    path = kind_dir(cfg, k) if k["store"] == "jsonl" else kind_dir(cfg, k) / f"{id_}-{slugify(title, 50)}.md"
    return _entity(k, id_, k["initial"], title or "", dict(sets), links,
                   [f"{now()} created · state {k['initial']} · by {who}"], path)


def persist_new(cfg: Cfg, k: dict, e: dict, body: str, who: str) -> None:
    if k["store"] == "jsonl":
        append_event(e["path"], {"id": e["id"], "op": "new", "state": e["state"], "title": e["title"], "fields": e["fields"],
                                 **({"rels": e["rels"]} if e["rels"] else {}), **({"body": body} if body else {}), "by": who})
    else:
        atomic_write(e["path"], entity_text(k, e, body))


def batch_lines(src: str, kind: str | None) -> list[dict]:
    text = sys.stdin.read() if src == "-" else read(Path(src)) if Path(src).is_file() else die(f"no batch file `{src}`")
    out = []
    for n, ln in enumerate(text.splitlines(), 1):
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except ValueError as ex:
            die(f"batch line {n}: not JSON ({ex})")
        if not isinstance(d, dict) or not (d.get("kind") or kind):
            die(f"batch line {n}: needs an object with `kind` (or pass the kind as the argument)")
        out.append({"n": n, "kind": d.get("kind") or kind, "title": d.get("title", ""), "set": d.get("set", {}),
                    "link": d.get("link", {}), "body": d.get("body", "")})
    return out


def cmd_new(args) -> None:
    """One entity (`new <kind> --title T --set k=v --link rel=ID`), or many from `--batch FILE|-` (JSON lines of
    {kind, title, set, link, body}; `@N` in a link names the entity made by batch line N). A batch is validated whole
    before anything is written: one bad line writes nothing."""
    cfg = find_cfg()
    who = args.agent or os.environ.get("GENOME_AGENT_ID", "agent")
    if args.batch:
        items = batch_lines(args.batch, args.kind)
    elif not args.kind:
        die("new needs a kind (or --batch FILE)")
    else:
        items = [{"n": 0, "kind": args.kind, "title": args.title or "", "set": parse_sets(args.set),
                  "link": args.link, "body": args.body or ""}]
    with Guarded(cfg.root / ".genome" / "entities"):
        ents, _ = load_entities(cfg)
        made, by_line, counters = [], {}, {}
        global DIE_PREFIX
        if args.batch:  # every line gets its id first, so `@N` may name a later line and a loop can close inside one batch
            for it in items:
                DIE_PREFIX = f"batch line {it['n']}: "
                k = kind_of(cfg, it["kind"])
                by_line[str(it["n"])] = i_ = next_entity_id(k, ents, counters)
                ents[i_] = _entity(k, i_, k["initial"], it["title"], {}, {}, [], None)  # a placeholder until its line is drafted
        for it in items:
            DIE_PREFIX = f"batch line {it['n']}: " if it["n"] else ""
            k = kind_of(cfg, it["kind"])
            links = parse_links(it["link"])
            own = by_line.get(str(it["n"]))
            if it["n"]:
                links = {r: [by_line.get(t[1:], t) if t.startswith("@") else t for t in tos] for r, tos in links.items()}
                bad = [t for tos in links.values() for t in tos if t.startswith("@")]
                if bad:
                    die(f"{bad[0]} names no line of this batch (lines are numbered from 1 over the input)")
                if own in [t for tos in links.values() for t in tos]:
                    die("a line cannot link to itself")
            sets = {f: str(v).lower() if isinstance(v, bool) else str(v) for f, v in it["set"].items()}
            e = draft_entity(cfg, k, ents, it["title"], sets, links, who, counters, id_=own)
            ents[e["id"]] = e
            made.append((k, e, it["body"]))
        DIE_PREFIX = ""
        for k, e, body in made:
            persist_new(cfg, k, e, body, who)
    if args.json:
        res = [{"id": e["id"], "kind": k["name"], "state": e["state"]} for k, e, _ in made]
        jprint(res if args.batch else res[0])
    else:
        for k, e, _ in made:
            print(f"{e['id']} created ({k['name']}{', ' + e['state'] if e['state'] else ''})")


def evidence_ref_problem(k: dict, state: str, ev: str, ents: dict[str, dict], me: str = "") -> str:
    """Why `ev` is not the kind of evidence this kind's `evidence_ref` demands for `state`, or "" when it is."""
    spec = k.get("evidence_ref", {}).get(state)
    if not spec:
        return ""
    rk, _, cond = str(spec).partition("?")
    f, _, vals = cond.partition("=")
    t = ents.get(ev)
    if t is None or t["kind"] != rk:
        return f"evidence for `{state}` must be the id of a `{rk}` entity" + (f" with {f}={vals}" if f else "")
    if vals == "@self":  # the evidence must itself point at the entity being moved (a red-team of *this* thesis)
        return "" if me in t["rels"].get(f, []) else f"evidence {ev} must have `{f}` pointing at {me}"
    have = t["state"] if f == "state" else t["fields"].get(f, "")
    if f and have not in vals.split("|"):
        return f"evidence {ev} has {f}={have or '(unset)'}; `{state}` needs {f}={vals}"
    return ""


def evidence_ok(cfg: Cfg, ev: str, ents: dict[str, dict]) -> bool:
    return ev.startswith(("commit:", "http://", "https://")) or (cfg.root / ev).exists() or ev in ents


def cmd_move(args) -> None:
    """move <id>[,<id>…] <state>: every id is checked before any is moved."""
    cfg = find_cfg()
    specs, (ents, _) = kind_specs(cfg), load_entities(cfg)
    plan = []
    for id_ in [i for i in args.id.split(",") if i]:
        if id_ not in ents:
            die(f"no entity `{id_}`")
        e = ents[id_]
        k = specs[e["kind"]]
        if k["states"] and args.state not in k["states"]:
            die(f"`{args.state}` is not a state of `{k['name']}` ({', '.join(k['states'])})")
        allowed = k.get("transitions", {})
        exit_ = args.state == k.get("quarantine")  # quarantine is reachable from anywhere, with the tainting id as evidence
        if allowed and not exit_ and args.state not in allowed.get(e["state"], []):
            die(f"{e['id']}: {e['state']} → {args.state} is not allowed; from `{e['state']}` you may go to {allowed.get(e['state'], []) or 'nowhere (terminal)'}", ERR)
        if args.state in k.get("evidence_on", []) or exit_:
            if not args.evidence:
                die(f"{e['id']} → {args.state} needs --evidence <existing path | entity id | commit:<sha> | URL>")
            if not evidence_ok(cfg, args.evidence, ents):
                die(f"evidence is not an existing path, entity id, commit:<sha> or URL: {args.evidence}")
            why = evidence_ref_problem(k, args.state, args.evidence, ents, e["id"])
            if why:
                die(f"{e['id']} → {args.state} is refused: {why}", ERR)
        probs = relation_problems(k, e, ents, args.state)
        if probs:
            die(f"{e['id']} → {args.state} is refused: " + "; ".join(m for _, m in probs), ERR)
        plan.append((e, k, human_check(k, args.state, args)))
    for e, k, who in plan:
        entry = f"{now()} {e['state']} → {args.state}" + (f" · evidence: {args.evidence}" if args.evidence else "") + f" · by {who}"
        with Guarded(e["path"]):
            if k["store"] == "jsonl":
                append_event(e["path"], {"id": e["id"], "op": "move", "state": args.state, "evidence": args.evidence or "", "by": who})
            else:
                cur = parse_dir_entity(k, e["path"])
                cur["state"], cur["history"] = args.state, cur["history"] + [entry]
                write_entity(cfg, k, cur)
        print(f"{e['id']}: → {args.state}")


def cmd_link(args, undo: bool = False) -> None:
    """link <a> <relation> <b>[,<b>…]: every target is checked before any edge is written."""
    cfg = find_cfg()
    e, k, ents = entity_of(cfg, args.a)
    rs = k["relations"].get(args.rel)
    if rs is None:
        die(f"`{k['name']}` has no relation `{args.rel}` (relations: {', '.join(k['relations']) or 'none'})")
    targets = list(dict.fromkeys(t for t in args.b.split(",") if t))
    missing = [t for t in targets if t not in ents]
    if missing:
        die(f"no entity `{missing[0]}`")
    allowed = [t for t in str(rs.get("to", "*")).split("|") if t]
    cur, changed = list(e["rels"].get(args.rel, [])), []
    for b in targets:
        if not undo and "*" not in allowed and ents[b]["kind"] not in allowed:
            die(f"{args.rel} points at {allowed}, but {b} is `{ents[b]['kind']}`", ERR)
        if not undo and rs.get("symmetric") and args.a in ents[b]["rels"].get(args.rel, []):
            print(f"{args.a} {args.rel} {b} already holds ({b} → {args.a}; `{args.rel}` is symmetric)")
        elif undo and b in cur:
            cur.remove(b)
            changed.append(b)
        elif not undo and b not in cur:
            if rs.get("max") and len(cur) >= int(rs["max"]):
                die(f"{args.rel} allows at most {rs['max']} target(s) and {args.a} has {len(cur)}", ERR)
            cur.append(b)
            changed.append(b)
    probs = relation_problems(k, e, ents, e["state"], {**e["rels"], args.rel: cur})
    if undo:
        gone = [m for c, m in probs if c == "E511" and f"{args.a}.{args.rel} " in m]
        if gone:
            die("cannot unlink: " + "; ".join(gone), ERR)
    else:
        tainted = [m.split(": `genome")[0] for c, m in probs if c == "E510" and any(f"→ {b} " in m for b in changed)]
        if tainted:
            die("cannot link: " + "; ".join(tainted) + f" (a tainted target is linked only from a `{k.get('quarantine')}` entity)", ERR)
    for b in changed:
        add_edge(cfg, k, e, args.rel, b, undo)
        print(f"{args.a} {args.rel} {'-/→' if undo else '→'} {b}")


def add_edge(cfg: Cfg, k: dict, e: dict, rel: str, to: str, undo: bool = False) -> None:
    with Guarded(e["path"]):
        if k["store"] == "jsonl":
            append_event(e["path"], {"id": e["id"], "op": "unlink" if undo else "link", "rel": rel, "to": to})
        else:
            cur = parse_dir_entity(k, e["path"])
            lst = cur["rels"].setdefault(rel, [])
            if undo and to in lst:
                lst.remove(to)
            elif not undo and to not in lst:
                lst.append(to)
            write_entity(cfg, k, cur)


def cmd_set(args) -> None:
    """set <id> --set field=value …: typed field updates, recorded in History (dir) or as a `set` event (jsonl)."""
    cfg = find_cfg()
    e, k, _ = entity_of(cfg, args.id)
    if k["mutability"] == "immutable":
        die(f"`{k['name']}` is immutable: supersede {e['id']} with a new entity instead", ERR)
    sets = parse_sets(args.set)
    if not sets:
        die("set needs at least one --set field=value")
    for f, v in sets.items():
        if f not in k["fields"]:
            die(f"`{f}` is not a field of `{k['name']}` (fields: {', '.join(k['fields']) or 'none'})")
        err = field_error(str(k["fields"][f]), v)
        if err:
            die(f"{f} {err}")
    who = args.agent or os.environ.get("GENOME_AGENT_ID", "agent")
    with Guarded(e["path"]):
        if k["store"] == "jsonl":
            append_event(e["path"], {"id": e["id"], "op": "set", "fields": sets, "by": who})
        else:
            cur = parse_dir_entity(k, e["path"])
            cur["fields"].update(sets)
            cur["history"].append(f"{now()} set {', '.join(sets)} · by {who}")
            write_entity(cfg, k, cur)
    print(f"{e['id']}: set {', '.join(f'{f}={v}' for f, v in sets.items())}")


def cmd_show(args) -> None:
    """show <id>[,<id>…]: one call reads several entities (fields, relations both ways, recent history)."""
    cfg = find_cfg()
    ents, _ = load_entities(cfg)
    invs = inverse_edges(cfg, ents)
    ids = [i for i in args.id.split(",") if i]
    missing = [i for i in ids if i not in ents]
    if missing:
        die(f"no entity `{missing[0]}`" + (f" (and {len(missing) - 1} more)" if len(missing) > 1 else ""))
    docs = []
    for id_ in ids:
        e, inv = ents[id_], invs.get(id_, [])
        if args.json:
            docs.append({"id": e["id"], "kind": e["kind"], "state": e["state"], "title": e["title"], "fields": e["fields"],
                         "relations": e["rels"], "inverse": [{"rel": r, "from": s} for r, s in inv], "history": e["history"],
                         **({"body": e["body"]} if e["body"] else {}), "path": cfg.rel(e["path"])})
            continue
        if docs:
            print()
        docs.append(e)
        print(f"{e['id']}  {e['kind']}  [{e['state']}]  {e['title']}")
        for f, v in e["fields"].items():
            print(f"  {f}: {v}")
        for r, tos in e["rels"].items():
            print(f"  {r} → {', '.join(f'{t} ({ents[t]['title'] or ents[t]['kind']})' if t in ents else t + ' (missing)' for t in tos)}")
        for r, sid in inv:
            print(f"  {r} ← {sid} ({ents[sid]['title'] or ents[sid]['kind']})")
        if e["body"]:
            lines = e["body"].splitlines()
            print("  | " + "\n  | ".join(lines[:30]) + (f"\n  | … {len(lines) - 30} more line(s) in the file" if len(lines) > 30 else ""))
        for h in e["history"][-5:]:
            print(f"  · {h}")
        print(f"  {cfg.rel(e['path'])}" + (f":{e['line']}" if e["line"] else ""))
    if args.json:
        jprint(docs[0] if len(docs) == 1 else docs)


def entity_value(e: dict, key: str) -> str:
    return {"id": e["id"], "kind": e["kind"], "state": e["state"], "title": e["title"]}.get(key, e["fields"].get(key, ""))


def matches(e: dict, conds: list[str]) -> bool:
    for c in conds or []:
        m = WHERE_RE.match(c)
        if not m:
            die(f"cannot read the condition `{c}` — use `field op value` with op one of = != < > <= >= ~")
        key, op, want = m.groups()
        have = entity_value(e, key)
        if op == "~":
            ok = want.lower() in have.lower()
        else:
            try:
                a, b = float(have), float(want)
            except ValueError:
                a, b = have, want
            ok = {"=": a == b, "!=": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op] if have != "" or op == "!=" else False
        if not ok:
            return False
    return True


def find_entities(cfg: Cfg, kind: str | None, conds: list[str], state: str | None = None) -> list[dict]:
    ents, _ = load_entities(cfg)
    return [e for e in ents.values() if (not kind or e["kind"] == kind) and (not state or e["state"] == state) and matches(e, conds)]


def cmd_find(args) -> None:
    cfg = find_cfg()
    kind_of(cfg, args.kind)
    hits = find_entities(cfg, args.kind, args.where, args.state)[:args.limit]
    if args.json:
        jprint([{"id": e["id"], "state": e["state"], "title": e["title"], "fields": e["fields"]} for e in hits])
        return
    for e in hits:
        extra = " ".join(f"{f}={v}" for f, v in e["fields"].items())[:70]
        print(f"{e['id']:12} {e['state']:12} {e['title'][:50]:50} {extra}")
    print(f"{len(hits)} {args.kind}")


def view_hits(cfg: Cfg, v: dict) -> list[dict]:
    hits = find_entities(cfg, v.get("kind"), v.get("where", []), v.get("state"))
    sort = v.get("sort", "id")
    hits.sort(key=lambda e: entity_value(e, sort.lstrip("-")), reverse=sort.startswith("-"))
    return hits


def wake_views(cfg: Cfg) -> list[str]:
    """`wake = true` views: a blueprint's work queue, 5 rows each, so orientation needs no further call."""
    out, empty = [], []
    for name, v in cfg.views.items():
        if v.get("wake") and not v.get("group_count"):
            hits = view_hits(cfg, v)
            if hits:
                out.append(f"- {name}: {len(hits)}")
                out += [f"    {e['id']} [{e['state']}] {e['title'][:70]}" for e in hits[:5]]
            else:
                empty.append(name)
    return out + ([f"- empty: {', '.join(empty)}"] if empty else [])


def render_view(cfg: Cfg, v: dict) -> str:
    hits = view_hits(cfg, v)
    cols = v.get("columns", ["id", "state", "title"])
    if v.get("group_count"):  # a generated count per state: numbers are never hand-written
        counts: dict[str, int] = {}
        for e in hits:
            counts[e["state"]] = counts.get(e["state"], 0) + 1
        return "| state | count |\n|---|---|\n" + "".join(f"| {s} | {n} |\n" for s, n in counts.items()) + f"| **total** | {len(hits)} |\n"
    body = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for e in hits[:int(v.get("limit", 200))]:
        body += "| " + " | ".join(entity_value(e, c).replace("|", "\\|") for c in cols) + " |\n"
    return body


def emit_views(cfg: Cfg) -> list[str]:
    changed = []
    for name, v in cfg.views.items():
        target = v.get("into")
        if not target:
            continue
        if not inside(str(target).partition("#")[0]):
            die(f"view `{name}`: into = `{target}` leaves the repo")
        path, _, zone = target.partition("#")
        if write_zone(cfg.root / path, zone or name, render_view(cfg, v)) and path not in changed:
            changed.append(path)
    return changed


def cmd_view(args) -> None:
    cfg = find_cfg()
    if args.name not in cfg.views:
        die(f"no view `{args.name}` — declared: {', '.join(cfg.views) or '(none)'}; declare [views.{args.name}] in genome.toml")
    print(render_view(cfg, cfg.views[args.name]), end="")
