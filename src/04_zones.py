# ---------------------------------------------------------------- zones and markdown structure

def zone_sha(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def write_zone(path: Path, name: str, body: str) -> bool:
    """Replace (or append) a generated zone. Returns True when the text changed."""
    body = body if body.endswith("\n") else body + "\n"
    block = f"<!-- genome:zone {name} sha={zone_sha(body)} -->\n{body}<!-- genome:end {name} -->"
    text = read(path)
    if name in broken_zones(text):
        die(f"{path}: zone `{name}` has a start marker without its end (or two starts) — repair it by hand, then re-emit")
    m = next((m for m in ZONE_RE.finditer(text) if m.group(1) == name), None)
    slot = f"<!-- genome:zone {name} -->"  # a placeholder line places a new zone; otherwise it goes at the end
    if m:
        new = text[:m.start()] + block + text[m.end():]
    elif slot in text:
        new = text.replace(slot, block, 1)
    else:
        new = (text.rstrip("\n") + "\n\n" + block + "\n").lstrip("\n")
    if new != text:
        atomic_write(path, new)
        return True
    return False


def broken_zones(text: str) -> list[str]:
    """Zone starts that no `zones()` match closes.

    A start marker inside a code fence is documentation, not a zone: `headings()`
    already skips fences, and a manual that shows the marker format would otherwise
    fail the lint it is describing (the case that produced this). The fenced example
    in `references/core.md` names a zone that can never be written, so `zones()`
    never finds it and the unguarded regex called it broken."""
    lines = text.splitlines()
    starts, fence = [], False
    for ln in lines:
        if ln.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence:
            starts += re.findall(r"<!-- genome:zone (\S+) sha=", ln)
    whole = {m.group(1) for m in ZONE_RE.finditer(text)}
    return sorted({n for n in starts if n not in whole or starts.count(n) > 1})


def zones(text: str) -> dict[str, tuple[str, str]]:
    return {m.group(1): (m.group(2), m.group(3)) for m in ZONE_RE.finditer(text)}


def blank_zones(text: str) -> str:
    """Generated zone bodies emptied, line numbers kept: an emitted table answers no question its source does not."""
    return ZONE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def headings(lines: list[str]) -> list[tuple[int, int]]:
    """(index, level) of every markdown heading outside code fences."""
    out, fence = [], False
    for k, ln in enumerate(lines):
        if ln.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and re.match(r"#{1,6} ", ln):
            out.append((k, len(ln) - len(ln.lstrip("#"))))
    return out


def heading_end(hs: list[tuple[int, int]], i: int, lvl: int, n: int) -> int:
    """Index one past the section opened by heading i: the next heading of the same or a higher level."""
    return next((k for k, lv in hs if k > i and lv <= lvl), n)


def md_sections(text: str, top: str, maxlevel: int = 4) -> list[tuple[str, int, int, str]]:
    """(heading, first line, last line, body) per section, 1-based; `top` names the text before the first heading."""
    lines = text.splitlines()
    out, head, start = [], top, 1
    for k in (k for k, lv in headings(lines) if lv <= maxlevel):
        if k + 1 > start:
            out.append((head, start, k, "\n".join(lines[start - 1:k])))
        head, start = lines[k].lstrip("# ").strip(), k + 1
    out.append((head, start, len(lines), "\n".join(lines[start - 1:])))
    return out


