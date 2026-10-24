# ---------------------------------------------------------------- blueprints

BP_KEYS = {"name", "version", "summary", "extends", "modules", "privacy", "routes", "playbook", "seed"}
PRIVACY = ("local", "private", "internal")  # strictest first


def bp_load(spec: str, root: Path | None = None, near: Path | None = None) -> tuple[dict, str, str]:
    """(parsed, toml text, origin) for a blueprint: a path, then genome/blueprints/<n>.toml, a sibling of the file
    that extends it, the built-in set, or a profile name (modules only)."""
    cand = None
    if spec.endswith(".toml") or "/" in spec:
        cand = Path(spec).expanduser()
        if not cand.is_file():
            die(f"no blueprint file `{spec}`")
    else:
        cand = next((d / f"{spec}.toml" for d in (root and root / "genome" / "blueprints", near)
                     if d and (d / f"{spec}.toml").is_file()), None)
    if cand:
        text, origin = read(cand), str(cand)
    elif spec in BLUEPRINTS:
        text, origin = BLUEPRINTS[spec], "built-in"
    elif spec in PROFILES:
        return {"blueprint": {"name": spec, "summary": f"profile: modules {', '.join(PROFILES[spec])}",
                              "modules": PROFILES[spec]}}, "", "profile"
    else:
        die(f"no blueprint `{spec}` — available: {', '.join([*BLUEPRINTS, *PROFILES])} (or a path to a .toml; see `genome blueprint list`)")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        die(f"{origin}: {e}")
    if not isinstance(data.get("blueprint"), dict):
        die(f"{origin}: no [blueprint] table")
    return data, text, origin


def bp_chain(specs: list[str], root: Path | None = None, near: Path | None = None, _seen: tuple = ()) -> list[tuple]:
    """[(name, data, text, origin)] with every `extends` base before the blueprint that names it, each once."""
    out: list[tuple] = []
    for spec in specs:
        data, text, origin = bp_load(spec, root, near)
        b = data["blueprint"]
        name = str(b.get("name") or Path(spec).stem)
        if name in _seen:
            die(f"blueprint `{name}` extends itself ({' → '.join([*_seen, name])})")
        here = Path(origin).parent if origin not in ("built-in", "profile") else near
        for base in bp_chain(list(b.get("extends", [])), root, here, (*_seen, name)):
            if base[0] not in {o[0] for o in out}:
                out.append(base)
        if name not in {o[0] for o in out}:
            out.append((name, data, text, origin))
    return out


def bp_problems(chain: list[tuple]) -> list[str]:
    """What is wrong with the declarations, before anything is applied."""
    out = []
    for name, data, text, origin in chain:
        b = data["blueprint"]
        def bad(msg, n=name):
            out.append(f"blueprint `{n}`: {msg}")
        if set(b) - BP_KEYS:
            bad(f"unknown [blueprint] keys {sorted(set(b) - BP_KEYS)} (known: {', '.join(sorted(BP_KEYS))})")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            bad("name must be lowercase letters, digits and hyphens")
        if not str(b.get("summary", "")).strip():
            bad("`summary` is required (one line: what the knowledge base is for)")
        if set(b.get("modules", ["core"])) - set(MODULES):
            bad(f"unknown modules {sorted(set(b['modules']) - set(MODULES))}")
        if b.get("privacy") and b["privacy"] not in PRIVACY:
            bad(f"privacy must be one of {PRIVACY}")
        for r in b.get("routes", []):
            if not (isinstance(r, list) and len(r) == 2 and all(isinstance(x, str) and x.strip() for x in r)):
                bad(f"each route is [question, where the answer lives]; got {r!r}")
        if not str(b.get("playbook", "")).strip() and text:
            bad("`playbook` is required: the loop an agent follows, as markdown (it is the blueprint's whole interface)")
    if out:
        return out
    merged: dict = {"kinds": {}, "views": {}}
    for _, _, text, _ in chain:
        more = tomllib.loads(text) if text else {}
        for sec in merged:
            deep_merge(merged[sec], more.get(sec, {}))
    cfg = Cfg(Path("."), {"genome": {"modules": ["core"]}, **merged}, False)
    out += kind_problems(cfg)
    for v, vs in merged["views"].items():
        if vs.get("kind") not in merged["kinds"]:
            out.append(f"E501 view `{v}`: kind `{vs.get('kind')}` is not declared")
        if vs.get("wake") and vs.get("group_count"):
            out.append(f"E501 view `{v}`: wake and group_count do not combine (a queue lists entities)")
        into = str(vs.get("into", ""))
        if into and (into.startswith("/") or ".." in Path(into.partition("#")[0]).parts):
            out.append(f"E501 view `{v}`: `into` must be a path inside the repo")
    for name, data, _, _ in chain:
        for s in data["blueprint"].get("seed", []):
            if s.get("kind") not in merged["kinds"]:
                out.append(f"blueprint `{name}`: seed kind `{s.get('kind')}` is not declared")
    return out


