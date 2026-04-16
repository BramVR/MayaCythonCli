param(
    [string]$EnvPath = ".conda/maya-cython-build",
    [string]$MayaPy = "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe",
    [switch]$DryRun,
    [switch]$Force
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repoRoot "src"
$py = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$resolvedEnvPath = if ([System.IO.Path]::IsPathRooted($EnvPath)) {
    $EnvPath
}
else {
    Join-Path $repoRoot ($EnvPath -replace "/", "\")
}
$localPython = Join-Path $resolvedEnvPath "python.exe"

if (Test-Path $localPython) {
    & $localPython -m maya_cython_compile smoke --repo-root $repoRoot --env-path $EnvPath --maya-py $MayaPy @(
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
elseif ($py) {
    & $py.Source -3 -m maya_cython_compile smoke --repo-root $repoRoot --env-path $EnvPath --maya-py $MayaPy @(
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
elseif ($python) {
    & $python.Source -m maya_cython_compile smoke --repo-root $repoRoot --env-path $EnvPath --maya-py $MayaPy @(
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
else {
    throw "No Python interpreter found for CLI wrapper."
}
if ($LASTEXITCODE -ne 0) {
    throw "CLI smoke failed."
}
