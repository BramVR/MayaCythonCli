param(
    [string]$EnvPath = ".conda/maya-cython-build"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repoRoot "src"
$py = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$localPython = Join-Path $repoRoot ".conda\curvenet-build\python.exe"

if ($py) {
    & $py.Source -3 -m maya_cython_compile create-env --repo-root $repoRoot --env-path $EnvPath
}
elseif ($python) {
    & $python.Source -m maya_cython_compile create-env --repo-root $repoRoot --env-path $EnvPath
}
elseif (Test-Path $localPython) {
    & $localPython -m maya_cython_compile create-env --repo-root $repoRoot --env-path $EnvPath
}
else {
    throw "No Python interpreter found for CLI wrapper."
}
if ($LASTEXITCODE -ne 0) {
    throw "CLI create-env failed."
}
