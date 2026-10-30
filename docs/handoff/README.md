# Entry — what a fresh agent does, in order

1. `python3 scripts/genome wake` — state, resume point, operator questions, jobs, health in one call.
   (From this repo root, or `python3 -m project_genome` if the wheel is installed.)
2. `python3 scripts/genome ask "<question>"` — the one section that answers it; read that range only.
3. Before work that touches a decision: `python3 scripts/genome rec recon <keywords>` (prior art).
4. End of iteration: `python3 scripts/genome close`.

**Read this second, and it is short:** `AGENTS.md` § Architecture. The property that
matters here — the CLI is one stdlib-only file — is what every rule below exists to
protect, and the lint code numbering rule is the one that is easiest to get wrong.

**Stop and ask the operator** (record it with `python3 scripts/genome q add`): anything
that publishes (`docs/PUBLISHING.md` needs a credential this seat does not have), anything
that rewrites the fleet (the 75-repo CLI upgrade is PQ-1, an operator-approved pass), and
the evals run (16 evals, a graded harness call).
