# ---------------------------------------------------------------- records

def rec_prefix(cfg: Cfg) -> str:
    p = cfg.get("records", "prefix", "")
    return f"{p}-" if p else ""


def rec_archive(cfg: Cfg) -> Path:
    return cfg.root / cfg.get("records", "archive", cfg.paths["archive"].rstrip("/") + "/records")


def front_span(text: str) -> tuple[int, int] | None:
    """(start, end) of the frontmatter body between the `---` lines, or None. An empty block (`---\\n---`) counts."""
    if not text.startswith("---\n"):
        return None
    if text.startswith("---\n---"):
        return 4, 4
    end = text.find("\n---", 4)
    return (4, end) if end >= 0 else None


def frontmatter(text: str) -> dict[str, str]:
    span = front_span(text)
    if span is None:
        return {}
    out = {}
    for ln in text[span[0]:span[1]].splitlines():
        m = re.match(r"([A-Za-z][\w-]*):\s*(.*?)\s*$", ln)
        if m:
            v = m.group(2)
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\") if v[0] == '"' else v[1:-1].replace("''", "'")
            out[m.group(1)] = v
    return out


def yq(v: str) -> str:
    """A value safe inside a double-quoted YAML scalar on one line."""
    return " ".join(str(v).split("\n")).replace("\\", "\\\\").replace('"', '\\"')


def add_revision(text: str, line: str) -> str:
    """Append a line to the end of the `## Revisions` section (wherever it sits), or start one at the end."""
    lines = text.rstrip("\n").splitlines()
    i = next((k for k, ln in enumerate(lines) if re.match(r"##\s+Revisions\b", ln)), None)
    if i is None:
        return "\n".join(lines) + f"\n\n## Revisions\n\n{line}\n"
    j = next((k for k in range(i + 1, len(lines)) if re.match(r"#{1,2} ", lines[k])), len(lines))
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1
    return "\n".join(lines[:j] + [line] + lines[j:]) + "\n"


def set_front(text: str, fields: dict[str, str]) -> str:
    """Set frontmatter fields. A record without a block gets one; its body lines (a body `Status:` included) stay untouched."""
    span = front_span(text)
    if span is None:
        text, span = "---\n---\n\n" + text, (4, 4)
    head = text[span[0]:span[1]].splitlines()
    for k, v in fields.items():
        line = f'{k}: "{yq(v)}"'
        idx = next((i for i, ln in enumerate(head) if re.match(rf"{re.escape(k)}:", ln)), None)
        if idx is None:
            head.append(line)
        else:
            head[idx] = line
    tail = text[span[1]:]
    if span[0] == span[1]:  # an empty block: its closing fence has no newline of its own
        tail = ("\n" if head else "") + tail
    return "---\n" + "\n".join(head) + tail


def parse_record(cfg: Cfg, p: Path) -> dict | None:
    m = re.match(rf"^({re.escape(rec_prefix(cfg))}(AD|RG)-(\d+))", p.name)
    if not m:
        return None
    text = read(p)
    fm = frontmatter(text)
    title = fm.get("Title", "")
    if not title:
        h = re.search(rf"^#\s+{re.escape(m.group(1))}\s*[:—-]?\s*(.+)$", text, re.M) or re.search(r"^#\s+(.+)$", text, re.M)
        title = h.group(1).strip() if h else p.stem
    st = fm.get("Status") or (re.search(r"^[-*\s]*\**Status:?\**:?[ \t]*\**([A-Za-z]+)", text, re.M) or [None, "Active"])[1]
    return {"id": fm.get("ID", m.group(1)), "kind": m.group(2), "num": int(m.group(3)), "title": title,
            "status": st, "desc": fm.get("Description", ""), "by": fm.get("SupersededBy") or fm.get("Superseded-By", ""),
            "sev": fm.get("Severity", ""), "fm": fm, "file_id": m.group(1), "path": p, "text": text}


def records(cfg: Cfg, archived: bool = False) -> list[dict]:
    dirs = [cfg.path("decisions"), cfg.path("regressions")] if not archived else [rec_archive(cfg)]
    out = []
    for d in dirs:
        if d.is_dir():
            out += [r for f in sorted(d.glob("*.md")) if (r := parse_record(cfg, f))]
    return out


def find_record(cfg: Cfg, rid: str, archived_ok: bool = False) -> dict:
    for r in records(cfg) + (records(cfg, True) if archived_ok else []):
        if r["id"] == rid:
            return r
    die(f"no record `{rid}`" + ("" if archived_ok else " among active records"))


def render_records(cfg: Cfg, kinds: tuple[str, ...] = ("AD", "RG")) -> str:
    rs = records(cfg)
    out = []
    for kind, label in (("AD", "Decisions"), ("RG", "Regressions")):
        sub = [r for r in rs if r["kind"] == kind]
        if not sub or kind not in kinds:
            continue
        col = "Severity" if kind == "RG" and any(r["sev"] for r in sub) else "Status"
        out += [f"**{label}** ({len(sub)})", "", f"| ID | Title | {col} | Description |", "|---|---|---|---|"]
        out += [f"| {r['id']} | {r['title'].replace('|', '/')} | {r['sev'] if col == 'Severity' else r['status']} | "
                f"{r['desc'][:200].replace('|', '/')} |" for r in sub]
        out.append("")
    return "\n".join(out) or "(no records)\n"


RENDER = {"records": render_records, "decisions": lambda c: render_records(c, ("AD",)),
          "regressions": lambda c: render_records(c, ("RG",)), "idmap": lambda c: render_idmap(c)}


def render_idmap(cfg: Cfg) -> str:
    rs = records(cfg, True)
    if not rs:
        return "(no retired records)\n"
    gone = {r["id"]: r["by"] for r in rs}
    pat = re.compile(rf"{re.escape(rec_prefix(cfg))}(?:AD|RG)-\d+")

    def owner(rid: str) -> str:
        """Follow SupersededBy through retired records to the live owner: `A → B (via X)`."""
        by, via = gone[rid], []
        while (m := pat.match(by or "")) and m.group(0) in gone and m.group(0) not in via and m.group(0) != rid:
            via.append(m.group(0))
            by = gone[m.group(0)]
        return (by or "—") + (f" (via {', '.join(via)})" if via else "")

    out = ["| Retired | Owner now | Status |", "|---|---|---|"]
    out += [f"| {r['id']} | {owner(r['id'])} | {r['status']} |" for r in rs]
    return "\n".join(out) + "\n"


def record_zone_targets(cfg: Cfg) -> dict[str, list[str]]:
    z = cfg.get("records", "zones")
    return z if isinstance(z, dict) else {cfg.paths["records_index"]: ["records", "idmap"]}


def emit_records(cfg: Cfg) -> list[str]:
    changed = []
    for target, names in record_zone_targets(cfg).items():
        for n in names:
            if n not in RENDER:
                die(f"records.zones: unknown zone `{n}` for {target} (known: {', '.join(RENDER)})")
            if write_zone(cfg.root / target, n, RENDER[n](cfg)):
                changed.append(f"{target}#{n}")
    return changed


