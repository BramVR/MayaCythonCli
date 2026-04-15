param(
    [string]$MayaPy = "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repoRoot "src"
$py = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$localPython = Join-Path $repoRoot ".conda\curvenet-build\python.exe"

if ($py) {
    & $py.Source -3 -m maya_cython_compile smoke --repo-root $repoRoot --maya-py $MayaPy
}
elseif ($python) {
    & $python.Source -m maya_cython_compile smoke --repo-root $repoRoot --maya-py $MayaPy
}
elseif (Test-Path $localPython) {
    & $localPython -m maya_cython_compile smoke --repo-root $repoRoot --maya-py $MayaPy
}
else {
    throw "No Python interpreter found for CLI wrapper."
}
if ($LASTEXITCODE -ne 0) {
    throw "CLI smoke failed."
}