def bp_modules(chain: list[tuple]) -> list[str]:
    return [m for bp in chain for m in bp[1]["blueprint"].get("modules", [])]


def bp_privacy(chain: list[tuple]) -> str:
    ps = [bp[1]["blueprint"]["privacy"] for bp in chain if bp[1]["blueprint"].get("privacy")]
    return min(ps, key=PRIVACY.index) if ps else ""


def bp_preflight(cfg: Cfg, chain: list[tuple]) -> None:
    """Refuse before writing anything: a missing module, or kinds that do not validate against the genome's own."""
    miss = sorted(set(bp_modules(chain)) - cfg.modules)
    if miss:
        die(f"this blueprint needs module(s) {', '.join(miss)}: add them to genome.toml [genome] modules, then re-run")
    import copy
    kinds, views = {}, {}
    for _, _, text, _ in chain:
        more = tomllib.loads(text) if text else {}
        deep_merge(kinds, more.get("kinds", {}))
        deep_merge(views, more.get("views", {}))
    own = tomllib.loads(read(cfg.root / "genome.toml")).get("kinds", {}) if (cfg.root / "genome.toml").is_file() else {}
    clash = sorted(set(kinds) & set(own))
    probs = kind_problems(Cfg(cfg.root, {"genome": {"modules": ["core"]}, "kinds": deep_merge(kinds, copy.deepcopy(cfg.kinds)),
                                         "views": deep_merge(views, copy.deepcopy(cfg.views))}, False))
    if probs:
        die("the blueprint does not fit this genome:\n  " + "\n  ".join(probs))
    for c in clash:
        print(f"genome: note: kind `{c}` is already declared here; the genome's own keys win over the blueprint's", file=sys.stderr)


def agents_add(root: Path, chain: list[tuple]) -> list[str]:
    """Routing rows into AGENTS.md's table (one row per question, once) and a pointer to each playbook."""
    p = root / "AGENTS.md"
    if not p.is_file():
        return ["(no AGENTS.md: routes not added; the playbooks are in docs/playbooks/)"]
    text = read(p)
    if "(one paragraph)" in text and chain[-1][2]:  # a fresh contract says what the project is, from the blueprint
        text = text.replace("(one paragraph)", f"{chain[-1][1]['blueprint']['summary']}.", 1)
        atomic_write(p, text)
    lines = text.splitlines()
    rows = []
    for name, data, text, _ in chain:
        if not text:
            continue
        b = data["blueprint"]
        rows += [(f"how to run the `{name}` loop: its steps and the rules the schema enforces", f"`docs/playbooks/{name}.md`"),
                 *[tuple(r) for r in b.get("routes", [])]]
    new = [f"| {q} | {a} |" for q, a in rows if not any(q in ln for ln in lines)]
    if not new:
        return []
    head = next((i for i, ln in enumerate(lines) if ln.lower().startswith("## routing table")), None)
    if head is not None:
        i = next((k for k in range(head + 1, len(lines)) if lines[k].startswith("|")), None)
        while i is not None and i < len(lines) and lines[i].startswith("|"):
            i += 1
        if i is not None:
            lines[i:i] = new
            atomic_write(p, "\n".join(lines) + "\n")
            return [f"AGENTS.md (+{len(new)} routing row(s))"]
    atomic_write(p, "\n".join(lines) + "\n\n## Routing — blueprints\n\n| question | answer lives in |\n|---|---|\n" + "\n".join(new) + "\n")
    return [f"AGENTS.md (+{len(new)} routing row(s), new table)"]


