# ---------------------------------------------------------------- pointers

PTR_BAD = re.compile(r"[<>{}*$…]|\.\.\.|NNNN|://|^[-~/]")


FILE_EXT = r"\.(?:md|toml|json|jsonl|yaml|yml|py|sh|txt|csv|mqh|mq5|rs|ts|js|go)"


def pointers(text: str, ignore: set[str], prefixes: tuple[str, ...] = ()) -> list[tuple[int, str]]:
    """Backticked pointers per line: (line, path). A pointer is file-shaped
    (`dir/name.ext` or `name.ext`), or starts with one of `prefixes` (then any
    path shape counts, directories included). Globs, placeholders, URLs, git
    refs (`origin/main`), flags and out-of-repo paths are prose."""
    out = []
    for n, ln in enumerate(text.splitlines(), 1):
        for tok in re.findall(r"`([^`\s]+)`", ln):
            t = tok.rstrip(".,:;)").split("#")[0].split("::")[0]
            t = re.sub(r":\d+(-\d+)?$", "", t)
            if not t or PTR_BAD.search(t) or t in ignore or not re.fullmatch(r"[\w./@+-]+", t):
                continue
            if (prefixes and t.startswith(prefixes)) or re.search(FILE_EXT + r"$", t) \
                    or re.search(FILE_EXT + r"\.[A-Za-z_]\w*$", t) and "/" in t:
                out.append((n, t))
    return out


def gmatch(path: str, pat: str, cfg=None) -> bool:
    """The one glob dialect (schema_version 2), root-relative as Path.glob: `*` within a segment, `**/` for zero or
    more segments, `?` one character; a leading `/` is allowed; a slashless pattern names a root entry. Schema 1
    matched a slashless membership pattern at any depth, so a schema-1 `cfg` keeps that until `genome migrate`
    writes the `**/` form."""
    if pat.startswith("/"):  # anchored at the project root: `/README.md` is the root README only
        pat = pat[1:]
    elif "/" not in pat and cfg is not None and cfg.schema_version < 2:
        return fnmatch.fnmatch(Path(path).name, pat)
    rx = "".join("(?:.*/)?" if tok == "**/" else ".*" if tok == "**" else "[^/]*" if tok == "*" else "[^/]" if tok == "?"
                 else re.escape(tok) for tok in re.findall(r"\*\*/?|\*|\?|[^*?]+", pat))
    return re.fullmatch(rx, path) is not None


MEMBERSHIP_KEYS = (("core", "never_commit"), ("drift", "paths"), ("ops", "code_roots"), ("ops", "code_globs"),
                   ("ops", "bulk_globs"), ("ops", "owner_globs"), ("ops", "owner_exempt"))


def membership_problems(sec: dict) -> list[tuple[str, str, str]]:
    """(section, key, pattern) for each slashless membership pattern: schema 1 matched it at any depth."""
    return [(s, k, p) for s, k in MEMBERSHIP_KEYS for p in (sec.get(s, {}).get(k) or [])
            if isinstance(p, str) and not p.startswith("/") and "/" not in p]


def changed_paths(cfg: Cfg) -> list[tuple[str, str]]:
    """(status, path) for every changed or untracked file — files, never whole dirs; quoting-safe."""
    raw = sh(cfg.root, "git", "status", "--porcelain", "-z", "--untracked-files=all").split("\0")
    out, i = [], 0
    while i < len(raw):
        ent = raw[i]
        i += 1
        if len(ent) < 4:
            continue
        out.append((ent[:2], ent[3:]))
        if ent[0] in "RC":
            i += 1  # the rename's source path follows
    return out


HEAVY_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "target", ".genome"}


def tracked(cfg: Cfg) -> list[str]:
    out = sh(cfg.root, "git", "ls-files").splitlines()
    if out:
        return [f for f in out if os.path.lexists(cfg.root / f)]  # moved-but-uncommitted files are gone
    found = []  # not a git repo: walk the tree, pruning dependency and build directories
    for dirpath, dirs, files in os.walk(cfg.root):
        dirs[:] = [d for d in dirs if d not in HEAVY_DIRS]
        found += [cfg.rel(Path(dirpath) / f) for f in files]
    return found


def is_git(cfg: Cfg) -> bool:
    return bool(sh(cfg.root, "git", "rev-parse", "--git-dir").strip())


def pointer_exists(cfg: Cfg, t: str, files: list[str]) -> bool:
    """Exists at the root, or names a live tracked file by its tail (`name.md`,
    `src/mod.rs` written relative to a package), or `pkg/module.func`. Archived
    copies never satisfy a pointer from a live doc."""
    files = [f for f in files if not is_archived(cfg, f)]
    if (cfg.root / t).exists():
        return True
    mod = re.sub(r"\.[A-Za-z_]\w*$", ".py", t)
    if "/" in t and (cfg.root / mod).exists():
        return True
    tail = "/" + t.rstrip("/")
    if any(("/" + f).endswith(tail) or (tail + "/") in ("/" + f) for f in files):
        return True
    first = "/" + t.split("/")[0] + "/"  # untracked artefact under a tracked dir (e.g. scratch/…)
    bases = {("/" + f)[:("/" + f).find(first)] for f in files if first in "/" + f}
    return any((cfg.root / b.lstrip("/") / t).exists() for b in bases)


def is_archived(cfg: Cfg, rel: str) -> bool:
    arch = cfg.paths["archive"].rstrip("/") + "/"
    return rel.startswith(arch) or "/archive/" in f"/{rel}"


