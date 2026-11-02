# Repo surface — about, topics, sponsorship, licence

A repository is not published because its code exists. It is published when a
stranger can find it, tell what it is, and click something. This is the
outermost layer of the genome: it lives on GitHub, not in the tree, so
`genome lint` cannot see it and nothing in the repo keeps it current.

## The four fields, and what each one is for

| Field | Where it lives | Why it matters | Absent means |
|---|---|---|---|
| **About** (description) | GitHub repo settings | The only sentence a search result or profile card shows | The repo is unreadable in a list, however good it is |
| **Topics** | GitHub repo settings | GitHub's own search index; how anyone finds it without knowing the name | Invisible to search; the only route in is the name |
| **Sponsorship** | `.github/FUNDING.yml` **in the repo** | Renders the Sponsor button on the repo and in the sidebar | The one place a reader is already convinced offers no way to act |
| **Licence** | `LICENSE` in the repo | Without it, default copyright applies: nobody may legally reuse the code | "Public" is technically still all-rights-reserved |

A placeholder `FUNDING.yml` whose entries are all commented out is worse than
none: GitHub renders no button, so it reads as configured when it is not.
Measured 2026-11-02: 47 of 48 public repos carried exactly that template.

## The rule

Every repository in the portfolio, whether it has a genome or not, carries all
four. The genome owns the discipline; the *portfolio* owns the measurement,
because GitHub-side facts can only be read with credentials and only across
the whole account.

The writers, in `~/Documents/github/my-projects`:

```bash
python3 scripts/measure.py   --json docs/audit/portfolio-measurements.json
python3 scripts/ownership.py --json docs/audit/portfolio-ownership.json
python3 scripts/enrich_repos.py                 # report gaps + proposals
python3 scripts/enrich_repos.py --apply --funding   # fill them
```

`ownership.py` emits a `metadata` section: every owned repo with description,
topics, funding links, licence, visibility and push date, plus named gap lists
(`no_description`, `no_topics`, `no_funding`, `no_license`). That is the
authority — not a guess about what GitHub probably shows.

`enrich_repos.py` only proposes from evidence, in this order: the repo's own
packaging metadata, then its README, then facts the engine measured. A repo
with no source is **reported, not filled** — a placeholder description reads as
finished and stops anyone from writing a real one.

## When a new repo is created

The four fields are part of creating it, not a later chore:

1. A description that says what it does, not what it is called.
2. Topics from measured facts — language, surface (`mcp`, `cli`, `library`,
   `docs`), and the group it belongs to. Not keywords invented from the name.
3. `.github/FUNDING.yml` with an active `github:` entry (the template in
   `assets/installer/` and `references/installer/cta-star-donate.md` has the
   canonical block; the installer epilogue adds it automatically).
4. A `LICENSE` appropriate to what the repo is meant to allow. Choosing a
   licence is an operator decision — never pick one on someone's behalf
   because a gap list asked for it.

## Verification

```bash
python3 scripts/ownership.py --check      # counts reconcile, metadata re-read
python3 scripts/enrich_repos.py           # must print no proposals
```

`enrich_repos.py` exiting with proposals pending IS the red state for this
discipline. It is not a lint warning; it is the repo surface being
unpublishable.

## Traps

- **Private repos have no Sponsor button.** `no_funding` will not reach zero
  across the account; only the public, non-fork, non-archived population
  matters.
- **`fundingLinks` is empty for a comment-only file.** Check for an *active*
  key, not for the file's existence.
- **An existing active `FUNDING.yml` is someone's choice.** Leave it; report
  it instead. The portfolio has both `github.com/sponsors/ishan-parihar` and a
  Razorpay custom URL in use, and overwriting one would break a real link.
- **Forks inherit their upstream's fields.** They are excluded from the gap
  lists on purpose; do not brand a fork as if it were the work.
