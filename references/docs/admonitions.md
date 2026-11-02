# GitHub Admonitions + Badge Snippets

Cited by polishing/ (Pass 2–3).

## Admonitions (GFM)

```markdown
> [!NOTE]
> Useful context the reader shouldn't miss.

> [!TIP]
> A faster or better way to do the thing.

> [!WARNING]
> Behavior that will surprise or bite.

> [!CAUTION]
> Data-loss or security risk. Use rarely.
```

Rule: at most a handful per README. If everything is highlighted, nothing is.

## Badges (3–8 in the hero)

```markdown
![Language](https://img.shields.io/badge/Language-Version-color?logo=logo)
![Version](https://img.shields.io/npm/v/package-name)
![Build](https://img.shields.io/github/actions/workflow/status/USER/REPO/ci.yml)
![License](https://img.shields.io/badge/License-MIT-green)
```

Prefer service-native badges (npm, PyPI, crates.io, Go pkg) over generic ones. Cap at 8 — past that they become noise.

## Visual proof patterns

Hero (first screen):

```markdown
# Project Name

**One-line promise — differentiators, stack, outcome.**

![Hero visual](https://github.com/USER/REPO/raw/main/assets/readme/hero.png)
```

Gallery (before Architecture):

```markdown
## Visual proof

| Feature A | Feature B | Feature C |
|:---:|:---:|:---:|
| ![A](url) | ![B](url) | ![C](url) |
| Caption | Caption | Caption |
```

Host images under `assets/readme/` on the repo's own `raw/main` URLs — no external hosts that rot.
