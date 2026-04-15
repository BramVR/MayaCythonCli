param(
    [string]$MayaPy = "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$config = Get-Content (Join-Path $repoRoot "build-config.json") | ConvertFrom-Json
$distributionName = $config.distribution_name.Replace("-", "_")
$packageName = $config.package_name
$distDir = Join-Path $repoRoot "dist"
$wheel = Get-ChildItem $distDir -Filter "$distributionName-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $wheel) {
    throw "No built wheel found in $distDir"
}

if (-not (Test-Path $MayaPy)) {
    throw "mayapy not found: $MayaPy"
}

$smokeRoot = Join-Path $repoRoot "build\smoke"
$extractDir = Join-Path $smokeRoot "wheel"
$zipPath = Join-Path $smokeRoot "wheel.zip"
$resolvedExtractDir = [System.IO.Path]::GetFullPath($extractDir)
$resolvedRepoRoot = [System.IO.Path]::GetFullPath($repoRoot)

if (-not $resolvedExtractDir.StartsWith($resolvedRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to extract outside the repo: $resolvedExtractDir"
}

New-Item -ItemType Directory -Force $smokeRoot | Out-Null
if (Test-Path $extractDir) {
    Remove-Item -LiteralPath $extractDir -Recurse -Force
}
Copy-Item -LiteralPath $wheel.FullName -Destination $zipPath -Force
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

$env:PYTHONPATH = $extractDir
& $MayaPy -c "from pathlib import Path; import importlib; pkg = importlib.import_module('$packageName'); cy = importlib.import_module('$packageName._cy_logic'); res = importlib.import_module('$packageName._resources'); print(pkg.show_ui()); print(cy.normalize_node_name('|group|ns:ctrl')); print(Path(res.resource_path('tool_manifest.json')).exists())"
if ($LASTEXITCODE -ne 0) {
    throw "Smoke test failed."
}
