# ---------------------------------------------------------------- outline

# The stack outline: facts derived from the tree, written into a generated zone in
# `AGENTS.md`, with the prose owned by a hand-written `docs/OUTLINE.md`.
#
# WHY IT IS A MODULE OF ITS OWN AND NOT SIX MORE FILES IN CORE. A records-only
# knowledge base is not forced to carry a stack table it will never refresh; the
# zone is registered like every other zone, and `genome lint` fails it when stale
# by the same E104 rule the records zones use. No new mechanism.
#
# THE ONE RULE: every row is derived, and a fact with no source is printed as
# "not derivable" rather than guessed. This is not fastidiousness. The sentence
# this module exists to prevent was "the interaction-surfaces family is all
# Python", written about a family whose largest member is Rust; nothing in the
# pipeline was positioned to notice, because the claim was asserted in prose by
# something that had read a directory listing. Read the manifest, never the name.

OUTLINE_ZONE = "stack"
OUTLINE_MANIFESTS = (("Cargo.toml", "rust"), ("pyproject.toml", "python"),
                     ("package.json", "javascript"), ("go.mod", "go"))
# Never a source tree: build output, vendored code, data. A count that includes
# them is a number the repository cannot reproduce from a clean clone.
OUTLINE_NOT_SRC = {"node_modules", "dist", "build", "target", "vendor", "uploads",
                   "probe-out", "samples", "assets", ".git", "__pycache__"}
OUTLINE_EXTS = {".rs": "rust", ".py": "python", ".go": "go",
                ".ts": "typescript", ".tsx": "typescript", ".js": "javascript"}


def o_lang(root: Path) -> tuple[str, str]:
    p = next((f for f, _ in OUTLINE_MANIFESTS if (root / f).is_file()), None)
    if not p:
        return "not derivable", "no manifest (Cargo.toml / pyproject.toml / package.json / go.mod)"
    lang = dict(OUTLINE_MANIFESTS)[p]
    # A package.json cannot say TypeScript from JavaScript, and that guess is the
    # same failure as the language guess above. tsconfig.json is the discriminator.
    if p == "package.json" and (root / "tsconfig.json").is_file():
        return "typescript", "package.json + tsconfig.json"
    return lang, p


def o_src(root: Path) -> tuple[list[str], str]:
    """(source dirs, entry point). The declared package wins over a conventional name:
    meesho-lyr's package is `meesho_cli/`, and probing only `src/` would report a
    2,000-file Python project as having no source at all."""
    out: list[str] = []
    pyp = root / "pyproject.toml"
    if pyp.is_file():
        t = read(pyp)
        for m in re.finditer(r'include\s*=\s*\[([^\]]*)\]|^\s*packages\s*=\s*\[([^\]]*)\]', t, re.M | re.S):
            for c in re.findall(r'"([^"]+)"', m.group(1) or m.group(2) or ""):
                d = c.rstrip("*").replace(".", "/")
                if (root / d).is_dir() and d not in out:
                    out.append(d)
        n = re.search(r'^name\s*=\s*"([^"]+)"', t, re.M)  # usually named after its package
        if n and (root / n.group(1).replace("-", "_")).is_dir():
            d = n.group(1).replace("-", "_")
            if d not in out:
                out.append(d)
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        n = re.search(r'^\s*(?:name|path)\s*=\s*"([^"]+)"', read(cargo), re.M)
        if n and (root / n.group(1)).is_dir() and n.group(1) not in out:
            out.append(n.group(1))
    pj = root / "package.json"
    if pj.is_file():
        m = re.search(r'"(?:main|bin)"\s*:\s*"([^"]+)"', read(pj))
        if m and "/" in m.group(1):
            d = m.group(1).rsplit("/", 1)[0]
            if (root / d).is_dir() and d not in OUTLINE_NOT_SRC and d not in out:
                out.append(d)
    for d in ("src", "lib", "crates", "cmd", "skills"):  # conventional, never instead of
        if (root / d).is_dir() and d not in OUTLINE_NOT_SRC and d not in out:
            out.append(d)
    entry = next((f"{d}/{c}" for d in out for c in ("__init__.py", "lib.rs", "main.rs", "index.ts", "mod.rs")
                  if (root / d / c).is_file()), "")
    return out, entry


def o_size(root: Path, src: list[str]) -> list[tuple[str, int]]:
    n: dict[str, int] = {}
    for d in src:
        for p in (root / d).rglob("*"):
            if p.is_file() and not any(x in OUTLINE_NOT_SRC for x in p.parts) and p.suffix in OUTLINE_EXTS:
                n[OUTLINE_EXTS[p.suffix]] = n.get(OUTLINE_EXTS[p.suffix], 0) + 1
    return sorted(n.items(), key=lambda kv: -kv[1])


def o_gate(root: Path) -> str:
    m = re.search(r'^\s*gate\s*=\s*"([^"]+)"', read(root / "genome.toml"), re.M)  # the KB's own setting first
    if m:
        return m.group(1)
    return next((g for f, g in (("Cargo.toml", "cargo test --locked"), ("pyproject.toml", "pytest -q"),
                                ("package.json", "npm test"), ("go.mod", "go test ./..."))
                 if (root / f).is_file()), "not derivable")


