#!/usr/bin/env python3
"""Build the research eval fixtures: one fresh repo per (eval, config).
Usage: python3 make_fixtures.py <out_root> <config>...   e.g. /var/tmp/genome-eval new old"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

FILLER = ("The funnel prices each cell on the deploy-exact money path; stage A screens coarse ranges, stage B "
          "refines to 0.01, stage C searches the book jointly. Every number is judged against the drift baseline "
          "and deflated over the full trial ledger before it may be quoted as an expectation.\n")


def git(d, *a):
    subprocess.run(["git", *a], cwd=d, capture_output=True, check=True)


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip("\n") if not text.startswith("RAW") else text[3:])


def commit(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "e@e"); git(root, "config", "user.name", "e")
    git(root, "add", "-A"); git(root, "commit", "-qm", "fixture")


KB_TOML = '''[paths]
agents = "AGENTS.md"
state = "docs/PROGRESS.md"
register = "native:the plan's gap register"
worklog = "core/worklog"
ledger = "docs/CLOSED.md"
closed = "docs/CLOSED.md"
plans = "docs/plans"
audits = "docs/audits"
decisions = "core/decisions"
regressions = "core/regressions"
archive = "archive"
feed = "native:none"
workflows = "native:none"
runbook = "native:AGENTS.md"
entry = "AGENTS.md"
dated_pattern = "^\\\\d{4}-"
'''
GENOME_TOML = '''[genome]
modules = ["core", "records", "research", "ops"]
[paths]
agents = "AGENTS.md"
state = "docs/PROGRESS.md"
entry = "AGENTS.md"
register = "native:the plan's gap register"
worklog = "core/worklog"
ledger = "docs/CLOSED.md"
asks = "docs/ASKS.md"
plans = "docs/plans"
audits = "docs/audits"
runbook = "native:AGENTS.md"
archive = "archive"
decisions = "core/decisions"
regressions = "core/regressions"
records_index = "docs/RECORDS.md"
evidence = "evidence"
hypotheses = "docs/HYPOTHESES.md"
quarantine = "docs/QUARANTINE.md"
prereg = "docs/PREREG.md"
ownership_map = "docs/INDEX.md"
[core]
worklog_form = "numbered"
archive_form = "generations"
living_plans = ["docs/plans/2026-10-12-foundation-plan.md"]
resume = "docs/plans/2026-10-12-foundation-plan.md#Resume here"
budgets = { "docs/PROGRESS.md" = 16000 }
[records]
prefix = "QX"
mode = "amendable"
[research]
surfaces = ["docs/PROGRESS.md", "AGENTS.md"]
[ops]
owner_globs = ["docs/notes/*.md"]
link_surfaces = ["AGENTS.md", "docs/PROGRESS.md", "docs/INDEX.md"]
'''


def research_repo(root: Path, cli_src: Path | None) -> None:
    """A mid-size quant R&D repo: big contract, living plan with a resume block, numbered worklogs, records."""
    write(root, "kb.toml", KB_TOML)
    write(root, "genome.toml", GENOME_TOML)
    if cli_src:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / cli_src.name).write_bytes(cli_src.read_bytes())
        (root / "scripts" / cli_src.name).chmod(0o755)
    write(root, "AGENTS.md", "# AGENTS.md — quantx front door\n\nRead `docs/PROGRESS.md`, then the plan "
          "`docs/plans/2026-10-12-foundation-plan.md`, then `docs/INDEX.md`.\n\n## Where truth lives\n\n"
          "| question | answer lives in |\n|---|---|\n| current state | `docs/PROGRESS.md` |\n"
          "| what happens next | `docs/plans/2026-10-12-foundation-plan.md` |\n| which doc owns what | `docs/INDEX.md` |\n"
          "| what was rejected | `docs/CLOSED.md` |\n| operator questions | `docs/ASKS.md` |\n\n## Environment\n\n"
          + FILLER * 120)
    write(root, "docs/PROGRESS.md", """
        # PROGRESS — state page

        ## STATE — 2026-10-17 — the trade engine

        Member 1 frozen: TE3 longs H1 k3 X1.4 q95, about +1.5 %/mo mean over refits `[OUT-OF-SAMPLE]`.
        compression_h1 cell: +6.9%/mo LB on 2023–26 (book candidate).
        Next: the plan's Resume-here block.

        ## History pointer

        Older state blocks: `core/worklog/`.
        """)
    plan = ["# Foundation plan (living)\n", "## Operator rulings\n", FILLER * 40]
    for i in range(1, 9):
        plan += [f"## Next phase {i} (outline 2026-10-{i:02d}, superseded by phase {i + 1})\n", FILLER * 25]
    plan += ["## Trajectory v2 (2026-10-17h)\n", "| Phase | What | Exit test |\n|---|---|---|\n",
             "| V1 | conditional runner on the H1 member | lift keeps its sign in ≥ 5 / 6 refits and pooled ΔR LB > 0 |\n",
             "| V2 | Stage-1 fade engine | paired ΔG_LB_loo > 0 |\n\n",
             "**Resume here (2026-10-17h):**\n",
             "- Order: maintenance first, then **V1 — the H1 conditional runner**: extend "
             "`scripts/excursion_store.py` `managed_path` with a conditional target (at the touch, switch to a "
             "trail if bars since entry ≤ cut); parity test cut=0 reproduces the bracket.\n",
             "- Accept V1 if the lift keeps its sign in ≥ 5 / 6 refits and pooled ΔR LB > 0.\n",
             "- Nothing running.\n\n", "## Gap register\n", FILLER * 30]
    write(root, "docs/plans/2026-10-12-foundation-plan.md", "RAW" + "\n".join(plan))
    write(root, "docs/ASKS.md", """
        # Operator questions and rulings

        | id | asked | status | question | ruling | applied |
        |---|---|---|---|---|---|
        | Q1 | 2026-10-16 | open | Start a shadow forward log on the frozen member now, or at V5? | — | — |
        | Q2 | 2026-10-17 | ruled | Release the 61-symbol holdout? | Released: breadth beats the holdout | `docs/plans/2026-10-12-foundation-plan.md` |
        """)
    write(root, "docs/INDEX.md", """
        # Ownership map

        | File | Status | Owns |
        |---|---|---|
        | `docs/notes/funnel.md` | LIVE | how the funnel prices cells |
        | `docs/plans/2026-10-12-foundation-plan.md` | PLAN-ACTIVE | what is built next |
        """)
    write(root, "docs/notes/funnel.md", "# Funnel notes\n\n" + FILLER * 20 +
          "\nThe compression_h1 survivor read +6.9%/mo LB in the 2023–26 window.\n")
    write(root, "docs/CLOSED.md", "# CLOSED — tried and rejected\n\nAppend-only.\n")
    write(root, "docs/HYPOTHESES.md", "# Hypotheses\n\n| id | status | hypothesis | verdict | reopen-if |\n|---|---|---|---|---|\n"
          "| H1 | open | the compression_h1 cell is a book member | — | — |\n")
    write(root, "docs/QUARANTINE.md", "# Quarantine\n\n| figures | where they appeared | why invalid | invalidating record | date |\n|---|---|---|---|---|\n")
    write(root, "docs/PREREG.md", "# Pre-registrations\n\n| date | spec | sha256 | head | note |\n|---|---|---|---|---|\n")
    write(root, "docs/RECORDS.md", "# Records\n")
    write(root, "evidence/dsr_audit.json", '{"cell": "compression_h1", "universe_dsr": 0.03, "trials": 21578, '
          '"verdict": "selection-biased: not distinguishable from the best of 21578 noise trials"}\n')
    for n, (kind, slug, title, body) in enumerate([
            ("RG", "010", "Deflate selections over the full trial ledger", "DSR/PBO over every trial, not the survivors."),
            ("RG", "014", "Seeds are model variance, not market paths", "Bootstrap market paths; seeds do not count as paths."),
            ("RG", "022", "Support must be sufficient before a number is quoted", "At least 100 trades and many months."),
            ("AD", "021", "R&D constitution", "Objective, cell, folds, funnel, evidence battery.")]):
        write(root, f"core/{'regressions' if kind == 'RG' else 'decisions'}/QX-{kind}-{slug}-{slug}-rule.md",
              f'---\nID: "QX-{kind}-{slug}"\nTitle: "{title}"\nStatus: "Active"\nDate: "2026-09-0{n + 1}"\n'
              f'Description: "{body}"\n---\n\n# QX-{kind}-{slug}: {title}\n\n## Law\n\n{body}\n\n'
              f'## Revisions\n\n- 2026-09-0{n + 1}: created\n')
    write(root, "scripts/excursion_store.py", "# Evidence integrity: see QX-RG-014 (seeds are not paths).\n"
          "def managed_path(trade, cut=0):\n    return trade\n")
    for i, t in enumerate(["noise floor and paired overlays", "C0 remedy fails; checkpoint C1",
                           "runtime autopsy, holdout release, trajectory v2"], 393):
        write(root, f"core/worklog/0{i}-2026-10-17-{t.split()[0]}.md", f"# 0{i} — 2026-10-17 — {t}\n\n" + FILLER * 10)
    write(root, "archive/2026-10-15-housekeeping/README.md", "# Archive generation\n\n| file | superseded by | reason | date |\n|---|---|---|---|\n")
    write(root, "pyproject.toml", '[project]\nname = "quantx"\nversion = "0.1"\n')


def coldstart_repo(root: Path) -> None:
    write(root, "pyproject.toml", '[project]\nname = "forecastlab"\nversion = "0.1"\n')
    write(root, "experiments/run_sweep.py", "# sweeps model configs; writes results/<run>.json\nprint('sweep')\n")
    write(root, "README.md", "# forecastlab\n\nDemand forecasting research.\n")


def custom_kb_repo(root: Path) -> None:
    write(root, "README.md", "# mindmap\n\nPersonal notes.\n")


def pipeline_repo(root: Path) -> None:
    write(root, "README.md", "# lanes\n\nJob, freelance and architecture work.\n")


def mind_repo(root: Path) -> None:
    write(root, "README.md", "# inner-map\n\nPrivate notes.\n")


def intersubjective_repo(root: Path, cli: Path) -> None:
    """A private mind map already in place: three entries from earlier sessions and the blueprint applied."""
    write(root, "README.md", "# inner-map\n\nPrivate notes.\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for args in (["init", "--blueprint", "mind-topology"],
                 ["new", "engram", "--title", "pride at work", "--set", "statement=I feel proud when my work is noticed", "--set", "modality=belief"],
                 ["new", "process", "--title", "overwork", "--set", "type=coping"]):
        subprocess.run([sys.executable, str(cli), *args], cwd=root, capture_output=True, check=True, env={**os.environ, "GENOME_AGENT_ID": "fixture"})
    cp = root / "scripts" / "genome"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_bytes(cli.read_bytes()); cp.chmod(0o755)


PAPERS = {
    "fish-oil-viscosity.md": ("# Dietary fish oil and whole-blood viscosity: a randomised trial (synthetic exercise paper)\n\n"
        "Design: randomised, double-blind, placebo-controlled trial. Participants: 30 healthy adults.\n\n"
        "## Results\n\nAfter 12 weeks of fish oil (3 g eicosapentaenoic acid plus docosahexaenoic acid daily), whole-blood viscosity "
        "fell by 11% (95% CI 6 to 16) compared with placebo. Red-cell deformability increased.\n\n"
        "## Table 2\n\nWhole-blood viscosity at 12 weeks: fish oil 3.9 mPa.s, placebo 4.4 mPa.s.\n"),
    "raynaud-viscosity.md": ("# Blood viscosity in primary Raynaud's syndrome: a case-control study (synthetic exercise paper)\n\n"
        "Design: case-control study. Participants: 48 patients with primary Raynaud's syndrome and 48 matched controls.\n\n"
        "## Results\n\nPatients had higher whole-blood viscosity than controls (mean difference 0.4 mPa.s, p < 0.01). "
        "Viscosity correlated with the number of attacks per week (r = 0.52).\n\n"
        "## Discussion\n\nElevated blood viscosity may contribute to reduced digital blood flow during cold exposure.\n"),
    "triglycerides-retracted.md": ("# RETRACTED (2025, data fabrication): Fish oil and serum triglycerides (synthetic exercise paper)\n\n"
        "Retraction notice: the journal retracted this article in 2025 after finding fabricated data. The findings below must not be relied on.\n\n"
        "## Results\n\nFish oil reduced serum triglycerides by 80% and increased platelet aggregation in 20 volunteers.\n"),
}


def ontology_axiom_repo(root: Path, cli: Path) -> None:
    """An ontology genome with one axiom already adopted by a human."""
    write(root, "README.md", "# ontology\n\nHow reality is structured.\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for args in (["init", "--blueprint", "ontology"], ["new", "axiom", "--title", "Unity", "--set", "statement=Reality is one undivided whole"],
                 ["move", "AX-001", "adopted", "--human", "operator"]):
        subprocess.run([sys.executable, str(cli), *args], cwd=root, capture_output=True, check=True, env={**os.environ, "GENOME_AGENT_ID": "fixture"})


def literature_repo(root: Path) -> None:
    write(root, "README.md", "# circulation-review\n\nLiterature base.\n")
    for name, text in PAPERS.items():
        write(root, f"papers/{name}", text)


def federation_repos(root: Path) -> None:
    """meta/ over alpha and bravo; alpha has a manual describing src/. Cards cache: <root>/../.cards"""
    for name in ("alpha", "bravo"):
        d = root / "meta" / name
        write(d, "README.md", f"# {name}\n\n{'Coolant pump controller for the alpha line.' if name == 'alpha' else 'Pastry order tracker.'}\n")
        write(d, "src/main.py", "print('run')\n")
        write(d, "docs/ARCHITECTURE.md", f"# Architecture\n\n## Overview\n\nSee src/main.py in {name}.\n")
    write(root / "meta", "README.md", "# meta\n")


def legacy_vendored_repo(root: Path, old_cli: Path) -> None:
    """A repo whose genome is vendored at the previous release and lints clean."""
    write(root, "README.md", "# svc\n\nA service.\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    cli = root / "scripts" / "genome"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(old_cli.read_bytes()); cli.chmod(0o755)
    subprocess.run([sys.executable, str(cli), "init", "--profile", "software"], cwd=root, capture_output=True, check=True)


def main():
    out, cfgs = Path(sys.argv[1]), sys.argv[2:]
    skill = Path(__file__).resolve().parents[1]
    snapshot = skill.parent / "project-genome-workspace" / "skill-snapshot"
    for cfg in cfgs:
        cli = skill / "scripts" / "genome" if cfg == "new" else snapshot / "scripts" / "kb"
        for name, build in [("e5-research-coldstart", lambda r: coldstart_repo(r)),
                            ("e6-resume-cheap", lambda r: research_repo(r, cli)),
                            ("e7-invalidated-figure", lambda r: research_repo(r, cli)),
                            ("e8-consolidate-records", lambda r: research_repo(r, cli)),
                            ("e9-custom-kb", lambda r: custom_kb_repo(r)),
                            ("e10-federation", lambda r: federation_repos(r)),
                            ("e12-mind", lambda r: mind_repo(r)),
                            ("e13-intersubjective", lambda r: intersubjective_repo(r, skill / "scripts" / "genome")),
                            ("e14-literature", lambda r: literature_repo(r)),
                            ("e15-ontology", lambda r: mind_repo(r)),
                            ("e16-custom-sre", lambda r: custom_kb_repo(r)),
                            ("e17-triangle", lambda r: mind_repo(r)),
                            ("e18-retraction", lambda r: mind_repo(r)),
                            ("e19-ontology-axiom", lambda r: ontology_axiom_repo(r, skill / "scripts" / "genome")),
                            ("e11-upgrade", lambda r: legacy_vendored_repo(r, skill / "evals" / "fixtures" / "genome-2026.10.17-4")),
                            ("e20-venture-pipeline", lambda r: pipeline_repo(r))]:
            root = out / f"{name}-{cfg}"
            if root.exists():
                subprocess.run(["rm", "-rf", str(root)], check=True)
            root.mkdir(parents=True)
            build(root)
            commit(root)
            print(root)


if __name__ == "__main__":
    main()
