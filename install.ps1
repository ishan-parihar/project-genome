# project-genome installer — Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/ishan-parihar/project-genome/main/install.ps1 | iex
#
# Installs the `genome` CLI as a Python package: uv -> pipx -> pip, the same
# chain as install.sh, with the PATH edit done in the Windows registry.
#
# Flags:
#   -Skill        also install the skill bundle into the detected harness dirs
#   -FromGitHub   install the CLI from the Git repo instead of PyPI
#   -NoCta        skip the star/donate epilogue (also: $env:SKIP_CTA = '1')
#   -ForceRoot    allow running as an elevated administrator

param(
    [switch]$Skill,
    [switch]$FromGitHub,
    [switch]$NoCta,
    [switch]$ForceRoot
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Name = 'genome'
$Pkg = 'project-genome'
$Repo = 'https://github.com/ishan-parihar/project-genome.git'
$Branch = 'main'
$TargetName = 'project-genome'

function Info($msg) { Write-Host "==> $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "warn: $msg" -ForegroundColor Yellow }
function Die($msg) {
    Write-Host "error: $msg" -ForegroundColor Red
    Write-Host "      fix it, then re-run this installer."
    exit 1
}

# ── root guard ───────────────────────────────────────────────────────────────
# Root/Administrator-owned files break every later upgrade (the tool writes its
# registry and cards under the user profile), so refuse by default.
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin -and -not $ForceRoot) {
    Die "Don't run as Administrator — this installs into your user profile. Re-run in a normal shell (override: -ForceRoot)."
}

# ── architecture (the registry is the truth under Windows emulation) ────────
$Arch = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').PROCESSOR_ARCHITECTURE
Info "platform: Windows/$Arch"

# ── prerequisites: a Python >= 3.11 interpreter ─────────────────────────────
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
    Die "python is not installed or not on PATH — project-genome needs Python >= 3.11 (stdlib only). Install it from python.org or the Microsoft Store, then re-run."
}
$pyVer = & $py.Source -c 'import sys; print("%d.%d" % sys.version_info[:2])'
$pyOk = & $py.Source -c 'import sys; print(1 if sys.version_info[:2] >= (3, 11) else 0)'
if ($pyOk -ne '1') {
    Die "python is $pyVer; project-genome needs >= 3.11 (it uses tomllib, added in 3.11). Upgrade Python, then re-run."
}
Info "python $pyVer ok"

# ── install: uv -> pipx -> pip ───────────────────────────────────────────────
$installedWith = ''
if ($FromGitHub) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "-FromGitHub needs git — install git, or drop the flag to install from PyPI" }
    Info "installing from the Git repository (unreleased build)"
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv tool install --force --from "git+$Repo" $Pkg; $installedWith = 'uv (from git)'
    }
    elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
        pipx install --force "git+$Repo"; $installedWith = 'pipx (from git)'
    }
    else {
        & $py.Source -m pip install --user --force-reinstall "git+$Repo"; $installedWith = 'pip (from git)'
    }
}
else {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Info "installing with uv"
        uv tool install --force $Pkg 2>$null
        if ($LASTEXITCODE -eq 0) { $installedWith = 'uv' }
        else {
            Warn "uv tool install failed — trying pipx"
            if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
                Die "uv could not install $Pkg and pipx is not installed. Install pipx (pipx install pipx) or uv (winget install --id=astral-sh.uv), then re-run."
            }
            pipx install --force $Pkg; $installedWith = 'pipx'
        }
    }
    elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
        Info "installing with pipx"
        pipx install --force $Pkg; $installedWith = 'pipx'
    }
    else {
        Info "installing with pip --user"
        & $py.Source -m pip install --user --upgrade $Pkg; $installedWith = 'pip --user'
    }
}
if (-not $installedWith) { Die "the install did not report a successful method — see the errors above" }
Info "installed via $installedWith"

