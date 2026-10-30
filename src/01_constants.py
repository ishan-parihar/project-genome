# ---------------------------------------------------------------- constants

JSON_CMDS = {"ask", "lint", "doctor", "new", "show", "find", "graph", "place", "card", "impact"}  # commands with a --json form
MODULES = ("core", "records", "research", "ops", "agents", "outline")
PROFILES = {
    "software": ["core", "records"],
    "research": ["core", "records", "research", "ops"],
    "team": ["core", "records", "agents"],
    "full": list(MODULES),
}
LEGACY_MODULES = ["core", "records", "agents"]  # what a kb.toml repo already had

STATUS_VOCAB = ("open", "in-progress", "done", "rejected", "blocked")
TERMINAL = ("done", "rejected")
HYP_VOCAB = ("open", "testing", "accepted", "rejected", "parked")
HYP_TERMINAL = ("accepted", "rejected")
ASK_VOCAB = ("open", "ruled", "withdrawn")
RETIRED_PATHS = ("closed",)  # accepted with a W507 warning (a dead role; same file as `ledger`); `genome migrate` removes it

CLASSES = ("CERT", "FORWARD", "LIVE", "OUT-OF-SAMPLE", "IN-SAMPLE")

DEFAULT_PATHS = {
    "agents": "AGENTS.md",
    "state": "docs/handoff/STATE.md",
    "entry": "docs/handoff/README.md",
    "register": "TODO.md",
    "ledger": "docs/kb/CLOSED.md",
    "worklog": "docs/kb/WORKLOG.md",
    "asks": "docs/kb/ASKS.md",
    "plans": "docs/plans",
    "audits": "docs/audit",
    "runbook": "docs/RUNBOOK.md",
    "archive": "docs/archive",
    "readme": "README.md",
    "docs": "docs",
    # records
    "decisions": "docs/decisions",
    "regressions": "docs/regressions",
    "records_index": "docs/RECORDS.md",
    # research
    "evidence": "evidence",
    "hypotheses": "docs/kb/HYPOTHESES.md",
    "quarantine": "docs/kb/QUARANTINE.md",
    "prereg": "docs/kb/PREREG.md",
    # ops
    "ownership_map": "docs/INDEX.md",
    # agents
    "feed": "docs/kb/feed.md",
    "workflows": "docs/kb/workflows",
}
MODULE_ROLES = {
    "core": ["agents", "state", "entry", "register", "ledger", "worklog", "asks", "plans",
             "audits", "runbook", "archive", "readme", "docs"],
    "records": ["decisions", "regressions", "records_index"],
    "research": ["evidence", "hypotheses", "quarantine", "prereg"],
    "ops": ["ownership_map"],
    "agents": ["feed", "workflows"],
    "outline": ["agents"],
}
APPEND_ONLY = ("ledger", "worklog", "feed", "prereg", "quarantine")
TOMBSTONE = re.compile(r"<!--\s*kb: tombstone target=\"([^\"]+)\"")
ZONE_RE = re.compile(r"<!-- genome:zone (\S+) sha=([0-9a-f]+) -->\n(.*?)<!-- genome:end \1 -->", re.S)
ERR = 2
MIN_CHUNK = 5  # lines; `ask` hits narrower than this point at a lead line without its content
HUB_NODE_CAP = 3000  # nodes; above this `graph hubs` ranks by degree and says betweenness was not computed
_TMP_SEQ = itertools.count()  # makes each atomic_write temp name unique within this process too
VERSION = "2026.10.30-23"
# every key genome reads: an unknown key is a typo that would silently switch a check off (E017)
CONFIG_KEYS = {
    "genome": {"modules", "schema_version"},
    "card": {"intent", "architecture", "operate", "decisions", "status", "offer", "purpose", "privacy", "components", "status_into"},
    "federation": {"repos", "cache", "status_into", "exclude"},
    "index": {"embed"},
    "drift": {"mode", "paths", "warn_until"},
    "core": {"append_window", "archive_form", "ask_days", "ask_globs", "ask_index", "budgets", "checklist", "dated_pattern",
             "emitters", "gate", "living_plans", "never_commit", "pointer_ignore", "resume", "resume_heading",
             "resume_lines", "toc_lines", "wake_lines", "worklog_form", "worklog_index", "worklog_width"},
    "records": {"archive", "mode", "prefix", "recon_hours", "width", "zones", "required", "governed_by"},
    "research": {"classes", "figure_pattern", "hyp_prefix", "hyp_statuses", "surfaces", "quarantine_surfaces"},
    "ops": {"bulk_allow", "bulk_globs", "code_globs", "code_roots", "jobs", "link_prefixes", "link_surfaces",
            "max_bytes", "owner_exempt", "owner_globs", "py_paths", "secrets", "root_files", "dir_suffixes",
            "dir_requires", "stale_terms", "stale_exempt", "external_ok"},
    "outline": {"zones"},
}
STALE_DOCS = ("*.md", "*.yaml", "*.yml", "*.toml", "*.txt", "*.rst")  # stale paths matter where people read
# The root files an ordinary software repo carries, and that no role points at.
# Each is an ecosystem convention, not a genome role: a repo that keeps one
# keeps it for the same reason every other repo does.
CONVENTIONAL_ROOT_DOCS = {
    "AGENTS.md", "CLAUDE.md", "README.md", "TODO.md",
    "CONTRIBUTING.md", "CHANGELOG.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    "GOVERNANCE.md", "MAINTAINERS.md", "SUPPORT.md", "AUTHORS.md",
    "NOTICE.md", "SKILL.md",
}
SEVERITIES = ("Critical", "High", "Medium", "Low")
STOP = set("the and for what where which how does did are was were this that with from into when who why "
           "should can its it's our your about have has not any all in is it of on or to we an as at by do if "
           "me my no so up us be he".split())


def jprint(obj) -> None:
    """The `--json` output form: one compact JSON document on stdout, for agents that pipe."""
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M")


def today() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d")


DIE_PREFIX = ""  # context for an error raised deep in a loop (e.g. "batch line 3: ")


def die(msg: str, code: int = 1):
    print(f"genome: {DIE_PREFIX}{msg}", file=sys.stderr)
    raise SystemExit(code)


def slugify(s: str, n: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def sh(root: Path, *cmd: str, timeout: int = 30) -> str:
    try:
        return subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def atomic_write(p: Path, text: str) -> None:
    """Write via a temp file + rename: a crash leaves the old file or the new one, never half of one.

    The temp name carries the pid and a per-process counter, because a name derived only from the
    filename collides the moment two processes write the same name: one `federate` merging two genomes
    that each hold `map/engrams/EN-0001-….md`, or a manual write racing the sync timer. Both would open
    the same `.genome-tmp` path and one would truncate the other mid-write, which is not hypothetical -
    it broke roughly one run in three. The pid alone is not enough, hence the counter for a second
    write inside one process, and a failed or interrupted write unlinks its temp so nothing is left
    for the next run to trip over."""
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.genome-tmp.{os.getpid()}.{next(_TMP_SEQ)}")
    try:
        with open(tmp, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp)
        raise


def read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


