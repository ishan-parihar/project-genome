#!/usr/bin/env python3
"""Measure the federation's class-hit rate: does a question that names a doc class get that class's document?

The bug this measures: every card class resolved, but `genome ask --all` almost never returned the
class document. A routing row's own question text ("where does the project stand right now") matches a
natural-language question better than a class heading does, and the routing row scored 2.5 against the
class headings' 1.5. The card map was right and the ranking was answering something else.

The measure, per doc class: for every repo whose card resolves that class, ask the class's own question
about that repo and check whether the repo's TOP hit points at its #<class> class.

Usage: python3 evals/measure-class-hit.py [CARDS_DIR] [SKILL_SCRIPTS]
  CARDS_DIR     the federation cache; default ~/.cache/genome/cards
  SKILL_SCRIPTS where the genome CLI lives; default <skill>/scripts (the vendored copy is what the fleet runs)

Exit code 0 when every repo/class pair hits, 1 when any misses, so it can be a gate.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

CARDS = Path(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/.cache/genome/cards"))
SKILL = Path(os.path.expanduser(sys.argv[2])) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "scripts"
CLI = SKILL / "genome"

# the class's own question, asked about one repo at a time
SHAPES = {
    "architecture": "how is {r} built architecture",
    "decisions": "why is {r} this way",
    "status": "where does {r} stand",
    "operate": "how do I run {r}",
    "intent": "what is {r}",
    # the offer class is opt-in (no role, no fallback), so it is measured only
    # for the repos whose card actually resolves it
    "offer": "what should we offer for {r} and at what price",
}


def meta_root(cards: dict) -> Path:
    """The federation's root: the deepest directory that holds a genome.toml and contains every member.

    `ask --all` needs a config to read (the cache path comes from GENOME_CARDS, but the CLI still
    wants a root), so the root is the meta directory the members sit under.
    """
    roots = [Path(c["root"]).resolve() for c in cards.values()]
    common = Path(os.path.commonpath([str(r) for r in roots]))
    for cand in [common, *common.parents]:
        if (cand / "genome.toml").is_file():
            return cand
    # the members do not share a root that holds a genome: fall back to any member's own root
    for r in roots:
        for cand in [r, *r.parents]:
            if (cand / "genome.toml").is_file():
                return cand
    raise SystemExit("no genome.toml above any member's repo: is the cache a federation cache?")


def ask(question: str, cwd: Path) -> list[dict]:
    r = subprocess.run([sys.executable, str(CLI), "ask", "--all", question, "--json"],
                       capture_output=True, text=True, cwd=str(cwd),
                       env={**os.environ, "GENOME_CARDS": str(CARDS)})
    if r.returncode != 0:
        raise SystemExit(f"ask --all failed: {r.stderr.strip() or r.stdout.strip()}")
    return json.loads(r.stdout)["hits"]


def main() -> None:
    if not CARDS.is_dir():
        raise SystemExit(f"no cards at {CARDS}: run `genome federate` at the meta root first")
    cards = {}
    for p in sorted(CARDS.glob("*.json")):
        try:
            c = json.loads(p.read_text())
        except ValueError:
            continue
        if c.get("root") and Path(c["root"]).is_dir():   # a card whose repo is gone is not a member
            cards[c["name"]] = c
    if not cards:
        raise SystemExit(f"no live cards in {CARDS}")
    root = meta_root(cards)
    print(f"cards: {len(cards)} (from {CARDS})")
    print(f"root:  {root}")
    print(f"cli:   {CLI}")
    total_ok = total = 0
    misses = []
    for cls, shape in SHAPES.items():
        ok = n = 0
        for name, card in sorted(cards.items()):
            if not card.get("classes", {}).get(cls, {}).get("path"):
                continue
            hits = ask(shape.format(r=name), root)
            mine = [h for h in hits if h["repo"] == name]
            if not mine:
                continue
            n += 1
            if mine[0]["pointer"].endswith("#" + cls):
                ok += 1
            else:
                misses.append((cls, name, mine[0]["pointer"]))
        total_ok += ok
        total += n
        print(f"  {cls:<13} top hit is the #{cls} class in {ok}/{n}")
    print(f"TOTAL: {total_ok}/{total}")
    for cls, name, ptr in misses:
        print(f"    miss [{cls}] {name} -> {ptr}")
    sys.exit(0 if total_ok == total else 1)


if __name__ == "__main__":
    main()
