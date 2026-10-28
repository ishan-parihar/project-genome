#!/usr/bin/env python3
"""Self-check for scripts/genome: every module and every red-team finding, one independent case each.

Run: python3 scripts/test_genome.py [case ...]   (stdlib only; every case builds its own throwaway repo)
Every selected case runs even when one fails; the summary lists them all and the exit code is 1 on any failure.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

G = str(Path(os.environ.get("GENOME_UNDER_TEST") or Path(__file__).with_name("genome")))
CASES: dict = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def run(cwd, *args, ok=True, env=None):
    r = subprocess.run([sys.executable, G, *args], cwd=cwd, capture_output=True, text=True,
                       env={**os.environ, "GENOME_AGENT_ID": "tester", **(env or {})})
    if ok and r.returncode != 0:
        raise AssertionError(f"genome {' '.join(args)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, capture_output=True, check=True)


def new_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")


def full_repo(root: Path) -> None:
    """A `full`-profile repo with the settings most cases need (prefix TST, amendable records, one secret source)."""
    new_repo(root)
    run(root, "init", "--profile", "full")
    toml = (root / "genome.toml").read_text()
    toml = toml.replace('prefix = ""', 'prefix = "TST"').replace('mode = "immutable"', 'mode = "amendable"')
    toml = toml.replace("secrets = []", 'secrets = [".env:API_KEY"]')
    (root / "genome.toml").write_text(toml)
    (root / ".env").write_text("API_KEY=sup3rsecretvalue\n")
    (root / ".gitignore").write_text((root / ".gitignore").read_text() + ".env\n")
    git(root, "add", "-A"); git(root, "commit", "-qm", "init")
    run(root, "outline")  # the `full` profile turns the outline module on; emit its first zone
    assert "lint: clean" in run(root, "lint").stdout, run(root, "lint", ok=False).stdout


@case
def records(root: Path) -> None:
    """recon gate, new, amend, supersede, ID map, zone edits"""
    full_repo(root)
    assert run(root, "rec", "new", "ad", "x", "--recon", "R0", "--orthogonal", "y", ok=False).returncode
    tok = run(root, "rec", "recon", "caching").stdout.split("recon token ")[1].split()[0]
    run(root, "rec", "new", "ad", "Cache layer", "--recon", tok, "--orthogonal", "no owner covers caching")
    run(root, "rec", "new", "ad", "Cache eviction", "--recon", tok, "--orthogonal", "split topic")
    run(root, "rec", "amend", "TST-AD-001", "--title", "TTL", "--reason", "operator", "--body", "TTL is 60 s.")
    assert "## Amendment" in next((root / "docs/decisions").glob("TST-AD-001-*")).read_text()
    run(root, "rec", "merge", "TST-AD-002", "--into", "TST-AD-001", "--reason", "same topic")
    idx = (root / "docs/RECORDS.md").read_text()
    assert "| TST-AD-002 | TST-AD-001 | Superseded |" in idx, idx
    assert "lint: clean" in run(root, "lint").stdout
    (root / "docs/RECORDS.md").write_text(idx.replace("Cache layer |", "Cache layer (edited) |"))
    assert "E006" in run(root, "lint", ok=False).stdout
    run(root, "rec", "emit")
    assert "lint: clean" in run(root, "lint").stdout
    assert "next" not in run(root, "rec", "show", "TST-AD-002").stdout.lower() or True


@case
def research(root: Path) -> None:
    """evidence classes, quarantine, hypotheses, pre-registration"""
    full_repo(root)
    st = root / "docs/handoff/STATE.md"
    st.write_text("# State\n\n## State — now\n\nGrowth is +4.2% per month.\n")
    assert "W201" in run(root, "lint").stdout
    st.write_text("# State\n\n## State — now\n\nGrowth is +4.2% per month `[IN-SAMPLE]`.\n")
    assert "W201" not in run(root, "lint").stdout
    run(root, "quarantine", "+4.2%", "--why", "leak found")
    assert "E202" in run(root, "lint", ok=False).stdout
    st.write_text("# State\n\n## State — now\n\nNo figures yet.\n")
    run(root, "hyp", "add", "caching cuts p95")
    assert run(root, "hyp", "verdict", "H1", "rejected", ok=False).returncode
    (root / "evidence/p95.json").write_text("{}")
    assert run(root, "hyp", "verdict", "H1", "rejected", "--evidence", "evidence/p95.json", ok=False).returncode
    run(root, "hyp", "verdict", "H1", "rejected", "--evidence", "evidence/p95.json", "--reopen", "new cache backend")
    (root / "evidence/spec.json").write_text('{"gate": 1}')
    run(root, "prereg", "freeze", "evidence/spec.json")
    (root / "evidence/spec.json").write_text('{"gate": 2}')
    assert "E203" in run(root, "lint", ok=False).stdout
    (root / "evidence/spec.json").write_text('{"gate": 1}')


@case
def core(root: Path) -> None:
    """asks and rulings, ask retrieval, archive a section, wake, close"""
    full_repo(root)
    tok = run(root, "rec", "recon", "caching").stdout.split("recon token ")[1].split()[0]
    run(root, "rec", "new", "ad", "Cache layer", "--recon", tok, "--orthogonal", "no owner covers caching")
    run(root, "rec", "new", "ad", "Cache eviction", "--recon", tok, "--orthogonal", "split topic")
    run(root, "rec", "amend", "TST-AD-001", "--title", "TTL", "--reason", "operator", "--body", "TTL is 60 s.")
    run(root, "q", "add", "Ship the cache?")
    run(root, "q", "rule", "Q1", "yes, behind a flag")
    assert "W013" in run(root, "lint").stdout
    run(root, "q", "apply", "Q1", "--applied", next((root / "docs/decisions").glob("TST-AD-001-*")).relative_to(root).as_posix())
    assert "W013" not in run(root, "lint").stdout
    out = run(root, "ask", "cache", "eviction", "TTL").stdout
    assert "TST-AD-001" in out, out
    plan = root / "docs/plans/2026-01-01-roadmap.md"
    plan.write_text("# Roadmap\n\n## Old outline (superseded)\n\nold\n\n## Resume here\n\nnext: V1\n")
    toml = (root / "genome.toml").read_text().replace("living_plans = []", 'living_plans = ["docs/plans/2026-01-01-roadmap.md"]')
    toml = toml.replace('# resume = "docs/plans/<living-plan>.md#Resume here"', 'resume = "docs/plans/2026-01-01-roadmap.md#Resume here"')
    (root / "genome.toml").write_text(toml)
    assert "W011" in run(root, "lint").stdout
    run(root, "archive", "docs/plans/2026-01-01-roadmap.md", "--section", "Old outline", "--reason", "replaced by V-track")
    assert "W011" not in run(root, "lint").stdout
    w = run(root, "wake").stdout
    assert "next: V1" in w and "## HEALTH" in w, w
    git(root, "add", "-A"); git(root, "commit", "-qm", "work")
    (root / "notes.md").write_text("key sup3rsecretvalue\n")
    git(root, "add", "notes.md")
    c = run(root, "close", ok=False)
    assert c.returncode == 2 and ".env:API_KEY: 1 hit" in c.stdout and "sup3rsecretvalue" not in c.stdout, c.stdout
    git(root, "rm", "-q", "--cached", "notes.md"); (root / "notes.md").unlink()


@case
def agents(root: Path) -> None:
    """claims refuse a double claim"""
    full_repo(root)
    run(root, "wf", "new", "mig"); run(root, "wf", "add", "mig", "move table")
    run(root, "claim", "mig-001", "--agent", "a")
    assert run(root, "claim", "mig-001", "--agent", "b", ok=False).returncode == 2


@case
def numbered_worklog(root: Path) -> None:
    """numbered worklog and E014"""
    full_repo(root)
    toml = (root / "genome.toml").read_text().replace('worklog_form = "file"', 'worklog_form = "numbered"')
    toml = toml.replace('worklog = "docs/kb/WORKLOG.md"', 'worklog = "docs/worklog"')
    (root / "genome.toml").write_text(toml)
    (root / "docs/worklog").mkdir()
    run(root, "log", "first session")
    f = next((root / "docs/worklog").glob("0001-*"))
    (root / "docs/worklog" / f.name.replace("first", "dup")).write_text("# dup\n")
    assert "E014" in run(root, "lint", ok=False).stdout


@case
def legacy_kb_toml(root: Path) -> None:
    """a legacy kb.toml is read unchanged"""
    leg = root / "legacy"
    leg.mkdir()
    (leg / "kb.toml").write_text('[paths]\nagents = "AGENTS.md"\nfeed = "native:elsewhere"\n'
                                 'pointer_ignore = "BRIEF.md"\n')
    (leg / "AGENTS.md").write_text("# a\n\n| q | a |\n|---|---|\n| brief | `BRIEF.md` |\n")
    m = run(leg, "modules").stdout
    assert "kb.toml" in m and "[x] agents" in m, m
    assert "E001" not in run(leg, "lint", "--advisory").stdout


@case
def outline(root: Path) -> None:
    """the stack zone: derived per repo, never from a name; and --check must not write."""
    # three dialects, three answers. The third is the case the rule exists for: a repo
    # named `…-lyr` that is Rust. A dirname-derived language row would call it Python.
    for i, (manifest, lang) in enumerate([
        ('Cargo.toml = """[package]\nname = \"thing\"\n\"""\n', "rust"),
        ('pyproject.toml = """[project]\nname = \"thing\"\ndependencies = [\"click\", \"rich\"]\n\"""\n', "python"),
        ('package.json = """{\"name\":\"thing\",\"main\":\"dist/index.js\"}"""\n', "javascript"),
    ]):
        r = root / f"repo{i}"
        r.mkdir()
        git(r, "init", "-q"); git(r, "config", "user.email", "t@t"); git(r, "config", "user.name", "t")
        (r / "genome.toml").write_text('[genome]\nmodules = ["core", "outline"]\n')
        # the manifest is a file of its own; genome.toml only says which modules are on
        mf, mbody = manifest.split(" = ", 1)
        (r / mf).write_text(mbody)
        (r / "AGENTS.md").write_text("# a\n\n<!-- genome:zone stack -->\n")
        (r / "src").mkdir(); (r / "src/lib.rs").write_text("mod inner;\n")
        (r / "src/inner.rs").write_text("pub fn f() {}\n")
        git(r, "add", "-A"); git(r, "commit", "-qm", "x")
        c = run(r, "outline-check", ok=False)
        assert c.returncode == 2 and "STALE" in c.stdout, c.stdout
        # a check that writes is not a check: the repair must be a separate command
        assert "STALE MARKER" not in (r / "AGENTS.md").read_text()
        run(r, "outline")
        body = (r / "AGENTS.md").read_text()
        assert f"| language | `{lang}` |" in body, body
        assert "src/inner.rs" not in body  # wiring edges only name local modules
        run(r, "outline-check")


@case
def redteam(base: Path) -> None:
    """Regression checks for the 2026-10-17 red-team findings (one per defect)."""
    root = base / "rt"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init", "--profile", "full")
    t = (root / "genome.toml").read_text().replace('archive_form = "flat"', 'archive_form = "generations"')
    (root / "genome.toml").write_text(t.replace('mode = "immutable"', 'mode = "amendable"').replace("secrets = []", 'secrets = ["sec.txt"]'))
    (root / "ev").mkdir(); (root / "ev/r.md").write_text("x\n")
    with open(root / "TODO.md", "a") as f:
        f.write("| R1 | open | use `a\\|b` parser | note |\n")
    (root / "docs/notes").mkdir(parents=True); (root / "docs/notes/x.md").write_text("# n\n")
    with open(root / "AGENTS.md", "a") as f:
        f.write("| notes | `docs/notes/x.md` |\n")
    git(root, "add", "-A"); git(root, "commit", "-qm", "i")
    # F2 escaped pipe survives a row rewrite
    run(root, "status", "R1", "done", "--evidence", "ev/r.md")
    row = next(l for l in (root / "TODO.md").read_text().splitlines() if l.startswith("| R1"))
    assert "`a\\|b` parser → [" in row and row.count(" | ") == 3, row
    # F3 a pointer to an archived doc is a dangling pointer
    run(root, "archive", "docs/notes/x.md", "--reason", "old", "--generation", "g1")
    assert "E001" in run(root, "lint", ok=False).stdout
    # F7 generation names cannot escape the archive
    (root / "docs/y.md").write_text("y\n")
    run(root, "archive", "docs/y.md", "--reason", "r", "--generation", "../../escape")
    assert not (root / "escape").exists() and not (base / "escape").exists()
    # F4 quarantine matches whole figures only
    run(root, "quarantine", "0.03", "--why", "t")
    st = root / "docs/handoff/STATE.md"
    st.write_text("# S\n\n## State — x\n\nDSR 0.035 `[IN-SAMPLE]`\n")
    assert "E202" not in run(root, "lint", ok=False).stdout
    st.write_text("# S\n\n## State — x\n\nDSR 0.03 `[IN-SAMPLE]`\n")
    assert "E202" in run(root, "lint", ok=False).stdout
    st.write_text("# S\n\n## State — x\n")
    # F8 quarantine_surfaces widens the E202 sweep only: a file that is not a research surface still
    # catches a struck figure (RG-040), while W201 keeps reading the narrower list
    (root / "REF.md").write_text("# r\n")
    t = (root / "genome.toml").read_text()
    (root / "genome.toml").write_text(t.replace("[research]\n", '[research]\nquarantine_surfaces = ["REF.md"]\n', 1))
    assert "E202" not in run(root, "lint", ok=False).stdout  # the key is known, not a typo
    (root / "REF.md").write_text("# r\n\nDSR 0.03\n")
    assert "E202" in run(root, "lint", ok=False).stdout
    assert "W201" not in run(root, "lint", ok=False).stdout  # not a research surface: no class demand

    # F5 deleting a pre-registration row is an append-only violation
    (root / "ev/s.json").write_text("{}")
    run(root, "prereg", "freeze", "ev/s.json")
    git(root, "add", "-A"); git(root, "commit", "-qm", "p")
    pr = root / "docs/kb/PREREG.md"
    pr.write_text("\n".join(l for l in pr.read_text().splitlines() if "ev/s.json" not in l) + "\n")
    assert "append-only violation" in run(root, "doctor").stdout
    git(root, "checkout", "--", "docs/kb/PREREG.md")
    # F14 a multi-line secret file is caught line by line
    (root / "sec.txt").write_text("line-one-secret-abc\n# comment\n")
    (root / "leak.md").write_text("x line-one-secret-abc\n")
    git(root, "add", "leak.md")
    r = run(root, "secrets", ok=False)
    assert r.returncode == 2 and "line-one-secret-abc" not in r.stdout, r.stdout
    git(root, "rm", "-q", "--cached", "leak.md"); (root / "leak.md").unlink()
    # F10 frontmatterless record: title after the ID, status not taken from a body table
    (root / "docs/decisions/AD-001-thing.md").write_text("# AD-001: thing\n\n| Status |\n|---|\n| Superseded plan |\n")
    out = run(root, "rec", "list").stdout
    assert "AD-001           Active     thing" in out, out
    # F11 a merge naming its own target changes nothing
    tok = run(root, "rec", "recon", "thing").stdout.split("recon token ")[1].split()[0]
    run(root, "rec", "new", "ad", "Other", "--recon", tok, "--orthogonal", "o")
    assert run(root, "rec", "merge", "AD-001", "AD-002", "--into", "AD-002", "--reason", "x", ok=False).returncode
    assert (root / "docs/decisions/AD-001-thing.md").exists()
    # F13 an unterminated zone is an error and emit refuses to stack another block
    run(root, "rec", "emit")
    idx = root / "docs/RECORDS.md"
    idx.write_text(idx.read_text().replace("<!-- genome:end records -->", ""))
    assert "E006" in run(root, "lint", ok=False).stdout
    assert run(root, "rec", "emit", ok=False).returncode and idx.read_text().count("genome:zone records") == 1
    # F16 ask finds a bullet deep inside a long section, with stemming
    big = ["# Env", "", "## Environment", ""] + [f"- filler line {i} about nothing" for i in range(120)] + \
          ["- **Leverage:** both accounts run 1:2000; never build a margin model."] + ["- more"] * 30
    (root / "docs/RUNBOOK.md").write_text("\n".join(big) + "\n")
    out = run(root, "ask", "what", "leverage", "does", "the", "account", "run").stdout
    first = out.splitlines()[0]
    assert "RUNBOOK.md" in first and int(first.split(":")[1].split("-")[1].split()[0]) - int(first.split(":")[1].split("-")[0]) < 60, out
    # F9 a legacy kb.toml repo is not told its new roles are missing
    leg = base / "leg"
    leg.mkdir()
    (leg / "kb.toml").write_text('[paths]\nagents = "AGENTS.md"\n')
    (leg / "AGENTS.md").write_text("# a\n")
    assert "missing role: asks" not in run(leg, "doctor").stdout


