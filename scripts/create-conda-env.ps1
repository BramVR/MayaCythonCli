param(
    [string]$Target = "",
    [string]$EnvPath = "",
    [switch]$DryRun,
    [switch]$Force
)

. (Join-Path $PSScriptRoot "_invoke-cli.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cliArgs = @(
    "create-env"
    "--repo-root"
    $repoRoot
    if ($Target) { "--target"; $Target }
    if ($EnvPath) { "--env-path"; $EnvPath }
    if ($DryRun) { "--dry-run" }
    if ($Force) { "--force" }
)

Invoke-MayaCythonCompileCli -CliArgs $cliArgs -EnvPath $EnvPath
