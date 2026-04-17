param(
    [string]$Target = "",
    [string]$EnvPath = "",
    [string]$ModuleName = "",
    [string]$MayaVersion = "",
    [switch]$DryRun,
    [switch]$Force
)

. (Join-Path $PSScriptRoot "_invoke-cli.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cliArgs = @(
    "assemble"
    "--repo-root"
    $repoRoot
    if ($Target) { "--target"; $Target }
    if ($EnvPath) { "--env-path"; $EnvPath }
    if ($ModuleName) { "--module-name"; $ModuleName }
    if ($MayaVersion) { "--maya-version"; $MayaVersion }
    if ($DryRun) { "--dry-run" }
    if ($Force) { "--force" }
)

Invoke-MayaCythonCompileCli -CliArgs $cliArgs -EnvPath $EnvPath
