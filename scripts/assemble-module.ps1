param(
    [string]$ModuleName = "MayaTool",
    [string]$MayaVersion = "2025",
    [switch]$DryRun,
    [switch]$Force
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repoRoot "src"
$py = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$localPython = Join-Path $repoRoot ".conda\curvenet-build\python.exe"

if (Test-Path $localPython) {
    & $localPython -m maya_cython_compile assemble --repo-root $repoRoot --module-name $ModuleName --maya-version $MayaVersion @(
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
elseif ($py) {
    & $py.Source -3 -m maya_cython_compile assemble --repo-root $repoRoot --module-name $ModuleName --maya-version $MayaVersion @(
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
elseif ($python) {
    & $python.Source -m maya_cython_compile assemble --repo-root $repoRoot --module-name $ModuleName --maya-version $MayaVersion @(
        if ($DryRun) { "--dry-run" }
        if ($Force) { "--force" }
    )
}
else {
    throw "No Python interpreter found for CLI wrapper."
}
if ($LASTEXITCODE -ne 0) {
    throw "CLI assemble failed."
}
