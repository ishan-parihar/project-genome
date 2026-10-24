# ---------------------------------------------------------------- worklog

def worklog_numbered(cfg: Cfg) -> bool:
    return cfg.get("core", "worklog_form", "file") == "numbered"


def worklog_files(cfg: Cfg) -> list[Path]:
    d = cfg.path("worklog")
    return sorted(f for f in d.glob("*.md") if re.match(r"\d{3,}", f.name)) if d.is_dir() else []


def worklog_index(cfg: Cfg) -> Path:
    return cfg.path("worklog") / cfg.get("core", "worklog_index", "INDEX.md")


def emit_worklog_index(cfg: Cfg) -> bool:
    return write_zone(worklog_index(cfg), "worklog", render_worklog_index(cfg))


def render_worklog_index(cfg: Cfg) -> str:
    out = ["| File | Date | Title |", "|---|---|---|"]
    for f in worklog_files(cfg):
        h = re.search(r"^#\s+(.+)$", read(f), re.M)
        d = re.search(r"\d{4}-\d{2}-\d{2}", f.name)
        out.append(f"| `{f.name}` | {d.group(0) if d else '—'} | {(h.group(1) if h else f.stem).replace('|', '/')[:140]} |")
    return "\n".join(out) + "\n"