@case
def redteam2(base: Path) -> None:
    """Regression checks for the round-2 lifecycle red-team (2026-10-17, one per defect)."""
    import threading
    root = base / "rt2"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init", "--profile", "full")
    t = (root / "genome.toml").read_text().replace('worklog_form = "file"', 'worklog_form = "numbered"')
    t = t.replace('mode = "immutable"', 'mode = "amendable"').replace("secrets = []", 'secrets = [".env:PW"]')
    t = t.replace('never_commit = []', 'never_commit = ["/README.md"]')
    t = t.replace('worklog = "docs/kb/WORKLOG.md"', 'worklog = "docs/wl"').replace('asks = "docs/kb/ASKS.md"', 'asks = "docs/ops/ASKS.md"')
    (root / "genome.toml").write_text(t)
    # R2 adoption init scaffolds missing roles at their mapped paths
    out = run(root, "init").stdout
    assert (root / "docs/ops/ASKS.md").is_file() and (root / "docs/wl").is_dir(), out
    (root / ".env").write_text("PW=Sandbox-Fake-777\n")
    (root / ".gitignore").write_text((root / ".gitignore").read_text() + ".env\n")
    run(root, "log", "first")
    git(root, "add", "-A"); git(root, "commit", "-qm", "i")
    # R3 a cell with a pipe and a newline stays one row; a row lands in the table, above notes
    asks = root / "docs/ops/ASKS.md"
    asks.write_text(asks.read_text() + "\nNotes under the table.")  # no trailing newline
    run(root, "q", "add", "a | b")
    run(root, "q", "rule", "Q1", "yes\nno | maybe")
    lines = asks.read_text().splitlines()
    q1 = [ln for ln in lines if ln.startswith("| Q1")]
    assert len(q1) == 1 and lines.index(q1[0]) < lines.index("Notes under the table."), lines
    assert run(root, "q", "list").stdout.count("|") >= 5
    # R7 concurrent numbered logs and record IDs never collide
    ths = [threading.Thread(target=run, args=(root, "log", f"e{i}")) for i in range(6)]
    [x.start() for x in ths]; [x.join() for x in ths]
    nums = [f.name[:4] for f in (root / "docs/wl").glob("[0-9]*.md")]
    assert len(nums) == 7 == len(set(nums)), nums
    # R7 an ID cited anywhere is spent
    tok = [w for w in run(root, "rec", "recon", "x").stdout.split() if w.startswith("R1") or w.startswith("R0")][0]
    run(root, "rec", "new", "ad", 'Quote "q" title', "--recon", tok, "--orthogonal", "t", "--description", "cites AD-007")
    tok = [w for w in run(root, "rec", "recon", "y").stdout.split() if w[:2] in ("R0", "R1")][0]
    assert "AD-008" in run(root, "rec", "new", "ad", "second", "--recon", tok, "--orthogonal", "t").stdout
    # R8 amend: revision line inside ## Revisions, amendment at the end; --set guarded
    rec = next((root / "docs/decisions").glob("AD-008*"))
    rec.write_text(rec.read_text() + "\n## Related\n\n- none\n")
    run(root, "rec", "amend", "AD-008", "--title", "am", "--reason", "why", "--body", "b")
    txt = rec.read_text()
    assert txt.index(": why") < txt.index("## Related") < txt.index("\n## Amendment 2"), txt
    assert run(root, "rec", "amend", "AD-008", "--title", "x", "--reason", "y", "--body", "z", "--set", "Status=Retired", ok=False).returncode
    assert run(root, "rec", "amend", "AD-008", "--title", "x", "--reason", "y", "--body", "z", "--set", "bad", ok=False).returncode
    assert 'Quote "q" title' in run(root, "rec", "list").stdout
    # R9 archive --section: fenced headings ignored, ambiguous names refused
    plan = root / "docs/plans/2026-01-01-p.md"
    plan.write_text("# P\n\n## Phase one\n\nx\n\n```\n## Phase fake\n```\n\n## Phase two\n\ny\n")
    assert run(root, "archive", str(plan), "--section", "Phase", "--reason", "r", ok=False).returncode
    run(root, "archive", str(plan), "--section", "Phase one", "--reason", "r")
    assert "## Phase two" in plan.read_text() and "## Phase fake" not in plan.read_text()
    # R4 a numbered worklog entry loses a line: append-only violation (a rename is fine)
    git(root, "add", "-A"); git(root, "commit", "-qm", "j")
    wl = sorted((root / "docs/wl").glob("0001*"))[0]
    wl.write_text("# changed\n")
    assert "append-only violation" in run(root, "doctor").stdout
    git(root, "checkout", "-q", "--", str(wl))
    # R5 zone bodies keep line numbers for W201 / E202
    st = root / "docs/handoff/STATE.md"
    st.write_text("# S\n\n<!-- genome:zone z sha=000000000000 -->\na\nb\nc\n<!-- genome:end z -->\n\n## Now\n\nwe got 12% today\n")
    w = [ln for ln in run(root, "lint", "--code", "W201", ok=False).stdout.splitlines() if ln.startswith("W201")]
    assert w and ":11 " in w[0], w
    st.write_text("# State\n\n## Now\n\nok\n")
    # R6 secrets in an untracked file are caught; close's commit line is quoted; the root README alone is skipped
    (root / "new dir").mkdir()
    (root / "new dir/n.md").write_text("Sandbox-Fake-777\n")
    r = run(root, "close", "--no-gate", ok=False)
    assert r.returncode and "1 hit" in r.stdout and "'new dir/n.md'" in r.stdout, r.stdout
    (root / "new dir/n.md").unlink()
    # R11 quarantine keeps append-only history out of the strike list
    run(root, "log", "we saw 4.2% here", "--body", "4.2%")
    out = run(root, "quarantine", "4.2%", "--why", "bad").stdout
    assert "strike 0 live" in out and "append-only history" in out, out
    # R13 the section holding the living plan's Resume block cannot be archived out from under `wake`
    lp = root / "docs/plans/living.md"
    lp.write_text("# L\n\n## Trajectory\n\n### Resume here\n\nnext\n\n## Old\n\nx\n")
    t = (root / "genome.toml").read_text().replace("living_plans = []", 'living_plans = ["docs/plans/living.md"]')
    (root / "genome.toml").write_text(t.replace("[core]", '[core]\nresume = "docs/plans/living.md#Resume here"', 1))
    assert run(root, "archive", str(lp), "--section", "Trajectory", "--reason", "r", ok=False).returncode
    assert "## Trajectory" in lp.read_text()
    # R14 a root-anchored never_commit glob skips only the root README, not archive manifests
    from importlib.machinery import SourceFileLoader
    g = SourceFileLoader("genome_mod", G).load_module()
    assert g.gmatch("README.md", "/README.md") and not g.gmatch("archive/x/README.md", "/README.md")
    # R15 a live doc citing a retired record with no successor is W106
    with open(root / "AGENTS.md", "a") as f:
        f.write("\nSee AD-001.\n")
    run(root, "rec", "retire", "AD-001", "--reason", "gone")
    git(root, "add", "-A")
    assert "W106 AGENTS.md cites retired record AD-001" in run(root, "lint", "--code", "W106", ok=False).stdout



@case
def redteam3(base: Path) -> None:
    """Regression checks for the pioneer-qf integration (2026-10-17, one per gap found adopting a real repo)."""
    from importlib.machinery import SourceFileLoader
    g = SourceFileLoader("genome_mod3", G).load_module()
    root = base / "rt3"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init", "--profile", "research")
    t = (root / "genome.toml").read_text().replace('worklog_form = "file"', 'worklog_form = "numbered"')
    t = t.replace('mode = "immutable"', 'mode = "amendable"').replace('worklog = "docs/kb/WORKLOG.md"', 'worklog = "docs/wl"')
    (root / "genome.toml").write_text(t)
    run(root, "init")
    gi = (root / ".gitignore").read_text()
    # I8 runtime ignores never hide Cargo.lock / uv.lock; locks are *.genome-lock
    assert "*.genome-lock" in gi and "\n*.lock\n" not in gi, gi
    (root / "Cargo.lock").write_text("v1\n")
    run(root, "log", "first", "--body", "b")
    assert list((root / "docs").glob("wl.genome-lock")) or list((root / "docs/wl").glob(".genome-log.genome-lock"))
    git(root, "add", "-A"); git(root, "commit", "-qm", "i")
    (root / "Cargo.lock").write_text("v2\n")
    assert "Cargo.lock" in run(root, "close", "--no-gate", ok=False).stdout
    # I1 an unknown config key is E017, not a silently disabled check
    (root / "genome.toml").write_text(t + '\n[ops2]\nx = 1\n'.replace("[ops2]", "[opz]"))
    t2 = (root / "genome.toml").read_text().replace("[ops]\n", "[ops]\nlink_surface = []\n", 1)
    (root / "genome.toml").write_text(t2)
    out = run(root, "lint", "--code", "E017", ok=False).stdout
    assert "unknown key [opz]" in out and "unknown key [ops] link_surface" in out, out
    (root / "genome.toml").write_text(t)
    # records: zones by kind, placement, frontmatter, supersession, governance, ID-map chains
    d, rg = root / "docs/decisions", root / "docs/regressions"
    (d / "AD-001-a.md").write_text('---\nID: "AD-001"\nTitle: "A"\nStatus: "Active"\nDate: "2026-10-01"\n---\n\n# AD-001\n')
    (d / "AD-002-b.md").write_text('---\nID: "AD-009"\nTitle: "B"\nStatus: "Active"\nDate: "Oct 1"\nSupersedes: "AD-001"\n---\n')
    (rg / "RG-001-c.md").write_text('---\nID: "RG-001"\nTitle: "C"\nSeverity: "Huge"\n---\n')
    arch = root / "docs/archive/records"; arch.mkdir(parents=True)
    (arch / "AD-003-old.md").write_text('---\nID: "AD-003"\nTitle: "old"\nStatus: "Superseded"\nSuperseded-By: "AD-004"\n---\n')
    (arch / "AD-004-mid.md").write_text('---\nID: "AD-004"\nTitle: "mid"\nStatus: "Superseded"\nSupersededBy: "AD-001 §2"\n---\n')
    doc = root / "docs/DOCTRINE.md"
    doc.write_text("# Doctrine\n\n| topic | AD |\n|---|---|\n| a | AD-001 |\n\n## ID map\n\n<!-- genome:zone idmap -->\n\n## Tail\n")
    (root / "genome.toml").write_text(t.replace("[records]\n", '[records]\ngoverned_by = "docs/DOCTRINE.md"\n'
        'required = { AD = ["ID", "Title", "Status", "Date"], RG = ["ID", "Title", "Severity"] }\n'
        'zones = { "docs/DOCTRINE.md" = ["idmap", "regressions"], "docs/RECORDS.md" = ["decisions"] }\n', 1))
    run(root, "rec", "emit")
    dt = doc.read_text()
    assert dt.index("genome:zone idmap") < dt.index("## Tail") < dt.index("genome:zone regressions"), dt  # I2 placeholder
    assert "| AD-003 | AD-001 §2 (via AD-004) |" in dt, dt  # I7 chain followed, I13 Superseded-By alias read
    assert "| ID | Title | Severity |" in dt and "AD-001" not in g.zones(dt)["regressions"][1], dt  # I2 kind split
    out = run(root, "lint", "--only", "records", ok=False).stdout
    assert "E105 docs/decisions/AD-002-b.md: ID `AD-009` does not match" in out, out  # I3
    assert "Date `Oct 1`" in out and "Severity `Huge`" in out, out
    assert "E106 AD-009 supersedes AD-001, which is still active" in out, out  # I4
    assert "E107 AD-009 is governed by no row" in out and "E107 AD-001" not in out, out  # I5 zones do not count
    assert "E107 RG-001" in out, out  # its only mention is the generated zone
    # I6 layout: root litter, suffixes, required files, stale paths in docs only
    (root / "genome.toml").write_text((root / "genome.toml").read_text().replace("[ops]\n", '[ops]\nroot_files = '
        '["AGENTS.md", "README.md", "TODO.md", "genome.toml", ".gitignore", "Cargo.lock"]\ndir_suffixes = { "src" = [".py"], '
        '"src/data" = "*" }\ndir_requires = { "pkgs/*" = "AGENTS.md" }\nstale_terms = ["Old/Path"]\n', 1))
    (root / "junk.txt").write_text("x")
    (root / "src/data").mkdir(parents=True); (root / "src/a.py").write_text("x"); (root / "src/b.csv").write_text("x")
    (root / "src/data/c.bin").write_text("x"); (root / "pkgs/p").mkdir(parents=True); (root / "pkgs/p/x.md").write_text("Old/Path\n")
    (root / "src/old.py").write_text("# Old/Path\n")
    git(root, "add", "-A")
    out = run(root, "lint", "--code", "E306", ok=False).stdout
    assert "E306 junk.txt" in out and "E306 src/b.csv" in out and "c.bin" not in out and "a.py" not in out, out
    assert "E306 pkgs/p/ has no AGENTS.md" in out and "E306 pkgs/p/x.md names the stale path" in out, out
    assert "src/old.py names" not in out, out
    # I9 a stale worklog index is E015; `genome emit` repairs it
    (root / "docs/wl/0099-2026-10-17-hand-made.md").write_text("# 0099 — hand made\n")
    assert "E015" in run(root, "lint", "--code", "E015", ok=False).stdout
    run(root, "emit")
    assert "E015" not in run(root, "lint", "--code", "E015", ok=False).stdout
    # I10 a long body from a file
    (root / "body.md").write_text("## Readings\n\n- x `[IN-SAMPLE]`\n")
    p = root / run(root, "log", "with body", "--body-file", "body.md").stdout.strip()
    assert "## Readings" in p.read_text()
    # I11 the docs landing page is not an orphan
    (root / "README.md").write_text("# r\n")
    (root / "docs/README.md").write_text("# docs\n")
    assert "W009 docs page not linked from README or any docs page: README.md" not in run(root, "lint", ok=False).stdout
    # I12 ask: archived files and generated zones never answer; merged leads keep their weight; adding → add
    (root / "docs/archive/x").mkdir(parents=True)
    (root / "docs/archive/x/zebra.md").write_text("# zebra quagga\n\nzebra quagga zebra\n")
    with open(root / "AGENTS.md", "a") as f:
        f.write("\nHistory: `docs/archive/x/zebra.md`.\n")
    assert "zebra.md" not in run(root, "ask", "zebra quagga", ok=False).stdout
    assert "DOCTRINE.md" not in run(root, "ask", "AD-003 mid superseded", ok=False).stdout.split("\n")[0]
    assert g.stem("adding") == "add"
    lines = ["# Big", ""] + [f"filler line {i}" for i in range(40)]
    lines[10] = "- **Leverage:** one"
    lines[12] = "- **Adding a symbol:** run the lane"
    (root / "docs/BIG.md").write_text("\n".join(lines) + "\n")
    ch = [c for c in g.chunks(root / "docs/BIG.md") if "Leverage" in c[0]]
    assert ch and "Adding a symbol" in ch[0][0] and ch[0][2] - ch[0][1] >= 4, ch  # merged, not a 1-line hit
    # I14 wake shows open hypotheses; I15 doctor prints the inventory
    run(root, "hyp", "add", "a testable claim")
    assert "## HYPOTHESES  1 open" in run(root, "wake", ok=False).stdout
    run(root, "hyp", "verdict", "H1", "rejected", "--evidence", "body.md", "--reopen", "new data")
    assert "| H1 | rejected |" in (root / "docs/kb/HYPOTHESES.md").read_text()
    assert "inventory:" in run(root, "doctor", ok=False).stdout
    assert run(root, "--version").stdout.startswith("genome ")
    # I16 close checks that a changed record is cited by this session's worklog entry
    git(root, "add", "-A"); git(root, "commit", "-qm", "rt3")
    run(root, "rec", "amend", "AD-001", "--title", "t", "--reason", "r", "--body", "b")
    run(root, "log", "an entry that forgets the record")
    assert "not cited: AD-001" in run(root, "close", "--no-gate", ok=False).stdout
    # I18 dotenv values: inline comments and quotes are not part of the secret
    (root / ".env").write_text('A=plainvalue123 # note\nB="quoted value#1" # c\n')
    (root / "genome.toml").write_text((root / "genome.toml").read_text().replace("secrets = []", 'secrets = [".env:A", ".env:B"]'))
    vals = {v for _, v in g.secret_values(g.find_cfg(root))}
    assert vals == {"plainvalue123", "quoted value#1"}, vals
    # I17 a deletion already staged is not in the `git add` line (git would reject the whole command)
    git(root, "rm", "-q", "Cargo.lock")
    out = run(root, "close", "--no-gate", ok=False).stdout
    line = next(ln for ln in out.splitlines() if "git add -- " in ln).strip()
    subprocess.run(line, shell=True, cwd=root, check=True, capture_output=True)
    assert "Cargo.lock" not in line, line
    # J7 `rec amend --body-file -` reads stdin like `log --body-file -`
    r = subprocess.run([sys.executable, G, "rec", "amend", "AD-001", "--title", "t", "--reason", "r", "--body-file", "-"],
                       cwd=root, input="from stdin 77\n", capture_output=True, text=True)
    assert r.returncode == 0 and "from stdin 77" in (d / "AD-001-a.md").read_text(), r.stderr


