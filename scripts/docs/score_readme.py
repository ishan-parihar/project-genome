#!/usr/bin/env python3
"""Score a README against the quality bar (see ../references/audit-rubric.md).

Usage: python3 score_readme.py README.md [--archetype NAME] [--json]

Exit 0 when no issues remain, else 1 (CI-usable). No dependencies.

Generalized from readme-quality-engineering's rubric. The value-prop check is
structural (a real first paragraph, not placeholders) instead of keyword-based,
so it works for any domain.

--archetype makes the thresholds archetype-relative (../references/archetypes.md).
Without a flag the generic README-shaped band applies, which is WRONG for curated
lists and learning resources: a correct 400+ line awesome-list scores negative
because it has no install section, no code examples, and no badges. Measured
against 11 high-profile repos (see ../references/mechanisms.md):

  archetype          length band     images  code  tables  badges
  doorway            70-340          >=1     >=2   any     <=7
  skills-pack        150-400         any*    >=2   any     <=7
  curated-list       400-2700        n/a     n/a   any     any
  learning-resource  800-2000        >=1     any   >=1     any
  monorepo           70-340          any*    >=2   any     <=7
  generic (default)  100-170         >=3     >=2   >=1     <=7

  * "any" = falls back to "a concrete artifact exists" (image OR code block).
  curated-list substitutes entry density (>=10 markdown links) for visual proof.

All eight checks run in every archetype so the scale stays comparable; a
threshold of 0 means "this archetype does not owe this", and those checks are
reported as not-applicable rather than counted as strengths.
"""
import argparse
import json
import re
import sys

# Per-archetype thresholds, from the 11-repo audit in ../references/archetypes.md.
ARCHETYPES = {
    #               length(min,max)  min_img  min_code  min_tables  min_entries
    "doorway":           dict(length=(70, 340),   min_images=1, min_code=2, min_tables=0, min_entries=0),
    "skills-pack":       dict(length=(150, 400),  min_images=0, min_code=2, min_tables=0, min_entries=0),
    "curated-list":      dict(length=(400, 2700), min_images=0, min_code=0, min_tables=0, min_entries=10),
    "learning-resource": dict(length=(800, 2000), min_images=1, min_code=0, min_tables=1, min_entries=0),
    "monorepo":          dict(length=(70, 340),   min_images=0, min_code=2, min_tables=0, min_entries=0),
    # No archetype declared: the README-shaped default.
    "generic":           dict(length=(100, 170),  min_images=3, min_code=2, min_tables=1, min_entries=0),
}

# No audited repo exceeds 7 badges and 6/11 use zero, so the ceiling is the
# evidence-backed check; a floor is not (a floor would fail n8n's correct 0).
BADGE_CEILING = 7
ARCH_INCIPIENT = ["architecture", "tech stack", "project structure", "technologies used"]
INSTALL_KW = ["install", "quick start", "getting started", "setup"]
PROOF_KW = ["visual proof", "proof", "screenshot", "output", "example", "showcase", "demo"]


def get_first_paragraph(content: str) -> str:
    """First prose paragraph within the first screen.

    A blockquote is a legitimate hook (system-design-primer and the awesome-list
    convention both open with one), so `>` lines count and the marker is stripped.
    Skip headings, images, tables, and list items.
    """
    for line in content.split("\n")[:40]:
        s = line.strip()
        if s.startswith(">"):
            s = s.lstrip(">").strip()
        # a list marker is "- " / "* " / "+ "; "**bold**" opens prose and is not a list item
        if s and not s.startswith(("#", "!", "[", "|")) and not re.match(r"[-*+]\s|([-*_]\s*){3,}$", s):
            return s
    return ""


def find_section_index(content: str, keywords: list) -> int | None:
    for i, line in enumerate(content.split("\n")):
        if line.startswith(("## ", "### ")):
            title = line.lstrip("# ").strip().lower()
            if any(k in title for k in keywords):
                return i
    return None


def order_ok(content, first_kw, second_kw) -> bool:
    a = find_section_index(content, first_kw)
    b = find_section_index(content, second_kw)
    if a is not None and b is not None:
        return a < b
    return True  # a missing section is not an ordering violation


MANIFESTS = ("Cargo.toml", "package.json", "pyproject.toml", "go.mod")


def detect_archetype(content: str, repo_dir) -> tuple[str, str]:
    """Pick an archetype from the repo's shape. Returns (name, reason).

    Conservative on purpose: a non-doorway label needs a strong structural
    signal, because doorway is the default for most fleet repos (72 of 93 in
    DOCS-SYSTEM-PLAN §4.5). Signals are counted on disk, not guessed from prose.
    """
    from pathlib import Path
    root = Path(repo_dir)
    # monorepo: three or more member packages under crates/ or packages/
    members = [d for name in ("crates", "packages") if (root / name).is_dir()
               for d in (root / name).iterdir()
               if d.is_dir() and any((d / m).exists() for m in MANIFESTS)]
    if len(members) >= 3 and re.search(r"\b(crates|packages)/", content):
        return "monorepo", f"{len(members)} member packages, and the README names crates/ or packages/"
    # skills-pack: three or more SKILL.md files in subdirectories (one root SKILL.md is one skill)
    skill_files = [p for p in root.glob("*/SKILL.md")] + [p for p in root.glob("skills/*/SKILL.md")]
    if len(skill_files) >= 3 and re.search(r"skill", content, re.I):
        return "skills-pack", f"{len(skill_files)} SKILL.md files in subdirectories"
    # learning-resource: long reference text with no install section
    lines = content.count("\n") + 1
    if lines >= 1000 and not re.search(r"^#+\s*(install|quick start|getting started)", content, re.I | re.M):
        return "learning-resource", f"{lines} lines and no install section"
    entries = len(re.findall(r"^\s*[-*+]\s+\[[^\]]*\]\([^)]*\)", content, re.M))
    # curated-list: the README IS the data. references/curated-list.md lists its
    # "Forbidden sections": install instructions, usage examples, and code blocks.
    # A README that has any of those is a doorway that happens to link out a lot,
    # however many bullets it carries — so entry count alone is not enough.
    # (The entry-count-only test mis-classified a 133-line doorway with an
    # 11-item docs index as a curated list, which then failed length_in_band
    # against the 400-line floor for a list it was not.)
    code_fences = len(re.findall(r"^```", content, re.M))
    has_install = bool(re.search(r"^#+\s*(install|quick start|getting started|setup|usage)", content, re.I | re.M))
    if entries >= 10 and not has_install and code_fences == 0:
        return "curated-list", f"{entries} linked list entries, no install section and no code blocks"
    return "doorway", "default: no monorepo, skills-pack, learning or list shape"