def privacy_set(root: Path, want: str) -> list[str]:
    """[card] privacy = want in an existing genome.toml, only when it says nothing; never rewrites a stated value."""
    if not want:
        return []
    p = root / "genome.toml"
    text = read(p)
    have = tomllib.loads(text).get("card", {}).get("privacy")
    if have == want:
        return []
    if have:
        print(f"genome: note: [card] privacy is `{have}`; the blueprint asks for `{want}` — change it deliberately if it should hold", file=sys.stderr)
        return []
    if re.search(r"^\[card\]", text, re.M):
        text = re.sub(r"^\[card\][^\n]*\n", lambda m: m.group(0) + f'privacy = "{want}"\n', text, 1, re.M)
    else:
        text = text.rstrip("\n") + f'\n\n[card]\nprivacy = "{want}"\n'
    atomic_write(p, text)
    return [f"genome.toml (+[card] privacy = \"{want}\")"]


def bp_apply(root: Path, chain: list[tuple]) -> list[str]:
    """Copy each blueprint verbatim to genome/kinds/NNN-<name>.toml, route and document it, create its view docs and
    seed, backfill relation defaults, and emit the views. Never overwrites a file."""
    made = []
    kd = root / "genome" / "kinds"
    for name, data, text, _ in chain:
        if not text:
            continue
        have = next(iter(kd.glob(f"*-{name}.toml")), None)
        if have:
            made.append(f"= {cfg_rel(root, have)} (kept{'' if read(have) == text else '; differs from the shipped one'})")
            continue
        kd.mkdir(parents=True, exist_ok=True)
        f = kd / f"{10 * (len(list(kd.glob('*.toml'))) + 1):03}-{name}.toml"
        f.write_text(text)
        made.append(cfg_rel(root, f))
    made += privacy_set(root, bp_privacy(chain))
    cfg = find_cfg(root)
    for k in kind_specs(cfg).values():  # a log kind's file exists from the start, so a route to it never dangles
        f = root / k["path"]
        if k["store"] == "jsonl" and not f.exists():
            atomic_write(f, "")
            made.append(cfg_rel(root, f))
    made += agents_add(root, chain)
    for name, data, text, _ in chain:
        pb = root / "docs" / "playbooks" / f"{name}.md"
        if text and not pb.exists():
            b = data["blueprint"]
            atomic_write(pb, f"# Playbook — {name}\n\n{b['summary']}\n\n_From blueprint `{name}` v{b.get('version', '1')}; "
                             f"edit freely, `genome init` never overwrites it._\n\n{b['playbook'].strip()}\n")
            made.append(cfg_rel(root, pb))
    for v in cfg.views.values():
        target = str(v.get("into", "")).partition("#")[0]
        if target and not (root / target).exists():
            atomic_write(root / target, f"# {Path(target).stem}\n\nGenerated by `genome emit` from saved views; the zones below are not hand-edited.\n")
            made.append(target)
    ents_made = bp_seed(root, cfg, chain)
    made += ents_made
    n = bp_backfill(root, cfg)
    if n:
        made.append(f"{n} existing entit(ies) given their default relations")
    emitted = sorted(set(emit_views(cfg)))
    if emitted:
        made.append("views emitted into " + ", ".join(emitted))
    made.append(f"modules on: {', '.join(cfg.modules)}; kinds: {', '.join(kind_specs(cfg))}")
    return made


def cfg_rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def bp_seed(root: Path, cfg: Cfg, chain: list[tuple]) -> list[str]:
    specs, who, made = kind_specs(cfg), os.environ.get("GENOME_AGENT_ID", "blueprint"), []
    with Guarded(root / ".genome" / "entities"):
        ents, _ = load_entities(cfg)
        for name, data, _, _ in chain:
            for s in data["blueprint"].get("seed", []):
                k = specs[s["kind"]]
                if any(e["kind"] == k["name"] and e["title"] == s.get("title", "") for e in ents.values()):
                    continue
                e = draft_entity(cfg, k, ents, s.get("title", ""), {f: str(v) for f, v in s.get("set", {}).items()},
                                 parse_links(s.get("link", {})), f"blueprint:{name}")
                ents[e["id"]] = e
                persist_new(cfg, k, e, "", who)
                made.append(f"{e['id']} ({k['name']} `{e['title']}`, seed)")
    return made