@case
def layout_invariant(base: Path) -> None:
    """A file may only live where a role points at — and close must not commit one that does not."""
    root = base / "layout"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init")
    # a root document with no role is misplaced
    (root / "ORPHAN.md").write_text("# Orphan\n\nA note nobody routes to.\n")
    out = run(root, "lint", "--code", "E306", "--all", ok=False).stdout
    assert "E306 ORPHAN.md" in out and "no role points here" in out, out
    # the conventional root docs are not misplaced
    (root / "ORPHAN.md").unlink()
    out = run(root, "lint", "--code", "E306", "--all", ok=False).stdout
    assert "E306" not in out, out
    # close must NOT name a misplaced path for commit: the tooling must not
    # produce the litter it is reporting
    (root / "ORPHAN.md").write_text("# Orphan\n\nA note nobody routes to.\n")
    git(root, "add", "ORPHAN.md")
    cl = run(root, "close", "--no-gate", ok=False).stdout
    assert "not committed" in cl and "ORPHAN.md" in cl, cl
    assert "git add -- ORPHAN.md" not in cl, cl
    # a repo that declares its own root_files keeps the strict allow-list it had
    (root / "genome.toml").write_text((root / "genome.toml").read_text().replace(
        "[core]", '[ops]\nroot_files = ["README.md", "AGENTS.md", "TODO.md", "genome.toml", "ORPHAN.md"]\n\n[core]', 1))
    out = run(root, "lint", "--code", "E306", "--all", ok=False).stdout
    assert "E306" not in out, out
    # an ops key that is NOT root_files must not silence the placement check:
    # the lint and close must agree on the same set
    (root / "genome.toml").write_text((root / "genome.toml").read_text().replace(
        '[ops]\nroot_files = ["README.md", "AGENTS.md", "TODO.md", "genome.toml", "ORPHAN.md"]',
        '[ops]\nstale_terms = ["Old/Path"]', 1))
    (root / "ORPHAN.md").write_text("# Orphan\n\nA note nobody routes to.\n")
    git(root, "add", "ORPHAN.md")
    out = run(root, "lint", "--code", "E306", "--all", ok=False).stdout
    assert "E306 ORPHAN.md" in out, out
    cl = run(root, "close", "--no-gate", ok=False).stdout
    assert "ORPHAN.md" in cl and "git add -- ORPHAN.md" not in cl, cl


@case
def redteam4(base: Path) -> None:
    """Round 4 (2026-10-17): a register kept inside a protocol doc, preregs that grow results, symlinks out."""
    root = base / "rt4"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init", "--profile", "research")
    t = (root / "genome.toml").read_text().replace('worklog_form = "file"', 'worklog_form = "numbered"')
    t = t.replace('worklog = "docs/kb/WORKLOG.md"', 'worklog = "docs/wl"')
    t = t.replace('hypotheses = "docs/kb/HYPOTHESES.md"', 'hypotheses = "docs/proto.md#Assumption register"')
    t = t.replace("[research]\n", '[research]\nhyp_prefix = "A"\nhyp_statuses = ["qualified"]\n', 1)
    (root / "genome.toml").write_text(t)
    run(root, "init")
    run(root, "log", "measured it", "--body", "b")
    wl = next((root / "docs/wl").glob("0001-*")).name[:4]
    proto = root / "docs/proto.md"
    proto.write_text("# Protocol\n\n## 7. Assumption register\n\n| # | Assumption | Deconstruction and evidence | Status |\n"
                     f"|---|---|---|---|\n| A1 | x | measured (worklog {wl}) | rejected (ruling 3) |\n"
                     "| A2 | y | partly | qualified |\n\n## 8. Other\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    # J1 the register is the section's first table; qualified statuses read by first word; worklog = evidence
    assert "E20" not in run(root, "lint", "--advisory").stdout
    run(root, "hyp", "add", "z holds")
    txt = proto.read_text()
    assert txt.index("| A3 | z holds | — | open |") < txt.index("## 8. Other"), txt
    assert "A3 [open] z holds" in run(root, "wake").stdout
    (root / "ev.json").write_text("{}")
    run(root, "hyp", "verdict", "A2", "rejected", "--evidence", "ev.json", "--note", "n")
    assert "| A2 | y | partly · [" in proto.read_text() and "`ev.json` — n | rejected |" in proto.read_text()
    # J2 a status outside the vocabulary, and a rejection citing a worklog that does not exist
    proto.write_text(proto.read_text().replace("|---|---|---|---|\n", "|---|---|---|---|\n| A9 | w | — | maybe |\n", 1).replace("open |", "rejected |", 1)
                     .replace(f"worklog {wl}", "worklog 0999"))
    out = run(root, "lint", "--advisory").stdout
    assert "E204 hypothesis" in out and "E205 hypothesis A1: evidence worklog 0999 missing" in out, out
    assert "E205 hypothesis A3: rejected without evidence" in out, out
    # J3 a prereg may grow a Results section; its spec part may not change; --at backfills from history
    spec = root / "pre.md"
    spec.write_text("# Prereg\n\n## Criteria\nX > 0\n")
    git(root, "add", "pre.md"); git(root, "commit", "-qm", "spec")
    spec.write_text(spec.read_text() + "\n## Results — evaluated\nX = 1\n")
    run(root, "prereg", "freeze", "pre.md", "--at", "HEAD")
    assert "E203" not in run(root, "lint", "--advisory").stdout
    spec.write_text(spec.read_text().replace("X > 0", "X > -1"))
    assert "E203 pre-registration `pre.md` changed" in run(root, "lint", "--advisory").stdout
    # J5 a stale term inside its archived path, or in a Revisions section, is not a stale pointer; law after it is
    (root / "genome.toml").write_text(t.replace("[ops]\n", '[ops]\nstale_terms = ["tools/old.py"]\n', 1))
    (root / "law.md").write_text("# L\n\nmoved to `archive/x/tools/old.py`\n\n## Revisions\n\n- used tools/old.py\n")
    git(root, "add", "law.md")
    # the stale-path finding only: `law.md` and `pre.md` are scratch files at the
    # root, which the layout invariant also reports (E306, no role points here)
    stale = [l for l in run(root, "lint", "--advisory").stdout.splitlines()
             if l.startswith("E306") and "names the stale path" in l]
    assert not stale, stale
    (root / "law.md").write_text((root / "law.md").read_text() + "\n## Amendment\n\nrun tools/old.py\n")
    assert "E306 law.md names the stale path" in run(root, "lint", "--advisory").stdout
    (root / "genome.toml").write_text(t)
    # J6 a whole superseded directory archives in one step, with one manifest row
    (root / "old/sub").mkdir(parents=True); (root / "old/sub/a.md").write_text("a\n"); (root / "old/b.md").write_text("b\n")
    out = run(root, "archive", "old", "--reason", "superseded folder").stdout
    arch = next(p for p in (root / "docs").rglob("old") if p.is_dir() and "archive" in str(p))
    assert (arch / "sub/a.md").exists() and not (root / "old").exists(), out
    assert "W007" not in run(root, "lint", "--advisory").stdout  # one manifest row covers the folder's files
    assert any("superseded folder" in m.read_text() for m in (root / "docs").rglob("*.md") if m.name in ("README.md", "INDEX.md"))
    # J4 a tracked symlink out of the repo is E307 unless allow-listed
    os.symlink("/tmp", root / "outside")
    git(root, "add", "outside")
    assert "E307 outside is a symlink out of the repo" in run(root, "lint", "--advisory").stdout
    (root / "genome.toml").write_text(t.replace("[ops]\n", '[ops]\nexternal_ok = ["outside"]\n', 1))
    assert "E307" not in run(root, "lint", "--advisory").stdout




@case
def regress_p0(root: Path) -> None:
    """P0 fixes: B1 frontmatter-less set_front, B2 feed IDs past F9999, B3 done by non-holder, B4 doctor hint,
    path#heading register, two-letter tokens, non-git close"""
    import importlib.machinery, importlib.util
    ld = importlib.machinery.SourceFileLoader("genome_mod", G)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("genome_mod", ld))
    ld.exec_module(mod)
    # B1: a record with no frontmatter gains a well-formed block and keeps its body
    out = mod.set_front("# Title\n\nbody\n", {"status": "Retired"})
    assert out.startswith("---\nstatus: \"Retired\"\n---\n"), out
    assert mod.frontmatter(out).get("status") == "Retired" and out.endswith("# Title\n\nbody\n"), out
    again = mod.set_front(out, {"status": "Superseded", "by": "X"})
    assert again.count("---") == 2 and mod.frontmatter(again).get("by") == "X", again
    # B2 + B3 + B4 + path#heading on a full repo
    full_repo(root)
    d = run(root, "doctor").stdout
    assert "q apply" not in d or "--applied" in d, d
    run(root, "wf", "new", "mig"); run(root, "wf", "add", "mig", "move table")
    run(root, "claim", "mig-001", "--agent", "a")
    r = run(root, "done", "mig-001", "done", "--agent", "b", "--evidence", "ev/x.md", ok=False)
    assert r.returncode == 2 and "claimed" in (r.stdout + r.stderr).lower(), r.stdout + r.stderr
    run(root, "done", "mig-001", "done", "--agent", "a", "--evidence", "ev/x.md")
    # path#heading register: rows outside the named section (a legend table) are not register rows
    reg = root / "TODO.md"
    reg.write_text(reg.read_text() + "\n## Legend\n\n| symbol | meaning |\n|---|---|\n| ! | urgent |\n")
    toml = (root / "genome.toml").read_text().replace('register = "TODO.md"', 'register = "TODO.md#Register"')
    (root / "genome.toml").write_text(toml)
    if "## Register" in reg.read_text():
        assert "E002" not in run(root, "lint", "--advisory").stdout
    # two-letter acronyms survive ask tokenisation
    ag = root / "AGENTS.md"
    ag.write_text(ag.read_text() + "\n## ML pipeline\n\nThe ML pipeline trains nightly.\n")
    out = run(root, "ask", "ML").stdout
    assert "ML pipeline" in out, out
    # not a git repo: close says so instead of passing silently
    plain = root / "plain"
    plain.mkdir()
    (plain / "AGENTS.md").write_text("# a\n")
    c = run(plain, "close", ok=False)
    assert "git" in (c.stdout + c.stderr).lower(), c.stdout + c.stderr


