# ci-validation.md — CI-enforced documentation validation

> Covers the public-apis CI model (3 workflows on push/PR to master, format.py rules, daily link sweep), what it does NOT do (no generator, no JSON source), the per-package contract enforced in CI (deepseek), the source-line footnote convention, and a decision rule for when a curated table warrants a validator script — plus a minimal Python validator skeleton. Plan §1.3 mechanism #6; gap G7.

## When to use / When NOT to use

**Use when** the README is data-shaped (curated list, public-apis style) and a malformed entry breaks downstream consumers; or when a monorepo (archetype E) ships per-package READMEs with a section contract.

**Do NOT use** when the README is a doorway (archetype A, ≤330 lines) maintained by a single author — CI beyond link checks adds friction. Do not reach for a generator when the README is canonical content that CI validates — this inverts the usual generated-docs assumption (plan §1.3 mechanism #6; plan §1.6 gap G7).

## The mechanism — public-apis model

public-apis ships a README that is **hand-authored canonical content validated by CI** — there is no generator and no JSON source file. CI checks hand-written markdown against structural rules, then points the author at the offending cell. This is the inverse of "generate from data then lint output."

Evidence: plan §1.3 mechanism #6 (lines 70–73); plan §1.6 gap G7 (line 156). Measured table: public-apis has 2655 README lines, 0 badges, 53 tables, `none` docs site, ~3 doc pages (plan §1.1 line 15).

### Three workflows, all on push/PR to master

| Workflow | Trigger | What it runs | Plan citation |
|---|---|---|---|
| `test_of_push_and_pull.yml` | every push + PR | `format.py README.md` + duplicate-link checker | plan §1.6 G7 line 156 |
| `test_of_validate_package.yml` | every push + PR | unittest suite | plan §1.6 G7 line 156 |
| `validate_links.yml` | daily cron + `workflow_dispatch` | full link sweep | plan §1.3 mechanism #6 line 73 ("daily `cron` link sweep") |

### format.py rules

All six rules from plan §1.3 mechanism #6 (lines 70–73):

| # | Rule |
|---|---|
| 1 | Alphabetical order within each category |
| 2 | ≥3 entries per category |
| 3 | ≥5 columns per row |
| 4 | ≤100-char descriptions |
| 5 | Closed Auth/HTTPS/CORS vocabularies |
| 6 | Every cell padded one space |

A companion `links.py` (plan §1.3 line 73) checks for duplicate link targets.

### What public-apis does NOT do

| Does NOT | Why it matters |
|---|---|
| No generator | The README is hand-authored; CI validates prose, not generated output |
| No JSON source | No `services.json` data file — entries live directly in the markdown table |
| No docs site | Measured table: `none` for docs site (plan §1.1 line 15); the README *is* the product |

This inverts the generated-docs assumption: CI errors point at a specific cell in the README, not a data file to regenerate.

## Per-package contract enforced in CI — deepseek

deepseek enforces a per-package README contract via two TypeScript script validators declared in `packages/README.md` (plan §1.3 mechanism #5, lines 67–69):

| Script | Checks |
|---|---|
| `scripts/verify-package-readme-model-experience.ts` | Model Experience section present |
| `scripts/verify-package-readme-limitations.ts` | Limitations section present |

The plan upgrades this to `verify_per_package_readme.py` (plan §4.1a line 291) requiring every `packages/*/` README to cover: **purpose**, **configuration**, **extension points**, and **limitations** (plan §4.1a lines 255–257). Measured table: deepseek-harness A+E, 77 lines, ~96 doc pages, `yes` for per-package READMEs (plan §1.1 line 23).

### API-reference-to-source-line footnote

deepseek's API reference (`docs/cordis-api/registry.md`) ends each `###` member heading with a source-line footnote (plan §1.3 mechanism #9, plan §1.3 lines 78–79):

```markdown
[Source](../../vendor/cordis/src/registry.ts#L176)
```

Every API reference member links to the exact source line that implements it.

## Worked example

**public-apis format.py.** The README is 2655 lines with 53 tables (plan §1.1 line 15). Each entry row must have ≥5 columns (Name, Description, Link, Auth, HTTPS, CORS, Category, Contributor). `format.py` rejects rows with <3 entries per category, descriptions >100 chars, or cells not padded one space. The daily `validate_links.yml` sweep catches link rot that push-time checks miss.

**deepseek per-package contract.** Every package under `packages/` has a README covering purpose, configuration, extension points, and limitations. CI script `verify_per_package_readme.py` exits non-zero if any package README omits a required section. API reference pages in `docs/cordis-api/` link each member to its source line via the `[Source]` footnote.

## Decision rule: when a table needs a validator

| Criterion | Threshold | Rationale |
|---|---|---|
| Row count | >100 rows | Manual review misses entries at scale |
| Contributors | >1 | Multiple writers drift on format |
| Closed vocabulary | ≥1 enum column | Auth/HTTPS/CORS, Status, Category — CI can enforce |

public-apis passes all three: 53 tables, 0 badges (no badge drift), closed Auth/HTTPS/CORS vocabularies. The validator exists because the table is the product's data surface.

## Minimal Python validator skeleton (stdlib only)

```python
#!/usr/bin/env python3
"""Minimal CI validator skeleton — adapt per plan §1.3 mechanism #6 format.py rules."""
import argparse
import sys
from pathlib import Path


def load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def check_columns(lines: list[str], min_cols: int) -> list[str]:
    """Reject table rows with fewer than min_cols cells."""
    errors = []
    for i, line in enumerate(lines, 1):
        if "|" not in line or line.lstrip().startswith("|---"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < min_cols:
            errors.append(f"  line {i}: {len(cells)} cells < {min_cols}")
    return errors


def check_padding(lines: list[str], pad: int = 1) -> list[str]:
    """Reject cells not padded exactly `pad` spaces on each side."""
    errors = []
    for i, line in enumerate(lines, 1):
        if "|" not in line or line.lstrip().startswith("|---"):
            continue
        parts = line.split("|")[1:-1]
        for j, cell in enumerate(parts, 1):
            stripped = cell.strip()
            if stripped and (len(cell) != len(stripped) + 2 * pad):
                errors.append(f"  line {i}: cell {j} padding != {pad} space(s)")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate curated-list README table structure."
    )
    ap.add_argument("readme", type=Path, help="path to README.md")
    ap.add_argument("--min-cols", type=int, default=5)
    ap.add_argument("--pad", type=int, default=1)
    args = ap.parse_args()

    lines = load_lines(args.readme)
    errors = check_columns(lines, args.min_cols) + check_padding(lines, args.pad)

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 2
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## What to check before shipping

- [ ] Confirm the workflow trigger matches the plan: push/PR to master for format + link checks; daily cron + `workflow_dispatch` for the full link sweep.
- [ ] List every format.py rule (6 rules above) — do not omit closed vocabularies or cell-padding.
- [ ] Confirm per-package scripts (`verify-package-readme-*.ts`) are declared in `packages/README.md`.
- [ ] Verify the `[Source](../../vendor/cordis/src/registry.ts#L176)` footnote on every `###` member in API reference docs.
- [ ] Apply the decision rule (table above) before writing a custom validator.
- [ ] Test the Python skeleton against a fixture (see run-it check in acceptance).
- [ ] For generated-docs repos: do NOT add a validator when the generator already enforces structure — the README is canonical content, not generated output.
