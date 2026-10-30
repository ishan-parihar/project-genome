# Skills-root audit — the differences, and the cleanup

Dated-frozen: published `2026-10-30`. Measured on this machine at that date, every
figure derived by the command named beside it.

**Owner:** `docs/audit/` (this document). **Inputs:** the six skills roots on this
machine, the installs manifest `~/.config/genome/installs.json`, the global skills
lock `~/.agents/.skill-lock.json`, the `skills-backup` service, and both installers
in this repo.

## The claim under test

Only `~/.agents/` is the canonical global skills directory, because only it is backed
up by gitsync; every other root must be a symlink into it. Measured, that claim splits
into three true statements and one false one.

| # | statement | verdict |
|---|---|---|
| 1 | `~/.agents` is the only root that is backed up | **True.** It is a git repo pushing hourly to `ishan-parihar/agents-backup`; the other five roots are not git repos at all |
| 2 | the others are symlinks into it | **Mostly true, but not uniformly.** `.claude` has 125 links but **11 real copies**; `.zcode` has 284 links but **2 real copies**; `.codex` has 1 real copy; and two roots the probes never look at exist |
| 3 | the redundancy is therefore only the leaf copies | **False.** the largest redundancy is not the leaves, it is that the *installer itself* clones the skill into four roots separately |
| 4 | a cold start works | **False in two places.** the installer probes four roots and misses two that exist, and the installer's own skill copy does not match what `npx skills add` writes |

## §1. The six roots

| root | is a git repo | entries | real dirs | symlinks | reaches |
|---|---|---|---|---|---|
| `~/.agents/skills` | **yes** (`agents-backup`) | 153 top-level | **152** | 2 | 260 `SKILL.md` |
| `~/.claude/skills` | no | 136 | **11** | 125 | 301 `SKILL.md` |
| `~/.zcode/skills` | no | 286 | **2** | 284 | 443 `SKILL.md` |
| `~/.codex/skills` | no | 4 | 1 (+ `.system`) | 2 | 8 `SKILL.md` |
| `~/.codegpt/skills` | no | 2 | 2 | 0 | — |
| `~/.config/opencode/skills` | no | 1 | 1 | 0 | — |

Counted with `ls -A` on the root, `-maxdepth 1 -type l` for the links, and
`find -L <root> -name SKILL.md | wc -l` for the reach. `.agents` is 44 MB on disk;
`.claude` and `.zcode` are 5.9 MB each and almost entirely links.

**The backup is one-way and hourly.** `~/.config/systemd/user/skills-backup.timer`
fires at minute 17; `~/bin/skills-backup` stages exactly `skills .skill-lock.json
.gitignore` — never a bare `git add -A` — pushes to origin, and on a rejected push
rebases once and never force-pushes. Last run: `9b1b0d66`, "Auto-backup: Fri Oct 30
10:20:43". Its `.gitignore` excludes `/logs/`, `/.agents/`, `/ao/`,
`/chandra-ocr-workspace/` and the root runtime dirs, so **the only durable copy of a
skill in this machine's backups is the one under `~/.agents/`.** That is what makes
the claim's first half true.

## §2. The differences, root by root

### 2.1 `.claude` — 11 real copies, each a *second source of truth*

These eleven are directories, not links, and ten of them are absent from
`~/.agents/skills`:

```
aportal   arch-deb-packaging   arch-deb-packaging-workspace   browseros-neo
claude-code-admin   facebook-mcp   gemini-model-manager   omarchy-bar-management
project-genome   wealth-sovereign
```

Of those, **`project-genome` and `browseros-neo` also exist in `~/.agents/skills`** —
byte-identical content (`diff -rq` reports only `.git/` internals and a
`__pycache__`), four distinct inodes. So they are four **full 4.8 MB clones** of the
skill, one per root, installed by `install.sh`'s `--skill` loop rather than by one
install and four links.

The other eight are real only in `.claude`. They are **not lost** — `.zcode/skills`
holds them as real dirs too — but they are also **not in the backup**. A disk failure
loses eight skills that no gitsync copy survives.

### 2.2 `.zcode` — 284 links, 207 of which point at `.claude`, not `.agents`

The zcode tree is the *most* correct root by count, but its links are chained:
`~/.zcode/skills/adepthood → /home/ishanp/.claude/skills/law-of-one/energy-centers/adepthood`,
then that `.claude` path resolves onward into `~/.agents/skills`. Two hops, through a
directory that is itself a link.

**Measured: 207 of the 284 zcode links name `/home/ishanp/.claude/skills` in their target**
(and the same 207 resolve through `.claude`, so the two counts agree). **A single pass at
`.agents` would collapse every one of those to one hop**, which also removes the case
where a link's target is a link to a link that was deleted.