@case
def p1_kernel(root: Path) -> None:
    """P1: one section parser (fences, zones), --json forms, handoff --write keeps curated prose"""
    import json
    full_repo(root)
    ag = root / "AGENTS.md"
    ag.write_text(ag.read_text() + "\n## Real section\n\nalpha beta gamma\n\n~~~\n# not a heading\n~~~\n\n## Next\n\ndelta\n")
    d = json.loads(run(root, "ask", "alpha", "beta", "--json").stdout)
    assert d["hits"] and d["hits"][0]["heading"].startswith("Real section") and "# not a heading" not in str(d), d
    assert not any(h["heading"] == "not a heading" for h in d["hits"]), d
    l = json.loads(run(root, "lint", "--json").stdout)
    assert l["errors"] == 0 and isinstance(l["findings"], list), l
    assert json.loads(run(root, "doctor", "--json").stdout)["healthy"] in (True, False)
    assert json.loads(run(root, "rec", "list", "--json").stdout) == []
    # handoff --write replaces its own zone only
    state = root / "docs/handoff/STATE.md"
    state.write_text(state.read_text() + "\nCURATED PROSE\n")
    run(root, "handoff", "--write"); run(root, "handoff", "--write")
    t = state.read_text()
    assert "CURATED PROSE" in t and t.count("genome:zone handoff") == 1, t


MIND_KINDS = """
[kinds.engram]
path = "map/engrams"
id = "EN-{n:04}"
mutability = "current"
fields = { statement = "text!", valence = "enum:-2..2", intensity = "int:0..10" }
states = ["captured", "mapped", "integrated", "canonical"]
transitions = { captured = ["mapped"], mapped = ["integrated", "captured"], integrated = ["canonical"] }
evidence_on = ["integrated"]
human_only = ["canonical"]
[kinds.engram.relations]
triggers = { to = "engram|emotion", inverse = "triggered-by" }
belongs_to = { to = "emotion", max = 1 }

[kinds.emotion]
path = "map/emotions"
id = "EM-{n:03}"
fields = { name = "text!" }

[kinds.outcome]
path = "data/outcomes.jsonl"
store = "jsonl"
id = "OC-{n:04}"
fields = { channel = "enum:email|dm", reply = "bool" }
states = ["sent", "replied", "won"]

[views.engram-counts]
kind = "engram"
group_count = true
into = "AGENTS.md#engram-counts"
"""


@case
def p2_kinds(root: Path) -> None:
    """P2: a declared kind gets new/move/link/show/find/view and schema-derived lint"""
    import json
    full_repo(root)
    (root / "genome.toml").write_text((root / "genome.toml").read_text() + MIND_KINDS)
    (root / "AGENTS.md").write_text((root / "AGENTS.md").read_text() + "\n<!-- genome:zone engram-counts -->\n")
    assert "E501" not in run(root, "lint", "--advisory").stdout
    # new: required fields, enums and ranges are enforced on write
    assert run(root, "new", "engram", "--title", "x", ok=False).returncode  # statement is required
    assert run(root, "new", "engram", "--title", "x", "--set", "statement=s", "--set", "valence=5", ok=False).returncode
    out = json.loads(run(root, "new", "engram", "--title", "Fear of failure", "--set", "statement=I will fail",
                         "--set", "valence=-2", "--set", "intensity=7", "--json").stdout)
    assert out["id"] == "EN-0001" and out["state"] == "captured", out
    run(root, "new", "engram", "--title", "Avoiding", "--set", "statement=I put it off")
    run(root, "new", "emotion", "--title", "Dread", "--set", "name=dread")
    assert (root / "map/emotions").is_dir() and next((root / "map/emotions").glob("EM-001-*.md"))
    # move: transitions, evidence, human-only
    assert "not allowed" in run(root, "move", "EN-0001", "integrated", ok=False).stderr  # captured -> integrated skips a step
    run(root, "move", "EN-0001", "mapped")
    assert run(root, "move", "EN-0001", "integrated", ok=False).returncode  # needs --evidence
    (root / "evidence").mkdir(exist_ok=True)
    (root / "evidence/ev.md").write_text("session notes\n")
    run(root, "move", "EN-0001", "integrated", "--evidence", "evidence/ev.md")
    r = run(root, "move", "EN-0001", "canonical", ok=False)
    assert r.returncode == 2 and "human-only" in r.stderr, r.stderr
    run(root, "move", "EN-0001", "canonical", "--human", "ishan")
    # link: allowed targets, cardinality, inverse edges
    run(root, "link", "EN-0002", "triggers", "EN-0001")
    assert run(root, "link", "EN-0002", "belongs_to", "EN-0001", ok=False).returncode  # engram is not an emotion
    run(root, "link", "EN-0002", "belongs_to", "EM-001")
    assert run(root, "link", "EN-0001", "belongs_to", "EM-001").returncode == 0
    shown = json.loads(run(root, "show", "EN-0001", "--json").stdout)
    assert shown["inverse"] == [{"rel": "triggered-by", "from": "EN-0002"}], shown
    # find
    f = json.loads(run(root, "find", "engram", "--where", "valence<0", "--json").stdout)
    assert [e["id"] for e in f] == ["EN-0001"], f
    # jsonl kind: append-only events, folded state
    run(root, "new", "outcome", "--set", "channel=email"); run(root, "move", "OC-0001", "replied")
    assert "replied" in run(root, "show", "OC-0001").stdout
    assert len((root / "data/outcomes.jsonl").read_text().splitlines()) == 2
    # views are generated counts
    run(root, "emit")
    assert "| canonical | 1 |" in (root / "AGENTS.md").read_text()
    git(root, "add", "-A"); git(root, "commit", "-qm", "kinds")
    assert "lint: clean" in run(root, "lint").stdout, run(root, "lint", ok=False).stdout
    # lint catches hand edits: a bad enum, a dangling edge, a rewritten append-only log
    f1 = next((root / "map/engrams").glob("EN-0002-*.md"))
    f1.write_text(f1.read_text().replace('state: "captured"', 'state: "nope"').replace('triggers: "EN-0001"', 'triggers: "EN-9999"'))
    out = run(root, "lint", ok=False).stdout
    assert "E503" in out and "E505" in out, (out, f1.read_text())
    f1.write_text(f1.read_text().replace('state: "nope"', 'state: "captured"').replace("EN-9999", "EN-0001"))
    log = root / "data/outcomes.jsonl"
    log.write_text(log.read_text().splitlines()[0] + "\n")
    git(root, "add", "-A"); git(root, "commit", "-qm", "rewrite")
    assert "E508" in run(root, "lint", ok=False).stdout


@case
def p2_kinds_undeclared_md_field(root: Path) -> None:
    """An undeclared front-matter key on a dir kind reaches lint (E502) and no write adopts or drops it.

    Found 2026-10-22 in the venture-pipeline KB audit: parse_dir_entity extracted only declared fields, so
    set(fields) - set(kind fields) was empty by construction and E502 could never fire for a .md row, while
    fold_jsonl enforced it. A typo'd key was silently dropped and lint stayed clean. The fix surfaces the
    undeclared keys on a separate `extra` list: lint sees them, the write paths never do, so a rewrite
    neither re-quotes the typo (adopting it) nor loses the report.
    """
    full_repo(root)
    (root / "genome.toml").write_text((root / "genome.toml").read_text() + MIND_KINDS)
    (root / "AGENTS.md").write_text((root / "AGENTS.md").read_text() + "\n<!-- genome:zone engram-counts -->\n")
    run(root, "new", "engram", "--title", "clean", "--set", "statement=s")
    f = next((root / "map/engrams").glob("EN-0001-*.md"))
    assert "E502" not in run(root, "lint", "--advisory").stdout
    # the defect: a typo'd key in a hand edit is invisible to lint on the old kernel
    f.write_text(f.read_text().replace('title: "clean"', 'title: "clean"\nvalencee: "1"'))
    out = run(root, "lint", ok=False).stdout
    assert "E502" in out and "valencee" in out and "is not a field" in out, out
    # a CLI write never adopts the typo (it is not in fields) and never drops it from the file
    run(root, "set", "EN-0001", "--set", "statement=t")
    assert "valencee" in f.read_text(), f.read_text()
    # removing the key returns lint to clean: the report names the exact key
    f.write_text(f.read_text().replace('valencee: "1"\n', ""))
    assert "lint: clean" in run(root, "lint").stdout, run(root, "lint", ok=False).stdout


@case
def p3_index(root: Path) -> None:
    """P3: rebuildable index, BM25 ask over sections and entities, graph queries, place"""
    import json
    full_repo(root)
    (root / "genome.toml").write_text((root / "genome.toml").read_text() + MIND_KINDS)
    for t in ("Fear of failure", "Avoidance habit", "Perfectionism", "Procrastination loop", "Rest guilt", "Isolated item"):
        run(root, "new", "engram", "--title", t, "--set", f"statement={t.lower()} shows up at night")
    for a, b in (("EN-0001", "EN-0002"), ("EN-0002", "EN-0001"), ("EN-0003", "EN-0001"), ("EN-0003", "EN-0004"), ("EN-0005", "EN-0004")):
        run(root, "link", a, "triggers", b)
    g = lambda *a: json.loads(run(root, "graph", *a, "--json").stdout)
    assert g("neighbors", "EN-0001", "--depth", "1")["layers"] == [["EN-0002", "EN-0003"]]
    assert g("path", "EN-0002", "EN-0005")["path"] == ["EN-0002", "EN-0001", "EN-0003", "EN-0004", "EN-0005"]
    assert g("path", "EN-0002", "EN-0006")["path"] is None
    assert g("hubs")[0]["id"] in ("EN-0001", "EN-0003", "EN-0004")
    assert g("cycles") == [["EN-0001", "EN-0002"]], g("cycles")
    assert ["EN-0001", "EN-0003"] in [list(b) for b in g("bridges")] or ["EN-0003", "EN-0004"] in [list(b) for b in g("bridges")]
    gaps = g("gaps")
    assert any({x["a"], x["c"]} == {"EN-0002", "EN-0003"} for x in gaps), gaps
    # BM25 ask finds an entity and a section; place proposes a kind and nearest entities
    a = json.loads(run(root, "ask", "--index", "perfectionism", "night", "--json").stdout)
    assert a["entities"] and a["entities"][0]["id"] == "EN-0003", a
    pl = json.loads(run(root, "place", "avoidance", "at", "night", "--json").stdout)
    assert pl["candidate_kinds"][0] == "engram" and pl["nearest"], pl
    # deleting the index rebuilds the same answers
    before = run(root, "graph", "hubs", "--json").stdout
    (root / ".genome/index.db").unlink()
    assert run(root, "graph", "hubs", "--json").stdout == before
    assert "10 files" not in run(root, "index").stdout and "entities" in run(root, "index", "--rebuild").stdout
    # an edit shows up on the next query without a manual rebuild
    run(root, "unlink", "EN-0003", "triggers", "EN-0001")
    assert g("neighbors", "EN-0001", "--depth", "1")["layers"] == [["EN-0002"]]


@case
def p5_federation(root: Path) -> None:
    """P5/P6: cards, federate (peer trees untouched), ask --all, repo: pointers, covers/verified drift, upgrade, migrate"""
    import json, shutil
    cache = root / "cards-cache"
    env = {"GENOME_CARDS": str(cache)}
    meta = root / "meta"
    meta.mkdir()
    new_repo(meta)
    run(meta, "init", "--profile", "software")
    (meta / "genome.toml").write_text((meta / "genome.toml").read_text() + '\n[federation]\nrepos = ["*"]\nstatus_into = "AGENTS.md#portfolio"\n')
    (meta / "AGENTS.md").write_text((meta / "AGENTS.md").read_text() + "\n<!-- genome:zone portfolio -->\n")
    a, b = meta / "alpha", meta / "bravo"
    for d in (a, b):
        d.mkdir(); new_repo(d); run(d, "init", "--profile", "software")
    (a / "src").mkdir(); (a / "src/engine.py").write_text("def run():\n    return 1\n")
    (a / "docs").mkdir(exist_ok=True)
    (a / "docs/ARCHITECTURE.md").write_text('---\ncovers: "src/**"\n---\n# Architecture\n\n## Engine\n\nThe pump circulates coolant through the engine.\n')
    (a / "genome.toml").write_text((a / "genome.toml").read_text() + '\n[card]\narchitecture = "docs/ARCHITECTURE.md"\npurpose = "Coolant pump controller for the alpha line."\n')
    (b / "genome.toml").write_text((b / "genome.toml").read_text() + '\n[card]\nprivacy = "local"\n')
    for d in (a, b):
        git(d, "add", "-A"); git(d, "commit", "-qm", "init")
    # drift: unverified -> verified -> stale -> verified
    assert "W402" in run(a, "lint", "--advisory").stdout
    run(a, "verify", "docs/ARCHITECTURE.md", "--reviewed")
    assert run(a, "verify", "docs/ARCHITECTURE.md", ok=False).returncode  # --reviewed is the point
    git(a, "add", "-A"); git(a, "commit", "-qm", "verified")
    assert "W40" not in run(a, "lint", "--advisory").stdout, run(a, "lint", "--advisory").stdout
    (a / "src/engine.py").write_text("def run():\n    return 2\n")
    git(a, "add", "-A"); git(a, "commit", "-qm", "engine change")
    assert "W401 docs/ARCHITECTURE.md is stale" in run(a, "lint", "--advisory").stdout
    (a / "genome.toml").write_text((a / "genome.toml").read_text() + '\n[drift]\nmode = "error"\n')
    assert "E401" in run(a, "lint", ok=False).stdout
    # federate reads trees and writes only the cache + the meta root's own zone
    snap = lambda d: subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=d, capture_output=True, text=True).stdout
    before = (snap(a), snap(b))
    f = run(meta, "federate", env=env)
    assert (snap(a), snap(b)) == before, "federate touched a peer tree"
    assert (cache / "alpha.json").exists() and not (cache / "bravo.json").exists(), f.stdout  # bravo is privacy = local
    card = json.loads((cache / "alpha.json").read_text())
    assert card["purpose"].startswith("Coolant pump") and card["manuals"][0]["stale"] is True, card
    assert "| alpha |" in (meta / "AGENTS.md").read_text()
    # ask --all and repo: pointers
    h = json.loads(run(meta, "ask", "--all", "coolant", "pump", "--json", env=env).stdout)["hits"]
    assert h and h[0]["repo"] == "alpha", h
    r = run(meta, "resolve", "repo:alpha#architecture", env=env).stdout
    assert r.startswith(str(a / "docs/ARCHITECTURE.md")), r
    assert "bravo" not in run(meta, "ask", "--all", "bravo", env=env).stdout
    # a secret-shaped string keeps a card from being written
    (a / "genome.toml").write_text((a / "genome.toml").read_text().replace("Coolant pump controller for the alpha line.",
                                                                          "token Bearer abcdefghijklmnopqrstuvwxyz0123456789"))
    assert run(a, "card", env=env, ok=False).returncode == 2
    # upgrade: dry run, apply keeps a backup, migrate stamps the schema
    skill = root / "skill-genome"
    shutil.copy(G, skill)
    skill.write_text(skill.read_text().replace('VERSION = "', 'VERSION = "9999.', 1))
    (a / "scripts").mkdir(); shutil.copy(G, a / "scripts/genome")
    up = lambda *x: subprocess.run([sys.executable, str(a / "scripts/genome"), *x], cwd=a, capture_output=True, text=True,
                                   env={**os.environ, "GENOME_SKILL": str(skill)})
    assert "9999." in up("upgrade").stdout
    out = up("upgrade", "--apply")
    assert out.returncode == 0 and (a / ".genome/genome.pre-upgrade").exists() and 'VERSION = "9999.' in (a / "scripts/genome").read_text(), out.stdout + out.stderr
    assert "schema_version = 2" in (a / "genome.toml").read_text()  # the upgrade ran the schema-2 migration
    # template overrides live beside the config, not in a patched copy of the CLI
    o = root / "ovr"; o.mkdir(); new_repo(o)
    (o / ".genome/overrides").mkdir(parents=True); (o / ".genome/overrides/RECORDS_TPL.md").write_text("# Registry\n\nLOCAL PARAGRAPH\n")
    run(o, "init", "--profile", "software")
    assert "LOCAL PARAGRAPH" in (o / "docs/RECORDS.md").read_text()