def score_readme(content: str, archetype: str = "generic") -> dict:
    cfg = ARCHETYPES[archetype]
    lines = content.split("\n")
    images = len(re.findall(r"!\[.*?\]\(.*?\)", content))
    code_blocks = len(re.findall(r"```", content)) // 2
    tables = len(re.findall(r"\|.*\|.*\n\|[-:| ]+\|", content))
    bullets = len(re.findall(r"^\s*[-*+]\s+\S", content, re.M))
    links = len(re.findall(r"\[[^\]]*\]\([^)]*\)", content))
    badges = len(re.findall(r"!\[.*?\]\(https://img\.shields\.io", content))
    first_para = get_first_paragraph(content)

    # Proof check: the form the archetype's audience expects.
    if cfg["min_images"] > 0:
        proof_name, proof_ok = f"visual_proof_{cfg['min_images']}plus", images >= cfg["min_images"]
    elif cfg["min_entries"] > 0:
        proof_name, proof_ok = f"entry_density_{cfg['min_entries']}plus", links >= cfg["min_entries"]
    else:
        # skills-pack / monorepo / curated-list: a concrete artifact suffices
        proof_name, proof_ok = "concrete_artifact", images >= 1 or code_blocks >= 1

    checks = [
        ("value_prop_clear", len(first_para) >= 20 and "[" not in first_para),
        (proof_name, proof_ok),
        ("proof_before_arch", order_ok(content, PROOF_KW, ARCH_INCIPIENT)),
        ("install_before_arch", order_ok(content, INSTALL_KW, ARCH_INCIPIENT)),
        ("code_examples_2plus", code_blocks >= cfg["min_code"]),
        ("tables_for_structure", tables >= cfg["min_tables"]),
        ("badges_within_ceiling", badges <= BADGE_CEILING),
        ("length_in_band", cfg["length"][0] <= len(lines) <= cfg["length"][1]),
    ]

    # A threshold of 0 means "this archetype does not owe this", not "this
    # archetype excelled at it" — report them so a clean 8/8 with three vacuous
    # passes is not mistaken for an 8/8 with eight real ones.
    vacuous = set()
    if cfg["min_code"] == 0:
        vacuous.add("code_examples_2plus")
    if cfg["min_tables"] == 0:
        vacuous.add("tables_for_structure")
    if cfg["min_images"] == 0 and cfg["min_entries"] == 0:
        vacuous.add(proof_name)

    strengths = [n for n, p in checks if p]
    issues = [n for n, p in checks if not p]
    return {
        "archetype": archetype,
        "strengths": strengths,
        "issues": issues,
        "not_applicable": sorted(vacuous),
        "score": len(strengths) - len(issues),
        "detail": {"lines": len(lines), "images": images, "code_blocks": code_blocks,
                   "tables": tables, "bullets": bullets, "links": links,
                   "badges": badges},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("readme")
    ap.add_argument("--archetype", default="generic",
                    choices=sorted(ARCHETYPES.keys()) + ["auto"],
                    help="documentation archetype (../references/archetypes.md); "
                         "'auto' infers it from the repo shape and prints the reason")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    import os
    with open(args.readme) as f:
        content = f.read()
    chosen, reason = args.archetype, "explicit --archetype"
    if args.archetype == "auto":
        chosen, reason = detect_archetype(content, os.path.dirname(os.path.abspath(args.readme)))
    r = score_readme(content, chosen)
    r["archetype_reason"] = reason

    if args.json:
        print(json.dumps(r, indent=2))
        return 0 if not r["issues"] else 1

    d = r["detail"]
    print(f"archetype: {r['archetype']} ({r['archetype_reason']})")
    print(f"Score: {r['score']}/8 [{r['archetype']}] "
          f"(lines={d['lines']} images={d['images']} "
          f"code={d['code_blocks']} tables={d['tables']} bullets={d['bullets']} "
          f"links={d['links']} badges={d['badges']})")
    print(f"Strengths ({len(r['strengths'])}): {r['strengths']}")
    print(f"Issues ({len(r['issues'])}): {r['issues']}")
    if r["not_applicable"]:
        print(f"Not applicable ({len(r['not_applicable'])}): {r['not_applicable']} "
              "— threshold 0, carried no signal")
    return 0 if not r["issues"] else 1


if __name__ == "__main__":
    sys.exit(main())
