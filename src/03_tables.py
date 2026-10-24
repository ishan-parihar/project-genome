# ---------------------------------------------------------------- tables

class Guarded:
    """flock-guarded read-modify-write: claims and appends race exactly when
    two agents act at once; the lock makes collisions impossible, not unlikely."""

    def __init__(self, path: Path):
        self.lock = path.with_name(path.name + ".genome-lock")  # never `*.lock`: Cargo.lock, uv.lock are real files

    def __enter__(self):
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        if fcntl is None:  # no flock: create the lock file exclusively, retry for up to 30 s
            for _ in range(300):
                try:
                    self.fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    return self
                except FileExistsError:
                    time.sleep(0.1)
            die(f"could not take {self.lock} (a stale lock? delete it if no genome command is running)")
        self.fd = open(self.lock, "a+")
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if fcntl is None:
            os.close(self.fd)
            self.lock.unlink(missing_ok=True)
            return False
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.close()
        return False


def cells(line: str) -> list[str]:
    """Split a table row on unescaped pipes; `\\|` inside a cell (code, regexes) stays in the cell."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


def is_sep(line: str) -> bool:
    return line.lstrip().startswith("|") and set(line.strip()) <= set("|-: ")


def tables(path: Path) -> list[tuple[list[str], list[list[str]]]]:
    """(header cells, data rows) per markdown table in a file."""
    lines = read(path).splitlines()
    out: list[tuple[list[str], list[list[str]]]] = []
    for i, ln in enumerate(lines):
        if not ln.lstrip().startswith("|") or is_sep(ln):
            continue
        if i + 1 < len(lines) and is_sep(lines[i + 1]):
            out.append((cells(ln), []))  # header
        elif out and i and lines[i - 1].lstrip().startswith("|"):
            out[-1][1].append(cells(ln))
        else:
            out.append(([], [cells(ln)]))  # headerless fragment
    return out


def rows(path: Path) -> list[list[str]]:
    """Data rows of every markdown table in a file (header and separator skipped)."""
    return [r for _, rs in tables(path) for r in rs]


def find_row(path: Path, rid: str) -> list[str] | None:
    return next((r for r in rows(path) if r and r[0] == rid), None)


def fmt_row(row: list[str]) -> str:
    """One table line: pipes escaped and newlines folded, so a cell can never split the row."""
    return "| " + " | ".join(re.sub(r"(?<!\\)\|", r"\|", " ".join(str(c).split("\n"))) for c in row) + " |"


def replace_row(path: Path, rid: str, new: list[str]) -> bool:
    lines = read(path).splitlines()
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("|") and not is_sep(ln) and cells(ln)[0] == rid:
            lines[i] = fmt_row(new)
            atomic_write(path, "\n".join(lines) + "\n")
            return True
    return False


def next_id(path: Path, prefix: str) -> str:
    nums = [int(m.group(1)) for r in rows(path) if r and (m := re.fullmatch(re.escape(prefix) + r"(\d+)", r[0]))]
    return f"{prefix}{max(nums, default=0) + 1}"


def append_row(path: Path, row: list[str], header: str) -> None:
    """Add a row after the file's last table line (notes under the table stay under it)."""
    lines = read(path).splitlines() if path.exists() else header.splitlines()
    last = max((i for i, ln in enumerate(lines) if ln.lstrip().startswith("|")), default=None)
    if last is None:
        last = len(lines) - 1
    lines.insert(last + 1, fmt_row(row))
    atomic_write(path, "\n".join(lines) + "\n")