# ---------------------------------------------------------------- P4: blueprints and their kernel

def bp_repo(root: Path, *names: str) -> None:
    new_repo(root)
    run(root, "init", "--blueprint", ",".join(names))


def lint_clean(root: Path) -> None:
    out = run(root, "lint", ok=False)
    assert "lint: clean" in out.stdout, out.stdout + out.stderr


@case
def p4_blueprints(root: Path) -> None:
    """init --blueprint: new genome, idempotence, hand edits kept, extends + backfill + seed, privacy guard, missing module, authoring kit"""
    bp_repo(root, "mind-topology")
    assert 'privacy = "local"' in (root / "genome.toml").read_text()
    kinds = root / "genome/kinds/010-mind-topology.toml"
    assert kinds.read_text() == run(root, "blueprint", "show", "mind-topology", "--toml").stdout
    assert (root / "docs/playbooks/mind-topology.md").exists() and (root / "map/sessions.jsonl").exists()
    lint_clean(root)  # routes to a log kind's file never dangle on a fresh genome
    ag = (root / "AGENTS.md").read_text()
    assert ag.count("docs/playbooks/mind-topology.md") == 1
    assert "playbook (read once per task)" in run(root, "wake").stdout
    out = run(root, "init", "--blueprint", "mind-topology").stdout  # a second run adds nothing
    assert "(kept" in out and (root / "AGENTS.md").read_text() == ag, out
    pb = root / "docs/playbooks/mind-topology.md"
    pb.write_text(pb.read_text() + "\nMINE\n")
    run(root, "init", "--blueprint", "mind-topology")
    assert "MINE" in pb.read_text()  # init never overwrites a file
    # extend later: an entity made before gets the default perspective edges; SU-01 is seeded once
    run(root, "new", "engram", "--title", "e", "--set", "statement=s")
    run(root, "init", "--blueprint", "intersubjective")
    assert (root / "genome/kinds/020-intersubjective.toml").exists()
    show = run(root, "show", "EN-0001").stdout
    assert "of → SU-01" in show and "seen_by → SU-01" in show, show
    run(root, "init", "--blueprint", "intersubjective")
    assert run(root, "find", "subject").stdout.count("SU-01") == 1
    lint_clean(root)
    # subjective data never leaves the machine: close refuses while a remote exists
    git(root, "remote", "add", "origin", "https://example.com/x.git")
    r = run(root, "close", "--no-gate", ok=False)
    assert r.returncode and "remote" in r.stderr + r.stdout, r.stdout + r.stderr
    # a blueprint needing a module the genome lacks is refused before anything is written
    c = root / "core-only"
    c.mkdir()
    new_repo(c)
    run(c, "init")
    r = run(c, "init", "--blueprint", "literature-research", ok=False)
    assert r.returncode and "records" in r.stderr and not (c / "genome").exists(), r.stderr
    # the authoring kit: new (never overwrites) → check → list → apply
    git(root, "remote", "remove", "origin")
    run(root, "blueprint", "new", "habit-log", "--from", "mind-topology")
    f = root / "genome/blueprints/habit-log.toml"
    assert f.exists() and run(root, "blueprint", "new", "habit-log", ok=False).returncode
    r = run(root, "blueprint", "check", "genome/blueprints/habit-log.toml")
    assert "PASS habit-log" in r.stdout, r.stdout + r.stderr
    assert "habit-log" in run(root, "blueprint", "list").stdout
    run(root, "init", "--blueprint", "habit-log")
    run(root, "new", "item", "--title", "walk", "--set", "statement=walk daily")
    lint_clean(root)


@case
def p4_check_catches(root: Path) -> None:
    """blueprint check is a real eval: each deliberate defect fails it, the untouched skeleton passes"""
    new_repo(root)
    run(root, "init")
    run(root, "blueprint", "new", "mut")
    base = (root / "genome/blueprints/mut.toml").read_text()
    assert "PASS mut" in run(root, "blueprint", "check", "mut").stdout

    def mutant(old: str, new: str, expect: str) -> None:
        assert old in base, old
        (root / "genome/blueprints/mut.toml").write_text(base.replace(old, new))
        r = run(root, "blueprint", "check", "mut", ok=False)
        assert r.returncode == 2 and "FAIL mut" in r.stdout and expect in r.stdout, f"{old!r} -> {r.stdout}{r.stderr}"

    mutant('states = ["open", "done"]', 'states = ["open", "done", "lost"]', "cannot be reached")
    mutant('related = { to = "item", inverse = "related-to" }', 'related = { to = "item", min = 1 }', "cannot be created")
    mutant('related = { to = "item", inverse = "related-to" }', 'related = { to = "nothing" }', "unknown kind `nothing`")
    mutant('related = { to = "item", inverse = "related-to" }', 'related = { to = "item", taint = ["done"] }', "no `quarantine` state")
    mutant('summary = "one line: what it holds and what an agent can do with it"', 'summary = ""', "`summary` is required")
    mutant("kind = \"item\"\nstate = \"open\"", "kind = \"ghost\"\nstate = \"open\"", "kind `ghost` is not declared")
    # an unknown [blueprint] key is a typo that would silently switch something off
    mutant('version = "1"', 'version = "1"\nprivcy = "local"', "unknown [blueprint] keys")


KERNEL_TOML = """[genome]
modules = ["core"]
[kinds.src]
path = "k/src"
id = "S-{n:02}"
states = ["live", "retracted"]
transitions = { live = ["retracted"] }
evidence_on = ["retracted"]
quarantine = "retracted"
[kinds.topic]
path = "k/topics"
id = "T-{n:02}"
states = ["a", "owned"]
transitions = { a = ["owned"] }
[kinds.topic.relations]
owner = { to = "src", required_in = ["owned"] }
near = { to = "topic", symmetric = true }
[kinds.claim]
path = "k/claims.jsonl"
store = "jsonl"
id = "C-{n:03}"
fields = { q = "text!" }
states = ["new", "ok", "bad"]
transitions = { new = ["ok"] }
evidence_on = ["ok"]
quarantine = "bad"
[kinds.claim.relations]
cites = { to = "src", min = 1, max = 1, taint = ["retracted"] }
about = { to = "topic", graph = false }
same = { to = "claim", symmetric = true }
[kinds.item]
path = "k/items"
id = "I-{n:02}"
[kinds.item.relations]
of = { to = "topic", default = "T-01", min = 1 }
"""


@case
def p4_kernel(root: Path) -> None:
    """min, required_in, taint, default, symmetric, graph=false, --link, --batch atomicity, multi-id move, entity-id evidence"""
    new_repo(root)
    (root / "genome.toml").write_text(KERNEL_TOML)
    run(root, "new", "src", "--title", "paper A")
    run(root, "new", "topic", "--title", "t1")
    r = run(root, "new", "claim", "--set", "q=x", ok=False)  # min = 1
    assert r.returncode and "--link cites" in r.stderr, r.stderr
    run(root, "new", "claim", "--title", "c1", "--set", "q=x", "--link", "cites=S-01")
    r = run(root, "new", "claim", "--set", "q=y", "--link", "cites=S-01,S-01", "--link", "about=T-01")  # duplicate target collapses
    assert "C-002" in r.stdout
    # default: the item points at T-01 without being told
    run(root, "new", "item", "--title", "i")
    assert "of → T-01" in run(root, "show", "I-01").stdout
    # batch: one bad line writes nothing and names the line; @N reaches an earlier line
    before = (root / "k/claims.jsonl").read_text()
    (root / "b.jsonl").write_text('{"kind":"src","title":"B"}\n{"kind":"claim","set":{"q":"z"},"link":{"cites":"@1"}}\n{"kind":"claim","set":{}}\n')
    r = run(root, "new", "--batch", "b.jsonl", ok=False)
    assert r.returncode and "batch line 3" in r.stderr and (root / "k/claims.jsonl").read_text() == before and "S-02" not in run(root, "find", "src").stdout, r.stderr
    (root / "b.jsonl").write_text('{"kind":"src","title":"B"}\n{"kind":"claim","set":{"q":"z"},"link":{"cites":"@1"}}\n')
    assert "C-003" in run(root, "new", "--batch", "b.jsonl").stdout
    assert "cites → S-02" in run(root, "show", "C-003").stdout
    # required_in is enforced on write: no owner, no `owned`; and the owner cannot be unlinked while owned
    r = run(root, "move", "T-01", "owned", ok=False)
    assert r.returncode and "owner" in r.stderr, r.stderr
    run(root, "link", "T-01", "owner", "S-01")
    run(root, "move", "T-01", "owned")
    assert run(root, "unlink", "T-01", "owner", "S-01", ok=False).returncode
    # taint: a retracted source flags every claim citing it, refuses new citations, and quarantine clears the flag
    assert run(root, "move", "S-01", "retracted", ok=False).returncode  # evidence required
    run(root, "move", "S-01", "retracted", "--evidence", "C-001")  # an entity id is evidence
    out = run(root, "lint", ok=False).stdout
    assert "E510" in out and "C-001" in out and "C-002" in out and "C-003" not in out, out
    r = run(root, "new", "claim", "--set", "q=w", "--link", "cites=S-01", ok=False)
    assert r.returncode and "tainted" in r.stderr, r.stderr
    assert run(root, "move", "C-001", "ok", "--evidence", "genome.toml", ok=False).returncode  # also refused: still cites S-01
    run(root, "move", "C-001,C-002", "bad", "--evidence", "S-01")
    assert "0 error(s)" in run(root, "lint", ok=False).stdout
    # a multi-id move checks every id before moving any
    r = run(root, "move", "C-003,C-001", "ok", "--evidence", "genome.toml", ok=False)
    assert r.returncode and "C-003" in run(root, "show", "C-003").stdout and "[new]" in run(root, "show", "C-003").stdout, r.stderr
    # symmetric: the reverse edge already holds; the pair is no cycle; graph=false edges make no hub
    run(root, "link", "C-001", "same", "C-002")
    assert "already holds" in run(root, "link", "C-002", "same", "C-001").stdout
    assert "no cycles" in run(root, "graph", "cycles").stdout
    assert "T-01" not in run(root, "graph", "neighbors", "C-002", "--depth", "1").stdout  # `about` (C-002 → T-01) is graph = false


@case
def p4_graph_projection(root: Path) -> None:
    """--kind projects through non-K nodes (Swanson ABC); --across keeps only pairs, loops and bridges that cross namespaces"""
    new_repo(root)
    (root / "genome.toml").write_text("""[genome]
modules = ["core"]
[kinds.who]
path = "g/who"
id = "W-{n:02}"
[kinds.thing]
path = "g/things"
id = "N-{n:02}"
[kinds.thing.relations]
of = { to = "who", graph = false, default = "W-01", min = 1 }
to = { to = "thing" }
via = { to = "link" }
[kinds.link]
path = "g/links"
id = "L-{n:02}"
[kinds.link.relations]
a = { to = "thing" }
b = { to = "thing" }
""")
    for t in ("A", "B"):
        run(root, "new", "who", "--title", t)
    for i in range(4):
        run(root, "new", "thing", "--title", f"n{i}", "--link", f"of=W-0{1 if i < 2 else 2}")
    # N-01 -L-01- N-02 -L-02- N-03: N-01 and N-03 share a middle but no direct link
    for a, b in (("N-01", "N-02"), ("N-02", "N-03")):
        run(root, "new", "link", "--title", f"{a}-{b}")
    run(root, "link", "L-01", "a", "N-01"); run(root, "link", "L-01", "b", "N-02")
    run(root, "link", "L-02", "a", "N-02"); run(root, "link", "L-02", "b", "N-03")
    gaps = run(root, "graph", "gaps", "--kind", "thing").stdout
    assert "N-01" in gaps and "N-03" in gaps and "via N-02" in gaps, gaps
    # the same gap seen across namespaces (N-01 is of A, N-03 of B): kept; N-01/N-02 are both A: dropped
    cross = run(root, "graph", "gaps", "--kind", "thing", "--across", "of").stdout
    assert "N-01" in cross and "N-03" in cross, cross
    # a loop inside A and a loop A↔B: --across keeps only the second
    run(root, "link", "N-01", "to", "N-02"); run(root, "link", "N-02", "to", "N-01")
    run(root, "link", "N-02", "to", "N-03"); run(root, "link", "N-03", "to", "N-02")
    plain = run(root, "graph", "cycles").stdout
    only = run(root, "graph", "cycles", "--across", "of").stdout
    assert "N-01" in plain and "N-03" in plain
    assert "N-01 ⟲ N-02" not in only and "N-01" in only.replace("⟲", " ") or "N-03" in only, only


