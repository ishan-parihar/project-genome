#!/usr/bin/env python3
"""Deepseek-style per-package README contract check for monorepos.

Every package in a monorepo MUST ship a README whose headings answer a fixed
contract, so a contributor landing in any package knows where each answer lives.
Model: deepseek-ai/deepseek-harness `scripts/verify-package-readme-*.ts`,
declared in that repo's `packages/README.md`.

Cited evidence (ground-truth, not invented):
  DOCS-SYSTEM-PLAN.md §1.3 mechanism #5:
    "Per-package README contract enforced by a script
     (deepseek scripts/verify-package-readme-model-experience.ts +
     verify-package-readme-limitations.ts, declared in packages/README.md)."
  DOCS-SYSTEM-PLAN.md §4.1 lines 255-257 names this script:
    `verify_per_package_readme.py` "deepseek-style contract check: every
     packages/*/ has a README with purpose, configuration, extension points,
     and limitations sections." This port adds `model experience` (the
     deepseek script's namesake section).

The technology shape (cli-go / library-python / operator / helm — see
../references/oss-project-types.md) and the documentation role
(doorway / skills-pack / curated-list / learning-resource / monorepo — see
the arctypes routing rule) are ORTHOGONAL axes. This script enforces only the
contract headings; it classifies nothing by technology or role.

Usage:
  python3 verify_per_package_readme.py [package ...]
  python3 verify_per_package_readme.py --packages-dir crates
  python3 verify_per_package_readme.py --require "api=API reference" --json

Exit codes: 0 = every package PASS, 2 = any FAIL. Read-only; never writes.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MANIFESTS = ("package.json", "pyproject.toml", "go.mod", "Cargo.toml")
README_NAMES = ("readme.md", "readme.markdown", "readme.mdown")
# The deepseek contract. Each entry is (heading_text, annotation). Annotation is
# descriptive metadata surfaced only in --json; null in human output.
DEFAULT_SECTIONS = [
    ("purpose", None),
    ("configuration", None),
    ("extension points", None),
    ("limitations", None),
    ("model experience", None),
]


def norm(s: str) -> str:
    """Lowercase + collapse whitespace for case-insensitive heading matching."""
    return " ".join(s.lower().split())


def split_fence(lines):
    """Yield (line_index, text) skipping fenced code blocks (``` or ~~~)."""
    in_fence = False
    fence_char = ""
    out = []
    fence_re = re.compile(r"^(\s*)(`{3,}|~{3,})")
    for idx, raw in enumerate(lines):
        m = fence_re.match(raw)
        if m and not in_fence:
            in_fence = True
            fence_char = m.group(2)[0]
            continue
        if m and in_fence and m.group(2)[0] == fence_char:
            in_fence = False
            fence_char = ""
            continue
        if in_fence:
            continue
        out.append((idx, raw))
    return out


def read_headings(text: str):
    """Return [(line_no, heading_text)] for ATX headings outside code fences."""
    lines = text.split("\n")
    headings = []
    for idx, raw in split_fence(lines):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw)
        if m:
            headings.append((idx + 1, m.group(2)))
    return headings


def find_readme(pkg: Path):
    """Return the README Path for *pkg*, or None if absent."""
    if not pkg.is_dir():
        return None
    hits = []
    for name in pkg.iterdir():
        low = name.name.lower()
        if low in README_NAMES or (
            low.startswith("readme") and low.endswith((".md", ".markdown", ".mdown"))
        ):
            hits.append(name)
    if not hits:
        return None
    hits.sort(key=lambda p: (0 if p.name.lower() == "readme.md" else 1, p.name.lower()))
    return hits[0]


def has_manifest(d: Path) -> bool:
    return any((d / m).exists() for m in MANIFESTS)


def discover_packages(packages_dir, explicit):
    """Resolve the list of package directories to check.

    Precedence: explicit positional args > --packages-dir > autodetect
    (first existing of packages/, src/, cmd/). The manifest rule
    (DOCS-SYSTEM-PLAN §1.3 #5) applies to autodiscover: a subdir qualifies if
    it contains a manifest OR its parent is literally `packages` (the
    packages/ convention that admits manifest-less subdirs).
    """
    if explicit:
        return [Path(p) for p in explicit]
    pd = Path(packages_dir) if packages_dir else None
    if pd is None:
        for cand in ("packages", "src", "cmd"):
            c = Path(cand)
            if c.is_dir():
                pd = c
                break
    if pd is None:
        return []
    if not pd.is_dir():
        # Explicit but missing — return it so the per-package check reports 404.
        return [pd]
    subs = sorted((d for d in pd.iterdir() if d.is_dir()), key=lambda d: d.name)
    out = []
    for d in subs:
        if has_manifest(d) or pd.name == "packages":
            out.append(d)
    return out


