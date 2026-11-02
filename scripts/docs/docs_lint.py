#!/usr/bin/env python3
"""Outward documentation lint: the README <-> docs/ boundary.

`kb lint` (project-kb) owns the internal agent genome; it does NOT own the
internal/outward boundary. These checks do. They enforce the doorway
discipline from ../references/readme-craft.md §Anti-Patterns ("the README
links, it does not paraphrase"): a thin root README that points at docs/ and
a docs/ tree that is itself reachable and self-consistent.

Checks (code / severity):

  D001  dead outward link   relative [text](file) in README.md must exist   [hard]
  D002  README paraphrases   h2/h3 heading text duplicated in docs/**/*.md     [advisory]
  D003  orphan doc page      docs/**/*.md not linked from README nor a doc     [hard]
  D004  dead ToC anchor      [text](#anchor) must resolve to a heading         [hard]
  D005  undeclared mutability  `Last reviewed` heading w/o a date, or          [advisory]
                          contradictory staleness markers

Exit codes: 0 = clean (advisories allowed), 2 = any hard failure.
--strict promotes D002/D005 advisories to hard failures.
Read-only; never writes. Stdlib only (argparse, json, re, sys, pathlib).
"""
import argparse
import json
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})")
STALENESS_TERMS = ("last reviewed", "last updated", "last modified", "last audited")
INLINE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)|\[([^\]]*)\]\(([^)]*)\)")
CODE_SPAN_RE = re.compile(r"`[^`]*`")
REF_LINK_RE = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]|\[([^\]]*)\]\[([^\]]*)\]")
REF_DEF_RE = re.compile(r"^\s*\[([^\]]+)\]:\s*(\S.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")  # CommonMark: a fence may be indented up to 3 spaces


def norm(s: str) -> str:
    """Lowercase + collapse whitespace for heading-text comparison."""
    return " ".join(s.lower().split())


