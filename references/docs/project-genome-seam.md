# The project-genome seam — where outward docs meet the internal genome

> How this skill's outward artifacts relate to `~/.agents/skills/project-genome`
> (the `genome` CLI), which owns a repo's internal agent documentation. Read when
> a task touches both the public README/docs and the repo's internal roles
> (state, plans, worklog, records, register).
>
> project-genome replaced `project-kb` on 2026-10-17; `kb.toml` repos still work
> unchanged under `genome`. The old skill is archived at
> `project-genome-workspace/archive/project-kb-2026-10-17/`.

## The division

`project-genome` owns the **internal roles**, each with a declared mutability
class, and a `genome` CLI that checks them. Its roles answer *agent* questions:
where the project stands, what was decided and why, what was tried and rejected.

This skill owns the **outward pair**: `README.md` (audience-facing: what is
this, how do I run it) and `docs/` (the depth the README links to). Those answer
*reader* questions.

## The seam

1. **The role map declares the outward pair.** `genome.toml` (or a legacy
   `kb.toml`) maps `readme = "README.md"` and `docs = "docs"`. Declared, not
   enforced: a repo may have no `docs/` depth behind its README.
2. **Two boundary lint codes** in `genome lint` (`project-genome/references/lint-rules.md`):
   - **W008**: a root README section and a `docs/` page answer the same
     question. Fix: the README links; it does not paraphrase.
   - **W009**: a `docs/` page is linked from neither the README nor any other
     page. Fix: link it, archive it, or delete it.

   Internal genome roles under `docs/` are exempt from W009: they are for
   agents, not readers.
3. **The `AGENTS.md` routing table reaches outward.** The template `genome init`
   writes carries rows for *"what is this, how do I run it" → `README.md`* and
   *"how does it work, in depth" → `docs/`*.

## What each side checks

| Concern | Owner | Tool |
|---|---|---|
| README section set, length band, proof, badges | this skill | `scripts/score_readme.py --archetype` |
| Per-package README contract (archetype E) | this skill | `scripts/verify_per_package_readme.py` |
| README↔docs dead links, orphan pages, dead anchors | this skill | `scripts/docs_lint.py` |
| README↔docs duplicate question (W008), unreachable page (W009) | project-genome | `genome lint` |
| Register, records, plans, worklog, evidence, housekeeping | project-genome | `genome lint`, `genome doctor` |

Overlap is deliberate and narrow: this skill judges the *quality of the outward
surface*; `genome` judges *ownership across the whole doc tree*. Run both.

## Which one to descend into

- "Write/improve the README" → this skill, `--mode=readme`.
- "The README is too long / needs a docs site" → this skill, `--mode=docs-site`.
- "Why is X built this way / what did we reject / where does the project stand"
  → `project-genome` (`genome wake`, `genome ask`); those are internal roles and
  this skill should not invent them.
- A repo with fewer than ~3 documents → a README suffices, and it is still the
  `readme` role; `genome lint` then has nothing to say about W008/W009.

## The invariant to preserve

**The README answers audience questions; `docs/` answers depth; the genome
answers agent questions.** A change that moves an answer across one of those
boundaries is a defect, and is what W008 and `docs_lint.py` D002 exist to catch.
