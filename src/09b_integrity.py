# ---------------------------------------------------------------- integrity

APP_KINDS = {
    # The manifest that identifies a toolchain, and the command that checks it. A repo
    # declares its toolchain by NAME and genome knows the rest, so "is this Rust
    # project's build broken" is one question every Rust repo answers the same way,
    # rather than one shell string each operator hand-writes. `probe` is what proves
    # the tool exists: `cargo --version` failing means the check cannot run, which is
    # an I, not an E — the repo is fine and the machine is not.
    "python": {"manifest": ["pyproject.toml", "setup.py", "requirements.txt", "setup.cfg"],
               "probe": ["python3", "--version"],
               "build": "python3 -m compileall -q .",
               "test": "python3 -m pytest -q",
               "lint": "python3 -m ruff check .",
               "fmt": "python3 -m ruff format --check .",
               "doc": "python3 -m pydoc -w ."},
    "rust": {"manifest": ["Cargo.toml"], "probe": ["cargo", "--version"],
             "build": "cargo build --workspace --locked",
             "test": "cargo test --workspace",
             "lint": "cargo clippy --workspace -- -D warnings",
             "fmt": "cargo fmt --check"},
    "node": {"manifest": ["package.json"], "probe": ["node", "--version"],
             "build": "npm run build", "test": "npm test",
             "lint": "npx eslint .", "doc": "npx typedoc"},
    "typescript": {"manifest": ["tsconfig.json"], "probe": ["node", "--version"],
                   # NOT `npx tsc --version`: with no node_modules, npx resolves the name from the
                   # registry and prints "This is not the tsc command you are looking for",
                   # which exits 0 and looks like a working toolchain. Measured 2026-11-03. The
                   # honest probe is node itself; whether tsc is a local dependency is a question
                   # `npm run build` answers when it actually runs.
                   "build": "npx tsc --noEmit", "test": "npm test",
                   "lint": "npx eslint .", "doc": "npx typedoc"},
    "go": {"manifest": ["go.mod"], "probe": ["go", "version"],
           "build": "go build ./...", "test": "go test ./...", "lint": "go vet ./...",
           "fmt": "test -z \"$(gofmt -l .)\""},
    "java": {"manifest": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
             # settings.gradle(.kts) as well as build.gradle: a multi-module Gradle project
             # declares its modules in settings and can carry NO root build script at all, so
             # the build-file-only list left exactly the shape a large project takes
             # unrecognised. Measured 2026-11-03 — a repo with settings.gradle + src/
             # inferred no toolchain and answered "clean", which is the silence that reads as
             # a green build.
             #
             # The default build prefers the WRAPPER (`./gradlew`) over a system `gradle` or
             # `mvn`: it pins the toolchain version, which is why a repo vendors one, and a
             # wrapper-less Gradle project is unusual enough that `./gradlew` failing is a
             # fact worth an E651 rather than a silent fallback. So the Maven command is the
             # default `test` only, not `build`, and a repo choosing either writes `[app]`.
             "probe": ["java", "-version"],
             "build": "./gradlew build -x test", "test": "mvn -q test"},
    "shell": {"manifest": [], "probe": ["bash", "--version"], "lint": "bash -n"},
}

APP_PHASES = ("build", "test", "typecheck", "lint", "fmt", "doc")  # `fmt` and `doc` are probes, not gates


def app_kind(cfg: Cfg) -> str | None:
    """The toolchain this repo declares, or the one its manifest reveals.

    The declaration wins. `app.toolchain = "rust"` in a repo that also has a
    package.json is a statement about what this project IS, and a nested JS tool in a
    Rust workspace must not reclassify the repo.

    Otherwise the manifest decides, and only one may match: two manifests is a
    monorepo question the operator answers by writing the key, because a guess here
    would run the wrong toolchain's checks and report a clean build for a repo that
    was never compiled.
    """
    declared = cfg.get("app", "toolchain")
    if declared:
        return str(declared)
    hits = [k for k, v in APP_KINDS.items() if any((cfg.root / m).exists() for m in v["manifest"])]
    # `python` and `typescript` both recognise a nested package.json/tsconfig, which is
    # how a Python CLI with a bundled frontend reads; python is the conservative answer
    # because its checks are the ones that cannot silently pass on the other language.
    order = ["rust", "go", "java", "typescript", "node", "python", "shell"]
    hits.sort(key=order.index)
    return hits[0] if hits else None


