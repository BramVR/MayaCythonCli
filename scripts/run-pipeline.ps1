param(
    [string]$Target = "",
    [string]$EnvPath = "",
    [string]$MayaPy = "",
    [switch]$EnsureEnv,
    [switch]$SkipSmoke,
    [switch]$SkipAssemble,
    [switch]$DryRun,
    [switch]$Force
)

. (Join-Path $PSScriptRoot "_invoke-cli.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cliArgs = @(
    "run"
    "--repo-root"
    $repoRoot
    if ($Target) { "--target"; $Target }
    if ($EnvPath) { "--env-path"; $EnvPath }
    if ($MayaPy) { "--maya-py"; $MayaPy }
    if ($EnsureEnv) { "--ensure-env" }
    if ($SkipSmoke) { "--skip-smoke" }
    if ($SkipAssemble) { "--skip-assemble" }
    if ($DryRun) { "--dry-run" }
    if ($Force) { "--force" }
)

Invoke-MayaCythonCompileCli -CliArgs $cliArgs -EnvPath $EnvPath
