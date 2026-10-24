#!/usr/bin/env python3
"""Mechanical grading of an eval run: the `checks` of an eval in evals.json, run against the repo the agent worked in.

Usage: python3 evals/grade.py <eval-id> <repo> [--genome PATH]     (exit 0 when every check passes)
Checks (all optional per eval; the prose `assertions` stay for a human or model grader):
  {"exists": ["path", ...]}                    every path exists
  {"unchanged": ["path", ...]}                 byte-identical to the fixture's first commit
  {"cmd": "genome lint", "exit": 0, "stdout_has": "text", "stdout_lacks": "text"}   `genome` expands to the repo's CLI
"""
import json
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent


def sh(repo, cmd, genome):
    return subprocess.run(cmd.replace("genome ", f"python3 {genome} ", 1) if cmd.startswith("genome ") else cmd,
                          shell=True, cwd=repo, capture_output=True, text=True)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    eval_id, repo = int(args[0]), Path(args[1])
    genome = sys.argv[sys.argv.index("--genome") + 1] if "--genome" in sys.argv else \
        str(repo / "scripts/genome" if (repo / "scripts/genome").exists() else here.parent / "scripts/genome")
    ev = next(e for e in json.load(open(here / "evals.json"))["evals"] if e["id"] == eval_id)
    root = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.split()[0]
    failed = 0
    for c in ev.get("checks", []):
        ok, why = True, ""
        for p in c.get("exists", []):
            if not (repo / p).exists():
                ok, why = False, f"missing {p}"
        for p in c.get("unchanged", []):
            d = subprocess.run(["git", "diff", "--quiet", root, "--", p], cwd=repo)
            if d.returncode or subprocess.run(["git", "status", "--porcelain", "--", p], cwd=repo, capture_output=True, text=True).stdout.strip():
                ok, why = False, f"{p} differs from the fixture"
        if "cmd" in c:
            r = sh(repo, c["cmd"], genome)
            if r.returncode != c.get("exit", 0):
                ok, why = False, f"`{c['cmd']}` exited {r.returncode}: {(r.stdout + r.stderr)[-300:]}"
            elif c.get("stdout_has") and c["stdout_has"] not in r.stdout:
                ok, why = False, f"`{c['cmd']}` output lacks {c['stdout_has']!r}"
            elif c.get("stdout_lacks") and c["stdout_lacks"] in r.stdout:
                ok, why = False, f"`{c['cmd']}` output has {c['stdout_lacks']!r}"
        print(("PASS " if ok else "FAIL ") + (c.get("name") or c.get("cmd") or ",".join(c.get("exists", c.get("unchanged", [])))) + ("" if ok else f" — {why}"))
        failed += not ok
    print(f"eval {eval_id} ({ev['name']}): {len(ev.get('checks', [])) - failed}/{len(ev.get('checks', []))} mechanical checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
