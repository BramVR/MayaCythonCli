param(
    [string]$EnvPath = ".conda/maya-cython-build"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $EnvPath))
$condaExe = "C:\Users\ZO\anaconda3\condabin\conda.bat"

if (-not (Test-Path $condaExe)) {
    throw "Conda was not found at $condaExe"
}

& $condaExe env create --prefix $envPath --force --file (Join-Path $repoRoot "environment.yml")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create Conda environment at $envPath"
}

Write-Host "Created Conda environment at $envPath"