def gh_anchor(text: str) -> str:
    """GitHub-compatible id slug for a heading (cmark-gfm)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s", "-", text)  # per whitespace char, as GitHub does
    # GitHub keeps every hyphen: "Daemon & queue" is "daemon--queue", so no collapse
    return text.strip("-")


def find_headings(text: str):
    """Return list of (line_no, level, heading_text) for ATX headings."""
    return FenceFilter(text).heading_lines()


class FenceFilter:
    """Iterate lines, skipping fenced code blocks."""

    def __init__(self, text: str):
        self.lines = text.split("\n")

    def heading_lines(self):
        """Return [(line_no, level, heading_text)] for ATX headings."""
        in_fence = False
        fc = ""
        out = []
        for i, raw in enumerate(self.lines):
            m = FENCE_RE.match(raw)
            if m:
                tok = m.group(1)
                if not in_fence:
                    in_fence = True
                    fc = tok[0]
                    continue
                if tok[0] == fc:
                    in_fence = False
                    fc = ""
                    continue
            if in_fence:
                continue
            hm = HEADING_RE.match(raw)
            if hm:
                out.append((i + 1, len(hm.group(1)), hm.group(2)))
        return out

    def link_lines(self):
        """Yield (line_no, link_text) for link-bearing lines outside fenced code."""
        in_fence = False
        fc = ""
        out = []
        for i, raw in enumerate(self.lines):
            m = FENCE_RE.match(raw)
            if m:
                tok = m.group(1)
                if not in_fence:
                    in_fence = True
                    fc = tok[0]
                    continue
                if tok[0] == fc:
                    in_fence = False
                    fc = ""
                    continue
            if in_fence:
                continue
            out.append((i + 1, raw))
        return out


def extract_links(text: str):
    """Return list of {line, target, image} for inline + reference links."""
    ff = FenceFilter(text)
    lines = ff.link_lines()
    # pass 1: reference definitions
    defs = {}
    for _i, raw in lines:
        m = REF_DEF_RE.match(raw)
        if m:
            defs[m.group(1).strip().lower()] = m.group(2).strip()
    # pass 2: inline + reference links
    out = []
    for ln, raw in lines:
        # inline code spans are text, not links: blank them, keeping offsets
        raw = CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), raw)
        for mm in INLINE_LINK_RE.finditer(raw):
            if mm.group(1) is not None:
                out.append({"line": ln, "target": mm.group(2), "image": True})
            else:
                out.append({"line": ln, "target": mm.group(4), "image": False})
        for mm in REF_LINK_RE.finditer(raw):
            if mm.group(1) is not None:
                ref = mm.group(2).strip().lower()
                if ref in defs:
                    out.append({"line": ln, "target": defs[ref], "image": True})
            else:
                ref = (mm.group(4) or "").strip().lower()
                if ref and ref in defs:
                    out.append({"line": ln, "target": defs[ref], "image": False})
    return out


def resolve_target(target: str, base_dir: Path, root: Path):
    """Classify a raw link target.

    Returns (kind, payload):
      ('file', Path|None)  a file-path link; payload is resolved Path or None if dead
      ('anchor', str)      an anchor-only link (#anchor)
      ('external', None)   http/https/mailto/etc.
    """
    target = (target or "").strip()
    if not target:
        return ("external", None)
    if target.startswith("#"):
        return ("anchor", target[1:])
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target):
        return ("external", None)
    path, _, anchor = target.partition("#")
    path = path.strip()
    if path == "":
        return ("anchor", anchor)
    if path.startswith("/"):
        base, rel = root, path.lstrip("/")
    else:
        base, rel = base_dir, path
    resolved = resolve_file(rel, base)
    return ("file", resolved)


def resolve_file(rel: str, base: Path):
    """Resolve a repo-relative path to an existing Path, or None if dead.

    A directory link resolves if the directory exists on disk (GitHub renders
    a listing; if it has an index.md/README.md that page is returned instead).
    Only a path that resolves to NEITHER a file nor a directory is dead.
    """
    p = base / rel
    if p.is_file():
        return p
    if p.is_dir():
        idx = index_of(p)
        if idx:
            return idx
        return p
    if not p.suffix:
        cand = p.with_name(p.name + ".md")
        if cand.is_file():
            return cand
    cand2 = Path(str(p) + ".md")
    if cand2.is_file():
        return cand2
    return None


def index_of(d: Path):
    for idx in ("index.md", "README.md", "readme.md"):
        c = d / idx
        if c.is_file():
            return c
    return None





def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #

def check_d001(readme_text, readme_path, root):
    """D001: dead outward link. README relative file links must resolve."""
    findings = []
    if not readme_path.is_file():
        return findings
    base = readme_path.parent
    for link in extract_links(readme_text):
        kind, payload = resolve_target(link["target"], base, root)
        if kind == "file" and payload is None:
            target = link["target"]
            msg = "target not found on disk"
            if link["image"]:
                msg = "image target not found on disk"
            findings.append({
                "code": "D001", "severity": "hard",
                "file": rel(readme_path, root),
                "line": link["line"], "target": target, "message": msg,
                "locations": [],
            })
    return findings


def check_d002(readme_text, readme_path, docs_dir, root):
    """D002: README h2/h3 heading duplicated as a heading inside docs/."""
    findings = []
    if not readme_path.is_file() or not docs_dir.is_dir():
        return findings
    readme_h = [(ln, txt) for ln, lvl, txt in find_headings(readme_text) if lvl in (2, 3)]
    readme_norms = {norm(t): ln for ln, t in readme_h}
    pages = sorted(docs_dir.rglob("*.md"))
    # map normalised docs heading -> list of (file, line, raw)
    docs_index = {}
    for page in pages:
        try:
            txt = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ln, lvl, txt_h in find_headings(txt):
            n = norm(txt_h)
            docs_index.setdefault(n, []).append((rel(page, root), ln, txt_h))
    seen = set()
    for ln, txt in readme_h:
        n = norm(txt)
        if n in docs_index:
            for dfile, dline, dtext in docs_index[n]:
                key = (n, dfile, dline)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "code": "D002", "severity": "advisory",
                    "file": rel(readme_path, root), "line": ln,
                    "target": txt, "message": "README heading duplicates a docs page heading; "
                                            "README should link, not paraphrase",
                    "locations": [{"file": dfile, "line": dline, "heading": dtext}],
                })
    return findings


def check_d003(docs_dir, readme_path, readme_text, root):
    """D003: orphan doc page not linked from README nor from any doc page.

    Internal agent records are exempt, matching `kb lint`'s W009: the genome
    keeps handoff/kb/archive/plans under docs/ on purpose — they are for agents,
    not readers, and are never meant to be README-linked. A repo that keeps its
    dated-frozen records elsewhere (docs/design/YYYY-MM-DD-*.md) is the same
    convention under a different name, so the dated-filename form is exempt too.
    """
    findings = []
    if not docs_dir.is_dir():
        return findings
    pages = sorted(docs_dir.rglob("*.md"))
    if not pages:
        return findings
    internal_dirs = {"handoff", "kb", "archive", "plans", "audit", "decisions",
                     "regressions", "workflows", "internal", "design"}
    dated = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
    # GitHub-UI meta docs are linked from the repo's Community/Security tabs, not the README.
    meta_docs = {"CODE_OF_CONDUCT", "CONTRIBUTING", "SECURITY", "SUPPORT", "ATTRIBUTION",
                 "CHANGELOG", "GOVERNANCE"}
    pages = [p for p in pages
             if not (any(part in internal_dirs for part in p.relative_to(docs_dir).parts[:-1])
                     or dated.match(p.name) or p.stem.upper() in meta_docs)]
    if not pages:
        return findings
    page_set = {p.resolve() for p in pages}
    reachable = set()
    # README -> docs
    if readme_path.is_file():
        for link in extract_links(readme_text):
            kind, payload = resolve_target(link["target"], readme_path.parent, root)
            if kind == "file" and payload is not None and payload.resolve() in page_set:
                reachable.add(payload.resolve())
    # docs -> docs
    for page in pages:
        try:
            txt = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        base = page.parent
        for link in extract_links(txt):
            kind, payload = resolve_target(link["target"], base, root)
            if kind == "file" and payload is not None:
                pr = payload.resolve()
                if pr in page_set and pr != page.resolve():
                    reachable.add(pr)
    for page in pages:
        if page.resolve() not in reachable:
            findings.append({
                "code": "D003", "severity": "hard",
                "file": rel(page, root), "line": 0, "target": None,
                "message": "orphan doc page — not linked from README nor any doc page",
                "locations": [],
            })
    return findings


def check_d004(readme_path, readme_text, extra_files, root):
    """D004: dead ToC anchor. [text](#anchor) must match a heading in same file."""
    findings = []
    files = []
    if readme_path.is_file():
        files.append((readme_path, readme_text))
    for ef in extra_files:
        p = Path(ef)
        if p.is_file():
            files.append((p, p.read_text(encoding="utf-8", errors="replace")))
    for fpath, text in files:
        cur = fpath.resolve()
        anchors = {gh_anchor(t).lower() for _ln, _l, t in find_headings(text)}
        base = fpath.parent
        for link in extract_links(text):
            kind, payload = resolve_target(link["target"], base, root)
            if kind == "anchor":
                anchor = payload.lower()
                if anchor not in anchors:
                    findings.append({
                        "code": "D004", "severity": "hard",
                        "file": rel(fpath, root), "line": link["line"],
                        "target": "#" + payload,
                        "message": "no matching heading for anchor",
                        "locations": [],
                    })
            elif kind == "file" and payload is not None and payload.resolve() == cur:
                # intra-file [text](thisfile.md#anchor)
                _path, _, anch = link["target"].partition("#")
                if anch and anch.lower() not in anchors:
                    findings.append({
                        "code": "D004", "severity": "hard",
                        "file": rel(fpath, root), "line": link["line"],
                        "target": "#" + anch,
                        "message": "no matching heading for anchor",
                        "locations": [],
                    })
    return findings


def check_d005(readme_text, readme_path, root):
    """D005: `Last reviewed` heading without a date, or contradictory staleness."""
    findings = []
    if not readme_path.is_file():
        return findings
    lines = readme_text.split("\n")
    headings = []
    in_fence = False
    fc = ""
    for i, raw in enumerate(lines):
        m = FENCE_RE.match(raw)
        if m:
            tok = m.group(1)
            if not in_fence:
                in_fence = True; fc = tok[0]; continue
            if tok[0] == fc:
                in_fence = False; fc = ""; continue
        if in_fence:
            continue
        hm = HEADING_RE.match(raw)
        if hm:
            headings.append((i + 1, hm.group(2).strip()))
    for ln, txt in headings:
        low = txt.lower()
        if "last reviewed" in low:
            window = "\n".join(lines[ln - 1:ln + 3])
            if not DATE_RE.search(window):
                findings.append({
                    "code": "D005", "severity": "advisory",
                    "file": rel(readme_path, root), "line": ln,
                    "target": txt, "message": "Last reviewed heading has no date",
                    "locations": [],
                })
    # contradictory staleness markers: multiple staleness headings w/ diff dates
    stale_dates = {}
    for ln, txt in headings:
        low = txt.lower()
        if any(term in low for term in STALENESS_TERMS):
            window = "\n".join(lines[ln - 1:ln + 3])
            dm = DATE_RE.search(window)
            if dm:
                stale_dates.setdefault(low, set()).add(dm.group(0))
    all_dates = {d for ds in stale_dates.values() for d in ds}
    keys = list(stale_dates.keys())
    if len(keys) >= 2 and len(all_dates) > 1:
        findings.append({
            "code": "D005", "severity": "advisory",
            "file": rel(readme_path, root), "line": headings[0][0],
            "target": ", ".join(keys),
            "message": "contradictory staleness markers: " + ", ".join(keys),
            "locations": [],
        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Outward documentation lint (README <-> docs boundary).")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--readme", default="README.md", help="root README (default: README.md)")
    ap.add_argument("--docs-dir", default="docs", help="docs tree (default: docs)")
    ap.add_argument("--file", action="append", default=[], metavar="F",
                    help="extra file to lint for D004 (repeatable)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true",
                    help="promote D002/D005 advisories to hard failures")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress advisory output")
    args = ap.parse_args()

    root = Path(args.root)
    readme_path = root / args.readme
    docs_dir = root / args.docs_dir

    readme_text = ""
    if readme_path.is_file():
        readme_text = readme_path.read_text(encoding="utf-8", errors="replace")
    elif not args.quiet:
        print(f"WARNING: {rel(readme_path, root)} not found; "
              f"skipping D001/D002/D004/D005.")

    findings = []
    findings += check_d001(readme_text, readme_path, root)
    findings += check_d002(readme_text, readme_path, docs_dir, root)
    findings += check_d003(docs_dir, readme_path, readme_text, root)
    findings += check_d004(readme_path, readme_text, args.file, root)
    findings += check_d005(readme_text, readme_path, root)

    hard = [f for f in findings if f["severity"] == "hard"]
    adv = [f for f in findings if f["severity"] == "advisory"]
    hard_count = len(hard) + (len(adv) if args.strict else 0)

    if args.json:
        serialised = []
        for f in findings:
            sev = "hard" if (f["severity"] == "hard" or args.strict) else "advisory"
            serialised.append({**f, "severity": sev})
        print(json.dumps({
            "root": str(root),
            "readme": rel(readme_path, root),
            "docs_dir": rel(docs_dir, root) if docs_dir.is_dir() else str(docs_dir),
            "strict": args.strict,
            "findings": serialised,
            "summary": {
                "hard": len(hard), "advisory": len(adv),
                "hard_total": hard_count,
            },
            "exit_code": 0 if hard_count == 0 else 2,
        }, indent=2))
        return 0 if hard_count == 0 else 2

    # text output
    if not readme_path.is_file():
        pass  # warning already printed
    # order by code then file then line
    findings.sort(key=lambda f: (f["code"], f["file"], f["line"]))
    for f in findings:
        sev = "hard" if (f["severity"] == "hard" or args.strict) else "advisory"
        if sev == "advisory" and args.quiet:
            continue
        target = f.get("target")
        suffix = f"  ({target})" if target else ""
        tag = " [advisory]" if sev == "advisory" else ""
        print(f"{f['code']}  {f['file']}:{f['line']}  {f['message']}{suffix}{tag}")
        for loc in f.get("locations", []):
            lt = f" ({loc.get('heading')})" if loc.get("heading") else ""
            print(f"        -> {loc['file']}:{loc['line']}{lt}")
    adv_tag = " (advisories promoted under --strict)" if adv and not args.strict else ""
    if args.strict:
        print(f"\n{hard_count} failure(s) "
              f"({len(hard)} hard, {len(adv)} advisory-as-hard).")
    else:
        print(f"\n{len(hard)} hard failure(s), {len(adv)} advisory(ies){adv_tag}.")
    if hard_count:
        print("docs_lint: FAIL")
        return 2
    print("docs_lint: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
