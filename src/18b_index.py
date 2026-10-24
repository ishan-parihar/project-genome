# ---------------------------------------------------------------- index and graph

# `.genome/index.db` is a cache: sections (FTS5, BM25), entities and typed edges, rebuilt incrementally from content
# hashes. Delete it and the next command rebuilds it identically. Nothing here is a source of truth.

INDEX_VERSION = 1


def index_path(cfg: Cfg) -> Path:
    return cfg.root / ".genome" / "index.db"


def open_index(cfg: Cfg):
    import sqlite3
    p = index_path(cfg)
    p.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(p)
    if con.execute("pragma user_version").fetchone()[0] != INDEX_VERSION:
        for t in ("docs", "sec", "ent", "ent_fts", "edges"):
            con.execute(f"drop table if exists {t}")
        con.execute(f"pragma user_version = {INDEX_VERSION}")
    con.executescript("""
        create table if not exists docs(path text primary key, sha text, kind text);
        create virtual table if not exists sec using fts5(path unindexed, heading, body, a unindexed, b unindexed,
                                                           tokenize='porter unicode61');
        create table if not exists ent(id text primary key, kind text, state text, title text, path text);
        create virtual table if not exists ent_fts using fts5(id unindexed, kind unindexed, title, body, tokenize='porter unicode61');
        create table if not exists edges(src text, rel text, dst text, path text);
        create table if not exists vec(sid integer primary key, v text);
        create index if not exists edges_src on edges(src);
        create index if not exists edges_dst on edges(dst);
    """)
    return con


