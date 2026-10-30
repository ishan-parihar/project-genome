# CLOSED — tried and rejected

Append-only. An entry names the item, the verdict, the measurement that killed it
(a path), and the re-open condition. Re-proposing needs new evidence.

## 2026-10-30 — Turning on all six modules here to match the modules this kernel ships

**Tried:** setting `modules = ["core","records","research","ops","agents","outline"]` in
`genome.toml` so this repo's own config exercises everything the kernel ships to adopters.

**Killed:** `research`, `ops`, `agents` and `outline` are modules *this repo ships*; they
are not disciplines *this repo* runs. Turning them on would add five kinds dirs, an
ownership map, a budget block and a drift-gated structural zone to a project whose entire
content is one built file and its ten manuals — zones that would then need their own
register entries and their own upkeep, with nothing to put in them. The lint wires them
independently; `core` + `records` is the honest configuration for a **software** profile.

**Measured:** `genome.toml` after `genome init --profile software` declares exactly
`["core", "records"]`; the reference for each optional module opens by describing the project
shape it is for, not the kernel that implements it.

**Re-open when:** a second sustained effort appears that this repo must run on its own —
a research programme of its own with hypotheses to pre-register, or agent work dispatched
from here with claims to coordinate. Not before.

## 2026-10-30 — Rewriting `README.md` as the routing page

**Tried (as a plan, not as a change):** replacing the README's front page with the
routing table, the way the meta-root's own README does for its 106 repos.

**Killed:** `README.md` is the **PyPI front page**. It is the file `[project] readme`
points at, it is what renders on the package index, and its tables about install shapes
and command surface are what a reader lands on first. Overwriting it with the agent-facing
routing table would either break the README that ships, or force a second README into the
package. The routing table lives in `AGENTS.md`, which is not packaged, and the README
gains one line pointing there (PQ-7) rather than a merge of the two.

**Measured:** `sdist` include list carries `README.md` and `SKILL.md` and does not carry
`AGENTS.md` (59-file listing of `dist/project_genome-0.1.0.tar.gz`, 2026-10-30).

**Re-open when:** the README is split into a marketplace front page and a repo-oriented
page as two files, which is a packaging change with its own gate, not a documentation edit.
