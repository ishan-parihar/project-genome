# Embedded CLI updater architecture

This reference is the update contract for CLI applications across the package
suite. The installer bootstraps an application; the installed application owns
its update command. A shell installer alone is not an update mechanism.

## Decision: follow the installation owner

An updater may replace an executable only when the application owns that file.
Record the install source in a small, non-secret receipt such as
`install-origin.json` beside the executable or in the app's data directory:

```json
{
  "schema": 1,
  "application": "example-cli",
  "source": "release-binary",
  "channel": "stable",
  "target": "linux-x86_64-musl",
  "update_origin": "https://updates.example.com"
}
```

Use one suite-wide target path convention:
`apps/<application>/<channel>/<os>-<arch>-<abi>/<version>/<artifact>`. For
example, `apps/example-cli/stable/linux-x86_64-musl/1.4.2/example-cli`. Keep
versioned artifacts immutable. Each application delegates its target paths to
its own role; a package's CI cannot publish another package's targets.

Use these rules:

| Install source | `app update` behavior |
|---|---|
| Direct binary installed by the project's installer | Verify and replace through the embedded updater |
| Python, Node, Rust, or distro package manager | Delegate to that manager or print its exact upgrade command; never overwrite manager-owned files |
| Container image | Pull a digest-pinned image and let Compose/Kubernetes perform health checks and rollback |
| Unknown source or unwritable install directory | Show the available version and the install command; do not guess or invoke `sudo` |

Package managers already have trusted metadata and ownership records. Do not
layer a second binary updater over a `pipx`, npm, Cargo, Homebrew, winget, or
distro-owned installation. A standalone bundle installed by a project script is
different: it can use the project's update client.

## Suite standard: TUF metadata, GitHub Releases as the public mirror