def file_sha(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def refresh_index(cfg: Cfg, con) -> dict:
    """Bring the cache in line with the working tree. Only changed files are re-read."""
    stats = {"sections": 0, "entities": 0, "removed": 0, "embedded": 0}
    have = dict(con.execute("select path, sha from docs"))
    live: dict[str, tuple[Path, str]] = {}
    for f in corpus(cfg):
        live[cfg.rel(f)] = (f, "doc")
    specs = kind_specs(cfg)
    for k in specs.values():
        d = kind_dir(cfg, k)
        for f in ([d] if k["store"] == "jsonl" and d.is_file() else sorted(d.glob("*.md")) if d.is_dir() else []):
            live[cfg.rel(f)] = (f, f"kind:{k['name']}")
    for rel in set(have) - set(live):
        drop_doc(con, rel)
        stats["removed"] += 1
    for rel, (f, kind) in live.items():
        sha = file_sha(f)
        if have.get(rel) == sha:
            continue
        drop_doc(con, rel)
        if kind == "doc":
            for h, a, b, body in chunks(f):
                con.execute("insert into sec(path, heading, body, a, b) values (?,?,?,?,?)", (rel, h, body, a, b))
                stats["sections"] += 1
        else:
            k = specs[kind.split(":", 1)[1]]
            es = list(fold_jsonl(k, f)[0].values()) if k["store"] == "jsonl" else [e for e in [parse_dir_entity(k, f)] if e]
            for e in es:
                body = " ".join([e["title"], *map(str, e["fields"].values())]) + " " + (read(f) if k["store"] == "dir" else e["body"])
                con.execute("insert or replace into ent values (?,?,?,?,?)", (e["id"], e["kind"], e["state"], e["title"], rel))
                con.execute("insert into ent_fts(id, kind, title, body) values (?,?,?,?)", (e["id"], e["kind"], e["title"], body))
                for r, tos in e["rels"].items():
                    con.executemany("insert into edges values (?,?,?,?)", [(e["id"], r, t, rel) for t in tos])
                stats["entities"] += 1
        con.execute("insert or replace into docs values (?,?,?)", (rel, sha, kind))
    if cfg.get("index", "embed"):  # embed every section that has no vector yet (new, changed, or the hook was just set)
        todo = con.execute("select sec.rowid, sec.body from sec left join vec on vec.sid = sec.rowid "
                           "where vec.sid is null").fetchall()
        for sid, vec in embed_texts(cfg, [(str(s), b) for s, b in todo]).items():
            con.execute("insert into vec(sid, v) values (?, ?)", (int(sid), json.dumps([round(x, 5) for x in vec])))
            stats["embedded"] += 1
    con.commit()
    return stats


def drop_doc(con, rel: str) -> None:
    con.execute("delete from vec where sid in (select rowid from sec where path = ?)", (rel,))
    con.execute("delete from sec where path = ?", (rel,))
    ids = [r[0] for r in con.execute("select id from ent where path = ?", (rel,))]
    for i in ids:
        con.execute("delete from ent_fts where id = ?", (i,))
    con.execute("delete from ent where path = ?", (rel,))
    con.execute("delete from edges where path = ?", (rel,))
    con.execute("delete from docs where path = ?", (rel,))


def fts_query(text: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in STOP and (len(w) > 2 or w.isupper() or w.isdigit())]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


def embed_texts(cfg: Cfg, items: list[tuple[str, str]]) -> dict[str, list[float]]:
    """The optional `[index] embed` hook: a command that reads JSON lines {"id","text"} on stdin and answers JSON lines
    {"id","vec"} on stdout, one per input. The kernel stays stdlib-only; without the hook the index is lexical."""
    cmd = cfg.get("index", "embed", "")
    if not cmd or not items:
        return {}
    inp = "".join(json.dumps({"id": i, "text": t}) + "\n" for i, t in items)
    r = subprocess.run(cmd, shell=True, cwd=cfg.root, input=inp, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"[index] embed hook failed ({r.returncode}): {r.stderr.strip()[:300]}", ERR)
    out = {}
    for line in r.stdout.splitlines():
        if line.strip():
            o = json.loads(line)
            out[o["id"]] = o["vec"]
    if any(i not in out for i, _ in items):
        die(f"[index] embed hook returned no vector for {sum(i not in out for i, _ in items)} input(s)", ERR)
    return out


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def index_ask(cfg: Cfg, question: str, k: int = 6) -> tuple[list[tuple[float, Path, str, int, int, str]], list[dict]]:
    """BM25 over sections (heading weighted 3x) plus the nearest entities. With an embed hook, the BM25 pool is
    re-ranked by cosine. Same tuple shape as `ask_rank`."""
    con = open_index(cfg)
    refresh_index(cfg, con)
    q = fts_query(question)
    if not q:
        return [], []
    rows = con.execute("select rowid, bm25(sec, 0.0, 3.0, 1.0), path, heading, a, b, body from sec where sec match ? "
                       "order by 2 limit ?", (q, max(k * 8, 40) if cfg.get("index", "embed") else k)).fetchall()
    hits = [(-s, cfg.root / p, h, int(a), int(b), body) for _, s, p, h, a, b, body in rows]
    if cfg.get("index", "embed") and rows:
        qv = embed_texts(cfg, [("q", question)])["q"]
        vecs = dict(con.execute(f"select sid, v from vec where sid in ({','.join('?' * len(rows))})",
                                [r[0] for r in rows]).fetchall())
        ranked = sorted(((cosine(qv, json.loads(vecs[r[0]])), h) for r, h in zip(rows, hits) if r[0] in vecs),
                        key=lambda t: -t[0])
        hits = [(round(c, 4), *h[1:]) for c, h in ranked[:k]]
    ents = [{"id": i, "kind": kd, "title": t, "score": round(-s, 1)} for s, i, kd, t in con.execute(
        "select bm25(ent_fts, 0.0, 0.0, 4.0, 1.0), id, kind, title from ent_fts where ent_fts match ? order by 1 limit ?", (q, k))]
    return hits, ents


# ---- graph (undirected unless noted; edges are stored forward once)

def load_graph(cfg: Cfg) -> tuple[dict[str, dict], dict[str, set[str]], dict[str, set[str]], list[tuple[str, str, str]]]:
    """(entity info by id, undirected adjacency, directed adjacency, edges) from the index."""
    con = open_index(cfg)
    refresh_index(cfg, con)
    info = {i: {"kind": k, "state": s, "title": t} for i, k, s, t in con.execute("select id, kind, state, title from ent")}
    specs = kind_specs(cfg)

    def rel(s: str, r: str) -> dict:
        return specs.get(info[s]["kind"], {}).get("relations", {}).get(r, {})
    # a quarantined entity (retracted, tainted: not its initial state) is not relied on, so it bridges nothing
    dead = {i for i, v in info.items() if (k := specs.get(v["kind"], {})).get("quarantine")
            and v["state"] == k["quarantine"] and v["state"] != k.get("initial")}
    # `graph = false` edges (membership, provenance) are stored and linted but are not topology
    edges = [(s, r, d) for s, r, d in con.execute("select src, rel, dst from edges")
             if s in info and d in info and s not in dead and d not in dead and rel(s, r).get("graph", True) is not False]
    und: dict[str, set[str]] = {i: set() for i in info}
    out: dict[str, set[str]] = {i: set() for i in info}
    for s, r, d in edges:
        und[s].add(d); und[d].add(s)
        if not rel(s, r).get("symmetric"):  # a symmetric relation has no direction, so it cannot close a loop
            out[s].add(d)
    return info, und, out, edges


def project(info: dict[str, dict], und: dict[str, set[str]], out: dict[str, set[str]], kind: str):
    """The graph seen from one kind: two K nodes are adjacent when linked directly or through one non-K node
    (concept — claim — concept). The usual input to ABC discovery."""
    keep = {i for i in info if info[i]["kind"] == kind}

    def hop(adj, a):
        near = {b for b in adj[a] if b in keep}
        near |= {b for m in adj[a] if m not in keep for b in adj[m] if b in keep}
        return near - {a}
    return ({i: info[i] for i in keep}, {a: hop(und, a) for a in keep}, {a: hop(out, a) for a in keep})


def namespaces(cfg: Cfg, info: dict[str, dict], across: str) -> dict[str, str]:
    """Each node's namespace: the first target of relation `across` (a node that is such a target is its own
    namespace), else the value of field `across`. Nodes with neither have none and never count as crossing."""
    specs = kind_specs(cfg)
    if any(across in k["relations"] for k in specs.values()):
        ns: dict[str, str] = {}
        for s, d in open_index(cfg).execute("select src, dst from edges where rel = ? order by rowid", (across,)):
            ns.setdefault(s, d)
            ns.setdefault(d, d)
        return ns
    if not any(across in k["fields"] for k in specs.values()):
        die(f"--across `{across}` is neither a relation nor a field of any kind")
    ents, _ = load_entities(cfg)
    return {i: e["fields"][across] for i, e in ents.items() if i in info and e["fields"].get(across)}


def bfs_path(adj: dict[str, set[str]], a: str, b: str) -> list[str] | None:
    prev, queue = {a: None}, [a]
    for n in queue:
        if n == b:
            path = []
            while n is not None:
                path.append(n); n = prev[n]
            return path[::-1]
        for m in sorted(adj.get(n, ())):
            if m not in prev:
                prev[m] = n; queue.append(m)
    return None


def betweenness(adj: dict[str, set[str]]) -> dict[str, float]:
    """Brandes. Exact up to a few thousand nodes; callers cap the node count."""
    bc = {v: 0.0 for v in adj}
    for s in adj:
        stack, pred, sigma, dist, q = [], {v: [] for v in adj}, dict.fromkeys(adj, 0), dict.fromkeys(adj, -1), [s]
        sigma[s], dist[s] = 1, 0
        for v in q:
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1; q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]; pred[w].append(v)
        delta = dict.fromkeys(adj, 0.0)
        for w in reversed(stack):
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    return {v: b / 2 for v, b in bc.items()}