def check_contract(pkg: Path, sections):
    """Check one package dir against the contract sections."""
    rel = str(pkg)
    readme = find_readme(pkg)
    section_names = [s[0] for s in sections]
    if readme is None:
        return {"package": pkg.name, "path": rel, "readme": None,
                "status": "fail", "reason": "no README found",
                "missing": section_names, "symlink": False}
    broken = readme.is_symlink() and not readme.exists()
    if broken:
        return {"package": pkg.name, "path": rel, "readme": str(readme),
                "status": "fail", "reason": "README is a broken symlink",
                "missing": section_names, "symlink": True}
    text = readme.read_text(encoding="utf-8", errors="replace")
    headings = [norm(h[1]) for h in read_headings(text)]
    missing = []
    for sec, _ann in sections:
        sn = norm(sec)
        if not any(sn in h for h in headings):
            missing.append(sec)
    status = "pass" if not missing else "fail"
    reason = None if not missing else "missing sections: " + ", ".join(missing)
    return {"package": pkg.name, "path": rel, "readme": readme.name,
            "status": status, "reason": reason, "missing": missing,
            "symlink": readme.is_symlink()}


def parse_require(value: str, sections):
    """Merge a --require heading=Annotation pair into the section list.

    Replaces an existing entry whose normalised heading matches
    (overridable), otherwise appends. Defaults are retained unless explicitly
    replaced.
    """
    if "=" in value:
        h, ann = value.split("=", 1)
    else:
        h, ann = value, None
    h = h.strip()
    hn = norm(h)
    for i, (s, _a) in enumerate(sections):
        if norm(s) == hn:
            sections[i] = (h, ann)
            return sections
    sections.append((h, ann))
    return sections


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Deepseek-style per-package README contract check.")
    ap.add_argument("packages", nargs="*", metavar="PACKAGE",
                    help="explicit package directories (overrides --packages-dir)")
    ap.add_argument("--packages-dir", default=None,
                    help="directory containing packages (default: autodetect "
                         "first of ./packages, ./src, ./cmd)")
    ap.add_argument("--require", action="append", default=[], metavar="heading=Annotation",
                    help="add or override a required contract heading "
                         "(default: %s)" % ", ".join(s[0] for s in DEFAULT_SECTIONS))
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    sections = list(DEFAULT_SECTIONS)
    for r in args.require:
        sections = parse_require(r, sections)

    # A directory with a .vendored marker holds third-party code; its README is not ours to write.
    pkgs = [p for p in discover_packages(args.packages_dir, args.packages)
            if not (p / ".vendored").exists()]

    if not pkgs:
        if args.json:
            print(json.dumps({
                "packages_dir": args.packages_dir or "autodetect",
                "required_sections": [s[0] for s in sections],
                "results": [],
                "summary": {"pass": 0, "fail": 0, "total": 0},
                "note": "no packages discovered (not a monorepo, or no "
                        "packages/src/cmd directory found)",
                "exit_code": 0,
            }, indent=2))
        else:
            print("No packages discovered "
                  "(no packages/, src/, or cmd/ dir; no explicit paths given).")
            print("Nothing to check. PASS")
        return 0

    results = [check_contract(p, sections) for p in pkgs]
    fails = sum(1 for r in results if r["status"] == "fail")
    passes = len(results) - fails

    if args.json:
        out = {
            "packages_dir": args.packages_dir or "autodetect",
            "required_sections": [{"heading": s[0], "annotation": s[1]} for s in sections],
            "results": results,
            "summary": {"pass": passes, "fail": fails, "total": len(results)},
            "exit_code": 0 if fails == 0 else 2,
        }
        print(json.dumps(out, indent=2))
        return 0 if fails == 0 else 2

    pd_label = args.packages_dir or "autodetect"
    print(f"Contract headings: {', '.join(s[0] for s in sections)}")
    print(f"Packages dir: {pd_label}  ({len(results)} package(s))\n")
    for r in results:
        if r["status"] == "pass":
            sl = " (symlink)" if r["symlink"] else ""
            print(f"{r['path']}: PASS  README={r['readme']}{sl}")
        else:
            print(f"{r['path']}: FAIL  — {r['reason']}")
            if r.get("missing"):
                print(f"    missing: {', '.join(r['missing'])}")
    print(f"\nPASS={passes} FAIL={fails}")
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
