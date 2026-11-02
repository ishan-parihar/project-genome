# Audit Rubric — 8-Check Quality Bar

Cited by verifying/ (Job 1). Each check: +1 pass, −1 fail. Target: no issues.

**The rubric is archetype-relative.** Run
`score_readme.py README.md --archetype <name>`; without the flag the generic
README-shaped bar applies. A correct curated list or learning resource scores
*negative* under the generic bar because it owes no install section, no code
examples, and no badges — measured during the 11-repo audit.

## The eight checks

| # | Check | Generic (default) | A Doorway | B Skills-pack | C Curated | D Learning | E Monorepo |
|---|---|---|---|---|---|---|---|
| 1 | `value_prop_clear` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | `proof_before_arch` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | proof form | ≥3 images | ≥1 image | concrete artifact | **entry density ≥10 links** | ≥1 inline at point of use | concrete artifact |
| 4 | `install_before_arch` | ✓ | ✓ | ✓ | n/a (nothing to install) | n/a | ✓ |
| 5 | `code_examples_2plus` | ≥2 blocks | ≥2 blocks | ≥2 blocks | **not owed** | **not owed** | ≥2 blocks |
| 6 | `tables_for_structure` | ≥1 table | **not owed** | **not owed** | **not owed** | ≥1 table | **not owed** |
| 7 | `badges_within_ceiling` | ≤7 | ≤7 | ≤7 | any | any | ≤7 |
| 8 | `length_in_band` | 100–170 | 70–340 | 150–400 | 400–2700 | 800–2000 | 70–340 |

Universal across every archetype: check 1 (a real first paragraph, not a
placeholder), check 2 (proof before architecture), check 7 (badge ceiling), and
check 8 (the archetype's band, not one global band).

**Why a ceiling and not a range on badges.** The audit measured 11 repos: no
repo exceeds 7, and 6/11 use zero and are correct (n8n, deepseek-harness,
system-design-primer, superpowers, karpathy, public-apis). A floor would fail
correct READMEs; only the ceiling is evidence-backed.

**Why check 6 is "not owed" for C.** A curated list's structure is its entry
list and its `## Index`, not a pipe table. build-your-own-x ships 505 lines with
zero tables and is correct.

**Why check 3 is entry density for C.** A list's proof is that it is dense and
curated. Ten-plus markdown links is the machine-checkable proxy.

## Scoring

```python
# score_readme.py --archetype <name>  (the machine-readable form)
# each check contributes +1 pass / -1 fail; thresholds from the table above
```

A check the archetype does not owe is reported as *not applicable* and excluded
from both counts, so a clean C-typed README is not credited with eight real
passes when three are vacuous.

## What a failure routes to

Content gaps (1, 5) → mining/. Structure gaps (2, 4, 6, 8) → constructing/.
Proof and badge gaps (3, 7) → polishing/. A length failure on a C or D README is
almost never "shorten it" — it is a wrong archetype declaration, so re-check
`archetypes.md` before editing the prose.

## The measured regression this rubric exists to prevent

A 737-line archetype-C-correct list scores **0/8 under the generic bar** and
**8/8 under `--archetype curated-list`**. A 1006-line archetype-D-correct
curriculum scores **0/8 generic**, **8/8 under `--archetype learning-resource`**.
Both were reproduced during the audit; both are the reason the flag exists.