**Re-measured 21:17 the same day: 207, and the published 43 was an artefact of a broken
count.** The audit's "43 directly to `.claude`, plus about 150 into `.claude`'s nested
category subdirectories" was measured with a `readlink` loop whose `case` pattern matched
only some targets; re-run plainly it returns 207 for the whole tree. The number is *larger*
than published, so **S5 (flatten the chain) is the highest-value single pass in this
document**, not a tidy-up: it removes two hops from 207 links and every
link-to-a-deleted-link case in the tree. This is the one figure in this audit that was
wrong in the direction of understating the defect, and the audit's own CR-4 rule — a
figure cites the command that produced it — is what caught it on re-measurement.

One link is already broken: `good-skill -> ../../.agents/skills/good-skill`, and the
target does not exist.

`.zcode` also holds **two real dirs of its own**: `project-genome` (a fourth clone)
and `security-ops` (absent from every other root and from the backup).

### 2.3 `.codex` — the *correct* shape, and a warning

`.codex/skills` holds two symlinks (`diagnose-crash`, `omarchy`, both into
`/usr/share/omarchy/default/agents/skills`), one real copy (`project-genome`, the
fourth clone), and `.system/` — its own tree, marked by a
`.codex-system-skills.marker` holding a hash. That marker is the convention worth
copying: **the harness's own system skills are namespaced and not for a global
installer to touch.** `project-genome` sitting beside them as a plain directory is
the one thing here that should have been a link.

### 2.4 `.agents` — the canonical root, and it is not flat

153 top-level entries: 152 real dirs, 2 symlinks. It carries both leaf skills
(`agent-mail`, `archify`, 100 more) and **category groups with nested skills**
(`devops` 32, `creative` 11, `software-development` 12, `social-media` 11,
`productivity` 22, `law-of-one` 63). It *also* carries a flat tail of root-level
entries: `business-actualisation`, `law-of-one`, `lifeos-sync`, `slideforge` (each a
real skill with its own `SKILL.md` at `~/.agents/<name>/SKILL.md`) and four category
dirs `career`, `creative`, `devops`, `software-development` — some of which are the
same skills as under `skills/` and some of which are not.

That last overlap is the redundancy that is *easiest to miss*: `~/.agents/career` and
`~/.agents/skills/resume-skills` both hold the resume family; `.claude/skills`
symlinks `resume-skills -> /home/ishanp/.agents/career/resume-skills`, i.e. through
the root-level copy rather than the `skills/` one.

### 2.5 The lock file names 23 of 153

`~/.agents/.skill-lock.json` (version 3, tracked by the backup) records 23 skills —
the entire `ResumeSkills` family plus `cv-builder`. All 23 exist on disk; **131 of
the 153 on-disk skills have no lock entry**, so `npx skills update` can never refresh
them. `project-genome` is one of the 131.

## §3. The genome-specific install gaps

Four measurements, each one a place a cold-start machine diverges from what the docs
promise.

### 3.1 `npx skills add` does not give you a CLI

`docs/PUBLISHING.md` line 122 claims `npx skills add` yields "CLI: yes (inside the
skill)". The first half is literally true and practically false: the skill directory
does ship `scripts/genome`, which runs (`./scripts/genome --version` → `genome
2026.10.30-22`), but **nothing puts a `genome` on PATH**, and nothing registers it in
`~/.config/genome/installs.json`. So every documented command in `references/` —
`genome lint`, `genome close`, `genome wake` — fails on a machine that installed the
npx way, until the operator edits PATH or re-runs `install.sh` for the CLI.
Meanwhile the repo has **no `package.json`**, so the skill cannot even be published to
the npm registry the npx path reads from — the current line works only because the
CLI takes a GitHub `owner/repo`.

The asymmetry in one line: **`install.sh` installs the CLI and skips the skill by
default; `npx skills add` installs the skill and skips the CLI by default. Neither
default is the product.**

### 3.2 The `--skill` loop clones four times instead of linking once

`install.sh` § `[SECTION: skill]` probes `$HOME/.agents/skills`,
`.claude/skills`, `.zcode/skills`, `.codex/skills` and, for each that exists, runs a
**separate `git clone --depth 1`**. That is the four 4.8 MB clones of
`project-genome` — the exact opposite of the convention `npx skills add -g` uses:
one real copy at `~/.agents/skills/<name>/`, then a symlink per agent, plus a
`.skill-lock.json` entry so `update` knows where to re-fetch from. The installer
writes **no lock file at all** (grep for `lock` in `install.sh`: no matches), which is
why `npx skills update` cannot see the copy it installed and why its 131 unlocked
skills never refresh.

### 3.3 The probe list misses two roots that exist

The four-root probe finds `.agents`, `.claude`, `.zcode`, `.codex`. It does not probe
`~/.codegpt/skills` (2 real skills) or `~/.config/opencode/skills` (1). Both are real
harness roots on this machine; `.claude/skills/browser-automation` is already a
symlink into `~/.codegpt/skills/browser-automation`, which proves a harness reads it.

### 3.4 The four skill copies are one commit behind the CLI