# ── PATH (user scope; merge, never overwrite) ───────────────────────────────
# uv and pipx land in %USERPROFILE%\.local\bin on Windows. The PATH edit goes
# to the USER environment variable in the registry, so it survives new shells.
$binDir = Join-Path $env:USERPROFILE '.local\bin'
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $userPath) { $userPath = '' }
if (($userPath -split ';') -notcontains $binDir) {
    [Environment]::SetEnvironmentVariable('Path', ($userPath.TrimEnd(';') + ';' + $binDir), 'User')
    Info "PATH updated for new shells (user scope): $binDir"
}
$env:Path = "$binDir;$env:Path"

# ── verify ──────────────────────────────────────────────────────────────────
$genomeCmd = Get-Command $Name -ErrorAction SilentlyContinue
if (-not $genomeCmd -and (Test-Path (Join-Path $binDir "$Name.exe"))) {
    $genomeCmd = Get-Command (Join-Path $binDir "$Name.exe") -ErrorAction SilentlyContinue
}
if (-not $genomeCmd) { Die "$Name is not on PATH — open a new shell and re-run, or add $binDir to your PATH" }
$versionOut = & $genomeCmd.Source --version 2>&1
if ($versionOut -notmatch '^genome ') { Die "the installed CLI did not run: $versionOut" }
Info "verified: $versionOut ($($genomeCmd.Source))"

# ── skill bundle (optional) ─────────────────────────────────────────────────
if ($Skill) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "-Skill needs git (install git, or drop -Skill)" }
    $roots = @()
    foreach ($d in @("$env:USERPROFILE\.agents\skills", "$env:USERPROFILE\.claude\skills", "$env:USERPROFILE\.codex\skills")) {
        if (Test-Path $d) { $roots += $d }
    }
    if ($roots.Count -eq 0) {
        $roots = @("$env:USERPROFILE\.agents\skills")
        Info "no harness skills directory found — using $($roots[0])"
    }
    foreach ($root in $roots) {
        $dest = Join-Path $root $TargetName
        New-Item -ItemType Directory -Force -Path $root | Out-Null
        if (Test-Path (Join-Path $dest '.git')) {
            git -C $dest fetch origin $Branch --quiet; git -C $dest reset --hard "origin/$Branch" --quiet
            if ($LASTEXITCODE -eq 0) { Info "updated skill: $dest" } else { Warn "could not update $dest" }
        }
        else {
            git clone --depth 1 --branch $Branch $Repo $dest --quiet 2>$null
            if ($LASTEXITCODE -eq 0) { Info "installed skill: $dest" } else { Warn "could not clone the skill into $dest" }
        }
    }
}

# ── summary ─────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host 'project-genome installed.'
Write-Host ''
Write-Host '  genome init --profile software   # scaffold a knowledge genome'
Write-Host '  genome wake                      # orient a fresh agent'
Write-Host '  genome lint                      # check the roles and their mutability'
Write-Host ''
if ($Skill) {
    Write-Host 'The skill bundle is installed too — agents pick up the methodology and references.'
}
else {
    Write-Host 'The CLI is installed. For the agent methodology + references, add -Skill'
    Write-Host '(or: npx skills add ishan-parihar/project-genome --agent ''*'' --skill ''*'' -y).'
}
Write-Host ''

# ── CTA ─────────────────────────────────────────────────────────────────────
if (-not $NoCta -and $env:SKIP_CTA -ne '1') {
    Write-Host '──────────────────────────────────────────────────────'
    Write-Host ' ⭐  Found project-genome useful? Star it:  https://github.com/ishan-parihar/project-genome'
    Write-Host ' 💜  Want to support development?'
    Write-Host '     GitHub Sponsors : https://github.com/sponsors/ishan-parihar'
    Write-Host '     Razorpay (UPI)  : https://rzp.io/rzp/ishan-parihar'
    Write-Host '──────────────────────────────────────────────────────'
}
