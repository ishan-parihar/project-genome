#!/usr/bin/env python3
"""The outline derivation, exercised across every language in the fleet.

Not a regression suite: a probe. It builds one throwaway repo per language, runs the
real `genome outline` against it, and asserts the language row names the manifest it
was read from. The rule the schema exists to prove is that no repository is called the
wrong language, and a repo named `twitter-lyr` that is Rust is the case that breaks a
dirname-derived guess.

Usage: python3 scripts/probe-outline-languages.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

G = str(Path(__file__).with_name("genome"))
ROOT = Path(__file__).resolve().parent.parent

# (label, files to write, expected language, the manifest the row must name)
CASES = [
    ("rust", {
        "Cargo.toml": '[package]\nname = "thing"\n\n[dependencies]\ntokio = "1"\n',
        "src/lib.rs": "pub mod pool;\n",
        "src/pool.rs": "pub struct Pool;\n",
    }, "rust", "Cargo.toml"),
    ("rust-plain-mod", {
        "Cargo.toml": '[package]\nname = "t2"\n',
        "src/main.rs": "mod util;\nfn main() {}\n",
        "src/util.rs": "pub fn u() {}\n",
    }, "rust", "Cargo.toml"),
    ("python", {
        "pyproject.toml": '[project]\nname = "thing"\ndependencies = ["click>=8.1", "rich", "httpx~=0.27"]\n',
        "thing/__init__.py": "from .client import Client\n",
        "thing/client.py": "import httpx\n",
    }, "python", "pyproject.toml"),
    ("python-setuptools-find", {
        "pyproject.toml": '[project]\nname = "meesho-ish"\n\n[tool.setuptools.packages.find]\nwhere = ["."]\ninclude = ["meesho_cli*"]\n',
        "meesho_cli/__init__.py": "from .cli import main\n",
        "meesho_cli/cli.py": "def main():\n    pass\n",
    }, "python", "pyproject.toml"),
    ("typescript", {
        "package.json": '{"name":"thing","main":"dist/index.js"}',
        "tsconfig.json": '{"compilerOptions":{}}',
        "src/index.ts": "import { helper } from './helper';\n",
        "src/helper.ts": "export const helper = 1;\n",
    }, "typescript", "package.json + tsconfig.json"),
    ("typescript-explicit-ext", {
        "package.json": '{"name":"t5","main":"dist/index.js"}',
        "tsconfig.json": '{"compilerOptions":{}}',
        "src/index.ts": "import { b } from './b.js';\n",
        "src/b.ts": "export const b = 2;\n",
    }, "typescript", "package.json + tsconfig.json"),
    ("javascript-no-tsconfig", {
        "package.json": '{"name":"thing","main":"dist/index.js","dependencies":{"axios":"^1"},"devDependencies":{"vitest":"^1"}}',
        "src/index.js": "const a = require('axios');\n",
    }, "javascript", "package.json"),
    ("go", {
        "go.mod": "module example.com/thing\n\ngo 1.22\n",
        "cmd/main.go": "package main\n\nimport \"example.com/thing/internal/pool\"\n\nfunc main() { _ = pool.P{} }\n",
        "internal/pool/pool.go": "package pool\n\ntype P struct{}\n",
    }, "go", "go.mod"),
    ("no-manifest", {
        "src/index.py": "x = 1\n",
    }, "not derivable", "no manifest (Cargo.toml / pyproject.toml / package.json / go.mod)"),
]


def build(root: Path, files: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    (root / "genome.toml").write_text('[genome]\nmodules = ["core", "outline"]\n')
    (root / "AGENTS.md").write_text("# a\n\n<!-- genome:zone stack -->\n")


def zone(path: Path) -> str:
    t = path.read_text()
    a = t.find("<!-- genome:zone stack")
    b = t.find("<!-- genome:end stack -->")
    return t[a:b + 25] if a >= 0 and b >= 0 else ""


def main() -> int:
    bad = 0
    for label, files, want_lang, want_ev in CASES:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, files)
            r = subprocess.run([sys.executable, G, "outline"], cwd=root, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"FAIL  {label:26} outline exited {r.returncode}\n{r.stdout}{r.stderr}")
                bad += 1
                continue
            z = zone(root / "AGENTS.md")
            ok_lang = f"| language | `{want_lang}` |" in z
            # the evidence string is inside the heading of the first table
            ok_ev = f"read from `{want_ev}`" in z
            if ok_lang and ok_ev:
                # the module's own read-only check must agree the zone is current
                c = subprocess.run([sys.executable, G, "outline-check"], cwd=root, capture_output=True, text=True)
                fresh = c.returncode == 0
                if fresh:
                    print(f"PASS  {label:26} {want_lang:14} from {want_ev}")
                else:
                    print(f"FAIL  {label:26} language ok but --check says stale:\n{c.stdout}{c.stderr}")
                    bad += 1
            else:
                print(f"FAIL  {label:26} wanted {want_lang}/{want_ev}; got:\n{z[:400]}")
                bad += 1
    print(f"\nprobe: {len(CASES) - bad}/{len(CASES)} languages derive correctly")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
