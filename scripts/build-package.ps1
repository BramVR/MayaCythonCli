param(
    [string]$EnvPath = ".conda/maya-cython-build",
    [string]$MayaPy = "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $EnvPath))
$condaExe = "C:\Users\ZO\anaconda3\condabin\conda.bat"
$buildRoot = Join-Path $repoRoot "build"
$resolvedBuildRoot = [System.IO.Path]::GetFullPath($buildRoot)

if (-not $resolvedBuildRoot.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean build directory outside the repo: $resolvedBuildRoot"
}

if (-not (Test-Path $envPath)) {
    throw "Conda environment missing: $envPath. Run scripts/create-conda-env.ps1 first."
}

if (-not (Test-Path $MayaPy)) {
    throw "mayapy not found: $MayaPy"
}

$mayaBin = Split-Path $MayaPy -Parent
$mayaRoot = Split-Path $mayaBin -Parent
$mayaInclude = Join-Path $mayaRoot "Python\Include"
$mayaLibDir = Join-Path $mayaRoot "lib"

if (-not (Test-Path $mayaInclude)) {
    $pythonHeader = Get-ChildItem $mayaRoot -Recurse -Filter "Python.h" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pythonHeader) {
        throw "Could not locate Maya Python headers under $mayaRoot"
    }

    $mayaInclude = Split-Path $pythonHeader.FullName -Parent
}

$mayaLib = Get-ChildItem $mayaLibDir -Filter "python*.lib" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -First 1
if (-not $mayaLib) {
    throw "Maya Python import library not found in: $mayaLibDir"
}

$env:MAYA_PYTHON_INCLUDE = $mayaInclude
$env:MAYA_PYTHON_LIBDIR = $mayaLibDir
$env:MAYA_PYTHON_LIBNAME = [System.IO.Path]::GetFileNameWithoutExtension($mayaLib.Name)
$tempRoot = Join-Path $repoRoot "build\tmp"
if (Test-Path $buildRoot) {
    @("lib.*", "bdist.*", "temp.*", "cython") | ForEach-Object {
        Get-ChildItem $buildRoot -Force -Filter $_ -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
    }
}
Get-ChildItem $repoRoot -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
}
New-Item -ItemType Directory -Force $tempRoot | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

Push-Location $repoRoot
try {
    & $condaExe run --prefix $envPath python setup.py bdist_wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Wheel build failed."
    }
}
finally {
    Pop-Location
}