Installed today: the PATH `genome` is `2026.10.30-23` (a uv tool install at 15:34,
registered in the manifest as a `bin` row with version `?`), while all four skill
copies are `2026.10.30-22`. `genome doctor` says "newer than the installed skill copy"
— the fence fix (`broken_zones`) is live in the CLI and absent from every skill copy.
And `~/bin/genome` still points at `/home/ishanp/organism/.../task-grid/bin/genome`
at `2026.10.21-2`, an orphan that is **not even on PATH** (`~/bin` is absent from
`$PATH` — measured: 0 occurrences).

## §4. What a cold start should do

1. **Install the CLI and register it** — the existing `install.sh` chain does this
   (uv → pipx → pip, `installs register bin`), and it is the only path that does.
2. **Write one real skill copy at `~/.agents/skills/project-genome`** — the backup
   root, so it survives.
3. **Symlink every other root's `project-genome` at that copy** — including
   `.codegpt` and `opencode`, which the probe must learn about.
4. **Write `~/.agents/.skill-lock.json`'s entry for project-genome**, so
   `npx skills add`/`update` sees it and does not install a second copy.
5. **Re-measure the reach** after the change: one real copy plus N links, and
   `find -L` on each root returning the same `SKILL.md` count.

## §5. Cleanup, ordered by what each step unblocks

Each step names its command and its check. **No step deletes anything without the
operator's call**, per the standing ruling — this document records differences, and
the deletions it implies are Tier 3 of the plan in `../plans/`.

| step | action | check |
|---|---|---|
| S1 | Repoint `.claude`, `.zcode`, `.codex` `project-genome` at the `.agents` copy: remove each clone, create each link | `diff -rq ~/.agents/skills/project-genome <root>/skills/project-genome` empty except the link; inode identical |
| S2 | Re-link `good-skill` or delete the dangling link | `for l in $(ls -A …); do [ -e "$l" ] \|\| echo broken; done` returns empty |
| S3 | Move the eight `.claude`-only skills into `~/.agents/skills/` and link them | each name resolves under `.agents`; the backup's next `skills-backup` run stages them (it stages `skills` wholesale) |
| S4 | Same for `.zcode`'s `security-ops` and the two `.codegpt` / one `opencode` skills | as S3 |
| S5 | Flatten the chained links: `.zcode`'s **207** links that name `.claude` in their target become links directly to `.agents` | `readlink` on every zcode entry returns a path under `~/.agents` |
| S6 | Reconcile `~/.agents/<skill>` (the root-level tail) against `~/.agents/skills/<skill>` — one owner per skill | no skill family exists twice under `.agents` |
| S7 | Register the 131 unlocked skills, or accept that `npx skills update` will not refresh them | `python3 -c "import json;…"` count of lock entries vs on-disk dirs |

**What S1–S7 do not fix:** the installer's four-clone loop (§3.2) and its probe list
(§3.3). Those are code changes in this repo, sequenced in the plan.

## Not covered by this audit

- Whether each harness follows symlinks into `~/.agents` (the `npx skills` docs say
  install with `--copy` where a tool does not; the measured roots all use links, and
  every harness on this machine resolves them, so this is a *documentation* gap, not
  an observed break).
- Any skill's content correctness. This is a topology audit only.
- The `.claude/.sync-protect` list. It names four skills; `gstack` and `ui-styling` no
  longer exist anywhere on the machine, so the protect list is stale in the
  direction that hides breakage rather than causing it.

## Re-measured 2026-10-30, 21:17 — three figures moved since publication

The audit was published the same day, so the tables above are a snapshot. Re-measured
four hours later, the drift is small but it is **upward in the wrong direction**:

| figure | published 10:30 | re-measured 21:17 | what moved |
|---|---|---|---|
| `.agents/skills` top-level real dirs | 152 | **153** | one more skill landed in the canonical root |
| `.agents/skills` SKILL.md | 260 | **263** | the same three new skills |
| `.claude/skills` links | 125 | **126** | one more link, and its real copies went 11 -> 11 |
| `.claude/skills` SKILL.md | 301 | **303** | two more skills reachable |
| `.zcode` links that name `.claude` in their target | 43 | **207** | **the audit undercounted the chain ~5x — a broken count, not drift** |
| backup last commit | `9b1b0d66` (10:20) | `0851491b` (20:18) | the hourly timer ran ten more times |

The zcode chain figure is the one that changes a decision, and it was measured wrong.
The published "43 directly to `.claude`, plus about 150 into `.claude`'s nested category
subdirectories" came from a `readlink` loop whose `case` pattern matched only some
targets; run plainly it returns **207** for the whole tree, and 207 is also the
resolved count, so the two agree. `~/.zcode/skills/devops` is not even a link (it is
one of `.zcode`'s two real dirs), and **207 of its siblings point through `.claude`** —
e.g. `~/.zcode/skills/adepthood -> /home/ishanp/.claude/skills/law-of-one/energy-centers/adepthood`.
So S5 (flatten the chain) is **more** valuable than the audit claimed, not less: a
single pass that re-points those 207 at `~/.agents` removes two hops and every
link-to-a-deleted-link case in the tree. Everything else in this document stands.