def o_deps(root: Path) -> list[str]:
    out: list[str] = []
    t = read(root / "Cargo.toml")
    out += re.findall(r'^([A-Za-z0-9_.-]+)\s*=', re.search(r'\[dependencies\](.*?)(?:\n\[|\Z)', t, re.S).group(1), re.M) \
        if re.search(r'\[dependencies\]', t) else []
    m = re.search(r'dependencies\s*=\s*\[(.*?)\]', read(root / "pyproject.toml"), re.S)
    if m:
        # Requirement NAMES, not specs: splitting `click>=8.1, rich` on the comma
        # is what leaves a bare "," in the table as a row.
        for spec in re.findall(r'"([^"]+)"', m.group(1)):
            name = re.split(r"[<>=!~\s;\[]", spec.strip(), maxsplit=1)[0]
            if re.fullmatch(r"[A-Za-z0-9_.-]+", name or ""):
                out.append(name)
    pj = read(root / "package.json")
    out += re.findall(r'"([^"@\s/][\w./-]*)"\s*:', re.search(r'"dependencies"\s*:\s*\{(.*?)\}', pj, re.S).group(1)) \
        if re.search(r'"dependencies"', pj) else []
    return sorted(set(out))


def o_wiring(root: Path, src: list[str]) -> list[tuple[str, str]]:
    if not src:
        return []
    base = src[0]
    top = root / base
    local = {p.stem for p in top.glob("*.py")} | {p.stem for p in top.glob("*.rs")} | {p.stem for p in top.glob("*.ts")}
    edges: set[tuple[str, str]] = set()
    for p in top.rglob("*"):
        if not p.is_file() or p.suffix not in (".py", ".rs", ".ts") or p.name.startswith("__"):
            continue
        t = read(p)
        for m in re.finditer(r'^\s*(?:from|import)\s+\.([\w.]*)', t, re.M):  # python relative
            d = m.group(1).lstrip(".").replace(".", "/")
            if d.split("/")[-1] in local:
                edges.add((f"{base}/{p.stem}", f"{base}/{d}"))
        for m in re.finditer(r'^\s*(?:pub(?:\s+\(\w+\))?\s+)?(?:use|mod)\s+(?:crate::)?(\w+)', t, re.M):  # rust
            if m.group(1) in local:
                edges.add((f"{base}/{p.stem}", f"{base}/{m.group(1)}"))
        for m in re.finditer(r'from\s+["\']\./([\w./-]+)["\']', t):  # ts relative
            edges.add((f"{base}/{p.stem}", f"{base}/{m.group(1).removesuffix('.js')}"))
    return sorted(edges)


def outline_body(cfg: Cfg) -> str:
    """Derived facts, and nothing that changes without the facts changing.

    There is deliberately NO timestamp and NO commit sha in this zone. A generated file
    whose stamp changes on every emit reports a diff every time, which trains a reader to
    skip past it; and a stamp that moves when the tree does not - a sha after a commit,
    a clock across a midnight - makes `genome outline-check` fail on a tree that has not
    changed. The zone re-derives from the tree each run, so the body itself is the
    freshness proof: it differs only when the repository differs.
    """
    r = cfg.root
    lang, ev = o_lang(r)
    src, entry = o_src(r)
    deps = o_deps(r)
    edges = o_wiring(r, src)
    L = ["**Generated by `genome outline` from the tree. Facts only — how the parts fit "
         "together is in `docs/OUTLINE.md`.**", "",
         f"### Language and layout — read from `{ev}`, not from the directory name", "",
         "| fact | value |", "|---|---|", f"| language | `{lang}` |",
         f"| source | {' · '.join(f'`{d}/`' for d in src) or 'not derivable'} |",
         f"| entry point | `{entry or 'not derivable'}` |", "",
         "### Size — files under the source dirs, excluding build output and vendored code", "",
         "| language | files |", "|---|---|"]
    L += [f"| {l} | {n} |" for l, n in o_size(r, src)] or ["| — | none found |"]
    L += ["", f"### Gate — `{cfg.paths['agents']}` declares it, or it is probed from the manifest", "",
          "```", o_gate(r), "```", ""]
    L += ["### Dependencies — direct, from the manifests", "", "| package |", "|---|"]
    L += [f"| `{d}` |" for d in deps] or ["| none declared |"]
    L += ["", "### Wiring — one row per internal import edge", "", "| from | to |", "|---|---|"]
    L += [f"| `{a}` | `{b}` |" for a, b in edges] or ["| — | no internal edges |"]
    return "\n".join(L) + "\n"


def outline_targets(cfg: Cfg) -> list[str]:
    return [cfg.paths["agents"]]


def emit_outline(cfg: Cfg) -> list[str]:
    changed = []
    for t in outline_targets(cfg):
        if not (cfg.root / t).is_file():
            continue  # `genome init` writes it; a KB without one has nowhere to put the zone
        if write_zone(cfg.root / t, OUTLINE_ZONE, outline_body(cfg)):
            changed.append(f"{t}#{OUTLINE_ZONE}")
    return changed


def outline_stale(cfg: Cfg) -> list[str]:
    """Which targets' zones differ from what the tree derives NOW — read-only.

    A check that writes is not a check: `genome outline-check` in a gate would repair the
    drift it was asked to report, and the next command would see a clean tree and pass.
    So this computes the body and compares bytes, the same way `genome lint`'s E104 does
    for the records zones.
    """
    out = []
    for t in outline_targets(cfg):
        p = cfg.root / t
        if not p.is_file():
            continue
        body = outline_body(cfg)
        got = zones(read(p)).get(OUTLINE_ZONE)
        if got is None or got[1] != body:
            out.append(f"{t}#{OUTLINE_ZONE}" + ("" if got is None else " (hand-edited or the tree moved)"))
    return out


def cmd_outline(args) -> None:
    ch = emit_outline(find_cfg())
    print(f"outline: {', '.join(ch)}" if ch else f"outline: {OUTLINE_ZONE} already current")


def cmd_outline_check(args) -> None:
    bad = outline_stale(find_cfg())
    if bad:
        print(f"outline: STALE — {', '.join(bad)}  (run `genome outline`)")
        raise SystemExit(ERR)
    print(f"outline: {OUTLINE_ZONE} current")
