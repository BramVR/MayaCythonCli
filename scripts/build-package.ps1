param(
    [string]$Target = "",
    [string]$EnvPath = "",
    [string]$MayaPy = "",
    [switch]$DryRun,
    [switch]$Force
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repoRoot "src"
$py = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$localPython = $null
if ($EnvPath) {
    $resolvedEnvPath = if ([System.IO.Path]::IsPathRooted($EnvPath)) {
        $EnvPath
    }
    else {
        Join-Path $repoRoot ($EnvPath -replace "/", "\")
    }
    $localPython = Join-Path $resolvedEnvPath "python.exe"
}

if ($localPython -and (Test-Path $localPython)) {
    & $localPython -m maya_cython_compile build --repo-root $repoRoot @(
        if ($Target) { "--target"; $Target }
        if ($EnvPath) { "--env-path"; $EnvPath }
        if ($MayaPy) { "--maya-py"; $MayaPy }
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
elseif ($py) {
    & $py.Source -3 -m maya_cython_compile build --repo-root $repoRoot @(
        if ($Target) { "--target"; $Target }
        if ($EnvPath) { "--env-path"; $EnvPath }
        if ($MayaPy) { "--maya-py"; $MayaPy }
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
elseif ($python) {
    & $python.Source -m maya_cython_compile build --repo-root $repoRoot @(
        if ($Target) { "--target"; $Target }
        if ($EnvPath) { "--env-path"; $EnvPath }
        if ($MayaPy) { "--maya-py"; $MayaPy }
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
else {
    throw "No Python interpreter found for CLI wrapper."
}
if ($LASTEXITCODE -ne 0) {
    throw "CLI build failed."
}