def _run_ok(cmd, cwd: Path) -> tuple[bool, str]:
    """(ok, tail) for one integrity command. Never raises: an absent binary is a fact."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=int(os.environ.get("GENOME_APP_TIMEOUT", "300")))
    except (OSError, subprocess.TimeoutExpired) as e:
        return (False, str(e)[:200])
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    return (r.returncode == 0, "\n       ".join(t for t in tail if t.strip()))


def lint_app(cfg: Cfg) -> list[str]:
    """E651..: application/system integrity — the app builds, tests, lints and installs.

    This is the check the three absorbed skills each needed and none of them had.
    `doc` validated prose, `install-script-creator` generated an installer, and
    `workspace-lint` checked the tree. None of them could answer *does this thing
    still build*, because a skill is not a build.

    Genome answers it from the repo's own declaration, in whatever language the repo
    is written, so it is the same question with the same answer everywhere:

    - **E651** the declared phase fails. `cargo test` failing is a defect in the code,
      and it is the one integrity fact that must stop a commit — everything else here
      is about the tree, this is about the program.
    - **E652** the `entry` or `manifest` named in `genome.toml` does not exist. A
      declaration pointing at nothing is worse than no declaration: it reads as
      checked and is not. (The install script has its own checks — E657/E658/W655.)
    - **I651** the toolchain is undeclared AND unmanifested, or a probe cannot run.
      A repo with no toolchain (a KB, a notes repo) is not broken; a Rust repo on a
      machine with no cargo is a fact about the machine. Neither is an error.

    Silence is the default. A repo that declares nothing AND has no manifest gets
    nothing at all: a knowledge base and a notes repo have no build, and that is not a
    finding. The one info worth printing is a toolchain genome found but could not run.
    """
    out: list[str] = []
    kind = app_kind(cfg)
    spec = APP_KINDS.get(kind, {}) if kind else {}
    declared_cmds = {p: cfg.get("app", p) for p in APP_PHASES if cfg.get("app", p)}

    # The probe first: a toolchain that cannot run on this machine is the ONE info that
    # is worth a line, and it is worth one because the alternative is silence about a
    # check that never ran. Measured 2026-11-03, an earlier "no toolchain declared and
    # none inferred" line broke every `assert "lint: clean"` in the suite — a KB
    # legitimately has no build, so the line fired on every healthy notes repo and made
    # that assertion unusable. An info that is not informational is a defect.
    probe = cfg.get("app", "install_probe") or (spec.get("probe") if spec else None)
    if probe:
        pcmd = probe if isinstance(probe, str) else " ".join(probe)
        ok, tail = _run_ok(pcmd, cfg.root)
        if not ok:
            return [f"I651 `{pcmd}` did not run — the {kind or 'declared'} toolchain is absent or "
                    f"broken on this machine, so its build/test phases were skipped (a fact about "
                    f"the environment, not the repo)"]
    elif not kind and not declared_cmds:
        return []

    # a repo with a toolchain and no declared phases still gets one line: it names what
    # was checked, so the estate view can answer "what is this repo" from the lint.
    if kind:
        out.append(f"I651 app integrity: toolchain {kind}, "
                   + (f"{len(declared_cmds)} declared phase(s)" if declared_cmds
                      else "no phase declared — [app] build/test/lint would run its defaults"))

    # each declared phase runs, and only a failure is an E
    for phase in APP_PHASES:
        cmd = cfg.get("app", phase)
        if cmd is None:
            continue
        if isinstance(cmd, str):
            cmds = [cmd]
        elif isinstance(cmd, list):
            cmds = [c for c in cmd if isinstance(c, str) and c.strip()]
        else:
            out.append(f"E652 [app] {phase} is neither a string nor a list of strings")
            continue
        for c in cmds:
            ok, tail = _run_ok(c, cfg.root)
            if not ok:
                label = phase if phase not in ("fmt", "doc") else f"{phase} (advisory phase)"
                if phase in ("fmt", "doc"):
                    # a formatter and a doc build are advisory: failing them is a W at
                    # most, because the app still builds and runs without prettier.
                    out.append(f"W654 [app] {label} `{c}` failed:\n       {tail}")
                else:
                    out.append(f"E651 [app] {label} `{c}` failed:\n       {tail}")

    # declared paths that must exist. The install script is NOT here: `lint_install_script`
    # owns that question whole (existence, executable bit, verification step), and a
    # second report for one missing file reads as two broken things instead of one.
    for key, label in (("entry", "entry"), ("manifest", "manifest")):
        v = cfg.get("app", key)
        if not v:
            continue
        paths = [v] if isinstance(v, str) else [p for p in v if isinstance(p, str)]
        for p in paths:
            if not (cfg.root / p).exists():
                out.append(f"E652 [app] {label} `{p}` does not exist — a declaration pointing at "
                           f"nothing reads as checked and is not")
    return out


def lint_docs_required(cfg: Cfg) -> list[str]:
    """E653: a document genome.toml declares, per kb, that this repo must carry.

    A project-grade repo owes its readers certain documents, and which ones is a
    property of the project, not of genome: a CLI owes a README and an ARCHITECTURE,
    a library owes API docs, a skill owes SKILL.md. So the repo writes the list in
    `[docs] required` and `genome lint` is what enforces it — the same way E306
    enforces the tree, one declaration and one gate.

    An empty or near-empty required document is the half that matters most and is the
    half a naive existence check misses: a README.md holding only a title satisfies
    "exists" and tells a reader nothing. So a required doc must carry real content,
    which is measured here rather than assumed.

    - **E653** a required document is absent, or holds no content beyond its heading.
    - **W653** a required document is shorter than the band its class expects — thin,
      which is a judgement the operator makes, not a broken gate.
    - **E654** a required section (`[docs] sections`) is missing from a required doc.
    - **W651** a required doc has no table of contents yet is long enough to need one.
    """
    out: list[str] = []
    req = cfg.get("docs", "required", [])
    if not req:
        return out
    # a required doc is either "every doc named" or a per-file map of {path = "class"};
    # a plain list names the paths, and a path may carry its class after a colon, so
    # the common case stays one line: required = ["README.md", "AGENTS.md", "docs/ARCHITECTURE.md"]
    entries: list[tuple[str, str]] = []
    for item in req:
        if isinstance(item, str):
            path, _, cls = item.partition(":")
            entries.append((path.strip(), cls.strip()))
        elif isinstance(item, dict):
            entries += [(str(p), str(c)) for p, c in item.items()]
    need_sections = cfg.get("docs", "sections", {})
    max_lines = int(cfg.get("docs", "max_lines", 0) or 0)
    # A repo that wants the thin-doc WARNING at all opts in by naming a minimum length.
    # Measured 2026-11-03: with a hardcoded band, a fresh `genome init` tree whose
    # README.md is a three-line stub was reported as thin, on every new repo, on its
    # first lint. A warning that fires on the tool's own scaffolding is a warning the
    # reader learns to skip, which is the same failure as having no check.
    min_lines = int(cfg.get("docs", "min_lines", 0) or 0)
    for path, cls in entries:
        p = cfg.root / path
        if not p.exists():
            out.append(f"E653 {path} is declared required by [docs] and does not exist")
            continue
        text = read(p)
        # a heading and nothing else is an absent document that happens to exist
        body = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        if not body:
            out.append(f"E653 {path} is declared required and holds no content beyond its heading")
            continue
        if min_lines and len(text.splitlines()) < min_lines:
            out.append(f"W653 {path} is declared required and is {len(text.splitlines())} line(s) — "
                       f"under [docs] min_lines = {min_lines}, a required doc this thin tells a "
                       f"reader nothing")
        if need_sections and path in need_sections:
            for sec in need_sections[path] if isinstance(need_sections[path], list) else [need_sections[path]]:
                if not re.search(rf"^#+\s+.*{re.escape(str(sec))}", text, re.M):
                    out.append(f"E654 {path} is missing the required section `{sec}`")
        if max_lines and len(text.splitlines()) > max_lines and not re.search(r"^##+ +Contents", text, re.M):
            out.append(f"W651 {path} is {len(text.splitlines())} lines with no table of contents "
                       f"(over [docs] max_lines = {max_lines})")
    return out


def lint_dirs_declared(cfg: Cfg) -> list[str]:
    """E655: a directory genome.toml declares must exist, and must not be empty.

    The inverse of E306, which asks "a directory that exists holds the file it must".
    This asks "a directory I declared is there at all" — and the second half is the one
    that actually bites, because a declared directory that exists but holds nothing is
    indistinguishable at a glance from a real one: `docs/audit/` with no reports in it
    either means the audit never ran or means its reports were lost.

    - **E655** a declared directory (`ops.dir_globs`) does not exist.
    - **E656** a declared directory that is NOT a genome role's home exists and is empty.
      An empty directory is invisible to git, so it is also invisible to every check
      that reads the index — which is why this one walks the filesystem rather than
      `git ls-files`. A role dir is exempt, because `genome init` creates those empty and
      they fill as the work happens.
    """
    out: list[str] = []
    globs = cfg.get("ops", "dir_globs", [])
    if not globs:
        return out
    # A genome role dir is created EMPTY by `genome init` and fills as the work happens,
    # so its emptiness is the project's lifecycle, not a defect: `docs/plans/` holds
    # nothing on a new repo until the first plan. Measured 2026-11-03, checking every
    # declared dir for emptiness reported E656 on `docs/audit` of a fresh tree — because
    # `audits` is a DEFAULT role pointing there — which made the check fire on the tool's
    # own scaffolding. So emptiness is scoped to declared dirs that are NOT a role's
    # mapped home: a role dir's emptiness is its lifecycle, a stranger dir's emptiness is
    # a directory git does not track and no reader can see.
    role_homes = {cfg.rel(cfg.path(r)).rstrip("/") for r in cfg.paths}
    for pat in globs:
        pat = str(pat)
        for d in sorted(p for p in cfg.root.glob(pat.rstrip("/")) if p.is_dir() and not p.name.startswith((".", "__"))):
            rel = cfg.rel(d)
            if rel not in role_homes and not any(d.iterdir()):
                out.append(f"E656 {rel}/ is declared by ops.dir_globs and is empty — git does not "
                           f"track empty directories, so this one exists on this machine only")
        # a declared dir that matches NOTHING is the more common failure: a typo, or a
        # dir an emitter was supposed to create. `genome init` creates the roles; a repo
        # that renames one by hand and forgets the key gets a silent no-match here.
        matches = [p for p in cfg.root.glob(pat.rstrip("/")) if p.is_dir() and not p.name.startswith((".", "__"))]
        if not matches and not (cfg.root / pat.rstrip("/")).exists():
            out.append(f"E655 {pat} is declared by ops.dir_globs and does not exist")
    return out


def lint_install_script(cfg: Cfg) -> list[str]:
    """E657: a project-grade repo's installer, when the repo declares it has one.

    A distribution question, not a code question: a repo that ships a one-line install
    must be able to install, and an installer that cannot be found is a broken release.
    The repo declares where its installer lives (`app.install_script`), or genome
    infers it from the conventional names, and then enforces the two things that make
    an installer real:

    - **E657** the declared or inferred install script does not exist.
    - **E658** the install script is not executable.
    - **W655** the install script does not name a verification step. An installer with
      no `verify` is one that reports success when the install half-happened, which is
      the failure mode `install-script-creator` wrote `verify_install.sh` to catch.

    Silence by default: a knowledge base and a notes repo have no installer, and this
    check asks nothing of them unless they declare one.
    """
    out: list[str] = []
    declared = cfg.get("app", "install_script")
    # inference is deliberately NARROW: only the name this project's own installer uses.
    # A repo that vendors a third-party install.sh is not shipping that installer, and
    # flagging it would be a false positive on every vendored dependency.
    candidates = [declared] if declared else []
    if not candidates:
        for name in ("install.sh", "install.ps1"):
            if (cfg.root / name).exists():
                candidates.append(name)
    if not candidates:
        return out
    for name in candidates:
        p = cfg.root / name
        if not p.exists():
            out.append(f"E657 install script `{name}` is declared by [app] and does not exist")
            continue
        if name.endswith(".sh"):
            if not os.access(p, os.X_OK):
                out.append(f"E658 {name} is not executable — `chmod +x {name}`")
            text = read(p)
            if not re.search(r"\b(verify|check|--version|--help)\b", text):
                out.append(f"W655 {name} has no verification step — an installer that reports success "
                           f"when the install half-happened is the failure mode verify_install.sh catches")
    return out


CHECKS["integrity"] = lambda cfg: lint_app(cfg) + lint_docs_required(cfg) + lint_dirs_declared(cfg) \
    + lint_install_script(cfg)
