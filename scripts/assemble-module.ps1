param(
    [string]$ModuleName = "GGMayaTool",
    [string]$MayaVersion = "2025"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$config = Get-Content (Join-Path $repoRoot "build-config.json") | ConvertFrom-Json
$distributionName = $config.distribution_name.Replace("-", "_")
$packageName = $config.package_name
$version = $config.version
$distDir = Join-Path $repoRoot "dist"
$wheel = Get-ChildItem $distDir -Filter "$distributionName-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $wheel) {
    throw "No built wheel found in $distDir"
}

$moduleRoot = Join-Path $distDir "module\$ModuleName"
$contentsRoot = Join-Path $moduleRoot "contents"
$scriptsRoot = Join-Path $contentsRoot "scripts"
$zipPath = Join-Path $moduleRoot "package.zip"

New-Item -ItemType Directory -Force $scriptsRoot | Out-Null
Copy-Item -LiteralPath $wheel.FullName -Destination $zipPath -Force
Expand-Archive -LiteralPath $zipPath -DestinationPath $scriptsRoot -Force

$modPath = Join-Path $moduleRoot "$ModuleName.mod"
$modText = @"
+ MAYAVERSION:$MayaVersion PLATFORM:win64 $ModuleName $version .\contents
"@
Set-Content -LiteralPath $modPath -Value $modText -NoNewline

Write-Host "Module assembled at $moduleRoot"
