#!/usr/bin/env python3
"""genome-outline: emit a KB's stack outline into a generated zone.

Prototype for the `outline` module proposed in
docs/plans/2026-10-27-KB-OUTLINE-SCHEMA.md. It implements the derivation for the five
tables and the zone write, so the proposal's claims can be tested rather than argued.

The rule it is built around: EVERY row is derived, and a fact with no source is dropped
rather than asserted. That is why the emitters return None freely and the caller prints
"not derivable" instead of guessing.

Usage:
    genome-outline.py [--check] [--root DIR]

Exits 1 on --check when the zone is stale.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ZONE = "stack"
# Language probes, in the order the schema names them: read the manifest, never the
# directory name. A directory called `twitter-lyr` tells you nothing about its language.
MANIFESTS = [
    ("Cargo.toml", "rust"),
    ("pyproject.toml", "python"),
    ("package.json", "javascript-or-typescript"),
    ("go.mod", "go"),
    ("genome.toml", "genome"),
]
SOURCE_DIRS = ("src", "lib", "crates", "pkg", "cmd", "app", "skills")
TEST_DIRS = ("tests", "test", "spec")
# Names that are never a source tree: build output, vendored code and data. A file
# count that includes them is a number the repository cannot reproduce.
SKIP_DIRS = {"node_modules", "dist", "build", "target", ".git", "__pycache__", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", ".venv", "venv", "egg-info", "vendor",
             "uploads", "probe-out", "samples", "assets"}
# Extensions by language, for the LOC-by-language table. Absent means the language is
# not counted rather than counted as zero.
LOC_EXTS = {
    "rust": (".rs",), "python": (".py",), "go": (".go",),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"), "typescript": (".ts", ".tsx"),
}


def sh(root: Path, *args: str) -> str:
    """One command's stdout, or '' when it fails. Empty is a real answer, never an error."""
    try:
        out = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=60)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


# ---------------------------------------------------------------- derivations

def derive_language(root: Path) -> tuple[str, str]:
    """(language, evidence). Read from the manifest, so a Rust member is never called Python.

    A `package.json` alone cannot say TypeScript from JavaScript, and guessing there is
    how "all Python" happens: a claim that one member silently falsifies. So the
    TypeScript answer is only given when a `tsconfig.json` exists, and the plain
    JavaScript answer when it does not. `manifest` never overrides a real manifest.
    """
    for name, lang in MANIFESTS:
        if (root / name).is_file():
            if name == "package.json" and (root / "tsconfig.json").is_file():
                return "typescript", "package.json + tsconfig.json"
            return lang, name
    return "not derivable", "no manifest among Cargo.toml/pyproject.toml/package.json/go.mod"


def derive_layout(root: Path) -> tuple[list[str], list[str], str]:
    """(source dirs, test dirs, entry point), each only when it exists on disk.

    THE SOURCE DIRS COMES FROM THE MANIFEST FIRST. A package named in its own
    manifest IS the source tree, whatever it is called: meesho-lyr's package is
    `meesho_cli/`, not `src/`, and probing only the conventional names would
    report "no source derived" for a 2,000-line Python project. So the declared
    package directory is read before the conventional list, never after it.
    """
    src: list[str] = []
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        m = re.search(r'^\s*(?:name|path)\s*=\s*"([^"]+)"', cargo.read_text(errors="replace"), re.M)
        if m and (root / m.group(1)).is_dir():
            src.append(m.group(1))
    pyp = root / "pyproject.toml"
    if pyp.is_file():
        txt = pyp.read_text(errors="replace")
        # The declared package, in either shape it is written. meesho-lyr uses
        # `[tool.setuptools.packages.find]` with an include list; a flat project uses
        # `packages = ["pkg"]`. Both name the source tree, and both beat a guess.
        cands = [c.rstrip("*").replace(".", "/")
                 for c in re.findall(r'include\s*=\s*\[([^\]]*)\]', txt)[0:1]
                 for c in re.findall(r'"([^"]+)"', c)] if "packages.find" in txt else []
        cands += [c.replace(".", "/") for c in re.findall(r'packages\s*=\s*\[([^\]]*)\]', txt)
                  for c in re.findall(r'"([^"]+)"', c)]
        # A package directory is usually named after the project itself.
        name = re.search(r'^name\s*=\s*"([^"]+)"', txt, re.M)
        if name and (root / name.group(1).replace("-", "_")).is_dir():
            cands.append(name.group(1).replace("-", "_"))
        for c in cands:
            if c and (root / c).is_dir() and c not in src:
                src.append(c)
    pj = root / "package.json"
    if pj.is_file():
        m = re.search(r'"main"\s*:\s*"([^"]+)"', pj.read_text(errors="replace"))
        cand = m.group(1).rsplit("/", 1)[0] if m else ""
        if cand and (root / cand).is_dir() and cand not in src and cand not in SKIP_DIRS:
            src.append(cand)
    for d in SOURCE_DIRS:
        if (root / d).is_dir() and d not in src and d not in SKIP_DIRS:
            src.append(d)
    tst = [d for d in TEST_DIRS if (root / d).is_dir()]
    entry = ""
    for cand in ("src/index.ts", "src/main.ts", "src/cli.ts", "src/lib.rs", "src/main.rs",
                 "src/index.py", "src/main.py", "src/cli.py", "main.go", "cli.py", "cli.rs",
                 "src/index.js", "src/main.js"):
        if (root / cand).is_file():
            entry = cand
            break
    # A manifest-declared package's own __init__ is the entry point when there is
    # no conventional src/ layout, so the entry point is found by the same rule.
    if not entry and src:
        for base, cand in ((".py", f"{src[0]}/__init__.py"), (".rs", f"{src[0]}/lib.rs"),
                           (".ts", f"{src[0]}/index.ts")):
            if (root / cand).is_file():
                entry = cand
                break
    return src, tst, entry