def bp_backfill(root: Path, cfg: Cfg) -> int:
    """Entities made before a relation with a `default` existed (a blueprint added later) get that default edge."""
    specs, n = kind_specs(cfg), 0
    with Guarded(root / ".genome" / "entities"):
        ents, _ = load_entities(cfg)
        for e in list(ents.values()):
            k = specs[e["kind"]]
            for r, rs in k["relations"].items():
                d = rs.get("default")
                allowed = str(rs.get("to", "*")).split("|")
                if d and not e["rels"].get(r) and d in ents and d != e["id"] and ("*" in allowed or ents[d]["kind"] in allowed):
                    add_edge(cfg, k, e, r, d)
                    n += 1
    return n


# ---- the verbs

def bp_summary_line(name: str, data: dict) -> str:
    b = data["blueprint"]
    ext = f" ← {', '.join(b['extends'])}" if b.get("extends") else ""
    return f"  {name:20} v{b.get('version', '1')}{ext} · {b.get('summary', '')[:110]}" + (f" [{b['privacy']}]" if b.get("privacy") else "")


def fmt_flow(k: dict) -> str:
    """A lifecycle as the legal moves, so an agent need not learn them from a refused one."""
    st, tr, q = k.get("states", []), k.get("transitions", {}), k.get("quarantine")
    if not st:
        return ""
    if not tr:
        return ", ".join(st) + " (any order)"
    ends = [s for s in st if s not in tr and s != q]
    return (f"start {st[0]}: " + " · ".join(f"{a}→{'|'.join(b)}" for a, b in tr.items())
            + (f" · end: {', '.join(ends)}" if ends else "") + (f" · any→{q} (quarantine, with evidence)" if q else ""))


def fmt_field(name: str, spec: str) -> str:
    req = "!" if str(spec).endswith("!") else ""
    typ, _, arg = str(spec).rstrip("!").partition(":")
    return f"{name}{req}" + ("" if typ == "text" else f"={arg}" if typ == "enum" else f":{typ}{arg}")


def fmt_rel(name: str, rs: dict) -> str:
    out = f"{name}→{rs.get('to', '?')}"
    if "min" in rs or "max" in rs:
        out += f" [{rs.get('min', 0)}..{rs.get('max', '')}]"
    if rs.get("required_in"):
        out += " req:" + "|".join(rs["required_in"])
    if rs.get("taint"):
        out += " ⚑" + "|".join(rs["taint"])
    out += (" ↔" if rs.get("symmetric") else "") + (" ~" if rs.get("graph") is False else "") + (f" ={rs['default']}" if rs.get("default") else "")
    return out


def bp_names_local(root: Path | None) -> list[Path]:
    return sorted((root / "genome" / "blueprints").glob("*.toml")) if root else []


