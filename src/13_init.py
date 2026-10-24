# ---------------------------------------------------------------- init

def scaffold_roles(cfg: Cfg) -> list[str]:
    """Create each enabled role that is missing, at its mapped path. Never touches an existing file,
    a native:/overlay: role, or a role the repo's own tooling generates."""
    tpl = {"register": REGISTER_TPL, "entry": ENTRY_TPL, "state": STATE_TPL, "runbook": RUNBOOK_TPL,
           "ledger": CLOSED_TPL, "asks": ASKS_TPL, "records_index": RECORDS_TPL, "hypotheses": HYP_TPL,
           "quarantine": QUAR_TPL, "prereg": PREREG_TPL, "ownership_map": MAP_TPL, "feed": FEED_TPL}
    dirs = ("plans", "audits", "decisions", "regressions", "workflows", "archive")
    made = []
    for m in sorted(cfg.modules):
        for role in MODULE_ROLES[m]:
            if cfg.form(role)[0] != "file" or cfg.path(role).exists():
                continue
            p = cfg.path(role)
            if role == "worklog":
                if worklog_numbered(cfg):
                    p.mkdir(parents=True)
                else:
                    atomic_write(p, WORKLOG_TPL)
            elif role == "evidence":
                atomic_write(p / "README.md", EVIDENCE_TPL)
            elif role in dirs:
                p.mkdir(parents=True)
                if role == "archive" and cfg.get("core", "archive_form", "flat") == "flat":
                    atomic_write(p / "INDEX.md", "| date | original | reason |\n|---|---|---|\n")
            elif role in tpl:
                atomic_write(p, tpl[role])
            else:
                continue
            made.append(cfg.paths[role])
    return made


def ignore_runtime(root: Path) -> list[str]:
    """Locks, temp files, recon tokens and read marks are machine state: never committed."""
    gi = root / ".gitignore"
    have = read(gi).splitlines()
    want = [g for g in ("*.genome-lock", "*.genome-tmp", ".genome/") if g not in have]
    if not want:
        return []
    with open(gi, "a") as f:
        f.write("\n# genome runtime state (locks, temp files, recon tokens, read marks)\n" + "\n".join(want) + "\n")
    return [f".gitignore (+{', '.join(want)})"]


def cmd_init(args) -> None:
    root = Path.cwd().resolve()
    chain = bp_chain([s for a in args.blueprint or [] for s in a.split(",") if s], root)
    if chain and (probs := bp_problems(chain)):
        die("blueprint declaration:\n  " + "\n  ".join(probs))
    if (root / "genome.toml").exists() and not args.force:  # adoption: the map is hand-written, fill its gaps
        cfg = find_cfg(root)
        if cfg.root != root:
            die(f"run init at the project root ({cfg.root})")
        if chain:
            bp_preflight(cfg, chain)
        made = scaffold_roles(cfg) + ignore_runtime(root)
        if chain:
            made += bp_apply(root, chain)
        print(f"genome init: genome.toml kept; {len(made)} change(s): missing roles at their mapped paths, runtime ignores")
        for m in made:
            print(f"  + {m}")
        print("next: `genome lint --advisory`, then triage (references/adoption.md)")
        return
    mods = PROFILES[args.profile] if args.profile else ["core", *[m for m in (args.modules or "").split(",") if m]]
    mods = [m for m in MODULES if m in set(mods) | set(bp_modules(chain)) | {"core"}]
    made, kept = [], []

    def write(rel: str, body: str) -> None:
        p = root / rel
        if p.exists():
            kept.append(rel)
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        made.append(rel)

    gate = next((g for f, g in (("Cargo.toml", "cargo test --locked"), ("pyproject.toml", "pytest -q"),
                                ("package.json", "npm test"), ("go.mod", "go test ./...")) if (root / f).is_file()), "")
    write("genome.toml", genome_toml(mods, gate) + (f'\n[card]\nprivacy = "{bp_privacy(chain)}"\n' if bp_privacy(chain) else ""))
    write("AGENTS.md", agents_tpl(mods, gate))
    files = {
        "core": [("TODO.md", REGISTER_TPL), ("docs/handoff/README.md", ENTRY_TPL),
                 ("docs/handoff/STATE.md", STATE_TPL), ("docs/RUNBOOK.md", RUNBOOK_TPL),
                 ("docs/kb/CLOSED.md", CLOSED_TPL), ("docs/kb/WORKLOG.md", WORKLOG_TPL),
                 ("docs/kb/ASKS.md", ASKS_TPL), ("docs/archive/INDEX.md", "| date | original | reason |\n|---|---|---|\n")],
        "records": [("docs/RECORDS.md", RECORDS_TPL)],
        "research": [("docs/kb/HYPOTHESES.md", HYP_TPL), ("docs/kb/QUARANTINE.md", QUAR_TPL),
                     ("docs/kb/PREREG.md", PREREG_TPL), ("evidence/README.md", EVIDENCE_TPL)],
        "ops": [("docs/INDEX.md", MAP_TPL)],
        "agents": [("docs/kb/feed.md", FEED_TPL)],
    }
    dirs = {"core": ["docs/plans", "docs/audit"], "records": ["docs/decisions", "docs/regressions"],
            "agents": ["docs/kb/workflows"]}
    for m in mods:
        for rel, body in files.get(m, []):
            write(rel, body)
        for d in dirs.get(m, []):
            (root / d).mkdir(parents=True, exist_ok=True)
    made += ignore_runtime(root)
    if "records" in mods:
        cfg = find_cfg(root)
        emit_records(cfg)
    if chain:
        bp_preflight(find_cfg(root), chain)
        made += bp_apply(root, chain)
    print(f"genome init [{', '.join(mods)}]: created {len(made)}, kept {len(kept)} existing")
    for m in made:
        print(f"  + {m}")
    for k in kept:
        print(f"  = {k} (kept)")
    print("next: `genome wake`; the loop is in docs/playbooks/" + chain[-1][0] + ".md" if chain and chain[-1][2]
          else "next: fill AGENTS.md (what this is, the routing table), then `genome lint`")


def cmd_modules(args) -> None:
    cfg = find_cfg()
    src = "kb.toml (legacy; `genome` reads it unchanged)" if cfg.legacy else "genome.toml"
    print(f"config: {src}")
    for m in MODULES:
        on = m in cfg.modules
        print(f"  [{'x' if on else ' '}] {m:9} {MODULE_HELP[m]}")


MODULE_HELP = {
    "core": "roles, lint, doctor, wake, ask, close, archive, plan/audit, log, status, q (operator asks)",
    "records": "rec recon|new|amend|supersede|merge|retire|list|show|emit (AD/RG lifecycle, ID map)",
    "research": "figure, quarantine, hyp add|verdict|list, prereg freeze|check (evidence discipline)",
    "ops": "secrets + lint gates: ownership map, links, unreachable code, tracked bulk, running-job guard",
    "agents": "wf new|add|list, claim, done, claim-register, post, feed (parallel agents)",
}