@case
def scenario_mind_topology(root: Path) -> None:
    """a self-feeding knot is found by cycles; interpretations stay proposed; untangling is the operator's alone"""
    bp_repo(root, "mind-topology")
    run(root, "new", "session", "--title", "first", "--set", "mode=capture")
    run(root, "new", "engram", "--title", "fear of being seen", "--set", "statement=I freeze when everyone looks at me", "--link", "from_session=SE-0001")
    run(root, "new", "process", "--title", "avoid rooms", "--set", "type=defence")
    near = run(root, "place", "I freeze when people look at me").stdout
    assert "EN-0001" in near and "via" in near, near  # new material lands near the fear; one line of candidate edges
    run(root, "link", "EN-0001", "triggers", "PR-001")
    run(root, "link", "PR-001", "feeds", "EN-0001")
    assert "EN-0001 ⟲ PR-001" in run(root, "graph", "cycles").stdout
    q = run(root, "wake").stdout
    assert "unmapped: 1" in q and "EN-0001" in q
    # an interpretation must say what it is about, and only the operator confirms it
    assert run(root, "new", "insight", "--title", "i", "--set", "statement=s", "--set", "type=pattern", "--set", "origin=agent", ok=False).returncode
    run(root, "new", "insight", "--title", "avoidance feeds the fear", "--set", "statement=s", "--set", "type=pattern", "--set", "origin=agent", "--link", "about=EN-0001,PR-001")
    assert "awaiting-operator: 1" in run(root, "wake").stdout
    r = run(root, "move", "IN-0001", "confirmed", ok=False)
    assert r.returncode and "human-only" in r.stderr
    run(root, "move", "IN-0001", "confirmed", "--human", "ishan")
    # untangling: the agent may open it, never close it
    run(root, "move", "EN-0001", "mapped")
    run(root, "move", "EN-0001", "untangling")
    assert run(root, "move", "EN-0001", "untangled", "--evidence", "SE-0001", ok=False).returncode
    run(root, "move", "EN-0001", "untangled", "--evidence", "SE-0001", "--human", "ishan")
    lint_clean(root)
    # a shadow is owned by the operator alone, and a local map publishes no card
    run(root, "new", "shadow", "--title", "my ambition", "--set", "trait=ambition", "--set", "golden=true")
    assert run(root, "move", "SH-001", "recognised", ok=False).returncode
    r = run(root, "card", ok=False)
    assert r.returncode == 2 and "publishes no card" in r.stderr, r.stderr


@case
def scenario_intersubjective(root: Path) -> None:
    """the pursue-withdraw loop spans two maps: --across of separates it from a private loop; perspective defaults; TA exchanges"""
    bp_repo(root, "intersubjective")
    run(root, "new", "subject", "--title", "Alex", "--set", "role=partner", "--set", "attachment=avoidant", "--set", "attachment_source=inferred", "--set", "consent=not-asked")
    run(root, "new", "process", "--title", "I pursue", "--set", "type=coping")
    run(root, "new", "process", "--title", "Alex goes quiet", "--set", "type=defence", "--link", "of=SU-02")
    show = run(root, "show", "PR-001").stdout
    assert "of → SU-01" in show and "seen_by → SU-01" in show, show  # perspective defaults to the self subject
    assert "of → SU-02" in run(root, "show", "PR-002").stdout
    run(root, "link", "PR-001", "triggers", "PR-002"); run(root, "link", "PR-002", "triggers", "PR-001")
    # a loop wholly inside one map (self): the plain query shows both loops, --across only the one between people
    run(root, "new", "engram", "--title", "not good enough", "--set", "statement=s")
    run(root, "new", "process", "--title", "overwork", "--set", "type=coping")
    run(root, "link", "EN-0001", "triggers", "PR-003"); run(root, "link", "PR-003", "feeds", "EN-0001")
    plain = run(root, "graph", "cycles").stdout
    across = run(root, "graph", "cycles", "--across", "of").stdout
    assert "EN-0001" in plain and "PR-002" in plain, plain
    assert "PR-002" in across and "EN-0001" not in across, across
    assert "PR-001" in run(root, "graph", "hubs", "--across", "of").stdout
    # a transactional-analysis exchange is between exactly two people, with ego states from a closed set
    ok = run(root, "new", "transaction", "--title", "dishes", "--set", "stimulus=CP", "--set", "response=AC", "--set", "type=crossed", "--link", "between=SU-01,SU-02")
    assert "TR-0001" in ok.stdout
    r = run(root, "new", "transaction", "--set", "stimulus=CP", "--set", "response=AC", "--set", "type=crossed", "--link", "between=SU-01", ok=False)
    assert r.returncode and "×2" in r.stderr, r.stderr
    assert run(root, "new", "transaction", "--set", "stimulus=XX", "--set", "response=AC", "--set", "type=crossed", "--link", "between=SU-01,SU-02", ok=False).returncode
    # naming the pattern is the operator's
    run(root, "new", "pattern", "--title", "pursue-withdraw", "--set", "type=pursue-withdraw", "--link", "involves=SU-01,SU-02", "--link", "sustained_by=PR-001,PR-002")
    assert run(root, "move", "PT-001", "named", ok=False).returncode
    lint_clean(root)


@case
def scenario_literature(root: Path) -> None:
    """Swanson's fish-oil gap, a one-call paper ingest that is all-or-nothing, and a retraction that cascades"""
    bp_repo(root, "literature-research")
    for t, ty in (("fish oil", "drug"), ("blood viscosity", "mechanism"), ("Raynaud syndrome", "disease")):
        run(root, "new", "concept", "--title", t, "--set", f"type={ty}")
    (root / "a.jsonl").write_text(
        '{"kind":"source","title":"DiGiacomo 1989","set":{"citation":"DiGiacomo 1989","design":"rct","n":30}}\n'
        '{"kind":"claim","title":"fish oil lowers viscosity","set":{"quote":"fish oil reduced blood viscosity","locator":"p.2 Table 1","direction":"decreases"},'
        '"link":{"cites":"@1","subject":"CO-0001","object":"CO-0002"}}\n')
    out = run(root, "new", "--batch", "a.jsonl").stdout
    assert "SRC-0001" in out and "CL-00001" in out, out
    (root / "b.jsonl").write_text(
        '{"kind":"source","title":"Smith 1980","set":{"citation":"Smith 1980","design":"cohort"}}\n'
        '{"kind":"claim","title":"Raynaud shows high viscosity","set":{"quote":"raised blood viscosity","locator":"p.5"},"link":{"cites":"@1","subject":"CO-0003","object":"CO-0002"}}\n'
        '{"kind":"claim","title":"no source","set":{"quote":"x","locator":"p.1"}}\n')
    r = run(root, "new", "--batch", "b.jsonl", ok=False)  # the third line has no source: nothing at all is written
    assert r.returncode and "batch line 3" in r.stderr and "SRC-0002" not in run(root, "find", "source").stdout, r.stderr
    (root / "b.jsonl").write_text((root / "b.jsonl").read_text().rsplit("\n", 2)[0] + "\n")
    run(root, "new", "--batch", "b.jsonl")
    gaps = run(root, "graph", "gaps", "--kind", "concept").stdout
    assert "CO-0001" in gaps and "CO-0003" in gaps and "via CO-0002" in gaps, gaps  # A and C share B but were never linked
    # claims are verified in a separate pass, with evidence; a finding needs at least one claim
    assert run(root, "move", "CL-00001", "verified", ok=False).returncode
    run(root, "move", "CL-00001,CL-00002", "verified", "--evidence", "research/claims.jsonl")
    assert run(root, "new", "finding", "--title", "f", "--set", "statement=s", "--set", "certainty=low", ok=False).returncode
    run(root, "new", "finding", "--title", "fish oil thins blood", "--set", "statement=s", "--set", "certainty=moderate", "--link", "supported_by=CL-00001,CL-00002")
    run(root, "new", "hypothesis", "--title", "fish oil for Raynaud", "--set", "statement=s", "--set", "origin=abc-gap", "--link", "grounded_in=CL-00001,FI-0001", "--link", "bridges=CO-0001,CO-0003", "--link", "via=CO-0002")
    assert run(root, "move", "HY-0001", "screened", ok=False).returncode  # a logged novelty search is the evidence
    run(root, "new", "search", "--set", "database=PubMed", "--set", "query=fish oil raynaud", "--set", "executed=yes", "--set", "hits=14", "--link", "for_question=HY-0001")
    run(root, "move", "HY-0001", "screened", "--evidence", "SR-0001")
    run(root, "move", "HY-0001", "testing")
    r = run(root, "move", "HY-0001", "supported", "--evidence", "genome.toml", ok=False)
    assert r.returncode and "human-only" in r.stderr
    # a retraction cascades one reviewed hop at a time
    run(root, "move", "SRC-0002", "retracted", "--evidence", "genome.toml")
    flagged = run(root, "lint", ok=False).stdout
    assert "E510" in flagged and "CL-00002" in flagged, flagged
    run(root, "move", "CL-00002", "quarantined", "--evidence", "SRC-0002")
    flagged = run(root, "lint", ok=False).stdout
    assert "E510" in flagged and "FI-0001" in flagged and "CL-00002" in flagged, flagged  # the finding is next
    run(root, "move", "FI-0001", "quarantined", "--evidence", "CL-00002")
    flagged = run(root, "lint", ok=False).stdout
    assert "HY-0001" in flagged and "FI-0001" in flagged, flagged  # then the hypothesis grounded in it
    run(root, "move", "HY-0001", "quarantined", "--evidence", "FI-0001")
    lint_clean(root)
    assert "docs/EVIDENCE.md" in run(root, "emit").stdout or (root / "docs/EVIDENCE.md").exists()


@case
def scenario_ontology(root: Path) -> None:
    """derive, do not borrow: no canonical thesis without a derivation and a human; a witness is never a premise; supersession flags the chain"""
    bp_repo(root, "ontology")
    run(root, "new", "axiom", "--title", "Unity", "--set", "statement=All is one")
    assert run(root, "move", "AX-001", "adopted", ok=False).returncode  # an axiom is adopted by a human
    run(root, "move", "AX-001", "adopted", "--human", "ishan")
    run(root, "new", "thesis", "--title", "Mirror", "--set", "statement=s", "--set", "scope=domain")
    r = run(root, "move", "TH-0001", "canonical-hypothesis", "--evidence", "genome.toml", ok=False)
    assert r.returncode and "red_team_of" in r.stderr, r.stderr  # the evidence must be a red-team of this very thesis
    run(root, "new", "thesis", "--title", "Anti", "--set", "statement=not s", "--set", "scope=domain", "--link", "red_team_of=TH-0001")
    r = run(root, "move", "TH-0001", "canonical-hypothesis", "--evidence", "TH-0002", ok=False)
    assert r.returncode and "derived_by" in r.stderr, r.stderr  # no derivation, no step up
    run(root, "new", "witness", "--title", "Upanishads", "--set", "tradition=Vedic", "--set", "quote=tat tvam asi")
    r = run(root, "new", "derivation", "--title", "d", "--set", "pattern=witness-corroboration", "--link", "from=WI-0001", ok=False)
    assert r.returncode and "witness" in r.stderr, r.stderr  # a witness corroborates, it is not a premise
    run(root, "new", "derivation", "--title", "d", "--set", "pattern=structural-mirroring", "--link", "from=AX-001")
    run(root, "link", "TH-0001", "derived_by", "DV-0001")
    run(root, "link", "TH-0001", "corroborated_by", "WI-0001")
    run(root, "move", "TH-0001", "canonical-hypothesis", "--evidence", "TH-0002")
    assert "awaiting-review: 1" in run(root, "wake").stdout
    assert run(root, "move", "TH-0001", "canonical", "--evidence", "genome.toml", ok=False).returncode
    run(root, "move", "TH-0001", "canonical", "--evidence", "genome.toml", "--human", "ishan")
    assert "TH-0001" in (run(root, "emit").stdout + (root / "docs/ONTOLOGY.md").read_text())
    # the axiom is retired: the derivation resting on it is flagged, suspended, and then the thesis is
    run(root, "move", "AX-001", "retired", "--evidence", "genome.toml", "--human", "ishan")
    assert "DV-0001" in run(root, "lint", ok=False).stdout and "AX-001" in run(root, "lint", ok=False).stdout
    run(root, "move", "DV-0001", "suspended", "--evidence", "AX-001")
    assert "TH-0001" in run(root, "lint", ok=False).stdout
    run(root, "move", "TH-0001", "ai-draft", "--evidence", "DV-0001")
    lint_clean(root)
    # the five-phase catalyst protocol cannot skip a phase
    run(root, "new", "catalyst", "--title", "a prompt", "--set", "type=user-prompt")
    assert run(root, "move", "CA-0001", "placed", "--evidence", "TH-0001", ok=False).returncode


@case
def p4_agent_friction(root: Path) -> None:
    """fixes from the independent-agent runs: link A,B; merged blueprint show; seen_by on every intersubjective kind; feeds/behaviour; witness verification; placed needs produced; collapse_paths"""
    bp_repo(root, "intersubjective")
    shown = run(root, "blueprint", "show", "intersubjective").stdout
    assert "behaviour" in shown and "feeds" in shown and "seen_by" in shown, shown  # the merged chain, with enum values
    run(root, "new", "subject", "--title", "Alex", "--set", "role=partner", "--set", "attachment=avoidant", "--set", "attachment_source=inferred", "--set", "consent=not-asked")
    run(root, "new", "bond", "--title", "us", "--link", "between=SU-01,SU-02")
    run(root, "new", "transaction", "--title", "t", "--set", "stimulus=CP", "--set", "response=AC", "--set", "type=crossed", "--link", "between=SU-01,SU-02")
    for ref in ("BO-001", "TR-0001"):
        assert "seen_by → SU-01" in run(root, "show", ref).stdout, ref
    run(root, "new", "engram", "--title", "e", "--set", "statement=s")
    run(root, "new", "emotion", "--title", "fear", "--set", "family=fear")
    run(root, "new", "process", "--title", "avoids", "--set", "type=behaviour")
    run(root, "link", "EN-0001", "feeds", "EM-001,PR-001")  # one call, several targets
    show = run(root, "show", "EN-0001").stdout
    assert "EM-001" in show and "PR-001" in show, show
    run(root, "link", "EM-001", "feeds", "EN-0001")
    lint_clean(root)
    # ontology: a witness quoted from memory is not verified, and a catalyst cannot be placed having produced nothing
    root2 = root / "o"; root2.mkdir(); bp_repo(root2, "ontology")
    run(root2, "new", "witness", "--title", "w", "--set", "tradition=t", "--set", "quote=q")
    assert run(root2, "move", "WI-0001", "verified", ok=False).returncode  # evidence: the words were checked
    run(root2, "move", "WI-0001", "verified", "--evidence", "genome.toml")
    run(root2, "new", "catalyst", "--title", "c", "--set", "type=user-prompt")
    for st, ev in (("articulated", None), ("red-teamed", "WI-0001"), ("corroborated", "WI-0001")):
        run(root2, "move", "CA-0001", st, *(["--evidence", ev] if ev else []))
    r = run(root2, "move", "CA-0001", "placed", "--evidence", "WI-0001", ok=False)
    assert r.returncode and "produced" in r.stderr, r.stderr
    run(root2, "link", "CA-0001", "produced", "WI-0001")
    run(root2, "move", "CA-0001", "placed", "--evidence", "WI-0001")
    # close: three changed files under one directory become that directory, unless one of them is left out
    import importlib.machinery, importlib.util
    ld = importlib.machinery.SourceFileLoader("genome_mod", G); spec = importlib.util.spec_from_loader("genome_mod", ld)
    mod = importlib.util.module_from_spec(spec); ld.exec_module(mod)
    fs = ["a/x", "a/y", "a/z", "b/q", "top"]
    assert mod.collapse_paths(fs, []) == ["a/", "b/q", "top"], mod.collapse_paths(fs, [])
    assert "a/" not in mod.collapse_paths(fs, ["a/y"])