def derive_size(root: Path, src: list[str]) -> list[tuple[str, int, str]]:
    """[(label, count, ext)] per language, over the source dirs only."""
    if not src:
        return []
    files: dict[str, int] = {}
    exts: dict[str, tuple[str, ...]] = {}
    for d in src:
        for p in (root / d).rglob("*"):
            if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
                continue
            matched = next((lang for lang, es in LOC_EXTS.items() if p.suffix in es), None)
            if matched:
                files[matched] = files.get(matched, 0) + 1
                exts[matched] = next(es for l, es in LOC_EXTS.items() if l == matched)
    return [(lang, n, "/".join(exts[lang])) for lang, n in sorted(files.items(), key=lambda kv: -kv[1])]


def derive_gate(root: Path) -> tuple[str, str]:
    """(gate command, evidence). genome.toml's own setting, else the same probe genome init uses."""
    gt = root / "genome.toml"
    if gt.is_file():
        m = re.search(r'^\s*gate\s*=\s*"([^"]+)"', gt.read_text(errors="replace"), re.M)
        if m:
            return m.group(1), "genome.toml"
    for f, g in (("Cargo.toml", "cargo test --locked"), ("pyproject.toml", "pytest -q"),
                 ("package.json", "npm test"), ("go.mod", "go test ./...")):
        if (root / f).is_file():
            return g, f"probed from {f} (genome.toml has no gate)"
    return "", "no gate derivable"


def derive_deps(root: Path) -> tuple[list[str], list[str]]:
    """(third-party, first-party). First-party = resolvable inside the meta-directory."""
    third: list[str] = []
    pj = root / "package.json"
    if pj.is_file():
        txt = pj.read_text(errors="replace")
        for block in ("dependencies", "devDependencies"):
            m = re.search(rf'"{block}"\s*:\s*\{{(.*?)\}}', txt, re.S)
            if m:
                third += re.findall(r'"([^"]+)"\s*:', m.group(1))
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        m = re.search(r'\[dependencies\](.*?)(?:\n\[|\Z)', cargo.read_text(errors="replace"), re.S)
        if m:
            third += re.findall(r'^([A-Za-z0-9_.-]+)\s*=', m.group(1), re.M)
    pyp = root / "pyproject.toml"
    if pyp.is_file():
        m = re.search(r'dependencies\s*=\s*\[(.*?)\]', pyp.read_text(errors="replace"), re.S)
        if m:
            # Each entry is a quoted requirement spec: "click>=8.1", "curl_cffi".
            # Taking the requirement NAME, not the whole spec, is what stops the
            # separator itself from becoming a row: a naive split on commas leaves
            # "8.1" behind and a bare "," ends up in the table.
            for spec in re.findall(r'"([^"]+)"', m.group(1)):
                name = re.split(r'[<>=!~\[\s;]', spec.strip(), maxsplit=1)[0]
                if name and re.fullmatch(r'[A-Za-z0-9_.-]+', name):
                    third.append(name)
    mono = find_monorepo(root)
    first = [d for d in third if mono and (mono / d.replace(".", "/")).exists()]
    return sorted(set(third) - set(first)), first


def find_monorepo(root: Path) -> Path | None:
    """The meta-directory, found by walking up for the allowlisted .gitignore."""
    for cand in [root, *root.parents]:
        gi = cand / ".gitignore"
        if gi.is_file() and re.search(r'^/\*\s*$', gi.read_text(errors="replace"), re.M):
            return cand
    return None


