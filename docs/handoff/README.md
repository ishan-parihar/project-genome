# Entry — what a fresh agent does, in order

1. `python3 scripts/genome wake` — state, resume point, operator questions, jobs, health in one call.
   (From this repo root, or `python3 -m project_genome` if the wheel is installed.)
2. `python3 scripts/genome ask "<question>"` — the one section that answers it; read that range only.
3. Before work that touches a decision: `python3 scripts/genome rec recon <keywords>` (prior art).
4. End of iteration: `python3 scripts/genome close`.

**Read this second, and it is short:** `AGENTS.md` § Architecture. The property that
matters here — the CLI is one stdlib-only file — is what every rule below exists to
protect, and the lint code numbering rule is the one that is easiest to get wrong.

**Then, for what to build:** [`../plans/2026-10-30-remaining-implementation-gaps-outline.md`](../plans/2026-10-30-remaining-implementation-gaps-outline.md)
is the live execution order. Its Tier 0 (sync the four skills roots, reconcile the
installs manifest) is the one part a fresh agent can do without a ruling; Tier 3 names the
operator's calls and none of them is answered there.

**Stop and ask the operator** (record it with `python3 scripts/genome q add`): anything
that publishes (`docs/PUBLISHING.md` needs a credential this seat does not have), anything
that rewrites the fleet (the 75-repo CLI upgrade is PQ-1, an operator-approved pass), and
the evals run (16 evals, a graded harness call).
