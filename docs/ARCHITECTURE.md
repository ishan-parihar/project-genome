<!-- kb: seam role="architecture" -->

# ARCHITECTURE

What `project-genome` is made of, how the pieces fit, and the rules the whole thing
obeys. The README says what it does; this says how it is built, which is the question
a change of any size asks first.

## Modules

The `integrity` module's `[docs] sections` declaration names `Modules` and `Commands`.
Keeping the names in the file and in `genome.toml` the same is the point: a section
renamed here without the config is **E604**, which is how the two stay honest.

| Module | Codes | What it answers |
|---|---|---|
| `core` | E001–E018, W001–W014 | the genome's own roles: state, register, worklog, plans, resume |
| `records` | E101–E107 | decisions and regressions, recon-gated, immutable or amendable |
| `research` | E201–E206, W201 | hypotheses, pre-registration, quarantined figures |
| `ops` | E301–E309 | the tree's shape: ownership, links, dead code, bulk, layout, names |
| `agents` | E008 | the workflow board's claims |
| `outline` | E104 | a stale zone outline |
| `integrity` | E601–E608, W601–W605, I601 | the app, its docs, its dirs |

`core` always runs: it is what makes a repo a genome rather than a folder with a
`genome.toml` in it.

## Build

`scripts/genome` is ONE stdlib-only Python file. That is the property the whole design
rests on — copy-one-file installability, so a repo can vendor the CLI without a
dependency, a virtualenv or a lockfile.

It is not hand-written. `src/NN_*.py` concatenate, in filename order, into it, and
`scripts/build.py` refuses to change the checksum of a released `VERSION` without a
bump — because the fleet's vendored copies are compared by sha, and a new checksum at
the same version makes every one of them look hand-patched.

So the edit loop is:

```
edit src/NN_*.py  ->  bump VERSION in src/01_constants.py  ->  python3 scripts/build.py
```

`blueprints/*.toml` are folded in at build time too, so a blueprint is a declaration,
not a script.

## The three integrity axes

The consolidated `doc`, `install-script-creator` and `workspace-lint` skills left one
gap between them, and it is what the `integrity` module exists to close: all three
validated a *surface* (prose, an installer, a tree) and none could ask whether the
application still builds. So `integrity` carries three axes and every one is declared
by the repo that needs it:

- **app** — `[app] toolchain` names the language (`python`, `rust`, `node`,
  `typescript`, `go`, `java`, `shell`), inferred from the manifest when undeclared;
  `[app] build` / `test` / `typecheck` / `lint` / `fmt` / `doc` are the commands. A
  failed phase is **E601**; a formatter is **W604** because the app still runs
  unformatted.
- **docs** — `[docs] required` names the documents the project owes its readers,
  `sections` the headings one must carry, `max_lines`/`min_lines` the shape they must
  hold. An absent or heading-only required doc is **E603**.
- **dirs** — `ops.dir_globs` names directories that must exist (**E605**) and must
  not be empty (**E606**, unless the dir is a genome role's home, because `genome init`
  creates those empty on purpose).

Three severities, and only one fails a build. An **I** (`I601`) is a fact an operator
should see — a toolchain genome found but could not run on this machine — that no
check can call a defect. A **W** is a judgement. An **E** stops the gate.

## Config

`genome.toml` is the one place a repo states its own law; `CONFIG_KEYS` in
`src/01_constants.py` enumerates every key the CLI reads, and an undeclared one is
**E017** rather than a silent switch-off. `[paths]` maps roles to files, so a repo can
put its worklog wherever it likes. `[kinds]` and `[views]` declare entity schemas.

`schema_version = 2` is the one-dialect change: membership globs are root-relative and
`*/`-anchored. A schema-1 repo is reported (**E018**) with the migration to run,
because a mismatched dialect reads the wrong patterns rather than none.

## Severity and exit

| | printed | in `--json` | fails `close` / a gate |
|---|---|---|---|
| `E` | yes | `severity: "error"` | yes |
| `W` | yes | `severity: "warning"` | no |
| `I` | yes | `severity: "info"` | no |

`genome lint --advisory` prints every code and exits 0 either way, for a triage pass
that must not stop to fix things.

## Commands

`genome --help` is the full list; the ones the architecture above depends on:

| Command | Used by |
|---|---|
| `init` | scaffold roles, or adopt an existing repo |
| `lint [--only M] [--code E306] [--all]` | the whole check catalogue; `--only` one module |
| `build.py --check` | verify `scripts/genome` matches `src/` at the current VERSION |
| `close` | emit, lint, secrets, the `[core] gate`, then name what to commit |
| `ask <question>` | retrieve an answer without reading the tree |
| `doctor` | health: tracked size, records, unmet roles |
| `kb lint` | the estate: every registered repo, its own CLI's own rules |

The gate in this repo's `[core]` runs the suites and then the structure and integrity
codes, so a misplaced file or an undeclared required doc cannot reach the commit
`close` names.