Use [The Update Framework (TUF)](https://github.com/theupdateframework/specification)
as the suite-wide trust and metadata protocol for self-updating release
binaries. TUF's root, timestamp, snapshot, and targets roles bind metadata and
artifacts with signatures, version counters, expiry, lengths, and hashes. The
client rejects stale metadata, rollback, freeze, and mix-and-match attacks. Root
rotation is verified against thresholds from both the old and new trusted root.

Host one static TUF repository on a stable HTTPS origin for the suite. Keep
GitHub Releases as the human-facing release page and a convenient mirror of the
same artifacts. The updater trusts the TUF repository, not a mutable GitHub
`latest` pointer or a checksum file fetched beside the binary. GitHub documents
`/releases/latest` as a stable release link and
`/releases/latest/download/<asset>` as a latest asset link; these are suitable
for a bootstrap path, but TUF metadata becomes the trust authority.

Use a shared suite root with per-application delegated target roles:

- Keep the root private keys offline, on separate hardware, with a threshold
  such as two of three required signatures. Ship a pinned root metadata file in
  every installer and package build.
- Delegate each application and release channel to a role with a narrow target
  path. CI for one app must not be able to publish another app's targets.
- Protect release publishing with a GitHub Actions environment and short-lived
  workload identity. Use the role key for the app's delegated targets; do not
  put a long-lived signing secret in a repository variable.
- Publish timestamp metadata frequently with a short expiry. Publish snapshot
  and targets metadata when a release changes. Rotate root keys by publishing
  each next root version signed by the required old-root and new-root
  thresholds.
- Keep the last known good targets available. Publish a rollback as a new
  metadata version that intentionally selects the prior artifact; never lower
  metadata version counters.
- Attach GitHub build provenance and an SBOM to the human-facing release as
  extra supply-chain evidence. They supplement TUF; they do not replace the
  updater's repository signatures.

Use the maintained TUF client implementation for each language. Do not write a
custom metadata parser or signature verifier. The protocol's client workflow
is root → timestamp → snapshot → targets → artifact. Each step verifies the
previously trusted role, metadata version, expiry, and declared hashes before
the next download.

Persist TUF's trusted root and highest accepted metadata versions in the
application's private state directory. Serialize updates with a per-install
lock so two CLI invocations cannot race over metadata or the executable. A
failed refresh must leave both the trusted state and installed program intact.
Treat expired metadata, a clock that makes metadata appear expired, and missing
or reset trust state after initialization as a clear update failure; never
silently bootstrap a fresh trust root from the same release host.

## Embedded command contract

Use `app update` as the canonical command. Keep an existing `app upgrade` as an
alias so users do not lose muscle memory. `app update` should support:

```text
app update [--check] [--channel stable|preview] [--version VERSION]
           [--allow-downgrade] [--restart] [--json]
```

- Stable is the default channel. Preview/beta channels require an explicit
  choice and use separate delegated targets.
- `--check` downloads and verifies metadata, prints current and available
  versions, and changes nothing. It must not download an artifact.
- `--version` pins a specific artifact. Downgrades require an explicit
  `--allow-downgrade` flag.
- `--restart` is explicit for services. A direct CLI update should not silently
  kill a daemon, shell, editor, or other running process.
- `--json` returns the same fields across apps: application, installed version,
  available version, channel, action, and result.
- No update request runs at ordinary startup by default. If a product offers
  background checks, make them opt-in, cache their result, expose an off switch,
  and never download or replace code without an explicit policy.
- Use stable exit classes consistently: `0` for success/current, `1` for
  network/trust/install failure, and `2` for invalid usage. Preserve each
  application's existing higher-level CLI conventions where they differ.

## Safe artifact transaction

For a direct binary, implement the update as a transaction:

1. Acquire an exclusive per-install lock. Use bounded HTTPS timeouts and byte
   limits. Follow redirects only to the configured update origin and its
   explicitly approved artifact CDN. Send no provider tokens, environment
   secrets, or unrelated credentials.
2. Update and verify TUF root metadata first, then timestamp, snapshot, and the
   selected target role. Refuse expired metadata, version rollback, wrong
   application/channel/platform, missing target, or inconsistent snapshot.
3. Download the target into a uniquely named temporary file beside the current
   executable. Enforce the declared size and hash while streaming; do not load a
   large artifact into memory. Preserve the existing executable's permissions.
4. Verify the artifact's target metadata and expected application version. Run
   a bounded, side-effect-free candidate probe such as `app --version`. Never
   execute an installer script from the release asset.
5. Flush the candidate and its parent directory, then atomically replace the
   executable on the same filesystem. Keep the previous executable until the
   post-update check succeeds; restore it if the managed service fails to start
   or its health check fails.
6. Report that the running process still has its old image unless the updater
   explicitly restarted the service. Retain enough state to diagnose a failed
   update, but remove temporary files and stale rollback copies after success.

On Windows, a running executable generally cannot replace itself. Stage the
verified binary, start a small signed helper that waits for the parent to exit,
replace the file, and relaunch; otherwise delegate to MSIX/winget or another
package manager. Do not weaken verification to make replacement easier.

## Release publication contract

CI for every CLI package must:

1. Test the exact tagged source and build for a declared OS/architecture/libc
   matrix. Do not let the release runner's CPU features leak into a portable
   artifact.
2. Generate versioned TUF targets with exact file sizes and hashes, update
   snapshot/timestamp metadata, and publish using only the package's delegated
   release authority.
3. Publish matching human-facing GitHub Release assets, build provenance, and
   an SBOM. Reject a release when the binary's reported version differs from
   the tag or its metadata names another package or target.
4. Verify a previous-version client can discover and install the new target;
   verify a corrupt target, expired metadata, rollback metadata, and a wrong
   platform target are refused without changing the installed binary.
5. Test service restart and rollback separately from binary replacement. No
   release is complete merely because upload succeeded.

Use a canary channel before stable for high-impact applications. Keep stable
metadata and target locations immutable by version; only the TUF timestamp is
expected to move frequently.

## Language and app profiles

| Profile | Embedded updater rule |
|---|---|
| Rust/Go standalone binary | Link a maintained TUF client; keep update I/O out of the request-serving hot path; stage beside the executable and use an OS-safe atomic replacement |
| Python CLI | If installed from PyPI/pipx/uv, delegate to that tool; for a standalone binary bundle, use the TUF client and replace the bundle entry point transactionally |
| Node CLI | If installed globally from npm/bun, delegate to the package manager; for a bundled executable, use the TUF client and keep the launcher stable while swapping its versioned payload |
| MCP server | Update the underlying package using the same rule; restart only after the new command passes its stdio/HTTP health check |
| systemd service | The CLI update changes the binary only; a timer may call update-only mode and restart only a service that was active before the update |
| container app | Resolve a signed/digest-pinned image, update the orchestrator, wait for health, then restore the prior digest on failure |

## Migration path for existing release redirect updaters

Some apps already fetch a stable GitHub release redirect and verify a
`SHA256SUMS` asset. Keep that route operational while introducing TUF, but label
it as a compatibility path: a checksum from the same release origin proves
byte consistency, not publisher identity, and latest redirects alone do not
provide rollback or freeze protection.

Migration order:

1. Add the shared TUF root and target repository; publish the current stable
   artifacts as TUF targets without removing GitHub assets.
2. Ship a client that can verify TUF metadata and fall back only to the old
   checksum path for versions that predate the trusted root. Never let an
   unverified fallback override a successful TUF refusal.
3. Roll the embedded TUF root into each app's release and installer. Measure
   clients on stable and preview channels.
4. Make TUF required for new installs and upgrades. Retire the checksum-only
   fallback after the oldest supported client has crossed the migration window.

The current Artificial Route updater is an interim direct-release client: it
uses GitHub's stable-release redirect, a size-bounded `SHA256SUMS` download, an
allow-listed HTTPS redirect, version verification, and an atomic replacement.
Its installer can optionally verify the GitHub Actions build attestation with
`gh`. It is Linux x86-64 only and does not yet use TUF metadata.

## Completion checklist for `install-script-creator`

- [ ] Read this reference for every CLI with a self-update request.
- [ ] Identify the install owner before implementing a self-replacing command.
- [ ] Keep the canonical update command in the CLI; use the installer only to
      bootstrap and provision it.
- [ ] Test current-version no-op, newest-version install, wrong target, bad
      digest/signature, interrupted download, unwritable install path, and
      service restart/rollback where applicable.
- [ ] Document supported platforms, update source, restart behavior, timer
      policy, downgrade behavior, and uninstall effects in the README.