def cmd_blueprint(args) -> None:
    root = next((d for d in [Path.cwd().resolve(), *Path.cwd().resolve().parents] if (d / "genome.toml").is_file()), None)
    verb = args.bp_cmd
    if verb == "list":
        print("built-in:")
        for n in BLUEPRINTS:
            print(bp_summary_line(n, bp_load(n)[0]))
        print("profiles (modules only): " + ", ".join(f"{p}={'+'.join(m)}" for p, m in PROFILES.items()))
        local = bp_names_local(root)
        if local:
            print("local (genome/blueprints/):")
            for f in local:
                print(bp_summary_line(f.stem, bp_load(str(f))[0]))
        applied = sorted((root / "genome" / "kinds").glob("*.toml")) if root else []
        if applied:
            print("applied here (genome/kinds/): " + ", ".join(f.name for f in applied))
    elif verb == "show":
        if not args.name:
            die("blueprint show needs a name")
        chain = bp_chain([args.name], root)
        name, data, text, origin = chain[-1]
        b = data["blueprint"]
        if args.toml:
            print(text, end="")
        elif args.playbook:
            print(b.get("playbook", "").strip())
        else:
            kinds, views, own = {}, {}, set(data.get("kinds") or {})
            for _, d, t, _ in chain:  # the whole chain, extensions applied: what the genome will actually have
                deep_merge(kinds, tomllib.loads(t).get("kinds", {}) if t else {})
                deep_merge(views, tomllib.loads(t).get("views", {}) if t else {})
            print(f"{name} v{b.get('version', '1')} [{origin}] modules {'+'.join(b.get('modules', ['core']))}"
                  f"{' · privacy ' + b['privacy'] if b.get('privacy') else ''}"
                  f"{' · extends ' + ', '.join(b['extends']) if b.get('extends') else ''}\n{b['summary']}")
            for kn, k in kinds.items():
                flow = fmt_flow(k)
                hum = f"\n    human-only: {', '.join(k['human_only'])}" if k.get("human_only") else ""
                print(f"- {kn} [{k.get('id', '?')}, {k.get('store', 'dir')}]{' ' + flow if flow else ''}{'' if kn in own else '  (from a base)'}{hum}\n"
                      f"    fields: {', '.join(fmt_field(f, sp) for f, sp in (k.get('fields') or {}).items()) or 'none'}\n"
                      f"    relations: {', '.join(fmt_rel(r, rs) for r, rs in (k.get('relations') or {}).items()) or 'none'}")
            if views:
                print("views: " + ", ".join(f"{v}{'*' if s.get('wake') else ''}" for v, s in views.items()) + "  (* = in wake)")
            print("legend: field! required · [min..max] targets · req:state needs it from that state · ⚑state tainted by that target state · ↔ symmetric · "
                  "~ left out of graph analytics · =ID default\nfull text: `genome blueprint show NAME --toml`; the loop: `--playbook`")
    elif verb == "new":
        if not args.name or not re.fullmatch(r"[a-z][a-z0-9-]*", args.name):
            die("blueprint new needs a name: lowercase letters, digits and hyphens")
        dest = (root or Path.cwd()) / "genome" / "blueprints" / f"{args.name}.toml"
        if dest.exists():
            die(f"{dest} exists; blueprint new never overwrites")
        base = bp_chain([args.base], root) if args.base else []
        taken = {k for b in base for k in (b[1].get("kinds") or {})}
        kn = next(c for c in ("item", "entry", "record", "unit") if c not in taken)
        atomic_write(dest, BP_SKELETON.format(name=args.name, kind=kn, pre=kn[:2].upper(),
                                              extends=json.dumps([args.base] if args.base else []),
                                              mods=json.dumps(sorted(set(bp_modules(base)) | {"core"}))))
        print(f"{dest.relative_to(root) if root else dest} written. Edit it, then `genome blueprint check {dest.relative_to(root) if root else dest}`;\n"
              f"apply with `genome init --blueprint {args.name}`. Authoring rules: references/blueprints.md")
    elif verb == "check":
        names = [args.name] if args.name else list(BLUEPRINTS)
        bad = 0
        for n in names:
            bad += bp_check(n, root, args.keep)
        raise SystemExit(2 if bad else 0)
    else:
        die(f"unknown blueprint command `{verb}`")