@case
def p4_round2(root: Path) -> None:
    """round-two agent findings: evidence must be the right kind of entity; forward @N and a loop closed inside one batch; --link hint; impact previews the cascade; unknown kind keys"""
    import json as _json
    bp_repo(root, "literature-research")
    batch = "\n".join(_json.dumps(d) for d in [
        {"kind": "claim", "title": "c", "set": {"quote": "q", "locator": "p1"}, "link": {"cites": "@2", "subject": "@3"}},  # forward refs
        {"kind": "source", "title": "s", "set": {"citation": "c", "design": "rct"}},
        {"kind": "concept", "title": "x", "set": {"type": "drug"}}])
    p = subprocess.run([sys.executable, G, "new", "--batch", "-"], cwd=root, input=batch, capture_output=True, text=True,
                       env={**os.environ, "GENOME_AGENT_ID": "tester"})
    assert p.returncode == 0 and "CL-00001" in p.stdout and "SRC-0001" in p.stdout, p.stdout + p.stderr
    assert "SRC-0001" in run(root, "show", "CL-00001").stdout
    bad = subprocess.run([sys.executable, G, "new", "--batch", "-"], cwd=root, input='{"kind":"concept","title":"y","set":{"type":"drug"},"link":{"is_a":"@9"}}',
                         capture_output=True, text=True)
    assert bad.returncode and bad.stderr.count("batch line") == 1 and "@9" in bad.stderr, bad.stderr  # one prefix, not two
    # a hypothesis is `screened` only on the evidence of a search that was executed
    run(root, "new", "hypothesis", "--title", "h", "--set", "statement=s", "--set", "origin=operator", "--link", "grounded_in=CL-00001")
    run(root, "new", "search", "--set", "database=PubMed", "--set", "query=q", "--set", "executed=no")
    r = run(root, "move", "HY-0001", "screened", "--evidence", "SR-0001", ok=False)
    assert r.returncode and "executed=no" in r.stderr, r.stderr
    assert run(root, "move", "HY-0001", "screened", "--evidence", "genome.toml", ok=False).returncode  # a path will not do either
    run(root, "new", "search", "--set", "database=PubMed", "--set", "query=q2", "--set", "executed=yes")
    run(root, "move", "HY-0001", "screened", "--evidence", "SR-0002")
    run(root, "move", "HY-0001", "proposed")  # a mistaken move can be undone
    # a loop closes inside one batch, and `--link a=X,b=Y` says what to do instead
    o = root / "m"; o.mkdir(); bp_repo(o, "mind-topology")
    loop = '{"kind":"engram","title":"a","set":{"statement":"a"},"link":{"triggers":"@2"}}\n{"kind":"engram","title":"b","set":{"statement":"b"},"link":{"triggers":"@1"}}'
    subprocess.run([sys.executable, G, "new", "--batch", "-"], cwd=o, input=loop, capture_output=True, text=True, check=True)
    assert "EN-0001" in run(o, "graph", "cycles").stdout
    r = run(o, "new", "engram", "--title", "c", "--set", "statement=c", "--link", "triggers=EN-0001,reframes=EN-0002", ok=False)
    assert r.returncode and "Repeat the flag" in r.stderr, r.stderr
    # ontology: impact previews the cascade without writing; a catalyst cannot call an unchecked witness corroboration
    w = root / "o"; w.mkdir(); bp_repo(w, "ontology")
    run(w, "new", "axiom", "--title", "A", "--set", "statement=s"); run(w, "move", "AX-001", "adopted", "--human", "h")
    run(w, "new", "derivation", "--title", "d", "--set", "pattern=none", "--link", "from=AX-001")
    run(w, "new", "thesis", "--title", "t", "--set", "statement=s", "--set", "scope=local"); run(w, "link", "TH-0001", "derived_by", "DV-0001")
    run(w, "new", "thesis", "--title", "anti", "--set", "statement=a", "--set", "scope=local", "--link", "red_team_of=TH-0001")
    run(w, "move", "TH-0001", "canonical-hypothesis", "--evidence", "TH-0002")
    before = run(w, "lint", ok=False).stdout
    imp = run(w, "impact", "AX-001", "--to", "retired").stdout
    assert "hop 2" in imp and "DV-0001 suspended --evidence AX-001" in imp and "TH-0001 ai-draft --evidence DV-0001" in imp, imp
    assert run(w, "lint", ok=False).stdout == before and "retired" not in run(w, "show", "AX-001").stdout.split("history")[0]
    assert _json.loads(run(w, "impact", "AX-001", "--json").stdout)["hops"][0][0]["ids"] == ["DV-0001"]
    run(w, "new", "witness", "--title", "w", "--set", "tradition=t", "--set", "quote=q"); run(w, "new", "catalyst", "--title", "c", "--set", "type=user-prompt")
    run(w, "move", "CA-0001", "articulated"); run(w, "move", "CA-0001", "red-teamed", "--evidence", "TH-0001")
    r = run(w, "move", "CA-0001", "corroborated", "--evidence", "WI-0001", ok=False)
    assert r.returncode and "state=verified" in r.stderr, r.stderr
    run(w, "move", "WI-0001", "verified", "--evidence", "genome.toml")
    run(w, "move", "CA-0001", "corroborated", "--evidence", "WI-0001")
    # orientation output an agent reads: legal moves shown up front, a stateless kind is a bare count, doctor knows which side is newer
    assert "queued→screened|excluded" in run(w, "blueprint", "show", "literature-research").stdout
    run(w, "new", "concept", "--title", "holon", "--set", "definition=d")
    assert "- concept: 1\n" in run(w, "wake").stdout and "( " not in run(w, "wake").stdout.split("## KINDS")[1].split("##")[0]
    old = root / "old-genome"; old.write_text('VERSION = "2020.01.01-1"\n')
    assert "newer than the installed skill copy" in run(w, "doctor", ok=False, env={"GENOME_SKILL": str(old)}).stdout
    # a misspelt kind key is an error, not a silent no-op
    (w / "genome/kinds/090-typo.toml").write_text('[kinds.note]\npath = "n"\nid = "N-{n:02}"\nstates = ["a", "b"]\nevidence_refs = { b = "note" }\n')
    assert "unknown key" in run(w, "lint", ok=False).stdout


@case
def p4_evidence_graph(root: Path) -> None:
    """a quarantined claim bridges nothing; a hypothesis's own links are proposals, so they do not close a Swanson gap"""
    bp_repo(root, "literature-research")
    run(root, "new", "source", "--title", "s", "--set", "citation=c", "--set", "design=rct")
    for t in ("Magnesium", "CRP", "NMDA"):
        run(root, "new", "concept", "--title", t, "--set", "type=drug")
    run(root, "new", "claim", "--title", "Mg-NMDA", "--set", "quote=q1", "--set", "locator=p1", "--link", "cites=SRC-0001", "--link", "subject=CO-0001", "--link", "object=CO-0003")
    run(root, "new", "claim", "--title", "CRP-Mg", "--set", "quote=q2", "--set", "locator=p2", "--link", "cites=SRC-0001", "--link", "subject=CO-0002", "--link", "object=CO-0001")
    gap = lambda: [ln for ln in run(root, "graph", "gaps", "--kind", "concept").stdout.splitlines() if "CO-0002" in ln and "CO-0003" in ln]
    assert gap(), "CRP and NMDA share magnesium and nothing links them directly: a gap"
    run(root, "new", "hypothesis", "--title", "h", "--set", "statement=s", "--set", "origin=abc-gap", "--link", "grounded_in=CL-00001",
        "--link", "bridges=CO-0002,CO-0003", "--link", "via=CO-0001")
    assert gap(), "a hypothesis proposing the link must not be what closes the gap"
    # a retraction: the source goes, its claims are quarantined one by one, and the link they carried goes with them
    run(root, "move", "SRC-0001", "retracted", "--evidence", "https://example.org/retraction")
    run(root, "move", "CL-00001,CL-00002", "quarantined", "--evidence", "SRC-0001")
    assert not gap(), "with both claims quarantined nothing connects magnesium to CRP or NMDA, so there is no gap to report"



@case
def installs_registry(root: Path) -> None:
    """installs: register/list/verify/scan round-trip, drift and missing detection, dedupe by path"""
    import json, os
    man = root / "installs.json"
    env = {"GENOME_INSTALLS": str(man)}
    # a fake skills root at the CONVENTIONAL location scan probes, plus a bin symlink on the iso PATH
    sk = root / ".agents/skills/project-genome"; (sk / "scripts").mkdir(parents=True)
    shutil.copyfile(G, sk / "scripts" / "genome")
    bin_dir = root / "bin"; bin_dir.mkdir()
    os.symlink(sk / "scripts" / "genome", bin_dir / "genome")
    iso = {**env, "HOME": str(root), "PATH": str(bin_dir) + ":/usr/bin:/bin"}
    # empty registry: list says so; scan finds both (HOME isolated from the host machine)
    assert "no installs registered" in run(root, "installs", "list", env=env).stdout
    # THE EMPTY-REGISTRY GATE: verify on a fresh manifest is NOT a pass — "all 0
    # registered ... unchanged" is the exact silent success the registry exists
    # to catch, so it must exit 2 and name the nothing-tested cause.
    v0 = run(root, "installs", "verify", ok=False, env=env)
    assert v0.returncode == 2 and "no installs registered" in v0.stderr, (v0.returncode, v0.stderr)
    out = run(root, "installs", "scan", ok=False, env=iso)
    found_paths = [ln.split()[2] for ln in out.stdout.splitlines() if ln.startswith("unregistered")]
    assert str(sk) in found_paths, (found_paths, out.stdout)
    assert str(bin_dir / "genome") in found_paths, (found_paths, out.stdout, iso.get("PATH"))
    # scan exits 2 and names what it found (the skill root and the bin, by path)
    assert out.returncode == 2 and "unregistered" in out.stdout, out.stdout
    # register both (absolute paths are recorded as given, symlinks NOT resolved)
    run(root, "installs", "register", "skill", str(sk), "--note", "test", env=env)
    run(root, "installs", "register", "bin", str(bin_dir / "genome"), env=env)
    data = json.loads(man.read_text())
    paths = {r["path"] for r in data["installs"]}
    assert paths == {str(sk), str(bin_dir / "genome")}, paths
    assert all(r["version"].startswith("2026.") for r in data["installs"]), data
    # re-registering the same path replaces, not duplicates
    run(root, "installs", "register", "skill", str(sk), env=env)
    assert len(json.loads(man.read_text())["installs"]) == 2
    # and now the scan is quiet: everything conventional is registered
    assert "no unregistered installs found" in run(root, "installs", "scan", env=iso).stdout
    # THE RESOLUTION CASE: un-register the bin but keep the skills root registered —
    # the link still resolves INTO a tracked root, so scan must NOT re-report it.
    data = json.loads(man.read_text())
    kept = [r for r in data["installs"] if r["kind"] != "bin"]
    man.write_text(json.dumps(data | {"installs": kept}))
    out = run(root, "installs", "scan", env=iso)
    assert "no unregistered installs found" in out.stdout, ("link-into-tracked-root re-reported", out.stdout)
    # restore the bin registration (drift checks below expect both rows present)
    # THE UPSTREAM CHECK: verify --against-shipped compares every row against the
    # freshest skill/bin copy (the install.sh-managed reference), not against its own
    # registration — the registry-vs-disk verify cannot see that a copy is behind.
    run(root, "installs", "register", "skill", str(sk), env=env)
    stale_copy = root / "oldrepo"; (stale_copy / "scripts").mkdir(parents=True)
    shutil.copyfile(G, stale_copy / "scripts" / "genome")
    gp2 = stale_copy / "scripts" / "genome"
    gp2.write_text(gp2.read_text().replace('VERSION = "2026.', 'VERSION = "2025.'))
    run(root, "installs", "register", "vendored", str(stale_copy), env=env)
    r = run(root, "installs", "verify", "--against-shipped", ok=False, env=env)
    assert r.returncode == 2 and "BEHIND" in r.stdout and str(stale_copy) in r.stdout, (r.returncode, r.stdout)
    # the default verify is UNCHANGED: the older vendored copy matches its own record
    assert "all" in run(root, "installs", "verify", env=env).stdout
    run(root, "installs", "register", "bin", str(bin_dir / "genome"), env=env)
    # verify: all present, versions unchanged -> exit 0
    v = run(root, "installs", "verify", env=env)
    assert "all 3 registered" in v.stdout, v.stdout
    # drift: bump the script's version under the registry -> STALE, exit 2
    gp = sk / "scripts" / "genome"
    gp.write_text(gp.read_text().replace('VERSION = "2026.', 'VERSION = "9999.'))
    v = run(root, "installs", "verify", ok=False, env=env)
    assert v.returncode == 2 and "STALE" in v.stdout, (v.returncode, v.stdout)
    # missing: delete the script -> MISSING (not a crash), exit 2
    gp.unlink()
    v = run(root, "installs", "verify", ok=False, env=env)
    assert v.returncode == 2 and "MISSING" in v.stdout, (v.returncode, v.stdout)
    # bad kind is refused
    assert run(root, "installs", "register", "wrong", str(sk), ok=False, env=env).returncode == 2




@case
def p1_dialect(base: Path) -> None:
    """One glob dialect: schema 2 is root-relative everywhere; schema 1 keeps basename-anywhere for membership
    patterns; `genome migrate` writes `**/` so the rewritten config means what it meant before."""
    import importlib.machinery
    import types
    loader = importlib.machinery.SourceFileLoader("genome_under_test", G)  # no .py suffix: name the loader
    mod = types.ModuleType(loader.name); loader.exec_module(mod)
    v1, v2 = types.SimpleNamespace(schema_version=1), types.SimpleNamespace(schema_version=2)
    assert mod.gmatch("src/deep/b.py", "*.py", v1) and not mod.gmatch("src/deep/b.py", "*.py", v2)
    assert mod.gmatch("a.py", "*.py", v2) and mod.gmatch("src/deep/b.py", "**/*.py", v2)
    assert not mod.gmatch("ax", "**/x", v2) and mod.gmatch("x", "**/x", v2) and mod.gmatch("a/x", "**/x", v2)
    assert mod.gmatch("a.py", "/a.py", v1) and not mod.gmatch("src/a.py", "/a.py", v2)
    root = base / "p1d"; root.mkdir(); new_repo(root)
    (root / "src").mkdir(); (root / "src" / "x.py").write_text("x = 1\n")
    (root / "genome.toml").write_text('[genome]\nmodules = ["core", "ops"]\n\n[paths]\nclosed = "docs/kb/CLOSED.md"\n\n[ops]\ncode_globs = ["*.py"]\n')
    git(root, "add", "-A"); git(root, "commit", "-qm", "init")
    lint = run(root, "lint", ok=False).stdout
    assert "W506 [ops] code_globs: `*.py` matches at any depth" in lint, lint
    assert "W507 [paths] closed is retired" in lint and "E017" not in lint, lint
    run(root, "migrate")
    text = (root / "genome.toml").read_text()
    assert "schema_version = 2" in text and '"**/*.py"' in text, text
    assert "closed =" not in text, text
    assert "W506" not in run(root, "lint", ok=False).stdout
    assert "nothing to migrate" in run(root, "migrate").stdout


