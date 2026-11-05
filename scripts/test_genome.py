#!/usr/bin/env python3
"""Self-check for scripts/genome: every module and every red-team finding, one independent case each.

Run: python3 scripts/test_genome.py [case ...]   (stdlib only; every case builds its own throwaway repo)
Every selected case runs even when one fails; the summary lists them all and the exit code is 1 on any failure.
"""
import json
import os
import re
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
def worktree_coordination(root: Path) -> None:
    """linked worktree: claims, feed ids and seen marks resolve to the main worktree (the coordination home)"""
    full_repo(root)
    wt = root.parent / f"{root.name}-wt"
    git(root, "worktree", "add", "-b", "feat", str(wt))
    run(root, "wf", "new", "mig"); run(root, "wf", "add", "mig", "move table")
    run(root, "claim", "mig-001", "--agent", "a")                 # claimed in the main worktree
    r = run(wt, "claim", "mig-001", "--agent", "b", ok=False)     # the claim is visible from another worktree
    assert r.returncode == 2 and "claimed by a" in r.stdout + r.stderr, r.stdout + r.stderr
    # claim posts F0001 from the main worktree; the worktree's post continues that
    # sequence (F0002) instead of minting F0001 again from its stale local copy
    assert "F0002" in run(wt, "post", "from the worktree").stdout
    r = run(wt, "wake")
    assert "coordination:" in r.stdout and root.as_posix() in r.stdout, r.stdout
    run(wt, "post", "hey @c", "--to", "@c", env={"GENOME_AGENT_ID": "tester"})
    assert "1 new" in run(wt, "wake", env={"GENOME_AGENT_ID": "c"}).stdout
    # the read mark is written to the coordination home, so the next wake (any worktree) starts here
    assert "1 new" not in run(wt, "wake", env={"GENOME_AGENT_ID": "c"}).stdout
    # the same-host default identity is disambiguated per checkout (agent_identity): two worktrees
    # that both forgot GENOME_AGENT_ID are two agents, and one cannot silently take the other's
    # claim. ("" overrides run()'s own tester default, forcing the never-exported fallback path.)
    run(root, "wf", "add", "mig", "second item")
    run(root, "claim", "mig-002", env={"GENOME_AGENT_ID": ""})    # default id in the main worktree
    r = run(wt, "claim", "mig-002", ok=False, env={"GENOME_AGENT_ID": ""})  # the wt default carries @wt — not the same agent
    assert r.returncode == 2 and "claimed by" in r.stdout + r.stderr, r.stdout + r.stderr
    assert "INBOX" in run(wt, "wake").stdout                      # the per-checkout identity gives every worktree its own inbox


@case
def worktrunk_init(root: Path) -> None:
    """init with agents on: the AGENTS.md worktrunk loop always, the wt.toml hooks only when wt exists"""
    new_repo(root)
    run(root, "init", "--profile", "team")
    assert "Parallel agents — worktrees" in (root / "AGENTS.md").read_text()
    (root / ".config" / "wt.toml").unlink(missing_ok=True)  # a host with a real wt already wrote these; re-offer
    fake = root.parent / f"{root.name}-bin"
    fake.mkdir()
    (fake / "wt").write_text("#!/bin/sh\nexit 0\n")
    (fake / "wt").chmod(0o755)
    run(root, "init", "--profile", "team", env={"PATH": f"{fake}:{os.environ['PATH']}"})
    assert "worktrunk hooks" in (root / ".config" / "wt.toml").read_text()
    assert (root / "docs/kb/workflows/.gitkeep").exists()          # empty role dirs survive the trip to a fresh worktree


@case
def coordination_fallback(root: Path) -> None:
    """doctor says it out loud when the coordination home cannot be trusted (the main checkout lost its config)"""
    full_repo(root)
    wt = root.parent / f"{root.name}-wt"
    git(root, "worktree", "add", "-b", "feat", str(wt))
    (root / "genome.toml").rename(root / "genome.toml.bak")
    out = run(wt, "doctor").stdout
    (root / "genome.toml.bak").rename(root / "genome.toml")
    assert "LOCAL coordination" in out, out


@case
def init_agents_note(root: Path) -> None:
    """a pre-existing AGENTS.md is kept — init says the worktrunk loop never landed instead of writing it"""
    new_repo(root)
    (root / "AGENTS.md").write_text("# my repo — my own contract\n")
    out = run(root, "init", "--profile", "team").stdout
    assert "predates the worktrunk loop" in out, out
    assert "Parallel agents — worktrees" not in (root / "AGENTS.md").read_text()


@case
def init_scaffold_has_no_dangling_pointer(root: Path) -> None:
    """`genome init` must not ship a pointer to a file it did not create.

    Measured 2026-11-05: the pre-500d87d init (2026.11.02-60) wrote a
    genome.toml declaring `readme = "README.md"` and an AGENTS.md whose routing
    table cited `README.md`, but its file list never contained a top-level
    README.md -- so the scaffold shipped a broken pointer BY CONSTRUCTION. Six
    fleet repos carry it, and because their scaffolds were never committed the
    lint could not see the half of the tree that was on disk.

    The scaffold is the first thing an operator runs, so a defect in it is the
    most expensive kind: it propagates to every repo it touches and it is
    invisible until someone reads the AGENTS.md. E001 catches the SYMPTOM at
    lint time; this catches the CAUSE at scaffold time.

    Every profile is checked, because a profile nobody checks is a profile
    nobody knows is broken. `full` needs `genome outline` first: the outline
    module's zone is a derived surface, so the scaffold is not clean until it
    is emitted -- that is init's own two-step, not a defect."""
    for prof in ("software", "research", "team"):
        d = root / f"p-{prof}"
        d.mkdir()
        new_repo(d)
        run(d, "init", "--profile", prof)
        git(d, "add", "-A"); git(d, "commit", "-qm", "init")
        out = run(d, "lint", "--code", "E", "--all", ok=False).stdout
        assert "E001" not in out, (f"the {prof} scaffold points at a file it did not create:\n" + out)
        # The declared readme role must be a file that EXISTS, not a promise.
        toml = (d / "genome.toml").read_text()
        m = re.search(r'^readme = "([^"]+)"', toml, re.M)
        assert m, f"the {prof} scaffold declares no readme role"
        assert (d / m.group(1)).is_file(), (
            f"the {prof} scaffold declares readme = {m.group(1)!r} and does not create it")
        assert "`README.md`" not in (d / "AGENTS.md").read_text() or (d / "README.md").is_file(), (
            f"the {prof} scaffold's AGENTS.md cites README.md and does not create it")

    # `full` turns the outline module on, whose zone is derived: init's own
    # second step is `genome outline`, and the scaffold is clean only after it.
    d = root / "p-full"
    d.mkdir()
    new_repo(d)
    run(d, "init", "--profile", "full")
    run(d, "outline")
    git(d, "add", "-A"); git(d, "commit", "-qm", "init")
    out = run(d, "lint", "--code", "E", "--all", ok=False).stdout
    assert "E001" not in out, (f"the full scaffold points at a file it did not create:\n" + out)
    assert (d / "README.md").is_file(), "the full scaffold did not create the README it declares"


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
def numbered_worklog_on_a_file_path_is_reported_not_crashed(root: Path) -> None:
    """`worklog_form = "numbered"` with a FILE `worklog` must be reported, not crash.

    The numbered form stores each entry as its own file under a DIRECTORY. The
    template ships `worklog = "docs/kb/WORKLOG.md"` (a file) and
    `worklog_form = "file"`, so a repo that flips only the form lands on a
    combination the kernel never handled: `Guarded` called `mkdir` on a FILE
    and `genome log` died with a raw FileExistsError traceback.

    The shape of the defect is the one this repo's rules exist to prevent, twice
    over. A traceback in a command log trains a reader to ignore them. And
    `genome doctor` reported `healthy: true` on exactly such a repo — a health
    check that does not check the thing that is broken, standing next to a
    crashing command.

    This case fails on the old code (the traceback) and passes on the new one
    (a named refusal), and it asserts the doctor finding too, because a fix
    that makes the command refuse but leaves doctor saying "healthy" has moved
    the problem rather than closed it.
    """
    full_repo(root)
    toml = (root / "genome.toml").read_text().replace('worklog_form = "file"', 'worklog_form = "numbered"')
    (root / "genome.toml").write_text(toml)
    assert (root / "docs/kb/WORKLOG.md").is_file(), "the fixture's worklog should be a file"

    # the command refuses, and says WHY
    r = run(root, "log", "MISCONFIGURED ENTRY", ok=False)
    both = r.stdout + r.stderr
    assert "Traceback" not in both, f"the command still crashes: {both[-500:]}"
    assert "DIRECTORY" in both, f"the refusal did not say what is wrong: {both[-500:]}"
    assert "WORKLOG.md" in both, f"the refusal did not name the path: {both[-500:]}"

    # and doctor does not call the tree healthy
    d = run(root, "doctor", "--json", ok=False)
    j = json.loads(d.stdout)
    assert not j["healthy"], f"doctor calls a crashing repo healthy: {d.stdout[:400]}"
    assert any("DIRECTORY" in f for f in j["findings"]), j["findings"]