def derive_wiring(root: Path, src: list[str]) -> list[tuple[str, str]]:
    """[(from, to)] import edges inside the source tree, one row per edge."""
    edges: set[tuple[str, str]] = set()
    if not src:
        return []
    top = root / src[0]
    modules = {p.stem for p in top.glob("*.ts")} | {p.stem for p in top.glob("*.py")} \
        | {p.stem for p in top.glob("*.rs")}
    for p in top.rglob("*"):
        if not p.is_file() or p.suffix not in (".ts", ".tsx", ".py", ".rs"):
            continue
        txt = p.read_text(errors="replace")
        rel = str(p.relative_to(root))
        for m in re.finditer(r'from\s+["\']\./([\w.-]+)["\']', txt):
            edges.add((rel, f"{src[0]}/{m.group(1)}"))
        for m in re.finditer(r'^\s*(?:from|import)\s+\.([\w.]*)', txt, re.M):
            tgt = m.group(1).lstrip(".").replace(".", "/")
            if tgt.split("/")[-1] in modules or tgt in modules:
                edges.add((rel, f"{src[0]}/{tgt}"))
        for m in re.finditer(r'^\s*(?:use|mod)\s+(\w+)\s*;', txt, re.M):
            if m.group(1) in modules:
                edges.add((rel, f"{src[0]}/{m.group(1)}"))
    return sorted(edges)


# ---------------------------------------------------------------- render

def render(root: Path) -> str:
    head = sh(root, "git", "rev-parse", "--short", "HEAD") or "uncommitted"
    lang, lang_ev = derive_language(root)
    src, tst, entry = derive_layout(root)
    size = derive_size(root, src)
    gate, gate_ev = derive_gate(root)
    third, first = derive_deps(root)
    edges = derive_wiring(root, src)

    lines = [f"**Generated by `genome outline` at `{head}`. Facts only; the prose is in "
             f"`docs/OUTLINE.md`.**", "",
             f"### Language and layout — read from `{lang_ev}`, not from the directory name", "",
             "| Fact | Value |", "|---|---|", f"| language | `{lang}` |",
             # One row, comma-joined: two `| source |` rows read as a table mistake, and
             # the reader wants the layout, not a row per directory.
             f"| source | {' · '.join(f'`{d}/`' for d in src) or 'not derivable'} |",
             f"| tests | {' · '.join(f'`{d}/`' for d in tst) or 'not derivable'} |"]
    lines.append(f"| entry point | `{entry}` |" if entry else "| entry point | not derivable |")
    lines.append("")

    lines += ["### Size — files counted under the source dirs, excluding build and cache dirs", "",
              "| Language | Files | Extensions counted |", "|---|---|---|"]
    lines += [f"| {l} | {n} | `{e}` |" for l, n, e in size] or ["| — | 0 | none found |"]
    lines.append("")

    lines += [f"### Gate — {gate_ev}", "", f"```", f"{gate or 'no gate derivable'}", "```", ""]

    lines += ["### Dependencies — split by whether the target resolves in the meta-directory", "",
              "| Third-party |", "|---|"]
    lines += [f"| `{d}` |" for d in third[:24]] or ["| none declared |"]
    lines += ["", "| First-party |", "|---|"]
    lines += [f"| `{d}` |" for d in first] or ["| none resolved |"]
    lines.append("")

    lines += ["### Wiring — one row per import edge inside the source tree", "",
              "| From | To |", "|---|---|"]
    lines += [f"| `{a}` | `{b}` |" for a, b in edges[:40]] or ["| — | no edges derived |"]
    lines += ["", "How these parts fit together, and the order to read them in: `docs/OUTLINE.md`.", ""]
    return "\n".join(lines)


def zone_block(body: str) -> str:
    import hashlib
    sha = hashlib.sha256(body.encode()).hexdigest()[:12]
    body = body if body.endswith("\n") else body + "\n"
    return f"<!-- genome:zone {ZONE} sha={sha} -->\n{body}<!-- genome:end {ZONE} -->"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=".")
    ap.add_argument("--file", default="AGENTS.md")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    target = root / args.file
    if not target.is_file():
        print(f"genome outline: no {args.file} at {root} — run `genome init` first")
        return 1

    body = render(root)
    new = zone_block(body)
    text = target.read_text(errors="replace")
    pat = re.compile(r"<!-- genome:zone stack sha=[0-9a-f]+ -->.*?<!-- genome:end stack -->", re.S)
    m = pat.search(text)

    if m:
        stale = m.group(0) != new
        if args.check:
            print(f"genome outline --check: {'STALE' if stale else 'fresh'} ({args.file}#{ZONE})")
            if stale:
                print("  the tree changed since the zone was emitted — run `genome outline`")
                return 1
            return 0
        if not stale:
            print(f"genome outline: {args.file}#{ZONE} already fresh")
            return 0
        target.write_text(text[:m.start()] + new + text[m.end():], encoding="utf-8")
    else:
        if args.check:
            print(f"genome outline --check: ABSENT ({args.file}#{ZONE})")
            return 1
        placeholder = f"<!-- genome:zone {ZONE} -->"
        if placeholder in text:
            target.write_text(text.replace(placeholder, new, 1), encoding="utf-8")
        else:
            target.write_text(text.rstrip("\n") + "\n\n" + new + "\n", encoding="utf-8")

    print(f"genome outline: wrote {args.file}#{ZONE} ({len(body.splitlines())} lines, "
          f"head {sh(root, 'git', 'rev-parse', '--short', 'HEAD') or 'uncommitted'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
