# Star + donate epilogue (mandatory section)

Every installer this skill generates ends with a CTA: star the repo, donate if the
project helped. Plus a persistent `donate` path in the tool itself. Defaults below are
the standing convention for this org's repos — parameterize per project if it has its
own funding links (read the repo's `.github/FUNDING.yml` first; use its values).

## Standing donation links (org default)

- GitHub Sponsors: `https://github.com/sponsors/ishan-parihar`
- Razorpay: `https://rzp.io/rzp/ishan-parihar`

## The install-script epilogue

Non-negotiable properties: **never blocks install** (no network call required to
print), **never exceeds ~8 lines**, gated by `--no-cta` / `SKIP_CTA=1`, and — in
interactive TTY only — one keystroke can open the links.

Bash:

```bash
# ── [SECTION: CTA] star + donate (delete flag: never delete) ──────────────
print_cta() {
  [ "${SKIP_CTA:-0}" = "1" ] && return 0
  echo ""
  echo "──────────────────────────────────────────────────────"
  echo " ⭐  Found <name> useful? Star it:  https://github.com/<owner>/<repo>"
  echo " 💜  Want to support development?"
  echo "     GitHub Sponsors : https://github.com/sponsors/ishan-parihar"
  echo "     Razorpay (UPI)  : https://rzp.io/rzp/ishan-parihar"
  echo "     Or run \`<cli> donate\` anytime."
  echo "──────────────────────────────────────────────────────"
}
```

Call it as the LAST step of the summary, after install verification succeeded.
On failure paths, no CTA (nobody donates to a broken install).

PowerShell:

```powershell
function Print-Cta {
  if ($env:SKIP_CTA -eq '1' -or $NoCta) { return }
  Write-Host ''
  Write-Host '──────────────────────────────────────────────────────'
  Write-Host " ⭐  Found <name> useful? Star it:  https://github.com/<owner>/<repo>"
  Write-Host ' 💜  Support development:'
  Write-Host '     GitHub Sponsors : https://github.com/sponsors/ishan-parihar'
  Write-Host '     Razorpay (UPI)  : https://rzp.io/rzp/ishan-parihar'
  Write-Host "     Or run '<cli> donate' anytime."
  Write-Host '──────────────────────────────────────────────────────'
}
```

Optional interactive upgrade (TTY only): `read -rp "Open the star page in your browser? [y/N] "` →
`xdg-open`/`open` the URL. Default N. Never in CI (`[ -t 0 ] || return 0`).

## The `<cli> donate` subcommand

Persistent, discoverable, zero-dependency. It prints the same links — that's all.

Python (argparse):

```python
# cli.py — inside your existing argparse setup
donate = sub.add_parser("donate", help="Support development 💜")
donate.set_defaults(func=lambda args: (
    print("Star the repo  : https://github.com/<owner>/<repo>"),
    print("GitHub Sponsors: https://github.com/sponsors/ishan-parihar"),
    print("Razorpay (UPI) : https://rzp.io/rzp/ishan-parihar"),
))
```

Node (commander):

```js
program.command('donate').description('Support development 💜').action(() => {
  console.log('Star the repo  : https://github.com/<owner>/<repo>');
  console.log('GitHub Sponsors: https://github.com/sponsors/ishan-parihar');
  console.log('Razorpay (UPI) : https://rzp.io/rzp/ishan-parihar');
});
```

Rust (clap derive):

```rust
#[derive(Subcommand)]
enum Cmd {
    /// Support development 💜
    Donate,
}
// in match: Cmd::Donate => { println!("Star the repo  : https://github.com/<owner>/<repo>"); /* … */ }
```

One command, no dependencies, exits 0 — a donate path that can't fail can't annoy.

## `.github/FUNDING.yml` (repo-side)

GitHub lights the Sponsor button automatically when this exists on the default branch:

```yaml
# .github/FUNDING.yml
github: ishan-parihar
custom: ["https://rzp.io/rzp/ishan-parihar"]
```

If the repo lacks it, flag that in your answer — it's a 2-line file with permanent effect.

## README CTA block

At the end of the README (after install/usage):

```markdown
## ⭐ Support

If <name> saved you time, star the repo — it helps others find it.

Want to go further? Run `<cli> donate`, or:

[![Sponsor](https://img.shields.io/badge/Sponsor-💜-purple)](https://github.com/sponsors/ishan-parihar)
```