def find_bridges(adj: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Edges whose removal disconnects their component (iterative Tarjan low-link)."""
    disc, low, out, t = {}, {}, [], 0
    for root in adj:
        if root in disc:
            continue
        disc[root] = low[root] = t = t + 1
        stack = [(root, None, iter(sorted(adj[root])))]
        while stack:
            v, parent, it = stack[-1]
            for w in it:
                if w == parent:
                    continue
                if w in disc:
                    low[v] = min(low[v], disc[w])
                else:
                    disc[w] = low[w] = t = t + 1
                    stack.append((w, v, iter(sorted(adj[w]))))
                    break
            else:
                stack.pop()
                if stack:
                    u = stack[-1][0]
                    low[u] = min(low[u], low[v])
                    if low[v] > disc[u]:
                        out.append((u, v))
    return out


def find_cycles(out: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components of size > 1 (and self-loops) in the directed graph: knots that feed themselves."""
    index, low, on, stack, res, counter = {}, {}, set(), [], [], [0]

    def strong(v):
        work = [(v, iter(sorted(out[v])))]
        index[v] = low[v] = counter[0]; counter[0] += 1; stack.append(v); on.add(v)
        while work:
            u, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1; stack.append(w); on.add(w)
                    work.append((w, iter(sorted(out[w]))))
                    break
                elif w in on:
                    low[u] = min(low[u], index[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[u])
                if low[u] == index[u]:
                    comp = []
                    while True:
                        w = stack.pop(); on.discard(w); comp.append(w)
                        if w == u:
                            break
                    if len(comp) > 1 or u in out[u]:
                        res.append(sorted(comp))

    for v in sorted(out):
        if v not in index:
            strong(v)
    return res


def open_triads(und: dict[str, set[str]], limit: int, keep=None) -> list[tuple[str, str, list[str]]]:
    """Pairs (A, C) with no edge between them that share neighbours B: the unseen connection worth testing (ABC discovery)."""
    shared: dict[tuple[str, str], list[str]] = {}
    for b, ns in und.items():
        ns = sorted(ns)
        for i, a in enumerate(ns):
            for c in ns[i + 1:]:
                if c not in und[a] and (keep is None or keep(a, c)):
                    shared.setdefault((a, c), []).append(b)
    ranked = sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [(a, c, bs) for (a, c), bs in ranked[:limit]]


def label(info: dict[str, dict], i: str) -> str:
    return f"{i} {info[i]['title'][:50]}".rstrip() if i in info else i


def cmd_graph(args) -> None:
    cfg = find_cfg()
    if not cfg.kinds:
        die("no kinds declared — graph queries run over typed entities (see [kinds.*] in genome.toml)")
    info, und, out, edges = load_graph(cfg)
    if args.kind:
        if args.kind not in kind_specs(cfg):
            die(f"no kind `{args.kind}`")
        info, und, out = project(info, und, out, args.kind)
    ns = namespaces(cfg, info, args.across) if args.across else {}

    def crosses(a: str, b: str) -> bool:
        return not args.across or (a in ns and b in ns and ns[a] != ns[b])
    q = args.query
    res: object
    if q in ("neighbors", "path"):
        if args.a not in info:
            die(f"no entity `{args.a}`" + (f" of kind `{args.kind}`" if args.kind else ""))
    if q == "neighbors":
        seen, frontier, layers = {args.a}, [args.a], []
        for _ in range(args.depth):
            nxt = sorted({m for n in frontier for m in und[n]} - seen)
            seen |= set(nxt); frontier = nxt
            layers.append(nxt)
        res = {"id": args.a, "layers": layers}
        text = [f"depth {d + 1}: " + ", ".join(label(info, i) for i in ly) for d, ly in enumerate(layers) if ly] or ["(isolated)"]
    elif q == "path":
        if not args.b or args.b not in info:
            die("path needs two entity ids: graph path <a> <b>")
        p = bfs_path(und, args.a, args.b)
        res, text = {"path": p}, [" → ".join(label(info, i) for i in p) if p else "no path"]
    elif q == "hubs":
        # Betweenness is Brandes, O(V·E); past HUB_NODE_CAP it would block for many seconds on a large
        # map, so degree still ranks the hubs and the column reports 0.0 rather than blocking. Saying so
        # matters: a silent 0.0 reads as "nothing passes through here", which is a different claim from
        # "not computed". The flag rides along in the JSON rows too, so a caller cannot read the zero
        # as a measurement.
        capped = len(und) > HUB_NODE_CAP
        bc = dict.fromkeys(und, 0.0) if capped else betweenness(und)
        cross = {i: sum(1 for m in und[i] if crosses(i, m)) for i in und}
        pool = [i for i in und if cross[i]] if args.across else [i for i in und if und[i]]  # a node with no edges is no hub
        rows = sorted(pool, key=lambda i: (-cross[i], -len(und[i]), -bc[i], i) if args.across else (-len(und[i]), -bc[i], i))[:args.top]
        res = [{"id": i, "degree": len(und[i]), "betweenness": round(bc[i], 1), **({"across": cross[i]} if args.across else {}), **({"capped": True} if capped else {})} for i in rows]
        # `--kind` only helps when the projection actually shrinks: on a map that is one kind it does
        # not, so name the two ways that do rather than promising the one that may not.
        hint = (f"narrow it: `--kind <k>` (if several kinds are present) or `--across <relation>`, "
                f"or raise HUB_NODE_CAP") if capped else ""
        note = f"{len(und)} nodes: betweenness not computed above {HUB_NODE_CAP} — ranked by degree only; " + hint
        text = [note] if capped else []
        text += [(f"across {cross[i]:3} " if args.across else "") + f"deg {len(und[i]):3} btw {bc[i]:7.1f}  {label(info, i)}" for i in rows]
    elif q == "cycles":
        cs = [c for c in find_cycles(out) if not args.across or len({ns.get(i) for i in c} - {None}) > 1]
        res, text = cs, [" ⟲ ".join(c) for c in cs] or ["no cycles"]
    elif q == "bridges":
        bs = [(a, b) for a, b in find_bridges(und) if crosses(a, b)]
        res, text = bs, [f"{label(info, a)} — {label(info, b)}" for a, b in bs] or ["no bridges"]
    elif q == "gaps":
        tr = open_triads(und, args.top, crosses if args.across else None)
        res = [{"a": a, "c": c, "via": bs} for a, c, bs in tr]
        text = [f"{label(info, a)}  ?—?  {label(info, c)}   via {', '.join(bs[:4])}" for a, c, bs in tr] or ["no open triads"]
    else:
        die("graph query: neighbors | path | hubs | cycles | bridges | gaps")
    if args.json:
        jprint(res)
    else:
        print("\n".join(text))


def cmd_place(args) -> None:
    """Where does this text land: candidate kinds, nearest entities, proposed edges. Nothing is written."""
    cfg = find_cfg()
    text = " ".join(args.text)
    con = open_index(cfg)
    refresh_index(cfg, con)
    q = fts_query(text)
    near = [(round(-s, 1), i, kd, st, t) for s, i, kd, st, t in con.execute(
        "select bm25(ent_fts, 0.0, 0.0, 4.0, 1.0), ent_fts.id, ent_fts.kind, ent.state, ent_fts.title from ent_fts "
        "join ent on ent.id = ent_fts.id where ent_fts match ? order by 1 limit ?", (q, args.k))] if q else []
    secs = [(cfg.rel(p), a, h) for _, p, h, a, _, _ in index_ask(cfg, text, 2)[0]] if q else []
    kinds: dict[str, float] = {}
    for s, _, kd, _, _ in near:
        kinds[kd] = kinds.get(kd, 0) + s
    specs = kind_specs(cfg)
    ranked = sorted(kinds, key=lambda x: -kinds[x])
    # proposed edges: for each declared kind, relations whose allowed targets include a nearby entity's kind
    props = []
    for name, k in specs.items():
        for r, rs in k["relations"].items():
            allowed = [t for t in str(rs.get("to", "*")).split("|") if t]
            for s, i, kd, _, t in near[:5]:
                if "*" in allowed or kd in allowed:
                    props.append({"if_new_kind": name, "relation": r, "target": i, "target_title": t})
    out = {"candidate_kinds": ranked or list(specs), "nearest": [{"id": i, "kind": kd, "state": st, "title": t, "score": s}
                                                                   for s, i, kd, st, t in near],
           "sections": [{"path": p, "line": a, "heading": h} for p, a, h in secs],
           "proposed_edges": [p for p in props if not ranked or p["if_new_kind"] == ranked[0]][:8]}
    if args.json:
        jprint(out)
        return
    print("candidate kinds: " + ", ".join(out["candidate_kinds"]))
    for n in out["nearest"]:
        print(f"  near {n['score']:6.1f}  {n['id']} [{n['state']}] {n['title'][:60]}")
    for s in out["sections"]:
        print(f"  doc  {s['path']}:{s['line']}  § {s['heading'][:60]}")
    by_target: dict[tuple, list[str]] = {}
    for p in out["proposed_edges"]:  # one line per nearby entity, the candidate relations joined
        by_target.setdefault((p["if_new_kind"], p["target"], p["target_title"]), []).append(p["relation"])
    for (kd, tid, ttl), rels in by_target.items():
        print(f"  edge: new {kd} → {tid} ({ttl[:40]}) via {' | '.join(rels)}")
    print("then: `genome new <kind> …` and `genome link <new> <relation> <target>`")


def cmd_index(args) -> None:
    cfg = find_cfg()
    if args.rebuild:
        index_path(cfg).unlink(missing_ok=True)
    con = open_index(cfg)
    st = refresh_index(cfg, con)
    n = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in ("docs", "sec", "ent", "edges")}
    print(f"index: {n['docs']} files · {n['sec']} sections · {n['ent']} entities · {n['edges']} edges "
          f"(this run: +{st['sections']} sections, +{st['entities']} entities, -{st['removed']} files"
          + (f", {st['embedded']} embedded" if st["embedded"] else "") + f") — {cfg.rel(index_path(cfg))}")


def cmd_impact(args) -> None:
    """What would moving <id> into a taint state flag? Follows the cascade one hop at a time: a pointer that lint would
    flag is assumed quarantined before the next hop, which is how the cascade runs in life. Reads only; writes nothing."""
    cfg = find_cfg()
    specs, (ents, _) = kind_specs(cfg), load_entities(cfg)
    if args.id not in ents:
        die(f"no entity `{args.id}`")
    root_kind = ents[args.id]["kind"]
    pointing = [(k, r, rs) for k in specs.values() for r, rs in k["relations"].items()
                if rs.get("taint") and (root_kind in str(rs.get("to", "")).split("|") or "*" in str(rs.get("to", "")))]
    state = args.to
    if not state:
        options = sorted({s for _, _, rs in pointing for s in rs["taint"] if s in specs[root_kind]["states"]})
        if len(options) != 1:
            die(f"`{root_kind}` can be tainted into {options or 'no state'}; say which: `genome impact {args.id} --to <state>`")
        state = options[0]
    elif specs[root_kind]["states"] and state not in specs[root_kind]["states"]:
        die(f"`{state}` is not a state of `{root_kind}` ({', '.join(specs[root_kind]['states'])})")
    hops, seen, frontier = [], {args.id}, [(args.id, state)]
    while frontier:
        found: dict[tuple[str, str], list[str]] = {}  # (state to move into, tainting id) → pointers
        nxt = []
        for tid, st in frontier:
            for e in ents.values():
                k = specs[e["kind"]]
                if e["id"] in seen or e["state"] == k.get("quarantine"):
                    continue
                if any(tid in e["rels"].get(r, []) and st in rs.get("taint", []) for r, rs in k["relations"].items()):
                    seen.add(e["id"])
                    found.setdefault((k.get("quarantine") or "(no quarantine state: unlink it)", tid), []).append(e["id"])
                    if k.get("quarantine"):
                        nxt.append((e["id"], k["quarantine"]))
        if not found:
            break
        hops.append(found)
        frontier = nxt
    if args.json:
        jprint({"id": args.id, "to": state, "hops": [[{"move_to": s, "evidence": t, "ids": ids} for (s, t), ids in h.items()] for h in hops]})
        return
    n = sum(len(i) for h in hops for i in h.values())
    print(f"impact of {args.id} → {state}: " + (f"{n} entit{'y' if n == 1 else 'ies'} flagged over {len(hops)} hop(s); nothing is changed by this command" if n else "nothing depends on it"))
    for i, h in enumerate(hops, 1):
        print(f"hop {i}" + ("" if i == 1 else f" (after hop {i - 1} is quarantined)"))
        for (s, t), ids in h.items():
            print(f"  {','.join(ids)}  →  genome move {','.join(ids)} {s} --evidence {t}" if s[0] != "(" else f"  {','.join(ids)}  {s}")