BP_SKELETON = '''# {name}: what this knowledge base is for, in one line.
# Check it:  genome blueprint check genome/blueprints/{name}.toml     Apply it:  genome init --blueprint {name}
[blueprint]
name = "{name}"
version = "1"
summary = "one line: what it holds and what an agent can do with it"
extends = {extends}                 # base blueprints applied first; their kinds can be extended below without restating them
modules = {mods}
# privacy = "local"                 # subjective or sensitive data: no card, `close` refuses with a git remote
routes = [
  ["the question an agent will ask", "`where/the/answer/lives`"],
]
playbook = \'\'\'
**What this is.** One paragraph: the purpose, who may decide what, and what is out of scope.

**The loop.**
1. `genome wake` shows the queue.
2. `genome new {kind} --title "…" --set statement="…" --link related=<ID>` records one unit (and its edges) in one call.
3. `genome move <ID> done --evidence <path | entity id | URL>` closes it.
4. `genome graph hubs | cycles | bridges | gaps` finds structure; `genome close` checks everything.
\'\'\'

[kinds.{kind}]
path = "{name}/{kind}s"            # a directory of markdown entities; use store = "jsonl" + a .jsonl path for a volume log
id = "{pre}-{{n:04}}"
fields = {{ statement = "text!" }}   # text · int[:lo..hi] · enum:a|b|c · date · bool; a trailing ! makes it required
states = ["open", "done"]
transitions = {{ open = ["done"] }}
evidence_on = ["done"]              # moving into these needs --evidence
# human_only = ["done"]             # only a person may enter these: `--human <name>`
[kinds.{kind}.relations]
related = {{ to = "{kind}", inverse = "related-to" }}   # min / max / required_in / taint / symmetric / graph = false / default

[views.open-{kind}s]
kind = "{kind}"
state = "open"
wake = true                         # shown in `genome wake` (5 rows)

[views.{kind}-counts]
kind = "{kind}"
group_count = true
into = "docs/{name}.md#{kind}-counts"
'''


# ---- the schema-derived smoke loop

class SmokeFail(Exception):
    pass


def sample_value(spec: str, field: str) -> str:
    typ, _, arg = spec.rstrip("!").partition(":")
    if typ == "enum":
        return re.sub(r"\.\..*", "", arg) if re.fullmatch(r"-?\d+\.\.-?\d+", arg) else arg.split("|")[0]
    if typ == "int":
        return arg.split("..")[0] or "1" if arg else "1"
    return {"date": "2026-01-01", "bool": "true"}.get(typ, f"sample {field}")


def state_path(k: dict, start: str, goal) -> list[str] | None:
    """Shortest run of states from `start` to the first state for which goal(state) holds (quarantine is reachable
    from anywhere); the walk prefers real states over the quarantine exit."""
    q = k.get("quarantine")
    seen, front = {start}, [(start, [])]
    while front:
        s, path = front.pop(0)
        for t in [*k.get("transitions", {}).get(s, []), *([q] if q and s != q else [])]:
            if t in seen:
                continue
            seen.add(t)
            if goal(t):
                return path + [t]
            front.append((t, path + [t]))
    return None