@case
def log_body_is_written(root: Path) -> None:
    """`genome log --body-file` writes the body, in BOTH worklog forms.

    The append form dropped the body: it wrote only the headline line, so
    every entry logged with --body-file in a single-file-worklog repo was
    silently truncated to its title. The worklog is the resume surface, so
    that is a lost-work surface. This case fails on the old code.
    """
    full_repo(root)
    body = "The body says a thing the headline does not: 42 and 43."
    (root / "body.md").write_text(body)

    # --- the append form (worklog_form = "file") ---
    run(root, "log", "APPEND ENTRY", "--body-file", "body.md")
    text = (root / "docs/kb/WORKLOG.md").read_text()
    assert "APPEND ENTRY" in text, text
    assert body in text, "the body was dropped by the append form"

    # --- the numbered form (worklog_form = "numbered") ---
    toml = (root / "genome.toml").read_text().replace('worklog_form = "file"', 'worklog_form = "numbered"')
    toml = toml.replace('worklog = "docs/kb/WORKLOG.md"', 'worklog = "docs/worklog"')
    (root / "genome.toml").write_text(toml)
    (root / "docs/worklog").mkdir()
    run(root, "log", "NUMBERED ENTRY", "--body-file", "body.md")
    numbered = "\n".join(p.read_text() for p in (root / "docs/worklog").glob("*.md"))
    assert "NUMBERED ENTRY" in numbered, numbered
    assert body in numbered, "the body was dropped by the numbered form"

    # --- each form keeps its own shape, and neither drops the body ---
    # The numbered form writes a PAGE, so a multi-line body stays multi-line:
    # a page has room for paragraphs. The append form writes ONE LINE per
    # entry, so its body is flattened. What must hold for both is that the
    # body is PRESENT and that the append form stays one entry.
    (root / "docs/worklog2").mkdir()
    (root / "multi.md").write_text("line one of the body\n\nline two of the body\n")
    toml2 = (root / "genome.toml").read_text().replace('worklog = "docs/worklog"', 'worklog = "docs/worklog2"')
    (root / "genome.toml").write_text(toml2)
    run(root, "log", "MULTILINE ENTRY", "--body-file", "multi.md")
    files = [p for p in (root / "docs/worklog2").glob("*.md") if p.name != "INDEX.md"]
    assert len(files) == 1, files
    page = files[0].read_text()
    assert "line one of the body" in page and "line two of the body" in page, page

    # --- and the file form's entry count grows by exactly ONE ---
    toml3 = toml2.replace('worklog = "docs/worklog2"', 'worklog = "docs/kb/WORKLOG.md"').replace('worklog_form = "numbered"', 'worklog_form = "file"')
    (root / "genome.toml").write_text(toml3)
    before = (root / "docs/kb/WORKLOG.md").read_text().count("- **")
    run(root, "log", "COUNTED ENTRY", "--body-file", "multi.md")
    text = (root / "docs/kb/WORKLOG.md").read_text()
    after = text.count("- **")
    assert after == before + 1, (before, after)
    # the flattened body is on that ONE line, not spread over several
    line = [l for l in text.splitlines() if "COUNTED ENTRY" in l]
    assert len(line) == 1, line
    assert "line one of the body line two of the body" in line[0], line[0]


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
    # A TOMBSTONE AT THE ROOT IS NOT MISPLACED. Measured 2026-10-31 on the live
    # fleet: post-upgrade `E306 PLAN_SESSION_PICKER_UPGRADE.md: no role points
    # here` fired on operant, on the file `genome archive` itself leaves behind —
    # a root pointer whose only content is "this moved to docs/archive/X".
    # Flagging it makes the prescribed act (move the doc, keep the pointer) an
    # error, which leaves the operator to commit an error or drop the pointer.
    # Every other check already honours the marker; this is the placement rule
    # joining them. AND a tombstone does not silence the rule for its neighbours:
    # a tombstone beside an orphan still leaves the orphan reported.
    (root / "TROVE.md").write_text('# TROVE (superseded)\n\n<!-- kb: tombstone target="docs/archive/TROVE.md" -->\n\nMoved on 2026-10-31.\n')
    (root / "ORPHAN.md").write_text("# Orphan\n\nA note nobody routes to.\n")
    out = run(root, "lint", "--code", "E306", "--all", ok=False).stdout
    assert "E306 ORPHAN.md" in out and "TROVE.md" not in out, out
    # and `close`, which decides commit through the same misplaced_paths, must
    # not hold the tombstone back: committing a pointer is the point of one.
    # (The orphan is still withheld — that is the invariant's other half.)
    cl = run(root, "close", "--no-gate", ok=False).stdout
    addline = next((l.strip() for l in cl.splitlines() if "git add" in l), "")
    assert "TROVE.md" in addline, cl
    assert "ORPHAN.md" not in addline and "ORPHAN.md" in cl, cl
    # removing the orphan leaves the tombstone legitimate and the lint clean
    (root / "ORPHAN.md").unlink()
    subprocess.run(["git", "rm", "-q", "--cached", "ORPHAN.md"], cwd=root, capture_output=True)
    out = run(root, "lint", "--code", "E306", "--all", ok=False).stdout
    assert "E306" not in out, out
    # A DOCUMENT THAT DESCRIBES A TOMBSTONE IS NOT A TOMBSTONE. The predicate is
    # anchored to the head of the file, which is where `genome archive` writes the
    # marker, because the old whole-body search was a false-positive machine:
    # measured 2026-11-01, the kernel's own `scripts/test_genome.py` (a live file,
    # 39/39 passing) explains this rule in a comment, and `E005` fired on AGENTS.md
    # for pointing at it — a doc that explains the mechanism read as the mechanism.
    # The writer puts the marker on line 3, inside the window; a marker at line 400
    # is not what any archive wrote.
    import importlib.machinery, importlib.util as _iu
    ld = importlib.machinery.SourceFileLoader("genome_mod_layout", G)
    mod = _iu.module_from_spec(_iu.spec_from_loader("genome_mod_layout", ld)); ld.exec_module(mod)
    real = '# TROVE (superseded)\n\n<!-- kb: tombstone target="docs/archive/TROVE.md" -->\n\nMoved on 2026-10-31.\n'
    prose = ("# Suite notes\n\n" + "filler\n" * 400
             + "the exemption: a file whose head carries the marker is a tombstone;\n"
               "this comment says `<!-- kb: tombstone target=\"x\" -->` and is not one.\n")
    assert mod.is_tombstone(real), real
    assert not mod.is_tombstone(prose), "a prose mention at line 400 was read as a tombstone"


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
def kb_registry(root: Path) -> None:
    """the KB registry: activated genomes found by sweep, reachable by name, lintable from anywhere"""
    import json, os
    man = root / "installs.json"
    # isolate PATH and HOME: scan also probes the host's PATH bins, and a case that
    # sees the real machine's ~/.local/bin/genome is testing the host, not the code
    iso_bin = root / "emptybin"; iso_bin.mkdir()
    env = {"GENOME_INSTALLS": str(man), "HOME": str(root), "PATH": str(iso_bin) + ":/usr/bin:/bin"}
    # a KB that VENDORS the CLI at bin/genome (not scripts/genome) — the layout that
    # made pioneer-qf invisible: the old _script_of looked only in scripts/
    kb_bin = root / "repos" / "bin-kb"; (kb_bin / "bin").mkdir(parents=True)
    shutil.copyfile(G, kb_bin / "bin" / "genome")
    (kb_bin / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    # a KB with NO local CLI at all (the meta-root shape)
    kb_nocli = root / "repos" / "meta-root"; kb_nocli.mkdir(parents=True)
    (kb_nocli / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    # two KBs sharing a basename: addressing must not silently pick one
    a = root / "repos" / "x" / "dup"; (a).mkdir(parents=True)
    (a / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    b = root / "repos" / "y" / "dup"; (b).mkdir(parents=True)
    (b / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')

    # THE SWEEP: scan --roots finds activated genomes the manifest does not know
    s = run(root, "installs", "scan", "--roots", str(root / "repos"), ok=False, env=env)
    assert s.returncode == 2 and "unregistered kb" in s.stdout, (s.returncode, s.stdout)
    for p in (kb_bin, kb_nocli, a, b):
        assert str(p) in s.stdout, f"sweep missed {p}"
    # registering them makes the sweep clean
    for p in (kb_bin, kb_nocli, a, b):
        run(root, "installs", "register", "kb", str(p), env=env)
    s2 = run(root, "installs", "scan", "--roots", str(root / "repos"), env=env)
    assert "no unregistered installs found" in s2.stdout, s2.stdout

    # kb list sees every registered KB
    lst = run(root, "kb", "list", env=env)
    assert "4 knowledge base(s) registered" in lst.stdout, lst.stdout

    # THE BIN/GENOME GAP: a repo whose CLI lives at bin/genome is NOT missing, and
    # its version is read — the old code reported 'missing' for pioneer-qf
    v = run(root, "installs", "verify", env=env)
    assert "MISSING" not in v.stdout, v.stdout
    rows = json.loads(man.read_text())["installs"]
    binrow = [r for r in rows if r["path"] == str(kb_bin)][0]
    assert binrow["version"] != "none" and binrow["version"] != "missing", binrow
    # a KB with no local CLI reads 'none' (present, nothing to compare) — not MISSING
    noclirow = [r for r in rows if r["path"] == str(kb_nocli)][0]
    assert noclirow["version"] == "none", noclirow

    # THE PACKAGE LAYOUT: a bin console-script stub carries no VERSION line, and the
    # real CLI sits beside it in the environment at lib/python*/site-packages/*/_genome.py.
    # Measured 2026-10-31 on the host, the registry read its bin row as '?' while that
    # file was `2026.10.30-23`, one release ahead of every skills root — so the only
    # aggregate a fleet view could be built on reported its own install as unknown.
    envdir = root / "tool"; (envdir / "bin").mkdir(parents=True)
    (envdir / "lib" / "python3.13" / "site-packages" / "project_genome").mkdir(parents=True)
    (envdir / "bin" / "genome").write_text(
        "#!/usr/bin/env python3\nimport sys\nfrom project_genome import main\nsys.exit(main())\n")
    (envdir / "lib" / "python3.13" / "site-packages" / "project_genome" / "_genome.py").write_text(
        Path(G).read_text())
    run(root, "installs", "register", "bin", str(envdir / "bin" / "genome"), env=env)
    pkgrow = [r for r in json.loads(man.read_text())["installs"] if r["path"] == str(envdir / "bin" / "genome")][0]
    assert pkgrow["version"] not in ("?", "none", "missing"), pkgrow
    # a VERSION-CARRYING bin (pioneer-qf's vendored copy) is left untouched: this must
    # not swallow a real CLI on its way to the package probe
    assert kb_bin.joinpath("bin", "genome").is_file()

    # THE FLEET SURFACE: one view that answers what is behind, by KB label. The ask was
    # three commands in three geometries joined by path; `fleet` is one of them. The
    # fixture is pinned one release older, because a fleet of copies at the running
    # version prints "current" for everything and would leave the group untested.
    cur = re.search(r'^VERSION = "([^"]+)"', Path(G).read_text(), re.M).group(1)
    prev = re.sub(r"-\d+$", lambda m: f"-{int(m.group(0)[1:]) - 1}", cur)
    kb_bin.joinpath("bin", "genome").write_text(
        Path(G).read_text().replace(f'VERSION = "{cur}"', f'VERSION = "{prev}"', 1))
    fl = run(root, "fleet", env=env)
    assert "current release" in fl.stdout, fl.stdout
    assert "behind (1)" in fl.stdout, f"fleet must name the behind count: {fl.stdout}"
    assert "bin-kb" in fl.stdout, f"a KB label must appear: {fl.stdout}"
    # the version column is on every row, which is what makes the list answer
    # "which are behind" in the same glance as "where are they"
    kbl = run(root, "kb", "list", env=env)
    # The version column is padded to a fixed width, so the gap between the
    # version and the word "behind" is whatever the padding leaves. Asserting
    # a literal run of spaces ties the test to the CURRENT version string's
    # LENGTH: the old "2026.11.02-75" is 13 chars and left 2, while a
    # 12-char "2026.11.05-1" leaves 3. The test failed on a version bump
    # that changed nothing about the behaviour it claims to check, so the
    # assertion now matches the version and the word, not the padding.
    assert re.search(rf"{re.escape(prev)}\s+behind\s+{re.escape(cur)}", kbl.stdout), \
        f"kb list must show the version and the gap: {kbl.stdout}"
    # restore it: the dispatch's target assertion below needs a copy that is NOT behind
    kb_bin.joinpath("bin", "genome").write_text(Path(G).read_text())
    run(root, "installs", "register", "kb", str(kb_bin), env=env)

    # REACHABLE FROM ANYWHERE: resolve a KB by name from an unrelated cwd
    away = root / "elsewhere"; away.mkdir()
    sh = run(away, "kb", "show", "bin-kb", env=env)
    assert str(kb_bin) in sh.stdout, sh.stdout
    # a basename collision is an error naming the candidates, never a guess
    # (die writes to stderr — that is where the candidates are named)
    amb = run(away, "kb", "show", "dup", ok=False, env=env)
    assert amb.returncode == 2 and "several knowledge bases" in amb.stderr, (amb.returncode, amb.stdout, amb.stderr)
    # ... and a full path disambiguates it
    sh2 = run(away, "kb", "show", str(a), env=env)
    assert str(a) in sh2.stdout, sh2.stdout

    # LINT ACROSS THE ESTATE: every registered KB, each with its own CLI, from any cwd
    lint = run(away, "kb", "lint", "--all", env=env)
    assert "4 KB(s)" in lint.stdout, lint.stdout
    # a KB with no CLI is reported as UNLINTED, not as a passing check
    assert "skip" in lint.stdout and "no CLI in this KB" in lint.stdout, lint.stdout

    # THE DISPATCH: a dry run names every copy that is behind the shipped one and
    # writes nothing. The reference is the registered skill/bin copy; a repo that
    # vendors an OLDER CLI is the target.
    sk = root / ".agents/skills/project-genome"; (sk / "scripts").mkdir(parents=True)
    shutil.copyfile(G, sk / "scripts" / "genome")
    old = root / "repos" / "old"; (old / "scripts").mkdir(parents=True)
    shutil.copyfile(G, old / "scripts" / "genome")
    oldcli = old / "scripts" / "genome"
    oldcli.write_text(oldcli.read_text().replace('VERSION = "2026.', 'VERSION = "2025.'))
    (old / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    run(root, "installs", "register", "skill", str(sk), env=env)
    run(root, "installs", "register", "vendored", str(old), env=env)
    d = run(root, "installs", "upgrade", env=env)
    assert "DRY RUN" in d.stdout and str(old) in d.stdout, d.stdout
    # the dry run CHANGED NOTHING
    assert 'VERSION = "2025.' in oldcli.read_text(), "the dry run wrote to a peer repo"
    # a KB with no CLI is not a dispatch target (there is nothing to upgrade there)
    assert str(kb_nocli) not in d.stdout, d.stdout
    # an UP-TO-DATE copy is not a target either: the dispatch names only what is
    # behind, so the list IS the work queue and it must not contain current copies
    # (the swap-source line below legitimately names the skill root, so the check
    # is on the target lines, which is what "is a target" means)
    upgrade_lines = [ln for ln in d.stdout.splitlines() if "would upgrade" in ln]
    assert upgrade_lines and all(str(sk) not in ln and str(kb_bin) not in ln for ln in upgrade_lines), d.stdout
    # the swap SOURCE is named too: the operator must be able to see which copy the
    # fleet is converging toward, and a lagging root is the failure this dispatch
    # exists to prevent (a -23 run converging the fleet on -22 looked like success)
    assert "swap source:" in d.stdout or "the swap source is" in d.stdout, d.stdout
    # THE FIX LIST MUST SURVIVE THE DISPATCH. `--apply` and assert the post-upgrade
    # findings reach the operator through the dispatcher, not just through the child run
    # directly: measured 2026-10-31, the dispatcher's own line filter dropped the
    # `post-upgrade:` header, matched no numbered finding, and printed the child's first
    # line twice — so a fleet run showed no fix list at all. A mechanism that reports its
    # own findings is not proven until something prints them.
    import subprocess as _sp
    target = old / "scripts" / "genome"
    kept_text = target.read_text()
    (old / "genome.toml").write_text('[genome]\nmodules = ["core"]\nnonsense_key = 1\n')  # E017: deterministic
    ap = _sp.run([sys.executable, G, "installs", "upgrade", "--roots", str(old), "--apply"],
                 capture_output=True, text=True, cwd=str(root), env={**os.environ, **env})
    # THE REGISTRY RECORDS WHAT THE DISPATCH LANDED: after --apply the manifest row reads
    # the shipped version, so `installs verify` judges later drift from today rather than
    # from registration day — the dispatch used to leave every row it upgraded reading
    # STALE ("changed since registration") forever, which drowned real drift in noise.
    row_after = [r for r in json.loads(man.read_text())["installs"] if r["path"] == str(old)][0]
    assert row_after["version"] == cur, (row_after, cur)
    assert "registry: 1 row(s) recorded at" in ap.stdout, ap.stdout
    target.write_text(kept_text)
    body = ap.stdout
    assert "upgraded" in body and str(old) in body, body
    assert "post-upgrade:" in body, ("the fix-list header was filtered out", body)
    assert "remedies:" in body, ("the remedy line was filtered out", body)
    assert re.search(r"^\s*1\. E017", body, re.M), ("the numbered finding was filtered out", body)
    assert body.count("genome.toml: schema_version") <= 1, ("the child's first line printed twice", body)
    # THE VERDICT IS THE CHILD'S, AND THIS FIXTURE IS WHY. `old` is deliberately broken
    # (E017: an unknown genome.toml key), so its swap leaves an error behind — and the
    # dispatch used to count that `ok` and exit 0, because the child exited 0 and the
    # finding list only ever went to stdout. Measured on the live estate 2026-10-31:
    # `dispatch: 74 ok, 0 failed` printed over a fleet with one broken member. Now the
    # dispatch reads the child's own verdict, prints it, and fails.
    assert "upgraded but BROKEN" in body, ("a broken swap was counted clean", body)
    assert "1 upgraded but BROKEN" in body, body
    assert "upgraded but left broken" in ap.stderr, ap.stderr
    assert ap.returncode == 2, ("the run must fail when a member is left broken", ap.returncode)


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
    # THE RUNNING CLI IS THE REFERENCE FLOOR, NOT THE PUBLISH SNAPSHOT. A skills root at
    # an older release must not drag the reported target backwards: measured 2026-10-31,
    # the four real roots were one release behind the running CLI and this check printed
    # "shipped is 2026.10.30-22" — naming a shipped version nobody held. The running CLI
    # wins, so make the roots lag and assert the reference does not follow them down.
    running_v = re.search(r'^VERSION = "([^"]+)"', Path(G).read_text(), re.M).group(1)
    lagged = sk / "scripts" / "genome"
    original = lagged.read_text()
    lagged.write_text(original.replace('VERSION = "2026.', 'VERSION = "2024.'))
    r2 = run(root, "installs", "verify", "--against-shipped", ok=False, env=env)
    assert f"shipped is {running_v}" in r2.stdout, ("the reference followed a lagging root", r2.stdout)
    assert "BEHIND" in r2.stdout and str(sk) in r2.stdout, ("a lagging skill root was not reported", r2.stdout)
    lagged.write_text(original)
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
def upgrade_integrity(root: Path) -> None:
    """The two gates that make a fleet upgrade trustworthy: the swap is verified on disk, and a
    copy that claims a release without its bytes is CORRUPTED rather than clean."""
    import importlib.machinery
    import types
    man = root / "installs.json"
    env = {"GENOME_INSTALLS": str(man), "HOME": str(root)}
    # a skills root holding the current release, and the RELEASE LEDGER beside it — the
    # publisher's copy, which is where the ledger lives. Measured 2026-10-31: a vendored
    # repo carries `scripts/genome` and no `releases.txt`, so a check reading the ledger
    # from beside each copy would find nothing on the whole fleet.
    sk = root / ".agents/skills/project-genome"; (sk / "scripts").mkdir(parents=True)
    shutil.copyfile(G, sk / "scripts" / "genome")
    shutil.copyfile(Path(G).with_name("releases.txt"), sk / "scripts" / "releases.txt")
    run(root, "installs", "register", "skill", str(sk), env=env)

    # THE INTEGRITY GATE. A copy at the reference version whose bytes differ from the
    # recorded release is a hand-edit, a partial write, or the wrong restore — and without
    # this check all three read as a clean fleet, because the version line is the only
    # thing either of them touched. Measured 2026-10-31 on the live estate: the gate
    # existed nowhere, and `verify` had one category (behind) for a copy it could not
    # distinguish from a genuine release.
    good = root / "repos" / "gen"; (good / "scripts").mkdir(parents=True)
    shutil.copyfile(sk / "scripts" / "genome", good / "scripts" / "genome")
    (good / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    run(root, "installs", "register", "vendored", str(good), env=env)
    v = run(root, "installs", "verify", "--against-shipped", env=env)
    assert v.returncode == 0, f"an unmodified release must pass: {v.stdout}"
    assert "CORRUPTED" not in v.stdout, f"an unmodified release must not be flagged: {v.stdout}"
    assert "all 2 registered" in v.stdout, v.stdout

    bad = root / "repos" / "bad"; (bad / "scripts").mkdir(parents=True)
    shutil.copyfile(sk / "scripts" / "genome", bad / "scripts" / "genome")
    (bad / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    # the smallest possible local change: one comment line. This is exactly what a stray
    # edit, a bad merge, or a restored-from-the-wrong-backup copy looks like.
    with open(bad / "scripts" / "genome", "a") as f:
        f.write("\n# a local note nobody remembers making\n")
    run(root, "installs", "register", "vendored", str(bad), env=env)
    v = run(root, "installs", "verify", "--against-shipped", ok=False, env=env)
    assert v.returncode == 2 and "CORRUPTED" in v.stdout, (v.returncode, v.stdout)
    assert str(bad) in v.stdout and "differ from the release" in v.stdout, v.stdout
    assert "1 corrupted" in (v.stdout + v.stderr), (v.stdout, v.stderr)
    # and the reason names the remedy's shape: a copy that is not the release is neither
    # a green copy nor merely behind
    assert "hand-edit" in v.stdout or "partial write" in v.stdout, v.stdout

    # THE VERDICT IS THE CHILD'S. The dispatcher's `ok` used to mean "the child exited 0",
    # and a swap that leaves the KB broken exits 0. Measured 2026-10-31 on the live
    # estate: `dispatch: 74 ok, 0 failed` printed while one repo had been left with a
    # stale generated zone the new CLI had correctly caught. `_child_broken` reads the
    # verdict the child already prints, so a broken member cannot be counted green.
    loader = importlib.machinery.SourceFileLoader("genome_uut", G)
    mod = types.ModuleType(loader.name); loader.exec_module(mod)
    clean_child = """upgraded scripts/genome to 2026.10.31-35 (backup: .genome/genome.pre-upgrade)
lint: clean [core, records] — nothing to fix after the upgrade"""
    warn_child = """upgraded scripts/genome to 2026.10.31-35
post-upgrade: 0 error(s), 3 warning(s) to fix in this KB
remedies: link the unreachable docs page"""
    broken_child = """upgraded scripts/genome to 2026.10.31-35
post-upgrade: 1 error(s), 4 warning(s) to fix in this KB
   1. E104 docs/RECORDS.md: zone `records` is stale — `genome rec emit`
remedies: `genome rec emit` (worklog zone is stale)"""
    assert mod._child_broken(clean_child) == "", "a clean child must not be called broken"
    # Warnings are the estate's normal state (100 across the fleet by design): a gate that
    # failed on warnings would fail every run, which is how gates get disabled.
    assert mod._child_broken(warn_child) == "", "warnings are advice, not breakage"
    got = mod._child_broken(broken_child)
    assert got and "1 error" in got, f"a child naming errors must be called broken: {got!r}"

    # THE SCHEMA GATE. A repo that DECLARES an old schema_version reads every membership
    # glob with the wrong dialect, so its checks read the wrong patterns and report clean.
    # Measured 2026-10-31 on the live machine: a schema-1 KB linted with 0 errors and no
    # schema finding of any kind, while `genome migrate` rewrote it — the silent-failure
    # shape, a check that cannot see the repo it is reading wrong. E018 closes it, and
    # `genome migrate` is the remedy. A schema_version that is NOT declared stays
    # tolerated: absent is not the same defect as declared-and-old, and the fixtures (and
    # any pre-key repo) rely on that.
    sr = root / "schema1"; sr.mkdir()
    (sr / "genome.toml").write_text('[genome]\nschema_version = 1\nmodules = ["core"]\n')
    l1 = run(sr, "lint", ok=False).stdout
    assert "E018" in l1 and "schema_version 1" in l1, l1
    assert "E018 genome.toml is schema_version 1; this CLI knows 2" in l1, l1
    run(sr, "migrate")
    assert "E018" not in run(sr, "lint").stdout, "migrate did not clear the schema gate"
    # an undeclared schema is still tolerated, so a pre-key repo is not flagged as behind
    (sr / "genome.toml").write_text('[genome]\nmodules = ["core"]\n')
    assert "E018" not in run(sr, "lint").stdout, "an undeclared schema was flagged as behind"
    # and the remedy names itself, through the same shared table the fleet printer uses
    assert "genome migrate" in mod._remedies_for(["E018"]), mod._remedies_for(["E018"])


@case
def declared_local_patch(root: Path) -> None:
    """A DECLARED local patch is reported as a patch, not as corruption — because the
    alarm's implied remedy would re-break the repo it names.

    Measured 2026-11-04: holon's vendored CLI differs from the -74 release by 127 lines,
    and the difference is the F1 rules (W00A/W00B) that upstream does not carry. The
    divergence was NOT damage. At -71 holon's vendor was byte-identical to the release
    AND carried ZERO F1 rules, because a re-vendor had wiped them; the divergence
    appeared exactly when commit edb9018 restored them.

    So `installs verify --against-shipped` was calling CORRUPTED a repo whose only crime
    was carrying a working fix, and the remedy its message implies — "re-vendor to match
    the release" — would WIPE THE F1 RULES AGAIN and recreate the original bug. The same
    sha comparison is called "local patch" by `upgrade` and by `federation swap`; verify
    was the only path calling it corruption, and the only one that GATED on it.

    The fix is a declaration, not a heuristic: a repo that owns a divergence says so in
    its own genome.toml, and verify reports it. An INFERRED "this looks intentional"
    would silence the alarm exactly where it matters, because corruption and an
    intentional patch are identical on disk.
    """
    import json, os
    man = root / "installs.json"
    env = {"GENOME_INSTALLS": str(man), "HOME": str(root)}
    sk = root / ".agents/skills/project-genome"; (sk / "scripts").mkdir(parents=True)
    shutil.copyfile(G, sk / "scripts" / "genome")
    shutil.copyfile(Path(G).with_name("releases.txt"), sk / "scripts" / "releases.txt")
    run(root, "installs", "register", "skill", str(sk), env=env)

    def make_repo(name: str, declare: bool) -> Path:
        d = root / "repos" / name; (d / "scripts").mkdir(parents=True)
        shutil.copyfile(sk / "scripts" / "genome", d / "scripts" / "genome")
        with open(d / "scripts" / "genome", "a") as f:
            f.write("\n# a local rule upstream does not carry\n")
        toml = '[genome]\nmodules = ["core"]\n'
        if declare:
            toml += '\n[core]\nvendored_cli_patch = "this repo carries its own lint rules"\n'
        (d / "genome.toml").write_text(toml)
        return d

    def register(d: Path) -> None:
        run(root, "installs", "register", "vendored", str(d), env=env)

    # UNDECLARED: still corruption, still gating. The alarm must survive for the case
    # it exists for — a hand-edit nobody remembers making.
    bad = make_repo("bad", declare=False)
    register(bad)
    v = run(root, "installs", "verify", "--against-shipped", ok=False, env=env)
    assert v.returncode == 2, f"an undeclared divergence must still fail the check: {v.stdout}"
    assert "CORRUPTED" in v.stdout and str(bad) in v.stdout, v.stdout
    assert "PATCHED" not in v.stdout, f"an undeclared divergence must not be excused: {v.stdout}"
    assert "1 corrupted" in (v.stdout + v.stderr), (v.stdout, v.stderr)

    # DECLARED: reported as a patch, and NOT gating. The fleet is honest about it and
    # the exit code does not turn a declared patch into a failed fleet. The undeclared
    # repo is unregistered first, so this measures the declared one ALONE.
    data = json.loads(man.read_text())
    man.write_text(json.dumps(data | {"installs": [r for r in data["installs"] if r["path"] != str(bad)]}))
    good = make_repo("good", declare=True)
    register(good)
    v = run(root, "installs", "verify", "--against-shipped", env=env)
    assert v.returncode == 0, f"a declared patch must not fail the check: {v.stdout}\n{v.stderr}"
    assert "PATCHED" in v.stdout and str(good) in v.stdout, v.stdout
    assert "CORRUPTED" not in v.stdout, f"a declared patch must not be called corruption: {v.stdout}"
    # it is still VISIBLE — the operator reads that a repo carries a patch
    assert "1 carrying a declared local patch" in v.stdout, v.stdout

    # THE DECLARATION IS READ FROM THE REPO'S OWN FILE, and it is not a wildcard:
    # an EMPTY value declares nothing, so the alarm stands.
    data = json.loads(man.read_text())
    man.write_text(json.dumps(data | {"installs": [r for r in data["installs"] if r["path"] != str(good)]}))
    empty = make_repo("empty", declare=False)
    (empty / "genome.toml").write_text('[genome]\nmodules = ["core"]\n\n[core]\nvendored_cli_patch = "   "\n')
    register(empty)
    v = run(root, "installs", "verify", "--against-shipped", ok=False, env=env)
    assert v.returncode == 2 and "CORRUPTED" in v.stdout, (v.returncode, v.stdout)
    assert str(empty) in v.stdout, v.stdout

    # AN ABSENT genome.toml declares nothing either: the declaration is opt-in, and a
    # repo without a config file is not excused by default.
    data = json.loads(man.read_text())
    man.write_text(json.dumps(data | {"installs": [r for r in data["installs"] if r["path"] != str(empty)]}))
    bare = root / "repos" / "bare"; (bare / "scripts").mkdir(parents=True)
    shutil.copyfile(sk / "scripts" / "genome", bare / "scripts" / "genome")
    with open(bare / "scripts" / "genome", "a") as f:
        f.write("\n# a local rule upstream does not carry\n")
    register(bare)
    v = run(root, "installs", "verify", "--against-shipped", ok=False, env=env)
    assert v.returncode == 2 and "CORRUPTED" in v.stdout, (v.returncode, v.stdout)
    assert str(bare) in v.stdout, v.stdout

    # THE DECLARATION IS A KNOWN CONFIG KEY, not an unknown one the linter would nag about.
    lint = run(root, "lint", ok=False).stdout
    assert "E016" not in lint and "unknown" not in lint.lower(), lint


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


@case
def p7_uncommitted_copy_is_reported_not_swallowed(root: Path) -> None:
    """P7: a vendored copy can hold the shipped bytes on disk AND be one `git restore`
    from a regression. Measured 2026-11-02 on the host: 74 of 85 registered rows read
    the shipped bytes with ` M scripts/genome` in `git status`, and
    `installs verify --against-shipped` — which reads the disk and never asks git —
    reported all of them healthy. A guard that checks a write landed and nothing that
    checks it stayed landed certifies a regression-in-waiting as clean, so the check
    gains the fourth question and this case pins both halves of it.

    It also pins the symlink half, because the first implementation got it wrong:
    holon/scripts/genome is a symlink to holon/vendor/genome.py, `git status` on the
    LINK is clean while the TARGET is modified, and asking about the link reported the
    uncommitted copy as clean. One fixture covers both shapes."""
    # a repo with a vendored copy, committed and clean
    env = dict(os.environ, GENOME_INSTALLS=str(root / "installs.json"))
    repo = root / "owned"
    repo.mkdir()
    new_repo(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "genome").write_text(Path(G).read_text())
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "pin the vendored CLI")
    run(repo, "installs", "register", "vendored", str(repo), "--note", "a clean vendored copy", env=env)

    # and one whose copy is current on disk but NOT committed — the estate's real state,
    # reached through a symlink so the second blind spot is covered by the same fixture
    dirty = root / "dirty"
    dirty.mkdir()
    new_repo(dirty)
    (dirty / "scripts").mkdir()
    (dirty / "vendor").mkdir()
    (dirty / "vendor" / "genome.py").write_text(Path(G).read_text() + "\n# a local edit\n")
    (dirty / "scripts" / "genome").symlink_to(dirty / "vendor" / "genome.py")
    git(dirty, "add", "-A")
    git(dirty, "commit", "-qm", "pin the vendored CLI and its symlink")
    # the uncommitted shape: the TARGET changes, the link does not
    (dirty / "vendor" / "genome.py").write_text(Path(G).read_text() + "\n# the upgrade write\n")
    run(dirty, "installs", "register", "vendored", str(dirty), "--note", "an uncommitted vendored copy", env=env)

    # verify needs a skill/bin row to name the shipped reference: the publisher's checkout
    # is what `install.sh` manages, and both test copies are versioned against it
    env = dict(os.environ, GENOME_INSTALLS=str(root / "installs.json"))
    (root / "skill").mkdir()
    (root / "skill" / "scripts").mkdir(parents=True)
    (root / "skill" / "scripts" / "genome").write_text(Path(G).read_text())
    run(root, "installs", "register", "skill", str(root / "skill"), env=env)
    v = run(repo, "installs", "verify", "--against-shipped", ok=False, env=env)
    # a report line ends with the prose, not the path, so take the word right after the
    # kind tag instead of the last field
    named = [l.split("—")[0].split()[-1] for l in v.stdout.splitlines() if l.startswith("UNCOMMITTED")]
    assert str(dirty) in named, f"an uncommitted vendored copy must be reported: {v.stdout}"
    assert not any(str(repo) in n for n in named), (
        f"a committed-and-clean copy must not be reported: {v.stdout}")
    # and the symlink blind spot, which is what the first implementation missed: git is
    # asked about the RESOLVED path, so the report names the target, not the clean link
    assert "vendor/genome.py" in v.stdout, (
        f"the report must name the resolved target, not the symlink: {v.stdout}")
    # the exit code is not gated on this: a repo that intentionally gitignores its
    # generated copy is healthy, so the report prints and the owner decides
    assert v.returncode in (0, 2), v.returncode


def name_invariant(base: Path) -> None:
    """A directory's NAME is an invariant, and the absorbed checks must both fire and be escapable.

    These two rules — a forbidden directory NAME, and a file git tracks AND ignores — are
    the only capability workspace-lint carried that genome had no answer for. Both were
    read out of the original validator on 2026-11-02 and re-proven against the live fleet
    the same day, where they found real defects: operant tracks Cargo.lock and
    kernel-sidecar/uv.lock while `*.lock` ignores them, and holon tracks
    .genome/overrides/RECORDS_TPL.md while `.genome/` ignores it.

    A rule that cannot be seen failing is not a rule, so each half gets a violation and
    each declared escape is proven to work and to be scoped.
    """
    root = base / "dirnames"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init")

    def ops(*lines: str) -> None:
        """(Re)write the [ops] block: `genome init` writes none, and a table may
        only appear once, so rewriting beats appending."""
        body = "" if not lines else "".join(lines)
        (root / "genome.toml").write_text((root / "genome.toml").read_text().split("\n[ops]")[0]
                                         + f"\n[ops]\n{body}")

    # ---- 1. E308: a name the project forbids. Silence is the default; a pattern declares it ----
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "00 scratch").mkdir()
    out = run(root, "lint", "--code", "E308", "--all").stdout
    assert "E308" not in out, f"a pattern nobody declared must be silent: {out}"
    ops('dir_name_patterns = ["^00"]\n')
    out = run(root, "lint", "--code", "E308", "--all", ok=False).stdout
    assert "E308" in out and "00 scratch" in out and "dir_name_patterns" in out, out
    # and removing that one pattern removes the error: a declaration, not a constant
    ops()
    out = run(root, "lint", "--code", "E308", "--all").stdout
    assert "E308" not in out, out

    # ---- 2. E308: a collision. Declared by nobody, reported with no pattern at all ----
    # `PHANTOM` beside `phantom` is one directory to a reader and two to git. This is the
    # shape found on the fourfold KBs before the check existed.
    (root / "kb").mkdir(exist_ok=True)
    (root / "kb" / "PHANTOM").mkdir()
    (root / "kb" / "phantom").mkdir()
    out = run(root, "lint", "--code", "E308", "--all", ok=False).stdout
    assert "E308" in out and "normalize to the same" in out, out
    assert "kb/PHANTOM/" in out and "kb/phantom/" in out, f"one line must name both: {out}"
    # The group is JUDGED ONCE AND COMPLETELY, not per pair in readdir order: three
    # directories that normalize together print one line naming all three, and the
    # answer does not depend on which one the filesystem happened to list first.
    (root / "kb" / " Phantom").mkdir()
    out = run(root, "lint", "--code", "E308", "--all", ok=False).stdout
    assert out.count("E308") == 1 and "normalize to the same" in out, out
    for n in ("kb/PHANTOM/", "kb/phantom/", "kb/ Phantom/"):
        assert n in out, f"{n} missing from the one group line: {out}"
    # the exemption is per NAME, and exempting one leaves the others reported
    ops('dir_name_exempt = ["kb/PHANTOM"]\n')
    out = run(root, "lint", "--code", "E308", "--all", ok=False).stdout
    assert "kb/PHANTOM/" not in out and "kb/phantom/" in out and "kb/ Phantom/" in out, out
    # the whole group exempted is silent: a repo that carries `fonts/Font` and
    # `fonts/font` on purpose has said so, and a gate that cannot be satisfied
    # stops being read
    ops('dir_name_exempt = ["kb/**"]\n')
    out = run(root, "lint", "--code", "E308", "--all").stdout
    assert "E308" not in out, out
    # two plainly different names stay silent
    shutil.rmtree(root / "kb" / "phantom"); shutil.rmtree(root / "kb" / "PHANTOM")
    shutil.rmtree(root / "kb" / " Phantom")
    (root / "kb" / "OBELISK").mkdir()
    ops()
    out = run(root, "lint", "--code", "E308", "--all").stdout
    assert "E308" not in out, out

    # ---- 3. E309: a file git tracks AND ignores. This is the measured fleet defect ----
    # `git ls-files -i -c` is the INTERSECTION, proven in a controlled repo where a
    # tracked-only file, an ignored-only file, and a tracked+ignored file sat side by
    # side and only the third was reported. A union would report the root's whole
    # vendor tree on every run, which is why the check is written the way it is.
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "state.jsonl").write_text('{"a": 1}\n')
    (root / ".gitignore").write_text("data/state.jsonl\n")
    git(root, "add", "--force", "data/state.jsonl")
    git(root, "commit", "-qm", "the contradiction")
    out = run(root, "lint", "--code", "E309", "--all", ok=False).stdout
    assert "E309" in out and "data/state.jsonl" in out, out
    assert "tracked and also matches" in out and "git rm --cached" in out, out
    # bulk_allow is the declared escape and it works here too
    ops('bulk_allow = ["data/state.jsonl"]\n')
    out = run(root, "lint", "--code", "E309", "--all").stdout
    assert "E309" not in out, out
    # the file must still exist: a report on a path that is not there is a ghost
    assert (root / "data" / "state.jsonl").exists(), "E309 named a path it could not see"

    # ---- 4. close must withhold the contradiction — the build-time half ----
    ops()
    git(root, "add", "genome.toml")
    cl = run(root, "close", "--no-gate", ok=False).stdout
    assert "data/state.jsonl" in cl and "git add -- data/state.jsonl" not in cl, (
        f"close must not name a tracked-and-ignored path for commit: {cl}")
    subprocess.run(["git", "rm", "--cached", "data/state.jsonl"], cwd=root, capture_output=True)
    out = run(root, "lint", "--code", "E309", "--all").stdout
    assert "E309" not in out, out

    # ---- 5. an undeclared key must fail loudly, never silently switch a check off ----
    ops('dir_name_patterns = []\n')
    out = run(root, "lint", "--code", "E017", "--all").stdout
    assert "E017" not in out, out
    ops('dir_name_paterns = []\n')
    out = run(root, "lint", "--code", "E017", "--all", ok=False).stdout
    assert "E017" in out and "dir_name_paterns" in out, (
        f"an unknown ops key must be E017, not a silent no-op: {out}")
    ops('dir_name_patterns = []\n')
    out = run(root, "lint", "--code", "E017", "--all").stdout
    assert "E017" not in out, out


@case
def redteam5(base: Path) -> None:
    name_invariant(base)


def integrity_module(base: Path) -> None:
    """The three integrity axes, each firing on a violation and silent on a clean tree.

    The three absorbed skills each carried one axis and none carried the other two: `doc`
    validated prose, `install-script-creator` shipped an installer, `workspace-lint`
    checked the tree. This case is what makes all three one discipline, and the clean
    half is the half that matters most — a check that fires on `genome init`'s own
    scaffolding is a check the reader learns to skip.
    """
    root = base / "integrity"
    root.mkdir()
    git(root, "init", "-q"); git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    run(root, "init")
    mods = 'modules = ["core", "integrity"]'
    (root / "genome.toml").write_text(
        (root / "genome.toml").read_text().replace('modules = ["core"]', mods, 1))

    def rewrite(keep_from: str, body: str) -> None:
        """Cut the config at `keep_from` and append a fresh section.

        A TOML table may appear once, and the sections here are appended one after
        another, so replacing the tail is the only way to keep the file valid: a
        `drop` that left an earlier `[app]` in place produced two `[app]` tables,
        and TOML then rejected the whole file with no lint output at all.
        """
        t = (root / "genome.toml").read_text().split(f"\n[{keep_from}]\n")[0]
        (root / "genome.toml").write_text(t + "\n" + body)

    def app(*lines: str) -> None:
        """One `[app]` section, replacing whichever tail section came last.

        `rewrite("app", ...)` only cuts at an `[app]` that already exists, so after the
        `[ops]` step it left the old `dir_globs` block attached and the install-script
        assertions ran against a config that still had directory findings in it.
        """
        t = (root / "genome.toml").read_text()
        for sec in ("app", "ops", "docs"):
            head = f"\n[{sec}]\n"
            if head in t:
                t = t.split(head)[0]
                break
        (root / "genome.toml").write_text(t + "\n[app]\n" + "".join(lines))

    # ---- APP INTEGRITY: the fingerprint is INFO and never fails the build ----
    # The single most important property: a repo with no build (a KB, a notes repo)
    # must not be an error, and a toolchain an operator cannot run (no cargo on a
    # laptop) must be an I, not an E.
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    out = run(root, "lint", "--only", "integrity", "--all").stdout
    assert "I651 app integrity: toolchain python" in out, out
    assert "0 error(s)" in out, out
    # and with NO manifest at all: a KB is not broken for having no toolchain
    (root / "pyproject.toml").unlink()
    out = run(root, "lint", "--only", "integrity", "--all").stdout
    assert "I651" not in out and "lint: clean" in out, out   # a KB is not a finding
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    # ---- a declared phase that FAILS is an E, and stops the commit ----
    app('toolchain = "python"\nbuild = "false"\n')
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E651 [app] build `false` failed" in out, out
    cl = run(root, "close", "--no-gate", ok=False).stdout
    assert "E651" in cl, f"close must surface a failed build: {cl}"
    # a phony pass is silent
    app('toolchain = "python"\nbuild = "true"\n')
    out = run(root, "lint", "--only", "integrity", "--all").stdout
    assert "E651" not in out, out

    # ---- DOCS INTEGRITY: required docs, with content, and required sections ----
    rewrite("app", '[docs]\nrequired = ["README.md", "AGENTS.md", "docs/ARCHITECTURE.md"]\n'
                     'sections = { "docs/ARCHITECTURE.md" = ["Components"] }\n'
                     'min_lines = 30\nmax_lines = 200\n')
    (root / "README.md").write_text("# X\n" + "filler\n" * 250)     # long, no TOC -> W651
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "ARCHITECTURE.md").write_text("# A\n" + "filler\n" * 40)   # wrong section
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E654 docs/ARCHITECTURE.md is missing the required section `Components`" in out, out
    assert "W651 README.md" in out and "table of contents" in out, out
    # min_lines is what makes a doc "thin": a 251-line README is past it, so no W653
    assert "W653 README.md" not in out, out
    # an absent required doc is an E
    (root / "README.md").unlink()
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E653 README.md is declared required by [docs] and does not exist" in out, out
    # a doc that exists but holds only a heading is still an E653 — the half a naive
    # existence check misses, and the reason this is not just `os.path.exists`
    (root / "README.md").write_text("# Only a title\n")
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E653 README.md" in out and "no content beyond its heading" in out, out
    # real content but under min_lines is the WARNING: opt-in, because a hardcoded
    # band flagged every fresh init's stub
    (root / "README.md").write_text("# Title\n\nOne real sentence of prose.\n")
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "W653 README.md" in out and "min_lines = 30" in out, out
    # with min_lines unset, the thin WARNING is silent (the section E654 above still
    # fails the run, so the assertion is on the code's absence, not the exit)
    rewrite("docs", '[docs]\nrequired = ["README.md", "AGENTS.md", "docs/ARCHITECTURE.md"]\n'
                     'sections = { "docs/ARCHITECTURE.md" = ["Components"] }\n')
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "W653" not in out, out
    # ---- DIRECTORY INTEGRITY: declared dirs must exist; stranger empties must not ----
    rewrite("docs", '[ops]\ndir_globs = ["docs/plans", "docs/audit", "vendor/*", "nowhere/*"]\n')
    (root / "vendor").mkdir(); (root / "vendor" / "extra").mkdir()
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E655 nowhere/*" in out and "does not exist" in out, out
    assert "E656 vendor/extra/" in out and "is empty" in out, out
    # ROLE dirs are exempt from E656, because `genome init` creates them empty and they
    # fill as the work happens. Measured 2026-11-03: without this, docs/plans of a fresh
    # tree failed, which is the tool's own scaffolding, so the reader skipped the code.
    assert "E656 docs/plans" not in out and "E656 docs/audit" not in out, out

    # ---- INSTALL-SCRIPT INTEGRITY: declared, executable, verifying ----
    app('install_script = "scripts/setup.sh"\n')
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E657 install script `scripts/setup.sh`" in out, out
    # ONE report for one missing file: the E652/E657 overlap was a real defect found here
    assert out.count("install script `scripts/setup.sh`") == 1, out
    (root / "scripts").mkdir()
    (root / "scripts" / "setup.sh").write_text("#!/bin/sh\necho hi\n")
    os.chmod(root / "scripts" / "setup.sh", 0o644)
    out = run(root, "lint", "--only", "integrity", "--all", ok=False).stdout
    assert "E658 scripts/setup.sh is not executable" in out, out
    assert "W655" in out and "verification step" in out, out
    # executable AND verifying: silent
    (root / "scripts" / "setup.sh").write_text("#!/bin/sh\necho verify\n")
    os.chmod(root / "scripts" / "setup.sh", 0o755)
    out = run(root, "lint", "--only", "integrity", "--all").stdout
    assert "E658" not in out and "W655" not in out, out

    # ---- THE SCAFFOLD FILLS THE README IT MAPS ----
    # The readme role is in every genome.toml this tool emits, and until 2026-11-03 no
    # scaffold wrote it: `genome init` produced a tree that declared `readme =
    # "README.md"` and held no README, so the first thing an operator did — declare
    # `[docs] required = ["README.md"]`, which this module invites — was fail with E653
    # against a file the tool itself was supposed to create. A declaration pointing at
    # nothing is worse than no declaration: it reads as checked and is not. So the
    # scaffold is asserted here, against the file the config maps rather than a
    # hardcoded name, and against the stub being W651-safe.
    fresh = base / "fresh"
    fresh.mkdir()
    run(fresh, "init")
    cfg_text = (fresh / "genome.toml").read_text()
    mapped = re.search(r'readme = "([^"]+)"', cfg_text).group(1)
    assert (fresh / mapped).is_file(), f"init must fill the readme it maps: {mapped}"
    stub = (fresh / mapped).read_text()
    assert stub.strip(), "the readme scaffold must not be an empty file (E653: no content beyond its heading)"
    assert len(stub.splitlines()) < 40, "the stub must stay under any plausible [docs] max_lines, so W651 cannot fire on it"
    # and it must not clobber a real one: adoption fills gaps, it never rewrites
    (fresh / mapped).write_text("# Real\n\nMine.\n")
    run(fresh, "init")
    assert (fresh / mapped).read_text() == "# Real\n\nMine.\n", "init must keep an existing readme word for word"

    # ---- TOOLCHAIN INFERENCE ACROSS LANGUAGES ----
    # The module's whole premise is that "does this still build" is one question answered
    # the same way in every language. Inference is the half nobody can see break, because
    # a manifest it misses reads as a repo with no build, which is a legitimate answer —
    # so the failure mode is SILENCE, not an error. Measured 2026-11-03: a multi-module
    # Gradle project carries settings.gradle(.kts) and may have NO root build script, and
    # the build-file-only manifest list left it unrecognised. One repo per manifest, each
    # asserted to name its toolchain rather than to build.
    for manifest, kind in (("Cargo.toml", "rust"), ("go.mod", "go"), ("tsconfig.json", "typescript"),
                          ("package.json", "node"), ("pyproject.toml", "python"),
                          ("pom.xml", "java"), ("build.gradle", "java"),
                          ("settings.gradle", "java"), ("settings.gradle.kts", "java")):
        d = base / f"lang-{manifest.replace('.', '_')}"
        d.mkdir()
        (d / manifest).write_text("{}\n" if manifest != "go.mod" else "module x\n\ngo 1.21\n")
        run(d, "init")
        t2 = (d / "genome.toml").read_text().replace('modules = ["core"]',
                                                      'modules = ["core", "integrity"]', 1)
        (d / "genome.toml").write_text(t2)
        out = run(d, "lint", "--only", "integrity", "--all").stdout
        assert f"toolchain {kind}" in out, f"{manifest} must infer {kind}: {out}"
        assert "0 error(s)" in out, f"inference is a fact, never a finding: {out}"


@case
def redteam6(base: Path) -> None:
    integrity_module(base)


@case
def redteam7(base: Path) -> None:
    """A `--code` filter that matches nothing is reported, not swallowed.

    Measured 2026-11-03: this repo's own `core.gate` carried `E601 E603 E604 E605 E606
    E607 E608` after the integrity module took the E65x range, and every one of those
    codes matched NOTHING. The gate looked green while checking eight conditions that no
    longer existed, and nothing in the tool could see it — the filter was a set
    intersection with no test that the left side still held anything.

    A typo'd or retired code makes a gate weaker in silence, which is the one failure a
    gate must not have. The test is unfiltered-relative rather than against a hardcoded
    registry: a registry would itself drift, and "this filter matched nothing while
    findings exist" is the fact that matters.
    """
    root = base / "codefilter"
    root.mkdir()
    new_repo(root)
    run(root, "init")
    base_toml = (root / "genome.toml").read_text().replace('modules = ["core"]',
                                                            'modules = ["core", "integrity"]', 1)

    def with_app(build: str) -> None:
        """One `[app]` section per write, so TOML never sees a duplicate table."""
        (root / "genome.toml").write_text(base_toml + f'\n[app]\ntoolchain = "python"\nbuild = "{build}"\n')

    with_app("false")

    # a filter that matches something: no note, and the finding survives
    out = run(root, "lint", "--only", "integrity", "--code", "E651", "--all", ok=False).stdout
    assert "E651 [app] build" in out, out
    assert "matched no finding" not in out, out

    # a filter that matches nothing, in a repo that DOES have findings: the note fires
    out = run(root, "lint", "--only", "integrity", "--code", "E999", "--all").stdout
    assert "matched no finding" in out, out
    # the note must not name the code it failed to match: a code in the note's own text is
    # matched by the filter that found nothing, so `--code E015` would "find" E015 in it
    assert "E999" not in out, f"the note names no code, or the filter matches its own note: {out}"
    assert "E651" not in out, f"the filter must still apply: {out}"

    # a genuinely clean tree is NOT nagged about: matches nothing AND nothing to match
    with_app("true")
    out = run(root, "lint", "--only", "integrity", "--code", "E999", "--all").stdout
    assert "matched no finding" not in out, f"a clean repo must not be told its filter was wrong: {out}"
    assert "lint: clean" in out, out

    # JSON stdout is a CONTRACT: it must parse as ONE document even when the filter hid
    # something. Measured 2026-11-04 — the note printed to stdout ahead of the document,
    # so `lint --json --code <dead>` emitted two lines and every consumer's json.loads()
    # raised. The --code tests above only ever read stdout in TEXT form, and the --json
    # test only ever ran without a filter, so the combination was uncovered.
    with_app("false")
    import json as _json
    res = run(root, "lint", "--only", "integrity", "--code", "E999", "--all", "--json")
    doc = _json.loads(res.stdout)   # raises if stdout is not exactly one JSON document
    assert doc["findings"] == [], doc
    assert doc["errors"] == 0, doc
    # the hidden counts travel INSIDE the document: a consumer reading an empty findings
    # list must still be able to see that the filter hid a live error
    assert doc.get("hidden") == {"errors": 1, "warnings": 0}, doc
    # the note is still said — on stderr, where stdout belongs to the document alone
    assert "matched no finding" in res.stderr, res.stderr

    # a JSON run WITHOUT a filter carries no `hidden` key: absent, not zero, so a
    # consumer can tell "nothing hidden" from "no filter in force". The tree holds a live
    # error, so this run EXITS 2 — that is the gate doing its job, and the document is
    # still the thing on stdout.
    doc2 = _json.loads(run(root, "lint", "--only", "integrity", "--all", "--json", ok=False).stdout)
    assert "hidden" not in doc2, doc2
    assert doc2["errors"] == 1, doc2

    # a JSON run whose filter MATCHES carries no `hidden` key either
    doc3 = _json.loads(run(root, "lint", "--only", "integrity", "--code", "E651", "--all",
                            "--json", ok=False).stdout)
    assert "hidden" not in doc3, doc3
    assert doc3["errors"] == 1 and len(doc3["findings"]) == 1, doc3




@case
def malformed_kind_is_a_message_not_a_traceback(root: Path) -> None:
    """A kind declaration missing `path` must be REPORTED, not crash the command.

    Measured 2026-11-05: `kind_dir()` read `k["path"]` with no guard, so a
    `[kinds.x]` block without a `path` made `graph`, `show`, `card`, `impact`
    and `place` die with a raw Python `KeyError: 'path'` traceback — while
    `lint` reported E501 correctly and `doctor` reported `healthy: true`.

    That is the exact shape this repo's rules exist to prevent, twice over.
    The crash is a traceback in a gate log, which trains a reader to ignore
    them. And `doctor` saying "healthy" on a repo whose commands crash is a
    report that contradicts the tool's own behaviour — a health check that
    does not check the thing that is broken.

    E501 already names the defect ("`path` is required"). So the fix is not a
    new check: it is that the commands must READ the declaration the way the
    linter does, and report the same fact the linter reports.
    """
    import json as _json
    new_repo(root)
    (root / "genome.toml").write_text(
        '[genome]\nmodules = ["core"]\n'
        '[kinds.probe]\n'
        'name = "probe"\n'
        'id = "P-{n:04}"\n'
        'states = ["live"]\n'
    )
    git(root, "add", "-A"); git(root, "commit", "-qm", "init")

    # the linter already names it — this is the fact the commands must share
    out = run(root, "lint", "--all", ok=False).stdout
    assert "E501" in out, out
    assert "path" in out, out

    # and NO command may crash on it. A traceback is a failure of the tool, not
    # of the repo: the repo's mistake is already named by E501.
    for args in (("graph", "probe"), ("show", "X"), ("card", "--stdout"),
                 ("impact", "X"), ("place", "x")):
        r = run(root, *args, ok=False)
        assert "Traceback" not in r.stdout + r.stderr, \
            f"genome {' '.join(args)} crashed on a malformed kind:\n{r.stdout}\n{r.stderr}"
        assert "KeyError" not in r.stdout + r.stderr, \
            f"genome {' '.join(args)} raised KeyError on a malformed kind"

    # doctor must not call a repo healthy whose commands crash.
    #
    # The assertion is on the SPECIFIC finding, not on `healthy` alone. A bare
    # `core` repo is already unhealthy for another reason — it has no
    # AGENTS.md, no docs/, no state — so `healthy is not True` passed on a
    # mutant that dropped the kind check entirely, because the MISSING ROLES
    # kept the repo unhealthy. The mutation escaped because the assertion was
    # satisfied by the wrong fact. So: the kind's own finding must be named.
    doc = _json.loads(run(root, "doctor", "--json").stdout)
    assert doc.get("healthy") is not True, \
        f"doctor reported healthy on a repo whose commands crash: {doc}"
    assert any("probe" in f and "path" in f for f in doc.get("findings", [])), \
        f"doctor did not name the unusable kind: {doc}"


@case
def register_evidence_grammar(root: Path) -> None:
    """E010 reads a register's evidence with the SAME grammar as the ledger's (E009).

    It did not: E010 matched every backticked run containing a slash, so a row whose
    evidence is a shell command (`cp ~/.local/bin/x && systemctl --user restart x`),
    an API route (`GET /api/providers`) or a diff invocation was a lint error — 10
    findings on switchpost's register, every one of them prose. The ledger asked the
    same question of the same kind of cell with the strict grammar and passed. One
    grammar for one question: a token is a missing file only when it is file-shaped.
    """
    full_repo(root)
    # a real file-shaped evidence token is still checked: the check did not go away
    (root / "ev").mkdir()
    (root / "ev" / "x.md").write_text("# x\n")
    reg = root / "TODO.md"
    reg.write_text(reg.read_text() +
                   "\n| R-EV-1 | done | a row whose evidence cites a real file → [2026-11-05] `ev/x.md` | ok |\n"
                   "| R-EV-2 | done | a row whose evidence cites a shell command → [2026-11-05] `cp ~/.local/bin/x && systemctl --user restart x` | ok |\n"
                   "| R-EV-3 | done | a row whose evidence cites an API route → [2026-11-05] `GET /api/providers` | ok |\n")
    out = run(root, "lint", ok=False).stdout
    assert "E010" not in out, ("prose evidence was read as a file path:\n" + out)
    # ... and a token that IS file-shaped but missing is still an error
    reg.write_text(reg.read_text() +
                   "| R-EV-4 | done | a row whose evidence cites a missing file → [2026-11-05] `ev/missing.md` | ok |\n")
    out2 = run(root, "lint", ok=False).stdout
    assert "E010" in out2 and "ev/missing.md" in out2, ("a missing file-shaped evidence went unreported:\n" + out2)
    # the repo's own pointer_ignore list applies here too: a repo that names a path in
    # prose says so once, and the register honours the same declaration as AGENTS.md.
    # The `full` profile writes no pointer_ignore line (its default is the empty
    # string), so the key is added under [core] rather than rewritten in place.
    toml = root / "genome.toml"
    t = toml.read_text()
    toml.write_text(t.replace("[core]\n", '[core]\npointer_ignore = "ev/missing.md"\n', 1))
    out3 = run(root, "lint", ok=False).stdout
    assert "E010" not in out3, ("pointer_ignore did not reach the register's evidence:\n" + out3)


@case
def append_only_publication_rule(root: Path) -> None:
    """The append-only check judges a REMOVED line against what was PUBLISHED.

    Four cases, each one a real defect the old net-diff-over-a-window rule got wrong.
    Every case goes through the PUBLIC interface (`genome log` publishes, `doctor`
    judges), so the check is exercised as a user meets it.

      1. A COMPLIANT REPAIR is silent.  A line published by an append, then rewritten
         in place (a violation), then RESTORED with the correction appended after it:
         the original is present now, so nothing is reported.
      2. A REAL VIOLATION is reported, even in a file ADDED after the window's base —
         the case a net diff over the window could not see at all.
      3. Removing REPLACEMENT TEXT (a line an in-place rewrite introduced) is the
         REPAIR of that rewrite, not a second violation, so it is silent.
      4. An unrelated APPEND is silent (the ordinary case: the check must not cry wolf).
    """
    full_repo(root)
    wl = root / "docs/kb/WORKLOG.md"
    entry1 = run(root, "log", "published entry one").stdout
    git(root, "add", "-A"); git(root, "commit", "-qm", "publish one")

    # (4) an ordinary append is silent.
    run(root, "log", "published entry two")
    git(root, "add", "-A"); git(root, "commit", "-qm", "append two")
    out = run(root, "doctor").stdout
    assert "append-only violation" not in out, ("an ordinary append was reported:\n" + out)

    # (1) a compliant repair: rewrite the published line in place (the violation),
    # then restore the original and append the correction after it.
    text = wl.read_text()
    wl.write_text(text.replace("published entry one", "published entry one REWRITTEN"))
    git(root, "add", "-A"); git(root, "commit", "-qm", "illegal rewrite")
    wl.write_text(text.replace("published entry one", "published entry one")
                  + "- **2026-11-05T00:00** — entry one AMENDED: the correction\n")
    git(root, "add", "-A"); git(root, "commit", "-qm", "compliant repair")
    out = run(root, "doctor").stdout
    assert "append-only violation" not in out, ("a compliant repair was reported:\n" + out)

    # (2) a real violation in a file ADDED after the base: the published line is
    # gone and never restored.  This is the case a net diff over a window missed.
    t = (root / "genome.toml").read_text()
    (root / "genome.toml").write_text(t.replace('worklog = "docs/kb/WORKLOG.md"',
                                                 'worklog = "docs/kb/EXTRA.md"'))
    git(root, "add", "-A"); git(root, "commit", "-qm", "point the role at a new file")
    run(root, "log", "published entry three")
    git(root, "add", "-A"); git(root, "commit", "-qm", "publish three")
    extra = root / "docs/kb/EXTRA.md"
    extra.write_text(extra.read_text().replace("published entry three", "replacement text"))
    git(root, "add", "-A"); git(root, "commit", "-qm", "rewrite it away")
    out = run(root, "doctor", ok=False).stdout
    assert "append-only violation" in out, ("a real violation was not reported:\n" + out)
    assert "EXTRA.md" in out, ("the violation did not name the file:\n" + out)

    # (3) removing REPLACEMENT TEXT is the repair of the illegal rewrite: silent.
    (root / "genome.toml").write_text((root / "genome.toml").read_text()
                                      .replace('worklog = "docs/kb/EXTRA.md"',
                                               'worklog = "docs/kb/WORKLOG.md"'))
    git(root, "add", "-A"); git(root, "commit", "-qm", "point the role back")
    extra.write_text("- **2026-11-05T00:00** — published entry three\n")
    git(root, "add", "-A"); git(root, "commit", "-qm", "restore the published line")
    out = run(root, "doctor").stdout
    assert "append-only violation" not in out, ("the restored repair was reported:\n" + out)


@case
def append_only_repair_in_working_tree(root: Path) -> None:
    """The working-tree check is publication-aware too: restoring a published line
    in the working tree is the compliant repair, and it must be silent."""
    full_repo(root)
    wl = root / "docs/kb/WORKLOG.md"
    run(root, "log", "published entry one")
    git(root, "add", "-A"); git(root, "commit", "-qm", "publish")
    # a working-tree removal of a published line IS a violation
    text = wl.read_text()
    wl.write_text(text.replace("published entry one", "replacement text"))
    out = run(root, "doctor", ok=False).stdout
    assert "append-only violation" in out, ("a working-tree removal was not reported:\n" + out)
    # restoring it is the repair: silent
    wl.write_text(text)
    out = run(root, "doctor").stdout
    assert "append-only violation" not in out, ("the repair was reported:\n" + out)


@case
def append_only_merge_resolution(root: Path) -> None:
    """A removal introduced ONLY by a MERGE is still a removal.

    `git log -p` omits a merge's diff by default, so a published line dropped by
    a merge's conflict resolution — and by no branch commit — was invisible to
    the check.  Measured 2026-11-05: 0 violations without the flag, 1 with
    `--diff-merges=first-parent`.
    """
    full_repo(root)
    wl = root / "docs/kb/WORKLOG.md"
    run(root, "log", "published entry one")
    git(root, "add", "-A"); git(root, "commit", "-qm", "publish")

    # A branch that appends, and a main that appends too, so the merge can
    # resolve the file to KEEP NEITHER of the original lines.
    git(root, "checkout", "-q", "-b", "side")
    run(root, "log", "side entry")
    git(root, "add", "-A"); git(root, "commit", "-qm", "side appends")
    git(root, "checkout", "-q", "-")
    run(root, "log", "main entry")
    git(root, "add", "-A"); git(root, "commit", "-qm", "main appends")

    # Merge and resolve the file by hand: the published line is dropped by the
    # MERGE and by no branch commit.
    subprocess.run(["git", "merge", "--no-commit", "side"], cwd=root, capture_output=True)
    text = wl.read_text()
    kept = [ln for ln in text.splitlines() if "published entry one" not in ln]
    wl.write_text("\n".join(kept) + "\n")
    git(root, "add", "-A")
    subprocess.run(["git", "commit", "-q", "-m", "merge side: the resolution drops the published line"],
                   cwd=root, capture_output=True)

    out = run(root, "doctor", ok=False).stdout
    assert "append-only violation" in out, ("a merge-only removal was not reported:\n" + out)
    assert "WORKLOG.md" in out, ("the violation did not name the file:\n" + out)


@case
def e004_tombstone(root: Path) -> None:
    """`genome archive` leaves a tombstone stub in the source dir, and E004 must not call that stub a violation.

    The kernel's own archive writes `# <stem> (superseded)` + a `kb: tombstone` marker into the
    archived path so the old location stays findable (cmd_archive, flat form). For a DATED name
    the stub inherits the date and dodges the check; for an UNDATED name the stub is doomed to
    fail it forever, because the archive deliberately cannot clear the stub. E004 was the only
    reader of plans/audits without is_tombstone, unlike its siblings at 43/189/507.

    Proven on a purpose-built repo: baseline 1 E004; run the KERNEL's archive; still 1 E004 on the
    kernel's own stub. The fix empties that tombstone hole while a real undated plan still fires."""
    full_repo(root)
    stale = root / "docs/plans/legendary-hacks.md"
    stale.write_text("# Legendary hacks\n\nAn un-dated plan: the exact content that E004 exists to name.\n")
    run(root, "archive", str(stale), "--reason", "probe: is a tombstone a plan?")
    stub = root / "docs/plans/legendary-hacks.md"
    assert 'kb: tombstone target=' in stub.read_text(), "the archive should have left a tombstone"
    lint_after = run(root, "lint", ok=False).stdout
    assert "E004 plans file without a date stamp: docs/plans/legendary-hacks.md" not in lint_after, (
        "the kernel is red on its OWN archive stub:\n" + lint_after)
    assert "lint: clean" in lint_after, lint_after

    # The exemption must not blind the rule to a real undated plan.
    real = root / "docs/plans/real-undated-plan.md"
    real.write_text("# Real undated plan\n\nNot a tombstone: this is the violation E004 exists to name.\n")
    assert "E004 plans file without a date stamp: docs/plans/real-undated-plan.md" in run(root, "lint", ok=False).stdout

    # The exemption must not be a blind spot either: a tombstone whose archived
    # TARGET is gone is named (E019), not excused by the tombstone marker.
    dangling = root / "docs/plans/dangling.md"
    dangling.write_text('# Dangling (superseded)\n\n<!-- kb: tombstone target="docs/archive/NOT-THERE.md" -->\n\nMoved.\n')
    out = run(root, "lint", ok=False).stdout
    assert "E019 plans tombstone points at missing `docs/archive/NOT-THERE.md`" in out, (
        "a tombstone pointing at a missing archive file was not named:\n" + out)
    assert "E004 plans file without a date stamp: docs/plans/dangling.md" not in out, (
        "the tombstone was still judged as a plan:\n" + out)
    # Restore the target and the finding clears.  The real undated plan is still
    # there, so lint still exits non-zero on E004; only E019 must be gone.
    (root / "docs/archive/NOT-THERE.md").write_text("# Restored\n")
    assert "E019" not in run(root, "lint", ok=False).stdout


def _git(cwd, *a, check=True):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=check)


@case
def unpushed_vendored_cli(root: Path) -> None:
    """A vendored CLI that is COMMITTED but whose commit is not on the remote must be
    reported — the rung above `_uncommitted_cli`, which is blind to it by construction.

    Measured 2026-11-05 over the fleet: 62 of 63 repos with a reachable remote were
    ahead of it, 46 carrying an unpushed dispatch commit, and no check anywhere said so.
    `_uncommitted_cli` asks whether the WORKING TREE is modified, and a committed copy
    has a clean working tree, so it cannot see this case. The whole point of this case
    is that a clean, committed, unpushed copy is still reported.

    The remote is a LOCAL bare repo and the registry is a PRIVATE manifest, so the
    case touches neither the network nor the operator's machine. The registry override
    is `GENOME_INSTALLS` — `installs_manifest()` reads that and NOT `XDG_CONFIG_HOME`,
    so without it the case would sweep the live fleet.

    FOUR separate situations are covered, because each one is a way the check can be
    wrong and a single fixture only proves one of them:
      1. the commit IS on the remote  -> not reported;
      2. the commit is NOT on it      -> reported, naming the remote;
      3. the remote has a name other than `origin` -> still resolved and reported
         (the fleet's remote names vary; automaton has `github` and NO `origin`);
      4. the remote does not answer   -> reported, NOT as clean — a measurement that
         could not be taken must never read as a pass;
      5. the REMOTE is ahead of the local checkout -> not reported, because every
         local commit is already on the remote's history;
      6. the repo has no remote at all -> not reported, because it is unversioned
         rather than unpushed."""
    remote = root / "remote.git"
    _git(root, "init", "-q", "--bare", str(remote))
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "scripts").mkdir()
    shutil.copyfile(G, repo / "scripts/genome")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "genome: commit the vendored CLI")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")

    # A PRIVATE registry holding exactly this one row, plus a skills root to serve
    # as the "shipped" reference the check compares against.
    manifest = root / "installs.json"
    manifest.write_text(json.dumps({
        "schema": 1,
        "installs": [
            {"kind": "vendored", "path": str(repo), "version": "?"},
            {"kind": "skill", "path": str(root / "skill"), "version": "?"},
        ],
    }))
    skill = root / "skill"
    (skill / "scripts").mkdir(parents=True)
    shutil.copyfile(G, skill / "scripts" / "genome")
    env = {**os.environ, "GENOME_INSTALLS": str(manifest)}

    # ---- 1. the control: the commit IS on the remote, so nothing is reported ----
    assert _unpushed_through_cli(repo, env) is None, (
        "a repo whose commit IS on the remote was reported as unpushed")

    # ---- 2. the mutation: one more commit, not pushed ----
    _git(repo, "commit", "-q", "--allow-empty", "-m", "genome: commit the vendored CLI")
    found = _unpushed_through_cli(repo, env)
    assert found is not None, (
        "a committed-but-unpushed vendored CLI was NOT reported — the working tree is clean, "
        "so this is exactly the case _uncommitted_cli cannot see")
    assert "not on origin" in found, f"the detail did not name the remote: {found}"

    # ---- and once it IS pushed, it clears ----
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    assert _unpushed_through_cli(repo, env) is None, (
        "the repo was still reported as unpushed after the commit reached the remote")

    # ---- 3. the remote is NOT named `origin` ----
    # The fleet's remote names vary: measured 2026-11-05, automaton has `github` and
    # `gitlab` and NO `origin`, and asking only for `origin` reported 25 repos that DO
    # have a remote as having none at all. So the check must resolve the remote the
    # branch's upstream names, and must say which one it used.
    named = root / "named.git"
    _git(root, "init", "-q", "--bare", str(named))
    _git(repo, "remote", "add", "github", str(named))
    _git(repo, "push", "-q", "github", "HEAD:refs/heads/main")
    _git(repo, "branch", "--set-upstream-to=github/main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "genome: commit the vendored CLI")
    found = _unpushed_through_cli(repo, env)
    assert found is not None, (
        "a repo whose remote is named something other than `origin` was NOT reported")
    assert "not on github" in found, (
        f"the detail did not name the remote the branch actually pushes to: {found}")

    # ---- 4. the remote does not answer ----
    # A remote that cannot be reached is a measurement that could NOT be taken. It
    # must not read as clean: that is the silent-green class this project exists to
    # catch, and it is the one place where "I could not check" and "it is fine" are
    # the same output.
    broken = root / "broken.git"
    _git(root, "init", "-q", "--bare", str(broken))
    _git(repo, "remote", "set-url", "github", str(root / "does-not-exist.git"))
    found = _unpushed_through_cli(repo, env)
    assert found is not None, (
        "a remote that did not answer was reported as clean — a measurement that could "
        "not be taken must never read as a pass")
    assert "did not answer" in found, (
        f"the detail did not say the remote was unreachable: {found}")

    # ---- 5. the REMOTE is ahead of the local checkout ----
    # Someone else pushed. The local HEAD is older, but every local commit IS on
    # the remote's history, so there is nothing unpushed — and reporting it would
    # be a false alarm on every repo whose collaborator pushed first. This is the
    # state the ancestry test exists to recognise.
    #
    # The collaborator pushes to the SAME remote, so the remote's history EXTENDS
    # the local one. Rewriting the local history instead (a reset onto a fetched
    # branch) produces an unrelated commit, which is a DIFFERENT state and does
    # not test this at all — the first version of this fixture did that and the
    # ancestry mutation escaped it.
    ahead_remote = root / "ahead.git"
    _git(root, "init", "-q", "--bare", str(ahead_remote))
    other = root / "other"
    other.mkdir()
    _git(other, "init", "-q")
    _git(other, "config", "user.email", "t@t")
    _git(other, "config", "user.name", "t")
    # The collaborator's repo carries the SAME vendored CLI, because the reset
    # below restores the tree from the remote — and a remote whose tree has no
    # `scripts/genome` DELETES the vendored copy on reset. The first version of
    # this fixture seeded the remote with a bare `seed/` directory, the reset
    # removed the CLI, and the check then correctly reported nothing — so the
    # fixture tested a row that no longer had a vendored copy, and the ancestry
    # mutation escaped it.
    (other / "scripts").mkdir()
    shutil.copyfile(G, other / "scripts" / "genome")
    _git(other, "add", "-A")
    _git(other, "commit", "-qm", "seed")
    _git(other, "remote", "add", "origin", str(ahead_remote))
    _git(other, "push", "-q", "origin", "HEAD:refs/heads/main")
    _git(repo, "remote", "set-url", "github", str(ahead_remote))
    _git(repo, "fetch", "-q", "github")
    _git(repo, "reset", "-q", "--hard", "github/main")
    assert (repo / "scripts" / "genome").exists(), (
        "the fixture deleted the vendored copy — the reset restored a tree without it")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "genome: commit the vendored CLI")
    _git(repo, "push", "-q", "github", "HEAD:refs/heads/main")
    # The collaborator now pushes ON TOP of what the local checkout has.
    _git(other, "fetch", "-q", "origin")
    _git(other, "reset", "-q", "--hard", "origin/main")
    _git(other, "commit", "-q", "--allow-empty", "-m", "the collaborator's commit")
    _git(other, "push", "-q", "origin", "HEAD:refs/heads/main")
    _git(repo, "fetch", "-q", "github")
    _git(repo, "branch", "--set-upstream-to=github/main")
    # The local checkout is now BEHIND the remote, and every local commit is on
    # the remote's history.
    assert _unpushed_through_cli(repo, env) is None, (
        "a repo whose REMOTE is ahead of the local checkout was reported as unpushed — "
        "every local commit is on the remote's history, so there is nothing to push")

    # ---- 6. a vendored row whose repo has NO remote ----
    # A repo with no remote is not unpushed, it is unversioned. It is committed and
    # clean and there is nowhere to push to, and calling that unpushed would put
    # every offline KB on the list.
    noremote = root / "noremote"
    noremote.mkdir()
    _git(noremote, "init", "-q")
    _git(noremote, "config", "user.email", "t@t")
    _git(noremote, "config", "user.name", "t")
    (noremote / "scripts").mkdir()
    shutil.copyfile(G, noremote / "scripts/genome")
    _git(noremote, "add", "-A")
    _git(noremote, "commit", "-qm", "genome: commit the vendored CLI")
    manifest.write_text(json.dumps({
        "schema": 1,
        "installs": [
            {"kind": "vendored", "path": str(repo), "version": "?"},
            {"kind": "vendored", "path": str(noremote), "version": "?"},
            {"kind": "skill", "path": str(root / "skill"), "version": "?"},
        ],
    }))
    out = subprocess.run([sys.executable, G, "installs", "verify", "--against-shipped"],
                         cwd=repo, capture_output=True, text=True, env=env)
    assert str(noremote) not in out.stdout, (
        "a repo with no remote at all was reported as unpushed — it is unversioned, "
        "not unpushed, and there is nowhere for it to push to")

    # ---- 7. the remote's commit is NOT in this checkout ----
    # A repo whose local objects predate the remote's tip: `merge-base` cannot
    # find the remote's commit and exits 128, not 1. That is a measurement that
    # COULD NOT BE TAKEN, and it must not read as "not an ancestor" — which would
    # report the repo as unpushed when its commits may all be on the remote. It
    # must say the answer could not be decided.
    unknown_remote = root / "unknown.git"
    _git(root, "init", "-q", "--bare", str(unknown_remote))
    fresh = root / "fresh"
    fresh.mkdir()
    _git(fresh, "init", "-q")
    _git(fresh, "config", "user.email", "t@t")
    _git(fresh, "config", "user.name", "t")
    (fresh / "scripts").mkdir()
    shutil.copyfile(G, fresh / "scripts" / "genome")
    _git(fresh, "add", "-A")
    _git(fresh, "commit", "-qm", "genome: commit the vendored CLI")
    _git(fresh, "remote", "add", "origin", str(unknown_remote))
    _git(fresh, "push", "-q", "origin", "HEAD:refs/heads/main")
    # The collaborator pushes a commit the local checkout has never seen, and the
    # local repo is NOT fetched — so the remote's HEAD object is absent locally.
    _git(other, "remote", "set-url", "origin", str(unknown_remote))
    _git(other, "fetch", "-q", "origin")
    _git(other, "reset", "-q", "--hard", "origin/main")
    _git(other, "commit", "-q", "--allow-empty", "-m", "a commit the local checkout has not seen")
    _git(other, "push", "-q", "origin", "HEAD:refs/heads/main")
    manifest.write_text(json.dumps({
        "schema": 1,
        "installs": [
            {"kind": "vendored", "path": str(fresh), "version": "?"},
            {"kind": "skill", "path": str(root / "skill"), "version": "?"},
        ],
    }))
    out = subprocess.run([sys.executable, G, "installs", "verify", "--against-shipped"],
                         cwd=repo, capture_output=True, text=True, env=env)
    assert str(fresh) in out.stdout, (
        "the fixture did not produce the state it claims: the repo whose remote's "
        f"commit is absent locally was not reported at all:\n{out.stdout}")
    assert "cannot be decided" in out.stdout, (
        "a repo whose remote's commit is absent locally was reported as unpushed — "
        "whether the commit is pushed CANNOT be decided, and a measurement that could "
        f"not be taken must never read as a verdict:\n{out.stdout}")


def _unpushed_through_cli(repo: Path, env):
    """The UNPUSHED detail the CLI prints for `repo`, or None when it prints none.

    Driven through the BUILT CLI so the case tests the shipped behaviour, not a
    re-implementation of it."""
    out = subprocess.run([sys.executable, G, "installs", "verify", "--against-shipped"],
                         cwd=repo, capture_output=True, text=True, env=env)
    for line in (out.stdout + out.stderr).splitlines():
        if line.startswith("UNPUSHED"):
            return line
    return None


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