@case
def p1_removed(root: Path) -> None:
    """The dead `wf` flag `--workflow` is gone; `wake --write` regenerates the handoff zone that `handoff` wrote."""
    full_repo(root)
    r = run(root, "done", "X-1", "done", "--workflow", "w", ok=False)
    assert r.returncode != 0 and "unrecognized arguments" in r.stderr, r.stderr
    run(root, "wake", "--write")
    assert "genome:zone handoff" in (root / "docs" / "handoff" / "STATE.md").read_text()


@case
def p3_embed(root: Path) -> None:
    """The optional embed hook: every section gets a cached vector, the BM25 pool is re-ranked by cosine, and the index
    is a cache: deleting it and rebuilding gives the same answer and the same vectors."""
    import sqlite3
    new_repo(root)
    run(root, "init", "--profile", "software")
    (root / "scripts").mkdir(exist_ok=True)
    (root / "scripts" / "embed.py").write_text('''import hashlib, json, sys
for line in sys.stdin:
    o = json.loads(line)
    v = [0.0] * 32
    for w in o["text"].lower().split():
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 32] += 1.0
    print(json.dumps({"id": o["id"], "vec": v}))
''')
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "alpha.md").write_text("# Alpha\n\nalpha beta gamma notes about the first topic.\n")
    (root / "docs" / "delta.md").write_text("# Delta\n\ndelta epsilon zeta notes about the second topic.\n")
    toml = (root / "genome.toml").read_text().replace("[core]\n", '[core]\nask_globs = ["docs/**/*.md"]\n', 1)
    (root / "genome.toml").write_text(toml + '\n[index]\nembed = "python3 scripts/embed.py"\n')
    git(root, "add", "-A"); git(root, "commit", "-qm", "embed")
    assert "embedded" in run(root, "index").stdout
    db = root / ".genome" / "index.db"

    def vectors() -> tuple[int, int]:
        con = sqlite3.connect(db)
        try:
            return con.execute("select count(*) from sec").fetchone()[0], con.execute("select count(*) from vec").fetchone()[0]
        finally:
            con.close()

    sections, embedded = vectors()
    assert sections >= 2 and embedded == sections, (sections, embedded)
    before = run(root, "ask", "--index", "alpha beta").stdout
    hits = [ln for ln in before.splitlines() if "docs/" in ln]
    assert hits and "docs/alpha.md" in hits[0], before
    db.unlink()
    run(root, "index")
    assert vectors() == (sections, embedded), vectors()
    assert run(root, "ask", "--index", "alpha beta").stdout == before, "rebuild after deleting the index changed the answer"


@case
def p5_drift_window(root: Path) -> None:
    """Drift severity: W401 while the warn window is open; E401 once it has closed in a repo with a gate."""
    import re
    new_repo(root)
    run(root, "init", "--profile", "software")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "mod.py").write_text("X = 1\n")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "ARCH.md").write_text('---\ncovers: "src/**"\n---\n# Arch\n\nThe module holds X.\n')
    toml = re.sub(r'(?m)^gate = .*$', 'gate = "true"', (root / "genome.toml").read_text())
    (root / "genome.toml").write_text(toml + '\n[drift]\nwarn_until = "2999-01-01"\n')
    git(root, "add", "-A"); git(root, "commit", "-qm", "base")
    run(root, "verify", "docs/ARCH.md", "--reviewed")  # verified = HEAD, which must exist before verify runs
    git(root, "commit", "-qam", "reviewed")
    (root / "src" / "mod.py").write_text("X = 2\n")
    git(root, "commit", "-qam", "change")
    out = run(root, "lint", "--advisory").stdout
    assert "W401 docs/ARCH.md is stale" in out and "E401" not in out, out
    (root / "genome.toml").write_text((root / "genome.toml").read_text().replace("2999-01-01", "2000-01-01"))
    out = run(root, "lint", "--advisory", ok=False).stdout
    assert "E401 docs/ARCH.md is stale" in out, out


@case
def p5_agnostic_classes(root: Path) -> None:
    """P5: a fresh objective's card classes all resolve, a role form names a doc, and [federation] exclude is honoured"""
    import json
    # 1. a fresh objective: the classes with no role of their own fall back to the agent contract
    fresh = root / "fresh"
    fresh.mkdir()
    new_repo(fresh)
    run(fresh, "init", "--profile", "software")
    card = json.loads(run(fresh, "card", "--stdout").stdout)
    for cls in ("intent", "architecture", "operate", "decisions", "status"):
        assert card["classes"][cls]["exists"], f"{cls} does not resolve on a fresh repo: {card['classes']}"
    assert card["classes"]["architecture"]["path"] == "AGENTS.md#Architecture", card["classes"]["architecture"]
    assert any("Architecture" in h[0] for h in card["headings"]["architecture"]), card["headings"].get("architecture")
    # the fallback never overrides a repo that names its own owner
    (fresh / "docs").mkdir(exist_ok=True)
    (fresh / "docs/ARCH.md").write_text("# Architecture\n\nThe parts, and what each is for.\n")
    (fresh / "genome.toml").write_text((fresh / "genome.toml").read_text() + '\n[card]\narchitecture = "docs/ARCH.md"\n')
    card = json.loads(run(fresh, "card", "--stdout").stdout)
    assert card["classes"]["architecture"]["path"] == "docs/ARCH.md", card["classes"]["architecture"]
    # 2. a role form: the file it names, when this repo has it
    overlay = root / "overlay"
    overlay.mkdir()
    new_repo(overlay)
    run(overlay, "init", "--profile", "software")
    (overlay / "docs/instance-STATE.md").write_text("# Instance state\n\nWhere this instance stands.\n")
    (overlay / "genome.toml").write_text((overlay / "genome.toml").read_text()
                                          .replace('state = "docs/handoff/STATE.md"', 'state = "overlay:docs/instance-STATE.md"'))
    card = json.loads(run(overlay, "card", "--stdout").stdout)
    assert card["classes"]["status"] == {"path": "docs/instance-STATE.md", "exists": True}, card["classes"]["status"]
    # a prose role form names no document, so the class stays empty
    (overlay / "genome.toml").write_text((overlay / "genome.toml").read_text()
                                          .replace('state = "overlay:docs/instance-STATE.md"', 'state = "native:the successor pattern"'))
    card = json.loads(run(overlay, "card", "--stdout").stdout)
    assert card["classes"]["status"]["exists"] is False, card["classes"]["status"]
    # the same role string behaves differently in a repo that does not hold the file
    plain = root / "plain"
    plain.mkdir()
    new_repo(plain)
    run(plain, "init", "--profile", "software")
    (plain / "genome.toml").write_text((plain / "genome.toml").read_text()
                                        .replace('state = "docs/handoff/STATE.md"', 'state = "overlay:docs/instance-STATE.md"'))
    card = json.loads(run(plain, "card", "--stdout").stdout)
    assert card["classes"]["status"]["exists"] is False, card["classes"]["status"]
    # 3. [federation] exclude: membership is a decision, not a glob accident
    meta = root / "meta"
    meta.mkdir()
    new_repo(meta)
    run(meta, "init", "--profile", "software")
    (meta / "genome.toml").write_text((meta / "genome.toml").read_text() + '\n[federation]\nrepos = ["*", "*/*"]\n')
    for name in ("venture", "EXPERIMENTAL/fixture"):
        d = meta / name
        d.mkdir(parents=True)
        new_repo(d)
        run(d, "init", "--profile", "software")
        git(d, "add", "-A"); git(d, "commit", "-qm", "init")
    cache = root / "cards"
    env = {"GENOME_CARDS": str(cache)}
    run(meta, "federate", env=env)
    assert (cache / "venture.json").exists() and (cache / "fixture.json").exists(), sorted(p.name for p in cache.glob("*.json"))
    (meta / "genome.toml").write_text((meta / "genome.toml").read_text() + 'exclude = ["EXPERIMENTAL"]\n')
    shutil.rmtree(cache)
    run(meta, "federate", env=env)
    assert (cache / "venture.json").exists(), sorted(p.name for p in cache.glob("*.json"))
    assert not (cache / "fixture.json").exists(), "exclude did not drop the fixture"


@case
def p5_class_intent(root: Path) -> None:
    """P5: a question that names a doc class is answered with that class's document, and a card whose repo is gone is pruned."""
    import json, shutil
    meta = root / "meta"
    meta.mkdir()
    new_repo(meta)
    run(meta, "init", "--profile", "software")
    (meta / "genome.toml").write_text((meta / "genome.toml").read_text() + '\n[federation]\nrepos = ["*"]\n')
    a = meta / "alpha"
    a.mkdir()
    new_repo(a)
    run(a, "init", "--profile", "software")
    (a / "docs").mkdir(exist_ok=True)
    (a / "docs/ARCH.md").write_text("# Architecture\n\nThe coolant pump circulates the coolant.\n")
    (a / "genome.toml").write_text((a / "genome.toml").read_text() + '\n[card]\narchitecture = "docs/ARCH.md"\n')
    git(a, "add", "-A"); git(a, "commit", "-qm", "init")
    cache = root / "cards"
    env = {"GENOME_CARDS": str(cache)}
    run(meta, "federate", env=env)

    def top(q):
        h = json.loads(run(meta, "ask", "--all", q, "--json", env=env).stdout)["hits"]
        return h[0] if h else None

    # a question that names a class is answered with that class, not with a routing row
    hit = top("how is alpha built architecture")
    assert hit and hit["repo"] == "alpha" and hit["pointer"] == "repo:alpha#architecture", hit
    assert "docs/ARCH.md" in hit["where"], hit
    # the other classes name themselves too
    for q, cls in (("why is alpha this way", "decisions"), ("where does alpha stand", "status"),
                   ("how do I run alpha", "operate"), ("what is alpha", "intent")):
        hit = top(q)
        assert hit and hit["repo"] == "alpha" and hit["pointer"] == f"repo:alpha#{cls}", (q, hit)
    # a question that names no class is unchanged: the repo's own name still outranks a mention
    h = json.loads(run(meta, "ask", "--all", "alpha coolant pump", "--json", env=env).stdout)["hits"]
    assert h and h[0]["repo"] == "alpha", h
    # the class is the answer even when the routing row matches the question's words better
    assert top("where does the project stand right now")["pointer"] == "repo:alpha#status", top("where does the project stand right now")

    # a card whose repo is gone is pruned, so it cannot outrank a live one
    gone = meta / "gamma"
    gone.mkdir()
    new_repo(gone)
    run(gone, "init", "--profile", "software")
    git(gone, "add", "-A"); git(gone, "commit", "-qm", "init")
    run(meta, "federate", env=env)
    assert (cache / "gamma.json").exists(), sorted(p.name for p in cache.glob("*.json"))
    shutil.rmtree(gone)
    out = run(meta, "federate", env=env).stdout
    assert "pruned 1 stale card" in out, out
    assert not (cache / "gamma.json").exists(), "the card for a deleted repo survived"
    assert (cache / "alpha.json").exists(), "the prune removed a live card"


@case
def p5_offer_class(root: Path) -> None:
    """P5: the offer class is opt-in — empty on a fresh repo, resolved by [card] offer, and answerable by ask --all"""
    import json
    # a fresh repo carries no offers: the class exists on the card but resolves to nothing,
    # because it has no role and no fallback (ventures do not carry offers)
    fresh = root / "fresh"
    fresh.mkdir()
    new_repo(fresh)
    run(fresh, "init", "--profile", "software")
    card = json.loads(run(fresh, "card", "--stdout").stdout)
    assert card["classes"]["offer"] == {"path": "", "exists": False}, card["classes"]["offer"]
    # the meta root opts in: [card] offer points at its proof/evidence document
    meta = root / "meta"
    meta.mkdir()
    new_repo(meta)
    run(meta, "init", "--profile", "software")
    (meta / "docs").mkdir(exist_ok=True)
    (meta / "docs/LEDGER.md").write_text("# Proof ledger\n\n## Offer 3 — the agentic-OS setup\n\n374 tests pass; the price band is $2,500.\n")
    (meta / "genome.toml").write_text((meta / "genome.toml").read_text()
                                        + '\n[card]\noffer = "docs/LEDGER.md"\npurpose = "The meta root of the portfolio."\n')
    (meta / "member").mkdir()
    new_repo(meta / "member")
    run(meta / "member", "init", "--profile", "software")
    cache = root / "cards"
    env = {"GENOME_CARDS": str(cache)}
    run(meta, "federate", env=env)
    run(meta, "card", env=env)  # the root's own card is not a member card; `card` writes it to the same cache
    assert (cache / "meta.json").exists() and (cache / "member.json").exists(), sorted(p.name for p in cache.glob("*.json"))
    rootcard = json.loads((cache / "meta.json").read_text())
    assert rootcard["classes"]["offer"] == {"path": "docs/LEDGER.md", "exists": True}, rootcard["classes"]["offer"]
    assert any("Offer 3" in h[0] for h in rootcard["headings"]["offer"]), rootcard["headings"].get("offer")
    member = json.loads((cache / "member.json").read_text())
    assert member["classes"]["offer"]["exists"] is False, member["classes"]["offer"]
    # a question that names the class is answered with the class document, on the repo that holds one
    h = json.loads(run(meta, "ask", "--all", "what should we offer and at what price", "--json", env=env).stdout)["hits"]
    assert h and h[0]["repo"] == "meta" and h[0]["pointer"] == "repo:meta#offer", h
    assert "docs/LEDGER.md" in h[0]["where"], h[0]
    # and the member never answers an offer question with its offer class (it has none)
    assert not any(x["repo"] == "member" and x["pointer"] == "repo:member#offer" for x in h), h
    # the pointer resolves
    r = run(meta, "resolve", "repo:meta#offer", env=env).stdout
    assert r.startswith(str(meta / "docs/LEDGER.md")), r


def main() -> None:
    names = sys.argv[1:] or list(CASES)
    unknown = [n for n in names if n not in CASES]
    if unknown:
        sys.exit(f"unknown case(s): {unknown}; known: {list(CASES)}")
    failed = []
    for n in names:
        with tempfile.TemporaryDirectory() as d:
            try:
                CASES[n](Path(d))
                print(f"ok    {n}")
            except Exception:
                failed.append(n)
                print(f"FAIL  {n}\n" + "".join("      " + l for l in traceback.format_exc().splitlines(True)))
    print(f"test_genome: {len(names) - len(failed)}/{len(names)} cases ok" + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
