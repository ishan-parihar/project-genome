# ---------------------------------------------------------------- config

class Cfg:
    """genome.toml (or a legacy kb.toml) resolved against the project root."""

    def __init__(self, root: Path, data: dict, legacy: bool):
        self.root, self.legacy = root, legacy
        g = data.get("genome", {})
        mods = g.get("modules", LEGACY_MODULES if legacy else PROFILES["software"])
        bad = set(mods) - set(MODULES)
        if bad:
            die(f"unknown module(s) in config: {sorted(bad)} (known: {', '.join(MODULES)})")
        self.modules = {"core", *mods}
        raw = data.get("paths", {})
        self.declared = {k for k in raw if isinstance(raw[k], str)}
        self.zones_declared = "zones" in data.get("records", {})
        self.paths = {**DEFAULT_PATHS, **{k: v for k, v in raw.items() if isinstance(v, str)}}
        self.sec = {s: dict(data.get(s, {})) for s in ("core", "records", "research", "ops", "card", "federation", "drift", "index")}
        self.schema_version = int(g.get("schema_version", 0))
        self.kinds = dict(data.get("kinds", {}))
        self.views = dict(data.get("views", {}))
        self.unknown = [] if legacy else \
            [f"[{s}]" for s in data if s not in CONFIG_KEYS and s not in ("paths", "kinds", "views")] + \
            [f"[paths] {k}" for k in raw if k not in DEFAULT_PATHS and k not in RETIRED_PATHS] + \
            [f"[{s}] {k}" for s, keys in CONFIG_KEYS.items() if isinstance(data.get(s), dict)
             for k in data[s] if k not in keys]
        for k in ("pointer_ignore", "dated_pattern"):  # legacy kb.toml kept these under [paths]
            if k in raw:
                self.sec["core"].setdefault(k, raw[k])

    def get(self, sec: str, key: str, default=None):
        return self.sec.get(sec, {}).get(key, default)

    def form(self, role: str) -> tuple[str, str]:
        v = self.paths[role]
        for f in ("overlay", "native"):
            if v.startswith(f + ":"):
                return f, v.split(":", 1)[1]
        return "file", v

    def path(self, role: str) -> Path:
        """The file a role lives in; a `path#heading` value (a register inside a section of a doc) names that file."""
        return self.root / self.paths[role].split(":", 1)[-1] if self.form(role)[0] != "file" \
            else (self.root / self.paths[role].split("#", 1)[0])

    def has(self, role: str) -> bool:
        return self.form(role)[0] == "file" and self.path(role).exists()

    def require(self, role: str, cmd: str) -> Path:
        """Writers never follow a pointer note into a literal path."""
        form, target = self.form(role)
        if form != "file":
            die(f"the {role} role is {form}-owned ({target}) — `{cmd}` does not write it here")
        return self.path(role)

    def need(self, module: str) -> None:
        if module not in self.modules:
            die(f"module `{module}` is not enabled — add it to genome.toml [genome] modules")

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(p)

    def globs(self, patterns) -> list[Path]:
        """Files matching root-relative `Path.glob` patterns (`**/x` for any depth). The ownership and bulk keys use
        `gmatch` instead (a pattern without `/` matches anywhere); `genome upgrade` will unify the two under schema_version 2."""
        out: list[Path] = []
        for g in patterns or []:
            out += [p for p in self.root.glob(g) if p.is_file()]
        return sorted(set(out))

    def ignore(self) -> set[str]:
        v = self.get("core", "pointer_ignore", "")
        return set(v.split() if isinstance(v, str) else v)


def deep_merge(base: dict, more: dict) -> dict:
    for k, v in more.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def find_cfg(start: Path | None = None) -> Cfg:
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        for name, legacy in (("genome.toml", False), ("kb.toml", True)):
            f = cand / name
            if f.is_file():
                try:
                    data = tomllib.loads(f.read_text())
                    # genome/kinds/*.toml (a blueprint's copy, or hand-written) deep-merge in name order, so an
                    # extension adds a relation to a base kind without restating it; genome.toml merges last and wins
                    layered: dict = {"kinds": {}, "views": {}}
                    for extra in sorted((cand / "genome" / "kinds").glob("*.toml")) if not legacy else []:
                        try:
                            more = tomllib.loads(extra.read_text())
                        except tomllib.TOMLDecodeError as e:
                            die(f"{extra}: {e}")
                        for sec in ("kinds", "views"):
                            deep_merge(layered[sec], more.get(sec, {}))
                    for sec in ("kinds", "views"):
                        data[sec] = deep_merge(layered[sec], data.get(sec, {}))
                    return Cfg(cand, data, legacy)
                except tomllib.TOMLDecodeError as e:
                    die(f"{f}: {e}")
    die("no genome.toml upward of cwd — run `genome init` at the project root")