class Register:
    """A register table: a whole file (`path`), or the first table under a heading (`path#heading`), so a repo's
    existing register (an assumption table inside a protocol doc) stays where it is and keeps its own columns.
    Columns are found by header name: the first is the id; `status`, `text`, `evidence` and `reopen` by keyword."""
    COLS = {"status": ("status",), "text": ("hypothes", "assumption", "claim", "question"),
            "evidence": ("verdict", "evidence"), "reopen": ("reopen", "re-open")}

    def __init__(self, cfg: "Cfg", role: str):
        self.path = cfg.path(role)
        self.heading = cfg.paths[role].partition("#")[2]
        self.load()

    def load(self) -> None:
        self.lines = read(self.path).splitlines() if self.path.exists() else []
        lo, hi = 0, len(self.lines)
        if self.heading:
            hs = headings(self.lines)
            hit = next(((k, lv) for k, lv in hs if self.heading.lower() in self.lines[k].lower()), None)
            if hit is None:
                die(f"{self.path.name}: no heading containing `{self.heading}` for the register")
            lo = hit[0]
            hi = heading_end(hs, lo, hit[1], len(self.lines))
        self.header, self.at = [], []  # header cells; line numbers of the data rows
        for i in range(lo, hi):
            ln = self.lines[i]
            if not ln.lstrip().startswith("|"):
                if self.header and (self.at or i > self.hdr + 1):
                    break  # the first table under the heading ends here
                continue
            if is_sep(ln):
                continue
            if not self.header and i + 1 < hi and is_sep(self.lines[i + 1]):
                self.header, self.hdr = cells(ln), i
            elif self.header:
                self.at.append(i)

    @property
    def rows(self) -> list[list[str]]:
        return [cells(self.lines[i]) for i in self.at]

    def col(self, name: str) -> int | None:
        if name == "id":
            return 0
        return next((k for k, h in enumerate(self.header) if any(w in h.lower() for w in self.COLS[name])), None)

    def get(self, row: list[str], name: str) -> str:
        k = self.col(name)
        return row[k] if k is not None and k < len(row) else ""

    def find(self, rid: str) -> tuple[int, list[str]] | None:
        return next(((i, cells(self.lines[i])) for i in self.at if cells(self.lines[i])[0] == rid), None)

    def write(self, i: int | None, row: list[str]) -> None:
        """Replace line i, or (i None) insert after the register's last row."""
        row = row + ["—"] * (len(self.header) - len(row))
        if i is None:
            self.lines.insert((self.at[-1] if self.at else self.hdr + 1) + 1, fmt_row(row))
        else:
            self.lines[i] = fmt_row(row)
        atomic_write(self.path, "\n".join(self.lines) + "\n")
        self.load()

    def next_id(self, prefix: str) -> str:
        nums = [int(m.group(1)) for r in self.rows if (m := re.fullmatch(re.escape(prefix) + r"(\d+)", r[0]))]
        return f"{prefix}{max(nums, default=0) + 1}"


def claim_holder(cell: str) -> str | None:
    """Who holds the claim noted in a notes cell, or None."""
    m = re.search(r"claimed-by `?([A-Za-z0-9_.-]+)", cell)
    return m.group(1) if m else None


def claim_text(agent: str) -> str:
    return f"claimed-by `{agent}` since {now()}"


def register_rows(cfg: Cfg) -> list[list[str]] | None:
    """Data rows of the register: the whole file, or only the table under `path#heading`. None: the heading is missing."""
    if "#" not in cfg.paths["register"]:
        return rows(cfg.path("register"))
    try:
        return Register(cfg, "register").rows
    except SystemExit:
        return None


def register_find(cfg: Cfg, rid: str) -> list[str] | None:
    if "#" not in cfg.paths["register"]:
        return find_row(cfg.path("register"), rid)
    hit = Register(cfg, "register").find(rid)
    return hit[1] if hit else None


def register_replace(cfg: Cfg, rid: str, row: list[str]) -> None:
    if "#" not in cfg.paths["register"]:
        replace_row(cfg.path("register"), rid, row)
        return
    reg = Register(cfg, "register")
    reg.write(reg.find(rid)[0], row)


def status_word(cell: str) -> str:
    """`rejected (ruling 12)` → `rejected`: a register may qualify a status in prose after its first word."""
    m = re.match(r"[a-z-]+", cell.strip().lower())
    return m.group(0) if m else ""


def evidence_refs(cfg: "Cfg", cell: str) -> tuple[list[str], list[str]]:
    """(resolving, missing) evidence in a verdict cell: backticked repo paths, and `worklog NNNN` citations
    (numbered worklogs carry the readings). Backticked commands or symbols are neither."""
    ok, bad = [], []
    for t in re.findall(r"`([^`\s]+)`", cell):
        if "/" in t or re.search(r"\.(json|jsonl|md|csv|parquet|txt|py|log)$", t):
            p = t.split("#")[0].split("::")[0]
            hit = (cfg.root / p).exists() or ("/" not in p and cfg.has("evidence")
                                                and next(cfg.path("evidence").rglob(p), None) is not None)
            (ok if hit else bad).append(t)
    if cfg.form("worklog")[0] == "file" and cfg.path("worklog").is_dir():
        for n in re.findall(r"worklogs? (\d{3,5}[a-z]?)", cell):
            (ok if next(cfg.path("worklog").glob(f"{n}-*"), None) else bad).append(f"worklog {n}")
    return ok, bad