def bp_check(spec: str, root: Path | None, keep: bool = False) -> int:
    """Initialise the blueprint in a scratch dir and drive the real CLI over every kind, relation, state, taint edge
    and view that the declaration implies. Returns 1 on failure. The same loop is a mechanical eval of any blueprint."""
    import tempfile, shutil
    chain = bp_chain([spec], root)
    label = chain[-1][0]
    probs = bp_problems(chain)
    if probs:
        print(f"FAIL {label}: declaration\n  " + "\n  ".join(probs))
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="genome-bp-"))
    calls = 0
    me = [sys.executable, os.path.abspath(__file__)]

    def run(*a, ok=(0,)) -> str:
        nonlocal calls
        calls += 1
        r = subprocess.run([*me, *a], cwd=tmp, capture_output=True, text=True, env={**os.environ, "GENOME_AGENT_ID": "bp-check"})
        if r.returncode not in ok:
            raise SmokeFail(f"genome {' '.join(a)}\n    exit {r.returncode}: {(r.stderr or r.stdout).strip()[:600]}")
        return r.stdout

    stats = {"entities": 0, "edges": 0, "moves": 0, "taint probes": 0}
    try:
        bp_dir = tmp / "_bp"
        bp_dir.mkdir()
        paths = []
        for n, _, text, _ in chain:
            if text:
                (bp_dir / f"{n}.toml").write_text(text)
                paths.append(str(bp_dir / f"{n}.toml"))
        run("init", "--blueprint", ",".join(paths) or label)
        cfg = find_cfg(tmp)
        specs = kind_specs(cfg)
        fresh = run("lint", ok=(0, 2))
        if "lint: clean" not in fresh:
            raise SmokeFail("a freshly initialised genome does not lint clean:\n    " + "\n    ".join(fresh.splitlines()[:6]))
        pool: dict[str, list[str]] = {}
        for e in load_entities(cfg)[0].values():
            pool.setdefault(e["kind"], []).append(e["id"])

        def targets(rs: dict) -> list[str]:
            allowed = [t for t in str(rs.get("to", "*")).split("|") if t]
            return [i for kk, ids in pool.items() if "*" in allowed or kk in allowed for i in ids]

        def need_links(k: dict, state: str | None = None) -> dict[str, list[str]]:
            out = {}
            for r, rs in k["relations"].items():
                n = max(int(rs.get("min", 0)), 1 if (state or k["initial"]) in rs.get("required_in", []) else 0)
                if n and not rs.get("default"):
                    ts = targets(rs)
                    if len(ts) < n:
                        raise SmokeFail(f"`{k['name']}` cannot be created: {r} needs {n} existing {rs.get('to')} entit(ies) and the blueprint has no seed or earlier kind to supply them")
                    out[r] = ts[:n]
            return out

        def make(kn: str, extra: dict | None = None, sets: dict | None = None) -> str:
            k = specs[kn]
            links = {**need_links(k), **(extra or {})}
            a = ["new", kn, "--title", f"smoke {kn}"]
            vals = {f: sample_value(str(sp), f) for f, sp in k["fields"].items() if str(sp).endswith("!")}
            for f, v in {**vals, **(sets or {})}.items():
                a += ["--set", f"{f}={v}"]
            for r, ids in links.items():
                a += ["--link", f"{r}={','.join(ids)}"]
            out = run(*a).split()[0]
            pool.setdefault(kn, []).append(out)
            stats["entities"] += 1
            return out

        # 1. one entity per kind, in the order their required relations allow (two where a relation needs a pair)
        want2 = {t for k in specs.values() for rs in k["relations"].values() if int(rs.get("min", 0)) > 1
                 for t in str(rs.get("to", "")).split("|")}
        todo = list(specs)
        while todo:
            progressed = False
            for kn in list(todo):
                try:
                    for _ in range(2 if kn in want2 else 1):
                        if len(pool.get(kn, [])) < (2 if kn in want2 else 1):
                            make(kn)
                    todo.remove(kn)
                    progressed = True
                except SmokeFail as ex:
                    last = ex
            if not progressed:
                raise last
        # 2. one edge per relation (the first entity of the kind, to the first other entity of an allowed kind)
        for kn, k in specs.items():
            e = pool[kn][0]
            for r, rs in k["relations"].items():
                have = {t for t in load_entities(find_cfg(tmp))[0][e]["rels"].get(r, [])}
                if have or rs.get("default"):
                    continue
                t = next((x for x in targets(rs) if x != e), None)
                if t is None:
                    t = make(next(a for a in str(rs["to"]).split("|") if a in specs and a != "*"))  # a self-targeting relation needs a second entity
                run("link", e, r, t)
                stats["edges"] += 1
        lint = run("lint", ok=(0, 2))
        errs = [ln for ln in lint.splitlines() if re.match(r"E\d", ln)]
        if errs:
            raise SmokeFail("lint after creating one entity and one edge per kind/relation:\n    " + "\n    ".join(errs[:6]))

        def walk(kn: str, goal, extra: dict | None = None, w: str | None = None) -> str:
            """A fresh entity of kind kn (or the existing `w`) moved to a state satisfying goal, evidence and sign-off
            supplied; returns its id."""
            k = specs[kn]
            start = load_entities(find_cfg(tmp))[0][w]["state"] if w else k["initial"]
            path = state_path(k, start, goal)
            if path is None:
                raise SmokeFail(f"`{kn}` has a state that cannot be reached from `{start}` by its transitions")
            w = w or make(kn, extra)
            for s in path:
                for r, rs in k["relations"].items():  # a relation required from this state on is supplied before entering it
                    if s in rs.get("required_in", []) and not load_entities(find_cfg(tmp))[0][w]["rels"].get(r):
                        ts = [x for x in targets(rs) if x != w]
                        if not ts:
                            raise SmokeFail(f"`{kn}` entering `{s}` needs {r} but no {rs.get('to')} entity exists")
                        run("link", w, r, ts[0])
                a = ["move", w, s, "--human", "bp-check"]
                if s in k.get("evidence_ref", {}):  # evidence that must be an entity of a given kind and condition
                    rk, _, cond = str(k["evidence_ref"][s]).partition("?")
                    f_, _, vals = cond.partition("=")
                    a += ["--evidence", make(rk, extra={f_: [w]}) if vals == "@self" else
                          walk(rk, lambda x, ok=vals.split("|"): x in ok) if f_ == "state" else make(rk, sets={f_: vals.split("|")[0]} if f_ else None)]
                elif s in k.get("evidence_on", []) or s == k.get("quarantine"):
                    a += ["--evidence", "genome.toml"]
                run(*a)
                stats["moves"] += 1
            return w

        # 3. every state of every kind is reached (the transition graph is a state machine that can be walked)
        for kn, k in specs.items():
            for s in k["states"]:
                if s != k["initial"]:
                    walk(kn, lambda x, s=s: x == s)
        # 4. every taint edge, as it happens in life: the target goes bad after the pointer exists. Lint flags the
        #    pointer (E510); a new pointer to it is refused on write; quarantining the pointer clears the flag.
        for kn, k in specs.items():
            for r, rs in k["relations"].items():
                if not rs.get("taint"):
                    continue
                tkn = next((t for t in str(rs["to"]).split("|") if t in specs and set(rs["taint"]) & set(specs[t]["states"])), None)
                if tkn is None:
                    continue
                ts, q = next(s for s in rs["taint"] if s in specs[tkn]["states"]), k["quarantine"]
                target = make(tkn)
                src = make(kn, {r: [target]})
                if k["initial"] == q:  # a pointer that starts in quarantine is exempt: take it out first
                    walk(kn, lambda x, q=q: x != q, w=src)
                walk(tkn, lambda x, ts=ts: x == ts, w=target)
                out = run("lint", ok=(0, 2))
                if not any(ln.startswith("E510") and src in ln for ln in out.splitlines()):
                    raise SmokeFail(f"taint: {src} ({kn}.{r}) points at {target} in `{ts}` but lint did not flag it (E510)")
                if src not in run("impact", target, "--to", ts):
                    raise SmokeFail(f"impact: `genome impact {target} --to {ts}` does not list {src}, which lint flags")
                if k["initial"] != q:
                    try:
                        make(kn, {r: [target]})
                        raise SmokeFail(f"taint: a new {kn} was created pointing at {target} in `{ts}`; it should be refused")
                    except SmokeFail as ex:
                        if "should be refused" in str(ex):
                            raise
                run("move", src, q, "--evidence", target)
                if any(ln.startswith("E510") and src in ln for ln in run("lint", ok=(0, 2)).splitlines()):
                    raise SmokeFail(f"taint: {src} was quarantined but lint still flags it")
                stats["taint probes"] += 1
        lint = run("lint", ok=(0, 2))
        errs = [ln for ln in lint.splitlines() if re.match(r"E\d", ln)]
        if errs:
            raise SmokeFail("lint after walking every state:\n    " + "\n    ".join(errs[:6]))
        # 5. views, graph, search, orientation
        run("emit")
        for v in cfg.views:
            run("view", v)
        run("graph", "hubs")
        run("place", "smoke test of the blueprint")
        run("index", "--rebuild")
        wake = run("wake")
        run("close", "--no-gate", ok=(0, 2))
    except SmokeFail as ex:
        print(f"FAIL {label}: {ex}" + f"\n    (scratch genome kept: {tmp})")
        return 1
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"PASS {label}: {len(specs)} kinds, {sum(len(k['relations']) for k in specs.values())} relations, "
          f"{sum(len(k['states']) for k in specs.values())} states ({stats['moves']} moves), {stats['taint probes']} taint probe(s), "
          f"{len(cfg.views)} views; {calls} CLI calls; wake {len(wake)} bytes (~{len(wake) // 4} tokens)"
          + (f"\n    scratch genome kept: {tmp}" if keep else ""))
    return 0
